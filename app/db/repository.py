"""Acesso ao SQLite: conexão, criação do schema e consultas simples."""

import sqlite3
from datetime import datetime
from pathlib import Path

from ..domain.models import Room

SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path, timeout=5)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    return connection


def init_db(db_path: Path) -> None:
    with connect(db_path) as connection:
        connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))


def save_match(db_path: Path, room: Room) -> None:
    """Grava o resultado final de uma partida."""
    finished_at = room.finished_at or datetime.now()
    ordered = sorted(room.teams, key=lambda team: team.score, reverse=True)

    with connect(db_path) as connection:
        cursor = connection.execute(
            """
            INSERT INTO matches (code, mode, answer_mode, theme, provider, created_at, finished_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                room.code,
                room.mode.value,
                room.answer_mode.value,
                room.theme,
                room.provider,
                room.created_at.isoformat(timespec="seconds"),
                finished_at.isoformat(timespec="seconds"),
            ),
        )
        match_id = cursor.lastrowid
        for position, team in enumerate(ordered, start=1):
            connection.execute(
                """
                INSERT INTO match_teams (match_id, name, score, position)
                VALUES (?, ?, ?, ?)
                """,
                (match_id, team.name, team.score, position),
            )


def ranking(db_path: Path, limit: int = 10) -> list[dict]:
    with connect(db_path) as connection:
        rows = connection.execute(
            """
            SELECT mt.name, mt.score, m.mode, m.theme, m.finished_at
            FROM match_teams mt
            JOIN matches m ON m.id = mt.match_id
            ORDER BY mt.score DESC, m.finished_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def normalize_theme_key(theme: str) -> str:
    """Normaliza o tema para chave de busca no cache."""
    return " ".join(theme.strip().lower().split())


def get_cached_questions(
    db_path: Path,
    theme: str,
    provider: str,
    model: str,
    n: int,
) -> str | None:
    """Recupera o payload JSON de perguntas em cache para a chave informada."""
    theme_norm = normalize_theme_key(theme)
    with connect(db_path) as connection:
        cursor = connection.execute(
            """
            SELECT payload_json
            FROM questions_cache
            WHERE theme_norm = ? AND provider = ? AND model = ? AND n = ?
            """,
            (theme_norm, provider, model, n),
        )
        row = cursor.fetchone()
        if row is not None:
            return str(row["payload_json"])
    return None


def save_cached_questions(
    db_path: Path,
    theme: str,
    provider: str,
    model: str,
    n: int,
    payload_json: str,
) -> None:
    """Armazena o payload JSON de perguntas no cache."""
    theme_norm = normalize_theme_key(theme)
    created_at = datetime.now().isoformat(timespec="seconds")
    with connect(db_path) as connection:
        connection.execute(
            """
            INSERT INTO questions_cache (theme_norm, provider, model, n, payload_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(theme_norm, provider, model, n)
            DO UPDATE SET payload_json = excluded.payload_json, created_at = excluded.created_at
            """,
            (theme_norm, provider, model, n, payload_json, created_at),
        )

