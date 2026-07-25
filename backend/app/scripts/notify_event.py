"""Publish a QUATA notification from a shell script.

The bridge between ops automation (cron, backup scripts, deploy hooks) and
@QuataAlertsBot. Anything that can run a command can now raise an alert,
without holding a bot token or an ingest key — it reuses the app's own
environment and publishes in-process.

    python -m app.scripts.notify_event infra.database_backup_completed \
        --payload '{"size": "412 MB", "detail": "pg_dump nightly"}' \
        --reference DB-BACKUP

    python -m app.scripts.notify_event infra.database_backup_failed \
        --payload '{"error": "pg_dump exit 1"}' --priority critical

Exit codes: 0 published (or deliberately suppressed by settings), 1 refused.
The command is safe to put in a `trap` — it never fails the caller's script
on its own account.

    --payload      JSON object of fields to render
    --reference    business reference shown as `Reference:`
    --platform     defaults to quata_digital
    --priority     info | warning | important | critical
    --status       overrides the rendered Status line
    --dedupe-key   idempotency key; repeats are recorded, not re-sent
    --wait         deliver synchronously and report the outcome
    --quiet        suppress stdout on success
"""
from __future__ import annotations

import argparse
import json
import sys


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Publish an event to the QUATA Notification Service",
    )
    parser.add_argument("event", help="catalogue key, e.g. infra.database_backup_completed")
    parser.add_argument("--payload", default="{}", help="JSON object of fields")
    parser.add_argument("--reference", default=None)
    parser.add_argument("--platform", default=None)
    parser.add_argument("--priority", default=None,
                        choices=["info", "warning", "important", "critical"])
    parser.add_argument("--status", default=None)
    parser.add_argument("--dedupe-key", dest="dedupe_key", default=None)
    parser.add_argument("--wait", action="store_true",
                        help="deliver synchronously and report the outcome")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    try:
        payload = json.loads(args.payload)
        if not isinstance(payload, dict):
            raise ValueError("payload must be a JSON object")
    except (json.JSONDecodeError, ValueError) as exc:
        print(f"Invalid --payload: {exc}", file=sys.stderr)
        return 1

    from app.core.logging_config import configure_logging
    from app.services.notifications import dispatch
    from app.services.notifications.catalog import DEFAULT_PLATFORM

    configure_logging()

    event_id = dispatch.emit(
        args.event,
        platform=args.platform or DEFAULT_PLATFORM,
        payload=payload,
        reference=args.reference,
        priority=args.priority,
        status=args.status,
        dedupe_key=args.dedupe_key,
        # With --wait we deliver below and want the outcome; otherwise the
        # in-process dispatcher takes it and this command exits immediately.
        dispatch=not args.wait,
    )
    if not event_id:
        print("Could not record the event (see the app log).", file=sys.stderr)
        return 1

    if args.wait:
        result = dispatch.deliver_event(event_id)
        if not args.quiet:
            print(json.dumps({"event_id": event_id, **result}))
        # A suppressed or undeliverable alert is not a failure of the
        # *calling* script — a backup that succeeded still succeeded.
        return 0

    if not args.quiet:
        print(event_id)
    return 0


if __name__ == "__main__":
    sys.exit(main())
