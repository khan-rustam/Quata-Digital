"""QCP background worker — the outbound queue's safety net.

Everything the WhatsApp send path needs that isn't tied to a request:

* **retry sweep**   — deliver messages queued while Meta was unreachable;
* **stuck reclaim** — un-wedge messages left in ``sending`` by a killed worker.

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
