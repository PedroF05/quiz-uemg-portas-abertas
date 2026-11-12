"""Aplicação FastAPI: rotas, arquivos estáticos e ciclo de vida."""

from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .api import routes_generation, routes_quiz, routes_rooms, ws
from .config import settings
from .db.repository import init_db
from .game.engine import EngineError

STATIC_DIR = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db(settings.db_path)
    yield


app = FastAPI(title="Quiz UEMG de Portas Abertas", lifespan=lifespan)

app.include_router(routes_quiz.router)
app.include_router(routes_rooms.router)
app.include_router(routes_generation.router)
app.include_router(ws.router)

app.mount("/css", StaticFiles(directory=STATIC_DIR / "css"), name="css")
app.mount("/js", StaticFiles(directory=STATIC_DIR / "js"), name="js")
app.mount("/img", StaticFiles(directory=STATIC_DIR / "img"), name="img")


@app.middleware("http")
async def no_cache_static_assets(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    response = await call_next(request)
    if request.url.path.startswith(("/css/", "/js/", "/img/")):
        response.headers["Cache-Control"] = "no-cache"
    return response


@app.exception_handler(EngineError)
async def engine_error_handler(_: Request, error: EngineError) -> JSONResponse:
    return JSONResponse(status_code=error.status_code, content={"detail": error.message})


@app.get("/", include_in_schema=False)
def host_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "host.html")


@app.get("/play", include_in_schema=False)
def play_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "play.html")


@app.get("/health", include_in_schema=False)
def health_redirect() -> dict[str, str]:
    return {"status": "ok"}
