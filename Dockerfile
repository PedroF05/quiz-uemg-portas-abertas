FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_PREFERENCE=only-system \
    UV_NO_CACHE=1

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/* && \
    groupadd -r -g 1000 appuser && \
    useradd -r -u 1000 -g appuser -m appuser

WORKDIR /app

COPY --chown=appuser:appuser pyproject.toml uv.lock ./
COPY --chown=appuser:appuser app/ app/
COPY --chown=appuser:appuser data/ data/
COPY --chown=appuser:appuser scripts/ scripts/

RUN chown -R appuser:appuser /app

USER appuser

RUN uv sync --frozen --no-dev

EXPOSE 8000

CMD ["/app/.venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
