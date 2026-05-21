from ipaddress import ip_address, ip_network
from typing import Annotated, Iterable

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import decode_token, decode_token_full
from app.db.session import get_db
from app.models import User

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user_lenient(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Session = Depends(get_db),
) -> User:
    """Authenticated user without the post-login compliance gates.

    Use this dependency only for the endpoints a user must reach *while*
    completing required setup (changing the seeded password, enrolling
    TOTP, viewing their own profile). Everything else should use
    ``get_current_user`` so the gates are enforced server-side.
    """
    if not creds or not creds.credentials:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing token")
    payload = decode_token_full(creds.credentials)
    if not payload or not payload.get("sub"):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")
    user = db.get(User, int(payload["sub"]))
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found or inactive")
    # Reject tokens issued before the last password change. Lets us
    # invalidate every active session of a user as a side-effect of
    # changing/resetting their password, without a session-store table.
    if user.password_changed_at:
        pwc = payload.get("pwc")
        if pwc is None or int(pwc) < int(user.password_changed_at.timestamp()):
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED, "Token superseded by password change"
            )
    return user


def get_current_user(
    user: User = Depends(get_current_user_lenient),
) -> User:
    """Authenticated user with compliance gates enforced.

    Rejects requests when:
    * ``must_reset_password`` is true (seeded password still in place);
    * the user's role is listed in ``REQUIRE_2FA_FOR_ROLES`` but TOTP has
      not yet been enrolled.

    The 403 carries a structured ``reason`` so the frontend can route to
    the right step instead of treating it as a generic auth failure.
    """
    if user.must_reset_password:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "password_reset_required",
        )
    role_slug = user.role.slug if user.role else "staff"
    if role_slug in settings.REQUIRE_2FA_FOR_ROLES and not user.totp_enabled:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "two_factor_enrolment_required",
        )
    return user


def user_permissions(user: User) -> set[str]:
    perms = {p.permission for p in user.role.permissions} if user.role else set()
    if user.role and user.role.slug == "super_admin":
        perms.add("*")
    return perms


def require_permission(*required: str):
    def _check(user: User = Depends(get_current_user)) -> User:
        perms = user_permissions(user)
        if "*" in perms:
            return user
        if not any(r in perms for r in required):
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"Missing permission: {required}")
        return user

    return _check


def _parse_trusted_networks() -> list:
    """Parse ``settings.TRUSTED_PROXIES`` into ip_network objects once."""
    nets = []
    for cidr in settings.TRUSTED_PROXIES:
        try:
            nets.append(ip_network(cidr, strict=False))
        except ValueError:
            continue
    return nets


_TRUSTED_PROXY_NETS = _parse_trusted_networks()


def _is_trusted_proxy(host: str) -> bool:
    if not host:
        return False
    try:
        addr = ip_address(host)
    except ValueError:
        return False
    return any(addr in net for net in _TRUSTED_PROXY_NETS)


def get_client_ip(request: Request) -> str:
    """Return the real client IP, only honouring XFF behind a trusted hop.

    Blindly trusting ``X-Forwarded-For`` lets any direct caller spoof the
    audit-log IP and defeat slowapi's IP bucketing. We only consume the
    header when the immediate socket peer is in ``TRUSTED_PROXIES``.
    """
    socket_host = request.client.host if request.client else ""
    if _is_trusted_proxy(socket_host):
        fwd = request.headers.get("x-forwarded-for")
        if fwd:
            return fwd.split(",")[0].strip()
    return socket_host


def log_activity(
    db: Session,
    *,
    actor: User | None,
    action: str,
    resource_type: str,
    resource_id: str | int | None = None,
    request: Request | None = None,
    details: dict | None = None,
):
    from app.models import ActivityLog
    log = ActivityLog(
        actor_id=actor.id if actor else None,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id is not None else None,
        ip_address=get_client_ip(request) if request else None,
        user_agent=(request.headers.get("user-agent") if request else None),
        details=details or {},
    )
    db.add(log)
