import time
import pytest
from fastapi.testclient import TestClient

from app.game.manager import manager
from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_full_websocket_match_flow(client: TestClient) -> None:
    res = client.post(
        "/api/rooms",
        json={
            "mode": "mobile",
            "team_names": ["Equipe Alfa", "Equipe Beta"],
            "theme_id": "jogos",
            "n": 2,
        },
    )
    assert res.status_code == 201
    room_data = res.json()
    code = room_data["code"]
    host_token = room_data["host_token"]
    teams = room_data["state"]["teams"]
    t1_id = teams[0]["id"]
    t2_id = teams[1]["id"]

    with client.websocket_connect(f"/ws/host?room={code}&token={host_token}") as host_ws:
        initial_host_msg = host_ws.receive_json()
        assert initial_host_msg["type"] == "state"
        assert initial_host_msg["phase"] == "lobby"

        p1_res = client.post(
            f"/api/rooms/{code}/players",
            json={"nickname": "Gamer1", "team_id": t1_id},
        )
        assert p1_res.status_code == 201
        p1_token = p1_res.json()["player_token"]

        host_after_p1 = host_ws.receive_json()
        assert host_after_p1["type"] == "state"
        assert len(host_after_p1["teams"][0]["players"]) == 1
        assert host_after_p1["teams"][0]["players"][0]["nickname"] == "Gamer1"

        p2_res = client.post(
            f"/api/rooms/{code}/players",
            json={"nickname": "Gamer2", "team_id": t2_id},
        )
        assert p2_res.status_code == 201
        p2_token = p2_res.json()["player_token"]

        host_after_p2 = host_ws.receive_json()
        assert host_after_p2["type"] == "state"
        assert len(host_after_p2["teams"][1]["players"]) == 1

        with client.websocket_connect(f"/ws/player?room={code}&token={p1_token}") as p1_ws:
            p1_lobby = p1_ws.receive_json()
            assert p1_lobby["type"] == "lobby"
            assert p1_lobby["team_id"] == t1_id

            with client.websocket_connect(f"/ws/player?room={code}&token={p2_token}") as p2_ws:
                p2_lobby = p2_ws.receive_json()
                assert p2_lobby["type"] == "lobby"
                assert p2_lobby["team_id"] == t2_id

                host_ws.send_json({"type": "start"})

                p1_q1 = p1_ws.receive_json()
                p2_q1 = p2_ws.receive_json()
                host_q1 = host_ws.receive_json()

                assert p1_q1["type"] == "question"
                assert p1_q1["index"] == 0
                assert p1_q1["total"] == 2
                assert len(p1_q1["options"]) == 4
                assert "correct_option_id" not in p1_q1

                assert p2_q1["type"] == "question"
                assert "correct_option_id" not in p2_q1
                assert host_q1["phase"] == "question"

                opt_team1 = p1_q1["options"][0]["id"]
                p1_ws.send_json({"type": "answer", "option_id": opt_team1})

                p1_lock = p1_ws.receive_json()
                p2_lock = p2_ws.receive_json()
                assert p1_lock["type"] == "team_locked"
                assert p1_lock["team_id"] == t1_id
                assert p2_lock["type"] == "team_locked"
                assert p2_lock["team_id"] == t1_id

                _ = host_ws.receive_json()

                opt_team2 = p2_q1["options"][1]["id"]
                p2_ws.send_json({"type": "answer", "option_id": opt_team2})

                _ = p1_ws.receive_json()
                _ = p2_ws.receive_json()

                p1_reveal = p1_ws.receive_json()
                p2_reveal = p2_ws.receive_json()
                host_reveal = host_ws.receive_json()

                assert p1_reveal["type"] == "reveal"
                assert p2_reveal["type"] == "reveal"
                assert "correct_option_id" in p1_reveal
                assert len(p1_reveal["answers"]) == 2
                assert host_reveal["phase"] == "reveal"

                host_ws.send_json({"type": "next"})

                p1_q2 = p1_ws.receive_json()
                p2_q2 = p2_ws.receive_json()
                host_q2 = host_ws.receive_json()

                assert p1_q2["type"] == "question"
                assert p1_q2["index"] == 1
                assert host_q2["index"] == 1

                p1_ws.send_json({"type": "answer", "option_id": p1_q2["options"][0]["id"]})
                _ = p1_ws.receive_json()
                _ = p2_ws.receive_json()
                _ = host_ws.receive_json()

                p2_ws.send_json({"type": "answer", "option_id": p2_q2["options"][0]["id"]})
                _ = p1_ws.receive_json()
                _ = p2_ws.receive_json()

                p1_rev2 = p1_ws.receive_json()
                p2_rev2 = p2_ws.receive_json()
                host_rev2 = host_ws.receive_json()

                assert p1_rev2["type"] == "reveal"
                assert p2_rev2["type"] == "reveal"
                assert host_rev2["phase"] == "reveal"

                host_ws.send_json({"type": "next"})

                p1_fin = p1_ws.receive_json()
                p2_fin = p2_ws.receive_json()
                host_fin = host_ws.receive_json()

                assert p1_fin["type"] == "finished"
                assert p2_fin["type"] == "finished"
                assert host_fin["phase"] == "finished"
                assert len(p1_fin["winners"]) >= 1

    ranking_res = client.get("/api/ranking")
    assert ranking_res.status_code == 200
    ranking_data = ranking_res.json()
    names = {item["name"] for item in ranking_data}
    assert "Equipe Alfa" in names or "Equipe Beta" in names


def test_player_reconnection(client: TestClient) -> None:
    res = client.post(
        "/api/rooms",
        json={"mode": "mobile", "team_names": ["A", "B"], "n": 2},
    )
    code = res.json()["code"]
    host_token = res.json()["host_token"]
    t1_id = res.json()["state"]["teams"][0]["id"]

    p_res = client.post(
        f"/api/rooms/{code}/players",
        json={"nickname": "Recon", "team_id": t1_id},
    )
    p_token = p_res.json()["player_token"]

    with client.websocket_connect(f"/ws/host?room={code}&token={host_token}") as host_ws:
        initial_host_state = host_ws.receive_json()
        assert initial_host_state["type"] == "state"

        host_ws.send_json({"type": "start"})
        started_host_state = host_ws.receive_json()
        assert started_host_state["phase"] == "question"

        with client.websocket_connect(f"/ws/player?room={code}&token={p_token}") as p_ws:
            q_msg = p_ws.receive_json()
            assert q_msg["type"] == "question"
            assert q_msg["index"] == 0

        with client.websocket_connect(f"/ws/player?room={code}&token={p_token}") as p_reconnect_ws:
            reconnect_msg = p_reconnect_ws.receive_json()
            assert reconnect_msg["type"] == "question"
            assert reconnect_msg["index"] == 0
            assert len(reconnect_msg["options"]) == 4


def test_ws_rejects_invalid_tokens_or_rooms(client: TestClient) -> None:
    res = client.post(
        "/api/rooms",
        json={"mode": "mobile", "team_names": ["A", "B"], "n": 2},
    )
    code = res.json()["code"]

    with pytest.raises(Exception):
        with client.websocket_connect(f"/ws/host?room={code}&token=badtoken"):
            pass

    with pytest.raises(Exception):
        with client.websocket_connect(f"/ws/player?room={code}&token=badtoken"):
            pass

    with pytest.raises(Exception):
        with client.websocket_connect("/ws/host?room=NONEXISTENT&token=any"):
            pass


def test_ws_host_next_in_lobby_returns_error_and_keeps_lobby(client: TestClient) -> None:
    res = client.post(
        "/api/rooms",
        json={"mode": "mobile", "team_names": ["A", "B"], "n": 2},
    )
    code = res.json()["code"]
    host_token = res.json()["host_token"]

    with client.websocket_connect(f"/ws/host?room={code}&token={host_token}") as host_ws:
        init_state = host_ws.receive_json()
        assert init_state["phase"] == "lobby"

        host_ws.send_json({"type": "next"})
        err_msg = host_ws.receive_json()
        assert err_msg["type"] == "error"
        assert "não foi iniciada" in err_msg["detail"]

        check_state = client.get(f"/api/rooms/{code}/state").json()
        assert check_state["phase"] == "lobby"


def test_ws_host_start_without_players_is_rejected(client: TestClient) -> None:
    res = client.post(
        "/api/rooms",
        json={"mode": "mobile", "team_names": ["A", "B"], "n": 2},
    )
    code = res.json()["code"]
    host_token = res.json()["host_token"]

    with client.websocket_connect(f"/ws/host?room={code}&token={host_token}") as host_ws:
        init_state = host_ws.receive_json()
        assert init_state["phase"] == "lobby"

        host_ws.send_json({"type": "start"})
        err_msg = host_ws.receive_json()
        assert err_msg["type"] == "error"
        assert "Não há jogadores" in err_msg["detail"]

        check_state = client.get(f"/api/rooms/{code}/state").json()
        assert check_state["phase"] == "lobby"


def test_same_team_two_players_second_does_not_score_twice(client: TestClient) -> None:
    res = client.post(
        "/api/rooms",
        json={"mode": "mobile", "team_names": ["Time 1", "Time 2"], "n": 2},
    )
    code = res.json()["code"]
    host_token = res.json()["host_token"]
    t1_id = res.json()["state"]["teams"][0]["id"]

    p1_res = client.post(f"/api/rooms/{code}/players", json={"nickname": "P1", "team_id": t1_id})
    p2_res = client.post(f"/api/rooms/{code}/players", json={"nickname": "P2", "team_id": t1_id})
    p1_token = p1_res.json()["player_token"]
    p2_token = p2_res.json()["player_token"]

    with client.websocket_connect(f"/ws/host?room={code}&token={host_token}") as host_ws:
        _ = host_ws.receive_json()
        host_ws.send_json({"type": "start"})
        _ = host_ws.receive_json()

        with client.websocket_connect(f"/ws/player?room={code}&token={p1_token}") as p1_ws:
            q_p1 = p1_ws.receive_json()
            correct_opt = manager.get(code).room.current.correct_option_id

            with client.websocket_connect(f"/ws/player?room={code}&token={p2_token}") as p2_ws:
                _ = p2_ws.receive_json()

                p1_ws.send_json({"type": "answer", "option_id": correct_opt})
                _ = p1_ws.receive_json()
                _ = p2_ws.receive_json()

                p2_ws.send_json({"type": "answer", "option_id": correct_opt})
                p2_lock_again = p2_ws.receive_json()
                assert p2_lock_again["type"] == "team_locked"

                engine = manager.get(code)
                t1 = engine.room.team(t1_id)
                assert t1 is not None
                assert t1.score == 15


def test_ws_player_reconnection_in_reveal_and_finished(client: TestClient) -> None:
    res = client.post(
        "/api/rooms",
        json={"mode": "mobile", "team_names": ["Time 1", "Time 2"], "n": 1},
    )
    code = res.json()["code"]
    host_token = res.json()["host_token"]
    t1_id = res.json()["state"]["teams"][0]["id"]
    t2_id = res.json()["state"]["teams"][1]["id"]

    p1_res = client.post(f"/api/rooms/{code}/players", json={"nickname": "P1", "team_id": t1_id})
    p2_res = client.post(f"/api/rooms/{code}/players", json={"nickname": "P2", "team_id": t2_id})
    p1_token = p1_res.json()["player_token"]
    p2_token = p2_res.json()["player_token"]

    with client.websocket_connect(f"/ws/host?room={code}&token={host_token}") as host_ws:
        _ = host_ws.receive_json()
        host_ws.send_json({"type": "start"})
        _ = host_ws.receive_json()

        with client.websocket_connect(f"/ws/player?room={code}&token={p1_token}") as p1_ws:
            q_p1 = p1_ws.receive_json()
            with client.websocket_connect(f"/ws/player?room={code}&token={p2_token}") as p2_ws:
                _ = p2_ws.receive_json()

                p1_ws.send_json({"type": "answer", "option_id": q_p1["options"][0]["id"]})
                _ = p1_ws.receive_json()
                _ = p2_ws.receive_json()

                p2_ws.send_json({"type": "answer", "option_id": q_p1["options"][1]["id"]})
                _ = p1_ws.receive_json()
                _ = p2_ws.receive_json()

                _ = p1_ws.receive_json()
                _ = p2_ws.receive_json()
                _ = host_ws.receive_json()

        with client.websocket_connect(f"/ws/player?room={code}&token={p1_token}") as p1_rev_ws:
            rev_msg = p1_rev_ws.receive_json()
            assert rev_msg["type"] == "reveal"
            assert "correct_option_id" in rev_msg

        host_ws.send_json({"type": "next"})
        _ = host_ws.receive_json()

        with client.websocket_connect(f"/ws/player?room={code}&token={p2_token}") as p2_fin_ws:
            fin_msg = p2_fin_ws.receive_json()
            assert fin_msg["type"] == "finished"
            assert len(fin_msg["winners"]) >= 1


def test_ws_automatic_timeout_reveal_and_persist(client: TestClient) -> None:
    res = client.post(
        "/api/rooms",
        json={"mode": "mobile", "team_names": ["Time X", "Time Y"], "n": 1},
    )
    code = res.json()["code"]
    host_token = res.json()["host_token"]
    t1_id = res.json()["state"]["teams"][0]["id"]

    p_res = client.post(f"/api/rooms/{code}/players", json={"nickname": "PX", "team_id": t1_id})
    p_token = p_res.json()["player_token"]

    engine = manager.get(code)
    engine.room.question_time = 1

    with client.websocket_connect(f"/ws/host?room={code}&token={host_token}") as host_ws:
        _ = host_ws.receive_json()
        host_ws.send_json({"type": "start"})
        _ = host_ws.receive_json()

        with client.websocket_connect(f"/ws/player?room={code}&token={p_token}") as p_ws:
            _ = p_ws.receive_json()

            rev_msg = p_ws.receive_json()
            assert rev_msg["type"] == "reveal"

            host_rev = host_ws.receive_json()
            assert host_rev["phase"] == "reveal"

            host_ws.send_json({"type": "next"})
            host_fin = host_ws.receive_json()
            assert host_fin["phase"] == "finished"

    ranking_res = client.get("/api/ranking")
    assert ranking_res.status_code == 200
    ranking = ranking_res.json()
    assert any(entry["name"] in {"Time X", "Time Y"} for entry in ranking)
