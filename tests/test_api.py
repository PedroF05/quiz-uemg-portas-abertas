import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def room(client):
    response = client.post(
        "/api/rooms",
        json={
            "mode": "session",
            "team_names": ["Alpha", "Beta"],
            "theme_id": "",
            "n": 2,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_health(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["database"] is True


def test_create_room_returns_session_lobby(client, room):
    assert room["join_url"].endswith("/play")

    state = room["state"]
    assert state["mode"] == "session"
    assert state["answer_mode"] == "simultaneous"
    assert state["phase"] == "lobby"
    assert state["question"] is None
    assert state["seconds_left"] == 0


def test_themes_are_listed(client):
    themes = client.get("/api/themes").json()
    ids = {theme["id"] for theme in themes}
    assert {"jogos", "filmes", "series", "anime", "tecnologia"} <= ids


def test_question_payload_does_not_leak_answer(client, room):
    code = room["code"]
    host_token = room["host_token"]
    team_id = room["state"]["teams"][0]["id"]

    player_res = client.post(
        f"/api/rooms/{code}/players",
        json={"nickname": "Ana", "team_id": team_id},
    )
    assert player_res.status_code == 201

    with client.websocket_connect(f"/ws/host?room={code}&token={host_token}") as host_ws:
        assert host_ws.receive_json()["phase"] == "lobby"

        host_ws.send_json({"type": "start"})
        state = host_ws.receive_json()

    assert state["phase"] == "question"
    assert state["reveal"] is None
    assert "correct_option_id" not in state["question"]


def test_full_match_persists_ranking(client):
    response = client.post(
        "/api/rooms",
        json={
            "mode": "session",
            "team_names": ["Gama", "Delta"],
            "theme_id": "",
            "n": 2,
        },
    )
    assert response.status_code == 201, response.text
    data = response.json()
    code, host_token = data["code"], data["host_token"]
    team_1, team_2 = data["state"]["teams"][0]["id"], data["state"]["teams"][1]["id"]

    player_1 = client.post(
        f"/api/rooms/{code}/players",
        json={"nickname": "Gama 1", "team_id": team_1},
    ).json()
    player_2 = client.post(
        f"/api/rooms/{code}/players",
        json={"nickname": "Delta 1", "team_id": team_2},
    ).json()

    with client.websocket_connect(f"/ws/host?room={code}&token={host_token}") as host_ws:
        assert host_ws.receive_json()["phase"] == "lobby"

        with client.websocket_connect(
            f"/ws/player?room={code}&token={player_1['player_token']}"
        ) as player_1_ws:
            _ = player_1_ws.receive_json()

            with client.websocket_connect(
                f"/ws/player?room={code}&token={player_2['player_token']}"
            ) as player_2_ws:
                _ = player_2_ws.receive_json()

                for index in range(2):
                    host_ws.send_json({"type": "start" if index == 0 else "next"})
                    host_state = host_ws.receive_json()
                    assert host_state["phase"] == "question"

                    player_1_question = player_1_ws.receive_json()
                    _ = player_2_ws.receive_json()

                    player_1_ws.send_json(
                        {
                            "type": "answer",
                            "option_id": player_1_question["options"][0]["id"],
                        }
                    )
                    _ = player_1_ws.receive_json()
                    _ = player_2_ws.receive_json()
                    _ = host_ws.receive_json()

                    player_2_ws.send_json(
                        {
                            "type": "answer",
                            "option_id": player_1_question["options"][1]["id"],
                        }
                    )
                    _ = player_1_ws.receive_json()
                    _ = player_2_ws.receive_json()
                    _ = player_1_ws.receive_json()
                    _ = player_2_ws.receive_json()
                    assert host_ws.receive_json()["phase"] == "reveal"

                host_ws.send_json({"type": "next"})
                finished_state = host_ws.receive_json()

    assert finished_state["phase"] == "finished"
    assert finished_state["winners"]

    ranking = client.get("/api/ranking").json()
    assert any(entry["name"] in {"Gama", "Delta"} for entry in ranking)


def test_theme_with_few_questions_is_not_padded(client, monkeypatch):
    sample = [
        {
            "category": "Curto",
            "prompt": f"Pergunta {i}?",
            "correct": "Certa",
            "distractors": ["E1", "E2", "E3"],
        }
        for i in range(3)
    ]
    monkeypatch.setattr("app.quiz.bank.theme_questions", lambda _s, _t: (sample, "Curto"))
    response = client.post(
        "/api/rooms",
        json={
            "mode": "session",
            "team_names": ["Um", "Dois"],
            "theme_id": "curto",
            "n": 10,
        },
    )
    assert response.status_code == 201
    assert response.json()["state"]["total"] == 3


def test_unknown_theme_is_rejected(client):
    response = client.post(
        "/api/rooms",
        json={
            "mode": "session",
            "team_names": ["Um", "Dois"],
            "theme_id": "inexistente",
            "n": 5,
        },
    )
    assert response.status_code == 400


def test_unknown_room_returns_404(client):
    assert client.get("/api/rooms/ZZZZZZ/state").status_code == 404
