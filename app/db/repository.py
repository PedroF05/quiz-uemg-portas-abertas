"""Acesso ao SQLite: conexão, criação do schema e consultas simples."""

from datetime import datetime
from pathlib import Path
import sqlite3
from typing import TypedDict

from ..domain.models import AnswerRecord, Room

SCHEMA_PATH = Path(__file__).with_name("schema.sql")


class PlayerHistoryDict(TypedDict):
    nickname: str
    answers_count: int
    correct_count: int


class TeamHistoryDict(TypedDict):
    name: str
    score: int
    position: int
    players: list[PlayerHistoryDict]


class MatchHistoryDict(TypedDict):
    id: int
    code: str
    mode: str
    answer_mode: str
    theme: str
    provider: str
    created_at: str
    finished_at: str
    teams: list[TeamHistoryDict]


class RankingEntryDict(TypedDict):
    name: str
    score: int
    mode: str
    theme: str
    finished_at: str


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
    all_answers: list[AnswerRecord] = room.all_answers

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
            team_cursor = connection.execute(
                """
                INSERT INTO match_teams (match_id, name, score, position)
                VALUES (?, ?, ?, ?)
                """,
                (match_id, team.name, team.score, position),
            )
            team_db_id = team_cursor.lastrowid
            for player in team.players:
                answers_count = sum(
                    1 for a in all_answers if a.player_id == player.id
                )
                correct_count = sum(
                    1
                    for a in all_answers
                    if a.player_id == player.id and a.correct
                )
                connection.execute(
                    """
                    INSERT INTO match_players (match_id, team_id, nickname, answers_count, correct_count)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        match_id,
                        team_db_id,
                        player.nickname,
                        answers_count,
                        correct_count,
                    ),
                )


def history(db_path: Path, limit: int = 5) -> list[MatchHistoryDict]:
    """Retorna as partidas mais recentes com equipes e jogadores."""
    with connect(db_path) as connection:
        match_rows = connection.execute(
            """
            SELECT id, code, mode, answer_mode, theme, provider, created_at, finished_at
            FROM matches
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

        if not match_rows:
            return []

        match_ids = [int(row["id"]) for row in match_rows]
        placeholders_matches = ",".join("?" for _ in match_ids)

        team_rows = connection.execute(
            f"""
            SELECT id, match_id, name, score, position
            FROM match_teams
            WHERE match_id IN ({placeholders_matches})
            ORDER BY position ASC, score DESC
            """,
            match_ids,
        ).fetchall()

        players_by_team: dict[int, list[PlayerHistoryDict]] = {}
        if team_rows:
            team_ids = [int(row["id"]) for row in team_rows]
            placeholders_teams = ",".join("?" for _ in team_ids)
            player_rows = connection.execute(
                f"""
                SELECT team_id, nickname, answers_count, correct_count
                FROM match_players
                WHERE team_id IN ({placeholders_teams})
                ORDER BY id ASC
                """,
                team_ids,
            ).fetchall()

            for p_row in player_rows:
                t_id = int(p_row["team_id"])
                if t_id not in players_by_team:
                    players_by_team[t_id] = []
                players_by_team[t_id].append(
                    {
                        "nickname": str(p_row["nickname"]),
                        "answers_count": int(p_row["answers_count"]),
                        "correct_count": int(p_row["correct_count"]),
                    }
                )

        teams_by_match: dict[int, list[TeamHistoryDict]] = {}
        for t_row in team_rows:
            m_id = int(t_row["match_id"])
            t_id = int(t_row["id"])
            if m_id not in teams_by_match:
                teams_by_match[m_id] = []
            teams_by_match[m_id].append(
                {
                    "name": str(t_row["name"]),
                    "score": int(t_row["score"]),
                    "position": int(t_row["position"]),
                    "players": players_by_team.get(t_id, []),
                }
            )

        results: list[MatchHistoryDict] = []
        for m_row in match_rows:
            m_id = int(m_row["id"])
            results.append(
                {
                    "id": m_id,
                    "code": str(m_row["code"]),
                    "mode": str(m_row["mode"]),
                    "answer_mode": str(m_row["answer_mode"]),
                    "theme": str(m_row["theme"]),
                    "provider": str(m_row["provider"]),
                    "created_at": str(m_row["created_at"]),
                    "finished_at": str(m_row["finished_at"]),
                    "teams": teams_by_match.get(m_id, []),
                }
            )

        return results


def ranking(db_path: Path, limit: int = 10) -> list[RankingEntryDict]:
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
    return [
        {
            "name": str(row["name"]),
            "score": int(row["score"]),
            "mode": str(row["mode"]),
            "theme": str(row["theme"]),
            "finished_at": str(row["finished_at"]),
        }
        for row in rows
    ]


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

