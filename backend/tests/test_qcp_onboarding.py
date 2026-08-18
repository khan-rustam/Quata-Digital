"""Onboarding one product onto QCP, end to end, and being told what is left.

The owner's order on 2026-08-17 was "all products should connect to WhatsApp",
QuataPay first. The write surface for that already existed
(``test_whatsapp_admin_write.py`` pins every route in isolation); what nothing
covered is the **journey** — taking one of the four *seeded* rows from dormant
to as-live-as-it-can-get, in the order an operator does it, and then asking
QCP what is still in the way.

Two things are pinned here that the per-route tests cannot be:

**The journey works on a seeded row, not just a freshly registered one.** The
four products arrive from ``app/seeds/whatsapp_seed.py`` disabled, with
``api_key_hash=""`` and least-privilege purposes. Every step below runs against
``quatapay`` — the product the owner named first, and the one whose seeded
ceiling (engagement only, because it moved to email OTP on 2026-06-03) must
survive being onboarded.

**Nothing sends, and QCP says exactly why.** Four independent gates stand
between a registered product and a delivered message — no key, not enabled, no
approved template, platform dormant — and they clear on wildly different
timescales: minting a key is a click, Meta template approval takes days. An
operator who is told only ``ok: false`` re-checks the switches they can see and
concludes QCP is broken. So the gates are named, with the same stable codes
``routing.resolve_route`` refuses a send with, on both surfaces: the product's
own ``GET /whatsapp/health`` and the operator's ``GET /admin/qcp/products``.

Isolation note: ``conftest.py`` runs one SQLite database for the whole session
and ``uq_whatsapp_accounts_active_purpose`` allows at most one *active* number
per purpose, so the fixture below raises its own two numbers, stands them down
afterwards, and restores ``quatapay`` to exactly its seeded shape.
"""
from __future__ import annotations

import hashlib
import json
import uuid

import pytest

from app.db.session import SessionLocal
from app.models import (
    WhatsAppAccount,
    WhatsAppAuditLog,
    WhatsAppProduct,
    WhatsAppRoutingRule,
    WhatsAppTemplate,
)


API = "/api/v1"

# The product the owner named first. Seeded, disabled, keyless,
# engagement-only.
SLUG = "quatapay"


# ---------------------------------------------------------------------------
# The world: two live numbers, and quatapay put back the way it was found
# ---------------------------------------------------------------------------

@pytest.fixture
def estate():
    """Two active numbers and a clean ``quatapay``, restored on the way out."""
    from app.services.whatsapp.credentials import encrypt_wa_secret

    suffix = uuid.uuid4().hex[:8]
    db = SessionLocal()
    try:
        db.query(WhatsAppAccount).filter(
            WhatsAppAccount.is_active == True  # noqa: E712
        ).update({WhatsAppAccount.is_active: False}, synchronize_session=False)
        db.flush()

        token = encrypt_wa_secret(f"PYTEST_NOT_A_REAL_TOKEN_{suffix}")
        verify = WhatsAppAccount(
            slug=f"onb_verify_{suffix}",
            name="Quata Verify",
            purpose="authentication",
            phone_number_id=f"PN_V_{suffix}",
            waba_id=f"WABA_V_{suffix}",
            display_phone="+237600000011",
            api_version="v21.0",
            access_token_encrypted=token,
            is_active=True,
            health="unknown",
        )
        engage = WhatsAppAccount(
            slug=f"onb_quata_{suffix}",
            name="QUATA",
            purpose="engagement",
            phone_number_id=f"PN_E_{suffix}",
            waba_id=f"WABA_E_{suffix}",
            display_phone="+237600000012",
            api_version="v21.0",
            access_token_encrypted=token,
            is_active=True,
            health="unknown",
        )
        db.add_all([verify, engage])
        db.commit()
        db.refresh(verify)
        db.refresh(engage)
        ids = {"verify": verify.id, "engage": engage.id, "suffix": suffix}
    finally:
        db.close()

    yield ids

    db = SessionLocal()
    try:
        product = db.query(WhatsAppProduct).filter(WhatsAppProduct.slug == SLUG).one()
        db.query(WhatsAppRoutingRule).filter(
            WhatsAppRoutingRule.product_id == product.id
        ).delete(synchronize_session=False)
        db.query(WhatsAppTemplate).filter(
            WhatsAppTemplate.account_id.in_([ids["verify"], ids["engage"]])
        ).delete(synchronize_session=False)
        # Exactly the seeded shape: disabled, keyless, engagement-only.
        product.is_enabled = False
        product.api_key_hash = ""
        product.api_key_prefix = ""
        product.allowed_purposes = ["engagement"]
        # Authenticating at the gateway stamps ``last_seen_at``, and
        # ``test_whatsapp_admin_console`` reads it as "these four seeded rows
        # have never called QCP". Restoring the seeded shape means restoring
        # that too, not only the columns this module set on purpose.
        product.last_seen_at = None
        db.query(WhatsAppAccount).filter(
            WhatsAppAccount.id.in_([ids["verify"], ids["engage"]])
        ).update({WhatsAppAccount.is_active: False}, synchronize_session=False)
        db.commit()
    finally:
        db.close()


def _row(slug: str = SLUG) -> WhatsAppProduct:
    db = SessionLocal()
    try:
        return db.query(WhatsAppProduct).filter(WhatsAppProduct.slug == slug).one()
    finally:
        db.close()


def _health(client, key: str, slug: str = SLUG):
    """``GET /whatsapp/health`` as the product, signed the way a product signs."""
    import hmac
    import time

    ts = str(int(time.time()))
    digest = hashlib.sha256(key.encode()).hexdigest()
    path = f"{API}/whatsapp/health"
    message = f"GET\n{path}\n\n{ts}.".encode()
    signature = hmac.new(digest.encode(), message, hashlib.sha256).hexdigest()
    return client.get(
        path,
        headers={
            "X-QCP-Product": slug,
            "X-QCP-Key": key,
            "X-QCP-Timestamp": ts,
            "X-QCP-Signature": signature,
        },
    )


def _codes(body: dict) -> list[str]:
    return [g["code"] for g in body["blocked_by"]]


def _admin_product(client, admin_headers, slug: str = SLUG) -> dict:
    r = client.get(f"{API}/admin/qcp/products", headers=admin_headers)
    assert r.status_code == 200, r.text
    return next(i for i in r.json()["items"] if i["slug"] == slug)


def _route(db, product_id: int, *, purpose: str, template_intent: str) -> None:
    db.add(
        WhatsAppRoutingRule(
            product_id=product_id,
            intent=template_intent,
            purpose=purpose,
            template_intent=template_intent,
            locale=None,
            priority=100,
            is_active=True,
            fallback_channel="none",
            conditions={},
        )
    )


def _template(db, account_id: int, *, purpose: str, category: str, intent: str, status: str):
    row = WhatsAppTemplate(
        account_id=account_id,
        account_purpose=purpose,
        product_id=None,
        name=f"onb_{intent}_{uuid.uuid4().hex[:6]}",
        language="en",
        category=category,
        intent=intent,
        status=status,
        variables=["one"],
    )
    db.add(row)
    return row


# ---------------------------------------------------------------------------
# The journey
# ---------------------------------------------------------------------------

def test_a_seeded_product_starts_behind_every_gate_it_can_be_behind(client, estate):
    """The starting line, asserted rather than assumed."""
    product = _row()
    assert product.is_enabled is False
    assert product.api_key_hash == ""
    assert [str(p) for p in product.allowed_purposes] == ["engagement"]


def test_the_operator_journey_mints_enables_and_grants_in_that_order(
    client, admin_headers, estate
):
    """Key → enable → authentication grant, on the seeded ``quatapay`` row.

    The order is the product's, not the test's: ``qcp_enable_product`` refuses
    a keyless product, because an enabled product that 401s at the gateway is
    an outage the console reports as healthy.
    """
    # A keyless product cannot be switched on.
    r = client.post(f"{API}/admin/qcp/products/{SLUG}/enable", headers=admin_headers)
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["reason"] == "no_api_key"

    # Mint. The plaintext exists exactly once, in this response.
    r = client.post(f"{API}/admin/qcp/products/{SLUG}/api-key", headers=admin_headers)
    assert r.status_code == 201, r.text
    minted = r.json()
    key = minted["api_key"]
    assert minted["shown_once"] is True
    assert _row().api_key_hash == hashlib.sha256(key.encode()).hexdigest()

    # And is never returned again, by any read on either surface.
    later = json.dumps(_admin_product(client, admin_headers)) + json.dumps(
        client.get(f"{API}/admin/qcp/overview", headers=admin_headers).json(),
        default=str,
    )
    assert key not in later

    # It authenticates at the gateway immediately.
    assert _health(client, key).status_code == 200

    # Enable.
    r = client.post(f"{API}/admin/qcp/products/{SLUG}/enable", headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.json()["is_enabled"] is True

    # Grant authentication — a separate, justified, separately-audited act.
    r = client.post(
        f"{API}/admin/qcp/products/{SLUG}/purposes/authentication",
        json={"justification": "owner order 2026-08-17: login codes have email backup"},
        headers=admin_headers,
    )
    assert r.status_code == 200, r.text
    assert "authentication" in r.json()["allowed_purposes"]

    db = SessionLocal()
    try:
        actions = [
            a.action
            for a in db.query(WhatsAppAuditLog)
            .filter(WhatsAppAuditLog.resource_id == SLUG)
            .order_by(WhatsAppAuditLog.id)
            .all()
        ]
    finally:
        db.close()
    assert "product.api_key_minted" in actions
    assert "product.enabled" in actions
    assert "product.authentication_granted" in actions


def test_onboarding_never_grants_authentication_by_itself(
    client, admin_headers, estate
):
    """Minting and enabling raise no ceiling. QuataPay stays engagement-only."""
    key = client.post(
        f"{API}/admin/qcp/products/{SLUG}/api-key", headers=admin_headers
    ).json()["api_key"]
    assert (
        client.post(
            f"{API}/admin/qcp/products/{SLUG}/enable", headers=admin_headers
        ).status_code
        == 200
    )
    assert [str(p) for p in _row().allowed_purposes] == ["engagement"]
    assert _health(client, key).json()["allowed_purposes"] == ["engagement"]


# ---------------------------------------------------------------------------
# The gates, named
# ---------------------------------------------------------------------------

def test_health_names_every_gate_rather_than_only_refusing(client, admin_headers, estate):
    """A newly keyed product is behind three gates at once, and hears all three."""
    key = client.post(
        f"{API}/admin/qcp/products/{SLUG}/api-key", headers=admin_headers
    ).json()["api_key"]

    body = _health(client, key).json()
    assert body["ok"] is False
    codes = _codes(body)
    assert "product_disabled" in codes
    assert "delivery_disabled" in codes
    assert "no_route" in codes
    # Every gate carries a sentence an operator can act on.
    assert all(g["message"].strip() for g in body["blocked_by"])


def test_the_template_gate_is_the_one_that_takes_days(
    client, admin_headers, estate, monkeypatch
):
    """Everything an operator controls is open; Meta has not approved yet.

    This is the state the whole gate report exists for. The switches all read
    "on", the number is live, a routing rule is active — and every send is
    refused ``template_not_approved`` days before Meta answers.
    """
    from tests.whatsapp_world import enable_delivery

    key = client.post(
        f"{API}/admin/qcp/products/{SLUG}/api-key", headers=admin_headers
    ).json()["api_key"]
    assert (
        client.post(
            f"{API}/admin/qcp/products/{SLUG}/enable", headers=admin_headers
        ).status_code
        == 200
    )
    enable_delivery(monkeypatch)

    db = SessionLocal()
    try:
        product = db.query(WhatsAppProduct).filter(WhatsAppProduct.slug == SLUG).one()
        _route(db, product.id, purpose="engagement", template_intent="order_dispatched")
        _template(
            db,
            estate["engage"],
            purpose="engagement",
            category="utility",
            intent="order_dispatched",
            status="pending_approval",
        )
        db.commit()
    finally:
        db.close()

    body = _health(client, key).json()
    assert _codes(body) == ["template_not_approved"]
    assert body["ok"] is False

    # Meta answers.
    db = SessionLocal()
    try:
        row = (
            db.query(WhatsAppTemplate)
            .filter(WhatsAppTemplate.account_id == estate["engage"])
            .one()
        )
        row.status = "approved"
        db.commit()
    finally:
        db.close()

    body = _health(client, key).json()
    assert body["blocked_by"] == []
    assert body["ok"] is True


def test_health_names_a_gate_without_ever_naming_a_number(
    client, admin_headers, estate
):
    """The gate report must not become the account disclosure health is not."""
    key = client.post(
        f"{API}/admin/qcp/products/{SLUG}/api-key", headers=admin_headers
    ).json()["api_key"]
    blob = json.dumps(_health(client, key).json())
    for secret in (
        "onb_verify_",
        "onb_quata_",
        "quata_verify",
        f"PN_V_{estate['suffix']}",
        f"WABA_E_{estate['suffix']}",
        "+237600000011",
        "+237600000012",
    ):
        assert secret not in blob


def test_the_operator_console_names_the_gate_a_product_cannot_report_itself(
    client, admin_headers, estate
):
    """"No key" is the one gate ``/whatsapp/health`` structurally cannot answer.

    A keyless product gets a 401 there — correctly, since telling an
    unauthenticated caller "that product exists but holds no key" is a probe.
    So the operator's registry carries it, using the same vocabulary.
    """
    item = _admin_product(client, admin_headers)
    assert item["has_api_key"] is False
    assert "no_api_key" in [g["code"] for g in item["blocked_by"]]

    client.post(f"{API}/admin/qcp/products/{SLUG}/api-key", headers=admin_headers)
    item = _admin_product(client, admin_headers)
    assert "no_api_key" not in [g["code"] for g in item["blocked_by"]]
    assert "product_disabled" in [g["code"] for g in item["blocked_by"]]


def test_a_dormant_platform_is_reported_to_every_product_not_just_the_broken_one(
    client, admin_headers, estate
):
    """QCP is dormant today. Every product's report says so in the same word."""
    item = _admin_product(client, admin_headers)
    assert "delivery_disabled" in [g["code"] for g in item["blocked_by"]]


def test_the_gate_codes_are_the_words_a_refused_send_uses(client, estate):
    """One vocabulary, not two.

    ``registry`` cannot import ``routing`` — ``routing`` is the send path and
    the dependency runs the other way — so the two lists are pinned against
    each other here instead. A product told ``template_not_approved`` by
    health is refused with ``template_not_approved`` by the send it tries
    next, and an operator grepping the audit log finds the same word.
    """
    from app.services.whatsapp import registry, routing

    assert {
        registry.GATE_PRODUCT_DISABLED,
        registry.GATE_NO_ROUTE,
        registry.GATE_NO_ACCOUNT,
        registry.GATE_TEMPLATE_NOT_APPROVED,
        registry.GATE_DELIVERY_DISABLED,
    } <= routing.REASONS

    # The exception, and why. ``routing`` never sees a keyless product: it is
    # refused at authentication, several layers earlier, and has no send to
    # refuse. So this one gate has no send-path twin, and belongs to the admin
    # registry alone.
    assert registry.GATE_NO_API_KEY not in routing.REASONS
