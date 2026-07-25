"""QUATA Notification Service background worker.

Everything the notification pipeline needs that isn't tied to a request:

* **retry sweep**   — deliver events queued while Telegram was unreachable;
* **stuck reclaim** — un-wedge events left in `sending` by a killed worker;
* **monitoring**    — sample CPU / RAM / disk / database / queue and raise
                      ❌ SYSTEM ALERT on the way down, ✅ on the way back;
* **daily summary** — send the business report at the configured hour;
* **retention**     — prune delivery records past the retention window.

Run it on the VPS next to the API:

    cd /home/Quata-Digital/backend
    source .venv/bin/activate
    python -m app.scripts.notification_worker

Or under systemd as `quata-notification-worker.service`:

    [Service]
    WorkingDirectory=/home/Quata-Digital/backend
    EnvironmentFile=/home/Quata-Digital/backend/.env
    ExecStart=/home/Quata-Digital/backend/.venv/bin/python -m app.scripts.notification_worker
    Restart=always
    RestartSec=10

This worker is *not* required for alerts to be delivered — the API sends
in-process the moment an event is published. It's the safety net that makes
delivery reliable across restarts and outages, plus the home of everything
scheduled.

    --once            run a single cycle and exit (use with cron)
    --interval N      seconds between cycles (default 60)
"""
from __future__ import annotations

import argparse
import logging
import sys
import time

from app.core.logging_config import configure_logging


log = logging.getLogger("quata.notifications.worker")

# Monitoring and retention don't need to run every minute.
MONITOR_EVERY_CYCLES = 5
PRUNE_EVERY_CYCLES = 60 * 12  # ~ every 12 hours at the default interval


def run_cycle(cycle: int) -> dict:
    """One pass. Each step is isolated — a failure in one doesn't stop the rest."""
    from app.db.session import SessionLocal
    from app.services.notifications import digest, dispatch, monitor

    summary: dict[str, object] = {"cycle": cycle}

    try:
        summary["reclaimed"] = dispatch.reclaim_stuck()
    except Exception as exc:  # noqa: BLE001
        log.warning("worker.reclaim_failed", extra={"error": str(exc)[:200]})

    try:
        summary["sweep"] = dispatch.sweep_pending()
    except Exception as exc:  # noqa: BLE001
        log.warning("worker.sweep_failed", extra={"error": str(exc)[:200]})

    if cycle % MONITOR_EVERY_CYCLES == 0:
        try:
            monitor.run_checks()
            summary["monitored"] = True
        except Exception as exc:  # noqa: BLE001
            log.warning("worker.monitor_failed", extra={"error": str(exc)[:200]})

    try:
        db = SessionLocal()
        try:
            due = digest.should_send_now(db)
        finally:
            db.close()
        if due:
            summary["digest"] = digest.send_daily_summary()
    except Exception as exc:  # noqa: BLE001
        log.warning("worker.digest_failed", extra={"error": str(exc)[:200]})

    if cycle % PRUNE_EVERY_CYCLES == 0:
        try:
            summary["pruned"] = dispatch.prune_log()
        except Exception as exc:  # noqa: BLE001
            log.warning("worker.prune_failed", extra={"error": str(exc)[:200]})

    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="QUATA notification worker")
    parser.add_argument("--once", action="store_true", help="run one cycle and exit")
    parser.add_argument("--interval", type=int, default=60, help="seconds between cycles")
    args = parser.parse_args()

    configure_logging()

    if args.once:
        result = run_cycle(1)
        log.info("worker.cycle", extra={"result": result})
        print(result)
        return 0

    interval = max(args.interval, 5)
    log.info("worker.boot", extra={"interval": interval})
    cycle = 0
    while True:
        cycle += 1
        try:
            run_cycle(cycle)
        except KeyboardInterrupt:
            log.info("worker.stopped")
            return 0
        except Exception as exc:  # noqa: BLE001 — the loop must not die
            log.exception("worker.cycle_failed", extra={"error": str(exc)[:200]})
        try:
            time.sleep(interval)
        except KeyboardInterrupt:
            log.info("worker.stopped")
            return 0


if __name__ == "__main__":
    sys.exit(main())
