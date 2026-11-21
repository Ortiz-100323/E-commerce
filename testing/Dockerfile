FROM node:22-bookworm-slim AS node

FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:0.11.29 /uv /usr/local/bin/uv
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -s /usr/local/lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx

ENV UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv

WORKDIR /repo

COPY backend/pyproject.toml backend/uv.lock backend/
RUN cd backend && uv sync --frozen --no-install-project

COPY frontend/package.json frontend/package-lock.json frontend/
RUN cd frontend && npm ci

COPY backend backend
COPY frontend frontend
COPY testing testing
RUN cd backend && uv sync --frozen

CMD ["python", "testing/run.py", "all"]
