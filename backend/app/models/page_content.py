from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin


class PageContent(Base, TimestampMixin):
    """Section-based content for marketing pages.

    Distinct from the legacy `Page` model (`cms_pages` table) which only
    holds a single body of text — that one stays around to keep existing
    admin URLs working until the Page model is fully migrated to this
    section-based store.

    Each row corresponds to one URL on the public site (Home, About,
    Privacy, /ecosystem/{slug}, /partners/{type}, …). `sections` is an
    ordered list of typed dicts; the public renderer dispatches on
    `sections[i]["type"]` to the matching section component.

    `page_type` constrains which section types are allowed on a page (a
    product page must follow a specific shape; a general page is open).
    """

    __tablename__ = "page_contents"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(200))
    # general | product | partner_type | (legal — same constraint as general)
    page_type: Mapped[str] = mapped_column(String(40), default="general", index=True)
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Ordered list of typed section dicts. Schema validated on write via
    # `SectionUnion` in app/schemas/page_sections.py.
    sections: Mapped[list] = mapped_column(JSON, default=list)

    is_published: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    updated_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    updated_by = relationship("User", foreign_keys=[updated_by_id])
