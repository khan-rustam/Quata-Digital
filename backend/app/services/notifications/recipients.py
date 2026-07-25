"""Who is allowed to receive a QUATA alert.

Delivery is a strict allow-list: a Telegram chat gets nothing unless it has
an active row in ``notification_recipients``. There is no "broadcast to
whoever messaged the bot" path, which is what satisfies *restrict
notifications to authorized Telegram administrators only*.

Each recipient can additionally narrow what they see:

* ``min_priority`` — a floor, so the CTO's chat can carry only 🔴 CRITICAL.
* ``platforms``    — empty list means every platform.
* ``categories``   — empty list means every category.
"""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.core.config import settings as env_settings
from app.models import NotificationRecipient

from .catalog import priority_rank


log = logging.getLogger("quata.notifications")


def seed_bootstrap_recipients(db: Session) -> int:
    """Create recipients from the bootstrap env vars on first boot.

    Reads both ``TELEGRAM_DEFAULT_CHAT_IDS`` (where alerts go — typically an
    ops group) and ``TELEGRAM_ADMIN_USER_IDS`` (individual administrators'
    private chats). They seed the same allow-list; the split exists so the
    two can be provisioned and revoked independently.

    Only ever *adds* — an id already present is left exactly as the admin
    configured it, so redeploying with the env vars still set can't silently
    re-enable a chat that was deliberately switched off.
    """
    sources = (
        (env_settings.TELEGRAM_DEFAULT_CHAT_IDS, "Bootstrap chat"),
        (env_settings.TELEGRAM_ADMIN_USER_IDS, "Bootstrap admin"),
    )
    created = 0
    for raw, label_prefix in sources:
        for chunk in (raw or "").split(","):
            chat_id = chunk.strip()
            if not chat_id:
                continue
            exists = (
                db.query(NotificationRecipient)
                .filter(NotificationRecipient.chat_id == chat_id)
                .first()
            )
            if exists:
                continue
            db.add(
                NotificationRecipient(
                    chat_id=chat_id,
                    label=f"{label_prefix} {chat_id}",
                    is_active=True,
                    # Negative ids are Telegram groups/supergroups/channels.
                    is_group=chat_id.startswith("-"),
                    min_priority="info",
                    platforms=[],
                    categories=[],
                )
            )
            # Flush per row so a duplicate id appearing in *both* env vars
            # is caught by the next existence check rather than blowing up
            # the whole commit on a unique-constraint violation.
            db.flush()
            created += 1
    if created:
        db.commit()
        log.info("notifications.recipients_seeded", extra={"count": created})
    return created


def _matches(values: Optional[list], candidate: str) -> bool:
    """An empty/absent filter list means "everything"."""
    if not values:
        return True
    return candidate in values


def recipients_for(
    db: Session, *, platform: str, category: str, priority: str
) -> list[NotificationRecipient]:
    """Active recipients whose filters admit this event."""
    rows = (
        db.query(NotificationRecipient)
        .filter(NotificationRecipient.is_active == True)  # noqa: E712
        .order_by(NotificationRecipient.id)
        .all()
    )
    rank = priority_rank(priority)
    return [
        r
        for r in rows
        if rank >= priority_rank(r.min_priority or "info")
        and _matches(r.platforms, platform)
        and _matches(r.categories, category)
    ]
