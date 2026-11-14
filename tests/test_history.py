"""Testes de histórico, persistência única e métricas por jogador."""

from datetime import datetime
from pathlib import Path
import sqlite3

from fastapi.testclient import TestClient
import pytest

from app.db import repository
from app.domain.models import (
    AnswerMode,
    AnswerRecord,
    Mode,
    Option,
    PlayerSummary,
    Question,
    Room,
    Team,
)
from app.main import app


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


def _build_test_room(code: str = "TST001") -> Room:
    p1 = PlayerSummary(id="p_1", nickname="Alice")
    p2 = PlayerSummary(id="p_2", nickname="Bob")
    p3 = PlayerSummary(id="p_3", nickname="Carlos")

    team1 = Team(id="t_1", name="Equipe Alfa", score=25, players=[p1, p2])
    team2 = Team(id="t_2", name="Equipe Beta", score=10, players=[p3])

    questions = [
        Question(
            id="q_1",
            category="Geral",
            prompt="Pergunta 1",
            options=[
                Option(id="o_1", text="Opcao 1"),
                Option(id="o_2", text="Opcao 2"),
            ],
            correct_option_id="o_1",
        )
    ]

    return Room(
        code=code,
        host_token="token_host_secret",
        mode=Mode.MOBILE,
        answer_mode=AnswerMode.SIMULTANEOUS,
        teams=[team1, team2],
        questions=questions,
        theme="Tecnologia",
        provider="offline",
        question_time=15,
    )


def test_save_match_records_players_metrics(tmp_path: Path) -> None:
    db_path = tmp_path / "quiz_test.db"
    repository.init_db(db_path)

    room = _build_test_room("MTR001")
    room.finished_at = datetime.now()

    room.all_answers = [
        AnswerRecord(
            team_id="t_1",
            option_id="o_1",
            correct=True,
            points=15,
            elapsed=2.5,
            player_id="p_1",
        ),
        AnswerRecord(
            team_id="t_1",
            option_id="o_2",
            correct=False,
            points=0,
            elapsed=4.0,
            player_id="p_1",
        ),
        AnswerRecord(
            team_id="t_2",
            option_id="o_1",
            correct=True,
            points=10,
            elapsed=5.1,
            player_id="p_3",
        ),
    ]

    repository.save_match(db_path, room)

    with repository.connect(db_path) as conn:
        matches = conn.execute("SELECT * FROM matches WHERE code = 'MTR001'").fetchall()
        assert len(matches) == 1
        match_id = int(matches[0]["id"])

        teams = conn.execute(
            "SELECT * FROM match_teams WHERE match_id = ? ORDER BY position ASC",
            (match_id,),
        ).fetchall()
        assert len(teams) == 2
        assert teams[0]["name"] == "Equipe Alfa"
        assert teams[0]["position"] == 1
        assert teams[1]["name"] == "Equipe Beta"
        assert teams[1]["position"] == 2

        players = conn.execute(
            "SELECT * FROM match_players WHERE match_id = ? ORDER BY nickname ASC",
            (match_id,),
        ).fetchall()
        assert len(players) == 3

        alice = next(p for p in players if p["nickname"] == "Alice")
        assert alice["answers_count"] == 2
        assert alice["correct_count"] == 1

        bob = next(p for p in players if p["nickname"] == "Bob")
        assert bob["answers_count"] == 0
        assert bob["correct_count"] == 0

        carlos = next(p for p in players if p["nickname"] == "Carlos")
        assert carlos["answers_count"] == 1
        assert carlos["correct_count"] == 1


def test_history_repository_returns_empty_and_populated(tmp_path: Path) -> None:
    db_path = tmp_path / "quiz_test.db"
    repository.init_db(db_path)

    assert repository.history(db_path, limit=5) == []

    room1 = _build_test_room("HIS001")
    room1.all_answers = [
        AnswerRecord(
            team_id="t_1",
            option_id="o_1",
            correct=True,
            points=10,
            elapsed=3.0,
            player_id="p_1",
        )
    ]
    repository.save_match(db_path, room1)

    room2 = _build_test_room("HIS002")
    room2.theme = "Jogos"
    room2.all_answers = []
    repository.save_match(db_path, room2)

    history_one = repository.history(db_path, limit=1)
    assert len(history_one) == 1
    assert history_one[0]["code"] == "HIS002"

    history_all = repository.history(db_path, limit=10)
    assert len(history_all) == 2
    assert history_all[0]["code"] == "HIS002"
    assert history_all[1]["code"] == "HIS001"

    match_entry = history_all[1]
    assert match_entry["theme"] == "Tecnologia"
    assert len(match_entry["teams"]) == 2
    alfa = next(t for t in match_entry["teams"] if t["name"] == "Equipe Alfa")
    assert alfa["score"] == 25
    assert len(alfa["players"]) == 2
    alice = next(p for p in alfa["players"] if p["nickname"] == "Alice")
    assert alice["answers_count"] == 1
    assert alice["correct_count"] == 1


def test_api_history_endpoint(client: TestClient) -> None:
    resp = client.get("/api/history")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)

    resp_invalid_low = client.get("/api/history?limit=0")
    assert resp_invalid_low.status_code == 422

    resp_invalid_high = client.get("/api/history?limit=51")
    assert resp_invalid_high.status_code == 422

    resp_valid = client.get("/api/history?limit=5")
    assert resp_valid.status_code == 200


def test_single_persistence_on_next(client: TestClient) -> None:
    res = client.post(
        "/api/rooms",
        json={
            "mode": "local",
            "team_names": ["Time 1", "Time 2"],
            "theme_id": "jogos",
            "n": 1,
        },
    )
    assert res.status_code == 201
    data = res.json()
    code = data["code"]
    token = data["host_token"]

    state = data["state"]
    turn_team = state["turn_team_id"]
    opt_id = state["question"]["options"][0]["id"]
    client.post(
        f"/api/rooms/{code}/answer",
        headers={"X-Host-Token": token},
        json={"team_id": turn_team, "option_id": opt_id},
    )

    next_res = client.post(
        f"/api/rooms/{code}/next",
        headers={"X-Host-Token": token},
    )
    assert next_res.status_code == 200
    finished_state = next_res.json()
    assert finished_state["phase"] == "finished"

    history_first = client.get("/api/history?limit=50").json()
    matches_for_code = [m for m in history_first if m["code"] == code]
    assert len(matches_for_code) == 1

    next_again = client.post(
        f"/api/rooms/{code}/next",
        headers={"X-Host-Token": token},
    )
    assert next_again.status_code == 200

    history_second = client.get("/api/history?limit=50").json()
    matches_for_code_after = [m for m in history_second if m["code"] == code]
    assert len(matches_for_code_after) == 1


def test_mobile_match_persists_players_metrics_via_ws(client: TestClient) -> None:
    res = client.post(
        "/api/rooms",
        json={
            "mode": "mobile",
            "team_names": ["Equipe Ouro", "Equipe Prata"],
            "theme_id": "jogos",
            "n": 1,
        },
    )
    assert res.status_code == 201
    room_data = res.json()
    code = room_data["code"]
    host_token = room_data["host_token"]
    teams = room_data["state"]["teams"]
    t1_id = teams[0]["id"]
    t2_id = teams[1]["id"]

    p1_res = client.post(
        f"/api/rooms/{code}/players",
        json={"nickname": "Beatriz", "team_id": t1_id},
    )
    assert p1_res.status_code == 201
    p1_token = p1_res.json()["player_token"]

    p2_res = client.post(
        f"/api/rooms/{code}/players",
        json={"nickname": "Daniel", "team_id": t2_id},
    )
    assert p2_res.status_code == 201
    p2_token = p2_res.json()["player_token"]

    p3_res = client.post(
        f"/api/rooms/{code}/players",
        json={"nickname": "Carlos", "team_id": t2_id},
    )
    assert p3_res.status_code == 201

    with client.websocket_connect(f"/ws/host?room={code}&token={host_token}") as host_ws:
        _ = host_ws.receive_json()

        with client.websocket_connect(f"/ws/player?room={code}&token={p1_token}") as p1_ws:
            _ = p1_ws.receive_json()

            with client.websocket_connect(f"/ws/player?room={code}&token={p2_token}") as p2_ws:
                _ = p2_ws.receive_json()

                host_ws.send_json({"type": "start"})
                p1_q = p1_ws.receive_json()
                _ = p2_ws.receive_json()
                _ = host_ws.receive_json()

                p1_opt = p1_q["options"][0]["id"]
                p1_ws.send_json({"type": "answer", "option_id": p1_opt})

                _ = p1_ws.receive_json()
                _ = p2_ws.receive_json()
                _ = host_ws.receive_json()

                p2_opt = p1_q["options"][1]["id"]
                p2_ws.send_json({"type": "answer", "option_id": p2_opt})

                _ = p1_ws.receive_json()
                _ = p2_ws.receive_json()
                _ = host_ws.receive_json()

                host_ws.send_json({"type": "next"})
                _ = host_ws.receive_json()
                _ = p1_ws.receive_json()
                _ = p2_ws.receive_json()

    history_res = client.get("/api/history?limit=50")
    assert history_res.status_code == 200
    all_history = history_res.json()
    target_match = next((m for m in all_history if m["code"] == code), None)
    assert target_match is not None

    team_ouro = next(t for t in target_match["teams"] if t["name"] == "Equipe Ouro")
    beatriz = next(p for p in team_ouro["players"] if p["nickname"] == "Beatriz")
    assert beatriz["answers_count"] == 1
    assert beatriz["correct_count"] in (0, 1)

    team_prata = next(t for t in target_match["teams"] if t["name"] == "Equipe Prata")
    daniel = next(p for p in team_prata["players"] if p["nickname"] == "Daniel")
    assert daniel["answers_count"] == 1

    carlos = next(p for p in team_prata["players"] if p["nickname"] == "Carlos")
    assert carlos["answers_count"] == 0
    assert carlos["correct_count"] == 0
