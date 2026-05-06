from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin


class SiteSetting(Base, TimestampMixin):
    """Runtime-editable site configuration.

    The admin can edit these from the cockpit without a redeploy. Backend
    services (captcha, Sentry, email) prefer this table over env vars when
    populated; env stays as a deploy-time fallback.

    Keys are dotted: e.g. `integrations.hcaptcha_site_key`,
    `contact.phone`, `social.linkedin_url`, `toggles.maintenance_mode`.
    """

    __tablename__ = "site_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    group: Mapped[str] = mapped_column(String(40), index=True)
    label: Mapped[str] = mapped_column(String(160))
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    # text | email | url | phone | password | toggle | number | textarea
    field_type: Mapped[str] = mapped_column(String(20), default="text")
    is_secret: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    updated_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )

    updated_by = relationship("User", foreign_keys=[updated_by_id])
