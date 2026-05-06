"""Top-level email job functions, importable by the RQ worker.

Functions defined here MUST be importable by their dotted path (e.g.
`app.services.email_jobs.send_broadcast_email`) — RQ pickles the import
path, not the function object. Don't define jobs as closures.

Each job opens its own DB session if needed; jobs run in the worker
process, not the request process.
"""
from __future__ import annotations

import logging
from typing import Optional

from app.db.session import SessionLocal
from app.models import NewsletterBroadcast


log = logging.getLogger("quata.email_jobs")


def send_broadcast_email(
    *,
    to: str,
    subject: str,
    body: str,
    broadcast_id: Optional[int] = None,
) -> dict:
    """Send a single email + bump the parent broadcast's counters.

    Idempotency: this is intentionally simple — RQ's at-least-once delivery
    means a job retry could double-count. For the v1 broadcast volume that
    risk is acceptable; if it bites, we can switch to an idempotent
    upsert keyed by (broadcast_id, recipient).
    """
    from app.services.email import send_email

    ok = False
    err: Optional[str] = None
    try:
        ok = send_email(to=to, subject=subject, body=body)
    except Exception as exc:  # noqa: BLE001
        err = f"{type(exc).__name__}: {str(exc)[:200]}"

    if broadcast_id is not None:
        try:
            with SessionLocal() as db:
                bc = db.get(NewsletterBroadcast, broadcast_id)
                if bc is not None:
                    if ok:
                        bc.delivered_count = (bc.delivered_count or 0) + 1
                    else:
                        bc.failed_count = (bc.failed_count or 0) + 1
                        if not bc.error_summary and err:
                            bc.error_summary = err
                    db.commit()
        except Exception as exc:  # noqa: BLE001
            log.warning("broadcast counter update failed: %s", exc)

    return {"to": to, "ok": ok, "error": err}
