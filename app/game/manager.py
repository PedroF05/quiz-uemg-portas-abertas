"""Gerenciamento das salas em memória."""

import asyncio
import random
import secrets
import uuid

from ..config import Settings, settings as app_settings
from ..db import repository
from ..domain.models import (
    AnswerMode,
    CreateRoomRequest,
    JoinInfoResponse,
    JoinTeamInfo,
    Mode,
    Option,
    Phase,
    Player,
    PlayerSummary,
    Question,
    Room,
    Team,
)
from ..quiz import bank
from .engine import EngineError, GameEngine, RoomSnapshotDict

CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 6


def _new_code() -> str:
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))


class RoomManager:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._engines: dict[str, GameEngine] = {}
        self._room_locks: dict[str, asyncio.Lock] = {}
        self._lock = asyncio.Lock()

    def room_lock(self, code: str) -> asyncio.Lock:
        normalized = code.upper()
        if normalized not in self._room_locks:
            self._room_locks[normalized] = asyncio.Lock()
        return self._room_locks[normalized]

    async def create(self, request: CreateRoomRequest) -> tuple[str, str, RoomSnapshotDict]:
        if request.mode is Mode.MOBILE:
            answer_mode = AnswerMode.SIMULTANEOUS
        else:
            answer_mode = request.answer_mode or AnswerMode.ALTERNATE

        if request.generated_questions:
            questions: list[Question] = []
            for i, item in enumerate(request.generated_questions):
                qid = f"gen_{i + 1}"
                options_raw: list[tuple[str, bool]] = [(item.correct, True)] + [
                    (distractor, False) for distractor in item.distractors
                ]
                random.shuffle(options_raw)
                options: list[Option] = []
                correct_id = ""
                for opt_index, (text, is_correct) in enumerate(options_raw):
                    option_id = f"o_{opt_index + 1}"
                    options.append(Option(id=option_id, text=text))
                    if is_correct:
                        correct_id = option_id
                questions.append(
                    Question(
                        id=qid,
                        category=item.category,
                        prompt=item.prompt,
                        options=options,
                        correct_option_id=correct_id,
                    )
                )
            theme_name = request.theme_id.strip() or "Tema Livre"
        else:
            questions, theme_name = bank.build_questions(
                self.settings, request.theme_id, request.n
            )

        names = [
            (name.strip() or f"Equipe {i + 1}")[:18]
            for i, name in enumerate(request.team_names)
        ]
        teams = [
            Team(id=uuid.uuid4().hex, name=name, players=[])
            for name in names
        ]
        host_token = secrets.token_urlsafe(24)

        async with self._lock:
            code = _new_code()
            while code in self._engines:
                code = _new_code()

            room = Room(
                code=code,
                host_token=host_token,
                mode=request.mode,
                answer_mode=answer_mode,
                teams=teams,
                questions=questions,
                theme=theme_name,
                provider=self.settings.llm_provider,
                question_time=self.settings.question_time,
            )
            engine = GameEngine(room, self.settings)
            self._engines[code] = engine

        return code, host_token, engine.snapshot()

    def get(self, code: str, host_token: str | None = None) -> GameEngine:
        engine = self._engines.get(code.upper())
        if engine is None:
            raise EngineError("Sala não encontrada.", 404)
        if host_token is not None and not secrets.compare_digest(
            engine.room.host_token, host_token
        ):
            raise EngineError("Token do host inválido.", 403)
        return engine

    def state(self, code: str) -> RoomSnapshotDict:
        return self.get(code).snapshot()

    def answer(self, code: str, host_token: str, team_id: str, option_id: str) -> RoomSnapshotDict:
        engine = self.get(code, host_token)
        return engine.answer(team_id, option_id)

    def next_question(self, code: str, host_token: str) -> RoomSnapshotDict:
        engine = self.get(code, host_token)
        state = engine.next_question()
        self._persist_if_finished(engine)
        return state

    def start_game(self, code: str, host_token: str) -> RoomSnapshotDict:
        engine = self.get(code, host_token)
        return engine.start_game()

    def add_player(self, code: str, nickname: str, team_id: str) -> tuple[Player, RoomSnapshotDict]:
        engine = self.get(code)
        room = engine.room

        if room.phase is not Phase.LOBBY:
            raise EngineError("A sala não está no lobby.", 400)

        clean_name = nickname.strip()
        if not (1 <= len(clean_name) <= 18):
            raise EngineError("Apelido deve ter entre 1 e 18 caracteres.", 400)

        team = room.team(team_id)
        if team is None:
            raise EngineError("Equipe não encontrada.", 404)

        if len(team.players) >= self.settings.max_team_size:
            raise EngineError("Equipe cheia.", 409)

        player_id = uuid.uuid4().hex
        player_token = secrets.token_urlsafe(24)
        player = Player(
            id=player_id,
            token=player_token,
            nickname=clean_name,
            team_id=team_id,
        )

        team.players.append(PlayerSummary(id=player_id, nickname=clean_name))
        room.players_by_token[player_token] = player
        room.players_by_id[player_id] = player

        return player, engine.snapshot()

    def get_join_info(self, code: str) -> JoinInfoResponse:
        engine = self.get(code)
        room = engine.room
        team_infos = [
            JoinTeamInfo(
                id=t.id,
                name=t.name,
                members=len(t.players),
                capacity=self.settings.max_team_size,
            )
            for t in room.teams
        ]
        return JoinInfoResponse(
            code=room.code,
            mode=room.mode.value,
            phase=room.phase.value,
            theme=room.theme,
            teams=team_infos,
        )

    def get_player(self, code: str, token: str) -> Player | None:
        try:
            engine = self.get(code)
            return engine.room.players_by_token.get(token)
        except EngineError:
            return None

    def persist_if_finished(self, engine: GameEngine) -> None:
        self._persist_if_finished(engine)

    def _persist_if_finished(self, engine: GameEngine) -> None:
        room = engine.room
        if room.phase is Phase.FINISHED and not room.persisted:
            repository.save_match(self.settings.db_path, room)
            room.persisted = True


manager = RoomManager(app_settings)
