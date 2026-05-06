"""RQ worker entry point.

Run on the VPS alongside the web app:

    cd /home/Quata-Digital/backend
    source .venv/bin/activate
    python -m app.scripts.email_worker

Or under systemd as `quata-digital-worker.service`:

    [Service]
    WorkingDirectory=/home/Quata-Digital/backend
    Environment=DATABASE_URL=...
    Environment=REDIS_URL=...
    ExecStart=/home/Quata-Digital/backend/.venv/bin/python -m app.scripts.email_worker
    Restart=on-failure

The worker consumes the "default" RQ queue, where the broadcast endpoint
enqueues per-recipient `send_broadcast_email` jobs.

When `REDIS_URL` is unset the script exits with a clear message so a
misconfigured `systemd` doesn't loop-restart silently.
"""
from __future__ import annotations

import logging
import sys

from app.core.config import settings
from app.core.logging_config import configure_logging


def main() -> int:
    configure_logging()
    log = logging.getLogger("quata.worker")

    if not settings.REDIS_URL:
        print(
            "REDIS_URL is not set. The web app falls back to synchronous "
            "in-request sends, so no worker is required. Set REDIS_URL in "
            "the env to enable the queue.",
            file=sys.stderr,
        )
        return 1

    try:
        from redis import Redis  # type: ignore
        from rq import Queue, Worker  # type: ignore
    except ImportError:
        print(
            "redis/rq aren't installed. Run `pip install -r requirements.txt` "
            "and try again.",
            file=sys.stderr,
        )
        return 2

    try:
        conn = Redis.from_url(settings.REDIS_URL)
        conn.ping()
    except Exception as exc:  # noqa: BLE001
        print(f"Couldn't reach Redis at {settings.REDIS_URL}: {exc}", file=sys.stderr)
        return 3

    log.info("worker.boot", extra={"redis": settings.REDIS_URL})
    queues = [Queue("default", connection=conn)]
    Worker(queues, connection=conn).work(with_scheduler=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
