"""Runtime switches for QCP.

Only four toggles, so they live in the **existing** ``site_settings`` table
under ``group="whatsapp"`` rather than in a ninth QCP table.

The one rule that matters:

    delivery_enabled() == env(WHATSAPP_ENABLED) AND db(whatsapp.delivery_enabled)

Env is a kill switch a DB toggle cannot override. This is the direct answer
to the audited QuataPay failure mode — credentials sitting in a production
table meant the rail was one admin form submission away from live with no
redeploy. Here, flipping every DB row still sends nothing unless the
environment says so, and turning the env var off stops delivery without a
code change. Same shape as
``services/notifications/settings_store.service_enabled``.

The DB key defaults to **false** when the row is absent, so a database that
has never been through the QCP admin console is dormant rather than
implicitly live.

``require_signature`` is floored the same way but in the opposite direction —
see its docstring. The rule for both: **env decides the unsafe direction, the
DB row may only move things the safe way.**
"""
from __future__ import annotations

from typing import Optional

from app.core.config import settings as env_settings
from app.services import site_settings


GROUP = "whatsapp"

KEY_DELIVERY_ENABLED = "whatsapp.delivery_enabled"
KEY_API_VERSION = "whatsapp.api_version"
KEY_REQUIRE_SIGNATURE = "whatsapp.require_signature"
KEY_MAX_ATTEMPTS = "whatsapp.max_attempts"

_TRUE = {"1", "true", "yes", "on"}


def _get(key: str, default: Optional[str] = None) -> Optional[str]:
    return site_settings.get_setting(key, default)


def _get_bool(key: str, default: bool) -> bool:
    raw = _get(key)
    if raw is None or raw == "":
        return default
    return str(raw).strip().lower() in _TRUE


def _get_int(key: str, default: int) -> int:
    raw = _get(key)
    if raw is None or raw == "":
        return default
    try:
        return int(str(raw).strip())
    except ValueError:
        return default


def delivery_enabled() -> bool:
    """Master switch: the env kill switch AND the admin toggle must agree."""
    if not env_settings.WHATSAPP_ENABLED:
        return False
    return _get_bool(KEY_DELIVERY_ENABLED, False)


def api_version() -> str:
    return _get(KEY_API_VERSION, env_settings.WHATSAPP_API_VERSION) or "v21.0"


def require_signature() -> bool:
    """Env floor first: a DB row may add strictness, never remove it.

    The mirror image of ``delivery_enabled`` above, and env-floored for the
    same reason. There the unsafe state is *on*, so env AND db means no DB row
    can start delivery. Here the unsafe state is *off* — this one switch gates
    the internet-facing Meta webhook **and** the product ``X-QCP-Signature``
    check — so ``WHATSAPP_REQUIRE_SIGNATURE=true`` (the default) pins it on
    and a ``settings:manage`` PUT cannot undo it. Read as a DB default, one
    row would turn ``POST /whatsapp/webhook/{slug}`` into an unauthenticated
    write API: forged inbound messages, forged conversations on the Verify
    number, forged status callbacks marking real messages delivered.

    Below the floor (``WHATSAPP_REQUIRE_SIGNATURE=false``, the dev escape
    hatch) the admin toggle still decides, and still defaults to off. Note
    that reaching that state at all now takes an unconfigured, non-production
    box: ``Settings.assert_whatsapp_signature_floor`` refuses to boot below
    the floor if delivery is on, if any account holds credentials, or if
    ``ENVIRONMENT=production``.
    """
    if env_settings.WHATSAPP_REQUIRE_SIGNATURE:
        return True
    return _get_bool(KEY_REQUIRE_SIGNATURE, False)


def max_attempts() -> int:
    return max(_get_int(KEY_MAX_ATTEMPTS, env_settings.WHATSAPP_MAX_ATTEMPTS), 1)
