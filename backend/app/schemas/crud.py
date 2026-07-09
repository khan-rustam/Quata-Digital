"""Pydantic IO schemas for admin CRUD."""
from datetime import date, datetime
from typing import List, Optional, Dict

from pydantic import BaseModel, EmailStr, Field


# ---------- Products ----------

class ProductIn(BaseModel):
    slug: str
    name: str
    tagline: str
    description: str = ""
    category: str
    status: str = Field(default="coming_soon", pattern="^(live|beta|coming_soon)$")
    accent: Optional[str] = None
    is_published: bool = True
    highlights: List[str] = Field(default_factory=list)
    features: List[Dict[str, str]] = Field(default_factory=list)


class ProductPatch(BaseModel):
    slug: Optional[str] = None
    name: Optional[str] = None
    tagline: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    status: Optional[str] = Field(default=None, pattern="^(live|beta|coming_soon)$")
    accent: Optional[str] = None
    is_published: Optional[bool] = None
    highlights: Optional[List[str]] = None
    features: Optional[List[Dict[str, str]]] = None


# ---------- Blog ----------

class BlogIn(BaseModel):
    slug: str
    title: str
    excerpt: str
    body: str
    category: str = "Insight"
    cover_image_url: Optional[str] = None
    is_published: bool = False
    published_at: Optional[datetime] = None


class BlogPatch(BaseModel):
    slug: Optional[str] = None
    title: Optional[str] = None
    excerpt: Optional[str] = None
    body: Optional[str] = None
    category: Optional[str] = None
    cover_image_url: Optional[str] = None
    is_published: Optional[bool] = None
    published_at: Optional[datetime] = None


# ---------- Pages ----------

class PageIn(BaseModel):
    slug: str
    title: str
    content: str
    is_published: bool = True


class PagePatch(BaseModel):
    slug: Optional[str] = None
    title: Optional[str] = None
    content: Optional[str] = None
    is_published: Optional[bool] = None


# ---------- Jobs ----------

class JobIn(BaseModel):
    slug: str
    title: str
    department: str
    location: str
    employment_type: str
    summary: str
    description: str
    responsibilities: List[str] = Field(default_factory=list)
    requirements: List[str] = Field(default_factory=list)
    is_published: bool = True


class JobPatch(BaseModel):
    slug: Optional[str] = None
    title: Optional[str] = None
    department: Optional[str] = None
    location: Optional[str] = None
    employment_type: Optional[str] = None
    summary: Optional[str] = None
    description: Optional[str] = None
    responsibilities: Optional[List[str]] = None
    requirements: Optional[List[str]] = None
    is_published: Optional[bool] = None


class ApplicationStatusIn(BaseModel):
    # Full recruitment pipeline (backward-compatible: the original
    # new/shortlisted/interviewed/rejected/hired all remain valid). Automated
    # candidate emails still fire only on shortlisted/hired/rejected.
    status: str = Field(
        pattern=(
            "^(new|hr_review|shortlisted|interview_scheduled|interviewed|"
            "assessment|reference_check|offer|offer_accepted|hired|rejected|"
            "archived)$"
        )
    )
    # Optional hiring-workflow details supplied from the admin dialog. When
    # `notify` is true, moving to shortlisted/hired/rejected triggers the
    # matching automated email to the candidate (copied to careers@).
    interview_at: Optional[datetime] = None
    interview_location: Optional[str] = Field(default=None, max_length=255)
    documents: Optional[str] = Field(default=None, max_length=2000)  # email-only
    start_date: Optional[date] = None
    message: Optional[str] = Field(default=None, max_length=4000)
    notify: bool = True


# ---------- Departments ----------

class DepartmentIn(BaseModel):
    slug: str
    name: str
    description: Optional[str] = None
    head_id: Optional[int] = None


class DepartmentPatch(BaseModel):
    slug: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    head_id: Optional[int] = None


# ---------- Staff ----------

class StaffIn(BaseModel):
    email: EmailStr
    full_name: str
    role_slug: str
    department_slug: Optional[str] = None
    job_title: Optional[str] = None
    phone: Optional[str] = None
    biometric_id: Optional[str] = None
    password: Optional[str] = None  # if absent, a temp one is generated


class StaffPatch(BaseModel):
    full_name: Optional[str] = None
    role_slug: Optional[str] = None
    department_slug: Optional[str] = None
    job_title: Optional[str] = None
    phone: Optional[str] = None
    biometric_id: Optional[str] = None
    status: Optional[str] = Field(default=None, pattern="^(active|invited|suspended)$")


# ---------- Devices ----------

class DeviceIn(BaseModel):
    name: str
    vendor: str = "Generic"
    ip_address: Optional[str] = None
    api_endpoint: Optional[str] = None
    location: str = "HQ"


class DevicePatch(BaseModel):
    name: Optional[str] = None
    vendor: Optional[str] = None
    ip_address: Optional[str] = None
    api_endpoint: Optional[str] = None
    location: Optional[str] = None
    status: Optional[str] = None


class DeviceWithToken(BaseModel):
    id: int
    name: str
    vendor: str
    ip_address: Optional[str] = None
    api_endpoint: Optional[str] = None
    location: str
    status: str
    last_sync_at: Optional[datetime] = None
    api_token: Optional[str] = None  # only returned on create/rotate

    class Config:
        from_attributes = True


# ---------- Listing helpers ----------

class Paginated(BaseModel):
    items: list
    total: int
    page: int
    page_size: int
