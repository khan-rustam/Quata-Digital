from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, log_activity
from app.core.security import hash_password, verify_password
from app.db.session import get_db
from app.models import AttendanceLog, LeaveRequest, User
from app.schemas.common import (
    AttendanceIn,
    AttendanceOut,
    LeaveIn,
    LeaveOut,
)

router = APIRouter(tags=["self-service"])


# ---------- Profile / password ----------

class ProfileUpdate(BaseModel):
    full_name: str | None = None
    phone: str | None = None
    avatar_url: str | None = None
    job_title: str | None = None


class PasswordChange(BaseModel):
    current_password: str
    new_password: str


@router.patch("/me")
def update_profile(
    payload: ProfileUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(user, k, v)
    log_activity(
        db,
        actor=user,
        action="update_profile",
        resource_type="user",
        resource_id=user.id,
        request=request,
        details={"fields": list(data.keys())},
    )
    db.commit()
    db.refresh(user)
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "phone": user.phone,
        "job_title": user.job_title,
        "avatar_url": user.avatar_url,
    }


@router.post("/me/password")
def change_password(
    payload: PasswordChange,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Current password is incorrect")
    if len(payload.new_password) < 10:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Password must be at least 10 characters")
    user.password_hash = hash_password(payload.new_password)
    user.must_reset_password = False
    log_activity(
        db,
        actor=user,
        action="change_password",
        resource_type="user",
        resource_id=user.id,
        request=request,
    )
    db.commit()
    return {"ok": True}


# ---------- Leave / Attendance (existing) ----------

@router.post("/leave", response_model=LeaveOut, status_code=201)
def create_leave(
    payload: LeaveIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if payload.end_date < payload.start_date:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "end_date must be on or after start_date")
    days = (payload.end_date - payload.start_date).days + 1
    lr = LeaveRequest(
        user_id=user.id,
        leave_type=payload.leave_type,
        start_date=payload.start_date,
        end_date=payload.end_date,
        days=days,
        reason=payload.reason,
        status="pending",
    )
    db.add(lr)
    db.flush()
    log_activity(
        db,
        actor=user,
        action="apply_leave",
        resource_type="leave_request",
        resource_id=lr.id,
        request=request,
    )
    db.commit()
    db.refresh(lr)
    return LeaveOut(
        id=lr.id,
        staff_name=user.full_name,
        leave_type=lr.leave_type,
        start_date=lr.start_date,
        end_date=lr.end_date,
        days=lr.days,
        status=lr.status,
        reason=lr.reason,
    )


@router.post("/attendance/in", response_model=AttendanceOut)
def check_in(
    payload: AttendanceIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    existing = (
        db.query(AttendanceLog)
        .filter(AttendanceLog.user_id == user.id)
        .filter(AttendanceLog.check_in_at.isnot(None))
        .filter(AttendanceLog.check_out_at.is_(None))
        .first()
    )
    if existing:
        return AttendanceOut(
            id=existing.id,
            staff_name=user.full_name,
            check_in_at=existing.check_in_at,
            check_out_at=existing.check_out_at,
            source=existing.source,
            device_name=existing.device.name if existing.device else None,
            status=existing.status,
        )
    log = AttendanceLog(
        user_id=user.id,
        check_in_at=datetime.now(timezone.utc),
        source=payload.source,
        device_id=payload.device_id,
        latitude=payload.latitude,
        longitude=payload.longitude,
        status="present",
    )
    db.add(log)
    db.flush()
    log_activity(
        db,
        actor=user,
        action="check_in",
        resource_type="attendance",
        resource_id=log.id,
        request=request,
    )
    db.commit()
    db.refresh(log)
    return AttendanceOut(
        id=log.id,
        staff_name=user.full_name,
        check_in_at=log.check_in_at,
        check_out_at=log.check_out_at,
        source=log.source,
        device_name=None,
        status=log.status,
    )


@router.post("/attendance/out", response_model=AttendanceOut)
def check_out(
    payload: AttendanceIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    log = (
        db.query(AttendanceLog)
        .filter(AttendanceLog.user_id == user.id)
        .filter(AttendanceLog.check_out_at.is_(None))
        .order_by(AttendanceLog.check_in_at.desc())
        .first()
    )
    if not log:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No active check-in to close")
    log.check_out_at = datetime.now(timezone.utc)
    log_activity(
        db,
        actor=user,
        action="check_out",
        resource_type="attendance",
        resource_id=log.id,
        request=request,
    )
    db.commit()
    db.refresh(log)
    return AttendanceOut(
        id=log.id,
        staff_name=user.full_name,
        check_in_at=log.check_in_at,
        check_out_at=log.check_out_at,
        source=log.source,
        device_name=log.device.name if log.device else None,
        status=log.status,
    )
