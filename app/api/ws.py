"""Endpoints e gerenciamento de conexões WebSocket."""

import asyncio
import json
import secrets
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..domain.models import Phase, Player
from ..game.engine import EngineError
from ..game.manager import manager
from .protocol import (
    ErrorMessage,
    HostNextMessage,
    HostStartMessage,
    HostStateMessage,
    OptionSnapshot,
    PlayerAnswerMessage,
    PlayerFinishedMessage,
    PlayerLobbyMessage,
    PlayerQuestionMessage,
    PlayerRevealAnswer,
    PlayerRevealMessage,
    PlayerTeamLockedMessage,
    PlayerTeamScore,
)

router = APIRouter(prefix="/ws", tags=["websocket"])


class WebSocketHub:
    def __init__(self) -> None:
        self.host_connections: dict[str, set[WebSocket]] = {}
        self.player_connections: dict[str, dict[str, WebSocket]] = {}
        self.question_timers: dict[str, asyncio.Task[None]] = {}
        self._lock = asyncio.Lock()

    async def register_host(self, room_code: str, websocket: WebSocket) -> None:
        async with self._lock:
            code = room_code.upper()
            if code not in self.host_connections:
                self.host_connections[code] = set()
            self.host_connections[code].add(websocket)

    async def unregister_host(self, room_code: str, websocket: WebSocket) -> None:
        async with self._lock:
            code = room_code.upper()
            if code in self.host_connections:
                self.host_connections[code].discard(websocket)
                if not self.host_connections[code]:
                    del self.host_connections[code]

    async def register_player(
        self, room_code: str, player_id: str, websocket: WebSocket
    ) -> None:
        async with self._lock:
            code = room_code.upper()
            if code not in self.player_connections:
                self.player_connections[code] = {}
            old_socket = self.player_connections[code].get(player_id)
            if old_socket is not None and old_socket != websocket:
                try:
                    await old_socket.close()
                except Exception:
                    pass
            self.player_connections[code][player_id] = websocket

    async def unregister_player(
        self, room_code: str, player_id: str, websocket: WebSocket
    ) -> None:
        async with self._lock:
            code = room_code.upper()
            if code in self.player_connections:
                current_socket = self.player_connections[code].get(player_id)
                if current_socket == websocket:
                    del self.player_connections[code][player_id]
                if not self.player_connections[code]:
                    del self.player_connections[code]

    def cancel_timer(self, room_code: str) -> None:
        code = room_code.upper()
        timer = self.question_timers.pop(code, None)
        if timer is not None and not timer.done():
            timer.cancel()

    def schedule_timer(
        self, room_code: str, question_index: int, duration: float
    ) -> None:
        code = room_code.upper()
        self.cancel_timer(code)

        async def _timer_runner() -> None:
            try:
                await asyncio.sleep(duration)
                async with manager.room_lock(code):
                    engine = manager.get(code)
                    if (
                        engine.room.phase is Phase.QUESTION
                        and engine.room.index == question_index
                    ):
                        engine.timeout_reveal()
                        await self.notify_room_state(code)
                        await self.broadcast_players_reveal(code)
            except asyncio.CancelledError:
                pass

        self.question_timers[code] = asyncio.create_task(_timer_runner())

    async def notify_room_state(self, room_code: str) -> None:
        code = room_code.upper()
        sockets = list(self.host_connections.get(code, set()))
        if not sockets:
            return
        snapshot_data = manager.state(code)
        message = HostStateMessage.from_snapshot(snapshot_data).model_dump_json()
        for ws in sockets:
            try:
                await ws.send_text(message)
            except Exception:
                pass

    async def broadcast_players_question(self, room_code: str) -> None:
        code = room_code.upper()
        player_map = self.player_connections.get(code, {})
        if not player_map:
            return
        engine = manager.get(code)
        question = engine.room.current
        message = PlayerQuestionMessage(
            index=engine.room.index,
            total=len(engine.room.questions),
            category=question.category,
            prompt=question.prompt,
            options=[
                OptionSnapshot(id=o.id, text=o.text)
                for o in question.options
            ],
            seconds_left=float(engine.room.question_time),
        ).model_dump_json()
        for ws in list(player_map.values()):
            try:
                await ws.send_text(message)
            except Exception:
                pass

    async def broadcast_players_reveal(self, room_code: str) -> None:
        code = room_code.upper()
        player_map = self.player_connections.get(code, {})
        if not player_map:
            return
        engine = manager.get(code)
        question = engine.room.current
        answers_data = [
            PlayerRevealAnswer(
                team_id=a.team_id,
                option_id=a.option_id,
                correct=a.correct,
                points=a.points,
            )
            for a in engine.room.answers
        ]
        teams_data = [
            PlayerTeamScore(id=t.id, name=t.name, score=t.score)
            for t in engine.room.teams
        ]
        message = PlayerRevealMessage(
            correct_option_id=question.correct_option_id,
            answers=answers_data,
            teams=teams_data,
        ).model_dump_json()
        for ws in list(player_map.values()):
            try:
                await ws.send_text(message)
            except Exception:
                pass

    async def broadcast_players_finished(self, room_code: str) -> None:
        code = room_code.upper()
        player_map = self.player_connections.get(code, {})
        if not player_map:
            return
        engine = manager.get(code)
        max_score = max((t.score for t in engine.room.teams), default=0)
        winners = [t.name for t in engine.room.teams if t.score == max_score]
        teams_data = [
            PlayerTeamScore(id=t.id, name=t.name, score=t.score)
            for t in engine.room.teams
        ]
        message = PlayerFinishedMessage(
            winners=winners,
            teams=teams_data,
        ).model_dump_json()
        for ws in list(player_map.values()):
            try:
                await ws.send_text(message)
            except Exception:
                pass

    async def broadcast_team_locked(self, room_code: str, team_id: str) -> None:
        code = room_code.upper()
        player_map = self.player_connections.get(code, {})
        if not player_map:
            return
        message = PlayerTeamLockedMessage(team_id=team_id).model_dump_json()
        for ws in list(player_map.values()):
            try:
                await ws.send_text(message)
            except Exception:
                pass

    async def handle_host_start(self, room_code: str, websocket: WebSocket) -> None:
        code = room_code.upper()
        async with manager.room_lock(code):
            try:
                engine = manager.get(code)
                if engine.room.phase is not Phase.LOBBY:
                    error_msg = ErrorMessage(detail="A partida já foi iniciada.")
                    await websocket.send_text(error_msg.model_dump_json())
                    return
                total_players = sum(len(team.players) for team in engine.room.teams)
                if total_players == 0:
                    error_msg = ErrorMessage(
                        detail="Não há jogadores na sala para iniciar a partida."
                    )
                    await websocket.send_text(error_msg.model_dump_json())
                    return
                engine.start_game()
                self.schedule_timer(code, engine.room.index, float(engine.room.question_time))
                await self.notify_room_state(code)
                await self.broadcast_players_question(code)
            except EngineError as err:
                await websocket.send_text(ErrorMessage(detail=err.message).model_dump_json())

    async def handle_host_next(self, room_code: str, websocket: WebSocket) -> None:
        code = room_code.upper()
        async with manager.room_lock(code):
            try:
                engine = manager.get(code)
                if engine.room.phase is Phase.LOBBY:
                    error_msg = ErrorMessage(detail="A partida não foi iniciada.")
                    await websocket.send_text(error_msg.model_dump_json())
                    return
                if engine.room.phase is Phase.QUESTION:
                    error_msg = ErrorMessage(detail="A pergunta atual ainda está aberta.")
                    await websocket.send_text(error_msg.model_dump_json())
                    return
                self.cancel_timer(code)
                engine.next_question()
                manager.persist_if_finished(engine)
                if engine.room.phase is Phase.FINISHED:
                    await self.notify_room_state(code)
                    await self.broadcast_players_finished(code)
                else:
                    self.schedule_timer(code, engine.room.index, float(engine.room.question_time))
                    await self.notify_room_state(code)
                    await self.broadcast_players_question(code)
            except EngineError as err:
                await websocket.send_text(ErrorMessage(detail=err.message).model_dump_json())

    async def handle_player_answer(
        self, room_code: str, player: Player, option_id: str, websocket: WebSocket
    ) -> None:
        code = room_code.upper()
        async with manager.room_lock(code):
            try:
                engine = manager.get(code)
                if engine.room.phase is not Phase.QUESTION:
                    await websocket.send_text(
                        ErrorMessage(detail="A pergunta não está aberta.").model_dump_json()
                    )
                    return
                team = engine.room.team(player.team_id)
                if team is None or team.answered:
                    await websocket.send_text(
                        PlayerTeamLockedMessage(team_id=player.team_id).model_dump_json()
                    )
                    return
                engine.answer(player.team_id, option_id)
                await self.broadcast_team_locked(code, player.team_id)
                if engine.room.phase is Phase.REVEAL:
                    self.cancel_timer(code)
                    await self.notify_room_state(code)
                    await self.broadcast_players_reveal(code)
                else:
                    await self.notify_room_state(code)
            except EngineError as err:
                await websocket.send_text(ErrorMessage(detail=err.message).model_dump_json())


hub = WebSocketHub()


@router.websocket("/host")
async def ws_host(websocket: WebSocket, room: str = "", token: str = "") -> None:
    code = room.upper()
    try:
        engine = manager.get(code)
    except EngineError:
        await websocket.close(code=1008)
        return

    if not secrets.compare_digest(engine.room.host_token, token):
        await websocket.close(code=1008)
        return

    await websocket.accept()
    await hub.register_host(code, websocket)

    try:
        initial_state = HostStateMessage.from_snapshot(manager.state(code))
        await websocket.send_text(initial_state.model_dump_json())

        while True:
            text = await websocket.receive_text()
            try:
                data = json.loads(text)
            except Exception:
                await websocket.send_text(
                    ErrorMessage(detail="JSON inválido.").model_dump_json()
                )
                continue

            msg_type = data.get("type")
            if msg_type == "start":
                _ = HostStartMessage.model_validate(data)
                await hub.handle_host_start(code, websocket)
            elif msg_type == "next":
                _ = HostNextMessage.model_validate(data)
                await hub.handle_host_next(code, websocket)
            else:
                await websocket.send_text(
                    ErrorMessage(detail="Tipo de mensagem desconhecido.").model_dump_json()
                )
    except WebSocketDisconnect:
        pass
    finally:
        await hub.unregister_host(code, websocket)


@router.websocket("/player")
async def ws_player(websocket: WebSocket, room: str = "", token: str = "") -> None:
    code = room.upper()
    try:
        engine = manager.get(code)
    except EngineError:
        await websocket.close(code=1008)
        return

    player = engine.room.players_by_token.get(token)
    if player is None:
        await websocket.close(code=1008)
        return

    await websocket.accept()
    await hub.register_player(code, player.id, websocket)

    try:
        if engine.room.phase is Phase.LOBBY:
            team = engine.room.team(player.team_id)
            team_name = team.name if team else ""
            msg = PlayerLobbyMessage(code=code, team_id=player.team_id, team_name=team_name)
            await websocket.send_text(msg.model_dump_json())
        elif engine.room.phase is Phase.QUESTION:
            q = engine.room.current
            seconds_left = max(0.0, engine.room.deadline - engine._clock())
            msg_q = PlayerQuestionMessage(
                index=engine.room.index,
                total=len(engine.room.questions),
                category=q.category,
                prompt=q.prompt,
                options=[OptionSnapshot(id=o.id, text=o.text) for o in q.options],
                seconds_left=round(seconds_left, 2),
            )
            await websocket.send_text(msg_q.model_dump_json())
            team = engine.room.team(player.team_id)
            if team is not None and team.answered:
                await websocket.send_text(
                    PlayerTeamLockedMessage(team_id=player.team_id).model_dump_json()
                )
        elif engine.room.phase is Phase.REVEAL:
            q = engine.room.current
            answers_data = [
                PlayerRevealAnswer(
                    team_id=a.team_id,
                    option_id=a.option_id,
                    correct=a.correct,
                    points=a.points,
                )
                for a in engine.room.answers
            ]
            teams_data = [
                PlayerTeamScore(id=t.id, name=t.name, score=t.score)
                for t in engine.room.teams
            ]
            msg_r = PlayerRevealMessage(
                correct_option_id=q.correct_option_id,
                answers=answers_data,
                teams=teams_data,
            )
            await websocket.send_text(msg_r.model_dump_json())
        elif engine.room.phase is Phase.FINISHED:
            max_score = max((t.score for t in engine.room.teams), default=0)
            winners = [t.name for t in engine.room.teams if t.score == max_score]
            teams_data = [
                PlayerTeamScore(id=t.id, name=t.name, score=t.score)
                for t in engine.room.teams
            ]
            msg_f = PlayerFinishedMessage(
                winners=winners,
                teams=teams_data,
            )
            await websocket.send_text(msg_f.model_dump_json())

        while True:
            text = await websocket.receive_text()
            try:
                data = json.loads(text)
            except Exception:
                await websocket.send_text(
                    ErrorMessage(detail="JSON inválido.").model_dump_json()
                )
                continue

            msg_type = data.get("type")
            if msg_type == "answer":
                ans_msg = PlayerAnswerMessage.model_validate(data)
                await hub.handle_player_answer(code, player, ans_msg.option_id, websocket)
            else:
                await websocket.send_text(
                    ErrorMessage(detail="Tipo de mensagem desconhecido.").model_dump_json()
                )
    except WebSocketDisconnect:
        pass
    finally:
        await hub.unregister_player(code, player.id, websocket)
