"""Employee HR records (HRMS Phase 2G): performance reviews, training, assets.

Child records tied to an employee (``users``). Never hard-deleted history where
it matters; simple rows for the append-only lists shown on the staff profile.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import String, Integer, Text, ForeignKey, Date, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin


class PerformanceReview(Base, TimestampMixin):
    __tablename__ = "performance_reviews"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    reviewer_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    period: Mapped[str] = mapped_column(String(40))  # e.g. "2026 H1"
    rating: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 1–5
    strengths: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    improvements: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    goals: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="submitted")  # draft|submitted

    reviewer = relationship("User", foreign_keys=[reviewer_id])
