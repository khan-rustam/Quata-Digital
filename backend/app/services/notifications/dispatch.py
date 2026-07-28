"""The QUATA Notification Service core: publish → persist → deliver.

    QuataPay · QuataFood · Abaqwa · QuataTrade · QUATA AI · Quata Digital
                                 │
                                 ▼
                    emit()  ── this module ──►  @QuataAlertsBot
                                 │
                                 ▼
                   Authorized Telegram administrators

``emit()`` is the single entry point every publisher uses, whether it's an
in-process call from this app or an HTTP POST from QuataPay. It is designed
to be *safe to call from a request handler*:

* it never raises — a notification failure must never fail a user's payment;
* it never blocks on Telegram — the row is written, then handed to RQ (when
  Redis is configured) or an in-process thread pool, and the caller returns;
* it is idempotent — a repeat publish of the same event is recorded as a
  duplicate instead of paging the administrators twice.

Delivery state lives entirely in ``notification_events``, so the retry
sweeper can pick up anything the in-process dispatcher dropped (process
restart mid-send, thread pool saturated, Telegram down for an hour).
"""
from __future__ import annotations

import hashlib
import logging
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings as env_settings
from app.db.session import SessionLocal
from app.models import NotificationEvent

from . import settings_store, telegram
from .catalog import (
    BANNER_LARGE_TX,
    DEFAULT_PLATFORM,
    PLATFORMS,
    PRIORITY_CRITICAL,
    priority_rank,
    resolve_event,
)
from .formatter import render
from .recipients import recipients_for
from .redaction import redact_payload


log = logging.getLogger("quata.notifications")

STATUS_PENDING = "pending"
STATUS_SENDING = "sending"
STATUS_SENT = "sent"
STATUS_FAILED = "failed"
STATUS_SUPPRESSED = "suppressed"

# Categories whose amounts are checked against the large-transaction
# threshold. Nothing else has a meaningful "amount" to escalate on.
_MONETARY_CATEGORIES = {"transaction", "trading", "merchant", "payment_gateway"}

_EXECUTOR: Optional[ThreadPoolExecutor] = None


def _executor() -> ThreadPoolExecutor:
    """Lazy in-process fallback worker pool.

    Only used when Redis isn't configured. Small on purpose: it exists so a
    request can hand off a send and return, not to be a general work queue.
    Anything it drops is recovered by ``sweep_pending``.
    """
    global _EXECUTOR
    if _EXECUTOR is None:
        _EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="quata-notify")
    return _EXECUTOR


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_aware(value: Optional[datetime]) -> Optional[datetime]:
    """SQLite hands back naive datetimes; comparisons need them aware."""
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Publish
# ---------------------------------------------------------------------------

def _derive_dedupe_key(
    platform: str, event_key: str, reference: Optional[str], payload: dict
) -> str:
    """Fingerprint an event so an accidental double-publish is caught.

    Bucketed by ``NOTIFY_DEDUPE_WINDOW_SECONDS`` so a genuinely repeated
    business event (the same customer depositing the same amount an hour
    later) still alerts, while a retried HTTP call seconds apart does not.
    """
    window = max(int(env_settings.NOTIFY_DEDUPE_WINDOW_SECONDS), 1)
    bucket = int(_now().timestamp()) // window
    basis = "|".join(
        [
            platform,
            event_key,
            reference or "",
            repr(sorted((str(k), str(v)) for k, v in payload.items())),
            str(bucket),
        ]
    )
    return "auto:" + hashlib.sha256(basis.encode("utf-8")).hexdigest()[:40]


def _amount_of(payload: dict) -> Optional[float]:
    raw = payload.get("amount")
    if raw is None or isinstance(raw, bool):
        return None
    try:
        return float(str(raw).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def _suppression_reason(platform: str, category: str, priority: str) -> Optional[str]:
    """Why this event should not be delivered, or None to proceed."""
    if not settings_store.service_enabled():
        return "Telegram notifications are disabled"
    if platform in PLATFORMS and not settings_store.platform_enabled(platform):
        return f"Platform '{platform}' is disabled"
    if not settings_store.category_enabled(category):
        return f"Category '{category}' is disabled"
    floor = settings_store.min_priority()
    if priority_rank(priority) < priority_rank(floor):
        return f"Priority '{priority}' is below the '{floor}' floor"
    return None


def emit(
    event_key: str,
    *,
    platform: str = DEFAULT_PLATFORM,
    payload: Optional[dict] = None,
    reference: Optional[str] = None,
    priority: Optional[str] = None,
    status: Optional[str] = None,
    banner: Optional[str] = None,
    dedupe_key: Optional[str] = None,
    occurred_at: Optional[datetime] = None,
    source_ip: Optional[str] = None,
    db: Optional[Session] = None,
    dispatch: bool = True,
) -> Optional[str]:
    """Publish one event. Returns its public ``event_id``, or None on error.

    Callers should treat this as fire-and-forget: it swallows every
    exception, because an alerting problem must never surface as a failed
    user action.

    ``db`` is accepted so a caller inside a request can reuse its session
    (the row then commits with the caller's transaction). Omit it and the
    function opens and commits its own — which is what you want when the
    surrounding transaction might roll back and you still want the alert.
    """
    try:
        return _emit_inner(
            event_key,
            platform=platform,
            payload=payload,
            reference=reference,
            priority=priority,
            status=status,
            banner=banner,
            dedupe_key=dedupe_key,
            occurred_at=occurred_at,
            source_ip=source_ip,
            db=db,
            dispatch=dispatch,
        )
    except Exception as exc:  # noqa: BLE001 — alerting must never break callers
        log.exception("notifications.emit_failed", extra={"event_key": event_key, "error": str(exc)[:200]})
        return None


def _emit_inner(
    event_key: str,
    *,
    platform: str,
    payload: Optional[dict],
    reference: Optional[str],
    priority: Optional[str],
    status: Optional[str],
    banner: Optional[str],
    dedupe_key: Optional[str],
    occurred_at: Optional[datetime],
    source_ip: Optional[str],
    db: Optional[Session],
    dispatch: bool,
) -> Optional[str]:
    spec = resolve_event(event_key)
    platform = (platform or DEFAULT_PLATFORM).strip().lower()
    clean_payload = redact_payload(payload)

    effective_priority = (priority or spec.priority).strip().lower()
    effective_banner = banner or spec.banner

    # 💰 Large-transaction escalation. Re-flagging the originating event
    # (rather than emitting a second one) means the administrators get one
    # message carrying the full transaction detail, marked at the severity
    # the amount deserves.
    amount = _amount_of(clean_payload)
    if (
        amount is not None
        and spec.category in _MONETARY_CATEGORIES
        and amount >= settings_store.large_transaction_threshold()
    ):
        effective_banner = BANNER_LARGE_TX
        effective_priority = PRIORITY_CRITICAL

    message = render(
        spec=spec,
        platform=platform,
        payload=clean_payload,
        priority=effective_priority,
        banner=effective_banner,
        status=status,
        reference=reference,
        occurred_at=occurred_at,
    )

    key = dedupe_key or _derive_dedupe_key(platform, event_key, reference, clean_payload)
    suppressed = _suppression_reason(platform, spec.category, effective_priority)

    row = NotificationEvent(
        event_id=uuid.uuid4().hex[:24],
        platform=platform,
        event_key=event_key,
        category=spec.category,
        priority=effective_priority,
        status=STATUS_SUPPRESSED if suppressed else STATUS_PENDING,
        title=spec.label[:200],
        payload=clean_payload,
        message=message,
        dedupe_key=key[:200],
        reference=str(reference)[:160] if reference not in (None, "") else None,
        attempts=0,
        max_attempts=max(int(env_settings.NOTIFY_MAX_ATTEMPTS), 1),
        next_attempt_at=None if suppressed else _now(),
        delivery=[],
        suppressed_reason=suppressed[:200] if suppressed else None,
        source_ip=source_ip,
    )

    owns_session = db is None
    session = db or SessionLocal()
    try:
        session.add(row)
        try:
            session.flush()
        except IntegrityError:
            # Unique violation on dedupe_key: this exact event is already
            # recorded. Idempotent by design — report the original.
            session.rollback()
            existing = (
                session.query(NotificationEvent)
                .filter(NotificationEvent.dedupe_key == key[:200])
                .first()
            )
            if existing:
                log.info(
                    "notifications.duplicate_suppressed",
                    extra={"event_key": event_key, "event_id": existing.event_id},
                )
                return existing.event_id
            return None
        if owns_session:
            session.commit()
        event_id = row.event_id
    finally:
        if owns_session:
            session.close()

    if suppressed:
        log.info(
            "notifications.suppressed",
            extra={"event_key": event_key, "reason": suppressed, "event_id": event_id},
        )
        return event_id

    if dispatch:
        # When the caller owns the session the row isn't committed yet, so a
        # worker picking it up now would find nothing. Handing off after the
        # caller commits isn't something we can hook portably — instead the
        # dispatcher tolerates a missing row and the sweeper retries it.
        schedule(event_id)
    return event_id


# ---------------------------------------------------------------------------
# Async hand-off
# ---------------------------------------------------------------------------

def schedule(event_id: str) -> None:
    """Hand an event to a background worker. Never blocks, never raises."""
    try:
        from app.services.queue import _get_queue  # noqa: PLC0415

        queue = _get_queue()
    except Exception:  # noqa: BLE001
        queue = None

    if queue is not None:
        try:
            queue.enqueue(deliver_event, event_id, description=f"notify:{event_id}")
            return
        except Exception as exc:  # noqa: BLE001 — fall through to threads
            log.warning("notifications.enqueue_failed", extra={"error": str(exc)[:200]})

    try:
        _executor().submit(deliver_event, event_id)
    except Exception as exc:  # noqa: BLE001
        # Nothing dispatched now — sweep_pending() will catch it.
        log.warning("notifications.submit_failed", extra={"error": str(exc)[:200]})


def _backoff_seconds(attempts: int) -> int:
    """1m, 2m, 4m, 8m … capped at an hour."""
    return min(60 * (2 ** max(attempts - 1, 0)), 3600)


# ---------------------------------------------------------------------------
# Delivery
# ---------------------------------------------------------------------------

def deliver_event(event_id: str) -> dict:
    """Deliver one event to every matching recipient.

    Runs off the request path (RQ worker or the local thread pool) and owns
    its own DB session. Safe to call concurrently: the row is claimed with a
    guarded UPDATE, so a second worker on the same event is a no-op.
    """
    db = SessionLocal()
    try:
        row = (
            db.query(NotificationEvent)
            .filter(NotificationEvent.event_id == event_id)
            .first()
        )
        if row is None:
            # Emitted inside a caller-owned transaction that hasn't
            # committed yet (or was rolled back). The sweeper re-checks.
            return {"ok": False, "reason": "not_found"}
        if row.status in (STATUS_SENT, STATUS_SUPPRESSED):
            return {"ok": True, "reason": "already_final", "status": row.status}

        # Claim: only one worker may move pending → sending.
        claimed = (
            db.query(NotificationEvent)
            .filter(
                NotificationEvent.id == row.id,
                NotificationEvent.status.in_([STATUS_PENDING, STATUS_FAILED]),
            )
            .update(
                {
                    NotificationEvent.status: STATUS_SENDING,
                    NotificationEvent.attempts: NotificationEvent.attempts + 1,
                },
                synchronize_session=False,
            )
        )
        db.commit()
        if not claimed:
            return {"ok": False, "reason": "claimed_elsewhere"}
        db.refresh(row)

        return _send_row(db, row)
    except Exception as exc:  # noqa: BLE001
        log.exception("notifications.deliver_failed", extra={"event_id": event_id, "error": str(exc)[:200]})
        return {"ok": False, "reason": "exception", "error": str(exc)[:200]}
    finally:
        db.close()


def _send_row(db: Session, row: NotificationEvent) -> dict:
    if not telegram.is_configured():
        return _record_failure(db, row, "Telegram bot token is not configured.", retryable=True)

    targets = recipients_for(
        db, platform=row.platform, category=row.category, priority=row.priority
    )
    if not targets:
        row.status = STATUS_SUPPRESSED
        row.suppressed_reason = "No authorised recipient matches this event"
        row.next_attempt_at = None
        db.commit()
        return {"ok": True, "delivered": 0, "reason": "no_recipients"}

    # Chats that already succeeded on an earlier attempt are skipped, so a
    # partial failure never double-messages the administrators who did get it.
    previous = row.delivery or []
    already_ok = {str(d.get("chat_id")) for d in previous if isinstance(d, dict) and d.get("ok")}

    results: list[dict] = [d for d in previous if isinstance(d, dict) and d.get("ok")]
    delivered = 0
    retryable_failure = False
    last_error: Optional[str] = None

    for recipient in targets:
        if str(recipient.chat_id) in already_ok:
            continue
        outcome = telegram.send_message(recipient.chat_id, row.message or row.title)
        results.append(
            {
                "chat_id": str(recipient.chat_id),
                "label": recipient.label,
                "ok": outcome.ok,
                "message_id": outcome.message_id,
                "error": outcome.error,
                "at": _now().isoformat(),
            }
        )
        if outcome.ok:
            delivered += 1
            recipient.last_ok_at = _now()
            recipient.last_error = None
        else:
            last_error = outcome.error
            recipient.last_error = (outcome.error or "")[:500]
            if outcome.retryable:
                retryable_failure = True

    row.delivery = results
    # "Done" means every *current* target has an ok record. Counting ok rows
    # instead would mark the event sent when a recipient that succeeded on an
    # earlier attempt has since been removed and a new one failed.
    succeeded = {str(r.get("chat_id")) for r in results if r.get("ok")}
    outstanding = [t for t in targets if str(t.chat_id) not in succeeded]

    if not outstanding:
        row.status = STATUS_SENT
        row.sent_at = _now()
        row.next_attempt_at = None
        row.last_error = None
        db.commit()
        log.info(
            "notifications.sent",
            extra={"event_id": row.event_id, "event_key": row.event_key, "recipients": delivered},
        )
        return {"ok": True, "delivered": delivered}

    return _record_failure(
        db,
        row,
        last_error or "Delivery incomplete",
        retryable=retryable_failure,
        keep_delivery=True,
    )


def _record_failure(
    db: Session,
    row: NotificationEvent,
    error: str,
    *,
    retryable: bool,
    keep_delivery: bool = False,
) -> dict:
    """Move a row out of `sending` after an unsuccessful attempt."""
    row.last_error = (error or "")[:500]
    exhausted = row.attempts >= row.max_attempts
    if retryable and not exhausted:
        row.status = STATUS_PENDING
        row.next_attempt_at = _now() + timedelta(seconds=_backoff_seconds(row.attempts))
    else:
        row.status = STATUS_FAILED
        row.next_attempt_at = None
    db.commit()
    log.warning(
        "notifications.delivery_failed",
        extra={
            "event_id": row.event_id,
            "attempts": row.attempts,
            "status": row.status,
            "retryable": retryable,
        },
    )
    return {
        "ok": False,
        "status": row.status,
        "attempts": row.attempts,
        "error": row.last_error,
    }


# ---------------------------------------------------------------------------
# Recovery
# ---------------------------------------------------------------------------

def sweep_pending(limit: int = 100) -> dict:
    """Deliver every event that's due. Called by the notification worker.

    This is the safety net that makes the "queue notifications if Telegram
    is temporarily unavailable" requirement real: nothing depends on the
    in-process thread pool surviving, only on this running periodically.
    """
    db = SessionLocal()
    try:
        due = (
            db.query(NotificationEvent.event_id)
            .filter(NotificationEvent.status == STATUS_PENDING)
            .filter(
                (NotificationEvent.next_attempt_at.is_(None))
                | (NotificationEvent.next_attempt_at <= _now())
            )
            .order_by(NotificationEvent.id)
            .limit(limit)
            .all()
        )
        event_ids = [e[0] for e in due]
    finally:
        db.close()

    sent = 0
    failed = 0
    for event_id in event_ids:
        outcome = deliver_event(event_id)
        if outcome.get("ok"):
            sent += 1
        else:
            failed += 1
    return {"picked": len(event_ids), "sent": sent, "failed": failed}


def reclaim_stuck(older_than_minutes: int = 15) -> int:
    """Return events wedged in `sending` to `pending`.

    A worker killed mid-send leaves its claim behind. Without this the
    event would sit in `sending` forever and never retry.
    """
    cutoff = _now() - timedelta(minutes=older_than_minutes)
    db = SessionLocal()
    try:
        count = (
            db.query(NotificationEvent)
            .filter(NotificationEvent.status == STATUS_SENDING)
            .filter(NotificationEvent.updated_at <= cutoff)
            .update(
                {
                    NotificationEvent.status: STATUS_PENDING,
                    NotificationEvent.next_attempt_at: _now(),
                },
                synchronize_session=False,
            )
        )
        db.commit()
        if count:
            log.warning("notifications.reclaimed_stuck", extra={"count": count})
        return count
    finally:
        db.close()


def retry_event(event_id: str, *, reset_attempts: bool = True) -> dict:
    """Admin-triggered retry of a failed (or suppressed) event.

    Re-sends the *stored* message rather than re-rendering it, so what the
    administrators eventually receive matches what the audit log says was
    approved at emit time.
    """
    db = SessionLocal()
    try:
        row = (
            db.query(NotificationEvent)
            .filter(NotificationEvent.event_id == event_id)
            .first()
        )
        if row is None:
            return {"ok": False, "error": "Event not found"}
        if row.status == STATUS_SENT:
            return {"ok": True, "status": STATUS_SENT, "note": "Already delivered"}
        if reset_attempts:
            row.attempts = 0
        row.status = STATUS_PENDING
        row.suppressed_reason = None
        row.next_attempt_at = _now()
        db.commit()
    finally:
        db.close()
    return deliver_event(event_id)


def retry_failed(limit: int = 50) -> dict:
    """Bulk retry — the "Retry failed notifications" admin button."""
    db = SessionLocal()
    try:
        rows = (
            db.query(NotificationEvent.event_id)
            .filter(NotificationEvent.status == STATUS_FAILED)
            .order_by(NotificationEvent.id.desc())
            .limit(limit)
            .all()
        )
        event_ids = [r[0] for r in rows]
    finally:
        db.close()

    requeued = 0
    for event_id in event_ids:
        outcome = retry_event(event_id)
        if outcome.get("ok"):
            requeued += 1
    return {"retried": len(event_ids), "delivered": requeued}


def prune_log(days: Optional[int] = None) -> int:
    """Delete delivery records older than the retention window."""
    horizon = days if days is not None else env_settings.NOTIFICATION_LOG_RETENTION_DAYS
    cutoff = _now() - timedelta(days=max(int(horizon), 1))
    db = SessionLocal()
    try:
        count = (
            db.query(NotificationEvent)
            .filter(NotificationEvent.created_at < cutoff)
            .delete(synchronize_session=False)
        )
        db.commit()
        return count
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Diagnostics
# ---------------------------------------------------------------------------

def send_test(*, triggered_by: str) -> dict:
    """Send a test alert through the whole pipeline, synchronously.

    Deliberately *not* fire-and-forget: the admin clicked "Send test" and is
    waiting for an answer, so this returns the real delivery outcome.
    """
    event_id = emit(
        "website.support_request",
        platform=DEFAULT_PLATFORM,
        payload={
            "full_name": triggered_by,
            "note": "Test notification from the QUATA admin console.",
            "checked": "Bot token, recipients, formatting and delivery",
        },
        reference=f"TEST-{uuid.uuid4().hex[:8].upper()}",
        status="🧪 TEST",
        # A unique key so repeated tests are never deduped against each other.
        dedupe_key=f"test:{uuid.uuid4().hex}",
        dispatch=False,
    )
    if not event_id:
        return {"ok": False, "error": "Couldn't record the test event."}

    db = SessionLocal()
    try:
        row = (
            db.query(NotificationEvent)
            .filter(NotificationEvent.event_id == event_id)
            .first()
        )
        if row is not None and row.status == STATUS_SUPPRESSED:
            return {
                "ok": False,
                "event_id": event_id,
                "error": row.suppressed_reason or "Event was suppressed by the current settings.",
            }
    finally:
        db.close()

    outcome = deliver_event(event_id)
    outcome["event_id"] = event_id
    return outcome


def stats(db: Session, *, hours: int = 24) -> dict:
    """Counts for the admin dashboard header."""
    from sqlalchemy import func

    since = _now() - timedelta(hours=hours)
    rows = (
        db.query(NotificationEvent.status, func.count(NotificationEvent.id))
        .filter(NotificationEvent.created_at >= since)
        .group_by(NotificationEvent.status)
        .all()
    )
    by_status = {status: count for status, count in rows}
    return {
        "window_hours": hours,
        "total": sum(by_status.values()),
        "sent": by_status.get(STATUS_SENT, 0),
        "pending": by_status.get(STATUS_PENDING, 0) + by_status.get(STATUS_SENDING, 0),
        "failed": by_status.get(STATUS_FAILED, 0),
        "suppressed": by_status.get(STATUS_SUPPRESSED, 0),
    }
