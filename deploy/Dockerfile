FROM python:3.12-slim AS server-build
COPY --from=ghcr.io/astral-sh/uv:0.9.18 /uv /usr/local/bin/uv
WORKDIR /app
COPY server/pyproject.toml server/uv.lock ./
COPY server/api ./api
COPY server/sim ./sim
RUN uv sync --locked --no-dev --no-editable

FROM python:3.12-slim AS server
ARG REVISION
LABEL org.opencontainers.image.revision=$REVISION
LABEL org.opencontainers.image.source="https://github.com/senior-design-organization/knights-sat-sim"
WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH" PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY --from=server-build /app /app
RUN mkdir /data && chown 10001:10001 /data
USER 10001:10001
EXPOSE 8000
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]

FROM node:22-alpine AS web-build
WORKDIR /app
COPY ui/package.json ui/package-lock.json ./
RUN npm ci
COPY ui/ ./
ARG REVISION
RUN npm run build && printf "%s\n" "$REVISION" > dist/revision.txt

FROM nginxinc/nginx-unprivileged:stable-alpine AS web
ARG REVISION
LABEL org.opencontainers.image.revision=$REVISION
LABEL org.opencontainers.image.source="https://github.com/senior-design-organization/knights-sat-sim"
COPY deploy/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=web-build /app/dist /usr/share/nginx/html
ENTRYPOINT ["nginx", "-g", "daemon off;"]
