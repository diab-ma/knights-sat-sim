FROM python:3.12-slim AS development
COPY --from=ghcr.io/astral-sh/uv:0.11.21 /uv /usr/local/bin/uv

# Keep dependencies outside /app so a source bind mount cannot hide them.
ENV UV_PROJECT_ENVIRONMENT=/opt/venv UV_LINK_MODE=copy \
    PATH="/opt/venv/bin:$PATH" PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --locked --extra dev --no-install-project
COPY api ./api
COPY sim ./sim
RUN uv sync --locked --extra dev
COPY tests ./tests

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
