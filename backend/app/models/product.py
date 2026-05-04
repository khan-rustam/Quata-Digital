from typing import Optional

from sqlalchemy import String, Boolean, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, SoftDeleteMixin


class Product(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    tagline: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(24), default="coming_soon")  # live|beta|coming_soon
    accent: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    is_published: Mapped[bool] = mapped_column(Boolean, default=True)
    highlights: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    features: Mapped[Optional[list]] = mapped_column(JSON, default=list)
