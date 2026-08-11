"""ADVERSARIAL probes at the two-number separation — now regression tests.

Every test in here was originally written to BREAK the invariant, and every
one of them PASSED, which is what a confirmed defect looks like. They have
been inverted in place: each now drives the same attack and asserts it is
REFUSED, at the layer that refuses it and with the reason code that names it.
The attack text is kept in the docstrings on purpose — a guarantee is only
worth reading if it says what it is a guarantee *against*.

The invariant under guard: nothing but an approved *authentication* template
may leave Quata Verify (``purpose='authentication'``), and no authentication
template may leave QUATA (``purpose='engagement'``).

Why this matters more than a category label: Meta restricts a number that
sends marketing on an authentication template, and QuataFood's login OTP,
payment-PIN reset and phone-change verification have no email fallback. A
restricted Verify number means those users cannot log in at all.

Four layers are exercised here, and each must refuse independently:

    L1  storage    a violating template row cannot exist
    L2  routing    ``resolve_route`` denies before a ticket is minted
    L3  transport  ``meta.send_*`` re-judges the ticket it was handed
    L4  gateway    the public product API refuses over signed HTTP
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from app.db.session import SessionLocal, engine
from app.models import (
    Base,
    WhatsAppAuditLog,
    WhatsAppMessage,
    WhatsAppRoutingRule,
    WhatsAppTemplate,
)
from app.services.whatsapp import dispatch, meta, routing
from app.services.whatsapp.routing import RoutingDenied

from . import whatsapp_world


@pytest.fixture(scope="module")
def world():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        built = whatsapp_world.build(db)
        # The original fixture stood up the template the whole attack chain
        # depended on: category='utility' bound to the VERIFY number. The
        # database now refuses that row outright, so the rest of this module
        # attacks through a routing rule that *points at* a template intent
        # which can no longer exist on Verify.
        db.add(
            WhatsAppRoutingRule(
                product_id=built.product.id,
                intent="weekend_promo_as_utility",
                purpose="authentication",
                template_intent="verify_utility",
                locale=None,
                priority=100,
                is_active=True,
                fallback_channel="none",
                conditions={},
            )
        )
        db.commit()
        yield built
        whatsapp_world.teardown(db, built)
    finally:
        db.close()


@pytest.fixture
def live(monkeypatch):
    whatsapp_world.enable_delivery(monkeypatch, enabled=True)


@pytest.fixture
def no_http(monkeypatch):
    """Record what WOULD have gone to Meta. Any entry = a real send."""
    calls: list[dict] = []

    def _recorder(url, *, token, payload=None, method="POST"):
        calls.append({"url": url, "payload": payload, "method": method})
        return True, {"messages": [{"id": "wamid.ATTACK"}]}, None, 200

    monkeypatch.setattr(meta, "_call", _recorder)
    return calls


def _auth_ticket(db, world):
    """A genuine, correctly-signed ticket for the Verify number.

    Minted by ``resolve_route`` itself — nothing is forged, no SECRET_KEY is
    used by the test, and the ticket is exactly what the choke point produces
    for QuataFood's login OTP.
    """
    ticket = routing.resolve_route(
        db,
        product_slug=world.product_slug,
        intent="login_otp",
        to_phone_e164="+237600000009",
        kind="template",
        variables=("482913",),
    )
    assert ticket.account_id == world.verify.id
    assert ticket.account_purpose == "authentication"
    return ticket


# ---------------------------------------------------------------------------
# L1 — the row the whole attack chain rested on cannot be stored
# ---------------------------------------------------------------------------

def test_a_utility_template_cannot_be_stored_on_quata_verify(world):
    """ATTACK: register ``category='utility'`` against the Verify number.

    This used to be accepted by everything. The two original CHECKs only ever
    spoke about 'authentication' and 'marketing', so 'utility' matched neither
    and was legal by omission — and ``category`` is operator-typed data that
    nothing re-syncs from Meta, so a template Meta later re-classifies as
    MARKETING would have kept leaving the verification number.
    """
    db = SessionLocal()
    try:
        db.add(
            WhatsAppTemplate(
                account_id=world.verify.id,
                account_purpose="authentication",
                product_id=world.product.id,
                name=f"tp_utility_on_verify_{uuid.uuid4().hex[:8]}",
                language="en",
                category="utility",
                intent="verify_utility",
                status="approved",
                variables=["offer"],
            )
        )
        with pytest.raises(IntegrityError) as exc:
            db.flush()
        assert "verify_is_auth_only" in str(exc.value)
        db.rollback()
    finally:
        db.close()


def test_an_approved_verify_template_cannot_be_re_categorised_in_place(world):
    """ATTACK: don't insert a bad row — mutate a good one.

    An operator (or a compromised console) retypes the live login-OTP
    template's category. The CHECKs have to hold on UPDATE, not just INSERT,
    or the number is one UPDATE away from restriction. ``utility`` is the case
    that matters: it was legal on Verify until the newest constraint, so the
    UPDATE path is the one an existing install would actually take.
    """
    for category in ("utility", "marketing"):
        db = SessionLocal()
        try:
            row = db.get(WhatsAppTemplate, world.otp_template.id)
            assert row.account_purpose == "authentication"
            row.category = category
            with pytest.raises(IntegrityError):
                db.flush()
            db.rollback()
        finally:
            db.close()


# ---------------------------------------------------------------------------
# L2 — routing refuses before a ticket exists
# ---------------------------------------------------------------------------

def test_a_non_authentication_category_is_refused_on_the_verify_number(world):
    """ATTACK: 'utility' matched neither purpose rule and fell through.

    Checked directly against the rule function, because with L1 in place no
    template of this shape can be stored for an end-to-end run — which is the
    point, but it must not be the *only* reason the pairing is refused.
    """
    for category in ("utility", "marketing", "service"):
        with pytest.raises(RoutingDenied) as exc:
            routing.assert_purpose_compatible(
                account_purpose="authentication",
                template_account_purpose="authentication",
                template_category=category,
                kind="template",
            )
        assert exc.value.reason in (
            "marketing_on_auth_account",
            "non_auth_template_on_verify",
        )

    # The one pairing that must still be allowed.
    routing.assert_purpose_compatible(
        account_purpose="authentication",
        template_account_purpose="authentication",
        template_category="authentication",
        kind="template",
    )


def test_a_rule_pointing_a_promotion_at_verify_resolves_to_nothing(world, live):
    """ATTACK: an operator writes the rule by hand, purpose='authentication'.

    ``whatsapp_world`` ships exactly that rule (``promo_on_verify``). It must
    not produce a ticket: the marketing template lives on QUATA, and no
    template with that intent can exist on Verify to satisfy it.
    """
    db = SessionLocal()
    try:
        with pytest.raises(RoutingDenied) as exc:
            routing.resolve_route(
                db,
                product_slug=world.product_slug,
                intent="promo_on_verify",
                to_phone_e164="+237600000009",
                kind="template",
                variables=("2-for-1 all weekend",),
            )
        assert exc.value.reason == "template_not_approved"
    finally:
        db.close()


# ---------------------------------------------------------------------------
# L3 — the transport re-judges the ticket it was handed
# ---------------------------------------------------------------------------

def test_free_form_text_cannot_leave_quata_verify_via_meta_send_text(
    world, live, no_http
):
    """ATTACK: ``meta.send_text`` never asked whether the ticket was for Verify.

    ``send_template`` guarded its own call shape; ``send_text`` had no
    equivalent. ``verify_ticket`` could not cover for it either — it evaluates
    ``freeform_on_auth_account`` against the ticket's DECLARED kind, and this
    ticket honestly declares 'template'. So a genuine, unforged authentication
    ticket was enough to POST arbitrary marketing prose from Quata Verify.
    """
    db = SessionLocal()
    try:
        ticket = _auth_ticket(db, world)
        with pytest.raises(RoutingDenied) as exc:
            meta.send_text(
                ticket,
                db=db,
                body_text=(
                    "FLASH SALE! 50% off all QuataFood orders this weekend. "
                    "Order now!"
                ),
            )
        assert exc.value.reason == "freeform_on_auth_account"
    finally:
        db.close()

    assert no_http == [], "the transport issued HTTP after refusing"


def test_a_template_ticket_is_not_permission_to_send_prose(world, live, no_http):
    """ATTACK: the same trick off Verify — reuse an order ticket as free text.

    Permission to send an approved template is not permission to send
    arbitrary text on the same number, so the kind check runs even where the
    purpose check does not apply.
    """
    db = SessionLocal()
    try:
        ticket = routing.resolve_route(
            db,
            product_slug=world.product_slug,
            intent="order_dispatched",
            to_phone_e164="+237600000009",
            kind="template",
            variables=("ORD-9", "18:40"),
        )
        assert ticket.account_purpose == "engagement"
        with pytest.raises(RoutingDenied) as exc:
            meta.send_text(ticket, db=db, body_text="anything at all")
        assert exc.value.reason == "invalid_ticket"
    finally:
        db.close()

    assert no_http == []


def test_l3_refuses_a_pairing_whose_ticket_states_no_category():
    """ATTACK: omit the category and skip every remaining rule.

    ``assert_purpose_compatible`` used to return early on
    ``template_category=None``. ``verify_ticket`` always passes
    ``template_account_purpose=None``, so the ``purpose_mismatch`` branch is
    dead at L3 — which left L3 an HMAC check and nothing else for that shape.
    A template send that states no category is now refused outright.
    """
    with pytest.raises(RoutingDenied) as exc:
        routing.assert_purpose_compatible(
            account_purpose="authentication",
            template_account_purpose=None,
            template_category=None,
            kind="template",
        )
    assert exc.value.reason == "missing_template_category"

    # Free-form off Verify is the one legitimate no-category shape.
    routing.assert_purpose_compatible(
        account_purpose="engagement",
        template_account_purpose=None,
        template_category=None,
        kind="text",
    )


# ---------------------------------------------------------------------------
# The full dispatch path, not just routing
# ---------------------------------------------------------------------------

def test_a_promotion_aimed_at_verify_is_suppressed_by_the_full_dispatch_path(
    world, live, no_http
):
    """ATTACK: skip the layers and go through ``dispatch.send`` + delivery."""
    accepted = dispatch.send(
        product_slug=world.product_slug,
        intent="weekend_promo_as_utility",
        to_phone_e164="+237600000011",
        variables=("2-for-1 all weekend",),
        reference="attack-utility-1",
        dispatch=False,
    )
    assert accepted["ok"] is False
    assert accepted["status"] == "suppressed"
    assert accepted["reason"] == "template_not_approved"
    assert no_http == []
    # No template resolved, so there is no legal message row to write: the
    # schema refuses an outbound template row with no template, and the Verify
    # number refuses any outbound row that is not one. The audit row is what
    # carries the refusal.
    assert accepted["message_uid"] is None

    db = SessionLocal()
    try:
        assert (
            db.query(WhatsAppMessage)
            .filter(
                WhatsAppMessage.account_id == world.verify.id,
                WhatsAppMessage.to_phone_e164 == "+237600000011",
            )
            .count()
            == 0
        )
        denial = (
            db.query(WhatsAppAuditLog)
            .filter(
                WhatsAppAuditLog.resource_id
                == f"{world.product_slug}:weekend_promo_as_utility"
            )
            .order_by(WhatsAppAuditLog.id.desc())
            .first()
        )
        assert denial is not None, "the refusal left no evidence"
        assert denial.outcome == "denied"
        assert denial.reason == "template_not_approved"
    finally:
        db.close()


# ---------------------------------------------------------------------------
# L4 — over signed HTTP, as a product would actually call it
# ---------------------------------------------------------------------------

def test_the_public_product_api_cannot_put_a_promotion_on_quata_verify(
    world, live, no_http, app_instance
):
    """ATTACK: drive it end to end with nothing but valid QCP credentials.

    A product asks for an intent it controls and QCP used to put a promotional
    utility template on Quata Verify; the ``/messages/utility`` alias agreed
    with the declared category, so the narrowing check waved it through too.
    """
    from fastapi.testclient import TestClient

    raw_key = f"qcp_live_{uuid.uuid4().hex}"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    db = SessionLocal()
    try:
        product = db.merge(world.product)
        product.api_key_hash = key_hash
        db.commit()
    finally:
        db.close()

    body = json.dumps(
        {
            "intent": "weekend_promo_as_utility",
            "to": "+237600000033",
            "variables": ["2-for-1 all weekend"],
            "reference": "attack-http-1",
        }
    ).encode()
    path = "/api/v1/whatsapp/messages/utility"
    ts = str(int(time.time()))
    # The signed material is the bound request: verb, routed path,
    # idempotency key, timestamp, body. Signing the body alone made one
    # capture valid for every route.
    material = f"POST\n{path}\n\n{ts}.".encode("utf-8") + body
    headers = {
        "X-QCP-Product": world.product_slug,
        "X-QCP-Key": raw_key,
        "X-QCP-Timestamp": ts,
        "X-QCP-Signature": hmac.new(
            key_hash.encode(), material, hashlib.sha256
        ).hexdigest(),
        "Content-Type": "application/json",
    }

    with TestClient(app_instance) as client:
        response = client.post(path, content=body, headers=headers)

    assert response.status_code == 202, response.text
    accepted = response.json()
    assert accepted["status"] == "suppressed"
    assert accepted["reason"] == "template_not_approved"
    assert no_http == []

    db = SessionLocal()
    try:
        # Nothing was put on the authentication number at all.
        assert (
            db.query(WhatsAppMessage)
            .filter(
                WhatsAppMessage.account_id == world.verify.id,
                WhatsAppMessage.to_phone_e164 == "+237600000033",
            )
            .count()
            == 0
        )
    finally:
        db.close()


# ---------------------------------------------------------------------------
# A reused idempotency key must not swallow an OTP
# ---------------------------------------------------------------------------

def test_a_reused_idempotency_key_does_not_swallow_the_login_otp(
    world, live, monkeypatch
):
    """ATTACK: reuse one business reference across a promotion and a login code.

    ``_explicit_idempotency_key`` namespaced by product and nothing else — not
    by purpose, not by recipient. The OTP came back ``{"ok": true,
    "duplicate": true}`` pointing at the *marketing* row on the OTHER number,
    and was never sent, queued or even recorded. The caller was told it
    succeeded, so the failure was silent on both sides.
    """
    monkeypatch.setattr(dispatch, "schedule", lambda *a, **k: None)
    shared = "order-7781"

    promo = dispatch.send(
        product_slug=world.product_slug,
        intent="promo_weekend",
        to_phone_e164="+237600000022",
        variables=("2-for-1",),
        idempotency_key=shared,
    )
    otp = dispatch.send(
        product_slug=world.product_slug,
        intent="login_otp",
        to_phone_e164="+237600000022",
        variables=("998877",),
        idempotency_key=shared,
    )

    assert promo["ok"] is True and promo["duplicate"] is False
    assert otp["ok"] is True
    assert otp["duplicate"] is False, "the OTP was swallowed as a duplicate"
    assert otp["message_uid"] != promo["message_uid"]

    db = SessionLocal()
    try:
        otp_row = (
            db.query(WhatsAppMessage)
            .filter(WhatsAppMessage.message_uid == otp["message_uid"])
            .first()
        )
        # The OTP got its own row, on the Verify number, with the OTP template.
        assert otp_row.account_id == world.verify.id
        assert otp_row.template_id == world.otp_template.id
        assert otp_row.intent == "login_otp"

        promo_row = (
            db.query(WhatsAppMessage)
            .filter(WhatsAppMessage.message_uid == promo["message_uid"])
            .first()
        )
        assert promo_row.account_id == world.quata.id
        assert promo_row.idempotency_key != otp_row.idempotency_key
    finally:
        db.close()


def test_the_same_reference_to_the_same_person_on_the_same_number_still_dedupes(
    world, live, monkeypatch
):
    """The fix must not have turned idempotency off.

    Narrowing the key is only correct if the retried-POST case it exists to
    collapse still collapses.
    """
    monkeypatch.setattr(dispatch, "schedule", lambda *a, **k: None)
    first = dispatch.send(
        product_slug=world.product_slug,
        intent="login_otp",
        to_phone_e164="+237600000044",
        variables=("121212",),
        idempotency_key="retry-me",
    )
    second = dispatch.send(
        product_slug=world.product_slug,
        intent="login_otp",
        to_phone_e164="+237600000044",
        variables=("121212",),
        idempotency_key="retry-me",
    )
    assert first["duplicate"] is False
    assert second["duplicate"] is True
    assert second["message_uid"] == first["message_uid"]
