FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.11.21 /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY api ./api
COPY sim ./sim
RUN uv sync --frozen --extra dev
COPY tests ./tests
ENV PATH=/app/.venv/bin:$PATH
CMD ["pytest", "tests/runtime", "-v"]
