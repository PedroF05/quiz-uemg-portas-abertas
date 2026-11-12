@echo off
cd /d "%~dp0"

where uv >nul 2>nul
if errorlevel 1 (
  echo uv nao encontrado. Instale em https://docs.astral.sh/uv/
  pause
  exit /b 1
)

uv sync

if not exist .env (
  copy .env.example .env >nul
  echo Criei .env a partir do .env.example.
)

echo.
echo Quiz disponivel em http://localhost:8000
echo Na rede local, use o IP deste notebook.
echo.
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
pause
