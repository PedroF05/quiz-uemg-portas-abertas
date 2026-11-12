"""Recursos gerais: temas, ranking e saúde do serviço."""

from fastapi import APIRouter, HTTPException, Query

from ..config import settings
from ..db import repository
from ..game.manager import manager
from ..quiz.bank import BankError, list_themes

router = APIRouter(prefix="/api", tags=["quiz"])


@router.get("/themes")
def themes() -> list[dict]:
    try:
        return list_themes(settings)
    except BankError as error:
        raise HTTPException(status_code=500, detail=str(error)) from error


@router.get("/ranking")
def ranking(limit: int = Query(default=10, ge=1, le=50)) -> list[dict]:
    return repository.ranking(settings.db_path, limit)


@router.get("/health")
def health() -> dict:
    try:
        repository.connect(settings.db_path).close()
        database_ok = True
    except Exception:
        database_ok = False

    try:
        theme_count = len(list_themes(settings))
    except BankError:
        theme_count = 0

    return {
        "status": "ok" if database_ok else "degraded",
        "database": database_ok,
        "provider": settings.llm_provider,
        "themes": theme_count,
        "rooms": len(manager._engines),
    }
