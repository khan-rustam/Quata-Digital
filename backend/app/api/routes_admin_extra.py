"""Additional admin endpoints layered on top of the v0.2 admin module:

- Role CRUD with full permission management
- Partner request notes update
- Application filters
- Staff detail summary (profile + leave + attendance)
- Activity log filters (actor / action / resource / since / until)
"""
from datetime import date, datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy import cast, func, String as SqlString
from sqlalchemy.orm import Session

from app.api.deps import log_activity, require_permission
from app.db.session import get_db
from app.models import (
    ActivityLog,
    Application,
    ApplicationAttachment,
    ApplicationNote,
    AttendanceLog,
    LeaveRequest,
    NewsletterBroadcast,
    NewsletterSubscriber,
    PartnerRequest,
    Role,
    RolePermission,
    User,
)
from app.schemas.common import (
    ActivityOut,
    ApplicationOut,
    LeaveOut,
    AttendanceOut,
    RoleOut,
)

router = APIRouter(prefix="/admin", tags=["admin-extra"])


# Catalogue of all permissions the system understands. Used to render the
# roles editor on the frontend and validate input.
ALL_PERMISSIONS = [
    {"key": "*", "label": "Wildcard (super admin)", "group": "system"},
    {"key": "content:manage", "label": "Manage CMS content", "group": "content"},
    {"key": "partners:manage", "label": "Manage partner requests", "group": "pipeline"},
    {"key": "careers:manage", "label": "Manage careers & applicants", "group": "pipeline"},
    {"key": "staff:manage", "label": "Manage staff & departments", "group": "people"},
    {"key": "rbac:manage", "label": "Manage roles & permissions", "group": "people"},
    {"key": "devices:manage", "label": "Manage biometric devices", "group": "infra"},
    {"key": "activity:view", "label": "View activity logs", "group": "system"},
    {"key": "analytics:view", "label": "View website analytics", "group": "system"},
    {"key": "newsletter:manage", "label": "Manage newsletter subscribers", "group": "content"},
    {"key": "settings:manage", "label": "Manage site settings (integrations, contact info, social)", "group": "system"},
]


@router.get("/permissions")
def list_permissions(
    user: User = Depends(require_permission("rbac:manage")),
):
    return ALL_PERMISSIONS


# -------- Role CRUD --------

class RoleIn(BaseModel):
    slug: str
    name: str
    description: Optional[str] = None
    permissions: List[str] = Field(default_factory=list)


class RolePatch(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    permissions: Optional[List[str]] = None


def _serialize_role(r: Role) -> dict:
    return {
        "id": r.id,
        "slug": r.slug,
        "name": r.name,
        "description": r.description,
        "permissions": [p.permission for p in r.permissions],
    }


@router.post("/roles", status_code=201)
def create_role(
    payload: RoleIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("rbac:manage")),
):
    if db.query(Role).filter(Role.slug == payload.slug).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "Role slug already exists")
    valid = {p["key"] for p in ALL_PERMISSIONS}
    bad = [p for p in payload.permissions if p not in valid]
    if bad:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unknown permissions: {bad}")
    role = Role(slug=payload.slug, name=payload.name, description=payload.description)
    db.add(role)
    db.flush()
    for perm in payload.permissions:
        db.add(RolePermission(role_id=role.id, permission=perm))
    log_activity(
        db,
        actor=user,
        action="create",
        resource_type="role",
        resource_id=role.id,
        request=request,
        details={"permissions": payload.permissions},
    )
    db.commit()
    db.refresh(role)
    return _serialize_role(role)


@router.put("/roles/{role_id}")
def update_role(
    role_id: int,
    payload: RolePatch,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("rbac:manage")),
):
    role = db.get(Role, role_id)
    if not role:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Role not found")
    if role.slug == "super_admin":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Super admin role is immutable")

    if payload.name is not None:
        role.name = payload.name
    if payload.description is not None:
        role.description = payload.description
    if payload.permissions is not None:
        valid = {p["key"] for p in ALL_PERMISSIONS}
        bad = [p for p in payload.permissions if p not in valid]
        if bad:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unknown permissions: {bad}")
        # Replace permissions
        for p in list(role.permissions):
            db.delete(p)
        db.flush()
        for perm in payload.permissions:
            db.add(RolePermission(role_id=role.id, permission=perm))

    log_activity(
        db,
        actor=user,
        action="update",
        resource_type="role",
        resource_id=role.id,
        request=request,
    )
    db.commit()
    db.refresh(role)
    return _serialize_role(role)


@router.delete("/roles/{role_id}", status_code=204)
def delete_role(
    role_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("rbac:manage")),
):
    role = db.get(Role, role_id)
    if not role:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Role not found")
    if role.slug == "super_admin":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Super admin role cannot be deleted")
    in_use = db.query(func.count(User.id)).filter(User.role_id == role_id).scalar() or 0
    if in_use > 0:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Role is assigned to {in_use} user(s) — reassign first")
    db.delete(role)
    log_activity(
        db,
        actor=user,
        action="delete",
        resource_type="role",
        resource_id=role_id,
        request=request,
    )
    db.commit()


# -------- Partner notes --------

class PartnerNotesIn(BaseModel):
    notes: str


@router.put("/partners/{partner_id}/notes")
def update_partner_notes(
    partner_id: int,
    payload: PartnerNotesIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("partners:manage")),
):
    pr = db.get(PartnerRequest, partner_id)
    if not pr:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    pr.notes = payload.notes[:1000]
    log_activity(
        db,
        actor=user,
        action="update_notes",
        resource_type="partner_request",
        resource_id=partner_id,
        request=request,
    )
    db.commit()
    return {"ok": True, "notes": pr.notes}


@router.get("/partners/{partner_id:int}")
def get_partner_request(
    partner_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("partners:manage")),
):
    pr = db.get(PartnerRequest, partner_id)
    if not pr:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    return {
        "id": pr.id,
        "partner_type": pr.partner_type,
        "status": pr.status,
        "payload": pr.payload,
        "notes": pr.notes,
        "created_at": pr.created_at,
        "updated_at": pr.updated_at,
    }


# -------- Application filters & detail --------

@router.get("/applications/v2")
def list_applications_filtered(
    db: Session = Depends(get_db),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    job_id: Optional[int] = None,
    q: Optional[str] = None,
    user: User = Depends(require_permission("careers:manage")),
):
    qry = db.query(Application)
    if status_filter:
        qry = qry.filter(Application.status == status_filter)
    if job_id:
        qry = qry.filter(Application.job_id == job_id)
    if q:
        like = f"%{q.lower()}%"
        qry = qry.filter(
            func.lower(Application.full_name).like(like)
            | func.lower(Application.email).like(like)
        )
    rows = qry.order_by(Application.created_at.desc()).limit(200).all()
    return [
        {
            "id": r.id,
            "full_name": r.full_name,
            "email": r.email,
            "job_title": r.job.title if r.job else "—",
            "status": r.status,
            "created_at": r.created_at,
        }
        for r in rows
    ]


@router.get("/applications/{app_id}")
def get_application(
    app_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("careers:manage")),
):
    a = db.get(Application, app_id)
    if not a:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")
    from app.services.uploads import is_internal_upload_url
    # CVs are private (boss Q1): never hand the raw file URL to the browser.
    # The reviewer downloads via the authenticated endpoint below instead.
    return {
        "id": a.id,
        "full_name": a.full_name,
        "email": a.email,
        "phone": a.phone,
        "has_resume": is_internal_upload_url(a.resume_url),
        "cover_letter": a.cover_letter,
        "status": a.status,
        "job_id": a.job_id,
        "job_title": a.job.title if a.job else None,
        "interview_at": a.interview_at,
        "interview_location": a.interview_location,
        "start_date": a.start_date,
        "assigned_hr_id": a.assigned_hr_id,
        "assigned_hr_name": a.assigned_hr.full_name if a.assigned_hr else None,
        "created_at": a.created_at,
        "updated_at": a.updated_at,
    }


class ApplicationAssignIn(BaseModel):
    assigned_hr_id: Optional[int] = None


@router.patch("/applications/{app_id}/assignment")
def assign_application(
    app_id: int,
    payload: ApplicationAssignIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("careers:manage")),
):
    """Assign (or clear) the HR officer who owns this applicant."""
    a = db.get(Application, app_id)
    if not a:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")
    if payload.assigned_hr_id is not None and not db.get(User, payload.assigned_hr_id):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown staff member")
    a.assigned_hr_id = payload.assigned_hr_id
    log_activity(
        db,
        actor=user,
        action="assign",
        resource_type="application",
        resource_id=a.id,
        request=request,
        details={"assigned_hr_id": payload.assigned_hr_id},
    )
    db.commit()
    return {"ok": True, "assigned_hr_id": a.assigned_hr_id}


class ApplicationNoteIn(BaseModel):
    body: str = Field(min_length=1, max_length=8000)


@router.get("/applications/{app_id}/notes")
def list_application_notes(
    app_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("careers:manage")),
):
    a = db.get(Application, app_id)
    if not a:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")
    return [
        {
            "id": n.id,
            "body": n.body,
            "author_name": n.author.full_name if n.author else "—",
            "created_at": n.created_at,
        }
        for n in a.notes
    ]


@router.post("/applications/{app_id}/notes", status_code=201)
def add_application_note(
    app_id: int,
    payload: ApplicationNoteIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("careers:manage")),
):
    a = db.get(Application, app_id)
    if not a:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")
    note = ApplicationNote(application_id=a.id, author_id=user.id, body=payload.body.strip())
    db.add(note)
    db.flush()
    log_activity(
        db,
        actor=user,
        action="note",
        resource_type="application",
        resource_id=a.id,
        request=request,
    )
    db.commit()
    db.refresh(note)
    return {
        "id": note.id,
        "body": note.body,
        "author_name": user.full_name,
        "created_at": note.created_at,
    }


@router.get("/applications/{app_id}/timeline")
def application_timeline(
    app_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("careers:manage")),
):
    """Activity history for one applicant (status changes, notes, assignments,
    CV downloads) plus the initial submission — most recent first."""
    a = db.get(Application, app_id)
    if not a:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")
    rows = (
        db.query(ActivityLog)
        .filter(
            ActivityLog.resource_type.in_(["application", "resume"]),
            ActivityLog.resource_id == str(app_id),
        )
        .order_by(ActivityLog.created_at.desc())
        .limit(200)
        .all()
    )
    events = [
        {
            "id": r.id,
            "action": r.action,
            "actor_id": r.actor_id,
            "details": r.details or {},
            "created_at": r.created_at,
        }
        for r in rows
    ]
    # The submission itself is logged against the job, so synthesise it here.
    events.append(
        {"id": 0, "action": "applied", "actor_id": None, "details": {}, "created_at": a.created_at}
    )
    return events


@router.get("/applications/{app_id}/resume")
def download_application_resume(
    app_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("careers:manage")),
):
    """Stream an applicant's CV to an authorised reviewer only (boss Q1).

    CVs are private — the file is not served from the public ``/uploads``
    mount (see the resume guard in ``main.py``), so this authenticated route
    is the only way to read one. Local-disk backend only: resumes are never
    written to S3 in this deployment, and every access is audit-logged.
    """
    a = db.get(Application, app_id)
    if not a:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")
    from app.services.uploads import resolve_local_upload_path

    path = resolve_local_upload_path(a.resume_url)
    if path is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Resume file not available")
    log_activity(
        db,
        actor=user,
        action="download",
        resource_type="resume",
        resource_id=a.id,
        request=request,
    )
    db.commit()
    return FileResponse(path, filename=f"resume-{a.id}{path.suffix.lower()}")


# -------- Applicant attachments (private HR documents) --------

@router.get("/applications/{app_id}/attachments")
def list_application_attachments(
    app_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("careers:manage")),
):
    a = db.get(Application, app_id)
    if not a:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")
    return [
        {
            "id": att.id,
            "filename": att.filename,
            "label": att.label,
            "size": att.size,
            "content_type": att.content_type,
            "uploaded_by": att.uploaded_by.full_name if att.uploaded_by else None,
            "created_at": att.created_at,
        }
        for att in a.attachments
    ]


@router.post("/applications/{app_id}/attachments", status_code=201)
def upload_application_attachment(
    app_id: int,
    request: Request,
    file: UploadFile = File(...),
    label: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("careers:manage")),
):
    """Attach a private HR document (offer letter, assessment, reference check)
    to an applicant. Stored under the private ``applicant-docs`` folder and
    only retrievable via the download endpoint below."""
    a = db.get(Application, app_id)
    if not a:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")
    from app.services.uploads import save_upload

    info = save_upload(file, folder="applicant-docs")
    att = ApplicationAttachment(
        application_id=a.id,
        uploaded_by_id=user.id,
        filename=file.filename or info["filename"],
        url=info["url"],
        content_type=info.get("content_type"),
        size=info.get("size"),
        label=(label or "").strip() or None,
    )
    db.add(att)
    db.flush()
    log_activity(
        db, actor=user, action="attach", resource_type="application",
        resource_id=a.id, request=request, details={"filename": att.filename},
    )
    db.commit()
    db.refresh(att)
    return {"id": att.id, "filename": att.filename, "label": att.label}


@router.get("/applications/{app_id}/attachments/{att_id}")
def download_application_attachment(
    app_id: int,
    att_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("careers:manage")),
):
    att = db.get(ApplicationAttachment, att_id)
    if not att or att.application_id != app_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Attachment not found")
    from app.services.uploads import resolve_local_upload_path

    path = resolve_local_upload_path(att.url)
    if path is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "File not available")
    log_activity(
        db, actor=user, action="download", resource_type="application",
        resource_id=app_id, request=request, details={"attachment_id": att_id},
    )
    db.commit()
    return FileResponse(path, filename=att.filename)


@router.delete("/applications/{app_id}/attachments/{att_id}", status_code=204)
def delete_application_attachment(
    app_id: int,
    att_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("careers:manage")),
):
    att = db.get(ApplicationAttachment, att_id)
    if not att or att.application_id != app_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Attachment not found")
    db.delete(att)
    log_activity(
        db, actor=user, action="detach", resource_type="application",
        resource_id=app_id, request=request, details={"attachment_id": att_id},
    )
    db.commit()


# -------- Staff detail --------

@router.post("/staff/{user_id}/identity", status_code=201)
def generate_staff_identity(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("staff:manage")),
):
    """Assign a permanent employee number + verification code to a staff member
    who doesn't have one yet (e.g. hired before this feature). Never overwrites
    an existing number."""
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Staff not found")
    from app.services.identity import ensure_employee_identity

    changed = ensure_employee_identity(db, u)
    if changed:
        log_activity(
            db, actor=user, action="assign_identity", resource_type="user",
            resource_id=u.id, request=request, details={"employee_number": u.employee_number},
        )
    db.commit()
    return {"employee_number": u.employee_number, "verification_code": u.verification_code}


@router.get("/staff/{user_id}/id-card")
def staff_id_card(
    user_id: int,
    format: str = Query(default="png", pattern="^(png|pdf)$"),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("staff:manage")),
):
    """Render a print-ready employee ID card (PNG or PDF). Ensures the employee
    has an identity first so the card always has a number + QR."""
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Staff not found")
    from app.services.identity import ensure_employee_identity

    if ensure_employee_identity(db, u):
        db.commit()
    from app.services.id_card import render_id_card_png, render_id_card_pdf

    stem = f"id-card-{u.employee_number or u.id}"
    if format == "pdf":
        return Response(
            content=render_id_card_pdf(u),
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{stem}.pdf"'},
        )
    return Response(
        content=render_id_card_png(u),
        media_type="image/png",
        headers={"Content-Disposition": f'inline; filename="{stem}.png"'},
    )


@router.get("/staff/{user_id}")
def get_staff_detail(
    user_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("staff:manage")),
):
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Staff not found")
    leave = (
        db.query(LeaveRequest)
        .filter(LeaveRequest.user_id == user_id)
        .order_by(LeaveRequest.created_at.desc())
        .limit(10)
        .all()
    )
    attendance = (
        db.query(AttendanceLog)
        .filter(AttendanceLog.user_id == user_id)
        .order_by(AttendanceLog.check_in_at.desc().nulls_last(), AttendanceLog.created_at.desc())
        .limit(10)
        .all()
    )
    activity = (
        db.query(ActivityLog)
        .filter(ActivityLog.actor_id == user_id)
        .order_by(ActivityLog.created_at.desc())
        .limit(20)
        .all()
    )
    return {
        "profile": {
            "id": u.id,
            "full_name": u.full_name,
            "email": u.email,
            "phone": u.phone,
            "avatar_url": u.avatar_url,
            "job_title": u.job_title,
            "biometric_id": u.biometric_id,
            "employee_number": u.employee_number,
            "verification_code": u.verification_code,
            "role": u.role.slug if u.role else None,
            "department": u.department.name if u.department else None,
            "status": u.status,
            "created_at": u.created_at,
            # Personnel file (HRMS 2A)
            "gender": u.gender,
            "date_of_birth": u.date_of_birth,
            "nationality": u.nationality,
            "national_id": u.national_id,
            "marital_status": u.marital_status,
            "blood_group": u.blood_group,
            "personal_email": u.personal_email,
            "address": u.address,
            "emergency_contacts": u.emergency_contacts or [],
            "employment_type": u.employment_type,
            "grade": u.grade,
            "work_location": u.work_location,
            "manager_id": u.manager_id,
            "manager_name": u.manager.full_name if u.manager else None,
            "date_hired": u.date_hired,
            "confirmation_date": u.confirmation_date,
            "contract_expiry": u.contract_expiry,
            "probation_status": u.probation_status,
            "education": u.education,
            "skills": u.skills or [],
            "languages": u.languages or [],
            "certifications": u.certifications or [],
            "previous_employment": u.previous_employment,
            "portfolio_url": u.portfolio_url,
        },
        "leave": [
            {
                "id": l.id,
                "leave_type": l.leave_type,
                "start_date": l.start_date,
                "end_date": l.end_date,
                "days": l.days,
                "status": l.status,
            }
            for l in leave
        ],
        "attendance": [
            {
                "id": a.id,
                "check_in_at": a.check_in_at,
                "check_out_at": a.check_out_at,
                "source": a.source,
                "status": a.status,
            }
            for a in attendance
        ],
        "activity": [
            {
                "id": ev.id,
                "action": ev.action,
                "resource_type": ev.resource_type,
                "resource_id": ev.resource_id,
                "created_at": ev.created_at,
            }
            for ev in activity
        ],
    }


# -------- Activity log filters --------

@router.get("/activity/v2", response_model=List[ActivityOut])
def list_activity_filtered(
    db: Session = Depends(get_db),
    actor_id: Optional[int] = None,
    action: Optional[str] = None,
    resource_type: Optional[str] = None,
    since: Optional[date] = None,
    until: Optional[date] = None,
    limit: int = Query(default=200, ge=1, le=1000),
    user: User = Depends(require_permission("activity:view")),
):
    qry = db.query(ActivityLog)
    if actor_id:
        qry = qry.filter(ActivityLog.actor_id == actor_id)
    if action:
        qry = qry.filter(ActivityLog.action == action)
    if resource_type:
        qry = qry.filter(ActivityLog.resource_type == resource_type)
    if since:
        qry = qry.filter(ActivityLog.created_at >= datetime.combine(since, datetime.min.time()))
    if until:
        qry = qry.filter(ActivityLog.created_at <= datetime.combine(until, datetime.max.time()))
    rows = qry.order_by(ActivityLog.created_at.desc()).limit(limit).all()
    return [
        ActivityOut(
            id=r.id,
            actor_name=r.actor.full_name if r.actor else "Public",
            action=r.action,
            resource_type=r.resource_type,
            resource_id=r.resource_id,
            ip_address=r.ip_address,
            details=r.details or {},
            created_at=r.created_at,
        )
        for r in rows
    ]


# -------- Leave reschedule (drag) --------

class LeaveDatesIn(BaseModel):
    start_date: date
    end_date: date


@router.patch("/leave/{leave_id}/dates")
def reschedule_leave(
    leave_id: int,
    payload: LeaveDatesIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("staff:manage")),
):
    lr = db.get(LeaveRequest, leave_id)
    if not lr:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Leave not found")
    if payload.end_date < payload.start_date:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "end_date must be on or after start_date")
    lr.start_date = payload.start_date
    lr.end_date = payload.end_date
    lr.days = (payload.end_date - payload.start_date).days + 1
    log_activity(
        db,
        actor=user,
        action="reschedule_leave",
        resource_type="leave_request",
        resource_id=leave_id,
        request=request,
        details={"start": str(payload.start_date), "end": str(payload.end_date)},
    )
    db.commit()
    return {"id": lr.id, "start_date": str(lr.start_date), "end_date": str(lr.end_date), "days": lr.days}


@router.get("/activity/distinct-actions")
def distinct_actions(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("activity:view")),
):
    rows = (
        db.query(ActivityLog.action, func.count(ActivityLog.id))
        .group_by(ActivityLog.action)
        .order_by(func.count(ActivityLog.id).desc())
        .all()
    )
    return [{"action": a, "count": c} for a, c in rows]


@router.get("/activity/distinct-resources")
def distinct_resources(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("activity:view")),
):
    rows = (
        db.query(ActivityLog.resource_type, func.count(ActivityLog.id))
        .group_by(ActivityLog.resource_type)
        .order_by(func.count(ActivityLog.id).desc())
        .all()
    )
    return [{"resource_type": r, "count": c} for r, c in rows]


# -------- Analytics extra: time-series --------

# -------- Newsletter --------

@router.get("/newsletter")
def list_newsletter_subscribers(
    db: Session = Depends(get_db),
    is_active: Optional[bool] = Query(default=None),
    q: Optional[str] = None,
    limit: int = Query(default=200, ge=1, le=1000),
    user: User = Depends(require_permission("newsletter:manage")),
):
    qry = db.query(NewsletterSubscriber)
    if is_active is not None:
        qry = qry.filter(NewsletterSubscriber.is_active == is_active)
    if q:
        like = f"%{q.lower()}%"
        qry = qry.filter(func.lower(NewsletterSubscriber.email).like(like))
    rows = qry.order_by(NewsletterSubscriber.created_at.desc()).limit(limit).all()
    total = db.query(func.count(NewsletterSubscriber.id)).scalar() or 0
    active = (
        db.query(func.count(NewsletterSubscriber.id))
        .filter(NewsletterSubscriber.is_active == True)  # noqa: E712
        .scalar()
        or 0
    )
    return {
        "total": total,
        "active": active,
        "items": [
            {
                "id": r.id,
                "email": r.email,
                "source": r.source,
                "locale": r.locale,
                "is_active": r.is_active,
                "confirmed_at": r.confirmed_at,
                "unsubscribed_at": r.unsubscribed_at,
                "created_at": r.created_at,
            }
            for r in rows
        ],
    }


@router.get("/newsletter/export.csv")
def export_newsletter_csv(
    db: Session = Depends(get_db),
    is_active: Optional[bool] = Query(default=True),
    user: User = Depends(require_permission("newsletter:manage")),
):
    import csv
    import io
    from fastapi.responses import StreamingResponse

    qry = db.query(NewsletterSubscriber)
    if is_active is not None:
        qry = qry.filter(NewsletterSubscriber.is_active == is_active)
    # Stream rows; previous implementation buffered the whole result set
    # in memory and stalled for tens of thousands of subscribers.
    qry = (
        qry.order_by(NewsletterSubscriber.created_at.asc())
        .execution_options(stream_results=True)
        .yield_per(500)
    )

    def iter_rows():
        header = io.StringIO()
        csv.writer(header).writerow(
            ["email", "source", "locale", "is_active", "subscribed_at", "unsubscribed_at"]
        )
        yield header.getvalue()
        for r in qry:
            line = io.StringIO()
            csv.writer(line).writerow(
                [
                    r.email,
                    r.source or "",
                    r.locale or "",
                    "yes" if r.is_active else "no",
                    r.created_at.isoformat() if r.created_at else "",
                    r.unsubscribed_at.isoformat() if r.unsubscribed_at else "",
                ]
            )
            yield line.getvalue()

    return StreamingResponse(
        iter_rows(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="newsletter-subscribers.csv"'},
    )


@router.delete("/newsletter/{subscriber_id}", status_code=204)
def delete_newsletter_subscriber(
    subscriber_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("newsletter:manage")),
):
    sub = db.get(NewsletterSubscriber, subscriber_id)
    if not sub:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Subscriber not found")
    db.delete(sub)
    log_activity(
        db,
        actor=user,
        action="delete",
        resource_type="newsletter",
        resource_id=subscriber_id,
        request=request,
    )
    db.commit()


# -------- Retention prune (activity log + page views) --------

@router.get("/retention/preview")
def retention_preview(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("activity:view")),
):
    """How many rows would be deleted if prune ran right now."""
    from app.core.config import settings as _settings
    from app.models import PageView

    cutoff_act = datetime.now(timezone.utc) - timedelta(
        days=_settings.ACTIVITY_LOG_RETENTION_DAYS
    )
    cutoff_pv = datetime.now(timezone.utc) - timedelta(
        days=_settings.PAGE_VIEW_RETENTION_DAYS
    )
    activity_count = (
        db.query(func.count(ActivityLog.id))
        .filter(ActivityLog.created_at < cutoff_act)
        .scalar()
        or 0
    )
    pageview_count = (
        db.query(func.count(PageView.id))
        .filter(PageView.created_at < cutoff_pv)
        .scalar()
        or 0
    )
    return {
        "activity_log": {
            "retention_days": _settings.ACTIVITY_LOG_RETENTION_DAYS,
            "would_delete": activity_count,
            "cutoff": cutoff_act.isoformat(),
        },
        "page_views": {
            "retention_days": _settings.PAGE_VIEW_RETENTION_DAYS,
            "would_delete": pageview_count,
            "cutoff": cutoff_pv.isoformat(),
        },
    }


# NOTE: retention_prune is destructive (hard-deletes activity logs, page
# views, media assets and version history). It must require a manage-tier
# permission, not the read-only `activity:view`.
@router.post("/retention/prune")
def retention_prune(
    request: Request,
    db: Session = Depends(get_db),
    # `rbac:manage` is the strongest non-wildcard permission and is held
    # only by super_admin + admin in the seeded role set, which is the
    # right blast radius for an irreversible purge.
    user: User = Depends(require_permission("rbac:manage")),
):
    """Hard-delete activity-log + page-view rows older than the retention
    windows configured in settings. Idempotent — safe to call from cron.
    """
    from app.core.config import settings as _settings
    from app.models import PageView

    cutoff_act = datetime.now(timezone.utc) - timedelta(
        days=_settings.ACTIVITY_LOG_RETENTION_DAYS
    )
    cutoff_pv = datetime.now(timezone.utc) - timedelta(
        days=_settings.PAGE_VIEW_RETENTION_DAYS
    )
    from app.models import MediaAsset, PageContentVersion

    cutoff_media = datetime.now(timezone.utc) - timedelta(days=30)

    deleted_act = (
        db.query(ActivityLog)
        .filter(ActivityLog.created_at < cutoff_act)
        .delete(synchronize_session=False)
    )
    deleted_pv = (
        db.query(PageView)
        .filter(PageView.created_at < cutoff_pv)
        .delete(synchronize_session=False)
    )
    # Hard-delete media that's been soft-deleted for 30+ days. Soft-deleted
    # rows are kept around long enough for the boss to spot a mistake; after
    # that we reclaim DB rows. Files on disk are NOT touched here — that's
    # a separate operation since other pages may still link to a leaked URL.
    deleted_media = (
        db.query(MediaAsset)
        .execution_options(include_deleted=True)
        .filter(
            MediaAsset.is_deleted == True,  # noqa: E712
            MediaAsset.deleted_at < cutoff_media,
        )
        .delete(synchronize_session=False)
    )
    # Page-content versions are already capped at 10 per page on every save,
    # but if a page is itself deleted the versions stay forever — sweep
    # orphans here.
    from app.models import PageContent

    live_slugs = {r[0] for r in db.query(PageContent.slug).all()}
    if live_slugs:
        deleted_versions = (
            db.query(PageContentVersion)
            .filter(PageContentVersion.page_slug.notin_(live_slugs))
            .delete(synchronize_session=False)
        )
    else:
        deleted_versions = 0

    log_activity(
        db,
        actor=user,
        action="retention_prune",
        resource_type="system",
        request=request,
        details={
            "activity_log": deleted_act,
            "page_views": deleted_pv,
            "media_assets_purged": deleted_media,
            "orphan_page_versions": deleted_versions,
        },
    )
    db.commit()
    return {
        "deleted": {
            "activity_log": deleted_act,
            "page_views": deleted_pv,
            "media_assets_purged": deleted_media,
            "orphan_page_versions": deleted_versions,
        }
    }


@router.get("/analytics/broken-paths")
def admin_broken_paths(
    days: int = Query(default=30, ge=1, le=180),
    limit: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("analytics:view")),
):
    """Top inbound 404 paths over the last N days. Lets the admin spot
    broken external links and add redirects."""
    from app.models import PageView

    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = (
        db.query(
            PageView.path,
            func.count(PageView.id).label("hits"),
            func.count(func.distinct(PageView.referrer)).label("referrers"),
        )
        .filter(PageView.is_404 == True)  # noqa: E712
        .filter(PageView.created_at >= since)
        .group_by(PageView.path)
        .order_by(func.count(PageView.id).desc())
        .limit(limit)
        .all()
    )
    return [
        {"path": r[0], "hits": r[1], "distinct_referrers": r[2]}
        for r in rows
    ]


@router.post("/media/reconcile-used-on")
def media_reconcile_used_on(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("content:manage")),
):
    """Rebuild every `MediaAsset.used_on` from scratch by walking all
    `PageContent.sections` payloads.

    Why this exists: the live tracking is updated incrementally on every
    page save, but if the boss hand-types a URL into a section, or a row
    drifts due to a partial save, the indexes can fall out of sync.
    Running this is idempotent and safe; recommended as a weekly cron.
    """
    from app.models import MediaAsset, PageContent
    from app.services.media_usage import extract_media_urls_from_sections

    # 1) Build the canonical url -> {slug, slug, ...} map from all pages.
    canonical: dict[str, set[str]] = {}
    pages = db.query(PageContent).all()
    for p in pages:
        urls = extract_media_urls_from_sections(p.sections or [])
        for url in urls:
            canonical.setdefault(url, set()).add(p.slug)

    # 2) Walk every live MediaAsset; replace `used_on` with the canonical
    # set for that URL (empty list when the asset isn't referenced anywhere).
    rows = (
        db.query(MediaAsset)
        .filter(MediaAsset.is_deleted == False)  # noqa: E712
        .all()
    )
    updated = 0
    for r in rows:
        new_set = sorted(canonical.get(r.url, set()))
        if list(r.used_on or []) != new_set:
            r.used_on = new_set
            updated += 1

    log_activity(
        db,
        actor=user,
        action="reconcile_media_used_on",
        resource_type="media_asset",
        request=request,
        details={
            "rows_total": len(rows),
            "rows_updated": updated,
            "urls_referenced": len(canonical),
        },
    )
    db.commit()
    return {
        "rows_total": len(rows),
        "rows_updated": updated,
        "urls_referenced_from_pages": len(canonical),
    }


@router.get("/analytics/timeseries")
def analytics_timeseries(
    days: int = Query(default=14, ge=1, le=90),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("analytics:view")),
):
    """Daily counts of pageviews / partner submissions / applications.

    Previously this issued ``3 × days`` count queries inside a Python
    loop (up to 270 round-trips for a 90-day chart). We now issue **one
    grouped query per series**, bucketing by the date portion of
    ``created_at`` and zero-filling missing days in Python.
    """
    from app.models import PageView

    today = datetime.now(timezone.utc).date()
    window_start = datetime.combine(
        today - timedelta(days=days - 1), datetime.min.time(), tzinfo=timezone.utc
    )

    def _bucket(model) -> dict[str, int]:
        # ``func.date(col)`` is portable between SQLite + Postgres; both
        # render dates as ``YYYY-MM-DD`` strings here.
        rows = (
            db.query(
                func.date(model.created_at).label("d"),
                func.count(model.id).label("c"),
            )
            .filter(model.created_at >= window_start)
            .group_by("d")
            .all()
        )
        return {str(r.d): int(r.c) for r in rows}

    visit_counts = _bucket(PageView)
    partner_counts = _bucket(PartnerRequest)
    app_counts = _bucket(Application)

    series_visits = []
    series_partners = []
    series_apps = []
    for i in range(days - 1, -1, -1):
        d = today - timedelta(days=i)
        key = d.isoformat()
        series_visits.append({"date": key, "value": visit_counts.get(key, 0)})
        series_partners.append({"date": key, "value": partner_counts.get(key, 0)})
        series_apps.append({"date": key, "value": app_counts.get(key, 0)})
    return {
        "visits": series_visits,
        "partner_requests": series_partners,
        "job_applications": series_apps,
    }


# -------- Newsletter broadcast: compose & send to all active subscribers --------


class BroadcastIn(BaseModel):
    # Caps are conservative — a 100 KB body is well above any real newsletter
    # we'd send, but small enough that a compromised editor can't spool
    # multi-MB phishing payloads through `noreply@quatadigital.com`.
    subject: str = Field(..., min_length=1, max_length=255)
    body: str = Field(..., min_length=1, max_length=100_000)
    test_email: Optional[str] = None  # if set, send only to this address (preview)


def _sanitize_broadcast_body(raw: str) -> str:
    """Strip ASCII control characters except newline + tab.

    Email clients render carriage-return + form-feed inconsistently, and
    NULL/escape characters in a subject/body line are a classic header-
    injection vector. We keep only printable + whitespace and clamp to
    the schema's already-enforced length cap as defence in depth.
    """
    keep = []
    for ch in raw:
        code = ord(ch)
        if code in (0x09, 0x0A):  # tab, newline
            keep.append(ch)
        elif code < 0x20 or code == 0x7F:
            continue
        else:
            keep.append(ch)
    return "".join(keep)[:100_000]


@router.post("/newsletter/broadcast", status_code=201)
def send_broadcast(
    payload: BroadcastIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("newsletter:manage")),
):
    """Send a newsletter to all active subscribers (or to `test_email` only,
    when set, for previews). Records a NewsletterBroadcast row regardless of
    outcome so the team has a full audit trail."""
    from app.services.email import send_email
    from app.core.config import settings as _settings

    # Defence in depth: strip control chars from the editor input before
    # touching the audit row or the SMTP body.
    payload = payload.model_copy(update={"body": _sanitize_broadcast_body(payload.body)})

    test_only = bool(payload.test_email and payload.test_email.strip())

    if test_only:
        recipients = [payload.test_email.strip().lower()]
    else:
        rows = (
            db.query(NewsletterSubscriber)
            .filter(NewsletterSubscriber.is_active == True)  # noqa: E712
            .order_by(NewsletterSubscriber.email)
            .all()
        )
        recipients = [r.email for r in rows]

    if not recipients:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "No active subscribers — nothing to send.",
        )

    # Insert the audit row up-front so a mid-send crash still leaves a trace.
    bc = NewsletterBroadcast(
        subject=payload.subject,
        body=payload.body,
        sender_id=user.id,
        recipients_count=len(recipients),
        status="pending",
    )
    db.add(bc)
    db.flush()
    bc_id = bc.id

    # Per-recipient send. When REDIS_URL is configured the helper enqueues
    # one RQ job per recipient and returns immediately — the worker process
    # increments the broadcast's counters as each email lands. When Redis is
    # absent (current single-VPS prod), the helper falls back to running the
    # job synchronously here, identical to the previous behaviour.
    from app.services.newsletter_tokens import unsubscribe_url_for
    from app.services.queue import _get_queue, enqueue
    from app.services.email_jobs import send_broadcast_email

    is_async = _get_queue() is not None

    delivered = 0
    failed = 0
    first_err: Optional[str] = None

    if is_async:
        for to in recipients:
            footer = (
                "\n\n—\n"
                "You're receiving this because you subscribed to QUATA Digital "
                "updates. To unsubscribe in one click:\n"
                f"{unsubscribe_url_for(to)}"
            )
            try:
                enqueue(
                    send_broadcast_email,
                    to=to,
                    subject=payload.subject,
                    body=payload.body + footer,
                    broadcast_id=bc_id,
                    description=f"newsletter:{bc_id}:{to}",
                )
            except Exception as exc:  # noqa: BLE001
                failed += 1
                if first_err is None:
                    first_err = f"enqueue failed: {type(exc).__name__}: {str(exc)[:200]}"
    else:
        for to in recipients:
            footer = (
                "\n\n—\n"
                "You're receiving this because you subscribed to QUATA Digital "
                "updates. To unsubscribe in one click:\n"
                f"{unsubscribe_url_for(to)}"
            )
            body_with_footer = payload.body + footer
            try:
                ok = send_email(to=to, subject=payload.subject, body=body_with_footer)
                if ok:
                    delivered += 1
                else:
                    failed += 1
                    if first_err is None:
                        first_err = "send_email returned False (check EMAIL_BACKEND / SMTP creds)"
            except Exception as exc:  # noqa: BLE001
                failed += 1
                if first_err is None:
                    first_err = f"{type(exc).__name__}: {str(exc)[:200]}"

    bc = db.get(NewsletterBroadcast, bc_id)
    if bc is None:
        # Defensive — should never happen, but don't crash the response.
        return {"id": bc_id, "delivered": delivered, "failed": failed}
    if is_async:
        # Counts are incremented by the worker as jobs complete. Mark the
        # broadcast as queued; it'll flip to sent/failed organically.
        bc.status = "queued"
        bc.error_summary = first_err
        bc.sent_at = datetime.now(timezone.utc)
    else:
        bc.delivered_count = delivered
        bc.failed_count = failed
        bc.sent_at = datetime.now(timezone.utc)
        bc.status = "sent" if failed == 0 else ("failed" if delivered == 0 else "sent")
        bc.error_summary = first_err

    log_activity(
        db,
        actor=user,
        action="newsletter_broadcast" if not test_only else "newsletter_broadcast_test",
        resource_type="newsletter_broadcast",
        resource_id=bc.id,
        request=request,
        details={
            "recipients": len(recipients),
            "delivered": delivered,
            "failed": failed,
            "test": test_only,
            "mode": "queued" if is_async else "synchronous",
        },
    )
    db.commit()
    db.refresh(bc)
    return {
        "id": bc.id,
        "subject": bc.subject,
        "mode": "queued" if is_async else "synchronous",
        "recipients_count": bc.recipients_count,
        "delivered": bc.delivered_count,
        "failed": bc.failed_count,
        "status": bc.status,
        "sent_at": bc.sent_at,
        "error_summary": bc.error_summary,
        "test_only": test_only,
    }


@router.get("/newsletter/broadcasts")
def list_broadcasts(
    db: Session = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=500),
    user: User = Depends(require_permission("newsletter:manage")),
):
    rows = (
        db.query(NewsletterBroadcast)
        .order_by(NewsletterBroadcast.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": r.id,
            "subject": r.subject,
            "recipients_count": r.recipients_count,
            "delivered_count": r.delivered_count,
            "failed_count": r.failed_count,
            "status": r.status,
            "sent_at": r.sent_at,
            "created_at": r.created_at,
            "sender": r.sender.full_name if r.sender else "—",
            "error_summary": r.error_summary,
        }
        for r in rows
    ]


@router.get("/newsletter/broadcasts/{broadcast_id}")
def get_broadcast(
    broadcast_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("newsletter:manage")),
):
    bc = db.get(NewsletterBroadcast, broadcast_id)
    if not bc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Broadcast not found")
    return {
        "id": bc.id,
        "subject": bc.subject,
        "body": bc.body,
        "recipients_count": bc.recipients_count,
        "delivered_count": bc.delivered_count,
        "failed_count": bc.failed_count,
        "status": bc.status,
        "sent_at": bc.sent_at,
        "created_at": bc.created_at,
        "sender": bc.sender.full_name if bc.sender else "—",
        "error_summary": bc.error_summary,
    }
