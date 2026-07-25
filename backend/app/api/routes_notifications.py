"""QUATA Notification Service — HTTP surface.

Two audiences, deliberately separated:

**Platforms** (`POST /notify/events`) — QuataPay, QuataFood, Abaqwa,
QuataTrade and QUATA AI publish business events here with a per-platform
ingest key. They never touch Telegram themselves; adding a sixth platform is
a new key in `NOTIFY_INGEST_KEYS`, not a code change.

**Administrators** (`/admin/alerts/*`) — the Notification Settings console:
toggles, thresholds, recipients, delivery logs, retries and a test send. All
gated on ``settings:manage``.

Note the admin prefix is ``/admin/alerts``, not ``/admin/notifications`` —
that path already serves the HR "needs attention" feed.
"""
from __future__ import annotations

import hashlib
import hmac
import time
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_client_ip, log_activity, require_permission
from app.core.config import settings as env_settings
from app.core.rate_limit import limiter
from app.db.session import get_db
from app.models import NotificationEvent, NotificationRecipient, User
from app.services.notifications import catalog, dispatch, digest, settings_store, telegram
from app.services.notifications.recipients import recipients_for


router = APIRouter(tags=["notifications"])


# ---------------------------------------------------------------------------
# Ingest — used by every QUATA platform outside this repository
# ---------------------------------------------------------------------------

class EventIn(BaseModel):
    """One published event.

    ``event`` is a catalogue key (``deposit.successful``). Unknown keys are
    accepted and categorised by namespace so a platform can ship an event
    before the catalogue catches up.
    """

    event: str = Field(..., min_length=3, max_length=100)
    platform: Optional[str] = Field(default=None, max_length=40)
    payload: dict[str, Any] = Field(default_factory=dict)
    reference: Optional[str] = Field(default=None, max_length=160)
    priority: Optional[str] = Field(default=None, max_length=20)
    status: Optional[str] = Field(default=None, max_length=40)
    # Publisher-supplied idempotency key. Strongly recommended — it is what
    # makes an at-least-once delivery pipeline safe to retry.
    dedupe_key: Optional[str] = Field(default=None, max_length=200)
    occurred_at: Optional[datetime] = None


class EventBatchIn(BaseModel):
    events: list[EventIn] = Field(..., min_length=1, max_length=50)


def _authenticate_platform(
    *,
    raw_body: bytes,
    platform_header: Optional[str],
    key_header: Optional[str],
    signature: Optional[str],
    timestamp: Optional[str],
) -> str:
    """Resolve and verify the publishing platform. Returns its slug."""
    configured = env_settings.notify_ingest_keys
    if not configured:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Event ingest is not configured. Set NOTIFY_INGEST_KEYS.",
        )

    slug = (platform_header or "").strip().lower()
    expected = configured.get(slug)
    # Constant-time compare, and only after we know a key exists — an
    # unknown platform and a wrong key must be indistinguishable.
    if not slug or not expected or not key_header or not hmac.compare_digest(expected, key_header):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid platform credentials")

    if env_settings.NOTIFY_REQUIRE_SIGNATURE:
        if not signature or not timestamp:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing request signature")
        try:
            sent_at = int(timestamp)
        except ValueError:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid signature timestamp") from None
        if abs(time.time() - sent_at) > env_settings.NOTIFY_SIGNATURE_SKEW_SECONDS:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Signature timestamp out of range")
        message = f"{sent_at}.".encode("utf-8") + raw_body
        digest_hex = hmac.new(expected.encode("utf-8"), message, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(digest_hex, signature):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid request signature")

    return slug


@router.post("/notify/events", status_code=202)
@limiter.limit("300/minute")
async def ingest_events(
    request: Request,
    x_quata_platform: Optional[str] = Header(default=None, alias="X-Quata-Platform"),
    x_quata_key: Optional[str] = Header(default=None, alias="X-Quata-Key"),
    x_quata_signature: Optional[str] = Header(default=None, alias="X-Quata-Signature"),
    x_quata_timestamp: Optional[str] = Header(default=None, alias="X-Quata-Timestamp"),
):
    """Publish one or more events to the notification service.

    Accepts either a single event object or ``{"events": [...]}``. Returns
    202 with an ``event_id`` per accepted event — the caller never waits for
    Telegram.
    """
    raw_body = await request.body()
    platform = _authenticate_platform(
        raw_body=raw_body,
        platform_header=x_quata_platform,
        key_header=x_quata_key,
        signature=x_quata_signature,
        timestamp=x_quata_timestamp,
    )

    try:
        batch = EventBatchIn.model_validate_json(raw_body)
        events = batch.events
    except Exception:  # noqa: BLE001 — fall back to the single-event shape
        try:
            events = [EventIn.model_validate_json(raw_body)]
        except Exception:  # noqa: BLE001
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Body must be an event object or {\"events\": [...]}.",
            ) from None

    source_ip = get_client_ip(request)
    accepted: list[dict] = []
    for item in events:
        # A platform may only publish as itself. Ignoring the body's
        # `platform` field stops QuataFood's key from forging a QuataPay
        # financial alert.
        event_id = dispatch.emit(
            item.event,
            platform=platform,
            payload=item.payload,
            reference=item.reference,
            priority=item.priority,
            status=item.status,
            dedupe_key=item.dedupe_key,
            occurred_at=item.occurred_at,
            source_ip=source_ip,
        )
        accepted.append({"event": item.event, "event_id": event_id, "accepted": bool(event_id)})

    return {"ok": True, "platform": platform, "results": accepted}


@router.get("/notify/health")
def ingest_health():
    """Unauthenticated liveness check for platform integrations.

    Says whether the service is accepting events — deliberately reveals no
    configuration detail beyond that.
    """
    return {
        "service": "quata-notification-service",
        "accepting_events": bool(env_settings.notify_ingest_keys),
        "delivery_enabled": settings_store.service_enabled(),
    }


# ---------------------------------------------------------------------------
# Admin — settings
# ---------------------------------------------------------------------------

class SettingOut(BaseModel):
    key: str
    value: Optional[str]
    group: str
    label: str
    description: Optional[str] = None
    field_type: str
    sort_order: int


class BulkSettingItem(BaseModel):
    key: str
    value: Optional[str] = None


class BulkSettingsIn(BaseModel):
    items: list[BulkSettingItem]


@router.get("/admin/alerts/settings")
def admin_alert_settings(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("settings:manage")),
):
    """Everything the Notification Settings page needs in one call."""
    rows = settings_store.list_settings(db)
    bot = telegram.get_me() if telegram.is_configured() else {"ok": False, "configured": False}
    return {
        "items": [
            SettingOut(
                key=r.key,
                value=r.value,
                group=r.group,
                label=r.label,
                description=r.description,
                field_type=r.field_type,
                sort_order=r.sort_order,
            )
            for r in rows
        ],
        "groups": sorted({r.group for r in rows}),
        "bot": bot,
        "env_kill_switch": not env_settings.NOTIFY_ENABLED,
        "delivery_enabled": settings_store.service_enabled(),
        "platforms": [
            {"slug": s.slug, "name": s.name, "description": s.description}
            for s in catalog.PLATFORMS.values()
        ],
        "categories": [
            {"slug": c.slug, "name": c.name, "description": c.description}
            for c in catalog.CATEGORIES.values()
        ],
        "priorities": [
            {"slug": p, "label": catalog.PRIORITY_BADGE[p]} for p in catalog.PRIORITY_ORDER
        ],
        "configured_platform_keys": sorted(env_settings.notify_ingest_keys.keys()),
        "stats": dispatch.stats(db),
    }


@router.post("/admin/alerts/settings/bulk")
def admin_update_alert_settings(
    payload: BulkSettingsIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("settings:manage")),
):
    """Update many toggles at once. All-or-nothing on an unknown key."""
    updated: list[str] = []
    for item in payload.items:
        try:
            settings_store.set_value(db, key=item.key, value=item.value, updated_by_id=user.id)
        except ValueError as exc:
            db.rollback()
            raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
        updated.append(item.key)
    log_activity(
        db,
        actor=user,
        action="update_alert_settings",
        resource_type="notification_setting",
        request=request,
        details={"keys": updated, "count": len(updated)},
    )
    db.commit()
    settings_store.invalidate()
    return {"updated": updated}


# ---------------------------------------------------------------------------
# Admin — recipients
# ---------------------------------------------------------------------------

class RecipientIn(BaseModel):
    chat_id: str = Field(..., min_length=1, max_length=40)
    label: str = Field(..., min_length=1, max_length=120)
    is_active: bool = True
    min_priority: str = Field(default="info", max_length=20)
    platforms: list[str] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)


class RecipientUpdateIn(BaseModel):
    label: Optional[str] = Field(default=None, max_length=120)
    is_active: Optional[bool] = None
    min_priority: Optional[str] = Field(default=None, max_length=20)
    platforms: Optional[list[str]] = None
    categories: Optional[list[str]] = None


def _recipient_out(row: NotificationRecipient) -> dict:
    return {
        "id": row.id,
        "chat_id": row.chat_id,
        "label": row.label,
        "is_active": row.is_active,
        "is_group": row.is_group,
        "min_priority": row.min_priority,
        "platforms": row.platforms or [],
        "categories": row.categories or [],
        "last_ok_at": row.last_ok_at,
        "last_error": row.last_error,
        "created_at": row.created_at,
    }


def _validate_filters(payload_platforms: Optional[list], payload_categories: Optional[list]) -> None:
    """Reject filters that reference something that doesn't exist — silently
    accepting a typo would quietly stop a recipient receiving anything."""
    for slug in payload_platforms or []:
        if slug not in catalog.PLATFORMS:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unknown platform: {slug}")
    for slug in payload_categories or []:
        if slug not in catalog.CATEGORIES:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unknown category: {slug}")


@router.get("/admin/alerts/recipients")
def admin_list_recipients(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("settings:manage")),
):
    rows = db.query(NotificationRecipient).order_by(NotificationRecipient.id).all()
    return {"items": [_recipient_out(r) for r in rows]}


@router.post("/admin/alerts/recipients", status_code=201)
def admin_create_recipient(
    payload: RecipientIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("settings:manage")),
):
    chat_id = payload.chat_id.strip()
    if payload.min_priority not in catalog.PRIORITY_ORDER:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown priority")
    _validate_filters(payload.platforms, payload.categories)
    if db.query(NotificationRecipient).filter(NotificationRecipient.chat_id == chat_id).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "That Telegram chat is already a recipient")

    row = NotificationRecipient(
        chat_id=chat_id,
        label=payload.label.strip(),
        is_active=payload.is_active,
        is_group=chat_id.startswith("-"),
        min_priority=payload.min_priority,
        platforms=payload.platforms,
        categories=payload.categories,
        created_by_id=user.id,
    )
    db.add(row)
    db.flush()
    log_activity(
        db,
        actor=user,
        action="add_alert_recipient",
        resource_type="notification_recipient",
        resource_id=row.id,
        request=request,
        # The chat id is an authorisation grant — record it in the audit log.
        details={"chat_id": chat_id, "label": row.label},
    )
    db.commit()
    db.refresh(row)
    return _recipient_out(row)


@router.put("/admin/alerts/recipients/{recipient_id}")
def admin_update_recipient(
    recipient_id: int,
    payload: RecipientUpdateIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("settings:manage")),
):
    row = db.get(NotificationRecipient, recipient_id)
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Recipient not found")
    if payload.min_priority is not None and payload.min_priority not in catalog.PRIORITY_ORDER:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown priority")
    _validate_filters(payload.platforms, payload.categories)

    for field in ("label", "is_active", "min_priority", "platforms", "categories"):
        value = getattr(payload, field)
        if value is not None:
            setattr(row, field, value)
    log_activity(
        db,
        actor=user,
        action="update_alert_recipient",
        resource_type="notification_recipient",
        resource_id=row.id,
        request=request,
        details={"chat_id": row.chat_id, "is_active": row.is_active},
    )
    db.commit()
    db.refresh(row)
    return _recipient_out(row)


@router.delete("/admin/alerts/recipients/{recipient_id}", status_code=204)
def admin_delete_recipient(
    recipient_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("settings:manage")),
):
    row = db.get(NotificationRecipient, recipient_id)
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Recipient not found")
    log_activity(
        db,
        actor=user,
        action="remove_alert_recipient",
        resource_type="notification_recipient",
        resource_id=row.id,
        request=request,
        details={"chat_id": row.chat_id, "label": row.label},
    )
    db.delete(row)
    db.commit()
    return None


# ---------------------------------------------------------------------------
# Admin — test, logs, retries
# ---------------------------------------------------------------------------

@router.post("/admin/alerts/test")
def admin_send_test(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("settings:manage")),
):
    """Push a real notification end-to-end and report what happened."""
    matched = recipients_for(db, platform="quata_digital", category="website", priority="warning")
    if not matched:
        return {
            "ok": False,
            "error": "No active recipient matches a test alert. Add a Telegram chat id first.",
        }

    result = dispatch.send_test(triggered_by=user.full_name)
    log_activity(
        db,
        actor=user,
        action="test_alert",
        resource_type="notification_event",
        resource_id=result.get("event_id"),
        request=request,
        details={"ok": bool(result.get("ok")), "error": result.get("error")},
    )
    db.commit()
    return result


@router.get("/admin/alerts/bot")
def admin_bot_status(
    user: User = Depends(require_permission("settings:manage")),
):
    """Ask Telegram to identify the configured bot."""
    return telegram.get_me()


@router.get("/admin/alerts/logs")
def admin_alert_logs(
    platform: Optional[str] = None,
    category: Optional[str] = None,
    event_status: Optional[str] = Query(default=None, alias="status"),
    priority: Optional[str] = None,
    q: Optional[str] = Query(default=None, max_length=120),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("settings:manage")),
):
    """Paginated delivery log — the complete audit trail of every alert."""
    query = db.query(NotificationEvent)
    if platform:
        query = query.filter(NotificationEvent.platform == platform)
    if category:
        query = query.filter(NotificationEvent.category == category)
    if event_status:
        query = query.filter(NotificationEvent.status == event_status)
    if priority:
        query = query.filter(NotificationEvent.priority == priority)
    if q:
        needle = f"%{q.lower()}%"
        from sqlalchemy import func, or_

        query = query.filter(
            or_(
                func.lower(NotificationEvent.title).like(needle),
                func.lower(NotificationEvent.event_key).like(needle),
                func.lower(NotificationEvent.reference).like(needle),
            )
        )

    total = query.count()
    rows = (
        query.order_by(NotificationEvent.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "event_id": r.event_id,
                "platform": r.platform,
                "platform_name": catalog.platform_name(r.platform),
                "event_key": r.event_key,
                "category": r.category,
                "category_name": catalog.category_name(r.category),
                "priority": r.priority,
                "priority_label": catalog.PRIORITY_BADGE.get(r.priority, r.priority),
                "status": r.status,
                "title": r.title,
                "reference": r.reference,
                "attempts": r.attempts,
                "max_attempts": r.max_attempts,
                "last_error": r.last_error,
                "suppressed_reason": r.suppressed_reason,
                "sent_at": r.sent_at,
                "created_at": r.created_at,
                "recipients": len(r.delivery or []),
            }
            for r in rows
        ],
        "stats": dispatch.stats(db),
    }


@router.get("/admin/alerts/logs/{event_id}")
def admin_alert_detail(
    event_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("settings:manage")),
):
    row = (
        db.query(NotificationEvent)
        .filter(NotificationEvent.event_id == event_id)
        .first()
    )
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Notification not found")
    return {
        "event_id": row.event_id,
        "platform": row.platform,
        "platform_name": catalog.platform_name(row.platform),
        "event_key": row.event_key,
        "category": row.category,
        "priority": row.priority,
        "status": row.status,
        "title": row.title,
        "reference": row.reference,
        # Already redacted at ingest — safe to show.
        "payload": row.payload,
        "message": row.message,
        "delivery": row.delivery or [],
        "attempts": row.attempts,
        "max_attempts": row.max_attempts,
        "last_error": row.last_error,
        "suppressed_reason": row.suppressed_reason,
        "next_attempt_at": row.next_attempt_at,
        "sent_at": row.sent_at,
        "created_at": row.created_at,
        "source_ip": row.source_ip,
    }


@router.post("/admin/alerts/logs/{event_id}/retry")
def admin_retry_alert(
    event_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("settings:manage")),
):
    result = dispatch.retry_event(event_id)
    log_activity(
        db,
        actor=user,
        action="retry_alert",
        resource_type="notification_event",
        resource_id=event_id,
        request=request,
        details={"ok": bool(result.get("ok"))},
    )
    db.commit()
    if result.get("error") == "Event not found":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Notification not found")
    return result


@router.post("/admin/alerts/retry-failed")
def admin_retry_failed(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("settings:manage")),
):
    result = dispatch.retry_failed(limit=limit)
    log_activity(
        db,
        actor=user,
        action="retry_failed_alerts",
        resource_type="notification_event",
        request=request,
        details=result,
    )
    db.commit()
    return result


# ---------------------------------------------------------------------------
# Admin — daily summary
# ---------------------------------------------------------------------------

@router.get("/admin/alerts/digest/preview")
def admin_digest_preview(
    hours: int = Query(default=24, ge=1, le=168),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("settings:manage")),
):
    """Render the daily business summary without sending it."""
    return digest.build_digest(db, hours=hours)


@router.post("/admin/alerts/digest/send")
def admin_digest_send(
    request: Request,
    hours: int = Query(default=24, ge=1, le=168),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("settings:manage")),
):
    """Send the daily summary now, bypassing the schedule and the toggle."""
    result = digest.send_daily_summary(hours=hours, force=True)
    log_activity(
        db,
        actor=user,
        action="send_daily_digest",
        resource_type="notification_event",
        resource_id=result.get("event_id"),
        request=request,
        details={"ok": bool(result.get("ok")), "hours": hours},
    )
    db.commit()
    return result
