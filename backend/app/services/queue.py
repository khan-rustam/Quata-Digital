"""Background job queue.

Two modes, picked at call time:

  - REDIS_URL is set → enqueue jobs into an RQ queue named "default" and
    return immediately. A separate worker process (`python -m
    app.scripts.email_worker`) consumes them.

  - REDIS_URL is unset → run the function synchronously in the current
    request, return its result. Same code path works for dev + small
    deployments without standing up Redis.

The current callers (newsletter broadcast) only need fire-and-forget
semantics — they record their own audit row up-front. If a future caller
needs the return value back, it can `.result(timeout=...)` on the Job.
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Optional

from app.core.config import settings


log = logging.getLogger("quata.queue")

_queue = None  # type: Optional[Any]


def _get_queue():
    """Lazy-init the RQ queue. Returns None when running in synchronous mode."""
    global _queue
    if _queue is not None:
        return _queue
    if not settings.REDIS_URL:
        return None
    try:
        from redis import Redis  # type: ignore
        from rq import Queue  # type: ignore
    except ImportError:
        log.warning("redis/rq not installed; running synchronously.")
        return None
    try:
        conn = Redis.from_url(settings.REDIS_URL)
        # Verify the connection now so the first enqueue isn't a surprise.
        conn.ping()
    except Exception as exc:  # noqa: BLE001
        log.warning("Redis connection failed (%s); running synchronously.", exc)
        return None
    _queue = Queue("default", connection=conn, default_timeout=600)
    log.info("RQ queue initialised against %s", settings.REDIS_URL)
    return _queue


def enqueue(func: Callable, *args, description: str | None = None, **kwargs):
    """Enqueue a callable for background execution. When Redis isn't
    configured, run synchronously and return the result. Returns either
    `rq.job.Job` (queued) or whatever `func` returned (synchronous)."""
    q = _get_queue()
    if q is None:
        return func(*args, **kwargs)
    return q.enqueue(
        func,
        *args,
        description=description,
        **kwargs,
    )


def queue_status() -> dict:
    """Lightweight health snapshot for the admin UI."""
    q = _get_queue()
    if q is None:
        return {"mode": "synchronous", "queued": 0, "failed": 0}
    try:
        return {
            "mode": "redis",
            "queue": q.name,
            "queued": q.count,
            "failed": q.failed_job_registry.count,
            "started": q.started_job_registry.count,
            "finished_recent": q.finished_job_registry.count,
        }
    except Exception as exc:  # noqa: BLE001
        return {"mode": "redis", "error": str(exc)[:120]}
