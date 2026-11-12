"""Máquina de estados da partida. O servidor é a fonte de verdade."""

from datetime import datetime
import time
from typing import TypedDict

from ..domain.models import (
    AnswerMode,
    AnswerRecord,
    Phase,
    Room,
    Team,
)
from ..domain.scoring import points_for


class EngineError(Exception):
    def __init__(self, message: str, status_code: int = 409) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class OptionDict(TypedDict):
    id: str
    text: str


class QuestionDict(TypedDict):
    id: str
    category: str
    prompt: str
    options: list[OptionDict]


class PlayerDict(TypedDict):
    id: str
    nickname: str


class TeamDict(TypedDict):
    id: str
    name: str
    score: int
    answered: bool
    players: list[PlayerDict]


class AnswerDict(TypedDict):
    team_id: str
    option_id: str
    correct: bool
    points: int
    elapsed: float


class RevealDict(TypedDict):
    correct_option_id: str
    answers: list[AnswerDict]


class RoomSnapshotDict(TypedDict):
    code: str
    mode: str
    answer_mode: str
    phase: str
    index: int
    total: int
    theme: str
    provider: str
    seconds_left: float
    turn_team_id: str | None
    teams: list[TeamDict]
    question: QuestionDict | None
    reveal: RevealDict | None
    winners: list[str]


class GameEngine:
    """Controla uma partida: pergunta atual, relógio, respostas e pontuação."""

    def __init__(self, room: Room, settings, clock=time.monotonic) -> None:
        self.room = room
        self.settings = settings
        self._clock = clock
        if self.room.phase is not Phase.LOBBY:
            self._open_question()

    def _open_question(self) -> None:
        room = self.room
        room.phase = Phase.QUESTION
        room.answers = []
        for team in room.teams:
            team.answered = False

        room.deadline = self._clock() + room.question_time
        if room.answer_mode is AnswerMode.ALTERNATE and room.teams:
            room.turn_team_id = room.teams[room.index % len(room.teams)].id
        else:
            room.turn_team_id = None

    def _eligible_teams(self) -> list[Team]:
        room = self.room
        if room.answer_mode is AnswerMode.ALTERNATE:
            return [t for t in room.teams if t.id == room.turn_team_id]
        return list(room.teams)

    def _reveal(self) -> None:
        self.room.phase = Phase.REVEAL

    def _check_timeout(self) -> bool:
        room = self.room
        if room.phase is Phase.QUESTION and self._clock() >= room.deadline:
            self._reveal()
            return True
        return False

    def start_game(self) -> RoomSnapshotDict:
        if self.room.phase is not Phase.LOBBY:
            raise EngineError("A partida já foi iniciada.")
        total_players = sum(len(team.players) for team in self.room.teams)
        if total_players == 0:
            raise EngineError("Não há jogadores na sala para iniciar a partida.")
        self._open_question()
        return self.snapshot()

    def timeout_reveal(self) -> RoomSnapshotDict:
        if self.room.phase is Phase.QUESTION:
            self._reveal()
        return self.snapshot()

    def answer(self, team_id: str, option_id: str) -> RoomSnapshotDict:
        room = self.room
        self._check_timeout()

        if room.phase is not Phase.QUESTION:
            raise EngineError("A pergunta não está aberta.")

        team = room.team(team_id)
        if team is None:
            raise EngineError("Equipe não encontrada.", 404)
        if team.answered:
            raise EngineError("Esta equipe já respondeu.")
        if team_id not in {t.id for t in self._eligible_teams()}:
            raise EngineError("Não é a vez desta equipe.")

        question = room.current
        if option_id not in {o.id for o in question.options}:
            raise EngineError("Opção inválida.", 400)

        elapsed = max(0.0, room.question_time - (room.deadline - self._clock()))
        correct = option_id == question.correct_option_id
        points = (
            points_for(
                elapsed,
                room.question_time,
                base=self.settings.base_points,
                bonus=self.settings.speed_bonus,
            )
            if correct
            else 0
        )

        team.answered = True
        team.score += points
        room.answers.append(
            AnswerRecord(
                team_id=team_id,
                option_id=option_id,
                correct=correct,
                points=points,
                elapsed=round(elapsed, 3),
            )
        )

        if all(t.answered for t in self._eligible_teams()):
            self._reveal()

        return self.snapshot()

    def next_question(self) -> RoomSnapshotDict:
        room = self.room
        self._check_timeout()

        if room.phase is Phase.LOBBY:
            raise EngineError("A partida não foi iniciada.")
        if room.phase is Phase.QUESTION:
            raise EngineError("A pergunta atual ainda está aberta.")
        if room.phase is Phase.FINISHED:
            return self.snapshot()

        if room.index + 1 >= len(room.questions):
            room.phase = Phase.FINISHED
            room.finished_at = datetime.now()
            return self.snapshot()

        room.index += 1
        self._open_question()
        return self.snapshot()

    def snapshot(self) -> RoomSnapshotDict:
        room = self.room
        self._check_timeout()

        seconds_left = 0.0
        if room.phase is Phase.QUESTION:
            seconds_left = max(0.0, room.deadline - self._clock())

        max_score = max((t.score for t in room.teams), default=0)
        winners = [t.name for t in room.teams if t.score == max_score]

        question_data: QuestionDict | None = None
        if room.phase is not Phase.LOBBY:
            question = room.current
            question_data = {
                "id": question.id,
                "category": question.category,
                "prompt": question.prompt,
                "options": [
                    {"id": o.id, "text": o.text} for o in question.options
                ],
            }

        teams_data: list[TeamDict] = [
            {
                "id": t.id,
                "name": t.name,
                "score": t.score,
                "answered": t.answered,
                "players": [
                    {"id": p.id, "nickname": p.nickname} for p in t.players
                ],
            }
            for t in room.teams
        ]

        reveal_data: RevealDict | None = None
        if room.phase in (Phase.REVEAL, Phase.FINISHED) and room.phase is not Phase.LOBBY:
            reveal_data = {
                "correct_option_id": room.current.correct_option_id,
                "answers": [
                    {
                        "team_id": a.team_id,
                        "option_id": a.option_id,
                        "correct": a.correct,
                        "points": a.points,
                        "elapsed": a.elapsed,
                    }
                    for a in room.answers
                ],
            }

        state: RoomSnapshotDict = {
            "code": room.code,
            "mode": room.mode.value,
            "answer_mode": room.answer_mode.value,
            "phase": room.phase.value,
            "index": room.index,
            "total": len(room.questions),
            "theme": room.theme,
            "provider": room.provider,
            "seconds_left": round(seconds_left, 2),
            "turn_team_id": room.turn_team_id,
            "teams": teams_data,
            "question": question_data,
            "reveal": reveal_data,
            "winners": winners if room.phase is Phase.FINISHED else [],
        }

        return state
