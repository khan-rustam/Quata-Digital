from datetime import date, datetime
from typing import Optional

from sqlalchemy import String, Boolean, JSON, Text, ForeignKey, DateTime, Date, Integer
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

    # HR officer who owns this applicant through the pipeline (nullable).
    assigned_hr_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # AI talent-intelligence results (HRMS 1E). Populated on demand from the CV.
    ai_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    ai_analysis: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    ai_analyzed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    job = relationship("Job")
    assigned_hr = relationship("User", foreign_keys=[assigned_hr_id])
    notes = relationship(
        "ApplicationNote",
        back_populates="application",
        cascade="all, delete-orphan",
        order_by="ApplicationNote.created_at",
    )
    attachments = relationship(
        "ApplicationAttachment",
        back_populates="application",
        cascade="all, delete-orphan",
        order_by="ApplicationAttachment.created_at",
    )


class ApplicationNote(Base, TimestampMixin):
    """Internal HR note / comment on an applicant. Never shown to the candidate."""

    __tablename__ = "application_notes"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), index=True
    )
    author_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    body: Mapped[str] = mapped_column(Text)

    application = relationship("Application", back_populates="notes")
    author = relationship("User", foreign_keys=[author_id])


class ApplicationAttachment(Base, TimestampMixin):
    """A private document attached to an applicant (offer letter, assessment,
    reference check, signed forms). Served only through the authenticated admin
    endpoint — never from the public /uploads mount."""

    __tablename__ = "application_attachments"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), index=True
    )
    uploaded_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    filename: Mapped[str] = mapped_column(String(255))
    url: Mapped[str] = mapped_column(String(500))
    content_type: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    size: Mapped[Optional[int]] = mapped_column(nullable=True)
    label: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    application = relationship("Application", back_populates="attachments")
    uploaded_by = relationship("User", foreign_keys=[uploaded_by_id])
