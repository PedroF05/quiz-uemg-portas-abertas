"""Criação de salas, ações do host e adesão de jogadores."""

import io
import socket

from fastapi import APIRouter, HTTPException, Response
import qrcode

from ..config import settings as app_settings
from ..domain.models import (
    CreateRoomRequest,
    JoinInfoResponse,
    PlayerJoinRequest,
    PlayerJoinResponse,
)
from ..game.engine import EngineError, RoomSnapshotDict
from ..game.manager import manager
from ..quiz.bank import BankError
from .ws import hub

router = APIRouter(prefix="/api", tags=["rooms"])


def get_lan_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            ip = sock.getsockname()[0]
            if ip:
                return str(ip)
    except Exception:
        pass
    try:
        return str(socket.gethostbyname(socket.gethostname()))
    except Exception:
        return "127.0.0.1"


def _public_base_url() -> str:
    """URL base pública da aplicação, priorizando a configuração explícita."""
    if app_settings.public_url:
        return app_settings.public_url.rstrip("/")
    return f"http://{get_lan_ip()}:{app_settings.app_port}"


@router.post("/rooms", status_code=201)
async def create_room(payload: CreateRoomRequest) -> dict[str, str | RoomSnapshotDict]:
    try:
        code, host_token, state = await manager.create(payload)
    except (BankError, EngineError) as error:
        status_code = getattr(error, "status_code", 400)
        message = getattr(error, "message", str(error))
        raise HTTPException(status_code=status_code, detail=message) from error
    return {
        "code": code,
        "host_token": host_token,
        "join_url": f"{_public_base_url()}/play",
        "state": state,
    }


@router.get("/rooms/{code}/state")
async def room_state(code: str) -> RoomSnapshotDict:
    async with manager.room_lock(code):
        try:
            return manager.state(code)
        except EngineError as error:
            raise HTTPException(status_code=error.status_code, detail=error.message) from error


@router.get("/rooms/{code}/join-info")
async def join_info(code: str) -> JoinInfoResponse:
    async with manager.room_lock(code):
        try:
            return manager.get_join_info(code)
        except EngineError as error:
            raise HTTPException(status_code=error.status_code, detail=error.message) from error


@router.post("/rooms/{code}/players", status_code=201)
async def join_player(code: str, payload: PlayerJoinRequest) -> PlayerJoinResponse:
    async with manager.room_lock(code):
        try:
            player, _ = manager.add_player(code, payload.nickname, payload.team_id)
            engine = manager.get(code)
            team = engine.room.team(player.team_id)
            team_name = team.name if team else ""
            await hub.notify_room_state(code)
            return PlayerJoinResponse(
                player_id=player.id,
                player_token=player.token,
                team_id=player.team_id,
                team_name=team_name,
            )
        except EngineError as error:
            raise HTTPException(status_code=error.status_code, detail=error.message) from error


@router.get("/rooms/{code}/qr.png")
async def room_qr(code: str) -> Response:
    async with manager.room_lock(code):
        try:
            _ = manager.get(code)
        except EngineError as error:
            raise HTTPException(status_code=error.status_code, detail=error.message) from error

    target_url = f"{_public_base_url()}/play?room={code.upper()}"
    image = qrcode.make(target_url)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return Response(content=buffer.getvalue(), media_type="image/png")
