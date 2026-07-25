"""QUATA AI event publishers.

The AI capability inside this application (the talent-intelligence engine in
``services/ai_cv.py``) publishes as the **quata_ai** platform, exactly as a
standalone QUATA AI deployment would. Same catalogue, same envelope — an
administrator reading Telegram can't tell, and shouldn't have to.

Availability events are edge-triggered and hourly-deduped: a broken API key
hit by fifty CV analyses is one outage, not fifty alerts.

Successful requests are *not* alerts. They feed an in-process rolling counter
whose only job is to notice a usage spike — the one thing about healthy
traffic that's worth waking someone for.
"""
from __future__ import annotations

import logging
import threading
from collections import deque
from datetime import datetime, timezone
from typing import Optional

from . import settings_store
from .dispatch import emit


log = logging.getLogger("quata.notifications.ai")

PLATFORM = "quata_ai"

# Rolling window of recent successful-request timestamps, used only for
# spike detection. Bounded so it can't grow without limit.
_WINDOW_SECONDS = 300
_REQUESTS: deque[float] = deque(maxlen=5000)
_LOCK = threading.Lock()


def _hour_bucket() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d%H")


def _emit(event_key: str, payload: dict, *, dedupe_suffix: str = "") -> None:
    """Publish an AI event, deduped to one per hour per condition."""
    try:
        emit(
            event_key,
            platform=PLATFORM,
            payload=payload,
            reference="QUATA-AI",
            dedupe_key=f"ai:{event_key}:{dedupe_suffix}:{_hour_bucket()}",
        )
    except Exception:  # noqa: BLE001 — alerting must never break the AI path
        log.debug("notifications.ai_emit_failed", exc_info=True)


# ---------------------------------------------------------------------------
# Availability
# ---------------------------------------------------------------------------

def unavailable(reason: str) -> None:
    """The AI subsystem cannot serve requests at all (no key, no package)."""
    _emit("ai.unavailable", {"service": "QUATA AI · talent intelligence", "error": reason[:400]})


def api_error(*, error: str, model: Optional[str] = None, operation: str = "") -> None:
    """An upstream AI API call failed.

    Deduped per operation so a broken endpoint reports once an hour rather
    than once per user action.
    """
    _emit(
        "ai.api_error",
        {
            "service": "QUATA AI",
            "operation": operation or "unknown",
            "model": model,
            "error": error[:400],
        },
        dedupe_suffix=operation,
    )


def service_started(detail: str = "") -> None:
    _emit("ai.service_started", {"service": "QUATA AI", "detail": detail})


def service_stopped(detail: str = "") -> None:
    _emit("ai.service_stopped", {"service": "QUATA AI", "detail": detail})


def model_updated(*, model: str, previous: Optional[str] = None) -> None:
    _emit(
        "ai.model_updated",
        {"service": "QUATA AI", "model": model, "previous_model": previous},
        dedupe_suffix=model,
    )


def knowledge_base_updated(*, detail: str, documents: Optional[int] = None) -> None:
    _emit(
        "ai.knowledge_base_updated",
        {"service": "QUATA AI", "detail": detail, "documents": documents},
        dedupe_suffix=detail[:40],
    )


def administrator_changed(*, full_name: str, email: str, added: bool) -> None:
    _emit(
        "ai.admin_added" if added else "ai.admin_removed",
        {"service": "QUATA AI", "full_name": full_name, "email": email},
        dedupe_suffix=email,
    )


# ---------------------------------------------------------------------------
# Usage
# ---------------------------------------------------------------------------

def request_succeeded(*, model: Optional[str] = None, operation: str = "") -> None:
    """Record a healthy AI request and alert if traffic spikes.

    Emits nothing on the happy path — per-request notifications would drown
    the channel. Only crossing the configured rate raises ⚠️ AI USAGE SPIKE,
    and that too is deduped to once an hour.
    """
    import time

    now = time.monotonic()
    threshold = settings_store.ai_spike_threshold()
    with _LOCK:
        _REQUESTS.append(now)
        cutoff = now - _WINDOW_SECONDS
        while _REQUESTS and _REQUESTS[0] < cutoff:
            _REQUESTS.popleft()
        recent = len(_REQUESTS)

    if threshold > 0 and recent >= threshold:
        _emit(
            "ai.usage_spike",
            {
                "service": "QUATA AI",
                "operation": operation or "unknown",
                "model": model,
                "metric": f"Requests in the last {_WINDOW_SECONDS // 60} minutes",
                "value": recent,
                "threshold": threshold,
            },
        )


def recent_request_count() -> int:
    """Requests inside the rolling window — used by tests and diagnostics."""
    import time

    now = time.monotonic()
    with _LOCK:
        cutoff = now - _WINDOW_SECONDS
        while _REQUESTS and _REQUESTS[0] < cutoff:
            _REQUESTS.popleft()
        return len(_REQUESTS)
