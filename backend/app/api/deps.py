from typing import Annotated, Iterable

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.db.session import get_db
from app.models import User

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Session = Depends(get_db),
) -> User:
    if not creds or not creds.credentials:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing token")
    user_id = decode_token(creds.credentials)
    if not user_id:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")
    user = db.get(User, int(user_id))
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found or inactive")
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


def get_client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else ""


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
