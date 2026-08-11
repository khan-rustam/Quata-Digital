"""QCP audit trail — ``whatsapp_audit_log``.

Every routing decision that is *refused* writes a row here, with no human
actor attached. That is the point of the table: a blocked
marketing-on-Verify attempt has no logged-in user, so ``activity_logs``
(admin-actor scoped) cannot record it.

``record`` writes on the caller's session and flushes — it never commits.
The caller owns the transaction, so a denial row lands in the same commit
as the ``suppressed`` message row that explains it.
"""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.models import WhatsAppAuditLog

from .redaction import redact_details


log = logging.getLogger("quata.whatsapp")

OUTCOME_OK = "ok"
OUTCOME_DENIED = "denied"
OUTCOME_ERROR = "error"


def record(
    db: Session,
    *,
    action: str,
    resource_type: str,
    outcome: str = OUTCOME_OK,
    reason: Optional[str] = None,
    actor_id: Optional[int] = None,
    product_id: Optional[int] = None,
    account_id: Optional[int] = None,
    resource_id: Optional[str] = None,
    details: Optional[dict] = None,
    ip_address: Optional[str] = None,
) -> WhatsAppAuditLog:
    """Append one audit row. Details are redacted before they are stored."""
    row = WhatsAppAuditLog(
        actor_id=actor_id,
        product_id=product_id,
        account_id=account_id,
        action=action[:80],
        resource_type=resource_type[:60],
        resource_id=str(resource_id)[:80] if resource_id is not None else None,
        outcome=outcome if outcome in (OUTCOME_OK, OUTCOME_DENIED, OUTCOME_ERROR) else OUTCOME_ERROR,
        reason=str(reason)[:500] if reason else None,
        details=redact_details(details),
        ip_address=ip_address,
    )
    db.add(row)
    db.flush()
    if outcome != OUTCOME_OK:
        log.warning(
            "whatsapp.%s", action, extra={"outcome": outcome, "reason": reason, "product_id": product_id}
        )
    return row
