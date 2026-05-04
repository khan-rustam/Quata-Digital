"""Security helpers: TOTP, password-reset tokens, account lockout, HMAC verification."""
from __future__ import annotations

import base64
import hashlib
import hmac
import io
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

import pyotp
import qrcode

from app.core.config import settings
from app.core.security import hash_password


# ---------------- Account lockout ----------------

def is_locked(user) -> bool:
    if not user.locked_until:
        return False
    return user.locked_until > datetime.now(timezone.utc)


def register_failed_login(user) -> None:
    user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
    if user.failed_login_attempts >= settings.MAX_LOGIN_ATTEMPTS:
        user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=settings.LOCKOUT_MINUTES)


def reset_failed_attempts(user) -> None:
    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login_at = datetime.now(timezone.utc)


# ---------------- Password reset tokens ----------------

def make_reset_token() -> tuple[str, str]:
    """Returns (raw_token_for_link, hashed_token_to_store)."""
    raw = secrets.token_urlsafe(48)
    h = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return raw, h


def hash_reset_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# ---------------- TOTP / 2FA ----------------

def new_totp_secret() -> str:
    return pyotp.random_base32()


def totp_uri(secret: str, account_name: str) -> str:
    return pyotp.totp.TOTP(secret).provisioning_uri(name=account_name, issuer_name=settings.TOTP_ISSUER)


def totp_qr_data_url(uri: str) -> str:
    """Returns a data: URL with an SVG QR code (no Pillow dependency)."""
    from qrcode.image.svg import SvgImage  # type: ignore
    qr = qrcode.QRCode(box_size=8, border=2)
    qr.add_data(uri)
    qr.make(fit=True)
    img = qr.make_image(image_factory=SvgImage)
    buf = io.BytesIO()
    img.save(buf)
    encoded = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"


def verify_totp(secret: str, code: str) -> bool:
    if not secret or not code:
        return False
    code = code.strip().replace(" ", "")
    return pyotp.TOTP(secret).verify(code, valid_window=1)


def make_recovery_codes(n: int = 8) -> list[str]:
    """One-time codes a user can keep offline. Stored hashed."""
    return [secrets.token_hex(5).upper() for _ in range(n)]


def hash_recovery_code(code: str) -> str:
    return hashlib.sha256(code.upper().strip().encode()).hexdigest()


def consume_recovery_code(stored: list[str] | None, attempt: str) -> tuple[bool, list[str]]:
    if not stored:
        return False, stored or []
    h = hash_recovery_code(attempt)
    if h in stored:
        new = [c for c in stored if c != h]
        return True, new
    return False, stored


# ---------------- HMAC for device webhook ----------------

def verify_device_hmac(*, secret: str, timestamp: str | None, signature: str | None, body: bytes) -> bool:
    if not signature or not timestamp or not secret:
        return False
    try:
        ts = int(timestamp)
    except ValueError:
        return False
    if abs(time.time() - ts) > settings.DEVICE_HMAC_SKEW_SECONDS:
        return False
    payload = f"{ts}.".encode("utf-8") + body
    expected = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)
