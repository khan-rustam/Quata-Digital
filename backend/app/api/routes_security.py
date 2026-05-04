"""2FA enrolment + notification prefs + soft-delete restore."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, log_activity, require_permission
from app.core.security import verify_password
from app.db.session import get_db
from app.models import (
    Application,
    BlogPost,
    Department,
    Device,
    Job,
    Page,
    PartnerRequest,
    Product,
    User,
)
from app.services.security_extras import (
    hash_recovery_code,
    make_recovery_codes,
    new_totp_secret,
    totp_qr_data_url,
    totp_uri,
    verify_totp,
)


router = APIRouter(tags=["security"])


# ---------------- 2FA ----------------

class TotpEnrolStartIn(BaseModel):
    password: str  # require password to start enrolment


class TotpVerifyIn(BaseModel):
    code: str


@router.post("/me/2fa/enrol")
def begin_totp_enrol(
    payload: TotpEnrolStartIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Password is incorrect")
    secret = new_totp_secret()
    user.totp_secret = secret
    user.totp_enabled = False  # not enabled until verified
    log_activity(db, actor=user, action="2fa_enrol_started", resource_type="user", resource_id=user.id, request=request)
    db.commit()

    uri = totp_uri(secret, user.email)
    return {
        "secret": secret,
        "otpauth_uri": uri,
        "qr_data_url": totp_qr_data_url(uri),
    }


@router.post("/me/2fa/verify")
def verify_totp_enrol(
    payload: TotpVerifyIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not user.totp_secret:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Start enrolment first")
    if not verify_totp(user.totp_secret, payload.code):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid code")

    user.totp_enabled = True
    raw_codes = make_recovery_codes()
    user.totp_recovery_codes = [hash_recovery_code(c) for c in raw_codes]
    log_activity(db, actor=user, action="2fa_enabled", resource_type="user", resource_id=user.id, request=request)
    db.commit()
    return {"enabled": True, "recovery_codes": raw_codes}


@router.post("/me/2fa/disable")
def disable_totp(
    payload: TotpEnrolStartIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Password is incorrect")
    user.totp_enabled = False
    user.totp_secret = None
    user.totp_recovery_codes = None
    log_activity(db, actor=user, action="2fa_disabled", resource_type="user", resource_id=user.id, request=request)
    db.commit()
    return {"enabled": False}


# ---------------- Notification preferences ----------------

DEFAULT_NOTIFICATION_PREFS = {
    "partner_requests": True,
    "job_applications": True,
    "leave_decisions": True,
    "contact_messages": False,
    "weekly_digest": True,
    "system_alerts": True,
}


@router.get("/me/notifications")
def get_notification_prefs(user: User = Depends(get_current_user)):
    return user.notification_prefs or DEFAULT_NOTIFICATION_PREFS


@router.put("/me/notifications")
def update_notification_prefs(
    payload: dict,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    cleaned = {k: bool(v) for k, v in payload.items() if k in DEFAULT_NOTIFICATION_PREFS}
    merged = {**DEFAULT_NOTIFICATION_PREFS, **(user.notification_prefs or {}), **cleaned}
    user.notification_prefs = merged
    log_activity(
        db,
        actor=user,
        action="update_notification_prefs",
        resource_type="user",
        resource_id=user.id,
        request=request,
    )
    db.commit()
    return merged


# ---------------- Soft-delete: trash + restore ----------------

# Whitelist of resources we expose for restore. Maps slug -> ORM model.
RESTORABLE = {
    "products": Product,
    "blog": BlogPost,
    "pages": Page,
    "jobs": Job,
    "applications": Application,
    "partners": PartnerRequest,
    "departments": Department,
    "devices": Device,
    "staff": User,
}

PERM_FOR_RESTORE = {
    "products": "content:manage",
    "blog": "content:manage",
    "pages": "content:manage",
    "jobs": "careers:manage",
    "applications": "careers:manage",
    "partners": "partners:manage",
    "departments": "staff:manage",
    "devices": "devices:manage",
    "staff": "staff:manage",
}


@router.get("/admin/trash/{resource}")
def list_trash(
    resource: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if resource not in RESTORABLE:
        raise HTTPException(404, "Unknown resource")
    perm = PERM_FOR_RESTORE[resource]
    if perm and "*" not in {p for p in (user_perms(user))} and perm not in user_perms(user):
        raise HTTPException(403, f"Missing permission: {perm}")
    Model = RESTORABLE[resource]
    rows = (
        db.query(Model)
        .execution_options(include_deleted=True)
        .filter(Model.is_deleted == True)  # noqa: E712
        .order_by(Model.deleted_at.desc())
        .limit(200)
        .all()
    )
    out = []
    for r in rows:
        item = {"id": r.id, "deleted_at": r.deleted_at}
        for attr in ("name", "title", "full_name", "slug", "email"):
            if hasattr(r, attr) and getattr(r, attr) is not None:
                item[attr] = getattr(r, attr)
                break
        out.append(item)
    return out


@router.post("/admin/trash/{resource}/{item_id}/restore")
def restore_item(
    resource: str,
    item_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if resource not in RESTORABLE:
        raise HTTPException(404, "Unknown resource")
    perm = PERM_FOR_RESTORE[resource]
    if perm and "*" not in user_perms(user) and perm not in user_perms(user):
        raise HTTPException(403, f"Missing permission: {perm}")
    Model = RESTORABLE[resource]
    # bypass the soft-delete filter so we can find a trashed row
    row = (
        db.query(Model)
        .execution_options(include_deleted=True)
        .filter(Model.id == item_id)
        .first()
    )
    if not row or not getattr(row, "is_deleted", False):
        raise HTTPException(404, "Not found in trash")
    row.is_deleted = False
    row.deleted_at = None
    log_activity(
        db,
        actor=user,
        action="restore",
        resource_type=resource,
        resource_id=item_id,
        request=request,
    )
    db.commit()
    return {"ok": True}


def user_perms(user: User) -> set[str]:
    from app.api.deps import user_permissions
    return user_permissions(user)
