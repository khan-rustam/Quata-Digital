"""HMAC-signed unsubscribe tokens for newsletter broadcasts.

A subscriber's token is deterministic: HMAC-SHA256(SECRET_KEY, "unsubscribe:" + email).
Truncated to 24 hex chars for URL friendliness — collision space is still
~10^28 which is plenty.

Why HMAC instead of a stored token column:
  - No schema change needed.
  - No leakage if the table is dumped — the token is reproducible from
    SECRET_KEY + email, so it isn't sensitive on its own.
  - Easy to invalidate everyone's links at once: rotate SECRET_KEY.
"""
from __future__ import annotations

import hashlib
import hmac
from urllib.parse import urlencode

from app.core.config import settings


_TOKEN_LEN = 24
_PREFIX = "unsubscribe:"


def make_unsubscribe_token(email: str) -> str:
    msg = (_PREFIX + email.lower().strip()).encode("utf-8")
    sig = hmac.new(
        settings.SECRET_KEY.encode("utf-8"), msg, hashlib.sha256
    ).hexdigest()
    return sig[:_TOKEN_LEN]


def verify_unsubscribe_token(email: str, token: str) -> bool:
    if not token or len(token) != _TOKEN_LEN:
        return False
    expected = make_unsubscribe_token(email)
    return hmac.compare_digest(expected, token)


def unsubscribe_url_for(email: str) -> str:
    """Returns the public one-click unsubscribe URL for a subscriber."""
    base = settings.FRONTEND_URL.rstrip("/")
    qs = urlencode({"email": email.lower().strip(), "token": make_unsubscribe_token(email)})
    return f"{base}/unsubscribe?{qs}"
