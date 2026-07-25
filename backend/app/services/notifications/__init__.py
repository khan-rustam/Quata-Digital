"""QUATA Notification Service — the single route to @QuataAlertsBot.

Every QUATA platform publishes here; only this package talks to Telegram.

    from app.services import notifications

    notifications.emit(
        "deposit.successful",
        platform="quatapay",
        payload={"full_name": "John Doe", "amount": 25000, "currency": "XAF"},
        reference="TXN-000245",
    )

``emit`` never raises and never blocks on the network, so it is safe to call
straight from a request handler. See ``docs/NOTIFICATIONS.md`` for the HTTP
ingest contract used by the platforms that live outside this repository.
"""
from .catalog import (
    CATEGORIES,
    EVENTS,
    PLATFORMS,
    PRIORITY_CRITICAL,
    PRIORITY_IMPORTANT,
    PRIORITY_INFO,
    PRIORITY_WARNING,
    resolve_event,
)
from .dispatch import (
    deliver_event,
    emit,
    prune_log,
    reclaim_stuck,
    retry_event,
    retry_failed,
    send_test,
    stats,
    sweep_pending,
)

__all__ = [
    "CATEGORIES",
    "EVENTS",
    "PLATFORMS",
    "PRIORITY_CRITICAL",
    "PRIORITY_IMPORTANT",
    "PRIORITY_INFO",
    "PRIORITY_WARNING",
    "resolve_event",
    "deliver_event",
    "emit",
    "prune_log",
    "reclaim_stuck",
    "retry_event",
    "retry_failed",
    "send_test",
    "stats",
    "sweep_pending",
]
