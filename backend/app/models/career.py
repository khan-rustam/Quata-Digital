from datetime import date, datetime
from typing import Optional

from sqlalchemy import String, Boolean, JSON, Text, ForeignKey, DateTime, Date
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, SoftDeleteMixin


class Job(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(180), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(180))
    department: Mapped[str] = mapped_column(String(64), index=True)
    location: Mapped[str] = mapped_column(String(120))
    employment_type: Mapped[str] = mapped_column(String(40))  # Full-time|Part-time|Contract|Intern
    summary: Mapped[str] = mapped_column(String(500))
    description: Mapped[str] = mapped_column(Text)
    responsibilities: Mapped[list] = mapped_column(JSON, default=list)
    requirements: Mapped[list] = mapped_column(JSON, default=list)
    is_published: Mapped[bool] = mapped_column(Boolean, default=True)


class Application(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"))
    full_name: Mapped[str] = mapped_column(String(160))
    email: Mapped[str] = mapped_column(String(255))
    phone: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    resume_url: Mapped[str] = mapped_column(String(500))
    cover_letter: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(24), default="new")  # new|shortlisted|interviewed|rejected|hired

    # Hiring-workflow scheduling, set when the admin advances the candidate and
    # the automated shortlist/hire emails go out. Shown on the admin dashboard.
    interview_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    interview_location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    job = relationship("Job")
