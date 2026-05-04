"""Admin CRUD endpoints: blog posts, CMS pages, products, jobs, staff, departments, devices, applications."""
from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, log_activity, require_permission
from app.core.security import hash_password
from app.db.session import get_db
from app.models import (
    Application,
    BlogPost,
    Department,
    Device,
    Job,
    Page,
    Product,
    Role,
    User,
)
from app.schemas.common import (
    ApplicationOut,
    BlogPostOut,
    DepartmentOut,
    JobOut,
    PageOut,
    ProductOut,
    StaffOut,
)
from app.schemas.crud import (
    ApplicationStatusIn,
    BlogIn,
    BlogPatch,
    DepartmentIn,
    DepartmentPatch,
    DeviceIn,
    DevicePatch,
    DeviceWithToken,
    JobIn,
    JobPatch,
    PageIn,
    PagePatch,
    ProductIn,
    ProductPatch,
    StaffIn,
    StaffPatch,
)
from app.services.email import notify_leave_decided

router = APIRouter(prefix="/admin", tags=["admin-crud"])


from app.schemas.common import serialize_blog_post as _serialize_blog


# -------------------- Products --------------------

@router.post("/products", response_model=ProductOut, status_code=201)
def create_product(
    payload: ProductIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("content:manage")),
):
    if db.query(Product).filter(Product.slug == payload.slug).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "Product slug already exists")
    p = Product(**payload.model_dump())
    db.add(p)
    db.flush()
    log_activity(db, actor=user, action="create", resource_type="product", resource_id=p.id, request=request)
    db.commit()
    db.refresh(p)
    return p


@router.put("/products/{product_id}", response_model=ProductOut)
def update_product(
    product_id: int,
    payload: ProductPatch,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("content:manage")),
):
    p = db.get(Product, product_id)
    if not p:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(p, k, v)
    log_activity(db, actor=user, action="update", resource_type="product", resource_id=product_id, request=request)
    db.commit()
    db.refresh(p)
    return p


@router.delete("/products/{product_id}", status_code=204)
def delete_product(
    product_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("content:manage")),
):
    p = db.get(Product, product_id)
    if not p:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")
    p.is_deleted = True
    p.deleted_at = datetime.now(timezone.utc)
    log_activity(db, actor=user, action="delete", resource_type="product", resource_id=product_id, request=request)
    db.commit()


# -------------------- Blog --------------------

@router.post("/blog", response_model=BlogPostOut, status_code=201)
def create_post(
    payload: BlogIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("content:manage")),
):
    if db.query(BlogPost).filter(BlogPost.slug == payload.slug).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "Slug already exists")
    p = BlogPost(**payload.model_dump(), author_id=user.id)
    if payload.is_published and not payload.published_at:
        p.published_at = datetime.now(timezone.utc)
    db.add(p)
    db.flush()
    log_activity(db, actor=user, action="create", resource_type="blog_post", resource_id=p.id, request=request)
    db.commit()
    db.refresh(p)
    return _serialize_blog(p)


@router.put("/blog/{post_id}", response_model=BlogPostOut)
def update_post(
    post_id: int,
    payload: BlogPatch,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("content:manage")),
):
    p = db.get(BlogPost, post_id)
    if not p:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Post not found")
    data = payload.model_dump(exclude_unset=True)
    if "is_published" in data and data["is_published"] and not p.published_at:
        p.published_at = datetime.now(timezone.utc)
    for k, v in data.items():
        setattr(p, k, v)
    log_activity(db, actor=user, action="update", resource_type="blog_post", resource_id=post_id, request=request)
    db.commit()
    db.refresh(p)
    return _serialize_blog(p)


@router.delete("/blog/{post_id}", status_code=204)
def delete_post(
    post_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("content:manage")),
):
    p = db.get(BlogPost, post_id)
    if not p:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Post not found")
    p.is_deleted = True
    p.deleted_at = datetime.now(timezone.utc)
    log_activity(db, actor=user, action="delete", resource_type="blog_post", resource_id=post_id, request=request)
    db.commit()


# -------------------- CMS Pages --------------------

@router.post("/pages", response_model=PageOut, status_code=201)
def create_page(
    payload: PageIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("content:manage")),
):
    if db.query(Page).filter(Page.slug == payload.slug).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "Slug already exists")
    p = Page(**payload.model_dump())
    db.add(p)
    db.flush()
    log_activity(db, actor=user, action="create", resource_type="page", resource_id=p.id, request=request)
    db.commit()
    db.refresh(p)
    return p


@router.put("/pages/{page_id}", response_model=PageOut)
def update_page(
    page_id: int,
    payload: PagePatch,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("content:manage")),
):
    p = db.get(Page, page_id)
    if not p:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Page not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(p, k, v)
    log_activity(db, actor=user, action="update", resource_type="page", resource_id=page_id, request=request)
    db.commit()
    db.refresh(p)
    return p


@router.delete("/pages/{page_id}", status_code=204)
def delete_page(
    page_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("content:manage")),
):
    p = db.get(Page, page_id)
    if not p:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Page not found")
    p.is_deleted = True
    p.deleted_at = datetime.now(timezone.utc)
    log_activity(db, actor=user, action="delete", resource_type="page", resource_id=page_id, request=request)
    db.commit()


# -------------------- Jobs --------------------

@router.post("/jobs", response_model=JobOut, status_code=201)
def create_job(
    payload: JobIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("careers:manage")),
):
    if db.query(Job).filter(Job.slug == payload.slug).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "Slug already exists")
    j = Job(**payload.model_dump())
    db.add(j)
    db.flush()
    log_activity(db, actor=user, action="create", resource_type="job", resource_id=j.id, request=request)
    db.commit()
    db.refresh(j)
    return j


@router.put("/jobs/{job_id}", response_model=JobOut)
def update_job(
    job_id: int,
    payload: JobPatch,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("careers:manage")),
):
    j = db.get(Job, job_id)
    if not j:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(j, k, v)
    log_activity(db, actor=user, action="update", resource_type="job", resource_id=job_id, request=request)
    db.commit()
    db.refresh(j)
    return j


@router.delete("/jobs/{job_id}", status_code=204)
def delete_job(
    job_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("careers:manage")),
):
    j = db.get(Job, job_id)
    if not j:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    j.is_deleted = True
    j.deleted_at = datetime.now(timezone.utc)
    log_activity(db, actor=user, action="delete", resource_type="job", resource_id=job_id, request=request)
    db.commit()


@router.patch("/applications/{app_id}", response_model=ApplicationOut)
def update_application_status(
    app_id: int,
    payload: ApplicationStatusIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("careers:manage")),
):
    a = db.get(Application, app_id)
    if not a:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")
    a.status = payload.status
    log_activity(
        db,
        actor=user,
        action="status_change",
        resource_type="application",
        resource_id=app_id,
        request=request,
        details={"to": payload.status},
    )
    db.commit()
    db.refresh(a)
    return ApplicationOut(
        id=a.id,
        full_name=a.full_name,
        email=a.email,
        job_title=a.job.title if a.job else "—",
        status=a.status,
        created_at=a.created_at,
    )


# -------------------- Staff --------------------

@router.post("/staff", response_model=StaffOut, status_code=201)
def create_staff(
    payload: StaffIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("staff:manage")),
):
    if db.query(User).filter(User.email == payload.email.lower()).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already in use")
    role = db.query(Role).filter(Role.slug == payload.role_slug).first()
    if not role:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown role")
    dept = (
        db.query(Department).filter(Department.slug == payload.department_slug).first()
        if payload.department_slug
        else None
    )
    pw = payload.password or secrets.token_urlsafe(12)
    u = User(
        email=payload.email.lower(),
        full_name=payload.full_name,
        password_hash=hash_password(pw),
        role_id=role.id,
        department_id=dept.id if dept else None,
        job_title=payload.job_title,
        phone=payload.phone,
        biometric_id=payload.biometric_id,
        status="invited" if not payload.password else "active",
        is_active=True,
        # Always force a reset for invited users; if the inviter chose the
        # password, force a reset on first login too — admins shouldn't know
        # other people's passwords.
        must_reset_password=True,
    )
    db.add(u)
    db.flush()
    log_activity(
        db,
        actor=user,
        action="create",
        resource_type="user",
        resource_id=u.id,
        request=request,
        details={"role": role.slug, "generated_password": payload.password is None},
    )
    db.commit()
    db.refresh(u)
    return StaffOut(
        id=u.id,
        full_name=u.full_name,
        email=u.email,
        role=u.role.slug,
        department=u.department.name if u.department else None,
        job_title=u.job_title,
        status=u.status,
    )


@router.put("/staff/{user_id}", response_model=StaffOut)
def update_staff(
    user_id: int,
    payload: StaffPatch,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("staff:manage")),
):
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    data = payload.model_dump(exclude_unset=True)
    if "role_slug" in data:
        role = db.query(Role).filter(Role.slug == data.pop("role_slug")).first()
        if not role:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown role")
        u.role_id = role.id
    if "department_slug" in data:
        slug = data.pop("department_slug")
        dept = db.query(Department).filter(Department.slug == slug).first() if slug else None
        u.department_id = dept.id if dept else None
    for k, v in data.items():
        setattr(u, k, v)
    log_activity(db, actor=user, action="update", resource_type="user", resource_id=user_id, request=request)
    db.commit()
    db.refresh(u)
    return StaffOut(
        id=u.id,
        full_name=u.full_name,
        email=u.email,
        role=u.role.slug,
        department=u.department.name if u.department else None,
        job_title=u.job_title,
        status=u.status,
    )


@router.delete("/staff/{user_id}", status_code=204)
def delete_staff(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("staff:manage")),
):
    if user_id == user.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cannot delete yourself")
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    u.is_active = False
    u.status = "suspended"
    log_activity(db, actor=user, action="suspend", resource_type="user", resource_id=user_id, request=request)
    db.commit()


# -------------------- Departments --------------------

@router.post("/departments", response_model=DepartmentOut, status_code=201)
def create_dept(
    payload: DepartmentIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("staff:manage")),
):
    if db.query(Department).filter(Department.slug == payload.slug).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "Slug already exists")
    d = Department(**payload.model_dump())
    db.add(d)
    db.flush()
    log_activity(db, actor=user, action="create", resource_type="department", resource_id=d.id, request=request)
    db.commit()
    db.refresh(d)
    return DepartmentOut(
        id=d.id,
        slug=d.slug,
        name=d.name,
        head_name=d.head.full_name if d.head else None,
        staff_count=0,
    )


@router.put("/departments/{dept_id}", response_model=DepartmentOut)
def update_dept(
    dept_id: int,
    payload: DepartmentPatch,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("staff:manage")),
):
    d = db.get(Department, dept_id)
    if not d:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Department not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(d, k, v)
    log_activity(db, actor=user, action="update", resource_type="department", resource_id=dept_id, request=request)
    db.commit()
    db.refresh(d)
    from sqlalchemy import func
    count = db.query(func.count(User.id)).filter(User.department_id == d.id).scalar() or 0
    return DepartmentOut(
        id=d.id,
        slug=d.slug,
        name=d.name,
        head_name=d.head.full_name if d.head else None,
        staff_count=count,
    )


@router.delete("/departments/{dept_id}", status_code=204)
def delete_dept(
    dept_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("staff:manage")),
):
    d = db.get(Department, dept_id)
    if not d:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Department not found")
    db.query(User).filter(User.department_id == dept_id).update({User.department_id: None})
    d.is_deleted = True
    d.deleted_at = datetime.now(timezone.utc)
    log_activity(db, actor=user, action="delete", resource_type="department", resource_id=dept_id, request=request)
    db.commit()


# -------------------- Devices --------------------

@router.post("/devices", response_model=DeviceWithToken, status_code=201)
def create_device(
    payload: DeviceIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("devices:manage")),
):
    d = Device(**payload.model_dump(), api_token=secrets.token_urlsafe(24))
    db.add(d)
    db.flush()
    log_activity(db, actor=user, action="create", resource_type="device", resource_id=d.id, request=request)
    db.commit()
    db.refresh(d)
    return d


@router.put("/devices/{device_id}", response_model=DeviceWithToken)
def update_device(
    device_id: int,
    payload: DevicePatch,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("devices:manage")),
):
    d = db.get(Device, device_id)
    if not d:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Device not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(d, k, v)
    log_activity(db, actor=user, action="update", resource_type="device", resource_id=device_id, request=request)
    db.commit()
    db.refresh(d)
    return d


@router.post("/devices/{device_id}/rotate", response_model=DeviceWithToken)
def rotate_device_token(
    device_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("devices:manage")),
):
    d = db.get(Device, device_id)
    if not d:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Device not found")
    d.api_token = secrets.token_urlsafe(24)
    log_activity(db, actor=user, action="rotate_token", resource_type="device", resource_id=device_id, request=request)
    db.commit()
    db.refresh(d)
    return d


@router.delete("/devices/{device_id}", status_code=204)
def delete_device(
    device_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("devices:manage")),
):
    d = db.get(Device, device_id)
    if not d:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Device not found")
    d.is_deleted = True
    d.deleted_at = datetime.now(timezone.utc)
    log_activity(db, actor=user, action="delete", resource_type="device", resource_id=device_id, request=request)
    db.commit()
