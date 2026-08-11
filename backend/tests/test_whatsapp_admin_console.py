"""The QCP admin console's read surface.

Three things are pinned here.

**Empty is the correct answer.** QCP ships dormant — both numbers inactive
and credential-free, every product disabled. Each endpoint must return a
well-formed payload in that state rather than a 500 or a null, because the
console renders it and a screen that looks broken when it is right gets
someone to "fix" a working system.

**No credential ever leaves.** ``whatsapp_accounts`` holds three Fernet
columns and ``whatsapp_products`` holds a key *hash*. The console gets
booleans. The assertion below checks the emitted JSON *keys*, so adding a
credential field to ``_account_out`` later fails this test rather than
shipping.

**The populated path works too.** A console that has only ever been tested
against an empty database is a console nobody has seen render.

Note on isolation: ``conftest.py`` uses one SQLite database for the whole
session and expects tests to use unique data. Nothing here asserts global
emptiness — the dormancy assertions are scoped to the two *seeded* rows,
which no other module mutates, so this file does not depend on collection
order.
"""
from __future__ import annotations

import uuid

import pytest

from app.db.session import SessionLocal
from app.models import WhatsAppConversation, WhatsAppMessage
from tests import whatsapp_world


SEEDED_ACCOUNTS = {"quata_verify", "quata"}
SEEDED_PRODUCTS = {"quatapay", "quatafood", "abaqwa", "quatatrade"}

# Column names that carry a value. None may appear as a key in any response.
CREDENTIAL_KEYS = {
    "access_token_encrypted",
    "app_secret_encrypted",
    "webhook_verify_token_encrypted",
    "webhook_secret_encrypted",
    "api_key_hash",
    "phone_number_id",
    "waba_id",
}


def _by_slug(rows):
    return {r["slug"]: r for r in rows}


# ---------------------------------------------------------------------------
# Overview
# ---------------------------------------------------------------------------

def test_the_overview_reports_both_seeded_numbers_as_dormant(client, admin_headers):
    r = client.get("/api/v1/admin/qcp/overview", headers=admin_headers)
    assert r.status_code == 200, r.text
    body = r.json()

    accounts = _by_slug(body["accounts"])
    assert SEEDED_ACCOUNTS <= set(accounts)
    verify, quata = accounts["quata_verify"], accounts["quata"]
    assert verify["purpose"] == "authentication"
    assert quata["purpose"] == "engagement"
    for a in (verify, quata):
        assert a["is_active"] is False
        # Dormant on every axis: no token, no Meta ids, so it could not
        # address the Graph API even if some other gate failed open.
        assert a["configured"] is False
        assert a["has_access_token"] is False
        assert a["health"] == "unknown"

    products = _by_slug(body["products"])
    assert SEEDED_PRODUCTS <= set(products)
    for slug in SEEDED_PRODUCTS:
        assert products[slug]["is_enabled"] is False

    # The environment kill switch defaults off and nothing in the console
    # can override it.
    assert body["gates"]["env_enabled"] is False


def test_the_overview_never_returns_a_credential(client, admin_headers):
    """Checked on the emitted keys, not on a substring of the body.

    ``has_phone_number_id`` legitimately contains a column's name, so a naive
    substring scan would be a false alarm. What must never appear is a key
    that carries a value.
    """
    body = client.get("/api/v1/admin/qcp/overview", headers=admin_headers).json()
    for account in body["accounts"]:
        assert CREDENTIAL_KEYS.isdisjoint(account), f"credential key in {account['slug']}"
    for product in body["products"]:
        assert CREDENTIAL_KEYS.isdisjoint(product), f"credential key in {product['slug']}"


def test_the_overview_is_shaped_the_same_whether_or_not_anything_happened(
    client, admin_headers
):
    body = client.get("/api/v1/admin/qcp/overview", headers=admin_headers).json()
    for section in ("gates", "queue", "recent", "templates", "conversations"):
        assert isinstance(body[section], dict), section
    for section in ("accounts", "products", "failures", "denials"):
        assert isinstance(body[section], list), section
    assert body["queue"]["queued"] >= 0


# ---------------------------------------------------------------------------
# Conversations
# ---------------------------------------------------------------------------

def test_an_inbox_with_no_matches_is_a_valid_response(client, admin_headers):
    """An unknown product filter must return empty, never widen to "all"."""
    r = client.get(
        "/api/v1/admin/qcp/conversations?product=not-a-real-product",
        headers=admin_headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["items"] == []
    assert body["total"] == 0
    assert body["page"] == 1


def test_a_missing_conversation_is_a_404(client, admin_headers):
    r = client.get("/api/v1/admin/qcp/conversations/999999", headers=admin_headers)
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------

def test_templates_list_both_numbers_even_with_nothing_bound_to_them(
    client, admin_headers
):
    """The screen groups by account, so the accounts must come back
    regardless of whether any template exists — otherwise a fresh install
    renders a blank page instead of "Quata Verify — no templates yet"."""
    body = client.get("/api/v1/admin/qcp/templates", headers=admin_headers).json()
    assert SEEDED_ACCOUNTS <= {a["slug"] for a in body["accounts"]}
    assert {a["purpose"] for a in body["accounts"]} == {"authentication", "engagement"}


def test_no_template_anywhere_is_ever_misbound(client, admin_headers):
    """The load-bearing assertion of the templates screen.

    An authentication template on the engagement number, or a marketing
    template on Verify, is refused by the storage engine. This must therefore
    always be zero — and if it is not, the console shouts.
    """
    body = client.get("/api/v1/admin/qcp/templates", headers=admin_headers).json()
    assert body["misbound_count"] == 0
    assert all(t["misbound"] is False for t in body["items"])


def test_a_legacy_utility_row_on_verify_would_be_shown_as_misbound():
    """The detector has to be wider than the constraint that predates it.

    Verify now takes the ``authentication`` category and nothing else, so a
    ``utility`` row on it is exactly the legacy shape the newest CHECK forbids.
    While ``_is_misbound`` only asked about 'marketing', such a row — the only
    kind that can exist, because it would have to predate the constraint —
    was the one thing the console could not tell an operator about.
    """
    from app.api.routes_admin_whatsapp import _is_misbound

    assert _is_misbound("utility", "authentication") is True
    assert _is_misbound("marketing", "authentication") is True
    assert _is_misbound("authentication", "engagement") is True

    # Still not misbound: the two legitimate pairings.
    assert _is_misbound("authentication", "authentication") is False
    assert _is_misbound("utility", "engagement") is False
    assert _is_misbound("marketing", "engagement") is False


def test_an_unknown_account_filter_returns_nothing(client, admin_headers):
    body = client.get(
        "/api/v1/admin/qcp/templates?account=not-a-real-number", headers=admin_headers
    ).json()
    assert body["items"] == []


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

def test_the_registry_shows_seeded_products_holding_no_key(client, admin_headers):
    items = _by_slug(client.get("/api/v1/admin/qcp/products", headers=admin_headers).json()["items"])
    assert SEEDED_PRODUCTS <= set(items)
    for slug in SEEDED_PRODUCTS:
        p = items[slug]
        assert p["has_api_key"] is False
        assert p["is_enabled"] is False
        assert p["last_seen_at"] is None
        assert CREDENTIAL_KEYS.isdisjoint(p)


def test_only_quatafood_may_reach_the_verify_number(client, admin_headers):
    """Least privilege, carried through to what the console displays.

    QuataFood owns the fleet's only WhatsApp auth path. QuataPay moved to
    email as its sole OTP channel, so re-opening an auth path for it must be
    a deliberate, visible change rather than something the seed granted.
    """
    items = _by_slug(client.get("/api/v1/admin/qcp/products", headers=admin_headers).json()["items"])
    assert "authentication" in items["quatafood"]["allowed_purposes"]
    for slug in ("quatapay", "abaqwa", "quatatrade"):
        assert items[slug]["allowed_purposes"] == ["engagement"]


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/admin/qcp/overview",
        "/api/v1/admin/qcp/conversations",
        "/api/v1/admin/qcp/conversations/1",
        "/api/v1/admin/qcp/templates",
        "/api/v1/admin/qcp/products",
    ],
)
def test_every_qcp_admin_route_requires_authentication(client, path):
    assert client.get(path).status_code == 401


# ---------------------------------------------------------------------------
# The populated path
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def world():
    db = SessionLocal()
    built = whatsapp_world.build(db)
    yield built
    whatsapp_world.teardown(db, built)
    db.close()


@pytest.fixture(scope="module")
def thread(world):
    """One real thread on the Verify number: an inbound text and the
    outbound template that answers it."""
    phone = "+23767" + uuid.uuid4().hex[:7].upper().translate(
        str.maketrans("ABCDEF", "012345")
    )
    with SessionLocal() as db:
        conversation = WhatsAppConversation(
            account_id=world.verify.id,
            product_id=world.product.id,
            wa_contact_id=phone.lstrip("+"),
            phone_e164=phone,
            display_name="Console Fixture",
            state="open",
        )
        db.add(conversation)
        db.flush()

        db.add(
            WhatsAppMessage(
                message_uid=uuid.uuid4().hex,
                account_id=world.verify.id,
                account_purpose="authentication",
                conversation_id=conversation.id,
                product_id=world.product.id,
                direction="inbound",
                kind="text",
                status="delivered",
                from_phone_e164=phone,
                body="hello",
            )
        )
        db.add(
            WhatsAppMessage(
                message_uid=uuid.uuid4().hex,
                account_id=world.verify.id,
                account_purpose="authentication",
                conversation_id=conversation.id,
                product_id=world.product.id,
                template_id=world.otp_template.id,
                direction="outbound",
                kind="template",
                status="delivered",
                intent="login_otp",
                to_phone_e164=phone,
                # Redacted at write time — this is what the row really holds.
                variables={"code": "sha256:ab12cd34"},
            )
        )
        db.commit()
        return {"id": conversation.id, "phone": phone}


def test_a_populated_inbox_lists_the_thread_with_its_number_and_product(
    client, admin_headers, world, thread
):
    body = client.get(
        f"/api/v1/admin/qcp/conversations?product={world.product_slug}",
        headers=admin_headers,
    ).json()
    row = next((c for c in body["items"] if c["id"] == thread["id"]), None)
    assert row is not None
    assert row["product"] == world.product_slug
    assert row["account_purpose"] == "authentication"
    assert row["state"] == "open"


def test_the_thread_view_returns_both_directions_with_delivery_state(
    client, admin_headers, thread
):
    body = client.get(
        f"/api/v1/admin/qcp/conversations/{thread['id']}", headers=admin_headers
    ).json()
    assert body["conversation"]["id"] == thread["id"]

    directions = {m["direction"] for m in body["messages"]}
    assert directions == {"inbound", "outbound"}
    outbound = next(m for m in body["messages"] if m["direction"] == "outbound")
    assert outbound["status"] == "delivered"
    assert outbound["kind"] == "template"
    assert outbound["intent"] == "login_otp"


def test_the_thread_view_shows_the_otp_only_as_a_digest(client, admin_headers, thread):
    """The console cannot leak a code the database does not hold."""
    raw = client.get(
        f"/api/v1/admin/qcp/conversations/{thread['id']}", headers=admin_headers
    ).text
    assert "sha256:" in raw
    body = client.get(
        f"/api/v1/admin/qcp/conversations/{thread['id']}", headers=admin_headers
    ).json()
    outbound = next(m for m in body["messages"] if m["direction"] == "outbound")
    assert outbound["variables"]["code"].startswith("sha256:")


def test_a_populated_overview_counts_the_thread(client, admin_headers, thread):
    body = client.get("/api/v1/admin/qcp/overview", headers=admin_headers).json()
    assert body["conversations"]["total"] >= 1
    assert body["queue"]["total"] >= 2
