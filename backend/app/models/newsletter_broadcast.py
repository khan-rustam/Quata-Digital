from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin


class NewsletterBroadcast(Base, TimestampMixin):
    """Audit row for every newsletter sent from the admin compose-and-send
    UI. We keep one row per broadcast so the team can see what was sent,
    when, by whom, and to how many recipients — useful for compliance and
    sanity-checking deliverability when subscribers report not receiving
    the latest issue."""

    __tablename__ = "newsletter_broadcasts"

    id: Mapped[int] = mapped_column(primary_key=True)
    subject: Mapped[str] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text)  # markdown source

    sender_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    sender = relationship("User", foreign_keys=[sender_id])

    # Snapshot of what happened when the broadcast ran.
    recipients_count: Mapped[int] = mapped_column(Integer, default=0)
    delivered_count: Mapped[int] = mapped_column(Integer, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, default=0)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|sent|failed
    error_summary: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
