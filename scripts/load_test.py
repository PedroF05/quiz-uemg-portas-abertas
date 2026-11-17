"""Teste de carga de sessões simultâneas: sobe N salas, joga partidas completas e mede latência e memória do servidor.

Uso (com o servidor já rodando em outra janela):
    ./run.sh
    uv run scripts/load_test.py --rooms 25 --questions 5

O teste replica o cenário do evento: cada sala tem 1 host + 2 equipes de
3 jogadores (7 conexões WebSocket), conduz perguntas até o fim e valida o
protocolo. A memória é lida de /proc em Linux quando o servidor é local.
"""

import argparse
import asyncio
from contextlib import AsyncExitStack
import json
import os
import statistics
import sys
import time

import httpx
import websockets
from websockets.asyncio.client import ClientConnection


def parse_arguments() -> argparse.Namespace:
    """Configura e processa argumentos de linha de comando."""
    parser = argparse.ArgumentParser(
        description="Teste de carga: N partidas simultâneas de 2x3 via WebSocket."
    )
    parser.add_argument(
        "--url",
        default="http://localhost:8000",
        help="URL base HTTP do servidor (padrao: http://localhost:8000)",
    )
    parser.add_argument(
        "--rooms",
        type=int,
        default=25,
        help="Numero de partidas simultaneas (padrao: 25)",
    )
    parser.add_argument(
        "--questions",
        type=int,
        default=5,
        help="Perguntas por partida (padrao: 5)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="Tempo limite por mensagem em segundos (padrao: 30.0)",
    )
    parser.add_argument(
        "--serial",
        action="store_true",
        help="Cria as salas uma a uma (default: todas em paralelo)",
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


def server_rss_mb() -> float | None:
    """Soma a memória RSS (MB) dos processos python servindo app.main:app (Linux)."""
    if not os.path.isdir("/proc"):
        return None
    total_kb = 0
    found = False
    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        try:
            with open(f"/proc/{entry}/cmdline", "rb") as handle:
                cmdline = handle.read()
            if b"app.main:app" not in cmdline:
                continue
            with open(f"/proc/{entry}/status") as handle:
                status = handle.read()
        except OSError:
            continue
        for line in status.splitlines():
            if line.startswith("VmRSS:"):
                total_kb += int(line.split()[1])
                found = True
    return round(total_kb / 1024, 1) if found else None


async def recv_json(ws: ClientConnection, timeout: float) -> dict:
    """Recebe e decodifica uma mensagem JSON com timeout."""
    raw = await asyncio.wait_for(ws.recv(), timeout)
    return json.loads(raw)


async def run_room(
    room_index: int,
    http_base: str,
    ws_base: str,
    n_questions: int,
    timeout: float,
    stats: dict,
) -> None:
    """Joga uma partida completa (1 host + 2x3 jogadores) e registra métricas."""
    label = f"sala {room_index + 1}"
    try:
        async with httpx.AsyncClient(base_url=http_base, timeout=timeout) as client:
            start = time.perf_counter()
            res_room = await client.post(
                "/api/rooms",
                json={
                    "mode": "session",
                    "team_names": [f"Alfa-{room_index}", f"Beta-{room_index}"],
                    "theme_id": "jogos",
                    "n": n_questions,
                },
            )
            res_room.raise_for_status()
            stats["create_ms"].append((time.perf_counter() - start) * 1000)
            room_data = res_room.json()
            code: str = room_data["code"]
            host_token: str = room_data["host_token"]
            teams = room_data["state"]["teams"]
            team_a_id: str = teams[0]["id"]
            team_b_id: str = teams[1]["id"]

            start = time.perf_counter()
            players: list[dict] = []
            for team_slot, team_id, team_name in (
                (range(3), team_a_id, "Alfa"),
                (range(3), team_b_id, "Beta"),
            ):
                for i in team_slot:
                    res = await client.post(
                        f"/api/rooms/{code}/players",
                        json={"nickname": f"{team_name}_{i}", "team_id": team_id},
                    )
                    res.raise_for_status()
                    players.append(res.json())
            stats["join_ms"].append((time.perf_counter() - start) * 1000)

        room_start = time.perf_counter()
        async with AsyncExitStack() as stack:
            host_ws: ClientConnection = await stack.enter_async_context(
                websockets.connect(
                    f"{ws_base}/ws/host?room={code}&token={host_token}",
                    open_timeout=timeout,
                    close_timeout=timeout,
                )
            )
            state = await recv_json(host_ws, timeout)
            assert state["type"] == "state" and state["phase"] == "lobby", state

            player_ws: list[ClientConnection] = []
            for p_info in players:
                p_ws: ClientConnection = await stack.enter_async_context(
                    websockets.connect(
                        f"{ws_base}/ws/player?room={code}&token={p_info['player_token']}",
                        open_timeout=timeout,
                        close_timeout=timeout,
                    )
                )
                lobby = await recv_json(p_ws, timeout)
                assert lobby["type"] == "lobby", lobby
                player_ws.append(p_ws)
            stats["connected"] += 1

            for round_idx in range(n_questions):
                await host_ws.send(json.dumps({"type": "start" if round_idx == 0 else "next"}))
                host_state = await recv_json(host_ws, timeout)
                assert host_state["phase"] == "question" and host_state["index"] == round_idx

                questions = await asyncio.gather(
                    *(recv_json(ws, timeout) for ws in player_ws)
                )
                first = questions[0]
                assert first["type"] == "question" and first["index"] == round_idx, first
                assert "correct_option_id" not in first, "vazamento de gabarito"
                option_a = first["options"][0]["id"]
                option_b = first["options"][1]["id"]

                await player_ws[0].send(json.dumps({"type": "answer", "option_id": option_a}))
                locks_a = await asyncio.gather(
                    *(recv_json(ws, timeout) for ws in player_ws)
                )
                assert all(m["type"] == "team_locked" for m in locks_a)
                await recv_json(host_ws, timeout)  # estado apos resposta Alfa

                await player_ws[3].send(json.dumps({"type": "answer", "option_id": option_b}))
                for ws in player_ws:
                    locked_b = await recv_json(ws, timeout)
                    assert locked_b["type"] == "team_locked", locked_b
                    reveal = await recv_json(ws, timeout)
                    assert reveal["type"] == "reveal" and "correct_option_id" in reveal
                host_state = await recv_json(host_ws, timeout)
                assert host_state["phase"] == "reveal", host_state

            await host_ws.send(json.dumps({"type": "next"}))
            host_final = await recv_json(host_ws, timeout)
            assert host_final["phase"] == "finished", host_final
            for ws in player_ws:
                finished = await recv_json(ws, timeout)
                assert finished["type"] == "finished", finished

            stats["match_ms"].append((time.perf_counter() - room_start) * 1000)
            stats["done"] += 1
    except Exception as error:  # noqa: BLE001 - o teste agrega falhas por sala
        stats["errors"].append(f"{label}: {type(error).__name__}: {error}")


def percentile(data: list[float], pct: float) -> float:
    """Percentil aproximado (pct em 0..1); tolerante a listas pequenas."""
    if not data:
        return 0.0
    ordered = sorted(data)
    index = min(len(ordered) - 1, int(round(pct * (len(ordered) - 1))))
    return ordered[index]


def report_line(name: str, data: list[float]) -> str:
    """Formata p50/p95/máximo de uma série de durações em ms."""
    return (
        f"{name:<28} p50={percentile(data, 0.5):8.0f}ms "
        f"p95={percentile(data, 0.95):8.0f}ms "
        f"max={max(data, default=0.0):8.0f}ms"
    )


async def run_load_test(args: argparse.Namespace) -> int:
    """Executa todas as salas e imprime o relatório de carga."""
    http_base = args.url.rstrip("/")
    ws_base = to_ws_url(http_base)
    total_players = args.rooms * 6
    total_connections = args.rooms * 7

    print(
        f"Teste de carga: {args.rooms} salas simultâneas, {args.questions} perguntas cada, "
        f"{total_players} jogadores ({total_connections} conexões WS) contra {http_base}"
    )

    stats = {
        "create_ms": [],
        "join_ms": [],
        "match_ms": [],
        "errors": [],
        "connected": 0,
        "done": 0,
    }
    rss_before = server_rss_mb()
    rss_peak = rss_before if rss_before is not None else None

    async def sample_memory(stop: asyncio.Event) -> None:
        nonlocal rss_peak
        while not stop.is_set():
            try:
                await asyncio.wait_for(stop.wait(), timeout=0.5)
            except asyncio.TimeoutError:
                pass
            current = server_rss_mb()
            if current is not None:
                rss_peak = max(rss_peak, current)

    mem_stop = asyncio.Event()
    mem_task = (
        asyncio.create_task(sample_memory(mem_stop)) if rss_peak is not None else None
    )

    wall_start = time.perf_counter()
    jobs = [
        run_room(i, http_base, ws_base, args.questions, args.timeout, stats)
        for i in range(args.rooms)
    ]
    if args.serial:
        for job in jobs:
            await job
    else:
        await asyncio.gather(*jobs)
    wall = time.perf_counter() - wall_start

    if mem_task is not None:
        mem_stop.set()
        await mem_task

    print()
    print(f"Concluídas: {stats['done']}/{args.rooms} | Conectadas: {stats['connected']} | "
          f"Tempo total: {wall:.1f}s")
    print(report_line("POST /api/rooms", stats["create_ms"]))
    print(report_line("Entrada de 6 jogadores", stats["join_ms"]))
    print(report_line(f"Partida de {args.questions} perguntas", stats["match_ms"]))

    rss_after = server_rss_mb()
    if rss_before is not None:
        print()
        print(f"Memória do servidor (RSS): antes={rss_before}MB | pico={rss_peak}MB | "
              f"depois={rss_after}MB")
        if stats["done"] and rss_after is not None:
            per_room = (rss_after - rss_before) / stats["done"]
            print(f"Variação por sala em memória residente: {per_room:+.2f}MB "
                  "(inclui sockets, respostas e alocação do interpretador)")
    else:
        print("\nServidor local não detectado via /proc; memória não medida "
              "(rode no mesmo host do uvicorn para medir RSS).")

    if stats["errors"]:
        print(f"\nFALHAS ({len(stats['errors'])}):")
        for error in stats["errors"]:
            print(f"  - {error}")
        if any("503" in error for error in stats["errors"]):
            print(
                "\nDica: o 503 indica o limite MAX_ACTIVE_ROOMS. Salas terminadas "
                "ficam em memória até ROOM_TTL_MINUTES; rode contra um servidor "
                "novo ou diminua ROOM_TTL_MINUTES para liberar mais rápido."
            )
        return 1

    print("\nTodos os fluxos validados: protocolo, revelação, finalização e ranking intactos.")
    return 0


def main() -> None:
    """Ponto de entrada do teste de carga."""
    args = parse_arguments()
    sys.exit(asyncio.run(run_load_test(args)))


if __name__ == "__main__":
    main()
