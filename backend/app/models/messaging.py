from datetime import datetime
from typing import Optional

from sqlalchemy import String, Boolean, Text, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin


class Message(Base, TimestampMixin):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    subject: Mapped[str] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text)
    audience: Mapped[str] = mapped_column(String(20))  # all|department|individual
    department_slug: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    recipient_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    message_type: Mapped[str] = mapped_column(String(20), default="general")  # general|announcement|urgent
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    attachment_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    sender = relationship("User", foreign_keys=[sender_id])
    recipient = relationship("User", foreign_keys=[recipient_id])

    recipients_status = relationship(
        "MessageRecipient", back_populates="message", cascade="all, delete-orphan"
    )


class MessageRecipient(Base):
    __tablename__ = "message_recipients"

    id: Mapped[int] = mapped_column(primary_key=True)
    message_id: Mapped[int] = mapped_column(ForeignKey("messages.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    message = relationship("Message", back_populates="recipients_status")
    user = relationship("User")
