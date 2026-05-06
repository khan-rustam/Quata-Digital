from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class PageContentVersion(Base):
    """Snapshot of a `PageContent` row at a point in time.

    Created automatically by the page editor on every PUT — captures the
    state BEFORE the new payload is applied so the boss can revert any
    individual save. Retention is bounded (`MAX_VERSIONS_PER_PAGE` in
    routes_pages.py), so the table stays small.

    Versions store the full sections JSON. When the boss reverts, we copy
    that JSON back into PageContent and snapshot the (now-being-overwritten)
    current state into a new version row — so revert itself is reversible.
    """

    __tablename__ = "page_content_versions"

    id: Mapped[int] = mapped_column(primary_key=True)
    page_slug: Mapped[str] = mapped_column(String(120), index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    sections: Mapped[list] = mapped_column(JSON, default=list)

    saved_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    saved_by = relationship("User", foreign_keys=[saved_by_id])

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
