"""The outbound queue: idempotency, redaction, retry and dead-letter.

``send()`` is called from inside other products' request handlers, so three
properties matter as much as delivery itself:

* **it never raises** — a QCP problem must not fail a QuataPay checkout;
* **it never double-sends** — a retried HTTP POST returns the original
  ``message_uid`` marked ``duplicate`` rather than sending a second OTP;
* **it never persists a code** — the row keeps ``sha256:…``, never the OTP.

Delivery is never exercised against the real Cloud API: ``meta._call`` is
replaced, so these tests assert everything up to the transport and the
transport's own state machine.
"""
from __future__ import annotations

import uuid

import pytest

from app.db.session import SessionLocal, engine
from app.models import Base, WhatsAppMessage
from app.services.whatsapp import dispatch, meta

from . import whatsapp_world


@pytest.fixture(scope="module")
def world():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        built = whatsapp_world.build(db)
        yield built
        whatsapp_world.teardown(db, built)
    finally:
        db.close()


@pytest.fixture
def live(monkeypatch):
    whatsapp_world.enable_delivery(monkeypatch, enabled=True)


@pytest.fixture
def provider(monkeypatch):
    """A programmable stand-in for the Cloud API.

    ``provider.calls`` records every request that would have been issued;
    ``provider.fail(...)`` makes the next calls fail.
    """

    class Provider:
        def __init__(self) -> None:
            self.calls: list[dict] = []
            self.mode = "ok"

        def fail(self, mode: str) -> None:
            self.mode = mode

        def __call__(self, url, *, token, payload=None, method="POST"):
            self.calls.append({"url": url, "payload": payload})
            if self.mode == "throttled":
                return False, {"error": {"code": 130429, "message": "Rate limit hit"}}, "Rate limit hit", 429
            if self.mode == "rejected":
                return False, {"error": {"code": 132000, "message": "Template mismatch"}}, "Template mismatch", 400
            # Unique per call: `provider_message_id` is globally unique, so a
            # fixed id would collide with an earlier test's row.
            return True, {"messages": [{"id": f"wamid.{uuid.uuid4().hex}"}]}, None, 200

    stub = Provider()
    monkeypatch.setattr(meta, "_call", stub)
    return stub


def _row(message_uid: str) -> WhatsAppMessage:
    with SessionLocal() as db:
        row = dispatch.get_message(db, message_uid)
        assert row is not None, f"no whatsapp_messages row for {message_uid}"
        db.expunge(row)
        return row


# ---------------------------------------------------------------------------
# Accept
# ---------------------------------------------------------------------------

def test_a_first_send_is_accepted_and_queued(world, live):
    result = dispatch.send(
        product_slug=world.product_slug,
        intent="login_otp",
        to_phone_e164="+237600000101",
        variables=("482913",),
        reference="ACCEPT-1",
        dispatch=False,
    )
    assert result["ok"] is True
    assert result["duplicate"] is False
    assert result["status"] == "queued"

    row = _row(result["message_uid"])
    assert row.direction == "outbound"
    assert row.account_purpose == "authentication"
    assert row.template_id == world.otp_template.id
    assert row.attempts == 0
    assert row.next_attempt_at is not None


def test_the_otp_is_never_persisted_in_clear(world, live):
    """The single most sensitive value QCP handles."""
    code = "913472"
    result = dispatch.send(
        product_slug=world.product_slug,
        intent="login_otp",
        to_phone_e164="+237600000102",
        variables=(code,),
        reference="REDACT-1",
        dispatch=False,
    )
    row = _row(result["message_uid"])
    stored = row.variables or {}
    assert code not in str(stored)
    assert stored["code"].startswith("sha256:")
    # Same code, same digest — support can compare without ever holding it.
    assert stored["code"] == dispatch.redact_variables({"code": code})["code"]


def test_a_repeated_send_is_a_duplicate_not_a_second_otp(world, live):
    first = dispatch.send(
        product_slug=world.product_slug,
        intent="login_otp",
        to_phone_e164="+237600000103",
        variables=("111111",),
        reference="DUP-1",
        dispatch=False,
    )
    second = dispatch.send(
        product_slug=world.product_slug,
        intent="login_otp",
        to_phone_e164="+237600000103",
        variables=("111111",),
        reference="DUP-1",
        dispatch=False,
    )
    assert second["duplicate"] is True
    assert second["message_uid"] == first["message_uid"]
    assert second["ok"] is True

    with SessionLocal() as db:
        count = (
            db.query(WhatsAppMessage)
            .filter(WhatsAppMessage.to_phone_e164 == "+237600000103")
            .count()
        )
    assert count == 1


def test_a_different_reference_is_a_new_message(world, live):
    first = dispatch.send(
        product_slug=world.product_slug,
        intent="login_otp",
        to_phone_e164="+237600000104",
        variables=("222222",),
        reference="REF-A",
        dispatch=False,
    )
    second = dispatch.send(
        product_slug=world.product_slug,
        intent="login_otp",
        to_phone_e164="+237600000104",
        variables=("222222",),
        reference="REF-B",
        dispatch=False,
    )
    assert second["duplicate"] is False
    assert second["message_uid"] != first["message_uid"]


def test_a_product_supplied_key_is_namespaced_by_product_purpose_and_recipient(
    world, live
):
    """A supplied key dedupes a retry and nothing else.

    Namespacing by product alone was not enough: one reused business
    reference across a promotion and a login code made the OTP come back
    ``{"ok": true, "duplicate": true}`` pointing at the marketing row on the
    other number. The stored key is now an opaque digest over
    (product, account purpose, recipient, supplied key), so an exact-string
    assertion on ``product:supplied`` is deliberately gone — what is pinned
    instead is the behaviour on each axis.
    """
    result = dispatch.send(
        product_slug=world.product_slug,
        intent="order_dispatched",
        to_phone_e164="+237600000105",
        variables=("ORD-42", "18:40"),
        idempotency_key="order-42",
        dispatch=False,
    )
    row = _row(result["message_uid"])
    assert row.idempotency_key.startswith("key:")
    # The supplied key must not be readable back out of the column.
    assert "order-42" not in row.idempotency_key

    # Same product, same purpose, same recipient, same key — a retry.
    again = dispatch.send(
        product_slug=world.product_slug,
        intent="order_dispatched",
        to_phone_e164="+237600000105",
        variables=("ORD-42", "19:10"),
        idempotency_key="order-42",
        dispatch=False,
    )
    assert again["duplicate"] is True
    assert again["message_uid"] == result["message_uid"]

    # A different recipient is a different message, not a duplicate.
    other_person = dispatch.send(
        product_slug=world.product_slug,
        intent="order_dispatched",
        to_phone_e164="+237600000115",
        variables=("ORD-42", "18:40"),
        idempotency_key="order-42",
        dispatch=False,
    )
    assert other_person["duplicate"] is False
    assert other_person["message_uid"] != result["message_uid"]
    assert _row(other_person["message_uid"]).idempotency_key != row.idempotency_key

    # And the same key on the OTHER number is a different message too — this
    # is the axis that swallowed the OTP.
    other_purpose = dispatch.send(
        product_slug=world.product_slug,
        intent="login_otp",
        to_phone_e164="+237600000105",
        variables=("445566",),
        idempotency_key="order-42",
        dispatch=False,
    )
    assert other_purpose["duplicate"] is False
    otp_row = _row(other_purpose["message_uid"])
    assert otp_row.account_id == world.verify.id
    assert otp_row.idempotency_key != row.idempotency_key


def test_send_never_raises_on_an_unknown_product():
    result = dispatch.send(
        product_slug="not_a_product_at_all",
        intent="login_otp",
        to_phone_e164="+237600000106",
        variables=("333333",),
        dispatch=False,
    )
    assert result["ok"] is False
    assert result["reason"] == "product_disabled"
    assert result["status"] == "suppressed"


def test_a_dormant_platform_records_what_it_would_have_sent(world, monkeypatch):
    """QCP takes zero traffic until it is switched on — visibly, not silently."""
    whatsapp_world.enable_delivery(monkeypatch, enabled=False)
    result = dispatch.send(
        product_slug=world.product_slug,
        intent="login_otp",
        to_phone_e164="+237600000107",
        variables=("444444",),
        reference="DORMANT-1",
        dispatch=False,
    )
    assert result["status"] == "suppressed"
    assert result["reason"] == "delivery_disabled"

    row = _row(result["message_uid"])
    assert row.status == "suppressed"
    assert row.suppressed_reason == "delivery_disabled"
    assert row.template_id == world.otp_template.id
    assert row.next_attempt_at is None


# ---------------------------------------------------------------------------
# Deliver
# ---------------------------------------------------------------------------

def test_delivery_marks_the_row_sent_and_records_the_wamid(world, live, provider):
    accepted = dispatch.send(
        product_slug=world.product_slug,
        intent="login_otp",
        to_phone_e164="+237600000108",
        variables=("555555",),
        reference="SEND-1",
        dispatch=False,
    )
    outcome = dispatch.deliver_message(accepted["message_uid"], {"variables": ["555555"]})
    assert outcome["ok"] is True

    row = _row(accepted["message_uid"])
    assert row.status == "sent"
    assert row.provider_message_id.startswith("wamid.")
    assert row.attempts == 1
    assert row.next_attempt_at is None
    # The clear code went to Meta and nowhere else.
    assert provider.calls[-1]["payload"]["template"]["components"][0]["parameters"][0]["text"] == "555555"


def test_a_transient_failure_is_requeued_with_a_backoff(world, live, provider):
    provider.fail("throttled")
    accepted = dispatch.send(
        product_slug=world.product_slug,
        intent="order_dispatched",
        to_phone_e164="+237600000109",
        variables=("ORD-9", "18:40"),
        idempotency_key="retry-1",
        dispatch=False,
    )
    outcome = dispatch.deliver_message(accepted["message_uid"], {"variables": ["ORD-9", "18:40"]})
    assert outcome["ok"] is False

    row = _row(accepted["message_uid"])
    assert row.status == "queued"
    assert row.attempts == 1
    assert row.next_attempt_at is not None
    assert row.error_code == "130429"


def test_a_permanent_rejection_dead_letters_immediately(world, live, provider):
    provider.fail("rejected")
    accepted = dispatch.send(
        product_slug=world.product_slug,
        intent="order_dispatched",
        to_phone_e164="+237600000110",
        variables=("ORD-10", "18:40"),
        idempotency_key="dead-1",
        dispatch=False,
    )
    dispatch.deliver_message(accepted["message_uid"], {"variables": ["ORD-10", "18:40"]})

    row = _row(accepted["message_uid"])
    assert row.status == "failed"
    assert row.failed_at is not None
    assert row.next_attempt_at is None
    assert row.attempts == 1  # not retried — a 400 fails identically every time

    with SessionLocal() as db:
        assert any(m.message_uid == accepted["message_uid"] for m in dispatch.dead_letters(db))


def test_attempts_are_capped_and_the_message_dead_letters(world, live, provider):
    provider.fail("throttled")
    accepted = dispatch.send(
        product_slug=world.product_slug,
        intent="order_dispatched",
        to_phone_e164="+237600000111",
        variables=("ORD-11", "18:40"),
        idempotency_key="cap-1",
        dispatch=False,
    )
    with SessionLocal() as db:
        row = dispatch.get_message(db, accepted["message_uid"])
        row.max_attempts = 2
        db.commit()

    payload = {"variables": ["ORD-11", "18:40"]}
    dispatch.deliver_message(accepted["message_uid"], payload)
    assert _row(accepted["message_uid"]).status == "queued"
    dispatch.deliver_message(accepted["message_uid"], payload)

    row = _row(accepted["message_uid"])
    assert row.status == "failed"
    assert row.attempts == 2
    assert row.next_attempt_at is None


def test_a_queued_otp_is_failed_rather_than_sent_with_the_wrong_code(world, live, provider):
    """After a restart the clear code is gone — the digest must never be sent.

    This is the deliberate cost of never persisting an OTP. The routing
    rule's ``fallback_channel`` is what the product falls back on.
    """
    accepted = dispatch.send(
        product_slug=world.product_slug,
        intent="login_otp",
        to_phone_e164="+237600000112",
        variables=("666666",),
        reference="LOST-1",
        dispatch=False,
    )
    # No payload — exactly what the sweeper has after a restart.
    outcome = dispatch.deliver_message(accepted["message_uid"])
    assert outcome["ok"] is False

    row = _row(accepted["message_uid"])
    assert row.status == "failed"
    assert row.error_code == "payload_not_recoverable"
    assert provider.calls == []


def test_a_non_secret_message_is_recoverable_from_its_row(world, live, provider):
    """An order update carries no secret, so the sweeper can retry it."""
    accepted = dispatch.send(
        product_slug=world.product_slug,
        intent="order_dispatched",
        to_phone_e164="+237600000113",
        variables=("ORD-13", "19:05"),
        idempotency_key="recover-1",
        dispatch=False,
    )
    outcome = dispatch.deliver_message(accepted["message_uid"])
    assert outcome["ok"] is True

    sent = provider.calls[-1]["payload"]["template"]["components"][0]["parameters"]
    assert [p["text"] for p in sent] == ["ORD-13", "19:05"]


def test_the_sweeper_picks_up_due_messages(world, live, provider):
    accepted = dispatch.send(
        product_slug=world.product_slug,
        intent="order_dispatched",
        to_phone_e164="+237600000114",
        variables=("ORD-14", "20:00"),
        idempotency_key="sweep-1",
        dispatch=False,
    )
    summary = dispatch.sweep_pending(limit=50)
    assert summary["picked"] >= 1
    assert _row(accepted["message_uid"]).status == "sent"


def test_reclaim_returns_a_wedged_claim_to_the_queue(world, live):
    from datetime import datetime, timedelta, timezone

    accepted = dispatch.send(
        product_slug=world.product_slug,
        intent="order_dispatched",
        to_phone_e164="+237600000115",
        variables=("ORD-15", "21:00"),
        idempotency_key="stuck-1",
        dispatch=False,
    )
    with SessionLocal() as db:
        row = dispatch.get_message(db, accepted["message_uid"])
        row.status = "sending"
        row.updated_at = datetime.now(timezone.utc) - timedelta(hours=2)
        db.commit()

    assert dispatch.reclaim_stuck(older_than_minutes=15) >= 1
    assert _row(accepted["message_uid"]).status == "queued"


def test_a_delivered_message_is_not_sent_twice(world, live, provider):
    accepted = dispatch.send(
        product_slug=world.product_slug,
        intent="order_dispatched",
        to_phone_e164="+237600000116",
        variables=("ORD-16", "22:00"),
        idempotency_key="once-1",
        dispatch=False,
    )
    payload = {"variables": ["ORD-16", "22:00"]}
    dispatch.deliver_message(accepted["message_uid"], payload)
    before = len(provider.calls)
    outcome = dispatch.deliver_message(accepted["message_uid"], payload)

    assert outcome["reason"] == "already_final"
    assert len(provider.calls) == before


def test_stats_reports_the_dormancy_state(world, live):
    with SessionLocal() as db:
        snapshot = dispatch.stats(db, hours=24)
    assert snapshot["delivery_enabled"] is True
    assert snapshot["total"] >= 1
