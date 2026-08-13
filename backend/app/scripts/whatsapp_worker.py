"""QCP background worker — the outbound queue's safety net.

Everything QCP needs doing that isn't tied to a request:

* **retry sweep**   — deliver messages queued while Meta was unreachable;
* **stuck reclaim** — un-wedge messages left in ``sending`` by a killed worker;
* **escalation chase** — alert on a customer the AI handed to a human and
  nobody picked up;
* **config check** — report an AI switched on that cannot route a reply.

The last two send nothing and run whether or not delivery is enabled. They
are here because this is the process this repo already runs unattended: a
second scheduler would be a second thing to keep alive, and the failure mode
of a background job nobody is running is exactly what they exist to fix.

Run it on the VPS next to the API:

    cd /home/Quata-Digital/backend
    source .venv/bin/activate
    python -m app.scripts.whatsapp_worker

Or under systemd as `quata-whatsapp-worker.service`:

    [Service]
    WorkingDirectory=/home/Quata-Digital/backend
    EnvironmentFile=/home/Quata-Digital/backend/.env
    ExecStart=/home/Quata-Digital/backend/.venv/bin/python -m app.scripts.whatsapp_worker
    Restart=always
    RestartSec=10

This worker is *not* required for a message to be delivered — the API hands
off in-process the moment ``send()`` accepts one. It is what makes delivery
reliable across restarts and outages.

It **is** required for the escalation SLA. Nothing else calls
``handover.flag_unanswered`` unless a human opens the agent console and presses
a button, so with this process stopped a customer the AI promised a person to
waits until somebody happens to look. Treat it not running the same way
``docs/ADMIN_USER_MANUAL.md`` treats a missing daily summary: a signal.

When ``REDIS_URL`` is set, hand-offs go to RQ instead of the in-process pool
and are consumed by the shared RQ worker (``app.scripts.email_worker``); this
process is still worth running, because the sweep and the reclaim are what
recover jobs RQ itself lost.

    --once            run a single cycle and exit (use with cron)
    --interval N      seconds between cycles (default 60)
    --limit N         max messages per sweep (default 100)
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.core.logging_config import configure_logging


log = logging.getLogger("quata.whatsapp.worker")

# Reclaiming is cheap but pointless every minute — a claim has to be stale
# before it is safe to steal.
RECLAIM_EVERY_CYCLES = 5

# Template reconciliation. ``templates.scheduled_sync`` is interval-gated on
# its own (default an hour) and reads the last ``template.sync`` audit row to
# decide, so this cycle count is only how often the *question* is asked. It is
# a belt to the cron entry in ``infra/cron/qcp-template-sync.cron``: either
# alone is enough, and running both costs one extra audit read per hour.
SYNC_TEMPLATES_EVERY_CYCLES = 60

# How often the AI's own configuration is questioned. Cheap (one rule lookup
# per enabled product per language) but pointless every minute, and the answer
# only changes when a human edits a rule or flips a switch.
CHECK_AI_CONFIG_EVERY_CYCLES = 5

# ``ai.misconfigured`` is a standing condition, not an event: it lasts until
# somebody creates the rule. One row an hour is a signal; one a minute is a
# log nobody reads, which is the same silence the row exists to break.
AI_MISCONFIG_REPORT_INTERVAL_SECONDS = 3600
ACTION_AI_MISCONFIGURED = "ai.misconfigured"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def chase_unanswered_escalations() -> int:
    """Alert on every escalation nobody picked up in time. Returns how many.

    This is the whole reason the AI support layer is allowed to exist: it
    refuses to talk about somebody's money or identity and fetches a human
    instead. If nobody comes, the customer has been *told* a person would
    help and then ignored, which is a worse outcome than never having
    answered at all.

    ``handover.flag_unanswered`` already did the work and already reports
    each escalation exactly once, no matter how often it is called. The only
    thing missing was something calling it that is not a person clicking a
    button on a screen they had to think to open — at 21:00 nobody opens it.
    That is this function.

    It **sends nothing**: one audit row per ignored customer and a mark on
    the thread so the next cycle stays quiet. So it is deliberately not
    behind ``delivery_enabled`` — a paused fleet is when escalations rot, not
    when they don't — and it is safe to schedule on today's dormant install,
    where there are no escalations and it writes nothing at all.
    """
    from app.db.session import SessionLocal  # noqa: PLC0415
    from app.services.whatsapp import handover  # noqa: PLC0415

    with SessionLocal() as db:
        reported = handover.flag_unanswered(db)
        count = len(reported)
        # ``flag_unanswered`` flushes; the commit is the caller's, and this
        # is the caller. Without it the alert dies with the session.
        db.commit()
    return count


def report_ai_misconfiguration(
    *,
    interval_seconds: int = AI_MISCONFIG_REPORT_INTERVAL_SECONDS,
    now: Optional[datetime] = None,
) -> Optional[str]:
    """Say out loud that the AI is switched on and cannot answer anybody.

    An operator turns the AI on, watches it do nothing, and concludes the
    feature is broken. It is not broken — an AI reply is a send, a send needs
    a routing rule, and without one every reply is refused as ``no_route``
    somewhere the operator will never look. The same happens to francophone
    customers alone when the rule exists for ``en`` only.

    So the condition is written where an operator already reads: the QCP
    audit log, as a denial carrying the blocker code and the exact products
    and languages missing a rule. Interval-gated off the last row of its own
    action — the same self-scheduling shape ``templates.scheduled_sync``
    uses — so calling this every cycle and calling it hourly do the same
    thing.

    Returns the blocker code when it reported, else ``None``. Writes nothing
    while the AI is off: dormant is the fleet's intended state, not a fault.
    """
    from app.db.session import SessionLocal  # noqa: PLC0415
    from app.models import WhatsAppAuditLog  # noqa: PLC0415
    from app.services.whatsapp import audit, settings_store  # noqa: PLC0415

    moment = now or _now()
    with SessionLocal() as db:
        state = settings_store.ai_reply_readiness(db)
        if not state["misconfigured"]:
            return None

        last = (
            db.query(WhatsAppAuditLog.created_at)
            .filter(WhatsAppAuditLog.action == ACTION_AI_MISCONFIGURED)
            .order_by(WhatsAppAuditLog.id.desc())
            .first()
        )
        if last is not None and last[0] is not None:
            stamp = last[0]
            if stamp.tzinfo is None:
                stamp = stamp.replace(tzinfo=timezone.utc)
            if stamp > moment - timedelta(seconds=max(int(interval_seconds), 0)):
                return None

        audit.record(
            db,
            action=ACTION_AI_MISCONFIGURED,
            resource_type="whatsapp_routing_rule",
            resource_id=state["intent"],
            outcome=audit.OUTCOME_DENIED,
            reason=state["blocker"],
            details={
                "intent": state["intent"],
                "locales": state["locales"],
                "gaps": state["gaps"],
                "routed_products": state["routed_products"],
            },
        )
        db.commit()
        return state["blocker"]


def run_cycle(cycle: int, *, limit: int) -> dict:
    """One pass. Each step is isolated — a failure in one doesn't stop the rest."""
    from app.services.whatsapp import dispatch
    from app.services.whatsapp import settings_store

    summary: dict[str, object] = {"cycle": cycle}

    if cycle % RECLAIM_EVERY_CYCLES == 0:
        try:
            summary["reclaimed"] = dispatch.reclaim_stuck()
        except Exception as exc:  # noqa: BLE001
            log.warning("whatsapp.worker.reclaim_failed", extra={"error": str(exc)[:200]})

    # BEFORE the delivery gate, deliberately. Meta re-classifying a template
    # from AUTHENTICATION to MARKETING underneath us is exactly the event that
    # strands QuataFood's login OTP, and it matters *most* while sending is
    # paused — that is when nobody is watching a failure rate. The sync itself
    # enables nothing: it needs a live account with a stored token (a dormant
    # install therefore dials Meta zero times) and the only status it writes
    # is the ``disabled`` of a quarantine.
    if cycle % SYNC_TEMPLATES_EVERY_CYCLES == 0:
        try:
            from app.services.whatsapp import templates as wa_templates

            summary["template_sync"] = wa_templates.scheduled_sync(
                fetch=dispatch.fetch_message_templates
            )["due"]
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "whatsapp.worker.template_sync_failed", extra={"error": str(exc)[:200]}
            )

    # Every cycle, and before the delivery gate. A customer who was promised a
    # human is waiting whether or not the fleet is sending, and the SLA
    # (``handover.UNANSWERED_AFTER``, 15 minutes) is short enough that an
    # hourly check would be most of the wait. Cheap by construction: the scan
    # only ever sees open, unclaimed escalations.
    try:
        summary["unanswered"] = chase_unanswered_escalations()
    except Exception as exc:  # noqa: BLE001
        log.warning("whatsapp.worker.unanswered_failed", extra={"error": str(exc)[:200]})

    # Also before the gate: "switched on and unable to route a reply" is a
    # configuration fault, not a delivery one, and an operator who pauses
    # delivery while they set the AI up is precisely the person who needs to
    # be told the rule is missing.
    if cycle % CHECK_AI_CONFIG_EVERY_CYCLES == 0 or cycle == 1:
        try:
            blocker = report_ai_misconfiguration()
            if blocker:
                summary["ai_misconfigured"] = blocker
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "whatsapp.worker.ai_config_check_failed", extra={"error": str(exc)[:200]}
            )

    # The env kill switch is honoured here too: with WHATSAPP_ENABLED=false
    # the sweeper does not even look at the outbox, so an operator can stop
    # delivery without touching the database or the code.
    if not settings_store.delivery_enabled():
        summary["skipped"] = "delivery_disabled"
        return summary

    try:
        summary["swept"] = dispatch.sweep_pending(limit=limit)
    except Exception as exc:  # noqa: BLE001
        log.warning("whatsapp.worker.sweep_failed", extra={"error": str(exc)[:200]})
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="QCP WhatsApp delivery worker")
    parser.add_argument("--once", action="store_true", help="run a single cycle and exit")
    parser.add_argument("--interval", type=int, default=60, help="seconds between cycles")
    parser.add_argument("--limit", type=int, default=100, help="max messages per sweep")
    args = parser.parse_args(argv)

    configure_logging()
    log.info("whatsapp.worker.start", extra={"interval": args.interval, "once": args.once})

    cycle = 0
    while True:
        cycle += 1
        summary = run_cycle(cycle, limit=args.limit)
        log.info("whatsapp.worker.cycle", extra=summary)
        if args.once:
            return 0
        try:
            time.sleep(max(args.interval, 5))
        except KeyboardInterrupt:
            log.info("whatsapp.worker.stop")
            return 0


if __name__ == "__main__":
    sys.exit(main())
