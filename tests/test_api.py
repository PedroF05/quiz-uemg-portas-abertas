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
            "mode": "local",
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


def test_themes_are_listed(client):
    themes = client.get("/api/themes").json()
    ids = {theme["id"] for theme in themes}
    assert {"jogos", "filmes", "series", "anime", "tecnologia"} <= ids


def test_question_payload_does_not_leak_answer(client, room):
    state = room["state"]
    assert state["phase"] == "question"
    assert state["reveal"] is None
    assert "correct_option_id" not in state["question"]


def test_answer_requires_host_token(client, room):
    state = room["state"]
    response = client.post(
        f"/api/rooms/{room['code']}/answer",
        json={
            "team_id": state["turn_team_id"],
            "option_id": state["question"]["options"][0]["id"],
        },
    )
    assert response.status_code == 403


def test_full_match_persists_ranking(client):
    response = client.post(
        "/api/rooms",
        json={
            "mode": "local",
            "team_names": ["Gama", "Delta"],
            "theme_id": "",
            "n": 2,
        },
    )
    data = response.json()
    code, token = data["code"], data["host_token"]
    headers = {"X-Host-Token": token}
    state = data["state"]

    for _ in range(100):
        if state["phase"] == "finished":
            break
        if state["phase"] == "question":
            result = client.post(
                f"/api/rooms/{code}/answer",
                json={
                    "team_id": state["turn_team_id"],
                    "option_id": state["question"]["options"][0]["id"],
                },
                headers=headers,
            )
        else:
            result = client.post(f"/api/rooms/{code}/next", headers=headers)
        assert result.status_code == 200, result.text
        state = result.json()

    assert state["phase"] == "finished"
    assert state["winners"]

    ranking = client.get("/api/ranking").json()
    assert any(entry["name"] in {"Gama", "Delta"} for entry in ranking)


def test_theme_with_few_questions_is_not_padded(client):
    response = client.post(
        "/api/rooms",
        json={
            "mode": "local",
            "team_names": ["Um", "Dois"],
            "theme_id": "anime",
            "n": 10,
        },
    )
    assert response.status_code == 201
    assert response.json()["state"]["total"] == 3


def test_unknown_theme_is_rejected(client):
    response = client.post(
        "/api/rooms",
        json={
            "mode": "local",
            "team_names": ["Um", "Dois"],
            "theme_id": "inexistente",
            "n": 5,
        },
    )
    assert response.status_code == 400


def test_unknown_room_returns_404(client):
    assert client.get("/api/rooms/ZZZZZZ/state").status_code == 404
