from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import ForeignKey, String, Boolean, JSON, Integer, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, SoftDeleteMixin


class Department(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "departments"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    head_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", use_alter=True, name="fk_dept_head"), nullable=True
    )

    head: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[head_id], post_update=True
    )
    members: Mapped[List["User"]] = relationship(
        "User", back_populates="department", foreign_keys="User.department_id"
    )


class Role(Base, TimestampMixin):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[Optional[str]] = mapped_column(String(500))

    permissions: Mapped[List["RolePermission"]] = relationship(
        "RolePermission", back_populates="role", cascade="all, delete-orphan"
    )


class RolePermission(Base):
    __tablename__ = "role_permissions"

    id: Mapped[int] = mapped_column(primary_key=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id", ondelete="CASCADE"))
    permission: Mapped[str] = mapped_column(String(80), index=True)

    role: Mapped[Role] = relationship("Role", back_populates="permissions")


class User(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(160))
    job_title: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    avatar_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active")  # active|invited|suspended
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    biometric_id: Mapped[Optional[str]] = mapped_column(String(80), nullable=True, index=True)

    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"))
    department_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("departments.id", use_alter=True, name="fk_user_dept"), nullable=True
    )

    # --- Account security ---
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # --- 2FA ---
    # Stored Fernet-encrypted (see security_extras.encrypt_totp_secret); the
    # ciphertext is longer than the raw base32 secret, hence 255.
    totp_secret: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    totp_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    totp_recovery_codes: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    # Forces the user to set a new password before any other admin action
    # is allowed. Set on invitation and on the seeded super admin.
    must_reset_password: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    # Wall-clock timestamp of the last password change. Folded into the
    # JWT as ``pwc``; tokens issued before this point are rejected, so
    # changing a password (or admin-resetting one) revokes every active
    # session without needing a server-side session table.
    password_changed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # --- Notification prefs (JSON for flexibility) ---
    notification_prefs: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    role: Mapped[Role] = relationship("Role")
    department: Mapped[Optional[Department]] = relationship(
        "Department", back_populates="members", foreign_keys=[department_id]
    )

    extra: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)


class PasswordResetToken(Base):
    """Single-use, short-lived tokens for password reset flow."""
    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(128), index=True, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
