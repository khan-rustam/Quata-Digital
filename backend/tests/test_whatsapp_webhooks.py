"""Pytest coverage for the QCP inbound webhook.

Three properties are load-bearing and every other test here exists to
support them:

1. **A payload Meta did not sign is refused.** ``test_bad_signature_*`` and
   ``test_missing_signature_*``. If those ever go green-on-accept, anyone who
   learns an account slug can inject conversations and delivery receipts.
2. **A redelivery is a no-op.** Meta re-POSTs the whole envelope when our 200
   is slow or lost. ``test_redelivery_*`` posts the identical bytes three
   times and asserts one message row, one conversation, and an
   ``unread_count`` of exactly 1.
3. **Nothing returns 500.** Meta disables a subscription whose endpoint keeps
   erroring, so malformed JSON, an unknown envelope shape and a wrong phone
   number id must all come back 200.

Everything runs against SQLite, so the composite-FK half of the account
purpose invariant is inert here (see the model docstring); these tests cover
the ingest path, not that invariant — ``test_whatsapp_invariant.py`` owns it.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid
from datetime import datetime, timezone

import pytest

from app.db.session import SessionLocal
from app.models import (
    WhatsAppAccount,
    WhatsAppConversation,
    WhatsAppDeliveryEvent,
    WhatsAppMessage,
)
from app.services.whatsapp import webhooks
from app.services.whatsapp.credentials import encrypt_wa_secret


APP_SECRET = "pytest-app-secret-8f2c"
VERIFY_TOKEN = "pytest-verify-token-91ab"
PHONE_NUMBER_ID = "PNID-PYTEST-0001"
DISPLAY_PHONE = "+237600000001"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def account_slug(app_instance):
    """A dedicated, deliberately INACTIVE account for this module.

    Inactive on purpose: the webhook must accept traffic for an account that
    has not been activated yet (Meta's handshake happens during
    provisioning), and staying inactive keeps this row clear of the partial
    unique index that allows only one live account per purpose — so this
    module cannot collide with the seeded ``quata``/``quata_verify`` rows or
    with any other test module.
    """
    from fastapi.testclient import TestClient

    slug = f"pytest-wh-{uuid.uuid4().hex[:8]}"
    with TestClient(app_instance):  # lifespan → create_all
        with SessionLocal() as db:
            db.add(
                WhatsAppAccount(
                    slug=slug,
                    name="Pytest Engagement",
                    purpose="engagement",
                    phone_number_id=PHONE_NUMBER_ID,
                    waba_id="WABA-PYTEST",
                    display_phone=DISPLAY_PHONE,
                    app_secret_encrypted=encrypt_wa_secret(APP_SECRET),
                    webhook_verify_token_encrypted=encrypt_wa_secret(VERIFY_TOKEN),
                    is_active=False,
                )
            )
            db.commit()
    return slug


@pytest.fixture(scope="module")
def uncredentialled_slug(account_slug):
    """An account with no app secret and no verify token — the fail-closed case."""
    slug = f"pytest-wh-bare-{uuid.uuid4().hex[:8]}"
    with SessionLocal() as db:
        db.add(
            WhatsAppAccount(
                slug=slug,
                name="Pytest Uncredentialled",
                purpose="engagement",
                phone_number_id="PNID-PYTEST-BARE",
                waba_id="WABA-PYTEST",
                display_phone="+237600000002",
                is_active=False,
            )
        )
        db.commit()
    return slug


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _wamid() -> str:
    return f"wamid.PYTEST{uuid.uuid4().hex.upper()}"


def _envelope(
    *,
    messages: list | None = None,
    statuses: list | None = None,
    contacts: list | None = None,
    field: str = "messages",
    obj: str = "whatsapp_business_account",
    phone_number_id: str = PHONE_NUMBER_ID,
) -> dict:
    value: dict = {
        "messaging_product": "whatsapp",
        "metadata": {
            "display_phone_number": DISPLAY_PHONE,
            "phone_number_id": phone_number_id,
        },
    }
    if contacts is not None:
        value["contacts"] = contacts
    if messages is not None:
        value["messages"] = messages
    if statuses is not None:
        value["statuses"] = statuses
    return {
        "object": obj,
        "entry": [{"id": "WABA-PYTEST", "changes": [{"value": value, "field": field}]}],
    }


def _body(envelope: dict) -> bytes:
    return json.dumps(envelope, separators=(",", ":")).encode("utf-8")


def _sign(raw: bytes, secret: str = APP_SECRET) -> str:
    return "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()


def _post(client, slug: str, raw: bytes, *, signature: str | None = "auto"):
    headers = {"Content-Type": "application/json"}
    if signature == "auto":
        headers["X-Hub-Signature-256"] = _sign(raw)
    elif signature is not None:
        headers["X-Hub-Signature-256"] = signature
    return client.post(f"/api/v1/whatsapp/webhook/{slug}", content=raw, headers=headers)


def _text_message(wamid: str, sender: str, text: str = "hello there") -> dict:
    return {
        "from": sender,
        "id": wamid,
        "timestamp": "1780000000",
        "type": "text",
        "text": {"body": text},
    }


def _message_row(wamid: str):
    with SessionLocal() as db:
        return (
            db.query(WhatsAppMessage)
            .filter(WhatsAppMessage.provider_message_id == wamid)
            .first()
        )


def _conversation(slug: str, wa_id: str):
    with SessionLocal() as db:
        account = db.query(WhatsAppAccount).filter(WhatsAppAccount.slug == slug).first()
        return (
            db.query(WhatsAppConversation)
            .filter(
                WhatsAppConversation.account_id == account.id,
                WhatsAppConversation.wa_contact_id == wa_id,
            )
            .first()
        )


def _outbound_row(slug: str, wamid: str) -> str:
    """Insert an outbound message the status callbacks can land on."""
    uid = uuid.uuid4().hex[:32]
    with SessionLocal() as db:
        account = db.query(WhatsAppAccount).filter(WhatsAppAccount.slug == slug).first()
        db.add(
            WhatsAppMessage(
                message_uid=uid,
                account_id=account.id,
                account_purpose=account.purpose,
                direction="outbound",
                kind="text",
                to_phone_e164="+237699000111",
                provider_message_id=wamid,
                status="sending",
                next_attempt_at=datetime.now(timezone.utc),
            )
        )
        db.commit()
    return uid


def _events(wamid: str) -> list:
    with SessionLocal() as db:
        return (
            db.query(WhatsAppDeliveryEvent)
            .filter(WhatsAppDeliveryEvent.provider_message_id == wamid)
            .all()
        )


# ---------------------------------------------------------------------------
# GET — the verification handshake
# ---------------------------------------------------------------------------

def test_handshake_echoes_challenge_verbatim(client, account_slug):
    """Meta compares the response body byte for byte — it must be raw text."""
    r = client.get(
        f"/api/v1/whatsapp/webhook/{account_slug}",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": VERIFY_TOKEN,
            "hub.challenge": "1158201444",
        },
    )
    assert r.status_code == 200, r.text
    assert r.text == "1158201444"
    assert r.headers["content-type"].startswith("text/plain")


def test_handshake_rejects_wrong_token(client, account_slug):
    r = client.get(
        f"/api/v1/whatsapp/webhook/{account_slug}",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "not-the-token",
            "hub.challenge": "123",
        },
    )
    assert r.status_code == 403
    assert "123" not in r.text


def test_handshake_rejects_wrong_mode(client, account_slug):
    r = client.get(
        f"/api/v1/whatsapp/webhook/{account_slug}",
        params={
            "hub.mode": "unsubscribe",
            "hub.verify_token": VERIFY_TOKEN,
            "hub.challenge": "123",
        },
    )
    assert r.status_code == 403


def test_handshake_unknown_account_is_404(client):
    r = client.get(
        "/api/v1/whatsapp/webhook/no-such-account",
        params={"hub.mode": "subscribe", "hub.verify_token": VERIFY_TOKEN, "hub.challenge": "9"},
    )
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# POST — signature
# ---------------------------------------------------------------------------

def test_valid_signature_is_accepted_and_ingested(client, account_slug):
    wamid, sender = _wamid(), "237677000111"
    raw = _body(
        _envelope(
            contacts=[{"profile": {"name": "Amina"}, "wa_id": sender}],
            messages=[_text_message(wamid, sender, "is my order out?")],
        )
    )
    r = _post(client, account_slug, raw)
    assert r.status_code == 200, r.text
    assert r.json()["messages"] == 1

    row = _message_row(wamid)
    assert row is not None
    assert row.direction == "inbound"
    assert row.kind == "text"
    assert row.body == "is my order out?"
    assert row.from_phone_e164 == f"+{sender}"
    assert row.status == "delivered"
    assert row.account_purpose == "engagement"

    convo = _conversation(account_slug, sender)
    assert convo is not None
    assert convo.display_name == "Amina"
    assert convo.unread_count == 1
    assert convo.service_window_expires_at is not None


def test_bad_signature_is_rejected_and_writes_nothing(client, account_slug):
    wamid, sender = _wamid(), "237677000222"
    raw = _body(_envelope(messages=[_text_message(wamid, sender)]))
    forged = "sha256=" + hmac.new(b"wrong-secret", raw, hashlib.sha256).hexdigest()

    r = _post(client, account_slug, raw, signature=forged)
    assert r.status_code == 403
    assert r.json()["reason"] == webhooks.REASON_BAD_SIGNATURE
    assert _message_row(wamid) is None
    assert _conversation(account_slug, sender) is None


def test_missing_signature_is_rejected(client, account_slug):
    wamid, sender = _wamid(), "237677000333"
    raw = _body(_envelope(messages=[_text_message(wamid, sender)]))

    r = _post(client, account_slug, raw, signature=None)
    assert r.status_code == 403
    assert r.json()["reason"] == webhooks.REASON_MISSING_SIGNATURE
    assert _message_row(wamid) is None


def test_signature_over_mutated_body_is_rejected(client, account_slug):
    """Signing one body and posting another must not pass."""
    sender = "237677000444"
    signed = _body(_envelope(messages=[_text_message(_wamid(), sender, "original")]))
    posted = _body(_envelope(messages=[_text_message(_wamid(), sender, "tampered")]))

    r = _post(client, account_slug, posted, signature=_sign(signed))
    assert r.status_code == 403


def test_webhook_for_unknown_account_is_404(client):
    raw = _body(_envelope(messages=[_text_message(_wamid(), "237677000555")]))
    r = _post(client, "no-such-account", raw)
    assert r.status_code == 404


def test_account_without_an_app_secret_fails_closed(client, uncredentialled_slug):
    """No secret means nothing can be authenticated, so nothing is trusted.

    The tempting alternative — "no secret configured, so skip the check" —
    would make an account one blank field away from accepting anything.
    """
    wamid, sender = _wamid(), "237677002222"
    raw = _body(_envelope(messages=[_text_message(wamid, sender)]))

    r = _post(client, uncredentialled_slug, raw)
    assert r.status_code == 403
    assert r.json()["reason"] == webhooks.REASON_NO_APP_SECRET
    assert _message_row(wamid) is None


def test_handshake_without_a_verify_token_fails_closed(client, uncredentialled_slug):
    r = client.get(
        f"/api/v1/whatsapp/webhook/{uncredentialled_slug}",
        params={"hub.mode": "subscribe", "hub.verify_token": "anything", "hub.challenge": "77"},
    )
    assert r.status_code == 403
    assert r.text == webhooks.REASON_NO_VERIFY_TOKEN


def test_unsigned_payload_is_accepted_only_when_signatures_are_off(
    client, account_slug, monkeypatch
):
    """The dev escape hatch works — and proves the default is the opposite."""
    wamid, sender = _wamid(), "237677003333"
    raw = _body(_envelope(messages=[_text_message(wamid, sender, "unsigned")]))

    monkeypatch.setattr(webhooks.settings_store, "require_signature", lambda: False)
    r = _post(client, account_slug, raw, signature=None)
    assert r.status_code == 200
    assert r.json()["messages"] == 1
    assert _message_row(wamid) is not None


# ---------------------------------------------------------------------------
# POST — redelivery
# ---------------------------------------------------------------------------

def test_redelivery_of_a_message_is_a_noop(client, account_slug):
    """Meta re-POSTs the entire envelope. Three identical deliveries must
    leave exactly one message, one conversation, and unread_count == 1."""
    wamid, sender = _wamid(), "237677000666"
    raw = _body(
        _envelope(
            contacts=[{"profile": {"name": "Bertrand"}, "wa_id": sender}],
            messages=[_text_message(wamid, sender, "still waiting")],
        )
    )

    first = _post(client, account_slug, raw)
    assert first.status_code == 200
    assert first.json()["messages"] == 1

    for _ in range(2):
        again = _post(client, account_slug, raw)
        assert again.status_code == 200
        assert again.json()["messages"] == 0
        assert again.json()["message_duplicates"] == 1

    with SessionLocal() as db:
        assert (
            db.query(WhatsAppMessage)
            .filter(WhatsAppMessage.provider_message_id == wamid)
            .count()
            == 1
        )
    convo = _conversation(account_slug, sender)
    assert convo.unread_count == 1


def test_redelivery_of_a_status_is_a_noop(client, account_slug):
    wamid = _wamid()
    _outbound_row(account_slug, wamid)
    raw = _body(
        _envelope(
            statuses=[
                {
                    "id": wamid,
                    "status": "delivered",
                    "timestamp": "1780000100",
                    "recipient_id": "237699000111",
                    "conversation": {"id": "CONV-1"},
                    "pricing": {"billable": True, "category": "utility", "pricing_model": "CBP"},
                }
            ]
        )
    )

    first = _post(client, account_slug, raw)
    assert first.json()["statuses"] == 1
    second = _post(client, account_slug, raw)
    assert second.json()["statuses"] == 0
    assert second.json()["status_duplicates"] == 1

    assert len(_events(wamid)) == 1


# ---------------------------------------------------------------------------
# POST — status receipts
# ---------------------------------------------------------------------------

def test_status_receipts_advance_the_message(client, account_slug):
    wamid = _wamid()
    _outbound_row(account_slug, wamid)

    for state, ts in (("sent", "1780000200"), ("delivered", "1780000210"), ("read", "1780000220")):
        raw = _body(_envelope(statuses=[{"id": wamid, "status": state, "timestamp": ts}]))
        assert _post(client, account_slug, raw).json()["statuses"] == 1

    row = _message_row(wamid)
    assert row.status == "read"
    assert row.sent_at is not None
    assert row.delivered_at is not None
    assert row.read_at is not None
    # Terminal: the retry sweeper must not pick it up again.
    assert row.next_attempt_at is None
    assert len(_events(wamid)) == 3


def test_out_of_order_status_does_not_regress(client, account_slug):
    """A late `sent` arriving after `read` must not walk the row backwards."""
    wamid = _wamid()
    _outbound_row(account_slug, wamid)

    read = _body(_envelope(statuses=[{"id": wamid, "status": "read", "timestamp": "1780000320"}]))
    assert _post(client, account_slug, read).json()["statuses"] == 1
    late = _body(_envelope(statuses=[{"id": wamid, "status": "sent", "timestamp": "1780000300"}]))
    assert _post(client, account_slug, late).json()["statuses"] == 1

    row = _message_row(wamid)
    assert row.status == "read"
    # The stage timestamp is still recorded — information gain either way.
    assert row.sent_at is not None


def test_failed_status_records_the_error(client, account_slug):
    wamid = _wamid()
    _outbound_row(account_slug, wamid)
    raw = _body(
        _envelope(
            statuses=[
                {
                    "id": wamid,
                    "status": "failed",
                    "timestamp": "1780000400",
                    "errors": [
                        {
                            "code": 131047,
                            "title": "Re-engagement message",
                            "message": "More than 24 hours have passed.",
                            "error_data": {"details": "outside window"},
                        }
                    ],
                }
            ]
        )
    )
    assert _post(client, account_slug, raw).json()["statuses"] == 1

    row = _message_row(wamid)
    assert row.status == "failed"
    assert row.error_code == "131047"
    assert row.failed_at is not None
    assert row.next_attempt_at is None

    event = _events(wamid)[0]
    assert event.error_title == "Re-engagement message"
    assert event.error_detail == "More than 24 hours have passed."


def test_status_for_unknown_wamid_is_still_recorded(client, account_slug):
    """A message sent from Meta's own inbox, or one predating QCP."""
    wamid = _wamid()
    raw = _body(_envelope(statuses=[{"id": wamid, "status": "delivered", "timestamp": "1780000500"}]))
    assert _post(client, account_slug, raw).json()["statuses"] == 1

    events = _events(wamid)
    assert len(events) == 1
    assert events[0].message_id is None


# ---------------------------------------------------------------------------
# POST — message kinds
# ---------------------------------------------------------------------------

def test_button_reply_is_interactive(client, account_slug):
    wamid, sender = _wamid(), "237677000777"
    raw = _body(
        _envelope(
            messages=[
                {
                    "from": sender,
                    "id": wamid,
                    "timestamp": "1780000600",
                    "type": "button",
                    "button": {"payload": "TRACK_ORDER", "text": "Track my order"},
                    "context": {"from": DISPLAY_PHONE, "id": "wamid.ORIGINAL"},
                }
            ]
        )
    )
    assert _post(client, account_slug, raw).json()["messages"] == 1

    row = _message_row(wamid)
    assert row.kind == "interactive"
    assert row.body == "Track my order"
    assert row.media["payload"] == "TRACK_ORDER"
    assert row.media["context"]["id"] == "wamid.ORIGINAL"


def test_list_reply_is_interactive(client, account_slug):
    wamid, sender = _wamid(), "237677000888"
    raw = _body(
        _envelope(
            messages=[
                {
                    "from": sender,
                    "id": wamid,
                    "timestamp": "1780000610",
                    "type": "interactive",
                    "interactive": {
                        "type": "list_reply",
                        "list_reply": {
                            "id": "SKU-42",
                            "title": "Jollof rice",
                            "description": "Family size",
                        },
                    },
                }
            ]
        )
    )
    assert _post(client, account_slug, raw).json()["messages"] == 1

    row = _message_row(wamid)
    assert row.kind == "interactive"
    assert row.media["interactive_type"] == "list_reply"
    assert row.media["id"] == "SKU-42"


def test_media_location_reaction_and_system_kinds(client, account_slug):
    sender = "237677000999"
    image_id, loc_id, react_id, sys_id = _wamid(), _wamid(), _wamid(), _wamid()
    raw = _body(
        _envelope(
            messages=[
                {
                    "from": sender,
                    "id": image_id,
                    "timestamp": "1780000700",
                    "type": "image",
                    "image": {
                        "id": "MEDIA-1",
                        "mime_type": "image/jpeg",
                        "caption": "the receipt",
                    },
                },
                {
                    "from": sender,
                    "id": loc_id,
                    "timestamp": "1780000701",
                    "type": "location",
                    "location": {
                        "latitude": 4.0511,
                        "longitude": 9.7679,
                        "name": "Akwa",
                        "address": "Douala",
                    },
                },
                {
                    "from": sender,
                    "id": react_id,
                    "timestamp": "1780000702",
                    "type": "reaction",
                    "reaction": {"message_id": "wamid.OURS", "emoji": "👍"},
                },
                {
                    "from": sender,
                    "id": sys_id,
                    "timestamp": "1780000703",
                    "type": "system",
                    "system": {"body": "User changed number", "new_wa_id": "237699111222",
                               "type": "user_changed_number"},
                },
            ]
        )
    )
    assert _post(client, account_slug, raw).json()["messages"] == 4

    assert _message_row(image_id).kind == "media"
    assert _message_row(image_id).media["mime_type"] == "image/jpeg"
    location = _message_row(loc_id)
    assert location.kind == "media"
    assert location.media["latitude"] == 4.0511
    assert _message_row(react_id).kind == "reaction"
    assert _message_row(sys_id).kind == "system"

    # Four messages, one thread, four unread.
    assert _conversation(account_slug, sender).unread_count == 4


def test_unsupported_type_does_not_break_ingestion(client, account_slug):
    wamid, sender = _wamid(), "237677001010"
    raw = _body(
        _envelope(
            messages=[
                {
                    "from": sender,
                    "id": wamid,
                    "timestamp": "1780000800",
                    "type": "unsupported",
                    "errors": [{"code": 131051, "title": "Message type not supported"}],
                }
            ]
        )
    )
    assert _post(client, account_slug, raw).status_code == 200
    assert _message_row(wamid).kind == "system"


# ---------------------------------------------------------------------------
# POST — malformed and hostile payloads must never 500
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "raw",
    [
        b"",
        b"not json at all",
        b"{",
        b"[]",
        b'{"object":"whatsapp_business_account"}',
        b'{"object":"whatsapp_business_account","entry":"nope"}',
        b'{"object":"whatsapp_business_account","entry":[{"changes":[{"field":"messages"}]}]}',
        b'{"object":"page","entry":[]}',
        b'{"object":"whatsapp_business_account","entry":[{"changes":[{"field":"messages","value":{"messages":[{}]}}]}]}',
    ],
)
def test_malformed_payloads_return_200(client, account_slug, raw):
    r = _post(client, account_slug, raw)
    assert r.status_code == 200, f"{raw!r} → {r.status_code} {r.text}"
    assert r.json()["ok"] is True


def test_unknown_change_field_is_skipped(client, account_slug):
    raw = _body(_envelope(messages=[], field="message_template_status_update"))
    r = _post(client, account_slug, raw)
    assert r.status_code == 200
    assert r.json()["skipped"] == 1


def test_phone_number_id_mismatch_is_ignored(client, account_slug):
    """A signed envelope for a *different* number must not be ingested here."""
    wamid, sender = _wamid(), "237677001111"
    raw = _body(
        _envelope(
            messages=[_text_message(wamid, sender)],
            phone_number_id="PNID-SOMEONE-ELSE",
        )
    )
    r = _post(client, account_slug, raw)
    assert r.status_code == 200
    assert r.json()["messages"] == 0
    assert _message_row(wamid) is None


def test_oversized_body_is_rejected(client, account_slug):
    raw = b'{"object":"whatsapp_business_account","padding":"' + b"x" * (
        webhooks.MAX_BODY_BYTES + 10
    ) + b'"}'
    r = _post(client, account_slug, raw)
    assert r.status_code == 413
    assert r.json()["reason"] == webhooks.REASON_PAYLOAD_TOO_LARGE


# ---------------------------------------------------------------------------
# Dedupe key
# ---------------------------------------------------------------------------

def test_status_dedupe_key_is_stable_and_bounded():
    wamid = "wamid." + "A" * 70
    key = webhooks.status_dedupe_key(wamid, "delivered", "1780000000")
    assert key == webhooks.status_dedupe_key(wamid, "delivered", "1780000000")
    assert key != webhooks.status_dedupe_key(wamid, "read", "1780000000")
    assert key != webhooks.status_dedupe_key(wamid, "delivered", "1780000001")
    # Must fit whatsapp_delivery_events.dedupe_key — String(160).
    assert len(key) <= 160


# ---------------------------------------------------------------------------
# The signature switch has an environment floor
# ---------------------------------------------------------------------------
#
# ``whatsapp.require_signature`` gates the only internet-facing door QCP
# opens *and* the product-facing X-QCP-Signature check. If the DB row wins,
# one PUT by anyone holding ``settings:manage`` turns
# POST /whatsapp/webhook/{slug} into an unauthenticated write API: forged
# inbound messages, forged conversations on the Verify number, forged status
# callbacks marking real messages delivered or failed.

@pytest.fixture
def signature_setting(client):
    """Write ``whatsapp.require_signature`` and remove it afterwards.

    Written straight to ``site_settings`` because ``set_setting`` refuses keys
    the seed catalogue has not declared yet — which is the only reason this
    defect is latent rather than live.
    """
    from app.models import SiteSetting
    from app.services import site_settings
    from app.services.whatsapp import settings_store

    key = settings_store.KEY_REQUIRE_SIGNATURE

    def _set(value: str):
        with SessionLocal() as db:
            row = db.query(SiteSetting).filter(SiteSetting.key == key).first()
            if row is None:
                row = SiteSetting(
                    key=key,
                    group=settings_store.GROUP,
                    label="Require signature",
                    field_type="toggle",
                )
                db.add(row)
            row.value = value
            db.commit()
        site_settings.invalidate_cache()

    yield _set

    with SessionLocal() as db:
        db.query(SiteSetting).filter(SiteSetting.key == key).delete()
        db.commit()
    site_settings.invalidate_cache()


def test_db_row_cannot_switch_signature_checking_off(
    client, account_slug, signature_setting
):
    """``WHATSAPP_REQUIRE_SIGNATURE`` is a floor, not a default.

    Same shape as ``delivery_enabled`` two functions above: the environment
    decides, and no admin toggle may cross it. Only the direction differs —
    there the unsafe state is *on*, here it is *off*.
    """
    from app.services.whatsapp import settings_store

    signature_setting("false")
    assert settings_store.require_signature() is True

    wamid, sender = _wamid(), "237677004444"
    raw = _body(_envelope(messages=[_text_message(wamid, sender, "forged")]))

    unsigned = _post(client, account_slug, raw, signature=None)
    assert unsigned.status_code == 403, unsigned.text

    forged = "sha256=" + hmac.new(b"not-the-secret", raw, hashlib.sha256).hexdigest()
    assert _post(client, account_slug, raw, signature=forged).status_code == 403

    assert _message_row(wamid) is None
    assert _conversation(account_slug, sender) is None


def test_db_row_can_still_add_strictness_when_the_env_floor_is_down(
    account_slug, signature_setting, monkeypatch
):
    """The key is not dead: with the env floor lowered the row still decides."""
    from app.core.config import settings as env_settings
    from app.services.whatsapp import settings_store

    monkeypatch.setattr(env_settings, "WHATSAPP_REQUIRE_SIGNATURE", False)
    signature_setting("false")
    assert settings_store.require_signature() is False
    signature_setting("true")
    assert settings_store.require_signature() is True


# ---------------------------------------------------------------------------
# Non-ASCII header bytes must not turn a refusal into an exception
# ---------------------------------------------------------------------------
#
# ``hmac.compare_digest`` raises TypeError on a non-ASCII ``str`` and
# Starlette decodes headers as latin-1, so the value is fully attacker
# controlled. On the POST webhook the broad ``except Exception`` converts the
# intended 403 into 200 {"ok": true} — an unauthenticated caller gets SUCCESS
# out of the one endpoint whose entire contract is "403 means you are not
# Meta". On the GET handshake and on ``current_product`` it is a 500.

NON_ASCII_HEX = b"sha256=" + b"\xe9" * 64


def test_non_ascii_signature_header_is_refused_not_acknowledged(client, account_slug):
    wamid, sender = _wamid(), "237677005555"
    raw = _body(_envelope(messages=[_text_message(wamid, sender, "latin-1")]))

    r = client.post(
        f"/api/v1/whatsapp/webhook/{account_slug}",
        content=raw,
        headers={b"Content-Type": b"application/json", b"X-Hub-Signature-256": NON_ASCII_HEX},
    )
    assert r.status_code == 403, r.text
    assert r.json()["reason"] == webhooks.REASON_BAD_SIGNATURE
    assert _message_row(wamid) is None


@pytest.mark.parametrize(
    "supplied",
    [
        b"sha256=" + b"z" * 64,          # right length, not hex
        b"sha256=" + b"ab" * 20,         # hex, wrong length
        b"sha256=",                      # empty digest
        b"\xe9" * 64,                    # non-ASCII, no prefix
    ],
)
def test_malformed_signature_shapes_are_refused(client, account_slug, supplied):
    raw = _body(_envelope(messages=[_text_message(_wamid(), "237677005566")]))
    r = client.post(
        f"/api/v1/whatsapp/webhook/{account_slug}",
        content=raw,
        headers={b"Content-Type": b"application/json", b"X-Hub-Signature-256": supplied},
    )
    assert r.status_code == 403, r.text


def test_non_ascii_verify_token_is_refused_not_a_500(client, account_slug):
    r = client.get(
        f"/api/v1/whatsapp/webhook/{account_slug}",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "cafés-and-crêpes-éé",
            "hub.challenge": "4242",
        },
    )
    assert r.status_code == 403, r.text
    assert "4242" not in r.text


def test_is_sha256_hex_accepts_only_a_64_char_digest():
    assert webhooks.is_sha256_hex("a" * 64) is True
    assert webhooks.is_sha256_hex("A" * 64) is True
    assert webhooks.is_sha256_hex("é" * 64) is False
    assert webhooks.is_sha256_hex("a" * 63) is False
    assert webhooks.is_sha256_hex("a" * 65) is False
    assert webhooks.is_sha256_hex("") is False
    assert webhooks.is_sha256_hex(None) is False


# ---------------------------------------------------------------------------
# Product-facing signature — same header-bytes hazard
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def qcp_product(account_slug):
    """A product with a real key, so ``current_product`` reaches the HMAC."""
    from app.models import WhatsAppProduct

    slug = f"pytest-sig-{uuid.uuid4().hex[:8]}"
    raw_key = f"qcp_live_{uuid.uuid4().hex}"
    with SessionLocal() as db:
        db.add(
            WhatsAppProduct(
                slug=slug,
                name="Pytest Signature Product",
                is_enabled=True,
                api_key_hash=hashlib.sha256(raw_key.encode()).hexdigest(),
                allowed_purposes=["engagement"],
            )
        )
        db.commit()
    return slug, raw_key


def test_non_ascii_product_signature_is_401_not_500(client, qcp_product):
    slug, raw_key = qcp_product
    r = client.get(
        "/api/v1/whatsapp/health",
        headers={
            b"X-QCP-Product": slug.encode(),
            b"X-QCP-Key": raw_key.encode(),
            b"X-QCP-Timestamp": str(int(time.time())).encode(),
            b"X-QCP-Signature": b"\xe9" * 64,
        },
    )
    assert r.status_code == 401, r.text


# ---------------------------------------------------------------------------
# Cross-number attribution must fail closed
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def unprovisioned_slug(account_slug):
    """An account still carrying the bootstrap seed's empty phone_number_id.

    Both QCP numbers normally live under one Meta App and share one
    ``app_secret``, so a correctly signed envelope for QUATA is equally valid
    at ``/whatsapp/webhook/quata_verify``. The ``phone_number_id`` comparison
    is the *only* thing separating them.
    """
    slug = f"pytest-wh-unprov-{uuid.uuid4().hex[:8]}"
    with SessionLocal() as db:
        db.add(
            WhatsAppAccount(
                slug=slug,
                name="Pytest Unprovisioned",
                purpose="authentication",
                phone_number_id="",
                waba_id="WABA-PYTEST",
                display_phone="+237600000003",
                app_secret_encrypted=encrypt_wa_secret(APP_SECRET),
                webhook_verify_token_encrypted=encrypt_wa_secret(VERIFY_TOKEN),
                is_active=False,
            )
        )
        db.commit()
    return slug


def test_account_without_a_phone_number_id_refuses_ingestion(client, unprovisioned_slug):
    """A signed envelope for *some* number is not evidence it is for this one."""
    wamid, sender = _wamid(), "237677006666"
    raw = _body(
        _envelope(
            messages=[_text_message(wamid, sender, "wrong number")],
            phone_number_id="PNID-SOMEONE-ELSE",
        )
    )
    r = _post(client, unprovisioned_slug, raw)

    # 200, not 403: Meta disables a subscription whose endpoint keeps erroring.
    assert r.status_code == 200, r.text
    assert r.json()["messages"] == 0
    assert r.json()["skipped"] == 1
    assert _message_row(wamid) is None
    assert _conversation(unprovisioned_slug, sender) is None
    assert _audit_reasons(webhooks.REASON_ACCOUNT_PHONE_UNSET) >= 1


def test_envelope_without_a_phone_number_id_is_not_attributed(client, account_slug):
    """The account knows its number; the payload has to name one too."""
    wamid, sender = _wamid(), "237677006677"
    raw = _body(_envelope(messages=[_text_message(wamid, sender)], phone_number_id=""))
    r = _post(client, account_slug, raw)
    assert r.status_code == 200, r.text
    assert r.json()["messages"] == 0
    assert _message_row(wamid) is None


# ---------------------------------------------------------------------------
# Failed authentication is not an unbounded write primitive
# ---------------------------------------------------------------------------

def _audit_reasons(reason: str) -> int:
    from app.models import WhatsAppAuditLog

    with SessionLocal() as db:
        return (
            db.query(WhatsAppAuditLog)
            .filter(WhatsAppAuditLog.reason == reason)
            .count()
        )


def test_repeated_forged_posts_do_not_write_a_row_each(client, account_slug):
    """The webhook is deliberately not rate-limited — shedding Meta's
    redelivery bursts is how a subscription gets disabled. That makes the
    audit log the write primitive instead, so identical refusals collapse."""
    webhooks.reset_rejection_windows()
    before = _audit_reasons(webhooks.REASON_BAD_SIGNATURE)

    raw = _body(_envelope(messages=[_text_message(_wamid(), "237677007777")]))
    forged = "sha256=" + hmac.new(b"wrong-secret", raw, hashlib.sha256).hexdigest()
    for _ in range(25):
        r = _post(client, account_slug, raw, signature=forged)
        # Every one of them is still refused — collapsing is about the writes.
        assert r.status_code == 403
        assert r.json()["reason"] == webhooks.REASON_BAD_SIGNATURE

    written = _audit_reasons(webhooks.REASON_BAD_SIGNATURE) - before
    assert written == 1, f"{written} audit rows for 25 forged posts"


def test_a_different_reason_still_gets_its_own_row(client, account_slug, uncredentialled_slug):
    """Collapsing is per (account, source ip, reason) — it must not swallow
    the *first* sighting of a different refusal."""
    webhooks.reset_rejection_windows()
    raw = _body(_envelope(messages=[_text_message(_wamid(), "237677007788")]))

    before_missing = _audit_reasons(webhooks.REASON_MISSING_SIGNATURE)
    before_secret = _audit_reasons(webhooks.REASON_NO_APP_SECRET)

    assert _post(client, account_slug, raw, signature=None).status_code == 403
    assert _post(client, uncredentialled_slug, raw).status_code == 403

    assert _audit_reasons(webhooks.REASON_MISSING_SIGNATURE) == before_missing + 1
    assert _audit_reasons(webhooks.REASON_NO_APP_SECRET) == before_secret + 1


def test_a_new_window_records_how_many_were_suppressed(client, account_slug, monkeypatch):
    """Evidence is collapsed, not lost."""
    from app.models import WhatsAppAuditLog

    webhooks.reset_rejection_windows()
    raw = _body(_envelope(messages=[_text_message(_wamid(), "237677007799")]))
    forged = "sha256=" + hmac.new(b"other-secret", raw, hashlib.sha256).hexdigest()

    for _ in range(4):
        assert _post(client, account_slug, raw, signature=forged).status_code == 403

    # Roll the window over; the next refusal reports the three it covered for.
    monkeypatch.setattr(webhooks, "REJECT_COLLAPSE_WINDOW_SECONDS", 0)
    assert _post(client, account_slug, raw, signature=forged).status_code == 403

    with SessionLocal() as db:
        row = (
            db.query(WhatsAppAuditLog)
            .filter(WhatsAppAuditLog.reason == webhooks.REASON_BAD_SIGNATURE)
            .order_by(WhatsAppAuditLog.id.desc())
            .first()
        )
    assert (row.details or {}).get("suppressed_repeats") == 3


# ---------------------------------------------------------------------------
# QCP rate limiting — before the credential check, keyed on the product
# ---------------------------------------------------------------------------

def _scope_request(headers: dict[str, str], client_host: str = "10.0.0.7"):
    from starlette.requests import Request

    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/api/v1/whatsapp/health",
            "raw_path": b"/api/v1/whatsapp/health",
            "query_string": b"",
            "root_path": "",
            "server": ("testserver", 80),
            "client": (client_host, 51234),
            "headers": [
                (k.lower().encode(), v.encode()) for k, v in headers.items()
            ],
        }
    )


def test_rate_limit_bucket_is_per_product_not_per_address():
    """QuataPay, QuataFood and Abaqwa can egress through one NAT address.
    An ``ip:`` bucket lets one product's burst rate-limit another's OTPs."""
    from app.api import routes_whatsapp

    pay = routes_whatsapp._qcp_rate_key(_scope_request({"X-QCP-Product": "quatapay"}))
    food = routes_whatsapp._qcp_rate_key(_scope_request({"X-QCP-Product": "quatafood"}))
    pay_again = routes_whatsapp._qcp_rate_key(
        _scope_request({"X-QCP-Product": "QuataPay"})
    )
    anonymous = routes_whatsapp._qcp_rate_key(_scope_request({}))

    assert pay != food
    assert pay == pay_again          # case-folded, same product, same address
    assert anonymous not in (pay, food)


def test_bad_credentials_are_rate_limited_before_they_reach_the_database(
    client, monkeypatch
):
    """Every guess used to cost a SELECT and a commit, on a route that carried
    no limiter at all."""
    from app.api import routes_whatsapp

    monkeypatch.setattr(routes_whatsapp, "QCP_RATE_LIMIT", "3/minute")
    slug = f"pytest-rl-{uuid.uuid4().hex[:10]}"
    headers = {"X-QCP-Product": slug, "X-QCP-Key": "not-a-real-key"}

    codes = [
        client.get("/api/v1/whatsapp/health", headers=headers).status_code
        for _ in range(5)
    ]
    assert codes[:3] == [401, 401, 401], codes
    assert codes[3:] == [429, 429], codes
