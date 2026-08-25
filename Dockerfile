FROM python:3.13-slim

WORKDIR /app

RUN apt-get update -y \
    && apt-get install -y --no-install-recommends curl unzip ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml rxconfig.py ./
COPY trackforge ./trackforge
COPY assets ./assets
# Pinned frontend deps: reflex recovers dependencies/lockfiles from here and
# does a frozen-lockfile install, so the image gets the exact versions
# committed in reflex.lock/ instead of whatever bun resolves at build time.
COPY reflex.lock ./reflex.lock

RUN pip install --no-cache-dir "reflex>=0.9" "httpx>=0.27" "uvicorn>=0.30"

# Build the static frontend; the backend serves it in prod backend-only mode.
RUN reflex init && reflex export --frontend-only --no-zip

ENV PYTHONUNBUFFERED=1 \
    REFLEX_ENV_MODE=prod \
    __REFLEX_MOUNT_FRONTEND_COMPILED_APP=1
EXPOSE 8000

CMD ["uvicorn", "--factory", "trackforge.trackforge:app", "--host", "0.0.0.0", "--port", "8000"]
