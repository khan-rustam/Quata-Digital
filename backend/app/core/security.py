"""Password hashing + JWT signing.

The JWT library is PyJWT (maintained). ``python-jose`` was unmaintained
and accumulated two unfixed CVEs in 2024.

Tokens carry a ``pwc`` claim (password-changed timestamp) so a password
change immediately invalidates every token issued before it — no
session table required.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt
from jwt.exceptions import InvalidTokenError

from .config import settings


def hash_password(password: str) -> str:
    pw = password.encode("utf-8")[:72]  # bcrypt max input length
    return bcrypt.hashpw(pw, bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    try:
        pw = password.encode("utf-8")[:72]
        return bcrypt.checkpw(pw, hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_access_token(
    subject: str | int,
    expires_minutes: int | None = None,
    *,
    password_changed_at: datetime | None = None,
) -> str:
    """Mint a JWT for ``subject``.

    ``password_changed_at`` is folded into the payload as ``pwc`` so a
    server-side comparison can reject tokens that were issued before a
    password change (token invalidation without a session table).
    """
    now = datetime.now(timezone.utc)
    expire = now + timedelta(
        minutes=expires_minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload: dict[str, Any] = {
        "sub": str(subject),
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    if password_changed_at is not None:
        payload["pwc"] = int(password_changed_at.timestamp())
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> str | None:
    """Return the ``sub`` claim, or ``None`` if the token is invalid."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload.get("sub")
    except InvalidTokenError:
        return None


def decode_token_full(token: str) -> dict | None:
    """Return the full decoded payload, or ``None`` if invalid."""
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except InvalidTokenError:
        return None
