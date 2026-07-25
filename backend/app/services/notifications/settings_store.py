"""Runtime switches for the notification service.

Same shape as ``app.services.site_settings`` — a seeded key/value catalogue
with a short process-wide TTL cache — but on its own table, because the
catalogue is *generated* (one row per platform and per category) and would
otherwise bury the site-settings form.

Every read goes through the helpers here so the precedence is uniform:

    notification_settings table → env default → hard-coded default

The env layer matters for the master switch: ``NOTIFY_ENABLED=false`` in the
environment silences the bot even if someone flips the DB toggle back on.
"""
from __future__ import annotations

import threading
import time
from typing import Optional

from sqlalchemy.orm import Session

from app.core.config import settings as env_settings
from app.db.session import SessionLocal
from app.models import NotificationSetting

from .catalog import CATEGORIES, PLATFORMS, PRIORITY_ORDER


_CACHE: dict[str, Optional[str]] = {}
_CACHE_AT: float = 0.0
_CACHE_TTL_SECONDS = 15.0
_LOCK = threading.Lock()


# ---------------------------------------------------------------------------
# Keys
# ---------------------------------------------------------------------------

KEY_ENABLED = "delivery.enabled"
KEY_MIN_PRIORITY = "delivery.min_priority"
KEY_LARGE_TX_THRESHOLD = "thresholds.large_transaction"
KEY_DIGEST_ENABLED = "digest.enabled"
KEY_DIGEST_HOUR_UTC = "digest.hour_utc"
KEY_CPU_THRESHOLD = "thresholds.cpu_percent"
KEY_MEMORY_THRESHOLD = "thresholds.memory_percent"
KEY_DISK_THRESHOLD = "thresholds.disk_percent"
KEY_AI_SPIKE_THRESHOLD = "thresholds.ai_requests_per_5min"


def platform_key(slug: str) -> str:
    return f"platform.{slug}"


def category_key(slug: str) -> str:
    return f"category.{slug}"


# ---------------------------------------------------------------------------
# Catalogue — seeded on boot so the admin form is always complete
# ---------------------------------------------------------------------------

def default_catalogue() -> list[dict]:
    rows: list[dict] = [
        {
            "key": KEY_ENABLED,
            "group": "delivery",
            "label": "Telegram notifications",
            "description": (
                "Master switch. When OFF, events are still recorded and audited "
                "but nothing is sent to @QuataAlertsBot."
            ),
            "field_type": "toggle",
            "sort_order": 10,
            "value": "true",
        },
        {
            "key": KEY_MIN_PRIORITY,
            "group": "delivery",
            "label": "Minimum priority to deliver",
            "description": (
                "Global floor. Events below this priority are recorded and "
                "suppressed. One of: " + ", ".join(PRIORITY_ORDER) + "."
            ),
            "field_type": "text",
            "sort_order": 20,
            "value": "info",
        },
        {
            "key": KEY_LARGE_TX_THRESHOLD,
            "group": "thresholds",
            "label": "Large transaction threshold (XAF)",
            "description": (
                "Any transaction at or above this amount is re-flagged as "
                "💰 LARGE TRANSACTION ALERT at CRITICAL priority."
            ),
            "field_type": "number",
            "sort_order": 10,
            "value": str(int(env_settings.NOTIFY_LARGE_TX_THRESHOLD)),
        },
        {
            "key": KEY_DIGEST_ENABLED,
            "group": "thresholds",
            "label": "Daily business summary",
            "description": "Send the scheduled daily report across all platforms.",
            "field_type": "toggle",
            "sort_order": 20,
            "value": "true",
        },
        {
            "key": KEY_DIGEST_HOUR_UTC,
            "group": "thresholds",
            "label": "Daily summary hour (UTC)",
            "description": "0–23. The worker sends the report on the first sweep at or after this hour.",
            "field_type": "number",
            "sort_order": 30,
            "value": "21",
        },
        {
            "key": KEY_CPU_THRESHOLD,
            "group": "thresholds",
            "label": "High CPU alert threshold (%)",
            "description": "1-minute load average as a share of available cores.",
            "field_type": "number",
            "sort_order": 40,
            "value": "85",
        },
        {
            "key": KEY_MEMORY_THRESHOLD,
            "group": "thresholds",
            "label": "High RAM alert threshold (%)",
            "description": "Used memory as a share of total. Linux hosts only.",
            "field_type": "number",
            "sort_order": 50,
            "value": "90",
        },
        {
            "key": KEY_DISK_THRESHOLD,
            "group": "thresholds",
            "label": "High disk alert threshold (%)",
            "description": "Disk usage on the uploads volume. A separate ⚠️ storage-low alert fires at 95%.",
            "field_type": "number",
            "sort_order": 60,
            "value": "85",
        },
        {
            "key": KEY_AI_SPIKE_THRESHOLD,
            "group": "thresholds",
            "label": "AI usage spike threshold (requests / 5 min)",
            "description": "Raises ⚠️ AI USAGE SPIKE above this rate. Set to 0 to disable.",
            "field_type": "number",
            "sort_order": 70,
            "value": "100",
        },
    ]
    for i, (slug, spec) in enumerate(PLATFORMS.items()):
        rows.append(
            {
                "key": platform_key(slug),
                "group": "platforms",
                "label": spec.name,
                "description": spec.description,
                "field_type": "toggle",
                "sort_order": (i + 1) * 10,
                "value": "true",
            }
        )
    for i, (slug, spec) in enumerate(CATEGORIES.items()):
        rows.append(
            {
                "key": category_key(slug),
                "group": "categories",
                "label": spec.name,
                "description": spec.description,
                "field_type": "toggle",
                "sort_order": (i + 1) * 10,
                "value": "true",
            }
        )
    return rows


def seed_defaults(db: Session) -> int:
    """Upsert the catalogue. Existing values are never overwritten — only
    the presentation metadata is refreshed. Returns rows inserted."""
    inserted = 0
    for spec in default_catalogue():
        row = (
            db.query(NotificationSetting)
            .filter(NotificationSetting.key == spec["key"])
            .first()
        )
        if row is None:
            db.add(NotificationSetting(**spec))
            inserted += 1
        else:
            for k in ("group", "label", "description", "field_type", "sort_order"):
                setattr(row, k, spec[k])
    db.commit()
    if inserted:
        invalidate()
    return inserted


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------

def invalidate() -> None:
    global _CACHE_AT
    with _LOCK:
        _CACHE.clear()
        _CACHE_AT = 0.0


def _load() -> dict[str, Optional[str]]:
    """Return the whole table as a dict, refreshing the cache when stale.

    One query for the whole (small, <40 row) table beats a query per key —
    the dispatcher reads several keys for every single event.
    """
    global _CACHE_AT
    with _LOCK:
        if _CACHE and (time.monotonic() - _CACHE_AT) < _CACHE_TTL_SECONDS:
            return dict(_CACHE)

    db = SessionLocal()
    try:
        rows = db.query(NotificationSetting).all()
        fresh = {r.key: r.value for r in rows}
    except Exception:  # noqa: BLE001
        # Table not created yet (fresh dev DB, or prod pre-migration).
        # Fall through to defaults without caching so the next call retries.
        db.rollback()
        return {}
    finally:
        db.close()

    with _LOCK:
        _CACHE.clear()
        _CACHE.update(fresh)
        _CACHE_AT = time.monotonic()
    return fresh


def get(key: str, default: Optional[str] = None) -> Optional[str]:
    value = _load().get(key)
    return value if value not in (None, "") else default


def get_bool(key: str, default: bool = True) -> bool:
    raw = get(key)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def get_float(key: str, default: float) -> float:
    raw = get(key)
    if raw is None:
        return default
    try:
        return float(str(raw).replace(",", "").strip())
    except ValueError:
        return default


def get_int(key: str, default: int) -> int:
    return int(get_float(key, float(default)))


def set_value(db: Session, *, key: str, value: Optional[str], updated_by_id: Optional[int]) -> NotificationSetting:
    """Update one setting. Unknown keys are refused so the admin can't
    introduce a key that nothing reads."""
    row = db.query(NotificationSetting).filter(NotificationSetting.key == key).first()
    if row is None:
        raise ValueError(f"Unknown notification setting: {key}")
    row.value = value
    row.updated_by_id = updated_by_id
    db.add(row)
    db.flush()
    invalidate()
    return row


def list_settings(db: Session, *, group: Optional[str] = None) -> list[NotificationSetting]:
    q = db.query(NotificationSetting)
    if group:
        q = q.filter(NotificationSetting.group == group)
    return q.order_by(
        NotificationSetting.group,
        NotificationSetting.sort_order,
        NotificationSetting.label,
    ).all()


# ---------------------------------------------------------------------------
# Derived answers the dispatcher asks
# ---------------------------------------------------------------------------

def service_enabled() -> bool:
    """Master switch: env kill-switch AND the admin toggle must both allow it."""
    if not env_settings.NOTIFY_ENABLED:
        return False
    return get_bool(KEY_ENABLED, True)


def platform_enabled(slug: str) -> bool:
    return get_bool(platform_key(slug), True)


def category_enabled(slug: str) -> bool:
    return get_bool(category_key(slug), True)


def min_priority() -> str:
    value = (get(KEY_MIN_PRIORITY, "info") or "info").strip().lower()
    return value if value in PRIORITY_ORDER else "info"


def large_transaction_threshold() -> float:
    return get_float(KEY_LARGE_TX_THRESHOLD, env_settings.NOTIFY_LARGE_TX_THRESHOLD)


def digest_enabled() -> bool:
    return get_bool(KEY_DIGEST_ENABLED, True)


def digest_hour_utc() -> int:
    hour = get_int(KEY_DIGEST_HOUR_UTC, 21)
    return hour if 0 <= hour <= 23 else 21


def cpu_threshold() -> float:
    return get_float(KEY_CPU_THRESHOLD, 85.0)


def memory_threshold() -> float:
    return get_float(KEY_MEMORY_THRESHOLD, 90.0)


def disk_threshold() -> float:
    return get_float(KEY_DISK_THRESHOLD, 85.0)


def ai_spike_threshold() -> int:
    """Requests per 5-minute window before ⚠️ AI USAGE SPIKE fires. 0 = off."""
    return max(get_int(KEY_AI_SPIKE_THRESHOLD, 100), 0)
