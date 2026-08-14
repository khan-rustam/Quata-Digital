"""The send loop: paced, stoppable, and refusing nothing to the send path.

    campaign (running)
          │
          ▼
    run_once() ── one batch ──►  dispatch.send()  ──►  routing.resolve_route()
          │                            │
          │                            └── refuses on its own terms; the
          │                                campaign records what it said
          ▼
    whatsapp_campaign_recipients + whatsapp_messages(campaign_id=…)

**Nothing here decides whether a message may be sent.** The runner picks a
phone number and calls ``dispatch.send`` with the campaign's product, intent
and locale — the same call QuataFood makes for an order update. Every rule
about which number, which template and which category then applies exactly
once, in the place that already owns it. A campaign that names an intent
routing to Quata Verify does not get a special error from this module: it
gets ``auth_template_off_verify`` from the choke point, the message row lands
``suppressed``, and the campaign screen shows it. Reimplementing those checks
here would create a second opinion that could drift from the first.

**Pace, because the number is shared.** A campaign sends at most
``messages_per_minute`` messages, enforced as small batches ten seconds
apart, with the next-due time stored on the campaign row rather than held in
a worker's memory — so a restart resumes at the pace it left rather than
bursting the backlog. 50,000 messages as fast as the API allows is how a
number gets throttled, and this number carries the fleet's login codes.

**Stop is checked per message, not per batch.** The campaign's status is
re-read from the database immediately before each individual send, so a stop
pressed in the console takes effect after at most one more message rather
than after the rest of the batch. That is also why the loop commits before
each send: the write transaction is released so a concurrent stop can land.

**Sending twice is impossible.** The idempotency key handed to ``dispatch``
is derived from ``(campaign_uid, phone)``, so a crash mid-batch, a double
click on Start, or two workers racing all converge on one message per person
per campaign — ``dispatch`` returns the original ``message_uid`` marked
duplicate instead of sending again.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional

from sqlalchemy.orm import Session

from app.models import WhatsAppMessage, WhatsAppProduct

from .. import audit, settings_store
from . import consent
from . import service as campaign_service
from .models import (
    MAX_MESSAGES_PER_PERSON_PER_DAY,
    PERSON_CAP_WINDOW_HOURS,
    RECIPIENT_FAILED,
    RECIPIENT_OPTED_OUT,
    RECIPIENT_PENDING,
    RECIPIENT_QUEUED,
    RECIPIENT_SUPPRESSED,
    STATUS_COMPLETED,
    STATUS_RUNNING,
    STATUS_SCHEDULED,
    STATUS_STOPPED,
    WhatsAppCampaign,
    WhatsAppCampaignRecipient,
)


# The pacing quantum. Short enough that a stop is felt almost immediately and
# that a small campaign is not held up by a coarse tick; long enough that the
# runner is not a busy loop.
BATCH_SECONDS = 10


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: Optional[datetime]) -> Optional[datetime]:
    """Read a stored timestamp back as UTC.

    Every QCP column is ``DateTime(timezone=True)`` and every writer here uses
    ``datetime.now(timezone.utc)``. Postgres round-trips the offset; SQLite
    (dev and test) drops it and hands back a naive value, which is not
    comparable with an aware one. The pacing check is a comparison, so the
    assumption is made explicit here rather than left to the dialect — the
    same rule the console's ``parseUtc`` applies at the other end.
    """
    if value is None:
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def batch_size(messages_per_minute: int) -> int:
    """How many messages one ten-second batch may carry. At least one."""
    return max(1, math.ceil(max(1, messages_per_minute) * BATCH_SECONDS / 60))


def _default_send(**kwargs) -> dict:
    """Hand off through the sanctioned send path.

    Imported inside the function, in the same spirit as the package facade:
    a process that only ingests webhooks should never pull the delivery path
    (and its HTTP client) in just because it imported this module.
    """
    from ..dispatch import send as dispatch_send

    return dispatch_send(**kwargs)


def _live_status(db: Session, campaign_id: int) -> Optional[str]:
    """Re-read the campaign's status. The stop check, per message."""
    row = (
        db.query(WhatsAppCampaign.status)
        .filter(WhatsAppCampaign.id == campaign_id)
        .first()
    )
    return row[0] if row else None


def _pending(
    db: Session, campaign: WhatsAppCampaign, limit: int
) -> list[WhatsAppCampaignRecipient]:
    return (
        db.query(WhatsAppCampaignRecipient)
        .filter(WhatsAppCampaignRecipient.campaign_id == campaign.id)
        .filter(WhatsAppCampaignRecipient.status == RECIPIENT_PENDING)
        .order_by(WhatsAppCampaignRecipient.id)
        .limit(limit)
        .all()
    )


def _pending_count(db: Session, campaign: WhatsAppCampaign) -> int:
    return (
        db.query(WhatsAppCampaignRecipient.id)
        .filter(WhatsAppCampaignRecipient.campaign_id == campaign.id)
        .filter(WhatsAppCampaignRecipient.status == RECIPIENT_PENDING)
        .count()
    )


# Message statuses that mean this person has had the message, or is about to.
# ``suppressed`` never left QCP and ``failed`` never arrived, so neither is a
# message anybody received.
_COUNTS_AGAINST_A_PERSON = ("queued", "sending", "sent", "delivered", "read")


def messages_in_window(db: Session, phone_e164: str, *, now: datetime) -> int:
    """How many messages this person has had in the last day, from any sender.

    Deliberately not scoped to campaigns, to this campaign, or to a product:
    the cap counts what arrived on the person's phone. A limit that only
    counted a campaign's own sends would be the same bug one level up — three
    campaigns over overlapping audiences would still be three messages, and
    an order update on top of them a fourth.
    """
    since = now - timedelta(hours=PERSON_CAP_WINDOW_HOURS)
    return (
        db.query(WhatsAppMessage.id)
        .filter(WhatsAppMessage.direction == "outbound")
        .filter(WhatsAppMessage.to_phone_e164 == phone_e164)
        .filter(WhatsAppMessage.created_at >= since)
        .filter(WhatsAppMessage.status.in_(_COUNTS_AGAINST_A_PERSON))
        .count()
    )


def daily_cap_reached(db: Session, phone_e164: str, *, now: datetime) -> bool:
    """Whether this person has already had their day's worth of messages."""
    if not phone_e164:
        return False
    return (
        messages_in_window(db, phone_e164, now=now) >= MAX_MESSAGES_PER_PERSON_PER_DAY
    )


def _halt_route_changed(
    db: Session,
    campaign: WhatsAppCampaign,
    refusal: campaign_service.CampaignRefused,
) -> None:
    """Stop the campaign for good, saying which number it was about to use.

    Not a skip. If routing moved underneath a running campaign then every
    message still to go is equally wrong, so the remaining recipients are
    cancelled rather than left to be retried against the new number. The
    denial is audited under its own action — "QCP halted this" is a different
    fact from "an operator stopped this", and only one of them is an incident.
    """
    audit.record(
        db,
        action="campaign.route_changed",
        resource_type="whatsapp_campaign",
        resource_id=campaign.campaign_uid,
        outcome=audit.OUTCOME_DENIED,
        reason=refusal.reason,
        product_id=campaign.product_id,
        account_id=campaign.account_id,
        details={"detail": refusal.detail},
    )
    campaign_service.stop(db, campaign, reason=f"{refusal.reason}: {refusal.detail}")
    campaign.last_error = refusal.detail[:500]
    db.commit()


def run_once(
    db: Session,
    campaign: WhatsAppCampaign,
    *,
    now: Optional[datetime] = None,
    send: Optional[Callable[..., dict]] = None,
    sweep_consent: bool = True,
) -> dict:
    """Send at most one paced batch for this campaign.

    ``send`` is injected rather than imported at module scope for the same
    reason ``templates.sync_from_meta`` takes its ``fetch``: the transport
    stays a parameter, so this loop is testable without a network and the
    "one module talks to Meta" boundary is never crossed from here.
    """
    now = now or _now()
    send = send or _default_send

    status = _live_status(db, campaign.id)
    if status != STATUS_RUNNING:
        return {"campaign": campaign.campaign_uid, "skipped": status or "missing"}

    # Dormancy, re-checked mid-flight. The env kill switch is exactly the
    # thing an operator reaches for when a campaign is going wrong, and it has
    # to stop this loop and *say so* rather than silently produce a run of
    # suppressed messages.
    if not settings_store.delivery_enabled():
        campaign_service.pause(db, campaign, reason="delivery_disabled")
        db.commit()
        return {"campaign": campaign.campaign_uid, "paused": "delivery_disabled"}

    due_at = _aware(campaign.next_batch_at)
    if due_at is not None and now < due_at:
        return {"campaign": campaign.campaign_uid, "paced": True}

    # Honour every STOP that has arrived since the last batch, before choosing
    # who to send to. See ``consent.sweep``.
    if sweep_consent:
        consent.sweep(db)
        db.commit()

    batch = _pending(db, campaign, batch_size(campaign.messages_per_minute))
    if not batch:
        return _complete(db, campaign)

    product = db.get(WhatsAppProduct, campaign.product_id)
    if product is None or not product.is_enabled:
        campaign_service.pause(db, campaign, reason="product_disabled")
        db.commit()
        return {"campaign": campaign.campaign_uid, "paused": "product_disabled"}

    # Snapshotted before the loop: every ``db.commit()`` below expires the
    # campaign instance, and re-reading five columns per message to build a
    # send call that cannot change mid-batch is noise.
    product_slug = product.slug
    campaign_id = campaign.id
    campaign_uid = campaign.campaign_uid
    intent = campaign.intent
    locale = campaign.locale
    variables = tuple(str(v) for v in (campaign.variables or []))
    counts = {"queued": 0, "suppressed": 0, "failed": 0, "opted_out": 0}
    stopped = False

    for recipient in batch:
        # ← the stop check. Per message, from the database, so an operator's
        # click lands between two sends rather than after the batch.
        if _live_status(db, campaign_id) != STATUS_RUNNING:
            stopped = True
            break

        # ← the route check, and it is per message for the same reason. The
        # campaign row is pinned to the engagement number, but ``dispatch``
        # re-resolves the route for every individual message, so an admin
        # saving the Routing screen mid-campaign moves the *messages* without
        # moving the row. See ``service.assert_route_unchanged``.
        try:
            campaign_service.assert_route_unchanged(db, campaign)
        except campaign_service.CampaignRefused as refusal:
            _halt_route_changed(db, campaign, refusal)
            return {
                "campaign": campaign_uid,
                "status": STATUS_STOPPED,
                "halted": refusal.reason,
                "detail": refusal.detail,
                **counts,
            }

        phone = recipient.phone_e164
        if consent.is_opted_out(db, phone):
            recipient.status = RECIPIENT_OPTED_OUT
            recipient.attempted_at = now
            recipient.last_error = "opted_out"
            counts["opted_out"] += 1
            db.commit()
            continue

        # ← the per-person ceiling, counted across every sender. One message
        # per person per campaign was never a limit on how much one person
        # hears from these two numbers; this is.
        if daily_cap_reached(db, phone, now=now):
            recipient.status = RECIPIENT_SUPPRESSED
            recipient.attempted_at = now
            recipient.last_error = "daily_cap_reached"
            counts["suppressed"] += 1
            db.commit()
            continue

        recipient_id = recipient.id
        # Release the write transaction before ``dispatch`` opens its own
        # session: a stop landing in another connection must not have to wait
        # on this one, and on SQLite it would fail outright.
        db.commit()

        result = send(
            product_slug=product_slug,
            intent=intent,
            to_phone_e164=phone,
            variables=variables,
            kind="template",
            locale=locale,
            reference=campaign_uid,
            # One message per person per campaign, forever.
            idempotency_key=f"campaign:{campaign_uid}:{phone}",
        )

        _apply_result(db, recipient_id, campaign_uid, result, at=now, counts=counts)
        db.commit()

    # Only re-arm a campaign that is still running. A stop landed in another
    # session while this batch was in flight, and writing a next-batch time
    # back onto a stopped row would be this loop overruling the stop button.
    still_running = _live_status(db, campaign_id) == STATUS_RUNNING
    if still_running:
        campaign.next_batch_at = now + timedelta(seconds=BATCH_SECONDS)
        db.flush()

    audit.record(
        db,
        action="campaign.batch",
        resource_type="whatsapp_campaign",
        resource_id=campaign_uid,
        outcome=audit.OUTCOME_OK,
        product_id=campaign.product_id,
        account_id=campaign.account_id,
        details=dict(counts, stopped=stopped),
    )
    db.commit()

    if still_running and _pending_count(db, campaign) == 0:
        return dict(_complete(db, campaign), **counts)

    return {
        "campaign": campaign_uid,
        "status": _live_status(db, campaign_id),
        "stopped_mid_batch": stopped,
        **counts,
    }


def _apply_result(
    db: Session,
    recipient_id: int,
    campaign_uid: str,
    result: dict,
    *,
    at: datetime,
    counts: dict,
) -> None:
    """Record what the send path said. Its verdict is copied, never argued with.

    ``dispatch.send`` never raises and never lies: ``queued`` means the row is
    in the outbox, ``suppressed`` means routing refused it and the reason code
    is the refusal. Both are written to the recipient row as-is, so a campaign
    that put marketing in front of the choke point reports the choke point's
    own words.
    """
    recipient = db.get(WhatsAppCampaignRecipient, recipient_id)
    if recipient is None:  # pragma: no cover — deleted mid-flight
        return

    recipient.attempted_at = at
    message_uid = result.get("message_uid")
    recipient.message_uid = str(message_uid)[:40] if message_uid else None
    status = result.get("status")

    if status == "queued":
        recipient.status = RECIPIENT_QUEUED
        recipient.last_error = None
        counts["queued"] += 1
    elif status == "suppressed":
        recipient.status = RECIPIENT_SUPPRESSED
        recipient.last_error = str(result.get("reason") or "suppressed")[:500]
        counts["suppressed"] += 1
    else:
        recipient.status = RECIPIENT_FAILED
        recipient.last_error = str(result.get("reason") or status or "error")[:500]
        counts["failed"] += 1

    # Stamp the message with the campaign it belongs to. ``campaign_id`` has
    # been a documented seam on ``whatsapp_messages`` since the platform was
    # built and this is its first writer; stamping it here rather than
    # threading a parameter through ``dispatch`` keeps the send path's
    # signature the same for every caller.
    if message_uid:
        db.query(WhatsAppMessage).filter(
            WhatsAppMessage.message_uid == message_uid
        ).update({WhatsAppMessage.campaign_id: campaign_uid[:40]},
                 synchronize_session=False)


def _complete(db: Session, campaign: WhatsAppCampaign) -> dict:
    campaign.status = STATUS_COMPLETED
    campaign.finished_at = campaign.finished_at or _now()
    campaign.next_batch_at = None
    db.flush()
    audit.record(
        db,
        action="campaign.completed",
        resource_type="whatsapp_campaign",
        resource_id=campaign.campaign_uid,
        outcome=audit.OUTCOME_OK,
        product_id=campaign.product_id,
        account_id=campaign.account_id,
        details={"audience_size": campaign.audience_size},
    )
    db.commit()
    return {"campaign": campaign.campaign_uid, "status": STATUS_COMPLETED}


def run_due(
    db: Session,
    *,
    now: Optional[datetime] = None,
    limit: int = 10,
    send: Optional[Callable[..., dict]] = None,
) -> dict:
    """The tick. Promote what is due, then run one batch for each runner.

    Idempotent and safe on any cron interval — the pacing state lives on the
    row, so calling this every second and calling it every minute differ in
    latency, not in how fast anybody is messaged::

        * * * * * curl -fsS -X POST \\
            https://api.quatadigital.com/api/v1/admin/qcp/campaigns/run-due \\
            -H "Authorization: Bearer $ADMIN_TOKEN"

    On a dormant install it promotes nothing and sends nothing: ``start`` and
    every batch both refuse while delivery is off.
    """
    now = now or _now()
    results: list[dict] = []

    if settings_store.delivery_enabled():
        due = (
            db.query(WhatsAppCampaign)
            .filter(WhatsAppCampaign.status == STATUS_SCHEDULED)
            .filter(WhatsAppCampaign.scheduled_at.isnot(None))
            .filter(WhatsAppCampaign.scheduled_at <= now)
            .order_by(WhatsAppCampaign.id)
            .limit(limit)
            .all()
        )
        for campaign in due:
            try:
                # ``start`` re-checks dormancy, the product gate and the route
                # at *this* moment, so a schedule cannot outrun a switch that
                # was turned off after it was set.
                campaign_service.start(db, campaign)
                db.commit()
            except campaign_service.CampaignRefused as exc:
                campaign_service.pause(db, campaign, reason=exc.reason)
                db.commit()
                results.append(
                    {"campaign": campaign.campaign_uid, "not_started": exc.reason}
                )

    running = (
        db.query(WhatsAppCampaign)
        .filter(WhatsAppCampaign.status == STATUS_RUNNING)
        .order_by(WhatsAppCampaign.next_batch_at.is_(None).desc(),
                  WhatsAppCampaign.next_batch_at)
        .limit(limit)
        .all()
    )
    for campaign in running:
        results.append(run_once(db, campaign, now=now, send=send))

    return {"ran": len(running), "campaigns": results}
