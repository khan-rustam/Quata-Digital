"""Storage for the QUATA Notification Service (@QuataAlertsBot).

Three tables, one job each:

* ``notification_events``     — the outbox + audit log. Every event that any
  QUATA platform publishes lands here first, is rendered + redacted, then
  delivered asynchronously. Delivery outcome is recorded per recipient so
  "what did the bot actually send?" is answerable months later.
* ``notification_recipients`` — the authorised Telegram chats. Nothing is
  ever sent to a chat that isn't an active row here.
* ``notification_settings``   — runtime toggles (per-platform, per-category,
  large-transaction threshold, …). Same key/value shape as ``site_settings``
  so the admin form renders both with one component.
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin


class NotificationEvent(Base, TimestampMixin):
    """One published event and its Telegram delivery record.

    Rows are never mutated in place by a publisher — only the dispatcher
    advances ``status``/``attempts``. That keeps the table usable as both a
    retry queue and a tamper-evident audit trail.
    """

    __tablename__ = "notification_events"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Public identifier handed back to the publishing platform so it can
    # correlate its own logs with ours without exposing our row ids.
    event_id: Mapped[str] = mapped_column(String(40), unique=True, index=True)

    platform: Mapped[str] = mapped_column(String(40), index=True)
    # Dotted key from the catalogue, e.g. "quatapay.deposit.successful".
    event_key: Mapped[str] = mapped_column(String(100), index=True)
    category: Mapped[str] = mapped_column(String(40), index=True)
    # info | warning | important | critical
    priority: Mapped[str] = mapped_column(String(20), index=True, default="info")
    # pending | sent | failed | suppressed
    status: Mapped[str] = mapped_column(String(20), index=True, default="pending")

    title: Mapped[str] = mapped_column(String(200))
    # Redacted payload — secrets are stripped before this is written.
    payload: Mapped[Optional[dict]] = mapped_column(JSON, default=dict, nullable=True)
    # Fully rendered Telegram message, stored so a retry re-sends exactly
    # what was approved rather than re-rendering against changed settings.
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Idempotency key. A second publish with the same key is rejected as a
    # duplicate instead of double-alerting the administrators.
    dedupe_key: Mapped[Optional[str]] = mapped_column(
        String(200), unique=True, index=True, nullable=True
    )
    # Business reference shown in the message (order no, tx id, user id…).
    reference: Mapped[Optional[str]] = mapped_column(String(160), nullable=True, index=True)

    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    last_error: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    # When the retry sweeper should next pick this row up. NULL once the
    # event reaches a terminal state.
    next_attempt_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # [{"chat_id": "...", "ok": true, "message_id": 42, "error": null}, …]
    delivery: Mapped[Optional[list]] = mapped_column(JSON, default=list, nullable=True)
    # Why a `suppressed` row was never sent (platform disabled, priority
    # below threshold, no recipients, …). Kept so "why didn't I get an
    # alert?" is self-service.
    suppressed_reason: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    # Ingest provenance for events posted over HTTP by another platform.
    source_ip: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)


class NotificationRecipient(Base, TimestampMixin):
    """A Telegram chat authorised to receive QUATA alerts.

    ``chat_id`` is a Telegram user id (positive) or group/channel id
    (negative). Delivery is *only* ever attempted against active rows here,
    which is what enforces "restrict notifications to authorised Telegram
    administrators only".
    """

    __tablename__ = "notification_recipients"

    id: Mapped[int] = mapped_column(primary_key=True)
    chat_id: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    label: Mapped[str] = mapped_column(String(120))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    is_group: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Floor for this chat — an "info" recipient gets everything, a
    # "critical" recipient only gets 🔴 events. Lets us page the CTO on
    # incidents without drowning them in signups.
    min_priority: Mapped[str] = mapped_column(String(20), default="info", nullable=False)
    # NULL/empty list = every platform / every category.
    platforms: Mapped[Optional[list]] = mapped_column(JSON, default=list, nullable=True)
    categories: Mapped[Optional[list]] = mapped_column(JSON, default=list, nullable=True)

    last_ok_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_by = relationship("User", foreign_keys=[created_by_id])


class NotificationSetting(Base, TimestampMixin):
    """Runtime-editable switch for the notification service.

    Deliberately a separate table from ``site_settings``: the catalogue here
    is generated from the event catalogue (one row per platform + per
    category) and would otherwise swamp the site-settings admin form.
    """

    __tablename__ = "notification_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # delivery | platforms | categories | thresholds
    group: Mapped[str] = mapped_column(String(40), index=True)
    label: Mapped[str] = mapped_column(String(160))
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    # toggle | number | text | password
    field_type: Mapped[str] = mapped_column(String(20), default="toggle")
    is_secret: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    updated_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    updated_by = relationship("User", foreign_keys=[updated_by_id])
