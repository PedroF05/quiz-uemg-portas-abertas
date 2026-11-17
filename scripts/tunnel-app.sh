#!/usr/bin/env bash
# Sobe o Quiz com um túnel Cloudflare (quick tunnel) para jogadores fora da LAN.
#
# Uso: ./scripts/tunnel-app.sh
#
# O script:
#   1. inicia o cloudflared apontando para a porta local da aplicação;
#   2. captura a URL pública https://<algo>.trycloudflare.com;
#   3. grava PUBLIC_URL no .env (o QR Code e o link de entrada usam essa URL);
#   4. inicia o servidor (run.sh). Ctrl+C encerra servidor e túnel.
#
# Atenção: quick tunnels ganham uma URL NOVA a cada execução. Se reiniciar o
# script, o QR Code muda — recrie a sessão depois de reiniciar. Para URL fixa,
# use um named tunnel (veja docs/operacao-evento.md).
set -euo pipefail
cd "$(dirname "$0")/.."

CLOUDFLARED="${CLOUDFLARED:-./cloudflared}"
if [ ! -x "$CLOUDFLARED" ]; then
  if command -v cloudflared >/dev/null 2>&1; then
    CLOUDFLARED="$(command -v cloudflared)"
  else
    echo "cloudflared não encontrado. Baixe em https://github.com/cloudflare/cloudflared/releases"
    echo "e coloque o binário como ./cloudflared na raiz do projeto (ou defina CLOUDFLARED=/caminho)."
    exit 1
  fi
fi

if [ ! -f .env ]; then
  cp .env.example .env
fi
PORT="$(grep -E '^APP_PORT=' .env | tail -n1 | cut -d= -f2 | tr -d '"' || true)"
PORT="${PORT:-8000}"

LOG="$(mktemp)"
"$CLOUDFLARED" tunnel --no-autoupdate --url "http://localhost:${PORT}" >"$LOG" 2>&1 &
CF_PID=$!
trap 'kill "$CF_PID" 2>/dev/null || true; rm -f "$LOG"' EXIT

URL=""
for _ in $(seq 1 60); do
  URL="$(grep -Eo 'https://[a-z0-9-]+\.trycloudflare\.com' "$LOG" | head -n1 || true)"
  [ -n "$URL" ] && break
  if ! kill -0 "$CF_PID" 2>/dev/null; then
    echo "cloudflared encerrou antes de gerar a URL. Log:"
    cat "$LOG"
    exit 1
  fi
  sleep 0.5
done

if [ -z "$URL" ]; then
  echo "Não foi possível obter a URL do túnel em 30 s. Log:"
  cat "$LOG"
  exit 1
fi

# Grava a URL pública no .env para o QR Code / link de entrada usarem o túnel.
if grep -qE '^PUBLIC_URL=' .env; then
  sed -i "s|^PUBLIC_URL=.*|PUBLIC_URL=${URL}|" .env
else
  echo "PUBLIC_URL=${URL}" >> .env
fi

echo
echo "=============================================================="
echo " Túnel ativo: ${URL}"
echo " Jogadores entram de QUALQUER rede (4G, outro Wi-Fi) pelo QR."
echo " Abra o host em http://localhost:${PORT} e crie a sessão."
echo "=============================================================="
echo

./run.sh