"""Testes de integracao WebSocket com fluxo 3v3 (2 equipes x 3 jogadores)."""

from collections.abc import Iterator
from contextlib import ExitStack
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.db.repository import connect
from app.game.manager import manager
from app.main import app


@pytest.fixture
def client() -> Iterator[TestClient]:
    """Fixture de cliente de teste FastAPI."""
    with TestClient(app) as test_client:
        yield test_client


def test_full_websocket_3v3_match_flow(client: TestClient) -> None:
    """Valida o fluxo completo de partida mobile com 2 equipes de 3 jogadores."""
    create_response = client.post(
        "/api/rooms",
        json={
            "mode": "mobile",
            "team_names": ["Equipe Alpha", "Equipe Beta"],
            "theme_id": "jogos",
            "n": 2,
        },
    )
    assert create_response.status_code == 201
    room_data = create_response.json()
    code: str = room_data["code"]
    host_token: str = room_data["host_token"]
    teams_meta = room_data["state"]["teams"]
    t1_id: str = teams_meta[0]["id"]
    t2_id: str = teams_meta[1]["id"]

    players_data: list[dict[str, str]] = []
    for i in range(1, 4):
        join_a = client.post(
            f"/api/rooms/{code}/players",
            json={"nickname": f"Alpha_{i}", "team_id": t1_id},
        )
        assert join_a.status_code == 201
        players_data.append(join_a.json())

    for i in range(1, 4):
        join_b = client.post(
            f"/api/rooms/{code}/players",
            json={"nickname": f"Beta_{i}", "team_id": t2_id},
        )
        assert join_b.status_code == 201
        players_data.append(join_b.json())

    assert len(players_data) == 6

    with ExitStack() as stack:
        host_ws = stack.enter_context(
            client.websocket_connect(f"/ws/host?room={code}&token={host_token}")
        )
        initial_host_state = host_ws.receive_json()
        assert initial_host_state["type"] == "state"
        assert initial_host_state["phase"] == "lobby"
        host_teams = initial_host_state["teams"]
        assert len(host_teams[0]["players"]) == 3
        assert len(host_teams[1]["players"]) == 3
        assert sum(len(t["players"]) for t in host_teams) == 6

        player_sockets = [
            stack.enter_context(
                client.websocket_connect(
                    f"/ws/player?room={code}&token={p['player_token']}"
                )
            )
            for p in players_data
        ]

        for idx, ws in enumerate(player_sockets):
            lobby_msg = ws.receive_json()
            assert lobby_msg["type"] == "lobby"
            assert lobby_msg["code"] == code
            assert lobby_msg["team_id"] == players_data[idx]["team_id"]

        host_ws.send_json({"type": "start"})
        host_q1 = host_ws.receive_json()
        assert host_q1["type"] == "state"
        assert host_q1["phase"] == "question"
        assert host_q1["index"] == 0

        q1_player_messages = [ws.receive_json() for ws in player_sockets]
        for q_msg in q1_player_messages:
            assert q_msg["type"] == "question"
            assert q_msg["index"] == 0
            assert q_msg["total"] == 2
            assert len(q_msg["options"]) == 4
            assert "correct_option_id" not in q_msg

        engine = manager.get(code)
        q1_correct_id: str = engine.room.current.correct_option_id
        q1_options: list[str] = [o.id for o in engine.room.current.options]
        q1_distractor_id: str = [oid for oid in q1_options if oid != q1_correct_id][0]

        player_sockets[0].send_json({"type": "answer", "option_id": q1_correct_id})

        for ws in player_sockets:
            lock_msg = ws.receive_json()
            assert lock_msg["type"] == "team_locked"
            assert lock_msg["team_id"] == t1_id

        host_after_p1 = host_ws.receive_json()
        assert host_after_p1["phase"] == "question"
        assert host_after_p1["teams"][0]["answered"] is True
        assert host_after_p1["teams"][1]["answered"] is False

        player_sockets[1].send_json({"type": "answer", "option_id": q1_correct_id})
        p1_lock = player_sockets[1].receive_json()
        assert p1_lock["type"] == "team_locked"
        assert p1_lock["team_id"] == t1_id

        player_sockets[2].send_json({"type": "answer", "option_id": q1_distractor_id})
        p2_lock = player_sockets[2].receive_json()
        assert p2_lock["type"] == "team_locked"
        assert p2_lock["team_id"] == t1_id

        assert engine.room.teams[0].score == 15

        player_sockets[3].send_json({"type": "answer", "option_id": q1_distractor_id})

        for ws in player_sockets:
            lock_msg2 = ws.receive_json()
            assert lock_msg2["type"] == "team_locked"
            assert lock_msg2["team_id"] == t2_id

        host_reveal_1 = host_ws.receive_json()
        assert host_reveal_1["phase"] == "reveal"
        assert host_reveal_1["teams"][0]["answered"] is True
        assert host_reveal_1["teams"][1]["answered"] is True

        for ws in player_sockets:
            reveal_msg = ws.receive_json()
            assert reveal_msg["type"] == "reveal"
            assert reveal_msg["correct_option_id"] == q1_correct_id
            assert len(reveal_msg["answers"]) == 2

        player_sockets[4].send_json({"type": "answer", "option_id": q1_distractor_id})
        p4_err = player_sockets[4].receive_json()
        assert p4_err["type"] == "error"

        player_sockets[5].send_json({"type": "answer", "option_id": q1_correct_id})
        p5_err = player_sockets[5].receive_json()
        assert p5_err["type"] == "error"

        scores_q1: dict[str, int] = {t["id"]: t["score"] for t in host_reveal_1["teams"]}
        assert scores_q1[t1_id] == 15
        assert scores_q1[t2_id] == 0
        assert engine.room.teams[0].score == 15
        assert engine.room.teams[1].score == 0

        host_ws.send_json({"type": "next"})
        host_q2 = host_ws.receive_json()
        assert host_q2["phase"] == "question"
        assert host_q2["index"] == 1

        q2_player_messages = [ws.receive_json() for ws in player_sockets]
        for q_msg in q2_player_messages:
            assert q_msg["type"] == "question"
            assert q_msg["index"] == 1

        q2_correct_id: str = engine.room.current.correct_option_id
        q2_options: list[str] = [o.id for o in engine.room.current.options]
        q2_distractor_id: str = [oid for oid in q2_options if oid != q2_correct_id][0]

        player_sockets[4].send_json({"type": "answer", "option_id": q2_correct_id})

        for ws in player_sockets:
            lock_msg_q2 = ws.receive_json()
            assert lock_msg_q2["type"] == "team_locked"
            assert lock_msg_q2["team_id"] == t2_id

        _ = host_ws.receive_json()

        player_sockets[2].send_json({"type": "answer", "option_id": q2_distractor_id})

        for ws in player_sockets:
            lock_msg_q2_b = ws.receive_json()
            assert lock_msg_q2_b["type"] == "team_locked"
            assert lock_msg_q2_b["team_id"] == t1_id

        host_reveal_2 = host_ws.receive_json()
        assert host_reveal_2["phase"] == "reveal"
        assert host_reveal_2["teams"][0]["answered"] is True
        assert host_reveal_2["teams"][1]["answered"] is True

        for ws in player_sockets:
            rev2 = ws.receive_json()
            assert rev2["type"] == "reveal"
            assert rev2["correct_option_id"] == q2_correct_id

        scores_q2: dict[str, int] = {t["id"]: t["score"] for t in host_reveal_2["teams"]}
        assert scores_q2[t1_id] == 15
        assert scores_q2[t2_id] == 15

        host_ws.send_json({"type": "next"})
        host_finished = host_ws.receive_json()
        assert host_finished["phase"] == "finished"

        for ws in player_sockets:
            fin_msg = ws.receive_json()
            assert fin_msg["type"] == "finished"
            assert len(fin_msg["winners"]) >= 1

    ranking_response = client.get("/api/ranking")
    assert ranking_response.status_code == 200
    ranking_items = ranking_response.json()
    ranking_names = {item["name"] for item in ranking_items}
    assert "Equipe Alpha" in ranking_names
    assert "Equipe Beta" in ranking_names

    with connect(settings.db_path) as connection:
        match_cursor = connection.execute(
            "SELECT COUNT(*) AS total FROM matches WHERE code = ?",
            (code,),
        )
        match_row = match_cursor.fetchone()
        assert match_row is not None
        assert match_row["total"] == 1

        teams_cursor = connection.execute(
            """
            SELECT COUNT(*) AS total
            FROM match_teams mt
            JOIN matches m ON m.id = mt.match_id
            WHERE m.code = ?
            """,
            (code,),
        )
        teams_row = teams_cursor.fetchone()
        assert teams_row is not None
        assert teams_row["total"] == 2
