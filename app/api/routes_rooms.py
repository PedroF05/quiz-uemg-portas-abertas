"""Criação de salas, ações do host e adesão de jogadores."""

import io
import socket
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Response
import qrcode

from ..config import settings as app_settings
from ..domain.models import (
    AnswerRequest,
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

HostToken = Annotated[str | None, Header(alias="X-Host-Token")]


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


@router.post("/rooms", status_code=201)
async def create_room(payload: CreateRoomRequest) -> dict[str, str | RoomSnapshotDict]:
    try:
        code, host_token, state = await manager.create(payload)
    except (BankError, EngineError) as error:
        status_code = getattr(error, "status_code", 400)
        message = getattr(error, "message", str(error))
        raise HTTPException(status_code=status_code, detail=message) from error
    return {"code": code, "host_token": host_token, "state": state}


@router.get("/rooms/{code}/state")
async def room_state(code: str) -> RoomSnapshotDict:
    async with manager.room_lock(code):
        try:
            return manager.state(code)
        except EngineError as error:
            raise HTTPException(status_code=error.status_code, detail=error.message) from error


@router.post("/rooms/{code}/answer")
async def answer(code: str, payload: AnswerRequest, host_token: HostToken = None) -> RoomSnapshotDict:
    if not host_token:
        raise HTTPException(status_code=403, detail="Token do host ausente.")
    async with manager.room_lock(code):
        try:
            return manager.answer(code, host_token, payload.team_id, payload.option_id)
        except EngineError as error:
            raise HTTPException(status_code=error.status_code, detail=error.message) from error


@router.post("/rooms/{code}/next")
async def next_question(code: str, host_token: HostToken = None) -> RoomSnapshotDict:
    if not host_token:
        raise HTTPException(status_code=403, detail="Token do host ausente.")
    async with manager.room_lock(code):
        try:
            return manager.next_question(code, host_token)
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

    if app_settings.public_url:
        base = app_settings.public_url.rstrip("/")
    else:
        lan_ip = get_lan_ip()
        base = f"http://{lan_ip}:{app_settings.app_port}"

    target_url = f"{base}/play?room={code.upper()}"
    image = qrcode.make(target_url)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return Response(content=buffer.getvalue(), media_type="image/png")
