"""Ciclo de vida das salas: limite de salas ativas, expiração e broadcasts resilientes."""

import asyncio
import contextlib
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.api import ws as ws_module
from app.config import Settings
from app.domain.models import CreateRoomRequest, Phase
from app.game.engine import EngineError
from app.game.manager import RoomManager, manager
from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def _request() -> CreateRoomRequest:
    return CreateRoomRequest(team_names=["A", "B"], theme_id="jogos", n=1)


class FakeSocket:
    def __init__(self, delay: float = 0.0, fail: bool = False) -> None:
        self.sent: list[str] = []
        self.closed = False
        self._delay = delay
        self._fail = fail

    async def send_text(self, message: str) -> None:
        if self._delay:
            await asyncio.sleep(self._delay)
        if self._fail:
            raise RuntimeError("socket quebrado")
        self.sent.append(message)

    async def close(self, code: int = 1000) -> None:
        self.closed = True


async def test_create_room_respects_active_limit() -> None:
    room_manager = RoomManager(Settings(max_active_rooms=2))
    await room_manager.create(_request())
    await room_manager.create(_request())
    with pytest.raises(EngineError) as excinfo:
        await room_manager.create(_request())
    assert excinfo.value.status_code == 503


def test_api_returns_503_when_limit_reached(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(manager.settings, "max_active_rooms", 0)
    res = client.post(
        "/api/rooms",
        json={"team_names": ["A", "B"], "theme_id": "jogos", "n": 1},
    )
    assert res.status_code == 503


async def test_sweep_removes_expired_rooms_only() -> None:
    room_manager = RoomManager(Settings(room_ttl_minutes=30))
    lobby_code, _, _ = await room_manager.create(_request())
    finished_code, _, _ = await room_manager.create(_request())
    live_code, _, _ = await room_manager.create(_request())

    old = datetime.now() - timedelta(minutes=31)
    room_manager.get(lobby_code).room.created_at = old

    finished = room_manager.get(finished_code).room
    finished.phase = Phase.FINISHED
    finished.finished_at = old

    live = room_manager.get(live_code).room
    live.phase = Phase.QUESTION  # partida em andamento nunca é removida

    recent = datetime.now() - timedelta(minutes=5)
    fresh_code, _, _ = await room_manager.create(_request())
    room_manager.get(fresh_code).room.created_at = recent

    removed = await room_manager.sweep_expired()

    assert set(removed) == {lobby_code, finished_code}
    with pytest.raises(EngineError):
        room_manager.get(lobby_code)
    assert room_manager.get(live_code) is not None
    assert room_manager.get(fresh_code) is not None


async def test_send_all_survives_slow_and_broken_sockets(monkeypatch) -> None:
    monkeypatch.setattr(ws_module.app_settings, "ws_send_timeout", 0.05)
    hub = ws_module.WebSocketHub()
    fast = FakeSocket()
    slow = FakeSocket(delay=5)
    broken = FakeSocket(fail=True)

    start = asyncio.get_event_loop().time()
    await hub._send_all([fast, slow, broken], "oi")
    elapsed = asyncio.get_event_loop().time() - start

    assert fast.sent == ["oi"]
    assert elapsed < 1.0  # não esperou o socket lento de 5s


async def test_purge_room_closes_connections_and_cancels_timer() -> None:
    hub = ws_module.WebSocketHub()
    host = FakeSocket()
    player = FakeSocket()
    await hub.register_host("ABC123", host)
    await hub.register_player("ABC123", "p1", player)
    timer = asyncio.create_task(asyncio.sleep(60))
    hub.question_timers["ABC123"] = timer

    await hub.purge_room("abc123")

    assert host.closed and player.closed
    assert "ABC123" not in hub.host_connections
    assert "ABC123" not in hub.player_connections
    assert "ABC123" not in hub.question_timers
    with contextlib.suppress(asyncio.CancelledError):
        await timer
    assert timer.cancelled()
