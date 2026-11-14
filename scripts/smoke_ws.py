"""Script manual de smoke test para fluxo WebSocket 3v3."""

import argparse
import asyncio
from contextlib import AsyncExitStack
import json
import sys
import httpx
import websockets
from websockets.asyncio.client import ClientConnection


def parse_arguments() -> argparse.Namespace:
    """Configura e processa argumentos de linha de comando."""
    parser = argparse.ArgumentParser(
        description="Smoke test manual do fluxo WebSocket mobile 3v3."
    )
    parser.add_argument(
        "--url",
        default="http://localhost:8000",
        help="URL base HTTP do servidor (padrao: http://localhost:8000)",
    )
    parser.add_argument(
        "--n",
        type=int,
        default=2,
        help="Quantidade de questoes na partida (padrao: 2)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="Tempo limite para respostas em segundos (padrao: 30.0)",
    )
    return parser.parse_args()


def to_ws_url(http_url: str) -> str:
    """Converte URL base HTTP para esquema WebSocket correspondente."""
    clean_url = http_url.rstrip("/")
    if clean_url.startswith("https://"):
        return f"wss://{clean_url[8:]}"
    if clean_url.startswith("http://"):
        return f"ws://{clean_url[7:]}"
    return f"ws://{clean_url}"


async def run_smoke_test(http_url: str, n_questions: int, timeout: float) -> None:
    """Executa o ciclo completo de smoke test 3v3 via HTTP e WebSocket."""
    ws_base = to_ws_url(http_url)
    print(f"Iniciando smoke test WS 3v3 contra {http_url} (WS: {ws_base}) com {n_questions} questoes...")

    async with httpx.AsyncClient(base_url=http_url.rstrip("/"), timeout=timeout) as client:
        res_room = await client.post(
            "/api/rooms",
            json={
                "mode": "mobile",
                "team_names": ["Equipe Alfa", "Equipe Beta"],
                "theme_id": "jogos",
                "n": n_questions,
            },
        )
        if res_room.status_code != 201:
            sys.stderr.write(f"Falha ao criar sala: HTTP {res_room.status_code} - {res_room.text}\n")
            sys.exit(1)

        room_data = res_room.json()
        code: str = str(room_data["code"])
        host_token: str = str(room_data["host_token"])
        teams_meta: list[dict[str, str]] = room_data["state"]["teams"]
        team_a_id: str = teams_meta[0]["id"]
        team_b_id: str = teams_meta[1]["id"]
        print(f"[1/6] Sala criada com sucesso: {code} (Equipes: {team_a_id}, {team_b_id})")

        players_info: list[dict[str, str]] = []
        for i in range(1, 4):
            join_a = await client.post(
                f"/api/rooms/{code}/players",
                json={"nickname": f"Alfa_{i}", "team_id": team_a_id},
            )
            if join_a.status_code != 201:
                sys.stderr.write(f"Falha ao cadastrar Alfa_{i}: HTTP {join_a.status_code} - {join_a.text}\n")
                sys.exit(1)
            players_info.append(join_a.json())

        for i in range(1, 4):
            join_b = await client.post(
                f"/api/rooms/{code}/players",
                json={"nickname": f"Beta_{i}", "team_id": team_b_id},
            )
            if join_b.status_code != 201:
                sys.stderr.write(f"Falha ao cadastrar Beta_{i}: HTTP {join_b.status_code} - {join_b.text}\n")
                sys.exit(1)
            players_info.append(join_b.json())

        if len(players_info) != 6:
            sys.stderr.write(f"Esperado 6 jogadores cadastrados, obtido {len(players_info)}\n")
            sys.exit(1)
        print("[2/6] 6 jogadores ingressaram via HTTP (3 na Equipe Alfa e 3 na Equipe Beta)")

    async with AsyncExitStack() as stack:
        host_ws: ClientConnection = await stack.enter_async_context(
            websockets.connect(f"{ws_base}/ws/host?room={code}&token={host_token}")
        )
        raw_host_state = await asyncio.wait_for(host_ws.recv(), timeout=timeout)
        host_state = json.loads(raw_host_state)
        if host_state.get("type") != "state" or host_state.get("phase") != "lobby":
            sys.stderr.write(f"Host WS nao iniciou no lobby: {host_state}\n")
            sys.exit(1)

        teams_in_host = host_state.get("teams", [])
        total_lobby_players = sum(len(t.get("players", [])) for t in teams_in_host)
        if total_lobby_players != 6:
            sys.stderr.write(f"Host reportou {total_lobby_players} jogadores no lobby, esperado 6\n")
            sys.exit(1)
        print("[3/6] Host conectado via WebSocket e reconheceu os 6 jogadores no lobby")

        player_sockets: list[ClientConnection] = []
        for idx, p_info in enumerate(players_info):
            p_ws: ClientConnection = await stack.enter_async_context(
                websockets.connect(f"{ws_base}/ws/player?room={code}&token={p_info['player_token']}")
            )
            raw_p_lobby = await asyncio.wait_for(p_ws.recv(), timeout=timeout)
            p_lobby = json.loads(raw_p_lobby)
            if p_lobby.get("type") != "lobby" or p_lobby.get("team_id") != p_info["team_id"]:
                sys.stderr.write(f"Mensagem de lobby inesperada para jogador {idx}: {p_lobby}\n")
                sys.exit(1)
            player_sockets.append(p_ws)
        print("[4/6] 6 conexoes WebSocket de jogadores estabelecidas simultaneamente")

        print(f"[5/6] Conduzindo partida de {n_questions} rodadas...")
        for round_idx in range(n_questions):
            if round_idx == 0:
                await host_ws.send(json.dumps({"type": "start"}))
            else:
                await host_ws.send(json.dumps({"type": "next"}))

            raw_host_q = await asyncio.wait_for(host_ws.recv(), timeout=timeout)
            host_q_data = json.loads(raw_host_q)
            if host_q_data.get("phase") != "question" or host_q_data.get("index") != round_idx:
                sys.stderr.write(f"Host nao entrou na questao {round_idx}: {host_q_data}\n")
                sys.exit(1)

            player_questions: list[dict[str, str | int | float | list[dict[str, str]]]] = []
            for p_idx, p_ws in enumerate(player_sockets):
                raw_p_q = await asyncio.wait_for(p_ws.recv(), timeout=timeout)
                q_msg = json.loads(raw_p_q)
                if q_msg.get("type") != "question" or q_msg.get("index") != round_idx:
                    sys.stderr.write(f"Jogador {p_idx} recebeu questao invalida: {q_msg}\n")
                    sys.exit(1)
                if "correct_option_id" in q_msg:
                    sys.stderr.write(f"Falha de seguranca: gabarito vazou para jogador {p_idx}!\n")
                    sys.exit(1)
                player_questions.append(q_msg)

            options: list[dict[str, str]] = player_questions[0]["options"]
            if len(options) < 2:
                sys.stderr.write("Questao possui menos de duas alternativas disponiveis\n")
                sys.exit(1)

            chosen_opt_a: str = options[0]["id"]
            chosen_opt_b: str = options[1]["id"]

            await player_sockets[0].send(json.dumps({"type": "answer", "option_id": chosen_opt_a}))

            for p_idx, p_ws in enumerate(player_sockets):
                raw_lock_a = await asyncio.wait_for(p_ws.recv(), timeout=timeout)
                lock_a = json.loads(raw_lock_a)
                if lock_a.get("type") != "team_locked" or lock_a.get("team_id") != team_a_id:
                    sys.stderr.write(f"Jogador {p_idx} nao recebeu trava da Equipe Alfa: {lock_a}\n")
                    sys.exit(1)

            raw_host_after_a = await asyncio.wait_for(host_ws.recv(), timeout=timeout)
            h_after_a = json.loads(raw_host_after_a)
            teams_status_a = {t["id"]: t["answered"] for t in h_after_a.get("teams", [])}
            if not teams_status_a.get(team_a_id) or teams_status_a.get(team_b_id):
                sys.stderr.write(f"Estado de resposta no host divergente: {teams_status_a}\n")
                sys.exit(1)

            await player_sockets[3].send(json.dumps({"type": "answer", "option_id": chosen_opt_b}))

            for p_idx, p_ws in enumerate(player_sockets):
                raw_lock_b = await asyncio.wait_for(p_ws.recv(), timeout=timeout)
                lock_b = json.loads(raw_lock_b)
                if lock_b.get("type") != "team_locked" or lock_b.get("team_id") != team_b_id:
                    sys.stderr.write(f"Jogador {p_idx} nao recebeu trava da Equipe Beta: {lock_b}\n")
                    sys.exit(1)

            raw_host_reveal = await asyncio.wait_for(host_ws.recv(), timeout=timeout)
            host_reveal = json.loads(raw_host_reveal)
            if host_reveal.get("phase") != "reveal":
                sys.stderr.write(f"Host nao transitou para reveal na rodada {round_idx}: {host_reveal}\n")
                sys.exit(1)

            for p_idx, p_ws in enumerate(player_sockets):
                raw_p_reveal = await asyncio.wait_for(p_ws.recv(), timeout=timeout)
                p_reveal = json.loads(raw_p_reveal)
                if p_reveal.get("type") != "reveal" or "correct_option_id" not in p_reveal:
                    sys.stderr.write(f"Jogador {p_idx} recebeu reveal incompleto: {p_reveal}\n")
                    sys.exit(1)

            print(f"  -> Rodada {round_idx + 1}/{n_questions} concluida com sucesso")

        await host_ws.send(json.dumps({"type": "next"}))
        raw_host_fin = await asyncio.wait_for(host_ws.recv(), timeout=timeout)
        host_fin = json.loads(raw_host_fin)
        if host_fin.get("phase") != "finished":
            sys.stderr.write(f"Host nao finalizou a partida: {host_fin}\n")
            sys.exit(1)

        for p_idx, p_ws in enumerate(player_sockets):
            raw_p_fin = await asyncio.wait_for(p_ws.recv(), timeout=timeout)
            p_fin = json.loads(raw_p_fin)
            if p_fin.get("type") != "finished" or "winners" not in p_fin:
                sys.stderr.write(f"Jogador {p_idx} recebeu finalizacao invalida: {p_fin}\n")
                sys.exit(1)

        print("[6/6] Partida finalizada com sucesso em todos os 7 clientes WS")

        print("\n================ PLACAR FINAL ================")
        final_teams: list[dict[str, str | int]] = host_fin.get("teams", [])
        for t in final_teams:
            print(f"- {t.get('name')}: {t.get('score')} pontos")
        winners: list[str] = host_fin.get("winners", [])
        print(f"Vencedor(es): {', '.join(winners)}")
        print("==============================================")

    async with httpx.AsyncClient(base_url=http_url.rstrip("/"), timeout=timeout) as client:
        res_rank = await client.get("/api/ranking")
        if res_rank.status_code != 200:
            sys.stderr.write(f"Falha ao consultar ranking: HTTP {res_rank.status_code}\n")
            sys.exit(1)
        rankings = res_rank.json()
        rank_names = {entry["name"] for entry in rankings}
        if "Equipe Alfa" not in rank_names and "Equipe Beta" not in rank_names:
            sys.stderr.write("Partida nao encontrada no ranking persistido\n")
            sys.exit(1)
        print("Persistencia no ranking validada com sucesso.")


def main() -> None:
    """Ponto de entrada do script de smoke test."""
    args = parse_arguments()
    asyncio.run(
        run_smoke_test(
            http_url=args.url,
            n_questions=args.n,
            timeout=args.timeout,
        )
    )


if __name__ == "__main__":
    main()
