"""The scheduled daily business summary.

QuataPay, QuataFood, Abaqwa, QuataTrade and QUATA AI each own their own
database; this service does not query them. What it *does* have is the
complete stream of events those platforms published over the last 24 hours,
which is enough to report the numbers the daily report asks for.

Two sources, in precedence order:

1. **Platform-supplied metrics.** A platform that wants authoritative
   figures publishes a ``summary.daily`` event carrying a ``metrics``
   object; whatever it sends is reported verbatim. This is the escape hatch
   for anything the event stream can't see (balances, MAUs, uptime %).
2. **Derived counts.** Otherwise the figures are counted from the events
   received in the window — deposits, orders, trades and so on.

The Quata Digital Enterprise section is computed directly from this
application's own tables, since that data *is* local.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models import NotificationEvent

from . import settings_store
from .catalog import BANNER_SUMMARY, platform_name
from .dispatch import emit
from .formatter import render_summary


log = logging.getLogger("quata.notifications.digest")


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Event-stream aggregation
# ---------------------------------------------------------------------------

def _counts_by_key(db: Session, platform: str, since: datetime) -> dict[str, int]:
    rows = (
        db.query(NotificationEvent.event_key, func.count(NotificationEvent.id))
        .filter(NotificationEvent.platform == platform)
        .filter(NotificationEvent.created_at >= since)
        .group_by(NotificationEvent.event_key)
        .all()
    )
    return {key: count for key, count in rows}


def _events(db: Session, platform: str, since: datetime, keys: tuple[str, ...]) -> list[NotificationEvent]:
    return (
        db.query(NotificationEvent)
        .filter(NotificationEvent.platform == platform)
        .filter(NotificationEvent.created_at >= since)
        .filter(NotificationEvent.event_key.in_(keys))
        .all()
    )


def _sum_amounts(events: list[NotificationEvent]) -> float:
    total = 0.0
    for event in events:
        raw = (event.payload or {}).get("amount")
        if raw is None or isinstance(raw, bool):
            continue
        try:
            total += float(str(raw).replace(",", "").strip())
        except (TypeError, ValueError):
            continue
    return total


def _distinct_payload_values(events: list[NotificationEvent], field: str) -> int:
    seen = {
        str((e.payload or {}).get(field))
        for e in events
        if (e.payload or {}).get(field) not in (None, "")
    }
    return len(seen)


def _supplied_metrics(db: Session, platform: str, since: datetime) -> Optional[dict]:
    """Most recent platform-published ``summary.daily`` metrics, if any."""
    row = (
        db.query(NotificationEvent)
        .filter(NotificationEvent.platform == platform)
        .filter(NotificationEvent.event_key == "summary.daily")
        .filter(NotificationEvent.created_at >= since)
        .order_by(NotificationEvent.id.desc())
        .first()
    )
    if row is None:
        return None
    metrics = (row.payload or {}).get("metrics")
    return metrics if isinstance(metrics, dict) and metrics else None


def _rows_from_metrics(metrics: dict) -> list[tuple[str, Any]]:
    from .formatter import label_for

    return [(label_for(key), value) for key, value in metrics.items()]


# ---------------------------------------------------------------------------
# Per-platform sections
# ---------------------------------------------------------------------------

def _sum_fees(events: list[NotificationEvent]) -> float:
    """Fees are QUATA's revenue on a transaction — sum them for the report."""
    total = 0.0
    for event in events:
        payload = event.payload or {}
        raw = payload.get("fee", payload.get("fees"))
        if raw is None or isinstance(raw, bool):
            continue
        try:
            total += float(str(raw).replace(",", "").strip())
        except (TypeError, ValueError):
            continue
    return total


_QUATAPAY_MONEY_EVENTS = (
    "deposit.successful",
    "withdrawal.completed",
    "transfer.wallet_to_wallet",
    "transfer.internal",
    "payment.merchant",
    "payment.qr",
    "payment.request_accepted",
    "merchant.settlement_completed",
)


def _quatapay_section(db: Session, since: datetime) -> list[tuple[str, Any]]:
    counts = _counts_by_key(db, "quatapay", since)
    money = _events(db, "quatapay", since, _QUATAPAY_MONEY_EVENTS)

    # Pending KYC = submitted but not yet decided inside this window. It can
    # go slightly negative when an approval lands for a submission from an
    # earlier window, so it's floored at zero rather than reported as a
    # nonsense figure.
    pending_kyc = max(
        counts.get("kyc.submitted", 0)
        - counts.get("kyc.approved", 0)
        - counts.get("kyc.rejected", 0),
        0,
    )
    return [
        ("New Users", counts.get("user.registered", 0)),
        ("Deposits", counts.get("deposit.successful", 0)),
        ("Withdrawals", counts.get("withdrawal.completed", 0)),
        ("Transaction Volume (XAF)", int(_sum_amounts(money))),
        ("Revenue · Fees (XAF)", int(_sum_fees(money))),
        ("Merchant Registrations", counts.get("merchant.registered", 0)),
        ("KYC Submitted", counts.get("kyc.submitted", 0)),
        ("KYC Approved", counts.get("kyc.approved", 0)),
        ("KYC Rejected", counts.get("kyc.rejected", 0)),
        ("Pending KYC", pending_kyc),
    ]


def _quatafood_section(db: Session, since: datetime) -> list[tuple[str, Any]]:
    counts = _counts_by_key(db, "quatafood", since)
    return [
        ("New Restaurants", counts.get("restaurant.registered", 0)),
        ("Orders", counts.get("order.placed", 0)),
        ("Completed Deliveries", counts.get("order.delivered", 0)),
        ("Cancelled Orders", counts.get("order.cancelled", 0)),
    ]


def _abaqwa_section(db: Session, since: datetime) -> list[tuple[str, Any]]:
    counts = _counts_by_key(db, "abaqwa", since)
    rider_events = _events(
        db, "abaqwa", since, ("rider.assigned", "rider.accepted", "delivery.completed")
    )
    requests = (
        counts.get("delivery.requested", 0)
        + counts.get("ride.requested", 0)
        + counts.get("parcel.requested", 0)
    )
    return [
        ("Delivery Requests", requests),
        ("Completed Deliveries", counts.get("delivery.completed", 0)),
        ("Active Riders", _distinct_payload_values(rider_events, "rider")),
    ]


def _quatatrade_section(db: Session, since: datetime) -> list[tuple[str, Any]]:
    counts = _counts_by_key(db, "quatatrade", since)
    escrow = (
        counts.get("escrow.funded", 0)
        + counts.get("escrow.released", 0)
        + counts.get("escrow.dispute_opened", 0)
    )
    new_users = counts.get("account.created", 0) + counts.get("user.registered", 0)
    return [
        ("New Users", new_users),
        ("Trades Completed", counts.get("trade.completed", 0)),
        ("Escrow Transactions", escrow),
    ]


def _quata_ai_section(db: Session, since: datetime) -> list[tuple[str, Any]]:
    counts = _counts_by_key(db, "quata_ai", since)
    ai_events = (
        db.query(NotificationEvent)
        .filter(NotificationEvent.platform == "quata_ai")
        .filter(NotificationEvent.created_at >= since)
        .all()
    )
    # A platform that reports its own request count wins; otherwise the
    # number of events we received is the best proxy we have.
    requests = sum(
        int(value)
        for value in (
            (e.payload or {}).get("requests")
            for e in ai_events
        )
        if isinstance(value, (int, float))
    ) or len(ai_events)

    down_keys = ("ai.unavailable", "ai.system_overload", "ai.service_stopped")
    status = "🟢 Operational"
    if any(counts.get(key) for key in down_keys):
        status = "🔴 Degraded"
    elif counts.get("ai.usage_spike") or counts.get("ai.restarted"):
        status = "🟡 Unstable"

    return [
        ("Total Requests", requests),
        ("Active Users", _distinct_payload_values(ai_events, "user_id")),
        ("API Errors", counts.get("ai.api_error", 0)),
        ("System Status", status),
    ]


def _quata_digital_section(db: Session, since: datetime) -> list[tuple[str, Any]]:
    """Computed from this application's own tables, not the event stream."""
    from app.models import (
        Application,
        ContactMessage,
        NewsletterSubscriber,
        PartnerRequest,
        User,
    )

    def _count(model) -> int:
        try:
            return (
                db.query(func.count(model.id))
                .filter(model.created_at >= since)
                .scalar()
                or 0
            )
        except Exception:  # noqa: BLE001 — never let one table break the report
            return 0

    rows: list[tuple[str, Any]] = [
        ("Contact Enquiries", _count(ContactMessage)),
        ("Partner Requests", _count(PartnerRequest)),
        ("Career Applications", _count(Application)),
        ("Newsletter Signups", _count(NewsletterSubscriber)),
    ]
    try:
        staff = (
            db.query(func.count(User.id))
            .filter(User.created_at >= since, User.is_deleted == False)  # noqa: E712
            .scalar()
            or 0
        )
        rows.append(("New Staff Accounts", staff))
    except Exception:  # noqa: BLE001
        pass
    return rows


_SECTION_BUILDERS = {
    "quatapay": _quatapay_section,
    "quatafood": _quatafood_section,
    "abaqwa": _abaqwa_section,
    "quatatrade": _quatatrade_section,
    "quata_ai": _quata_ai_section,
    "quata_digital": _quata_digital_section,
}


# ---------------------------------------------------------------------------
# Build + send
# ---------------------------------------------------------------------------

def build_digest(db: Session, *, hours: int = 24) -> dict:
    """Assemble the report. Returns both the structured data and the message."""
    since = _now() - timedelta(hours=hours)
    sections: list[tuple[str, list[tuple[str, Any]]]] = []
    structured: dict[str, list] = {}

    for slug, builder in _SECTION_BUILDERS.items():
        if not settings_store.platform_enabled(slug):
            continue
        supplied = _supplied_metrics(db, slug, since) if slug != "quata_digital" else None
        rows = _rows_from_metrics(supplied) if supplied else builder(db, since)
        sections.append((platform_name(slug), rows))
        structured[slug] = [{"label": label, "value": value} for label, value in rows]

    window_end = _now()
    title = (
        f"Last {hours}h · "
        f"{since.strftime('%d %b %H:%M')} → {window_end.strftime('%d %b %H:%M')} UTC"
    )
    message = render_summary(title=title, sections=sections, occurred_at=window_end)
    return {
        "title": title,
        "since": since.isoformat(),
        "until": window_end.isoformat(),
        "sections": structured,
        "message": message,
        "banner": BANNER_SUMMARY,
    }


def send_daily_summary(*, hours: int = 24, force: bool = False) -> dict:
    """Emit the daily summary as a normal event so it inherits queuing,
    retry, recipient filtering and audit logging like everything else."""
    if not force and not settings_store.digest_enabled():
        return {"ok": False, "reason": "digest_disabled"}

    db = SessionLocal()
    try:
        digest = build_digest(db, hours=hours)
    finally:
        db.close()

    # One digest per platform-day: the dedupe key makes a double-fire from
    # two workers a no-op rather than two identical reports.
    day = _now().strftime("%Y-%m-%d")
    event_id = emit(
        "summary.daily",
        platform="quata_digital",
        payload={"report": digest["message"]},
        reference=f"DIGEST-{day}",
        dedupe_key=f"digest:{day}" if not force else None,
    )
    if not event_id:
        return {"ok": False, "reason": "emit_failed"}

    # The digest is its own fully-formed message — replace the rendered
    # envelope with it so administrators get the report, not a wrapper
    # around a giant "Report:" field.
    db = SessionLocal()
    try:
        row = (
            db.query(NotificationEvent)
            .filter(NotificationEvent.event_id == event_id)
            .first()
        )
        if row is not None and row.status == "pending":
            row.message = digest["message"]
            row.payload = {"sections": digest["sections"]}
            db.commit()
    finally:
        db.close()

    from .dispatch import deliver_event

    outcome = deliver_event(event_id)
    outcome["event_id"] = event_id
    return outcome


def should_send_now(db: Session) -> bool:
    """True when the configured digest hour has arrived and today's report
    hasn't gone out yet. Called by the worker on every sweep."""
    if not settings_store.digest_enabled():
        return False
    now = _now()
    if now.hour < settings_store.digest_hour_utc():
        return False
    day = now.strftime("%Y-%m-%d")
    already = (
        db.query(NotificationEvent.id)
        .filter(NotificationEvent.dedupe_key == f"digest:{day}")
        .first()
    )
    return already is None
