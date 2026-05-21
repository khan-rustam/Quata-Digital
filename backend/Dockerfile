# syntax=docker/dockerfile:1.7
# ---- builder ----------------------------------------------------------------
# Multi-stage build: compile wheels in a fat builder image, then copy the
# installed packages into a tiny runtime image. Keeps the production
# image free of compilers / libpq-dev / apt cache.
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --prefix=/install -r requirements.txt


# ---- runtime ----------------------------------------------------------------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PATH=/usr/local/bin:$PATH

# `libpq5` (the shared client lib) is enough at runtime — the dev
# headers + compilers stay in the builder. `curl` lets the HEALTHCHECK
# hit /health/ready without bundling a Python script.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 curl tini \
    && rm -rf /var/lib/apt/lists/*

# Non-root runtime user. App owns /app + /app/uploads so it can write
# without escalating privileges.
RUN useradd --create-home --shell /bin/false --uid 10001 quata
WORKDIR /app

COPY --from=builder /install /usr/local
COPY --chown=quata:quata app ./app
COPY --chown=quata:quata alembic ./alembic
COPY --chown=quata:quata alembic.ini ./
COPY --chown=quata:quata start.py ./

# Uploads volume; bind-mount or named volume in compose.
RUN mkdir -p /app/uploads && chown -R quata:quata /app

USER quata

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:8000/health/live || exit 1

# `tini` reaps zombies and forwards SIGTERM cleanly for graceful shutdown.
ENTRYPOINT ["tini", "--"]

# `--proxy-headers` honours X-Forwarded-* from the reverse proxy so
# request.client.host is correct (rate-limit + audit IPs depend on it).
# Worker count is intentionally low (2) for a single-VPS deploy; raise
# it via the orchestrator (compose / systemd / k8s) when needed.
CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "2", \
     "--proxy-headers", \
     "--forwarded-allow-ips=*", \
     "--timeout-graceful-shutdown", "20"]
