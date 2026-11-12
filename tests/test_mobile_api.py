import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_create_mobile_room_starts_in_lobby(client: TestClient) -> None:
    response = client.post(
        "/api/rooms",
        json={
            "mode": "mobile",
            "team_names": ["Equipe Sol", "Equipe Lua"],
            "theme_id": "jogos",
            "n": 5,
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert "code" in data
    assert "host_token" in data
    state = data["state"]
    assert state["phase"] == "lobby"
    assert state["question"] is None
    assert state["seconds_left"] == 0
    assert len(state["teams"]) == 2
    for team in state["teams"]:
        assert team["players"] == []


def test_create_local_room_still_opens_first_question(client: TestClient) -> None:
    response = client.post(
        "/api/rooms",
        json={
            "mode": "local",
            "team_names": ["Equipe 1", "Equipe 2"],
            "theme_id": "jogos",
            "n": 5,
        },
    )
    assert response.status_code == 201
    state = response.json()["state"]
    assert state["phase"] == "question"
    assert state["question"] is not None
    assert "options" in state["question"]


def test_create_room_with_generated_questions(client: TestClient) -> None:
    generated = [
        {
            "category": "Inovação",
            "prompt": "Qual é o objetivo do Portas Abertas?",
            "correct": "Apresentar a universidade à comunidade",
            "distractors": ["Vender cursos", "Fazer prova", "Distribuir diplomas"],
        },
        {
            "category": "Inovação",
            "prompt": "Em qual estado fica a UEMG?",
            "correct": "Minas Gerais",
            "distractors": ["São Paulo", "Rio de Janeiro", "Bahia"],
        },
    ]
    response = client.post(
        "/api/rooms",
        json={
            "mode": "mobile",
            "team_names": ["Time A", "Time B"],
            "theme_id": "UEMG IA",
            "generated_questions": generated,
        },
    )
    assert response.status_code == 201
    state = response.json()["state"]
    assert state["total"] == 2
    assert state["theme"] == "UEMG IA"


def test_generated_questions_validation_limits(client: TestClient) -> None:
    two_distractors = [
        {
            "category": "Cat",
            "prompt": "Pergunta de teste?",
            "correct": "Certa",
            "distractors": ["Errada 1", "Errada 2"],
        }
    ]
    res_2_dist = client.post(
        "/api/rooms",
        json={
            "mode": "mobile",
            "team_names": ["A", "B"],
            "generated_questions": two_distractors,
        },
    )
    assert res_2_dist.status_code == 422

    long_distractor = [
        {
            "category": "Cat",
            "prompt": "Pergunta?",
            "correct": "Certa",
            "distractors": ["A" * 45, "Errada 2", "Errada 3"],
        }
    ]
    res_long_dist = client.post(
        "/api/rooms",
        json={
            "mode": "mobile",
            "team_names": ["A", "B"],
            "generated_questions": long_distractor,
        },
    )
    assert res_long_dist.status_code == 422

    too_many = [
        {
            "category": "Cat",
            "prompt": f"Pergunta {i}?",
            "correct": "Certa",
            "distractors": ["E1", "E2", "E3"],
        }
        for i in range(21)
    ]
    res_too_many = client.post(
        "/api/rooms",
        json={
            "mode": "mobile",
            "team_names": ["A", "B"],
            "generated_questions": too_many,
        },
    )
    assert res_too_many.status_code == 422


def test_join_info_and_add_players_with_capacity(client: TestClient) -> None:
    create_res = client.post(
        "/api/rooms",
        json={
            "mode": "mobile",
            "team_names": ["Azul", "Vermelho"],
            "theme_id": "jogos",
            "n": 5,
        },
    )
    code = create_res.json()["code"]
    t1_id = create_res.json()["state"]["teams"][0]["id"]
    t2_id = create_res.json()["state"]["teams"][1]["id"]

    info_res = client.get(f"/api/rooms/{code}/join-info")
    assert info_res.status_code == 200
    info = info_res.json()
    assert info["code"] == code
    assert info["phase"] == "lobby"
    assert len(info["teams"]) == 2
    assert info["teams"][0]["members"] == 0
    assert info["teams"][0]["capacity"] == 3

    p1 = client.post(
        f"/api/rooms/{code}/players",
        json={"nickname": "Alice", "team_id": t1_id},
    )
    assert p1.status_code == 201
    p1_data = p1.json()
    assert p1_data["team_id"] == t1_id
    assert p1_data["team_name"] == "Azul"
    assert "player_token" in p1_data
    assert "player_id" in p1_data

    p2 = client.post(
        f"/api/rooms/{code}/players",
        json={"nickname": "Bob", "team_id": t1_id},
    )
    assert p2.status_code == 201

    p3 = client.post(
        f"/api/rooms/{code}/players",
        json={"nickname": "Carol", "team_id": t1_id},
    )
    assert p3.status_code == 201

    p4 = client.post(
        f"/api/rooms/{code}/players",
        json={"nickname": "David", "team_id": t1_id},
    )
    assert p4.status_code == 409

    info_after = client.get(f"/api/rooms/{code}/join-info").json()
    assert info_after["teams"][0]["members"] == 3
    assert info_after["teams"][1]["members"] == 0

    p_t2 = client.post(
        f"/api/rooms/{code}/players",
        json={"nickname": "Eduardo", "team_id": t2_id},
    )
    assert p_t2.status_code == 201


def test_player_validation_rules(client: TestClient) -> None:
    create_res = client.post(
        "/api/rooms",
        json={"mode": "mobile", "team_names": ["T1", "T2"], "n": 3},
    )
    code = create_res.json()["code"]
    team_id = create_res.json()["state"]["teams"][0]["id"]

    empty_nick = client.post(
        f"/api/rooms/{code}/players",
        json={"nickname": "   ", "team_id": team_id},
    )
    assert empty_nick.status_code == 400

    long_nick = client.post(
        f"/api/rooms/{code}/players",
        json={"nickname": "NomeMuitoLongoComMaisDeDezoitoCaracteres", "team_id": team_id},
    )
    assert long_nick.status_code == 400

    bad_team = client.post(
        f"/api/rooms/{code}/players",
        json={"nickname": "Valido", "team_id": "equipe_fantasma"},
    )
    assert bad_team.status_code == 404

    bad_room = client.post(
        "/api/rooms/INEXIST/players",
        json={"nickname": "Valido", "team_id": team_id},
    )
    assert bad_room.status_code == 404


def test_qr_code_image_endpoint(client: TestClient) -> None:
    create_res = client.post(
        "/api/rooms",
        json={"mode": "mobile", "team_names": ["A", "B"], "n": 2},
    )
    code = create_res.json()["code"]

    qr_res = client.get(f"/api/rooms/{code}/qr.png")
    assert qr_res.status_code == 200
    assert qr_res.headers["content-type"] == "image/png"
    assert len(qr_res.content) > 100

    qr_404 = client.get("/api/rooms/999999/qr.png")
    assert qr_404.status_code == 404


def test_play_endpoint_serves_html(client: TestClient) -> None:
    res = client.get("/play")
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]
    assert "Quiz UEMG" in res.text


def test_next_in_lobby_via_http_is_rejected(client: TestClient) -> None:
    create_res = client.post(
        "/api/rooms",
        json={"mode": "mobile", "team_names": ["A", "B"], "n": 2},
    )
    code = create_res.json()["code"]
    token = create_res.json()["host_token"]

    res = client.post(
        f"/api/rooms/{code}/next",
        headers={"X-Host-Token": token},
    )
    assert res.status_code == 409
    assert "não foi iniciada" in res.json()["detail"]
