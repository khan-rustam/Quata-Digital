"""Telegram transport for @QuataAlertsBot.

The *only* module in the entire QUATA estate that talks to the Telegram Bot
API. Everything else publishes events to the notification service; the
service calls in here. That single choke point is what makes "one bot for
every platform" enforceable rather than a convention.

Uses ``urllib`` from the stdlib (same approach as the hCaptcha verifier) so
the notification path adds no new runtime dependency.

The bot token is resolved from the site-settings table first, falling back
to ``TELEGRAM_BOT_TOKEN`` in the environment — matching how hCaptcha and
Sentry credentials already work here, so the boss can rotate it from the
admin without a redeploy. It is never logged and never included in an error
string returned to a caller.
"""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Optional

from app.core.config import settings as env_settings


log = logging.getLogger("quata.notifications.telegram")

TOKEN_SETTING_KEY = "integrations.telegram_bot_token"


@dataclass
class SendResult:
    ok: bool
    message_id: Optional[int] = None
    error: Optional[str] = None
    # True when the failure is transient (network, 5xx, 429) and a retry
    # could plausibly succeed. False for permanent rejections such as
    # "chat not found" or "bot was blocked by the user" — retrying those
    # just burns attempts and rate limit.
    retryable: bool = False
    retry_after: Optional[int] = None


def get_bot_token() -> str:
    """Resolve the bot token. Empty string means "not configured"."""
    # Imported lazily: site_settings opens its own DB session, and importing
    # it at module scope would drag the DB into `import telegram` during
    # tests that never touch delivery.
    try:
        from app.services.site_settings import get_setting

        token = get_setting(
            TOKEN_SETTING_KEY, env_fallback=env_settings.TELEGRAM_BOT_TOKEN
        )
    except Exception:  # noqa: BLE001 — DB not ready; env is still valid
        token = env_settings.TELEGRAM_BOT_TOKEN
    return (token or "").strip()


def is_configured() -> bool:
    return bool(get_bot_token())


def _api_url(method: str, token: str) -> str:
    base = env_settings.TELEGRAM_API_BASE.rstrip("/")
    return f"{base}/bot{token}/{method}"


def _scrub(text: str, token: str) -> str:
    """Belt-and-braces: make sure a token can never ride out in an error."""
    if token and token in text:
        text = text.replace(token, "***")
    return text


def _call(method: str, params: dict, *, timeout: Optional[int] = None) -> tuple[bool, dict, Optional[str], Optional[int]]:
    """POST to the Bot API. Returns (ok, body, error, http_status)."""
    token = get_bot_token()
    if not token:
        return False, {}, "Telegram bot token is not configured.", None

    data = urllib.parse.urlencode(params).encode("utf-8")
    request = urllib.request.Request(
        _api_url(method, token),
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    seconds = timeout or env_settings.NOTIFY_TIMEOUT_SECONDS
    try:
        with urllib.request.urlopen(request, timeout=seconds) as response:
            body = json.loads(response.read().decode("utf-8"))
        return bool(body.get("ok")), body, None, 200
    except urllib.error.HTTPError as exc:
        raw = ""
        try:
            raw = exc.read().decode("utf-8")
            body = json.loads(raw)
        except Exception:  # noqa: BLE001
            body = {}
        description = body.get("description") or _scrub(raw[:200], token) or str(exc.code)
        return False, body, _scrub(description, token), exc.code
    except Exception as exc:  # noqa: BLE001 — URLError, timeout, bad JSON
        return False, {}, _scrub(f"{type(exc).__name__}: {exc}", token)[:300], None


def send_message(chat_id: str, text: str, *, disable_preview: bool = True) -> SendResult:
    """Send one HTML message to one chat."""
    ok, body, error, status = _call(
        "sendMessage",
        {
            "chat_id": str(chat_id),
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": "true" if disable_preview else "false",
        },
    )
    if ok:
        result = body.get("result") or {}
        return SendResult(ok=True, message_id=result.get("message_id"))

    retry_after = None
    parameters = body.get("parameters") or {}
    if isinstance(parameters, dict):
        retry_after = parameters.get("retry_after")

    # 429 = flood control, 5xx = Telegram-side blip, no status = network.
    # 400/403 are our fault (bad chat id, bot blocked, malformed HTML) and
    # will fail identically on every retry.
    retryable = status is None or status == 429 or (status is not None and status >= 500)
    log.warning(
        "telegram.send_failed",
        extra={"chat_id": str(chat_id)[:20], "http_status": status, "retryable": retryable},
    )
    return SendResult(
        ok=False,
        error=(error or "Unknown Telegram error")[:400],
        retryable=retryable,
        retry_after=retry_after if isinstance(retry_after, int) else None,
    )


def get_me() -> dict:
    """Identify the configured bot — powers the admin's connection check."""
    if not is_configured():
        return {"ok": False, "configured": False, "error": "Telegram bot token is not configured."}
    ok, body, error, _ = _call("getMe", {})
    if not ok:
        return {"ok": False, "configured": True, "error": error or "Telegram rejected the request."}
    result = body.get("result") or {}
    return {
        "ok": True,
        "configured": True,
        "bot_id": result.get("id"),
        "username": result.get("username"),
        "first_name": result.get("first_name"),
    }
