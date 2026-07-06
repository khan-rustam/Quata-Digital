from datetime import datetime, date
from typing import Any, List, Optional, Dict

from pydantic import BaseModel, Field, EmailStr, field_validator


class PartnerSubmitIn(BaseModel):
    payload: Dict[str, Any]
    captcha_token: Optional[str] = None

    @field_validator("payload")
    @classmethod
    def _cap_payload(cls, v: Any) -> Any:
        """Bound the free-form partner payload so an anonymous submitter can't
        stuff megabytes of junk into the DB."""
        import json as _json

        if not isinstance(v, dict):
            raise ValueError("payload must be an object")
        if len(v) > 40:
            raise ValueError("payload has too many fields")
        if len(_json.dumps(v, default=str)) > 20_000:
            raise ValueError("payload is too large")
        return v


class PartnerOut(BaseModel):
    id: int
    partner_type: str
    status: str
    payload: Dict[str, Any]
    created_at: datetime

    class Config:
        from_attributes = True


class PartnerStatusUpdate(BaseModel):
    status: str = Field(pattern="^(new|in_review|approved|rejected)$")


class ProductOut(BaseModel):
    id: int
    slug: str
    name: str
    tagline: str
    category: str
    status: str
    is_published: bool
    description: str = ""
    accent: Optional[str] = None
    highlights: List[str] = Field(default_factory=list)
    features: List[Dict[str, str]] = Field(default_factory=list)

    class Config:
        from_attributes = True


class BlogPostOut(BaseModel):
    id: int
    slug: str
    title: str
    excerpt: str
    body: str = ""
    category: str
    cover_image_url: Optional[str] = None
    is_published: bool
    published_at: Optional[datetime] = None
    author: str = "QUATA Editorial"

    # No `from_attributes` — `author` collides with the BlogPost.author relationship.
    # All callers serialize via the helper below so this schema is fed dicts only.


def serialize_blog_post(p) -> dict:
    return {
        "id": p.id,
        "slug": p.slug,
        "title": p.title,
        "excerpt": p.excerpt,
        "body": p.body,
        "category": p.category,
        "cover_image_url": p.cover_image_url,
        "is_published": p.is_published,
        "published_at": p.published_at,
        "author": p.author.full_name if getattr(p, "author", None) else "QUATA Editorial",
    }


class PageOut(BaseModel):
    id: int
    slug: str
    title: str
    is_published: bool
    updated_at: datetime

    class Config:
        from_attributes = True


class JobOut(BaseModel):
    id: int
    slug: str
    title: str
    department: str
    location: str
    employment_type: str
    summary: str
    description: str = ""
    is_published: bool
    responsibilities: List[str] = Field(default_factory=list)
    requirements: List[str] = Field(default_factory=list)
    applications_count: int = 0

    class Config:
        from_attributes = True


class JobApplicationIn(BaseModel):
    full_name: str = Field(min_length=1, max_length=160)
    email: EmailStr
    phone: Optional[str] = Field(default=None, max_length=40)
    resume_url: str = Field(min_length=1, max_length=500)
    cover_letter: Optional[str] = Field(default=None, max_length=8000)
    captcha_token: Optional[str] = None


class ApplicationOut(BaseModel):
    id: int
    full_name: str
    email: EmailStr
    job_title: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class StaffOut(BaseModel):
    id: int
    full_name: str
    email: EmailStr
    role: str
    department: Optional[str] = None
    job_title: Optional[str] = None
    status: str

    class Config:
        from_attributes = True


class DepartmentOut(BaseModel):
    id: int
    slug: str
    name: str
    head_name: Optional[str] = None
    staff_count: int = 0

    class Config:
        from_attributes = True


class RoleOut(BaseModel):
    id: int
    slug: str
    name: str
    description: Optional[str] = None
    permissions: List[str] = Field(default_factory=list)

    class Config:
        from_attributes = True


class MessageIn(BaseModel):
    subject: str
    body: str
    audience: str = Field(pattern="^(all|department|individual)$")
    message_type: str = Field(default="general", pattern="^(general|announcement|urgent)$")
    department_slug: Optional[str] = None
    recipient_id: Optional[int] = None


class MessageOut(BaseModel):
    id: int
    subject: str
    body: str
    audience: str
    message_type: str
    department: Optional[str] = None
    recipient: Optional[str] = None
    read_count: int = 0
    total_recipients: int = 0
    created_at: datetime
    author: str

    class Config:
        from_attributes = True


class LeaveIn(BaseModel):
    leave_type: str = Field(pattern="^(annual|sick|parental|unpaid|other)$")
    start_date: date
    end_date: date
    reason: Optional[str] = None


class LeaveOut(BaseModel):
    id: int
    staff_name: str
    leave_type: str
    start_date: date
    end_date: date
    days: int
    status: str
    reason: Optional[str] = None

    class Config:
        from_attributes = True


class LeaveStatusIn(BaseModel):
    status: str = Field(pattern="^(approved|rejected)$")


class AttendanceIn(BaseModel):
    source: str = Field(default="web", pattern="^(manual|biometric|gps|web)$")
    device_id: Optional[int] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class AttendanceOut(BaseModel):
    id: int
    staff_name: str
    check_in_at: Optional[datetime] = None
    check_out_at: Optional[datetime] = None
    source: str
    device_name: Optional[str] = None
    status: str

    class Config:
        from_attributes = True


class DeviceOut(BaseModel):
    id: int
    name: str
    vendor: str
    ip_address: Optional[str] = None
    api_endpoint: Optional[str] = None
    location: str
    status: str
    last_sync_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ActivityOut(BaseModel):
    id: int
    actor_name: str = "System"
    action: str
    resource_type: str
    resource_id: Optional[str] = None
    ip_address: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    class Config:
        from_attributes = True


class ContactIn(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    email: EmailStr
    company: Optional[str] = Field(default=None, max_length=160)
    reason: str = Field(min_length=1, max_length=80)
    message: str = Field(min_length=1, max_length=8000)
    captcha_token: Optional[str] = None


class OverviewOut(BaseModel):
    totals: Dict[str, int]
    recent_partners: List[PartnerOut]
    recent_applications: List[Dict[str, Any]]
    attendance_today: Dict[str, int]


class AnalyticsOut(BaseModel):
    visits_7d: int
    unique_visitors_7d: int
    form_submissions_7d: int
    partner_requests_7d: int
    job_applications_7d: int
    contact_messages_7d: int
    top_pages: List[Dict[str, Any]]
    partner_funnel: List[Dict[str, Any]]
