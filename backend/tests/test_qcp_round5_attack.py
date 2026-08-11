"""Round 5 — adversarial pass over what rounds 1-4 claimed to have fixed.

Every test here was written against the *claim*, not the implementation, and
every one of them was observed failing before anything was changed. The five
questions asked, in order:

1. Can a credential still reach a stored row through provider text — through a
   door nobody named? (The status webhook is a door: Meta authors that text
   too, and ``webhooks._ingest_status`` wrote it into three columns raw.)
2. Can a verification code still be stored readable, via a Meta-sourced
   template with positional placeholders and an innocent name?
3. Are ordinary engagement variables still readable — order id, ETA, amount,
   customer name, restaurant name? A fix that digests everything is a
   regression, and this file pins the readability so nobody can buy safety
   with it.
4. Can an Admin without ``whatsapp:operate`` reach the five dangerous routes
   anyway — by editing the role catalogue rather than by calling the route?
5. Does QCP still ship dormant?
"""
from __future__ import annotations

import urllib.parse
import uuid
from datetime import datetime, timezone

import pytest

from app.db.session import SessionLocal, engine
from app.models import (
    Base,
    Role,
    User,
    WhatsAppAccount,
    WhatsAppDeliveryEvent,
    WhatsAppMessage,
    WhatsAppProduct,
)
from app.services.whatsapp import dispatch, meta, redaction, templates, webhooks

from . import whatsapp_world


API = "/api/v1"

# Synthetic, structural. Nothing here is or has ever been a live value.
ACCESS_TOKEN = "EAAG" + "8ZBv1k/QZCdp7m3X" * 9
APP_SECRET = "9f3c1d7b0a4e6528d1c9b7a35f204e68"      # 32 hex
APPSECRET_PROOF = "c4e2" * 16                         # 64 hex
URL_ESCAPED = urllib.parse.quote(ACCESS_TOKEN, safe="")
JSON_ESCAPED = ACCESS_TOKEN.replace("/", "\\/")
TRUNCATED = ACCESS_TOKEN[:28]

LEAKED = (
    ("whole access token", ACCESS_TOKEN),
    ("truncated access token", TRUNCATED),
    ("URL-escaped access token", URL_ESCAPED),
    ("JSON-escaped access token", JSON_ESCAPED),
    ("app secret", APP_SECRET),
    ("appsecret_proof", APPSECRET_PROOF),
)

_FRAGMENT_FLOOR = 12


def assert_no_fragment(text, secret: str, label: str) -> None:
    haystack = str(text or "")
    for start in range(0, len(secret) - _FRAGMENT_FLOOR + 1):
        window = secret[start : start + _FRAGMENT_FLOOR]
        assert window not in haystack, (
            f"{label}: a {_FRAGMENT_FLOOR}-character run of the credential survived"
        )


def assert_clean(text, where: str) -> None:
    for label, secret in LEAKED:
        assert_no_fragment(text, secret, f"{where} / {label}")


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


# ---------------------------------------------------------------------------
# 1 — the status webhook is a persisted-error sink too
# ---------------------------------------------------------------------------
#
# Round 1 fixed the *send* path and reported this door as "not my file". Meta
# authors the status callback as surely as it authors the send rejection, and
# ``_ingest_status`` wrote ``error_title``, ``error_detail`` and
# ``message.last_error`` with no filter of any kind — not even the exact-match
# one the send path started with.

STATUS_ERROR_TITLE = f"Access token error: Bearer {ACCESS_TOKEN} was revoked"
STATUS_ERROR_DETAIL = (
    "(#131047) Re-engagement message failed. "
    f"retry_with=token={TRUNCATED}&appsecret_proof={APPSECRET_PROOF} "
    f'context={{"app_secret":"{APP_SECRET}","escaped":"{JSON_ESCAPED}"}} '
    f"https://lookaside.fbsbx.com/x?access_token={URL_ESCAPED} fbtrace_id Ax7Bq2Cd9Ef"
)


@pytest.fixture
def sent_message(world):
    """One message already handed to Meta, so a status callback can land on it."""
    wamid = f"wamid.PYTEST{uuid.uuid4().hex[:16].upper()}"
    uid = f"r5-{uuid.uuid4().hex[:12]}"
    with SessionLocal() as db:
        db.add(
            WhatsAppMessage(
                message_uid=uid,
                account_id=world.quata.id,
                product_id=world.product.id,
                template_id=world.order_template.id,
                direction="outbound",
                kind="template",
                account_purpose="engagement",
                to_phone_e164="+237600000041",
                status="sent",
                provider_message_id=wamid,
                attempts=1,
                max_attempts=3,
            )
        )
        db.commit()
    return wamid, uid


def test_a_status_callback_cannot_write_a_credential_into_the_message_row(
    world, sent_message
):
    wamid, uid = sent_message
    with SessionLocal() as db:
        account = db.get(WhatsAppAccount, world.quata.id)
        created = webhooks._ingest_status(
            db,
            account,
            {
                "id": wamid,
                "status": "failed",
                "timestamp": "1770000000",
                "errors": [
                    {
                        "code": 131047,
                        "title": STATUS_ERROR_TITLE,
                        "message": STATUS_ERROR_DETAIL,
                    }
                ],
            },
        )
        assert created is True

    with SessionLocal() as db:
        row = db.query(WhatsAppMessage).filter(WhatsAppMessage.message_uid == uid).one()
        assert row.status == "failed"
        assert row.last_error, "the failure must still say why"
        assert_clean(row.last_error, "whatsapp_messages.last_error (status webhook)")

        event = (
            db.query(WhatsAppDeliveryEvent)
            .filter(WhatsAppDeliveryEvent.provider_message_id == wamid)
            .one()
        )
        assert_clean(event.error_title, "whatsapp_delivery_events.error_title")
        assert_clean(event.error_detail, "whatsapp_delivery_events.error_detail")
        assert_clean(str(event.raw or {}), "whatsapp_delivery_events.raw")


def test_the_status_webhook_still_records_why_it_failed(world, sent_message):
    """The other half: scrubbing must not empty the column."""
    wamid, uid = sent_message
    with SessionLocal() as db:
        account = db.get(WhatsAppAccount, world.quata.id)
        webhooks._ingest_status(
            db,
            account,
            {
                "id": wamid,
                "status": "failed",
                "timestamp": "1770000001",
                "errors": [
                    {
                        "code": 131047,
                        "title": "Re-engagement message",
                        "message": (
                            "Message failed to send because more than 24 hours "
                            "have passed since the customer last replied."
                        ),
                    }
                ],
            },
        )
    with SessionLocal() as db:
        row = db.query(WhatsAppMessage).filter(WhatsAppMessage.message_uid == uid).one()
        assert "Re-engagement message" in (row.last_error or "")
        assert row.error_code == "131047"


# ---------------------------------------------------------------------------
# 2 — a Meta-sourced template, positional placeholders, innocent name
# ---------------------------------------------------------------------------

INNOCENT_CODE_BODIES = (
    # Meta's own authentication copy, on a UTILITY classification.
    "{{1}} is your verification code. For your security, do not share this code.",
    # The same idea without the giveaway noun — the evasion the phrase list
    # cannot see.
    "Hello! Use {{1}} to finish signing in. It is valid for 5 minutes. "
    "Do not tell anyone.",
    # French, same evasion.
    "Bonjour ! Utilisez {{1}} pour terminer votre connexion. Valable 5 minutes.",
)


@pytest.mark.parametrize("body", INNOCENT_CODE_BODIES)
def test_a_meta_sourced_code_template_cannot_land_routable(world, body):
    """Sync must not leave a code-carrying non-auth template selectable.

    Name is innocent, placeholders are positional, category is Meta's own —
    exactly the shape the sync path has no operator to refuse.
    """
    name = f"r5_order_update_{uuid.uuid4().hex[:8]}"
    remote = [
        {
            "name": name,
            "language": "en",
            "category": "UTILITY",
            "status": "APPROVED",
            "components": [{"type": "BODY", "text": body}],
        }
    ]

    def _fetch(db, account):
        return {"ok": True, "data": remote}

    with SessionLocal() as db:
        account = db.get(WhatsAppAccount, world.quata.id)
        templates.sync_from_meta(db, account, fetch=_fetch)
        db.commit()

    with SessionLocal() as db:
        from app.models import WhatsAppTemplate

        row = (
            db.query(WhatsAppTemplate)
            .filter(WhatsAppTemplate.name == name)
            .one_or_none()
        )
        assert row is not None, "sync should have written the row"
        assert row.status != "approved", (
            "a non-authentication template whose body carries a verification "
            f"code must not be left selectable (body={body!r})"
        )


@pytest.mark.parametrize("body", INNOCENT_CODE_BODIES)
def test_a_code_body_is_recognised_whatever_the_wording(body):
    """The classifier itself, independent of any sink."""
    assert templates.code_body_signal(body) is not None, (
        f"no signal at all for a body that hands the customer a code: {body!r}"
    )


def test_redaction_alone_cannot_save_a_positional_code_on_a_bland_intent():
    """The residual gap, pinned so it is not mistaken for safety.

    Name is the ordinal ``1``, category is ``utility``, intent is ``signin``
    (not on the deny-list), value is a bare six-digit code. Redaction has no
    signal left — the template body, the only thing that says "this is a login
    code", is not stored on ``whatsapp_templates`` (only its ``body_hash`` is),
    so it is not reachable from here.

    The defence is therefore upstream, not here: ``code_body_signal`` refuses
    to let such a template be created, edited into existence, or left
    selectable by a sync. This test exists so that if someone later plumbs the
    body through, it goes red and gets tightened rather than staying a
    surprise.
    """
    stored = redaction.redact_variables(
        {"1": "483920"},
        template_category="utility",
        intent="signin",
        declared_names=["1"],
    )
    assert stored == {"1": "483920"}


# ---------------------------------------------------------------------------
# 3 — the regression that a "fix everything" answer would cause
# ---------------------------------------------------------------------------

def test_ordinary_engagement_variables_stay_readable():
    """Order id, ETA, amount, customer and restaurant must survive verbatim."""
    stored = redaction.redact_variables(
        {
            "order_number": "ORD-77421",
            "eta": "18:40",
            "amount": "12 500 XAF",
            "customer_name": "Ngwa Bih",
            "restaurant": "Chez Paul • Douala",
            "promo_code": "SOLDES25",
            "tracking_code": "TRK-99120",
        },
        template_category="utility",
        intent="order_dispatched",
    )
    assert stored == {
        "order_number": "ORD-77421",
        "eta": "18:40",
        "amount": "12 500 XAF",
        "customer_name": "Ngwa Bih",
        "restaurant": "Chez Paul • Douala",
        "promo_code": "SOLDES25",
        "tracking_code": "TRK-99120",
    }


def test_a_marketing_body_mentioning_a_promo_code_is_not_refused():
    """The false-positive outage the body rule must not cause."""
    assert (
        templates.body_code_problem(
            "marketing",
            "Weekend offer! Use promo code SOLDES25 for 25% off your next order.",
        )
        is None
    )


# ---------------------------------------------------------------------------
# 4 — the permission split, attacked sideways
# ---------------------------------------------------------------------------
#
# Calling the five routes as an Admin is already covered. The question here is
# whether an Admin can *grant themselves* what the split took away. They hold
# ``rbac:manage``, and the role editor validates only that a key exists in the
# catalogue — including ``*``.


@pytest.fixture(scope="module")
def escalation_actor(app_instance):
    """An Admin-shaped actor on a role of its own, so the seeded role is safe.

    Same permissions the seeded ``admin`` role holds; a private row so a
    successful escalation cannot leak into the rest of the session.
    """
    from fastapi.testclient import TestClient

    from app.core.security import create_access_token, hash_password
    from app.models import RolePermission

    # Entering the client runs the lifespan, which creates the tables and
    # seeds the roles this fixture reads.
    with TestClient(app_instance):
        pass

    slug = f"r5_admin_{uuid.uuid4().hex[:8]}"
    with SessionLocal() as db:
        seeded = db.query(Role).filter(Role.slug == "admin").one()
        held = [p.permission for p in seeded.permissions]
        assert "rbac:manage" in held
        assert "whatsapp:operate" not in held

        role = Role(slug=slug, name="Round-5 Admin", description="attack fixture")
        db.add(role)
        db.flush()
        for perm in held:
            db.add(RolePermission(role_id=role.id, permission=perm))
        user = User(
            email=f"{slug}@quatadigital.com",
            full_name="Round-5 Admin",
            password_hash=hash_password("NotUsed!2026"),
            is_active=True,
            role_id=role.id,
            must_reset_password=False,
            password_changed_at=datetime.now(timezone.utc),
        )
        db.add(user)
        db.commit()
        token = create_access_token(user.id, password_changed_at=user.password_changed_at)
        role_id = role.id
    return {"Authorization": f"Bearer {token}"}, role_id, held


def test_an_admin_cannot_grant_its_own_role_the_wildcard(client, escalation_actor):
    headers, role_id, held = escalation_actor
    r = client.put(
        f"{API}/admin/roles/{role_id}",
        json={"permissions": held + ["*"]},
        headers=headers,
    )
    assert r.status_code == 403, (
        "an rbac:manage holder without the wildcard granted itself the wildcard: "
        f"{r.status_code} {r.text[:200]}"
    )
    with SessionLocal() as db:
        role = db.get(Role, role_id)
        assert "*" not in {p.permission for p in role.permissions}


def test_an_admin_cannot_grant_its_own_role_the_qcp_operate_permission(
    client, escalation_actor
):
    headers, role_id, held = escalation_actor
    r = client.put(
        f"{API}/admin/roles/{role_id}",
        json={"permissions": held + ["whatsapp:operate"]},
        headers=headers,
    )
    assert r.status_code == 403, (
        "the split is advisory if the holder of rbac:manage can grant it: "
        f"{r.status_code} {r.text[:200]}"
    )


def test_an_admin_cannot_create_a_role_carrying_more_than_it_holds(
    client, escalation_actor
):
    headers, _role_id, _held = escalation_actor
    r = client.post(
        f"{API}/admin/roles",
        json={
            "slug": f"r5_super_{uuid.uuid4().hex[:8]}",
            "name": "Escalation",
            "permissions": ["*"],
        },
        headers=headers,
    )
    assert r.status_code == 403, (
        f"a role granting the wildcard was created by a non-wildcard actor: {r.text[:200]}"
    )


def test_the_qcp_operate_permission_is_in_the_catalogue():
    """Otherwise no role can ever hold it and the split is Super-Admin-only."""
    from app.api.routes_admin_extra import ALL_PERMISSIONS

    assert "whatsapp:operate" in {p["key"] for p in ALL_PERMISSIONS}


def test_a_role_holding_the_wildcard_really_does_reach_the_operate_routes(
    client, escalation_actor
):
    """Why the guard above matters: ``*`` on a role is a genuine bypass.

    Granted here directly in the database rather than through the API — the
    API now refuses — so the claim "the roles editor was an escalation path"
    rests on something observed rather than on reading ``deps.py``.
    """
    from app.models import RolePermission

    headers, role_id, held = escalation_actor
    with SessionLocal() as db:
        db.add(RolePermission(role_id=role_id, permission="*"))
        db.commit()
    try:
        r = client.post(
            f"{API}/admin/qcp/accounts/quata_verify/disable", headers=headers
        )
        assert r.status_code != 403, (
            "the wildcard did not bypass whatsapp:operate — then the roles "
            "editor was never an escalation path and this finding is wrong"
        )
    finally:
        with SessionLocal() as db:
            db.query(RolePermission).filter(
                RolePermission.role_id == role_id, RolePermission.permission == "*"
            ).delete(synchronize_session=False)
            db.commit()


def test_a_super_admin_can_still_grant_the_new_permission(client, admin_headers):
    """The guard must not lock the fleet out of delegating QCP operation."""
    slug = f"r5_operator_{uuid.uuid4().hex[:8]}"
    r = client.post(
        f"{API}/admin/roles",
        json={
            "slug": slug,
            "name": "QCP Operator",
            "permissions": ["settings:manage", "whatsapp:operate"],
        },
        headers=admin_headers,
    )
    assert r.status_code == 201, r.text
    assert set(r.json()["permissions"]) == {"settings:manage", "whatsapp:operate"}
    client.delete(f"{API}/admin/roles/{r.json()['id']}", headers=admin_headers)


def test_a_delegated_qcp_operator_can_complete_commissioning(client, admin_headers):
    """Nobody is locked out: a role holding both permissions works end to end."""
    from app.core.security import create_access_token, hash_password

    slug = f"r5_op_{uuid.uuid4().hex[:8]}"
    role_resp = client.post(
        f"{API}/admin/roles",
        json={
            "slug": slug,
            "name": "QCP Operator",
            "permissions": ["settings:manage", "whatsapp:operate"],
        },
        headers=admin_headers,
    )
    assert role_resp.status_code == 201, role_resp.text
    role_id = role_resp.json()["id"]

    with SessionLocal() as db:
        operator = User(
            email=f"{slug}@quatadigital.com",
            full_name="QCP Operator",
            password_hash=hash_password("NotUsed!2026"),
            is_active=True,
            role_id=role_id,
            must_reset_password=False,
            password_changed_at=datetime.now(timezone.utc),
        )
        db.add(operator)
        db.commit()
        op_headers = {
            "Authorization": "Bearer "
            + create_access_token(
                operator.id, password_changed_at=operator.password_changed_at
            )
        }

    product = f"r5_prod_{uuid.uuid4().hex[:8]}"
    assert (
        client.post(
            f"{API}/admin/qcp/products",
            json={"slug": product, "name": "Round-5 product"},
            headers=op_headers,
        ).status_code
        == 201
    )
    assert (
        client.post(
            f"{API}/admin/qcp/products/{product}/api-key", headers=op_headers
        ).status_code
        == 201
    )
    assert (
        client.post(
            f"{API}/admin/qcp/products/{product}/purposes/authentication",
            json={"justification": "round-5 commissioning rehearsal"},
            headers=op_headers,
        ).status_code
        == 200
    )


# ---------------------------------------------------------------------------
# 4b — the separation hole, re-opened by moving the world instead of the rule
# ---------------------------------------------------------------------------

def test_revoking_a_purpose_records_the_rules_it_strands(client, admin_headers):
    """The stranded-rule case: named in the audit log, and not shown as live.

    NOT deactivated, deliberately — see ``qcp_set_product_purposes``. With the
    rule still there ``resolve_route`` refuses with ``purpose_not_permitted``,
    which says what is wrong; deactivating it turns the same refusal into
    ``no_route``, and restoring the grant would not restore the rule, so an
    operator re-opening QuataFood's login path would find the grant back and
    the OTP still dead. What must be true is that nothing *displays* it as
    live and that the event is on the record.
    """
    slug = f"r5_revoke_{uuid.uuid4().hex[:8]}"
    assert (
        client.post(
            f"{API}/admin/qcp/products",
            json={"slug": slug, "name": "Revoke-test product"},
            headers=admin_headers,
        ).status_code
        == 201
    )
    assert (
        client.post(
            f"{API}/admin/qcp/products/{slug}/purposes/authentication",
            json={"justification": "round-5 revoke rehearsal"},
            headers=admin_headers,
        ).status_code
        == 200
    )

    with SessionLocal() as db:
        from app.models import WhatsAppRoutingRule

        product = db.query(WhatsAppProduct).filter(WhatsAppProduct.slug == slug).one()
        rule = WhatsAppRoutingRule(
            product_id=product.id,
            intent="login_otp",
            purpose="authentication",
            template_intent="login_otp",
            locale=None,
            priority=100,
            is_active=True,
        )
        db.add(rule)
        db.commit()
        rule_id = rule.id

    r = client.put(
        f"{API}/admin/qcp/products/{slug}/purposes",
        json={"purposes": ["engagement"]},
        headers=admin_headers,
    )
    assert r.status_code == 200, r.text

    listed = client.get(
        f"{API}/admin/qcp/routing-rules", headers=admin_headers
    ).json()["items"]
    mine = [item for item in listed if item["id"] == rule_id]
    assert mine, "the rule vanished from the console"
    assert mine[0]["is_blocked"] is True
    assert mine[0]["is_effectively_live"] is False, (
        "a rule its product may no longer reach was reported as live"
    )
    assert mine[0]["blocked_detail"], "blocked with no explanation is not an answer"

    with SessionLocal() as db:
        from app.models import WhatsAppAuditLog

        strand = (
            db.query(WhatsAppAuditLog)
            .filter(
                WhatsAppAuditLog.action == "routing_rule.stranded_by_purpose_revoke",
                WhatsAppAuditLog.resource_id == slug,
            )
            .one()
        )
        assert [r["id"] for r in strand.details["rules"]] == [rule_id]

    # And the send still refuses with the reason that names the cause.
    from app.services.whatsapp import routing

    with SessionLocal() as db:
        with pytest.raises(routing.RoutingDenied) as exc:
            routing.resolve_route(
                db,
                product_slug=slug,
                intent="login_otp",
                to_phone_e164="+237600000001",
                variables=("483920",),
            )
    assert exc.value.reason == "purpose_not_permitted"


# ---------------------------------------------------------------------------
# 4c — the unattended template sync actually runs unattended
# ---------------------------------------------------------------------------

def test_the_worker_cycle_reconciles_templates_before_the_delivery_gate(monkeypatch):
    """A re-classification must be caught while sending is paused, not after.

    The endpoint and the function both existed; nothing on a schedule called
    either, so "Meta re-classified our OTP template to marketing" was caught
    whenever an operator next opened the console.
    """
    from app.scripts import whatsapp_worker
    from app.services.whatsapp import settings_store as store
    from app.services.whatsapp import templates as wa_templates

    calls: list[dict] = []
    monkeypatch.setattr(
        wa_templates,
        "scheduled_sync",
        lambda **kw: calls.append(kw) or {"due": 0, "skipped": []},
    )
    # Delivery off — the dormant state, and the state in which this matters
    # most. If the sync sits behind this gate it never runs on a paused fleet.
    monkeypatch.setattr(store, "delivery_enabled", lambda: False)

    summary = whatsapp_worker.run_cycle(
        whatsapp_worker.SYNC_TEMPLATES_EVERY_CYCLES, limit=10
    )
    assert calls, "the worker never asked for a template reconciliation"
    assert summary.get("skipped") == "delivery_disabled"


# ---------------------------------------------------------------------------
# 5 — still dormant
# ---------------------------------------------------------------------------

def test_the_seeded_estate_is_still_inert(client):
    """Fresh install: no live number, no enabled product, no key, no delivery."""
    from app.services.whatsapp import settings_store

    with SessionLocal() as db:
        for slug in ("quata_verify", "quata"):
            account = (
                db.query(WhatsAppAccount).filter(WhatsAppAccount.slug == slug).one()
            )
            assert account.is_active is False, f"{slug} arrived active"
            assert not account.access_token_encrypted, f"{slug} arrived with a token"
            assert not account.app_secret_encrypted
            assert not account.webhook_verify_token_encrypted
        for product in db.query(WhatsAppProduct).filter(
            WhatsAppProduct.slug.in_(["quatapay", "quatafood", "abaqwa", "quatatrade"])
        ):
            assert product.is_enabled is False, f"{product.slug} arrived enabled"
            assert not product.api_key_hash, f"{product.slug} arrived with a key"
    assert settings_store.delivery_enabled() is False
