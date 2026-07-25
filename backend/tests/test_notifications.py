"""Pytest coverage for the QUATA Notification Service (@QuataAlertsBot).

Delivery itself is never exercised against the real Telegram API — the test
environment has no bot token, so every event settles as `pending` (retryable)
or `suppressed`. That's exactly the boundary worth testing: everything up to
the transport must be correct, deterministic and safe.

The security assertions here are the load-bearing ones. If
``test_secrets_are_never_persisted_or_rendered`` ever fails, a password or an
OTP has reached the audit table and, from there, a Telegram group.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import time
from datetime import timezone

import pytest

from app.db.session import SessionLocal
from app.models import NotificationEvent
from app.services.notifications import catalog, dispatch, settings_store
from app.services.notifications.formatter import format_amount, render
from app.services.notifications.redaction import (
    REDACTED,
    is_secret_key,
    mask_identifier,
    redact_payload,
)


INGEST_PLATFORM = "quatapay"
INGEST_KEY = "pytest-ingest-key"


@pytest.fixture(autouse=True)
def _ingest_key(monkeypatch):
    """Give the ingest endpoint one configured platform for the whole module.

    ``notify_ingest_keys`` is a property over ``NOTIFY_INGEST_KEYS``, so
    patching the underlying list is enough and no cache needs clearing.
    """
    from app.core.config import settings as env_settings

    monkeypatch.setattr(
        env_settings, "NOTIFY_INGEST_KEYS", [f"{INGEST_PLATFORM}:{INGEST_KEY}"]
    )
    yield


def _row(event_id: str) -> NotificationEvent:
    with SessionLocal() as db:
        row = (
            db.query(NotificationEvent)
            .filter(NotificationEvent.event_id == event_id)
            .first()
        )
        assert row is not None, f"no notification_events row for {event_id}"
        db.expunge(row)
        return row


# ---------------------------------------------------------------------------
# Redaction — the security contract
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "key",
    [
        "password", "Password", "user_password", "passwordHash",
        "otp", "OTP_CODE", "totp", "pin", "pinCode",
        "api_key", "apiKey", "X-API-KEY", "access_token", "refreshToken",
        "authorization", "secret", "client_secret", "cvv", "seed_phrase",
        "mnemonic", "private_key", "session_id", "signature",
    ],
)
def test_credential_field_names_are_detected(key):
    assert is_secret_key(key), f"{key!r} must be treated as a credential"


@pytest.mark.parametrize("key", ["pinned_at", "keyboard", "codename", "author", "hashtag_count"])
def test_ordinary_field_names_are_not_over_matched(key):
    """The deny-list must not swallow innocent fields — over-redaction
    silently strips the detail an administrator needs."""
    assert not is_secret_key(key)


def test_secrets_are_stripped_recursively():
    payload = redact_payload(
        {
            "full_name": "John Doe",
            "password": "hunter2",
            "auth": {"api_key": "sk-live-123", "token": "eyJhbGciOi"},
            "attempts": [{"otp": "123456", "ip_address": "10.0.0.1"}],
        }
    )
    flat = json.dumps(payload)
    assert "hunter2" not in flat
    assert "sk-live-123" not in flat
    assert "eyJhbGciOi" not in flat
    assert "123456" not in flat
    # Non-sensitive siblings survive.
    assert payload["full_name"] == "John Doe"
    assert payload["attempts"][0]["ip_address"] == "10.0.0.1"


def test_account_numbers_are_masked_not_dropped():
    payload = redact_payload({"account_number": "1234567890123456", "iban": "CM2110002000"})
    assert payload["account_number"] == "12••••••••••3456"
    assert payload["account_number"].endswith("3456")
    assert "1234567890123456" not in json.dumps(payload)
    assert "•" in payload["iban"]


def test_short_identifiers_are_fully_masked():
    """Masking a 5-character value with head+tail would leak nearly all of it."""
    assert mask_identifier("12345") == "•" * 5


def test_redaction_does_not_mutate_the_callers_dict():
    original = {"password": "hunter2", "amount": 100}
    redact_payload(original)
    assert original["password"] == "hunter2"


def test_oversized_payloads_are_bounded():
    payload = redact_payload({"note": "x" * 10_000, "items": list(range(500))})
    assert len(payload["note"]) <= 500
    assert len(payload["items"]) <= 26  # 25 kept + the "omitted" marker


def test_secrets_are_never_persisted_or_rendered(client):
    """End-to-end: a publisher sends credentials; neither the stored audit
    row nor the outgoing Telegram message may contain them."""
    event_id = dispatch.emit(
        "user.registered",
        platform="quatapay",
        payload={
            "full_name": "Jane Roe",
            "email": "jane@example.com",
            "password": "SuperSecret123",
            "otp": "998877",
            "api_key": "sk-live-should-never-appear",
        },
        reference="USR-SEC-1",
    )
    row = _row(event_id)
    blob = json.dumps(row.payload) + (row.message or "")
    assert "SuperSecret123" not in blob
    assert "998877" not in blob
    assert "sk-live-should-never-appear" not in blob
    # The marker is retained in the payload for auditing the bad integration,
    # but must not be printed into the message.
    assert row.payload["password"] == REDACTED
    assert "Password" not in (row.message or "")


# ---------------------------------------------------------------------------
# Catalogue
# ---------------------------------------------------------------------------

def test_every_catalogue_event_has_a_known_category():
    for key, spec in catalog.EVENTS.items():
        assert spec.category in catalog.CATEGORIES, f"{key} has unknown category {spec.category}"
        assert spec.priority in catalog.PRIORITY_ORDER, f"{key} has unknown priority"
        assert spec.banner in catalog.BANNER_TEXT, f"{key} has unknown banner"


def test_all_six_platforms_are_registered():
    assert set(catalog.PLATFORMS) == {
        "quatapay",
        "quatafood",
        "abaqwa",
        "quatatrade",
        "quata_ai",
        "quata_digital",
    }


def test_unknown_event_keys_are_accepted_and_categorised():
    """A future platform must be able to publish before the catalogue
    catches up — that's what keeps the architecture modular."""
    spec = catalog.resolve_event("loyalty.points_awarded")
    assert spec.category == catalog.UNCATEGORISED
    assert spec.priority == catalog.PRIORITY_INFO
    # A key in a known namespace still lands in the right bucket.
    assert catalog.resolve_event("deposit.reversed").category == "transaction"


@pytest.mark.parametrize(
    "key",
    [
        # Every event named in the brief must resolve to a curated spec, not
        # to the unknown-key fallback.
        "user.registered", "user.email_verified", "user.phone_verified",
        "user.profile_updated", "user.password_reset_requested",
        "user.password_changed", "user.deactivated", "user.reactivated",
        "user.deleted",
        "security.admin_login", "security.admin_logout",
        "security.admin_login_failed", "security.suspicious_login",
        "security.multiple_failed_logins", "security.new_device_login",
        "security.new_location_login", "security.two_factor_enabled",
        "security.two_factor_disabled", "security.account_locked",
        "wallet.created", "wallet.activated",
        "deposit.initiated", "deposit.successful", "deposit.failed",
        "withdrawal.requested", "withdrawal.approved",
        "withdrawal.completed", "withdrawal.failed",
        "transfer.wallet_to_wallet", "payment.merchant", "payment.qr",
        "payment.request_accepted",
        "merchant.registered", "merchant.approved", "merchant.suspended",
        "merchant.settlement_completed",
        "transaction.refund_issued", "transaction.chargeback",
        "transaction.dispute_opened", "transaction.dispute_resolved",
        "kyc.submitted", "kyc.approved", "kyc.rejected",
        "restaurant.registered", "restaurant.approved",
        "order.placed", "order.accepted", "order.rejected", "order.prepared",
        "order.rider_assigned", "order.picked_up", "order.delivered",
        "order.cancelled", "order.refund_processed",
        "restaurant.payout_completed", "promotion.created",
        "delivery.requested", "parcel.requested", "ride.requested",
        "rider.assigned", "rider.accepted", "pickup.completed",
        "delivery.completed", "delivery.cancelled",
        "delivery.payment_completed",
        "account.created", "trade.created", "trade.accepted",
        "trade.completed", "trade.cancelled", "escrow.funded",
        "escrow.released", "escrow.dispute_opened", "crypto.deposit",
        "crypto.withdrawal", "fiat.deposit", "fiat.withdrawal",
        "trade.large", "trade.suspicious",
        "ai.service_started", "ai.service_stopped", "ai.restarted",
        "ai.unavailable", "ai.api_error", "ai.model_updated",
        "ai.knowledge_base_updated", "ai.system_overload",
        "ai.usage_spike", "ai.admin_added", "ai.admin_removed",
        "website.contact_submitted", "website.investor_inquiry",
        "website.partnership_request", "website.business_inquiry",
        "website.career_application", "website.support_request",
        "infra.server_offline", "infra.server_restarted",
        "infra.server_recovered", "infra.database_disconnected",
        "infra.database_backup_completed", "infra.database_backup_failed",
        "infra.storage_low", "infra.high_cpu", "infra.high_ram",
        "infra.high_disk", "infra.api_unavailable", "infra.queue_failure",
        "infra.job_failure", "infra.application_error",
        "gateway.momo_unavailable", "gateway.momo_restored",
        "gateway.callback_failure", "gateway.settlement_completed",
        "gateway.settlement_failed", "gateway.payment_delayed",
    ],
)
def test_every_specified_event_is_in_the_catalogue(key):
    assert key in catalog.EVENTS, f"{key} is missing from the catalogue"


def test_sdk_event_constants_match_the_catalogue():
    """The shipped SDKs carry their own copy of the event keys. If one drifts,
    a platform publishes a key the catalogue doesn't curate and silently
    loses its priority and category."""
    import pathlib

    root = pathlib.Path(__file__).resolve().parents[2]
    known = set(catalog.EVENTS)

    python_sdk = (root / "sdk" / "python" / "quata_notify.py").read_text()
    ts_sdk = (root / "sdk" / "typescript" / "quata-notify.ts").read_text()

    for name, source, pattern in (
        ("python", python_sdk, r'^\s{4}[A-Z_0-9]+ = "([a-z_]+\.[a-z_]+)"'),
        ("typescript", ts_sdk, r'^\s{2}[A-Z_0-9]+: "([a-z_]+\.[a-z_]+)",'),
    ):
        declared = set(re.findall(pattern, source, re.MULTILINE))
        assert declared, f"no event constants found in the {name} SDK"
        unknown = declared - known
        assert not unknown, f"{name} SDK declares keys missing from the catalogue: {sorted(unknown)}"


def test_security_events_use_the_security_banner():
    for key in ("security.suspicious_login", "security.account_locked", "security.multiple_failed_logins"):
        assert catalog.EVENTS[key].banner == catalog.BANNER_SECURITY
        assert catalog.EVENTS[key].priority == catalog.PRIORITY_CRITICAL


def test_infrastructure_events_use_the_system_banner():
    for key in ("infra.server_offline", "infra.database_disconnected", "infra.api_unavailable"):
        assert catalog.EVENTS[key].banner == catalog.BANNER_SYSTEM


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------

def test_message_follows_the_standard_layout():
    """Pins the exact specified envelope, block by block and in order."""
    from datetime import datetime

    message = render(
        spec=catalog.EVENTS["user.registered"],
        platform="quatapay",
        payload={
            "full_name": "John Doe",
            "email": "john@example.com",
            "phone": "+2376XXXXXXXX",
            "country": "Cameroon",
        },
        priority="info",
        reference="USR-000245",
        # 13:30 UTC = 14:30 WAT, matching the specified sample.
        occurred_at=datetime(2026, 7, 25, 13, 30, tzinfo=timezone.utc),
    )
    plain = re.sub(r"<[^>]+>", "", message)
    assert plain == (
        "🔔 QUATA ALERT\n"
        "\n"
        "Platform:\n"
        "QuataPay\n"
        "\n"
        "Priority:\n"
        "🟢 INFO\n"
        "\n"
        "Event:\n"
        "New User Registration\n"
        "\n"
        "Status:\n"
        "SUCCESS\n"
        "\n"
        "Name:\n"
        "John Doe\n"
        "\n"
        "Email:\n"
        "john@example.com\n"
        "\n"
        "Phone:\n"
        "+2376XXXXXXXX\n"
        "\n"
        "Country:\n"
        "Cameroon\n"
        "\n"
        "Reference:\n"
        "USR-000245\n"
        "\n"
        "Date:\n"
        "25 Jul 2026\n"
        "\n"
        "Time:\n"
        "14:30"
    )


def test_priority_is_rendered_above_the_event():
    """Severity must be readable before the event name — on a phone lock
    screen that's often all you get."""
    message = re.sub(
        r"<[^>]+>",
        "",
        render(
            spec=catalog.EVENTS["deposit.successful"],
            platform="quatapay",
            payload={"amount": 100},
            priority="critical",
        ),
    )
    assert message.index("Priority:") < message.index("Event:")


def test_status_is_plain_text():
    """The emoji signal lives on Priority and only there, so the two
    channels don't compete."""
    for spec in catalog.EVENTS.values():
        assert spec.status == spec.status.upper(), f"{spec.key} status is not uppercase"
        assert spec.status.isascii(), f"{spec.key} status carries a glyph: {spec.status!r}"


def test_date_and_time_are_separate_blocks():
    message = re.sub(
        r"<[^>]+>",
        "",
        render(
            spec=catalog.EVENTS["order.placed"],
            platform="quatafood",
            payload={"order_number": "QF-1"},
            priority="info",
        ),
    )
    assert "Date:" in message and "Time:" in message
    assert message.index("Date:") < message.index("Time:")
    # The specified sample is a bare `14:30` — no timezone suffix.
    time_value = message.rsplit("Time:\n", 1)[1].strip()
    assert re.fullmatch(r"\d{2}:\d{2}", time_value), time_value


def test_payload_values_are_html_escaped():
    """An untrusted payload must not be able to inject Telegram markup."""
    message = render(
        spec=catalog.EVENTS["website.contact_submitted"],
        platform="quata_digital",
        payload={"full_name": "<b>evil</b> & co"},
        priority="info",
    )
    assert "&lt;b&gt;evil&lt;/b&gt; &amp; co" in message
    assert "<b>evil</b>" not in message


def test_amounts_are_thousands_separated():
    assert format_amount(1500000) == "1,500,000"
    assert format_amount("2500.5") == "2,500.50"
    assert format_amount("not-a-number") == "not-a-number"


def test_messages_are_truncated_below_the_telegram_limit():
    message = render(
        spec=catalog.EVENTS["infra.application_error"],
        platform="quata_digital",
        payload={f"field_{i}": "y" * 400 for i in range(40)},
        priority="critical",
    )
    assert len(message) <= 4100
    assert message.endswith("truncated</i>")


# ---------------------------------------------------------------------------
# Publish / dedupe / suppression
# ---------------------------------------------------------------------------

def test_emit_records_an_event(client):
    event_id = dispatch.emit(
        "order.placed",
        platform="quatafood",
        payload={"order_number": "QF-1001", "customer": "Ada", "amount": 4500},
        reference="QF-1001",
    )
    row = _row(event_id)
    assert row.platform == "quatafood"
    assert row.category == "order"
    assert row.status in {"pending", "failed"}  # no bot token in tests
    assert row.reference == "QF-1001"


def test_emit_never_raises_on_a_bad_payload(client):
    """Alerting must never be able to fail the caller's request."""

    class Explodes:
        def __repr__(self):
            raise RuntimeError("boom")

    # Must return cleanly rather than propagating.
    dispatch.emit("order.placed", platform="quatafood", payload={"x": Explodes()})


def test_duplicate_events_are_deduplicated(client):
    payload = {"order_number": "QF-DEDUPE", "amount": 1000}
    first = dispatch.emit("order.placed", platform="quatafood", payload=payload, reference="QF-DEDUPE")
    second = dispatch.emit("order.placed", platform="quatafood", payload=payload, reference="QF-DEDUPE")
    assert first == second, "a repeated publish must not alert twice"


def test_explicit_dedupe_key_is_honoured(client):
    a = dispatch.emit("deposit.successful", platform="quatapay", payload={"amount": 1},
                      dedupe_key="idem:test:1")
    b = dispatch.emit("deposit.successful", platform="quatapay", payload={"amount": 999},
                      dedupe_key="idem:test:1")
    assert a == b


def test_large_transactions_are_escalated(client):
    threshold = settings_store.large_transaction_threshold()
    event_id = dispatch.emit(
        "transfer.wallet_to_wallet",
        platform="quatapay",
        payload={"amount": threshold + 1, "currency": "XAF", "sender": "A", "receiver": "B"},
        reference="TXN-BIG",
    )
    row = _row(event_id)
    assert row.priority == catalog.PRIORITY_CRITICAL
    assert "💰 LARGE TRANSACTION ALERT" in (row.message or "")


def test_small_transactions_are_not_escalated(client):
    event_id = dispatch.emit(
        "deposit.successful",
        platform="quatapay",
        payload={"amount": 100, "currency": "XAF"},
        reference="TXN-SMALL",
    )
    row = _row(event_id)
    assert row.priority == catalog.PRIORITY_INFO
    assert "🔔 QUATA ALERT" in (row.message or "")


def test_disabled_platform_suppresses_delivery(client, admin_headers):
    client.post(
        "/api/v1/admin/alerts/settings/bulk",
        json={"items": [{"key": "platform.abaqwa", "value": "false"}]},
        headers=admin_headers,
    )
    settings_store.invalidate()
    try:
        event_id = dispatch.emit("ride.requested", platform="abaqwa", payload={"customer": "Ada"})
        row = _row(event_id)
        assert row.status == "suppressed"
        assert "abaqwa" in (row.suppressed_reason or "")
    finally:
        client.post(
            "/api/v1/admin/alerts/settings/bulk",
            json={"items": [{"key": "platform.abaqwa", "value": "true"}]},
            headers=admin_headers,
        )
        settings_store.invalidate()


def test_priority_floor_suppresses_low_priority_events(client, admin_headers):
    client.post(
        "/api/v1/admin/alerts/settings/bulk",
        json={"items": [{"key": "delivery.min_priority", "value": "critical"}]},
        headers=admin_headers,
    )
    settings_store.invalidate()
    try:
        event_id = dispatch.emit("order.delivered", platform="quatafood", payload={"order_number": "X"})
        row = _row(event_id)
        assert row.status == "suppressed"
        assert "below" in (row.suppressed_reason or "")
    finally:
        client.post(
            "/api/v1/admin/alerts/settings/bulk",
            json={"items": [{"key": "delivery.min_priority", "value": "info"}]},
            headers=admin_headers,
        )
        settings_store.invalidate()


# ---------------------------------------------------------------------------
# Ingest API
# ---------------------------------------------------------------------------

def test_ingest_requires_credentials(client):
    r = client.post("/api/v1/notify/events", json={"event": "deposit.successful"})
    assert r.status_code == 401


def test_ingest_rejects_a_wrong_key(client):
    r = client.post(
        "/api/v1/notify/events",
        json={"event": "deposit.successful"},
        headers={"X-Quata-Platform": INGEST_PLATFORM, "X-Quata-Key": "wrong"},
    )
    assert r.status_code == 401


def test_ingest_rejects_an_unknown_platform(client):
    r = client.post(
        "/api/v1/notify/events",
        json={"event": "deposit.successful"},
        headers={"X-Quata-Platform": "not-a-platform", "X-Quata-Key": INGEST_KEY},
    )
    assert r.status_code == 401


def test_ingest_accepts_a_single_event(client):
    r = client.post(
        "/api/v1/notify/events",
        json={
            "event": "deposit.successful",
            "payload": {"amount": 2500, "currency": "XAF", "full_name": "Ada"},
            "reference": "TXN-INGEST-1",
        },
        headers={"X-Quata-Platform": INGEST_PLATFORM, "X-Quata-Key": INGEST_KEY},
    )
    assert r.status_code == 202
    body = r.json()
    assert body["platform"] == INGEST_PLATFORM
    assert body["results"][0]["accepted"] is True


def test_ingest_accepts_a_batch(client):
    r = client.post(
        "/api/v1/notify/events",
        json={
            "events": [
                {"event": "kyc.submitted", "payload": {"user_id": 1}, "reference": "K1"},
                {"event": "kyc.approved", "payload": {"user_id": 1}, "reference": "K1"},
            ]
        },
        headers={"X-Quata-Platform": INGEST_PLATFORM, "X-Quata-Key": INGEST_KEY},
    )
    assert r.status_code == 202
    assert len(r.json()["results"]) == 2


def test_a_platform_cannot_publish_as_another_platform(client):
    """QuataPay's key claiming to be QuataFood must be recorded as QuataPay.

    Without this, any compromised platform key could forge financial alerts
    attributed to a different product.
    """
    r = client.post(
        "/api/v1/notify/events",
        json={"event": "order.placed", "platform": "quatafood", "payload": {"order_number": "FORGED"}},
        headers={"X-Quata-Platform": INGEST_PLATFORM, "X-Quata-Key": INGEST_KEY},
    )
    assert r.status_code == 202
    row = _row(r.json()["results"][0]["event_id"])
    assert row.platform == INGEST_PLATFORM


def test_ingest_signature_is_enforced_when_required(client, monkeypatch):
    from app.core.config import settings as env_settings

    monkeypatch.setattr(env_settings, "NOTIFY_REQUIRE_SIGNATURE", True)
    body = json.dumps({"event": "deposit.failed", "payload": {"amount": 1}}).encode()
    headers = {
        "X-Quata-Platform": INGEST_PLATFORM,
        "X-Quata-Key": INGEST_KEY,
        "Content-Type": "application/json",
    }

    assert client.post("/api/v1/notify/events", content=body, headers=headers).status_code == 401

    stamp = str(int(time.time()))
    signature = hmac.new(INGEST_KEY.encode(), f"{stamp}.".encode() + body, hashlib.sha256).hexdigest()
    ok = client.post(
        "/api/v1/notify/events",
        content=body,
        headers={**headers, "X-Quata-Signature": signature, "X-Quata-Timestamp": stamp},
    )
    assert ok.status_code == 202

    # A valid signature with a stale timestamp is a replay — refuse it.
    stale = str(int(time.time()) - 100_000)
    stale_sig = hmac.new(INGEST_KEY.encode(), f"{stale}.".encode() + body, hashlib.sha256).hexdigest()
    replay = client.post(
        "/api/v1/notify/events",
        content=body,
        headers={**headers, "X-Quata-Signature": stale_sig, "X-Quata-Timestamp": stale},
    )
    assert replay.status_code == 401


def test_ingest_health_is_public(client):
    r = client.get("/api/v1/notify/health")
    assert r.status_code == 200
    assert r.json()["service"] == "quata-notification-service"


# ---------------------------------------------------------------------------
# Admin API
# ---------------------------------------------------------------------------

def test_alert_settings_require_permission(client):
    assert client.get("/api/v1/admin/alerts/settings").status_code == 401


def test_alert_settings_expose_the_full_catalogue(client, admin_headers):
    body = client.get("/api/v1/admin/alerts/settings", headers=admin_headers).json()
    assert set(body["groups"]) == {"delivery", "platforms", "categories", "thresholds"}
    assert len(body["platforms"]) == 6
    assert {p["slug"] for p in body["priorities"]} == set(catalog.PRIORITY_ORDER)
    assert "stats" in body


def test_unknown_setting_key_is_rejected(client, admin_headers):
    r = client.post(
        "/api/v1/admin/alerts/settings/bulk",
        json={"items": [{"key": "platform.does_not_exist", "value": "false"}]},
        headers=admin_headers,
    )
    assert r.status_code == 404


def test_recipient_lifecycle(client, admin_headers):
    created = client.post(
        "/api/v1/admin/alerts/recipients",
        json={"chat_id": "-1009998887", "label": "Ops group", "min_priority": "warning"},
        headers=admin_headers,
    )
    assert created.status_code == 201
    row = created.json()
    assert row["is_group"] is True, "a negative chat id is a Telegram group"

    # Same chat twice would double-message the same humans.
    dup = client.post(
        "/api/v1/admin/alerts/recipients",
        json={"chat_id": "-1009998887", "label": "again"},
        headers=admin_headers,
    )
    assert dup.status_code == 409

    paused = client.put(
        f"/api/v1/admin/alerts/recipients/{row['id']}",
        json={"is_active": False},
        headers=admin_headers,
    )
    assert paused.json()["is_active"] is False

    assert client.delete(
        f"/api/v1/admin/alerts/recipients/{row['id']}", headers=admin_headers
    ).status_code == 204


def test_recipient_filters_are_validated(client, admin_headers):
    """A typo in a filter would silently stop the recipient receiving anything."""
    r = client.post(
        "/api/v1/admin/alerts/recipients",
        json={"chat_id": "555000", "label": "typo", "platforms": ["quatapayy"]},
        headers=admin_headers,
    )
    assert r.status_code == 400


def test_recipient_min_priority_is_validated(client, admin_headers):
    r = client.post(
        "/api/v1/admin/alerts/recipients",
        json={"chat_id": "555001", "label": "bad priority", "min_priority": "urgent"},
        headers=admin_headers,
    )
    assert r.status_code == 400


def test_logs_are_listable_and_filterable(client, admin_headers):
    dispatch.emit("restaurant.approved", platform="quatafood", payload={"restaurant": "Chez Ada"})
    r = client.get("/api/v1/admin/alerts/logs?platform=quatafood", headers=admin_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 1
    assert all(item["platform"] == "quatafood" for item in body["items"])


def test_log_detail_and_retry(client, admin_headers):
    event_id = dispatch.emit("merchant.approved", platform="quatapay", payload={"full_name": "Ada"})
    detail = client.get(f"/api/v1/admin/alerts/logs/{event_id}", headers=admin_headers)
    assert detail.status_code == 200
    assert detail.json()["event_id"] == event_id

    retried = client.post(f"/api/v1/admin/alerts/logs/{event_id}/retry", headers=admin_headers)
    assert retried.status_code == 200
    # No bot token in tests, so the retry reports the real reason rather
    # than pretending to succeed.
    assert retried.json()["ok"] is False


def test_missing_log_returns_404(client, admin_headers):
    assert client.get(
        "/api/v1/admin/alerts/logs/does-not-exist", headers=admin_headers
    ).status_code == 404


def test_test_send_reports_missing_recipients(client, admin_headers):
    """With no active recipient the test must say so, not silently pass."""
    from app.models import NotificationRecipient

    with SessionLocal() as db:
        existing = db.query(NotificationRecipient).all()
        for row in existing:
            db.delete(row)
        db.commit()

    r = client.post("/api/v1/admin/alerts/test", headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["ok"] is False
    assert "recipient" in r.json()["error"].lower()


# ---------------------------------------------------------------------------
# Daily summary
# ---------------------------------------------------------------------------

def test_digest_covers_every_enabled_platform(client, admin_headers):
    r = client.get("/api/v1/admin/alerts/digest/preview", headers=admin_headers)
    assert r.status_code == 200
    body = r.json()
    assert set(body["sections"]) == set(catalog.PLATFORMS)
    assert "📊 QUATA DAILY SUMMARY" in body["message"]


def test_quatapay_summary_reports_pending_kyc_and_revenue(client, admin_headers):
    for i in range(4):
        dispatch.emit("kyc.submitted", platform="quatapay", payload={"user_id": i},
                      dedupe_key=f"sum-kyc-sub-{i}")
    dispatch.emit("kyc.approved", platform="quatapay", payload={"user_id": 0},
                  dedupe_key="sum-kyc-app-0")
    dispatch.emit("deposit.successful", platform="quatapay",
                  payload={"amount": 50_000, "fee": 500}, dedupe_key="sum-fee-1")
    dispatch.emit("payment.merchant", platform="quatapay",
                  payload={"amount": 20_000, "fee": 250}, dedupe_key="sum-fee-2")

    body = client.get("/api/v1/admin/alerts/digest/preview", headers=admin_headers).json()
    rows = {row["label"]: row["value"] for row in body["sections"]["quatapay"]}
    assert rows["Pending KYC"] >= 3
    assert rows["Revenue · Fees (XAF)"] >= 750
    assert rows["Transaction Volume (XAF)"] >= 70_000


def test_pending_kyc_never_goes_negative(client, admin_headers):
    """An approval for a submission from an earlier window would otherwise
    produce a nonsense negative figure."""
    for i in range(3):
        dispatch.emit("kyc.approved", platform="quatatrade", payload={"user_id": i},
                      dedupe_key=f"neg-kyc-{i}")
    body = client.get("/api/v1/admin/alerts/digest/preview", headers=admin_headers).json()
    rows = {row["label"]: row["value"] for row in body["sections"]["quatapay"]}
    assert rows["Pending KYC"] >= 0


def test_digest_reflects_published_events(client, admin_headers):
    for i in range(3):
        dispatch.emit(
            "deposit.successful",
            platform="quatapay",
            payload={"amount": 1000},
            dedupe_key=f"digest-test-deposit-{i}",
        )
    body = client.get("/api/v1/admin/alerts/digest/preview", headers=admin_headers).json()
    deposits = {row["label"]: row["value"] for row in body["sections"]["quatapay"]}
    assert deposits["Deposits"] >= 3


# ---------------------------------------------------------------------------
# Local platform wiring
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "reason,expected",
    [
        # The public form posts human labels, not slugs — see
        # frontend/components/forms/contact-form.tsx.
        ("Investor relations", "website.investor_inquiry"),
        ("Partnerships", "website.partnership_request"),
        ("Customer support", "website.support_request"),
        ("Press / media", "website.business_inquiry"),
        ("General enquiry", "website.contact_submitted"),
        ("Other", "website.contact_submitted"),
        ("", "website.contact_submitted"),
        (None, "website.contact_submitted"),
    ],
)
def test_contact_reasons_route_to_the_right_event(reason, expected):
    """Regression: an exact-match table silently routed every real form
    submission to the generic event, because the form sends labels."""
    from app.services.notifications.local_events import contact_event_for

    assert contact_event_for(reason) == expected


def test_investor_enquiry_publishes_the_investor_event(client):
    r = client.post(
        "/api/v1/contact",
        json={
            "name": "Amina Farouk",
            "email": "amina@example.com",
            "message": "Interested in a Series A conversation.",
            "reason": "Investor relations",
        },
    )
    assert r.status_code == 201
    with SessionLocal() as db:
        row = (
            db.query(NotificationEvent)
            .filter(NotificationEvent.event_key == "website.investor_inquiry")
            .order_by(NotificationEvent.id.desc())
            .first()
        )
    assert row is not None
    assert row.priority == catalog.PRIORITY_IMPORTANT


def test_website_contact_form_publishes_an_event(client):
    before = _count_events("website")
    r = client.post(
        "/api/v1/contact",
        json={
            "name": "Grace Mbeki",
            "email": "grace@example.com",
            "message": "I'd like to discuss a partnership.",
            "reason": "partnership",
        },
    )
    assert r.status_code == 201
    assert _count_events("website") > before


def test_failed_admin_login_publishes_a_security_event(client):
    before = _count_events("security")
    client.post(
        "/api/v1/auth/login",
        json={"email": "admin@quatadigital.com", "password": "definitely-wrong"},
    )
    assert _count_events("security") > before


def test_login_to_an_unknown_account_is_flagged_as_suspicious(client):
    client.post(
        "/api/v1/auth/login",
        json={"email": "intruder@example.com", "password": "guessing"},
    )
    with SessionLocal() as db:
        row = (
            db.query(NotificationEvent)
            .filter(NotificationEvent.event_key == "security.suspicious_login")
            .order_by(NotificationEvent.id.desc())
            .first()
        )
    assert row is not None
    assert row.priority == catalog.PRIORITY_CRITICAL


def test_country_is_read_from_a_cdn_header():
    """Country comes from a CDN/proxy header — the only geo signal available
    without shipping a GeoIP database."""
    from starlette.datastructures import Headers

    from app.services.notifications.local_events import request_country

    class FakeRequest:
        def __init__(self, headers):
            self.headers = Headers(headers)

    assert request_country(FakeRequest({"cf-ipcountry": "cm"})) == "CM"
    assert request_country(FakeRequest({"x-vercel-ip-country": "NG"})) == "NG"
    # Cloudflare's "unknown" and "Tor" sentinels must not be treated as places.
    assert request_country(FakeRequest({"cf-ipcountry": "XX"})) is None
    assert request_country(FakeRequest({"cf-ipcountry": "T1"})) is None
    assert request_country(FakeRequest({})) is None
    assert request_country(None) is None


def test_login_from_a_different_country_is_flagged(client):
    """Two sign-ins from different countries must raise the location alert."""
    from app.models import User

    with SessionLocal() as db:
        user = db.query(User).filter(User.email == "admin@quatadigital.com").first()
        user.must_reset_password = False
        db.commit()

    creds = {"email": "admin@quatadigital.com", "password": "ChangeMe!2026"}
    client.post("/api/v1/auth/login", json=creds, headers={"CF-IPCountry": "CM"})
    before = _count_key("security.new_location_login")
    client.post("/api/v1/auth/login", json=creds, headers={"CF-IPCountry": "RU"})
    assert _count_key("security.new_location_login") > before

    with SessionLocal() as db:
        row = (
            db.query(NotificationEvent)
            .filter(NotificationEvent.event_key == "security.new_location_login")
            .order_by(NotificationEvent.id.desc())
            .first()
        )
    assert "RU" in (row.message or "")


def test_same_country_login_does_not_alert(client):
    creds = {"email": "admin@quatadigital.com", "password": "ChangeMe!2026"}
    client.post("/api/v1/auth/login", json=creds, headers={"CF-IPCountry": "CM"})
    before = _count_key("security.new_location_login")
    client.post("/api/v1/auth/login", json=creds, headers={"CF-IPCountry": "CM"})
    assert _count_key("security.new_location_login") == before


def test_admin_logout_publishes_a_security_event(client, admin_headers):
    before = _count_key("security.admin_logout")
    r = client.post("/api/v1/auth/logout", headers=admin_headers)
    assert r.status_code == 200
    assert _count_key("security.admin_logout") > before


def test_logout_requires_a_session(client):
    assert client.post("/api/v1/auth/logout").status_code == 401


# ---------------------------------------------------------------------------
# QUATA AI wiring
# ---------------------------------------------------------------------------

def test_ai_unavailable_is_published_when_the_key_is_missing(client, monkeypatch):
    """The local talent-intelligence engine publishes as the quata_ai
    platform, exactly as a standalone deployment would."""
    from app.services import ai_cv

    monkeypatch.setattr(ai_cv.settings, "OPENAI_API_KEY", "")
    before = _count_key("ai.unavailable")
    with pytest.raises(ai_cv.AiUnavailable):
        ai_cv.analyze_cv("Some CV text", "Engineer")
    assert _count_key("ai.unavailable") > before

    with SessionLocal() as db:
        row = (
            db.query(NotificationEvent)
            .filter(NotificationEvent.event_key == "ai.unavailable")
            .order_by(NotificationEvent.id.desc())
            .first()
        )
    assert row.platform == "quata_ai"
    assert row.priority == catalog.PRIORITY_CRITICAL


def test_ai_outage_alerts_once_per_hour(client, monkeypatch):
    """Fifty CV analyses against a dead key are one outage, not fifty alerts."""
    from app.services import ai_cv

    monkeypatch.setattr(ai_cv.settings, "OPENAI_API_KEY", "")
    for _ in range(3):
        with pytest.raises(ai_cv.AiUnavailable):
            ai_cv.analyze_cv("Some CV text", "Engineer")
    before = _count_key("ai.unavailable")
    for _ in range(5):
        with pytest.raises(ai_cv.AiUnavailable):
            ai_cv.analyze_cv("Some CV text", "Engineer")
    assert _count_key("ai.unavailable") == before, "duplicate outage alerts leaked"


def test_ai_usage_spike_fires_above_the_threshold(client, admin_headers):
    from app.services.notifications import ai_events

    client.post(
        "/api/v1/admin/alerts/settings/bulk",
        json={"items": [{"key": "thresholds.ai_requests_per_5min", "value": "3"}]},
        headers=admin_headers,
    )
    settings_store.invalidate()
    try:
        before = _count_key("ai.usage_spike")
        for _ in range(4):
            ai_events.request_succeeded(model="gpt-4o-mini", operation="cv_analysis")
        assert _count_key("ai.usage_spike") > before
    finally:
        client.post(
            "/api/v1/admin/alerts/settings/bulk",
            json={"items": [{"key": "thresholds.ai_requests_per_5min", "value": "100"}]},
            headers=admin_headers,
        )
        settings_store.invalidate()


def test_healthy_ai_requests_do_not_alert(client, admin_headers):
    """Per-request notifications would drown the channel."""
    from app.services.notifications import ai_events

    settings_store.invalidate()  # threshold back to the default 100
    before = _count_events("ai_ops")
    ai_events.request_succeeded(model="gpt-4o-mini", operation="cv_analysis")
    assert _count_events("ai_ops") == before


# ---------------------------------------------------------------------------
# Infrastructure wiring
# ---------------------------------------------------------------------------

def test_unhandled_errors_become_system_alerts(client):
    from app.services.notifications import monitor

    before = _count_key("infra.application_error")
    monitor.report_application_error(
        path="/api/v1/some/route", method="POST", error="ValueError: boom"
    )
    assert _count_key("infra.application_error") > before

    with SessionLocal() as db:
        row = (
            db.query(NotificationEvent)
            .filter(NotificationEvent.event_key == "infra.application_error")
            .order_by(NotificationEvent.id.desc())
            .first()
        )
    assert "❌ SYSTEM ALERT" in (row.message or "")


def test_repeated_endpoint_errors_alert_once_per_hour(client):
    """A broken route hit 5,000 times is one problem, not 5,000 messages."""
    from app.services.notifications import monitor

    monitor.report_application_error(path="/api/v1/hot", method="GET", error="boom")
    before = _count_key("infra.application_error")
    for _ in range(5):
        monitor.report_application_error(path="/api/v1/hot", method="GET", error="boom")
    assert _count_key("infra.application_error") == before


def test_backup_outcomes_are_published(client):
    from app.services.notifications import monitor

    before_ok = _count_key("infra.database_backup_completed")
    monitor.report_backup(ok=True, detail="pg_dump 412 MB", size="412 MB")
    assert _count_key("infra.database_backup_completed") > before_ok

    before_fail = _count_key("infra.database_backup_failed")
    monitor.report_backup(ok=False, detail="disk full")
    assert _count_key("infra.database_backup_failed") > before_fail


def test_gateway_outage_is_published_as_a_system_alert(client):
    from app.services.notifications import monitor

    before = _count_key("gateway.momo_unavailable")
    monitor.report_gateway("gateway.momo_unavailable", error="504 from collection API")
    assert _count_key("gateway.momo_unavailable") > before

    with SessionLocal() as db:
        row = (
            db.query(NotificationEvent)
            .filter(NotificationEvent.event_key == "gateway.momo_unavailable")
            .order_by(NotificationEvent.id.desc())
            .first()
        )
    assert row.category == "payment_gateway"
    assert row.priority == catalog.PRIORITY_CRITICAL


def test_monitor_checks_run_without_error(client):
    """The sampler must degrade gracefully on any host — /proc/meminfo and
    getloadavg aren't available everywhere."""
    from app.services.notifications import monitor

    result = monitor.run_checks()
    assert "results" in result
    assert any(r["check"] == "database" for r in result["results"])


def test_monitor_alerts_are_edge_triggered(client):
    """Sampling every minute must not re-alert every minute."""
    from app.services.notifications import monitor

    monitor._STATE.clear()
    assert monitor._transition("demo", True) == "down"
    assert monitor._transition("demo", True) is None
    assert monitor._transition("demo", False) == "up"
    assert monitor._transition("demo", False) is None


def test_api_watchdog_is_off_until_a_url_is_configured(client, monkeypatch):
    """Opt-in on purpose — a watchdog pointed at the wrong host reports
    outages that aren't happening. It must also never reach the network
    during a test run."""
    from app.core.config import settings as env_settings
    from app.services.notifications import monitor

    monkeypatch.setattr(env_settings, "NOTIFY_HEALTHCHECK_URL", "")
    assert monitor.check_api_reachable() is None


def test_api_watchdog_reports_an_unreachable_host(client, monkeypatch):
    from app.core.config import settings as env_settings
    from app.services.notifications import monitor

    # Port 1 on localhost refuses instantly — no real network egress.
    monkeypatch.setattr(env_settings, "NOTIFY_HEALTHCHECK_URL", "http://127.0.0.1:1/health/ready")
    monitor._STATE.pop("api", None)
    before = _count_key("infra.api_unavailable")
    result = monitor.check_api_reachable()
    assert result is not None and result["healthy"] is False
    assert _count_key("infra.api_unavailable") > before


# ---------------------------------------------------------------------------
# Retention
# ---------------------------------------------------------------------------

def test_retention_preview_includes_notification_logs(client, admin_headers):
    body = client.get("/api/v1/admin/retention/preview", headers=admin_headers).json()
    assert "notification_events" in body
    assert body["notification_events"]["retention_days"] > 0


def test_prune_keeps_recent_notifications(client):
    """Retention must not eat the alerts an auditor is most likely to want."""
    event_id = dispatch.emit("kyc.approved", platform="quatapay", payload={"user_id": 42})
    dispatch.prune_log()
    assert _row(event_id).event_id == event_id


# ---------------------------------------------------------------------------
# Ops CLI — how cron jobs and deploy hooks raise alerts
# ---------------------------------------------------------------------------

def _run_cli(argv: list[str]) -> int:
    import sys

    from app.scripts.notify_event import main

    original = sys.argv
    sys.argv = ["notify_event", *argv]
    try:
        return main()
    finally:
        sys.argv = original


def test_cli_publishes_an_event(client, capsys):
    before = _count_key("infra.database_backup_completed")
    code = _run_cli([
        "infra.database_backup_completed",
        "--payload", '{"size": "412 MB", "detail": "pg_dump nightly"}',
        "--reference", "DB-BACKUP",
        "--wait", "--quiet",
    ])
    assert code == 0
    assert _count_key("infra.database_backup_completed") > before

    with SessionLocal() as db:
        row = (
            db.query(NotificationEvent)
            .filter(NotificationEvent.event_key == "infra.database_backup_completed")
            .order_by(NotificationEvent.id.desc())
            .first()
        )
    assert row.payload["size"] == "412 MB"
    assert row.reference == "DB-BACKUP"


def test_cli_rejects_a_malformed_payload(client, capsys):
    assert _run_cli(["infra.job_failure", "--payload", "not-json"]) == 1
    # A JSON scalar isn't a field map — refuse rather than render nonsense.
    assert _run_cli(["infra.job_failure", "--payload", '"a string"']) == 1


def test_cli_succeeds_even_when_delivery_fails(client):
    """The backup cron wraps this call — a backup that worked must not be
    reported as failed just because Telegram is unreachable."""
    assert _run_cli([
        "infra.database_backup_failed",
        "--payload", '{"error": "disk full"}',
        "--priority", "critical",
        "--wait", "--quiet",
    ]) == 0


def test_cli_honours_priority_override(client):
    _run_cli([
        "infra.job_failure",
        "--payload", '{"service": "cli-priority-test"}',
        "--priority", "critical",
        "--dedupe-key", "cli-priority-test",
        "--quiet",
    ])
    with SessionLocal() as db:
        row = (
            db.query(NotificationEvent)
            .filter(NotificationEvent.dedupe_key == "cli-priority-test")
            .first()
        )
    assert row.priority == catalog.PRIORITY_CRITICAL


# ---------------------------------------------------------------------------
# Bootstrap recipients
# ---------------------------------------------------------------------------

def test_bootstrap_seeds_chat_ids_and_admin_user_ids(client, monkeypatch):
    from app.core.config import settings as env_settings
    from app.models import NotificationRecipient
    from app.services.notifications.recipients import seed_bootstrap_recipients

    monkeypatch.setattr(env_settings, "TELEGRAM_DEFAULT_CHAT_IDS", "-1005550001")
    monkeypatch.setattr(env_settings, "TELEGRAM_ADMIN_USER_IDS", "5550002, 5550003")

    with SessionLocal() as db:
        created = seed_bootstrap_recipients(db)
        assert created == 3
        rows = {
            r.chat_id: r
            for r in db.query(NotificationRecipient)
            .filter(NotificationRecipient.chat_id.in_(["-1005550001", "5550002", "5550003"]))
            .all()
        }
    assert rows["-1005550001"].is_group is True, "a negative id is a Telegram group"
    assert rows["5550002"].is_group is False

    # Re-running must not duplicate, and must not resurrect a chat an admin
    # deliberately paused.
    with SessionLocal() as db:
        rows["5550002"].is_active = False
        db.merge(rows["5550002"])
        db.commit()
        assert seed_bootstrap_recipients(db) == 0
        again = (
            db.query(NotificationRecipient)
            .filter(NotificationRecipient.chat_id == "5550002")
            .first()
        )
        assert again.is_active is False, "bootstrap re-enabled a paused recipient"


def test_bootstrap_tolerates_an_id_in_both_variables(client, monkeypatch):
    """The same chat listed as both a chat id and an admin id must not blow
    up the whole seed on a unique-constraint violation."""
    from app.core.config import settings as env_settings
    from app.services.notifications.recipients import seed_bootstrap_recipients

    monkeypatch.setattr(env_settings, "TELEGRAM_DEFAULT_CHAT_IDS", "5559999")
    monkeypatch.setattr(env_settings, "TELEGRAM_ADMIN_USER_IDS", "5559999")
    with SessionLocal() as db:
        assert seed_bootstrap_recipients(db) == 1


def _count_key(event_key: str) -> int:
    with SessionLocal() as db:
        return (
            db.query(NotificationEvent)
            .filter(NotificationEvent.event_key == event_key)
            .count()
        )


def _count_events(category: str) -> int:
    with SessionLocal() as db:
        return (
            db.query(NotificationEvent)
            .filter(NotificationEvent.category == category)
            .count()
        )
