"""Admin CRUD + public read for the site-settings store.

- `GET  /admin/site-settings`            list all (secrets are masked unless
                                          `include_secrets=true` is passed by
                                          someone with `settings:manage`)
- `PUT  /admin/site-settings/{key}`      update a single setting's value
- `POST /admin/site-settings/bulk`       update many settings in one call
- `GET  /site-settings`                  PUBLIC — non-secret values from
                                          the `contact` and `social` groups
                                          (used by the marketing footer).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, log_activity, require_permission
from app.db.session import get_db
from app.models import SiteSetting, User
from app.services.site_settings import (
    list_settings,
    public_settings_payload,
    set_setting,
)


router = APIRouter(tags=["site-settings"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class SettingOut(BaseModel):
    key: str
    value: Optional[str]
    group: str
    label: str
    description: Optional[str] = None
    field_type: str
    is_secret: bool
    sort_order: int
    has_value: bool

    @classmethod
    def from_row(cls, row: SiteSetting, *, mask_secrets: bool = True) -> "SettingOut":
        masked = mask_secrets and row.is_secret and bool(row.value)
        return cls(
            key=row.key,
            value=None if masked else row.value,
            group=row.group,
            label=row.label,
            description=row.description,
            field_type=row.field_type,
            is_secret=row.is_secret,
            sort_order=row.sort_order,
            has_value=bool(row.value),
        )


class SettingUpdateIn(BaseModel):
    value: Optional[str] = None


class BulkSettingItem(BaseModel):
    key: str
    value: Optional[str] = None


class BulkSettingsIn(BaseModel):
    items: list[BulkSettingItem]


# ---------------------------------------------------------------------------
# Public read
# ---------------------------------------------------------------------------

@router.get("/site-settings")
def public_site_settings(db: Session = Depends(get_db)):
    """Public — non-secret values from the `contact` and `social` groups,
    plus the maintenance toggle. Consumed by the marketing footer + contact
    page to render dynamic copy without a redeploy."""
    return public_settings_payload(db)


# ---------------------------------------------------------------------------
# Admin
# ---------------------------------------------------------------------------

@router.get("/admin/site-settings")
def admin_list_site_settings(
    group: Optional[str] = None,
    include_secrets: bool = Query(default=False),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("settings:manage")),
):
    rows = list_settings(db, group=group)
    return {
        "items": [SettingOut.from_row(r, mask_secrets=not include_secrets) for r in rows],
        "groups": sorted({r.group for r in rows}),
    }


@router.put("/admin/site-settings/{key}")
def admin_update_site_setting(
    key: str,
    payload: SettingUpdateIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("settings:manage")),
):
    try:
        row = set_setting(db, key=key, value=payload.value, updated_by_id=user.id)
    except ValueError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    log_activity(
        db,
        actor=user,
        action="update_setting",
        resource_type="site_setting",
        resource_id=row.key,
        request=request,
        details={"is_secret": row.is_secret, "had_value": bool(payload.value)},
    )
    db.commit()
    db.refresh(row)
    return SettingOut.from_row(row, mask_secrets=False)


@router.post("/admin/site-settings/test-hcaptcha")
def admin_test_hcaptcha(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("settings:manage")),
):
    """Verify the configured hCaptcha keys are reachable by hitting the
    siteverify endpoint with a dummy response token. A valid secret returns
    one of the well-known error codes (`missing-input-response` or
    `invalid-input-response`); an invalid secret returns
    `invalid-input-secret`. Either way we can tell the boss whether the
    secret is good."""
    import json
    import urllib.parse
    import urllib.request

    from app.services.site_settings import get_setting
    from app.core.config import settings as env_settings

    site = get_setting("integrations.hcaptcha_site_key", env_fallback=env_settings.HCAPTCHA_SITE_KEY) or ""
    secret = get_setting("integrations.hcaptcha_secret_key", env_fallback=env_settings.HCAPTCHA_SECRET_KEY) or ""

    if not site or not secret:
        return {
            "ok": False,
            "configured": False,
            "message": "Both site key and secret key must be set first.",
        }

    payload = {"secret": secret, "response": "test-only-not-a-real-token"}
    data = urllib.parse.urlencode(payload).encode("utf-8")
    req = urllib.request.Request("https://api.hcaptcha.com/siteverify", data=data)
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        log_activity(
            db, actor=user, action="hcaptcha_test", resource_type="site_setting",
            resource_id="hcaptcha", request=request,
            details={"ok": False, "error": str(exc)[:200]},
        )
        db.commit()
        return {
            "ok": False,
            "configured": True,
            "message": f"Couldn't reach hCaptcha: {exc}",
        }

    err_codes = body.get("error-codes") or []
    secret_invalid = "invalid-input-secret" in err_codes
    expected = (
        "missing-input-response" in err_codes
        or "invalid-input-response" in err_codes
        or body.get("success") is True
    )
    ok = expected and not secret_invalid

    log_activity(
        db, actor=user, action="hcaptcha_test", resource_type="site_setting",
        resource_id="hcaptcha", request=request,
        details={"ok": ok, "error_codes": err_codes},
    )
    db.commit()
    if secret_invalid:
        return {
            "ok": False,
            "configured": True,
            "message": "hCaptcha rejected the secret key as invalid. Double-check the value at hcaptcha.com.",
            "error_codes": err_codes,
        }
    if ok:
        return {
            "ok": True,
            "configured": True,
            "message": "hCaptcha keys are reachable and the secret is accepted. Public forms will enforce captcha within ~15 seconds.",
        }
    return {
        "ok": False,
        "configured": True,
        "message": f"Unexpected hCaptcha response. Error codes: {err_codes}",
        "error_codes": err_codes,
    }


@router.post("/admin/site-settings/test-sentry")
def admin_test_sentry(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("settings:manage")),
):
    """Send a one-off test event to Sentry using the configured DSN. Uses
    a temporary `Client`/`Hub` so the running process's global Sentry SDK
    state is unaffected (i.e. testing here doesn't accidentally route
    real errors through a half-configured client).
    """
    from app.services.site_settings import get_setting
    from app.core.config import settings as env_settings

    dsn = get_setting("integrations.sentry_dsn", env_fallback=env_settings.SENTRY_DSN)
    env = get_setting("integrations.sentry_env", env_fallback=env_settings.SENTRY_ENV or env_settings.ENVIRONMENT) or "production"

    if not dsn:
        return {
            "ok": False,
            "configured": False,
            "message": "Set the Sentry DSN first.",
        }

    # Basic format check before doing a network round-trip.
    if not (dsn.startswith("https://") and "@" in dsn and "/" in dsn.split("@", 1)[1]):
        return {
            "ok": False,
            "configured": True,
            "message": "DSN doesn't match the expected `https://<key>@<host>/<project>` shape.",
        }

    try:
        import sentry_sdk  # type: ignore
        from sentry_sdk import Client, Hub  # type: ignore
    except ImportError:
        return {
            "ok": False,
            "configured": True,
            "message": "sentry-sdk is not installed in the backend environment.",
        }

    try:
        client = Client(dsn=dsn, environment=env, send_default_pii=False)
        hub = Hub(client)
        with hub:
            event_id = sentry_sdk.capture_message(
                f"QUATA admin test event from {user.full_name}",
                level="info",
            )
        client.flush(timeout=5)
    except Exception as exc:  # noqa: BLE001
        log_activity(
            db, actor=user, action="sentry_test", resource_type="site_setting",
            resource_id="sentry", request=request,
            details={"ok": False, "error": str(exc)[:200]},
        )
        db.commit()
        return {
            "ok": False,
            "configured": True,
            "message": f"Sentry rejected the event: {exc}",
        }

    log_activity(
        db, actor=user, action="sentry_test", resource_type="site_setting",
        resource_id="sentry", request=request,
        details={"ok": True, "event_id": str(event_id) if event_id else None},
    )
    db.commit()
    return {
        "ok": True,
        "configured": True,
        "event_id": str(event_id) if event_id else None,
        "message": (
            "Test event accepted by Sentry. Check your project — it should appear within a minute. "
            "Note: a DSN change requires a backend restart for the running app's Sentry SDK to "
            "actually send real errors there (this test is one-off and doesn't reconfigure the live SDK)."
        ),
    }


@router.post("/admin/site-settings/test-email")
def admin_test_email(
    payload: dict,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("settings:manage")),
):
    """Send a sample email to verify the configured SMTP backend works. The
    boss pastes their own address, clicks Send test, and confirms it lands.
    Logged in the activity feed regardless of outcome."""
    from app.services.email import send_email

    target = (payload or {}).get("to", "").strip()
    if not target or "@" not in target:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Provide a valid email address in the 'to' field.",
        )
    subject = "QUATA — SMTP test email"
    body = (
        "This is a test email from the QUATA admin panel.\n\n"
        f"If you can read this, your SMTP configuration is working.\n\n"
        f"Triggered by: {user.full_name} <{user.email}>\n"
        f"At: {datetime.now(timezone.utc).isoformat()}\n"
    )
    ok = False
    err: Optional[str] = None
    try:
        ok = send_email(to=target, subject=subject, body=body)
    except Exception as exc:  # noqa: BLE001
        err = f"{type(exc).__name__}: {str(exc)[:240]}"

    log_activity(
        db,
        actor=user,
        action="smtp_test",
        resource_type="site_setting",
        resource_id="email",
        request=request,
        details={"to": target, "ok": ok, "error": err},
    )
    db.commit()
    if not ok:
        return {
            "ok": False,
            "error": err
            or "Email backend returned False — check EMAIL_BACKEND, SMTP host/credentials, or Mail provider status.",
        }
    return {"ok": True, "to": target}


@router.post("/admin/site-settings/bulk")
def admin_bulk_update_site_settings(
    payload: BulkSettingsIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("settings:manage")),
):
    """Update multiple keys in a single request. Useful when the admin form
    saves a whole tab at once. All-or-nothing — first invalid key aborts."""
    updated: list[str] = []
    for item in payload.items:
        try:
            set_setting(db, key=item.key, value=item.value, updated_by_id=user.id)
        except ValueError as exc:
            db.rollback()
            raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
        updated.append(item.key)
    log_activity(
        db,
        actor=user,
        action="bulk_update_settings",
        resource_type="site_setting",
        request=request,
        details={"keys": updated, "count": len(updated)},
    )
    db.commit()
    return {"updated": updated}
