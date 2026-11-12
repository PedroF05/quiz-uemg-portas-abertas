#!/usr/bin/env bash
# Sobe o Quiz UEMG. Uso: ./run.sh
set -euo pipefail
cd "$(dirname "$0")"

if ! command -v uv >/dev/null 2>&1; then
  echo "uv não encontrado. Instale em https://docs.astral.sh/uv/ ou use python -m venv."
  exit 1
fi

uv sync

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Criei .env a partir do .env.example. Edite se quiser usar IA."
fi

HOST="${APP_HOST:-0.0.0.0}"
PORT="${APP_PORT:-8000}"
echo
echo "Quiz disponível em http://localhost:${PORT}"
echo "Na rede local, use o IP deste notebook. Pressione Ctrl+C para parar."
echo
exec uv run uvicorn app.main:app --host "$HOST" --port "$PORT"
