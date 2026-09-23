FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:0.12.18 /uv /usr/local/bin/uv

WORKDIR /app

RUN apt-get update -y \
    && apt-get install -y --no-install-recommends curl unzip ca-certificates \
    && rm -rf /var/lib/apt/lists/*

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PATH="/app/.venv/bin:$PATH"

# Backend deps come from uv.lock, the same lockfile CI tests against and
# Dependabot updates, so the image can't drift from pyproject.toml.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY rxconfig.py ./
COPY trackforge ./trackforge
COPY assets ./assets
# Pinned frontend deps: reflex recovers dependencies/lockfiles from here and
# does a frozen-lockfile install, so the image gets the exact versions
# committed in reflex.lock/ instead of whatever bun resolves at build time.
COPY reflex.lock ./reflex.lock

# Build the static frontend; the backend serves it in prod backend-only mode.
RUN reflex init && reflex export --frontend-only --no-zip

ENV PYTHONUNBUFFERED=1 \
    REFLEX_ENV_MODE=prod \
    __REFLEX_MOUNT_FRONTEND_COMPILED_APP=1
EXPOSE 8000

CMD ["granian", "--interface", "asgi", "--factory", "--host", "0.0.0.0", "--port", "8000", "trackforge.trackforge:app"]
