"""Rate-limiting wrapper around slowapi.

Use `limiter` as a dependency-style decorator on routes:

    from app.core.rate_limit import limiter
    from app.core.config import settings

    @router.post(\"/login\")
    @limiter.limit(settings.RATE_LIMIT_LOGIN)
    def login(request: Request, ...):
        ...
"""
from __future__ import annotations

from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.security import decode_token


def _key_user_or_ip(request: Request) -> str:
    """Auth-aware rate-limit key.

    Authenticated requests bucket by user id (`u:<id>`) so a shared
    office IP doesn't penalise individual admins. Anonymous requests
    fall back to remote address (`ip:<addr>`).
    """
    auth = request.headers.get("authorization") or ""
    if auth.lower().startswith("bearer "):
        token = auth.split(" ", 1)[1].strip()
        try:
            user_id = decode_token(token)
            if user_id:
                return f"u:{user_id}"
        except Exception:  # noqa: BLE001
            pass
    return f"ip:{get_remote_address(request)}"


# When REDIS_URL is set, share rate-limit state across uvicorn workers and
# replicas. Otherwise the limiter is per-process — fine for a single worker
# on one VPS, hazardous beyond that. See docs/SCALING.md.
_kwargs: dict = {"key_func": _key_user_or_ip, "default_limits": []}
if settings.REDIS_URL:
    _kwargs["storage_uri"] = settings.REDIS_URL

limiter = Limiter(**_kwargs)


def rate_limit_handler(_request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": "Too many requests — slow down."},
        headers={"Retry-After": str(int(exc.detail.split("/")[-1] if "/" in str(exc.detail) else 60))},
    )
