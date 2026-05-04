from sqlalchemy import String, JSON
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, SoftDeleteMixin


class PartnerRequest(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "partner_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    partner_type: Mapped[str] = mapped_column(String(32), index=True)  # business|strategic|investor|service
    status: Mapped[str] = mapped_column(String(24), default="new")  # new|in_review|approved|rejected
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    notes: Mapped[str] = mapped_column(String(1000), default="")
