from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, log_activity, user_permissions
from app.core.config import settings
from app.core.rate_limit import limiter
from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import get_db
from app.models import PasswordResetToken, User
from app.schemas.auth import LoginIn, MeOut, TokenOut
from app.services.email import send_email
from app.services.security_extras import (
    consume_recovery_code,
    hash_reset_token,
    is_locked,
    make_reset_token,
    register_failed_login,
    reset_failed_attempts,
    verify_totp,
)

router = APIRouter(prefix="/auth", tags=["auth"])


# ---------------- Login (with lockout + 2FA) ----------------

class TwoFactorLoginIn(BaseModel):
    email: EmailStr
    password: str
    totp_code: Optional[str] = None
    recovery_code: Optional[str] = None


@router.post("/login")
@limiter.limit(settings.RATE_LIMIT_LOGIN)
def login(payload: TwoFactorLoginIn, request: Request, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email.lower()).first()
    if not user:
        # Avoid disclosing which emails exist.
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")

    if user.is_deleted:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account is closed")

    if is_locked(user):
        retry_in = int((user.locked_until - datetime.now(timezone.utc)).total_seconds())
        raise HTTPException(
            status.HTTP_423_LOCKED,
            f"Account locked. Try again in {max(retry_in, 1)} seconds.",
        )

    if not verify_password(payload.password, user.password_hash):
        register_failed_login(user)
        log_activity(
            db,
            actor=None,
            action="login_failed",
            resource_type="auth",
            resource_id=user.id,
            request=request,
            details={"attempts": user.failed_login_attempts},
        )
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")

    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account disabled")

    # 2FA challenge if enabled
    if user.totp_enabled:
        if payload.recovery_code:
            ok, remaining = consume_recovery_code(user.totp_recovery_codes, payload.recovery_code)
            if not ok:
                register_failed_login(user)
                db.commit()
                raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid recovery code")
            user.totp_recovery_codes = remaining
        elif payload.totp_code:
            if not verify_totp(user.totp_secret or "", payload.totp_code):
                register_failed_login(user)
                db.commit()
                raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid 2FA code")
        else:
            # Tell the client to prompt for the second factor.
            return {"two_factor_required": True}

    reset_failed_attempts(user)
    log_activity(db, actor=user, action="login", resource_type="auth", request=request)
    db.commit()
    token = create_access_token(user.id)
    return TokenOut(access_token=token).model_dump()


@router.get("/me", response_model=MeOut)
def me(user: User = Depends(get_current_user)):
    perms = sorted(p for p in user_permissions(user) if p != "*")
    if any(p == "*" for p in user_permissions(user)):
        perms = ["*"]
    role_slug = user.role.slug if user.role else "staff"
    return MeOut(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=role_slug,
        department=user.department.name if user.department else None,
        permissions=perms,
        requires_2fa=role_slug in settings.REQUIRE_2FA_FOR_ROLES,
        has_2fa=bool(user.totp_enabled),
        must_reset_password=bool(user.must_reset_password),
    )


# ---------------- Forgot / reset password ----------------

class ForgotPasswordIn(BaseModel):
    email: EmailStr


class ResetPasswordIn(BaseModel):
    token: str
    new_password: str


@router.post("/forgot-password", status_code=202)
@limiter.limit(settings.RATE_LIMIT_PASSWORD_RESET)
def forgot_password(payload: ForgotPasswordIn, request: Request, db: Session = Depends(get_db)):
    """Always returns 202 to avoid disclosing which emails exist."""
    user = db.query(User).filter(User.email == payload.email.lower()).first()
    if user and user.is_active and not user.is_deleted:
        raw, hashed = make_reset_token()
        token_row = PasswordResetToken(
            user_id=user.id,
            token_hash=hashed,
            expires_at=datetime.now(timezone.utc)
            + timedelta(minutes=settings.PASSWORD_RESET_TTL_MINUTES),
        )
        db.add(token_row)
        log_activity(
            db,
            actor=user,
            action="password_reset_requested",
            resource_type="auth",
            resource_id=user.id,
            request=request,
        )
        db.commit()
        link = f"{settings.FRONTEND_URL}/admin/reset-password?token={raw}"
        try:
            send_email(
                to=user.email,
                subject="QUATA — reset your password",
                body=(
                    f"Hi {user.full_name},\n\n"
                    f"Use the link below to reset your QUATA password.\n"
                    f"It expires in {settings.PASSWORD_RESET_TTL_MINUTES} minutes.\n\n"
                    f"{link}\n\n"
                    f"If you didn't request this, you can ignore this email."
                ),
            )
        except Exception:  # noqa: BLE001
            pass
    return {"ok": True}


@router.post("/reset-password")
@limiter.limit(settings.RATE_LIMIT_PASSWORD_RESET)
def reset_password(payload: ResetPasswordIn, request: Request, db: Session = Depends(get_db)):
    if len(payload.new_password) < settings.PASSWORD_MIN_LENGTH:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Password must be at least {settings.PASSWORD_MIN_LENGTH} characters",
        )
    h = hash_reset_token(payload.token)
    row = db.query(PasswordResetToken).filter(PasswordResetToken.token_hash == h).first()
    if not row or row.used_at or row.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid or expired reset token")
    user = db.get(User, row.user_id)
    if not user or user.is_deleted or not user.is_active:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid or expired reset token")

    user.password_hash = hash_password(payload.new_password)
    user.must_reset_password = False
    reset_failed_attempts(user)
    row.used_at = datetime.now(timezone.utc)

    log_activity(
        db,
        actor=user,
        action="password_reset_completed",
        resource_type="auth",
        resource_id=user.id,
        request=request,
    )
    db.commit()
    return {"ok": True}
