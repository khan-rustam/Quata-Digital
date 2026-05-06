"""Site-settings store.

A small key/value table the admin edits at runtime. Backend services that
historically read configuration from env (`HCAPTCHA_*`, `SENTRY_DSN`, the
public phone number) prefer this table when populated; env stays as a
deploy-time fallback for the placeholder/dev setup.

Design notes:
- Reads are cached with a process-wide TTL to keep hot paths fast. The
  TTL is short (15s) so admin edits propagate quickly without a restart.
- Writes invalidate the cache.
- `get_setting()` is the only entry point services should use. Direct DB
  queries inside other services would skip the env fallback + caching.
- Sentry is special — it only initialises once at process start, so a DSN
  change requires a backend restart to take effect. The admin form notes this.
"""
from __future__ import annotations

import threading
import time
from typing import Iterable, Optional

from sqlalchemy.orm import Session

from app.core.config import settings as env_settings
from app.db.session import SessionLocal
from app.models import SiteSetting


_CACHE: dict[str, tuple[float, Optional[str]]] = {}
_CACHE_TTL_SECONDS = 15.0
_LOCK = threading.Lock()


# ---------------------------------------------------------------------------
# Default catalogue. `seed_default_settings()` upserts these on boot so the
# admin always sees a complete form. Existing values are never overwritten.
# ---------------------------------------------------------------------------

DEFAULT_SETTINGS: list[dict] = [
    # ---- Integrations ----
    {
        "key": "integrations.hcaptcha_site_key",
        "group": "integrations",
        "label": "hCaptcha site key",
        "description": "Public site key from hcaptcha.com. Paired with the secret below.",
        "field_type": "text",
        "is_secret": False,
        "sort_order": 10,
    },
    {
        "key": "integrations.hcaptcha_secret_key",
        "group": "integrations",
        "label": "hCaptcha secret key",
        "description": "Server secret from hcaptcha.com. Validates tokens server-side. Leave blank to disable hCaptcha enforcement.",
        "field_type": "password",
        "is_secret": True,
        "sort_order": 11,
    },
    {
        "key": "integrations.sentry_dsn",
        "group": "integrations",
        "label": "Sentry DSN",
        "description": "Sentry project DSN. Backend must be restarted after a change for the SDK to re-initialise.",
        "field_type": "password",
        "is_secret": True,
        "sort_order": 20,
    },
    {
        "key": "integrations.sentry_env",
        "group": "integrations",
        "label": "Sentry environment",
        "description": "Tag attached to events. e.g. production / staging.",
        "field_type": "text",
        "is_secret": False,
        "sort_order": 21,
    },

    # ---- Contact info (publicly readable) ----
    {
        "key": "contact.phone",
        "group": "contact",
        "label": "Public phone number",
        "description": "Shown in the footer and on the contact page. Hidden when blank.",
        "field_type": "phone",
        "is_secret": False,
        "sort_order": 10,
    },
    {
        "key": "contact.email",
        "group": "contact",
        "label": "Public email",
        "description": "General-enquiries email. Defaults to info@quatadigital.com when blank.",
        "field_type": "email",
        "is_secret": False,
        "sort_order": 20,
    },
    {
        "key": "contact.address",
        "group": "contact",
        "label": "Office address",
        "description": "Multi-line; rendered in the footer + contact page.",
        "field_type": "textarea",
        "is_secret": False,
        "sort_order": 30,
    },
    {
        "key": "contact.support_hours",
        "group": "contact",
        "label": "Support hours",
        "description": "e.g. \"Mon–Fri 09:00–18:00 WAT\". Hidden when blank.",
        "field_type": "text",
        "is_secret": False,
        "sort_order": 40,
    },

    # ---- Social links (publicly readable) ----
    {
        "key": "social.linkedin_url",
        "group": "social",
        "label": "LinkedIn URL",
        "description": "Full https URL. Hidden when blank.",
        "field_type": "url",
        "is_secret": False,
        "sort_order": 10,
    },
    {
        "key": "social.twitter_url",
        "group": "social",
        "label": "Twitter / X URL",
        "field_type": "url",
        "is_secret": False,
        "sort_order": 20,
    },
    {
        "key": "social.instagram_url",
        "group": "social",
        "label": "Instagram URL",
        "field_type": "url",
        "is_secret": False,
        "sort_order": 30,
    },
    {
        "key": "social.youtube_url",
        "group": "social",
        "label": "YouTube URL",
        "field_type": "url",
        "is_secret": False,
        "sort_order": 40,
    },
    {
        "key": "social.facebook_url",
        "group": "social",
        "label": "Facebook URL",
        "field_type": "url",
        "is_secret": False,
        "sort_order": 50,
    },

    # ---- Toggles ----
    {
        "key": "toggles.maintenance_mode",
        "group": "toggles",
        "label": "Maintenance mode",
        "description": "When ON, the public site shows a maintenance banner. Admin remains accessible.",
        "field_type": "toggle",
        "is_secret": False,
        "sort_order": 10,
    },
    {
        "key": "toggles.maintenance_message",
        "group": "toggles",
        "label": "Maintenance banner copy",
        "description": "Optional message shown in the maintenance banner when the toggle is ON. Leave blank for the default.",
        "field_type": "textarea",
        "is_secret": False,
        "sort_order": 11,
    },
    {
        "key": "toggles.cookie_banner_text",
        "group": "toggles",
        "label": "Cookie banner copy override",
        "description": "Optional override for the cookie banner message. Leave blank for the default.",
        "field_type": "textarea",
        "is_secret": False,
        "sort_order": 20,
    },
]


# Groups whose values are safe to expose publicly. Anything else (integrations,
# toggles where toggle key starts with `internal.`) requires admin auth to read.
PUBLIC_GROUPS = {"contact", "social"}
PUBLIC_KEYS = {"toggles.maintenance_mode", "toggles.maintenance_message"}


def seed_default_settings(db: Session) -> int:
    """Upsert the default catalogue. Existing values are NEVER overwritten —
    only the metadata (label / description / field_type / sort_order) is
    refreshed so admin renders the latest help text. Returns the number of
    rows inserted (not updated)."""
    inserted = 0
    for spec in DEFAULT_SETTINGS:
        row = (
            db.query(SiteSetting)
            .filter(SiteSetting.key == spec["key"])
            .first()
        )
        if row is None:
            db.add(SiteSetting(**spec))
            inserted += 1
        else:
            # Refresh metadata; preserve `value` and `is_secret` (boss may
            # have intentionally set is_secret on an existing row).
            for k in ("group", "label", "description", "field_type", "sort_order"):
                if k in spec:
                    setattr(row, k, spec[k])
    db.commit()
    return inserted


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _cache_get(key: str) -> tuple[bool, Optional[str]]:
    with _LOCK:
        entry = _CACHE.get(key)
        if entry is None:
            return False, None
        cached_at, value = entry
        if (time.monotonic() - cached_at) > _CACHE_TTL_SECONDS:
            _CACHE.pop(key, None)
            return False, None
        return True, value


def _cache_put(key: str, value: Optional[str]) -> None:
    with _LOCK:
        _CACHE[key] = (time.monotonic(), value)


def invalidate_cache(key: str | None = None) -> None:
    with _LOCK:
        if key is None:
            _CACHE.clear()
        else:
            _CACHE.pop(key, None)


def get_setting(key: str, default: Optional[str] = None, *, env_fallback: Optional[str] = None) -> Optional[str]:
    """Resolve a setting value.

    Priority: site_settings table → env_fallback → default.

    `env_fallback` is the env value the caller already has on hand (the
    helper does not import config.settings dynamically to keep dependencies
    explicit).
    """
    hit, cached = _cache_get(key)
    if hit:
        if cached:
            return cached
        # cached null — try env fallback
        return env_fallback if env_fallback else default

    db = SessionLocal()
    try:
        row = db.query(SiteSetting).filter(SiteSetting.key == key).first()
        value = row.value if row else None
    except Exception:  # noqa: BLE001
        # Most common: the `site_settings` table doesn't exist yet (fresh
        # dev DB before lifespan runs `create_all`, or prod before the
        # alembic migration has been applied). Fall through to env without
        # caching so the next call retries once the table is real.
        db.rollback()
        return env_fallback if env_fallback else default
    finally:
        db.close()
    _cache_put(key, value)

    if value:
        return value
    if env_fallback:
        return env_fallback
    return default


def list_settings(db: Session, *, group: Optional[str] = None) -> list[SiteSetting]:
    q = db.query(SiteSetting)
    if group:
        q = q.filter(SiteSetting.group == group)
    return q.order_by(SiteSetting.group, SiteSetting.sort_order, SiteSetting.label).all()


def public_settings_payload(db: Session) -> dict:
    """Return a flat dict of public-safe key→value pairs. Skips secrets and
    non-public groups. Used by the marketing frontend."""
    rows = (
        db.query(SiteSetting)
        .filter(SiteSetting.is_secret == False)  # noqa: E712
        .all()
    )
    out: dict[str, Optional[str]] = {}
    for r in rows:
        if r.group in PUBLIC_GROUPS or r.key in PUBLIC_KEYS:
            out[r.key] = r.value
    return out


def set_setting(db: Session, *, key: str, value: Optional[str], updated_by_id: Optional[int]) -> SiteSetting:
    row = db.query(SiteSetting).filter(SiteSetting.key == key).first()
    if row is None:
        # Allow ad-hoc creation only via the seed catalogue. Refuse otherwise
        # so the admin can't introduce arbitrary keys that nothing reads.
        raise ValueError(f"Unknown setting key: {key}")
    row.value = value
    row.updated_by_id = updated_by_id
    db.add(row)
    db.flush()
    invalidate_cache(key)
    return row
