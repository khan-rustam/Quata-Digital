"""The Meta WhatsApp Cloud API client.

The *only* module in the entire QUATA estate that talks to Meta. Everything
else calls QCP; QCP calls in here. That single choke point is what makes "one
platform for every product" enforceable rather than a convention, and it is
asserted by ``tests/test_whatsapp_boundaries.py`` — this module may be
imported by ``dispatch.py`` and by nothing else.

Uses ``urllib`` from the stdlib (same approach as
``services/notifications/telegram.py``) so the send path adds no new runtime
dependency.

Two things this module will not do:

* **It will not send anything but a ``SendTicket``.** ``send_template`` takes
  no account id, no phone number id and no template name as loose arguments.
  Its first statement re-verifies the ticket's HMAC with
  ``hmac.compare_digest`` and re-asserts the purpose rules from the ticket's
  own fields (layer L3). A hand-built or mutated ticket never reaches the
  network.
* **It will not reveal a token.** The access token is decrypted from the
  account row at call time, is never logged, never interpolated into an error
  string, and is scrubbed out of any provider response before it is returned.
  The only thing logged about a token is its presence and length.

The scrubbing that makes the second of those true lives in ``scrub.py`` and is
re-exported here as ``scrub_provider_text``. Meta's error text is echoed *back*
through QCP into persisted columns, so the same scrub has to run at every sink
downstream, not only on the way out of here — including the status webhook,
which is not allowed to import this module at all.
"""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session

from app.core.config import settings as env_settings
from app.models import WhatsAppAccount

from . import settings_store
from .credentials import decrypt_wa_secret
from .scrub import scrub_provider_text  # noqa: F401 — re-export, see below
from .routing import (
    KIND_TEMPLATE,
    PURPOSE_AUTHENTICATION,
    RoutingDenied,
    SendTicket,
    verify_ticket,
)


log = logging.getLogger("quata.whatsapp.meta")


@dataclass
class SendResult:
    """Outcome of one provider call. Mirrors ``telegram.SendResult``."""

    ok: bool
    provider_message_id: Optional[str] = None
    error: Optional[str] = None
    # True when the failure is transient (network, 5xx, 429) and a retry
    # could plausibly succeed. False for permanent rejections such as an
    # invalid template or a number that has not opted in — retrying those
    # burns attempts and messaging quota for nothing.
    retryable: bool = False
    retry_after: Optional[int] = None
    error_code: Optional[str] = None


# Meta error codes worth another attempt. Everything else is treated as
# permanent unless the HTTP status says otherwise.
_RETRYABLE_CODES = {"130429", "131056", "133016", "132015", "500"}


def _api_version(account: WhatsAppAccount) -> str:
    return (account.api_version or settings_store.api_version() or "v21.0").strip()


def _endpoint(account: WhatsAppAccount, path: str) -> str:
    base = env_settings.WHATSAPP_GRAPH_BASE.rstrip("/")
    return f"{base}/{_api_version(account)}/{path.lstrip('/')}"


# ---------------------------------------------------------------------------
# Scrubbing provider text
# ---------------------------------------------------------------------------
# The rules live in ``scrub.py``, not here. Meta authors error text on two
# doors — the send rejection this module reads, and the status webhook
# ``webhooks.py`` reads — and ``webhooks.py`` may not import this module
# (``tests/test_whatsapp_boundaries.py``: exactly one module reaches the
# transport). A scrubber only both doors can call therefore cannot live in
# the transport. It is re-exported here because ``dispatch`` and the tests
# already reach it as ``meta.scrub_provider_text``.


def _scrub(text: str, token: Optional[str]) -> str:
    """Belt-and-braces: a token can never ride out inside an error string."""
    return scrub_provider_text(text, token)


def resolve_token(db: Session, account: WhatsAppAccount) -> Optional[str]:
    """Decrypt this account's access token.

    Credentials live in the database (encrypted), never in code and never in
    a literal. ``None`` means "not configured" and is reported as a retryable
    failure so the admin sees it in the console instead of losing the message.
    """
    token = decrypt_wa_secret(account.access_token_encrypted)
    log.debug(
        "whatsapp.token_resolved",
        extra={
            "account": account.slug,
            "configured": bool(token),
            "token_length": len(token) if token else 0,
        },
    )
    return token


def is_configured(db: Session, account: WhatsAppAccount) -> bool:
    return bool(resolve_token(db, account))


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

def _call(
    url: str,
    *,
    token: str,
    payload: Optional[dict] = None,
    method: str = "POST",
) -> tuple[bool, dict, Optional[str], Optional[int]]:
    """Issue one Graph API call. Returns (ok, body, error, http_status)."""
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    timeout = max(int(env_settings.NOTIFY_TIMEOUT_SECONDS), 1)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            body = json.loads(raw) if raw else {}
        return True, body, None, getattr(response, "status", 200)
    except urllib.error.HTTPError as exc:
        raw = ""
        try:
            raw = exc.read().decode("utf-8")
            body = json.loads(raw)
        except Exception:  # noqa: BLE001 — non-JSON error body
            body = {}
        detail = (body.get("error") or {}).get("message") if isinstance(body, dict) else None
        # Scrub, *then* truncate. Cutting first slices a credential in half
        # and leaves the half that matters sitting at the end of the string
        # with nothing left to recognise it by.
        message = detail or _scrub(raw, token)[:200] or str(exc.code)
        return False, body if isinstance(body, dict) else {}, _scrub(message, token), exc.code
    except Exception as exc:  # noqa: BLE001 — URLError, timeout, bad JSON
        return False, {}, _scrub(f"{type(exc).__name__}: {exc}", token)[:300], None


def _failure(body: dict, error: Optional[str], status: Optional[int], token: str) -> SendResult:
    err = body.get("error") if isinstance(body, dict) else None
    code = None
    if isinstance(err, dict) and err.get("code") is not None:
        code = str(err.get("code"))
    # No status = network/timeout; 429 = throttled; 5xx = Meta-side blip.
    # 400/401/403 are ours (bad template, revoked token, unopted number) and
    # fail identically on every retry.
    retryable = status is None or status == 429 or (status is not None and status >= 500)
    if code in _RETRYABLE_CODES:
        retryable = True
    log.warning(
        "whatsapp.send_failed",
        extra={"http_status": status, "error_code": code, "retryable": retryable},
    )
    return SendResult(
        ok=False,
        error=_scrub((error or "Unknown Meta error"), token)[:400],
        retryable=retryable,
        error_code=code[:40] if code else None,
    )


def _sent(body: dict) -> SendResult:
    messages = body.get("messages") or []
    wamid = None
    if messages and isinstance(messages[0], dict):
        wamid = messages[0].get("id")
    return SendResult(ok=True, provider_message_id=str(wamid)[:80] if wamid else None)


# ---------------------------------------------------------------------------
# Send — ticket in, result out
# ---------------------------------------------------------------------------

def _prepare(db: Session, ticket: SendTicket) -> tuple[WhatsAppAccount, str]:
    """L3: verify the ticket, then load the account it names.

    Raises ``RoutingDenied`` before any socket is opened.
    """
    verify_ticket(ticket)
    account = (
        db.query(WhatsAppAccount).filter(WhatsAppAccount.id == ticket.account_id).first()
    )
    if account is None or not account.is_active:
        raise RoutingDenied("no_account_for_purpose", account_id=ticket.account_id)
    if account.purpose != ticket.account_purpose:
        raise RoutingDenied("purpose_mismatch", account_id=account.id)
    if account.phone_number_id != ticket.phone_number_id:
        raise RoutingDenied("invalid_ticket", account_id=account.id)
    return account, ticket.phone_number_id


def send_template(ticket: SendTicket, *, db: Session) -> SendResult:
    """Send one approved template message. The only outbound path for Verify.

    The ticket's ``variables`` are the clear values (an OTP included). They go
    straight into the request body and are never logged or persisted here.
    """
    account, phone_number_id = _prepare(db, ticket)
    if ticket.kind != "template" or not ticket.template_name:
        raise RoutingDenied("invalid_ticket", account_id=account.id)

    token = resolve_token(db, account)
    if not token:
        return SendResult(
            ok=False,
            error=f"WhatsApp access token is not configured for account '{account.slug}'.",
            retryable=True,
            error_code="token_not_configured",
        )

    components = []
    if ticket.variables:
        components.append(
            {
                "type": "body",
                "parameters": [{"type": "text", "text": str(v)} for v in ticket.variables],
            }
        )
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": ticket.to_phone_e164,
        "type": "template",
        "template": {
            "name": ticket.template_name,
            "language": {"code": ticket.template_language or "en"},
            **({"components": components} if components else {}),
        },
    }
    ok, body, error, status = _call(
        _endpoint(account, f"{phone_number_id}/messages"), token=token, payload=payload
    )
    return _sent(body) if ok else _failure(body, error, status, token)


def send_text(ticket: SendTicket, *, db: Session, body_text: str) -> SendResult:
    """Send one free-form text message. Never from the Verify number.

    ``verify_ticket`` cannot cover this call: it evaluates
    ``freeform_on_auth_account`` against the ticket's *declared* kind, and a
    genuine login-OTP ticket honestly declares ``kind='template'``. So an
    unforged authentication ticket handed to this function would otherwise be
    enough to POST arbitrary prose from Quata Verify. This layer is only
    independent if it judges the ticket it was actually given, so both
    guards below are re-checked here rather than assumed of the caller.
    """
    account, phone_number_id = _prepare(db, ticket)
    if ticket.account_purpose == PURPOSE_AUTHENTICATION:
        raise RoutingDenied("freeform_on_auth_account", account_id=account.id)
    if ticket.kind == KIND_TEMPLATE:
        # Permission to send a template is not permission to send prose.
        raise RoutingDenied("invalid_ticket", account_id=account.id)

    token = resolve_token(db, account)
    if not token:
        return SendResult(
            ok=False,
            error=f"WhatsApp access token is not configured for account '{account.slug}'.",
            retryable=True,
            error_code="token_not_configured",
        )

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": ticket.to_phone_e164,
        "type": "text",
        "text": {"preview_url": False, "body": body_text},
    }
    ok, resp, error, status = _call(
        _endpoint(account, f"{phone_number_id}/messages"), token=token, payload=payload
    )
    return _sent(resp) if ok else _failure(resp, error, status, token)


# ---------------------------------------------------------------------------
# Non-send provider calls (template sync, phone health)
# ---------------------------------------------------------------------------

def list_message_templates(account: WhatsAppAccount, *, db: Session, limit: int = 200) -> dict:
    """Meta's view of this WABA's templates. Read-only."""
    token = resolve_token(db, account)
    if not token:
        return {"ok": False, "error": "Access token is not configured.", "data": []}
    ok, body, error, _ = _call(
        _endpoint(account, f"{account.waba_id}/message_templates?limit={int(limit)}"),
        token=token,
        method="GET",
    )
    if not ok:
        return {"ok": False, "error": _scrub(error or "Meta rejected the request.", token)[:400], "data": []}
    return {"ok": True, "data": body.get("data") or []}


def get_phone_health(account: WhatsAppAccount, *, db: Session) -> dict:
    """Quality rating + messaging tier for the account's number."""
    token = resolve_token(db, account)
    if not token:
        return {"ok": False, "error": "Access token is not configured."}
    ok, body, error, status = _call(
        _endpoint(
            account,
            f"{account.phone_number_id}?fields=quality_rating,messaging_limit_tier,verified_name,display_phone_number",
        ),
        token=token,
        method="GET",
    )
    if not ok:
        return {
            "ok": False,
            "error": _scrub(error or "Meta rejected the request.", token)[:400],
            "unauthorized": status in (401, 403),
        }
    return {
        "ok": True,
        "quality_rating": body.get("quality_rating"),
        "messaging_limit": body.get("messaging_limit_tier"),
        "verified_name": body.get("verified_name"),
        "display_phone_number": body.get("display_phone_number"),
    }
