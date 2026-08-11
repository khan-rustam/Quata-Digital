"""Inbound from Meta — verification handshake, signature, and ingestion.

This is the only door QCP opens to the outside world, and everything about
it is written for one operational fact:

    **Meta redelivers.** If our 200 is slow, lost, or a 5xx, Meta re-POSTs
    the *entire* ``entry[].changes[]`` envelope — the same messages and the
    same statuses, sometimes many times. And if an endpoint keeps erroring,
    Meta disables the subscription for the whole WABA. So a redelivery must
    be a **no-op**, and a malformed payload must produce a **200, never a
    500**.

Two dedupe layers, one per direction:

* **Inbound messages** are keyed on ``whatsapp_messages.provider_message_id``
  (the ``wamid``), which is UNIQUE. A replayed message finds the existing row
  and stops — no second message row, no second conversation, and critically
  no second ``unread_count`` bump.
* **Status callbacks** are keyed on ``whatsapp_delivery_events.dedupe_key``,
  a hash of ``(wamid, status, Meta's own timestamp)``, also UNIQUE. A
  replayed ``delivered`` collides and is dropped before it can touch the
  message row.

Both layers check first and then rely on the unique index as the backstop,
catching ``IntegrityError`` the same way ``notifications/dispatch.py`` does —
the pre-check handles the common case, the index handles the race.

**What is rejected, and what is merely ignored.** A bad or missing signature
is a 403: that request is not Meta, and answering 200 to an unauthenticated
caller would both accept forged traffic and hand an attacker an oracle. A
payload that *is* signed but that we cannot use — malformed JSON, an
unexpected object type, a field we do not consume — is a 200 with an audit
row, because asking Meta to redeliver something we will never parse only
walks the endpoint towards being disabled.

**A refusal is not a write primitive.** This endpoint is deliberately not
rate-limited (see the router), so the refusals themselves have to be metered:
identical rejections collapse into one audit row per window instead of one row
per request. The 403 is never withheld — only the row.

This module never sends. It imports models, conversations, redaction, audit
and credentials, and it must never import ``meta`` or ``dispatch``.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    WhatsAppAccount,
    WhatsAppDeliveryEvent,
    WhatsAppMessage,
)

from . import audit, conversations, settings_store
from .credentials import decrypt_wa_secret
from .redaction import redact_body, redact_details
from .scrub import scrub_provider_text, scrub_structure


log = logging.getLogger("quata.whatsapp")


# Meta's webhook envelope for a WhatsApp Business Account.
EXPECTED_OBJECT = "whatsapp_business_account"
# The only `change.field` QCP consumes in v1. Template-approval and
# quality-rating callbacks are recognised and skipped rather than errored,
# so turning them on at Meta cannot break ingestion.
FIELD_MESSAGES = "messages"

SIGNATURE_HEADER = "X-Hub-Signature-256"
SIGNATURE_PREFIX = "sha256="

# A Meta webhook is a few KB. Anything past this is not Meta and must not be
# hashed or parsed.
MAX_BODY_BYTES = 1_000_000

# Rejections that surface as HTTP, and their reason codes. Stable strings —
# they land in whatsapp_audit_log.reason and are read by operators.
REASON_UNKNOWN_ACCOUNT = "unknown_account"
REASON_NO_APP_SECRET = "no_app_secret"
REASON_MISSING_SIGNATURE = "missing_signature"
REASON_BAD_SIGNATURE = "bad_signature"
REASON_NO_VERIFY_TOKEN = "no_verify_token"
REASON_BAD_VERIFY_TOKEN = "bad_verify_token"
REASON_BAD_HUB_MODE = "bad_hub_mode"
REASON_PAYLOAD_TOO_LARGE = "payload_too_large"
# Reasons that are logged but answered 200.
REASON_MALFORMED_JSON = "malformed_json"
REASON_UNEXPECTED_OBJECT = "unexpected_object"
REASON_PHONE_NUMBER_MISMATCH = "phone_number_id_mismatch"
REASON_ACCOUNT_PHONE_UNSET = "account_phone_number_id_unset"
REASON_MISSING_PHONE_NUMBER_ID = "missing_phone_number_id"
REASON_PROVIDER_ERROR = "provider_error"

# Failed authentication must not be an unbounded write primitive. This
# endpoint is deliberately *not* rate-limited — shedding Meta's redelivery
# bursts is precisely how a subscription gets disabled — so without this a
# forged-POST loop commits one audit row per request. Identical refusals
# (same account, same source IP, same reason) collapse into a counter and
# land as one row per window, carrying how many they stood in for.
REJECT_COLLAPSE_WINDOW_SECONDS = 60
# Bound on distinct (account, ip, reason) windows held in memory. ``source_ip``
# comes from ``get_client_ip``, which only honours X-Forwarded-For behind a
# trusted hop, so this cannot be inflated by a header.
REJECT_COLLAPSE_MAX_KEYS = 4096

_reject_windows: dict[tuple, list] = {}
_reject_lock = threading.Lock()


def reset_rejection_windows() -> None:
    """Drop every open collapse window. Test seam — nothing in the app calls it."""
    with _reject_lock:
        _reject_windows.clear()


def _open_rejection_window(key: tuple) -> Optional[int]:
    """Should this refusal be written, and how many did it stand in for?

    Returns the number of suppressed repeats to record alongside the row, or
    ``None`` when the refusal falls inside a window already on disk.
    """
    now = time.monotonic()
    with _reject_lock:
        entry = _reject_windows.get(key)
        if entry is not None and (now - entry[0]) < REJECT_COLLAPSE_WINDOW_SECONDS:
            entry[1] += 1
            return None
        suppressed = entry[1] if entry is not None else 0
        if entry is None and len(_reject_windows) >= REJECT_COLLAPSE_MAX_KEYS:
            for stale, values in list(_reject_windows.items()):
                if (now - values[0]) >= REJECT_COLLAPSE_WINDOW_SECONDS:
                    del _reject_windows[stale]
            if len(_reject_windows) >= REJECT_COLLAPSE_MAX_KEYS:
                # Every window is live. Forget them all rather than grow
                # without bound; the cost is one extra audit row apiece.
                _reject_windows.clear()
        _reject_windows[key] = [now, 0]
        return suppressed


_HEX_DIGITS = frozenset("0123456789abcdef")


def is_sha256_hex(value: Optional[str]) -> bool:
    """True only for exactly 64 hex characters.

    Every ``hmac.compare_digest`` against an attacker-controlled header goes
    through this first. ``compare_digest`` raises ``TypeError`` on a non-ASCII
    ``str`` and Starlette decodes headers as latin-1, so the byte that makes
    it raise is entirely the caller's to choose — and on the POST webhook the
    broad ``except Exception`` in the router turns the intended 403 into
    ``200 {"ok": true}``, handing an unauthenticated caller SUCCESS from the
    one endpoint whose whole contract is "403 means you are not Meta".
    """
    if not value or len(value) != 64:
        return False
    return all(ch in _HEX_DIGITS for ch in value.casefold())


class WebhookRejected(Exception):
    """A webhook request QCP refuses to process at all.

    ``reason`` is a stable code, never free text — the router turns it into
    an HTTP status and the audit log stores it verbatim.
    """

    def __init__(self, reason: str, *, http_status: int = 403):
        super().__init__(reason)
        self.reason = reason
        self.http_status = http_status


# ---------------------------------------------------------------------------
# Account resolution
# ---------------------------------------------------------------------------

def resolve_account(db: Session, account_slug: str) -> WhatsAppAccount:
    """Look up the account this webhook URL belongs to.

    Deliberately does **not** require ``is_active``. Meta's verification
    handshake happens while the number is still being provisioned, and an
    account that has been deactivated can still receive a trailing status
    callback for a message it already sent. Activation gates *outbound*
    delivery; it must not silently discard evidence of what arrived.
    """
    row = (
        db.query(WhatsAppAccount)
        .filter(WhatsAppAccount.slug == (account_slug or "").strip().lower())
        .first()
    )
    if row is None:
        raise WebhookRejected(REASON_UNKNOWN_ACCOUNT, http_status=404)
    return row


# ---------------------------------------------------------------------------
# GET — the subscription handshake
# ---------------------------------------------------------------------------

def verify_subscription(
    db: Session,
    *,
    account_slug: str,
    mode: Optional[str],
    token: Optional[str],
    challenge: Optional[str],
    source_ip: Optional[str] = None,
) -> str:
    """Answer Meta's ``hub.challenge`` handshake.

    Returns the challenge string to echo back **verbatim** — Meta compares
    the raw response body, so the caller must send it as text/plain and must
    not wrap it in JSON.
    """
    account = resolve_account(db, account_slug)

    if (mode or "") != "subscribe":
        _reject(db, account, REASON_BAD_HUB_MODE, source_ip=source_ip)

    expected = decrypt_wa_secret(account.webhook_verify_token_encrypted)
    if not expected:
        # No token configured (or SECRET_KEY was rotated). Fail closed —
        # never accept an arbitrary token because we have nothing to compare.
        _reject(db, account, REASON_NO_VERIFY_TOKEN, source_ip=source_ip)

    # Compared as bytes: a verify token is arbitrary text, and
    # ``compare_digest`` raises TypeError on a non-ASCII ``str``. UTF-8
    # encoding always succeeds and keeps the compare constant-time.
    if not token or not hmac.compare_digest(
        expected.encode("utf-8"), token.encode("utf-8")
    ):
        _reject(db, account, REASON_BAD_VERIFY_TOKEN, source_ip=source_ip)

    audit.record(
        db,
        action="webhook.verified",
        resource_type="whatsapp_account",
        resource_id=account.slug,
        account_id=account.id,
        ip_address=source_ip,
        details={"mode": mode},
    )
    db.commit()
    return challenge or ""


# ---------------------------------------------------------------------------
# Signature
# ---------------------------------------------------------------------------

def compute_signature(app_secret: str, raw_body: bytes) -> str:
    """The hex digest Meta puts in ``X-Hub-Signature-256``."""
    return hmac.new(app_secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()


def _verify_signature(
    db: Session,
    account: WhatsAppAccount,
    *,
    raw_body: bytes,
    header: Optional[str],
    source_ip: Optional[str],
) -> None:
    """Raise ``WebhookRejected`` unless the body is signed by this account.

    Note there is no timestamp to check — Meta signs the body only, so
    ``WHATSAPP_SIGNATURE_SKEW_SECONDS`` applies to the *product-facing*
    ingest endpoint, not here. Replay protection on this path comes from the
    dedupe keys instead, which is the right layer for it: a replay of a real
    Meta payload is exactly what a redelivery is.
    """
    if not settings_store.require_signature():
        return

    app_secret = decrypt_wa_secret(account.app_secret_encrypted)
    if not app_secret:
        # Fail closed. An account with no app secret cannot have its
        # webhooks authenticated, so nothing it receives may be trusted.
        _reject(db, account, REASON_NO_APP_SECRET, source_ip=source_ip)

    if not header:
        _reject(db, account, REASON_MISSING_SIGNATURE, source_ip=source_ip)

    supplied = header.strip()
    if supplied.startswith(SIGNATURE_PREFIX):
        supplied = supplied[len(SIGNATURE_PREFIX):]

    if not is_sha256_hex(supplied):
        # Refuse on shape before comparing — see ``is_sha256_hex``.
        _reject(db, account, REASON_BAD_SIGNATURE, source_ip=source_ip)

    expected = compute_signature(app_secret, raw_body)
    if not hmac.compare_digest(
        expected.encode("ascii"), supplied.casefold().encode("ascii")
    ):
        _reject(db, account, REASON_BAD_SIGNATURE, source_ip=source_ip)


def _reject(
    db: Session,
    account: Optional[WhatsAppAccount],
    reason: str,
    *,
    source_ip: Optional[str] = None,
    http_status: int = 403,
    details: Optional[dict] = None,
) -> None:
    """Audit a refusal, commit it, and raise. Never returns.

    The refusal itself is unconditional — every caller still gets its 403.
    What is conditional is the *row*: repeats of the same refusal from the
    same source collapse into the window opened by the first one, so a forged
    burst cannot use this endpoint as an unmetered INSERT.
    """
    suppressed = _open_rejection_window(
        (account.id if account else None, source_ip or "", reason)
    )
    if suppressed is not None:
        payload = dict(details or {})
        if suppressed:
            payload["suppressed_repeats"] = suppressed
        try:
            audit.record(
                db,
                action="webhook.rejected",
                resource_type="whatsapp_account",
                resource_id=(account.slug if account else None),
                account_id=(account.id if account else None),
                outcome=audit.OUTCOME_DENIED,
                reason=reason,
                ip_address=source_ip,
                details=payload,
            )
            db.commit()
        except Exception:  # noqa: BLE001 — an audit failure must not mask the refusal
            db.rollback()
            log.warning("whatsapp.webhook_audit_failed", extra={"reason": reason})
    raise WebhookRejected(reason, http_status=http_status)


# ---------------------------------------------------------------------------
# POST — ingestion
# ---------------------------------------------------------------------------

def handle_event(
    db: Session,
    *,
    account_slug: str,
    raw_body: bytes,
    signature_header: Optional[str],
    source_ip: Optional[str] = None,
) -> dict:
    """Ingest one webhook envelope. Returns counters for the 200 body.

    Raises ``WebhookRejected`` only for authentication failures. Everything
    else — bad JSON, an unknown shape, a single poisonous message inside an
    otherwise good batch — is recorded and counted, and the caller still
    answers 200.
    """
    account = resolve_account(db, account_slug)

    if len(raw_body) > MAX_BODY_BYTES:
        _reject(
            db,
            account,
            REASON_PAYLOAD_TOO_LARGE,
            source_ip=source_ip,
            http_status=413,
            details={"bytes": len(raw_body)},
        )

    _verify_signature(
        db, account, raw_body=raw_body, header=signature_header, source_ip=source_ip
    )

    counters = {
        "messages": 0,
        "message_duplicates": 0,
        "statuses": 0,
        "status_duplicates": 0,
        "skipped": 0,
        "errors": 0,
    }

    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except Exception:  # noqa: BLE001 — bad encoding or bad JSON, same answer
        _note(db, account, REASON_MALFORMED_JSON, source_ip=source_ip)
        counters["skipped"] += 1
        return counters

    if not isinstance(payload, dict) or payload.get("object") != EXPECTED_OBJECT:
        _note(
            db,
            account,
            REASON_UNEXPECTED_OBJECT,
            source_ip=source_ip,
            details={"object": (payload or {}).get("object") if isinstance(payload, dict) else None},
        )
        counters["skipped"] += 1
        return counters

    entries = payload.get("entry")
    if not isinstance(entries, list):
        counters["skipped"] += 1
        return counters

    for entry in entries:
        if not isinstance(entry, dict):
            counters["skipped"] += 1
            continue
        changes = entry.get("changes")
        if not isinstance(changes, list):
            counters["skipped"] += 1
            continue
        for change in changes:
            if not isinstance(change, dict):
                counters["skipped"] += 1
                continue
            try:
                _handle_change(
                    db, account, change, counters=counters, source_ip=source_ip
                )
            except Exception:  # noqa: BLE001 — one bad change must not lose the batch
                db.rollback()
                counters["errors"] += 1
                log.exception(
                    "whatsapp.webhook_change_failed",
                    extra={"account": account.slug, "field": change.get("field")},
                )

    return counters


def _handle_change(
    db: Session,
    account: WhatsAppAccount,
    change: dict,
    *,
    counters: dict,
    source_ip: Optional[str],
) -> None:
    if change.get("field") != FIELD_MESSAGES:
        # message_template_status_update, phone_number_quality_update, … —
        # recognised, not consumed by v1.
        counters["skipped"] += 1
        return

    value = change.get("value")
    if not isinstance(value, dict):
        counters["skipped"] += 1
        return

    # A signed payload still has to be *for this number*, and the check has to
    # hold from both sides. Both QCP numbers normally live under one Meta App
    # and share one ``app_secret``, so a correctly signed envelope for QUATA is
    # equally valid at ``/whatsapp/webhook/quata_verify`` — this comparison is
    # the *only* thing separating them. Skipping it whenever either side is
    # blank meant it was off for the whole provisioning window, because the
    # bootstrap seed writes ``phone_number_id=""``. Fail closed instead: no
    # attribution, no ingestion.
    metadata = value.get("metadata") or {}
    phone_number_id = str(metadata.get("phone_number_id") or "")
    if not account.phone_number_id:
        _note(db, account, REASON_ACCOUNT_PHONE_UNSET, source_ip=source_ip)
        counters["skipped"] += 1
        return
    if not phone_number_id:
        _note(db, account, REASON_MISSING_PHONE_NUMBER_ID, source_ip=source_ip)
        counters["skipped"] += 1
        return
    if phone_number_id != account.phone_number_id:
        _note(
            db,
            account,
            REASON_PHONE_NUMBER_MISMATCH,
            source_ip=source_ip,
            details={"received_phone_number_id": phone_number_id},
        )
        counters["skipped"] += 1
        return

    profiles = _contact_profiles(value.get("contacts"))

    for message in value.get("messages") or []:
        if not isinstance(message, dict):
            counters["skipped"] += 1
            continue
        created = _ingest_message(
            db, account, message, profiles=profiles, source_ip=source_ip
        )
        counters["messages" if created else "message_duplicates"] += 1

    for status in value.get("statuses") or []:
        if not isinstance(status, dict):
            counters["skipped"] += 1
            continue
        created = _ingest_status(db, account, status)
        counters["statuses" if created else "status_duplicates"] += 1

    # Value-level errors (e.g. an account-wide problem Meta wants to tell us
    # about) carry no wamid, so they go to the audit log rather than to
    # whatsapp_delivery_events.
    for err in value.get("errors") or []:
        if not isinstance(err, dict):
            continue
        _note(
            db,
            account,
            REASON_PROVIDER_ERROR,
            source_ip=source_ip,
            outcome=audit.OUTCOME_ERROR,
            details={
                "code": err.get("code"),
                "title": err.get("title"),
                "message": err.get("message"),
            },
        )
        counters["errors"] += 1


# ---------------------------------------------------------------------------
# Inbound messages
# ---------------------------------------------------------------------------

# Meta message type → whatsapp_messages.kind. The rule: `text` for text,
# `interactive` for a tap on something we sent, `reaction` for a reaction,
# `system` for events Meta itself generated, and `media` for anything else
# the *user* attached — including location, contacts and orders, whose
# structured payload lands in the `media` JSON column.
_KIND_BY_TYPE = {
    "text": "text",
    "button": "interactive",
    "interactive": "interactive",
    "reaction": "reaction",
    "image": "media",
    "video": "media",
    "audio": "media",
    "voice": "media",
    "document": "media",
    "sticker": "media",
    "location": "media",
    "contacts": "media",
    "order": "media",
    "system": "system",
    "unsupported": "system",
}

_MEDIA_TYPES = ("image", "video", "audio", "voice", "document", "sticker")


def _contact_profiles(contacts: Any) -> dict[str, str]:
    """``wa_id`` → profile name, from the envelope's ``contacts`` block."""
    out: dict[str, str] = {}
    if not isinstance(contacts, list):
        return out
    for contact in contacts:
        if not isinstance(contact, dict):
            continue
        wa_id = str(contact.get("wa_id") or "").strip()
        name = ((contact.get("profile") or {}) if isinstance(contact.get("profile"), dict) else {}).get("name")
        if wa_id and name:
            out[wa_id] = str(name)
    return out


def _meta_timestamp(value: Any) -> datetime:
    """Meta sends epoch seconds as a string. Fall back to now, never raise."""
    try:
        return datetime.fromtimestamp(int(str(value)), tz=timezone.utc)
    except (TypeError, ValueError, OSError, OverflowError):
        return datetime.now(timezone.utc)


def _to_e164(wa_id: str) -> str:
    """Meta's ``wa_id`` is E.164 without the ``+``. Store it with one."""
    digits = "".join(ch for ch in str(wa_id) if ch.isdigit())
    return f"+{digits}" if digits else str(wa_id)[:24]


def _describe(message: dict, msg_type: str) -> tuple[Optional[str], dict]:
    """Return ``(body, media)`` for one inbound message.

    ``body`` is what a human reads in the admin console. ``media`` is the
    structured payload — the button id a customer tapped, the media handle,
    the coordinates — kept because that is what a product's webhook consumer
    actually branches on.
    """
    media: dict[str, Any] = {"type": msg_type}
    body: Optional[str] = None

    if msg_type == "text":
        body = (message.get("text") or {}).get("body")

    elif msg_type == "button":
        # Quick-reply button on a template we sent.
        button = message.get("button") or {}
        body = button.get("text")
        media.update({"payload": button.get("payload"), "text": button.get("text")})

    elif msg_type == "interactive":
        interactive = message.get("interactive") or {}
        itype = interactive.get("type")
        reply = interactive.get(itype) if isinstance(interactive.get(itype), dict) else {}
        body = reply.get("title")
        media.update(
            {
                "interactive_type": itype,
                "id": reply.get("id"),
                "title": reply.get("title"),
                "description": reply.get("description"),
            }
        )

    elif msg_type == "reaction":
        reaction = message.get("reaction") or {}
        body = reaction.get("emoji")
        media.update(
            {"emoji": reaction.get("emoji"), "message_id": reaction.get("message_id")}
        )

    elif msg_type in _MEDIA_TYPES:
        payload = message.get(msg_type) or {}
        body = payload.get("caption") or payload.get("filename")
        media.update(
            {
                "id": payload.get("id"),
                "mime_type": payload.get("mime_type"),
                "filename": payload.get("filename"),
                "caption": payload.get("caption"),
                "voice": payload.get("voice"),
                "animated": payload.get("animated"),
            }
        )

    elif msg_type == "location":
        location = message.get("location") or {}
        label = location.get("name") or location.get("address")
        body = label or f"{location.get('latitude')},{location.get('longitude')}"
        media.update(
            {
                "latitude": location.get("latitude"),
                "longitude": location.get("longitude"),
                "name": location.get("name"),
                "address": location.get("address"),
            }
        )

    elif msg_type == "contacts":
        names = []
        for contact in message.get("contacts") or []:
            if isinstance(contact, dict):
                names.append(((contact.get("name") or {}).get("formatted_name")) or "")
        body = ", ".join(n for n in names if n) or None
        media.update({"count": len(message.get("contacts") or [])})

    elif msg_type == "order":
        order = message.get("order") or {}
        body = order.get("text")
        media.update(
            {
                "catalog_id": order.get("catalog_id"),
                "item_count": len(order.get("product_items") or []),
            }
        )

    elif msg_type == "system":
        system = message.get("system") or {}
        body = system.get("body")
        media.update(
            {
                "system_type": system.get("type"),
                "new_wa_id": system.get("new_wa_id") or system.get("wa_id"),
            }
        )

    else:
        # "unsupported" and anything Meta ships after this was written.
        errors = message.get("errors") or []
        if errors and isinstance(errors[0], dict):
            body = errors[0].get("title")

    # A reply carries the wamid of the message it answers — this is what
    # lets a product thread a response back onto its own send.
    context = message.get("context")
    if isinstance(context, dict):
        media["context"] = {
            "from": context.get("from"),
            "id": context.get("id"),
            "forwarded": context.get("forwarded"),
        }
    referral = message.get("referral")
    if isinstance(referral, dict):
        media["referral"] = {
            "source_type": referral.get("source_type"),
            "source_id": referral.get("source_id"),
        }

    return body, media


def _ingest_message(
    db: Session,
    account: WhatsAppAccount,
    message: dict,
    *,
    profiles: dict[str, str],
    source_ip: Optional[str],
) -> bool:
    """Persist one inbound message. Returns True if it was new.

    The conversation upsert happens first so a brand-new contact gets a
    thread, but the counters only move when the message itself is new — that
    is the whole redelivery contract in three lines.

    The upsert is passed no ``product_id``: ingest must never decide, or
    change, who owns a thread. Which product this *message* is for is a
    separate, evidence-based question answered by
    ``conversations.attribute_inbound`` below, and its answer is allowed to
    be "nobody".
    """
    wamid = str(message.get("id") or "").strip()
    if not wamid:
        # Nothing to dedupe on. Refusing it is safer than storing something
        # a redelivery would duplicate forever.
        return False

    wa_id = str(message.get("from") or "").strip()
    if not wa_id:
        return False

    existing = (
        db.query(WhatsAppMessage)
        .filter(WhatsAppMessage.provider_message_id == wamid[:80])
        .first()
    )
    if existing is not None:
        db.rollback()
        return False

    conversation = conversations.upsert_conversation(
        db,
        account_id=account.id,
        wa_contact_id=wa_id[:40],
        phone_e164=_to_e164(wa_id),
        display_name=(profiles.get(wa_id) or None) and profiles[wa_id][:120],
    )

    msg_type = str(message.get("type") or "unsupported")
    body, media = _describe(message, msg_type)
    occurred_at = _meta_timestamp(message.get("timestamp"))

    # Who is this reply *for*? Never the thread's owner by default: four
    # products share one conversation row on the engagement number, so
    # ``conversation.product_id`` is a claim on the thread, not evidence
    # about this message. ``attribute_inbound`` prefers Meta's own threading
    # (``context.id``, which no other product can forge) and otherwise
    # answers only when there is exactly one candidate — returning None, and
    # leaving the message admin-console-only, when there is not.
    context = message.get("context")
    context_wamid = None
    if isinstance(context, dict):
        context_wamid = str(context.get("id") or "").strip() or None
    attributed_id, basis, candidates = conversations.attribute_inbound(
        db, conversation, context_wamid=context_wamid
    )

    row = WhatsAppMessage(
        message_uid=uuid.uuid4().hex[:32],
        account_id=account.id,
        account_purpose=account.purpose,
        conversation_id=conversation.id,
        product_id=attributed_id,
        template_id=None,
        direction="inbound",
        kind=_KIND_BY_TYPE.get(msg_type, "system"),
        intent=None,
        to_phone_e164=(account.display_phone or None),
        from_phone_e164=_to_e164(wa_id),
        body=redact_body(body),
        variables={},
        media=redact_details(media),
        provider_message_id=wamid[:80],
        # An inbound message has already arrived; there is nothing to retry.
        status="delivered",
        delivered_at=occurred_at,
        next_attempt_at=None,
        source_ip=source_ip,
    )
    db.add(row)
    # Only reached when the message is genuinely new, so a redelivery can
    # never bump unread_count or re-open the service window a second time.
    conversations.touch_inbound(db, conversation, at=occurred_at)

    if basis == conversations.BASIS_AMBIGUOUS:
        # A real customer message that no product may be handed. It is in the
        # thread and the admin console reads the thread unscoped, but an
        # operator will not go looking, so say so where they already look:
        # a denial row is what the QCP overview's feed is built from.
        audit.record(
            db,
            action="conversation.inbound_unattributed",
            resource_type="whatsapp_conversation",
            resource_id=str(conversation.id),
            outcome=audit.OUTCOME_DENIED,
            reason="ambiguous_inbound",
            account_id=account.id,
            details={"candidate_product_ids": candidates},
        )

    try:
        db.commit()
    except IntegrityError:
        # Lost the race against a concurrent redelivery of the same wamid.
        # The other worker's row is authoritative; ours is discarded whole,
        # conversation counter included.
        db.rollback()
        return False
    return True


# ---------------------------------------------------------------------------
# Status callbacks
# ---------------------------------------------------------------------------

# How far a message has got. A status only ever moves forward — a late
# `sent` arriving after `read` must not walk the row backwards.
_STATUS_RANK = {"queued": 0, "sending": 1, "sent": 2, "delivered": 3, "read": 4}
_STATUS_TIMESTAMP_COLUMN = {
    "sent": "sent_at",
    "delivered": "delivered_at",
    "read": "read_at",
    "failed": "failed_at",
}
# Statuses Meta reports that are not a delivery stage: recorded as evidence,
# but they never move the message's own status.
_NON_PROGRESS_STATUSES = ("deleted", "warning")


def status_dedupe_key(provider_message_id: str, status: str, timestamp: Any) -> str:
    """The key that makes a redelivered status a no-op.

    Hashed rather than concatenated so it always fits ``String(160)`` — a
    ``wamid`` alone can run to 60+ characters. Meta's own timestamp is part
    of the key, so a genuine second ``delivered`` (different second) is a
    distinct event while a replay of the first one is not.
    """
    raw = f"{provider_message_id}|{status}|{timestamp}"
    return "status:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _ingest_status(db: Session, account: WhatsAppAccount, status: dict) -> bool:
    """Record one status callback. Returns True if it was new."""
    wamid = str(status.get("id") or "").strip()
    state = str(status.get("status") or "").strip().lower()
    if not wamid or not state:
        return False

    raw_timestamp = status.get("timestamp")
    dedupe = status_dedupe_key(wamid, state, raw_timestamp)

    existing = (
        db.query(WhatsAppDeliveryEvent)
        .filter(WhatsAppDeliveryEvent.dedupe_key == dedupe)
        .first()
    )
    if existing is not None:
        db.rollback()
        return False

    status_at = _meta_timestamp(raw_timestamp)
    errors = status.get("errors") or []
    first_error = errors[0] if errors and isinstance(errors[0], dict) else {}
    error_detail = first_error.get("message") or (
        (first_error.get("error_data") or {}).get("details")
        if isinstance(first_error.get("error_data"), dict)
        else None
    )
    # Meta authors this text, and it echoes back what it was sent — the same
    # reason the send-failure path scrubs. This is the *other* door: nothing
    # downstream of here filtered it at all, so a rejected call whose error
    # quotes the bearer header landed in three columns in clear. Scrub before
    # truncating, never after: cutting first slices a token in half and leaves
    # the surviving half with nothing left to recognise it by.
    error_title = scrub_provider_text(first_error.get("title") or "")
    error_detail = scrub_provider_text(error_detail or "")
    pricing = status.get("pricing") if isinstance(status.get("pricing"), dict) else {}
    conversation_ref = None
    if isinstance(status.get("conversation"), dict):
        conversation_ref = status["conversation"].get("id")

    message = (
        db.query(WhatsAppMessage)
        .filter(WhatsAppMessage.provider_message_id == wamid[:80])
        .first()
    )

    event = WhatsAppDeliveryEvent(
        message_id=message.id if message else None,
        provider_message_id=wamid[:80],
        account_id=account.id,
        status=state[:20],
        status_at=status_at,
        error_code=(
            scrub_provider_text(str(first_error.get("code")))[:40]
            if first_error.get("code") is not None
            else None
        ),
        error_title=error_title[:200] or None,
        error_detail=error_detail[:500] or None,
        pricing=redact_details(pricing),
        conversation_ref=str(conversation_ref)[:80] if conversation_ref else None,
        dedupe_key=dedupe,
        # ``redact_details`` keys on field *names*; Meta's own error prose is
        # not a named credential field, so the shape scrub runs over the whole
        # structure as well before the envelope is stored.
        raw=scrub_structure(redact_details(status)),
        received_at=datetime.now(timezone.utc),
    )
    db.add(event)

    if message is not None:
        _apply_status(message, state, status_at=status_at, event=event, pricing=pricing)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return False
    return True


def _apply_status(
    message: WhatsAppMessage,
    state: str,
    *,
    status_at: datetime,
    event: WhatsAppDeliveryEvent,
    pricing: dict,
) -> None:
    """Advance a message row from one status callback. Never regresses it."""
    # Fill the stage timestamp even for an out-of-order callback — knowing
    # when Meta says it was sent is information gain either way.
    column = _STATUS_TIMESTAMP_COLUMN.get(state)
    if column and getattr(message, column, None) is None:
        setattr(message, column, status_at)

    if pricing:
        message.pricing_category = str(pricing.get("category") or "")[:20] or None

    if state in _NON_PROGRESS_STATUSES:
        return

    if state == "failed":
        # A message Meta already confirmed as delivered or read did arrive;
        # a later failure is about something else and must not rewrite that.
        if message.status not in ("delivered", "read"):
            message.status = "failed"
            message.next_attempt_at = None
        message.error_code = event.error_code
        # Already scrubbed on the way into ``event`` — see ``_ingest_status``.
        # Copying from the event rather than from ``status`` is what keeps that
        # true, so do not reach back into the raw callback here.
        message.last_error = (event.error_title or event.error_detail or "")[:500] or None
        return

    if state in _STATUS_RANK:
        if _STATUS_RANK[state] > _STATUS_RANK.get(message.status, -1):
            message.status = state
        # Meta has taken the message; the retry sweeper is done with it.
        message.next_attempt_at = None


# ---------------------------------------------------------------------------
# Audit helpers
# ---------------------------------------------------------------------------

def _note(
    db: Session,
    account: Optional[WhatsAppAccount],
    reason: str,
    *,
    source_ip: Optional[str] = None,
    outcome: str = audit.OUTCOME_DENIED,
    details: Optional[dict] = None,
) -> None:
    """Record something we refused to act on, without refusing the request.

    Never raises: an audit-log problem must not turn a 200 into a 500 and
    walk the subscription towards being disabled.
    """
    try:
        audit.record(
            db,
            action="webhook.rejected",
            resource_type="whatsapp_account",
            resource_id=(account.slug if account else None),
            account_id=(account.id if account else None),
            outcome=outcome,
            reason=reason,
            ip_address=source_ip,
            details=details or {},
        )
        db.commit()
    except Exception:  # noqa: BLE001
        db.rollback()
        log.warning("whatsapp.webhook_audit_failed", extra={"reason": reason})
