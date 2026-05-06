from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, SoftDeleteMixin


class MediaAsset(Base, TimestampMixin, SoftDeleteMixin):
    """An uploaded file tracked in the media library.

    Every upload that goes through `/api/v1/uploads` (the authenticated
    endpoint used by admin) automatically creates a row here so the boss
    can browse, search, and reuse images across pages without re-uploading.

    Filename / URL stay opaque (whatever `services/uploads.save_upload`
    produced). The library indexes them by `tags` (free-form) and
    `alt_text` (the only metadata the boss actually edits).

    Public uploads (`/uploads/public` — used by the careers form for
    resumes) deliberately do NOT create rows here, so resume uploads
    don't leak into the admin media browser.
    """

    __tablename__ = "media_assets"

    id: Mapped[int] = mapped_column(primary_key=True)
    url: Mapped[str] = mapped_column(String(500), unique=True, index=True)
    filename: Mapped[str] = mapped_column(String(255))
    original_filename: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    content_type: Mapped[str] = mapped_column(String(80))
    size: Mapped[int] = mapped_column(Integer, default=0)
    folder: Mapped[str] = mapped_column(String(80), default="general", index=True)

    # Image-only metadata. Null for non-images.
    width: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    height: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # WebP version auto-generated for JPG/PNG. Frontend prefers this URL
    # when present; falls back to `url` for SVG / GIF / WebP / non-images.
    optimized_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    optimized_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    alt_text: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    tags: Mapped[Optional[list]] = mapped_column(JSON, default=list)

    uploaded_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    uploaded_by = relationship("User", foreign_keys=[uploaded_by_id])

    # Track which page slugs reference this asset, so the admin can warn
    # before a delete that would orphan an image. Updated by the page
    # editor on save (best-effort; not authoritative).
    used_on: Mapped[Optional[list]] = mapped_column(JSON, default=list)
