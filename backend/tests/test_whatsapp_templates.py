"""Template sync, template CRUD and routing-rule CRUD — the root-cause fix.

QCP's original hole was not the missing CHECK constraint. It was that
``whatsapp_templates.category`` was *operator-typed data that nothing
validated and nothing ever re-asked Meta about*. Meta owns the category and
Meta re-classifies templates; a template that becomes MARKETING while
sitting on the Quata Verify number is exactly how a number gets restricted,
and QuataFood's login OTP, payment-PIN reset and phone-change verification
have no email fallback — a restricted Verify number locks those users out.

So the properties pinned here are, in order of how much they matter:

1. **Meta is the authority.** A sync overwrites category and status; a local
   edit never silently wins.
2. **A non-authentication category arriving on Verify is an ALERT, not a
   crash and not a swallow.** The database CHECK refuses the row; that
   refusal is handled as *data* — an audited alert with a reason a human can
   act on — and the offending local row is quarantined so it cannot send.
3. **An operator cannot hand-approve a template.** That is the same class of
   unvalidated-operator-data bug as the original hole.
4. **Routing rules cannot be pointed at a retired, unapproved or
   wrong-number template**, and cannot be duplicated.
5. **Nothing here switches QCP on**, and nothing here returns a credential.
"""
from __future__ import annotations

import uuid

import pytest

from app.db.session import SessionLocal, engine
from app.models import WhatsAppAuditLog, WhatsAppRoutingRule, WhatsAppTemplate
from app.models.base import Base
from tests import whatsapp_world


# Mirrors tests/test_whatsapp_admin_console.py — column names that carry a
# value. None may ever appear as a key in a response from this module.
CREDENTIAL_KEYS = {
    "access_token_encrypted",
    "app_secret_encrypted",
    "webhook_verify_token_encrypted",
    "webhook_secret_encrypted",
    "api_key_hash",
    "phone_number_id",
    "waba_id",
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module", autouse=True)
def _mounted(app_instance):
    """Mount the write router if ``main.py`` has not been wired up yet.

    Registering the router is a one-line change in ``app/main.py``, which
    this build does not own. Mounting it here keeps the module runnable
    either way, and becomes a no-op the moment that line lands.
    """
    from app.api.routes_admin_templates import router

    paths = {getattr(r, "path", None) for r in app_instance.routes}
    if "/api/v1/admin/qcp/routing-rules" not in paths:
        from app.core.config import settings as env_settings

        app_instance.include_router(router, prefix=env_settings.API_PREFIX)
    return True


@pytest.fixture(scope="module")
def world():
    # Mirrors test_whatsapp_invariant: this module can be the first to touch
    # the session database, and the tables are otherwise created by the app
    # lifespan a `client` fixture happens to run.
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    built = whatsapp_world.build(db)
    try:
        yield built
    finally:
        whatsapp_world.teardown(db, built)
        db.close()


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def meta_template(
    name: str,
    *,
    category: str,
    status: str = "APPROVED",
    language: str = "en",
    # Deliberately innocent. The old default said "Your code is {{1}}", which
    # every caller inherited — including the ones asserting ``alerts == []`` —
    # so the body-text guard below could not be added without every one of
    # them lighting up. A code in a body is now a thing a test states on
    # purpose, never a thing it inherits.
    body: str = "Hello {{1}}, your order is on its way.",
    rejected_reason: str | None = None,
) -> dict:
    """One entry as the Graph API's ``message_templates`` edge returns it."""
    payload = {
        "id": f"MT_{uuid.uuid4().hex[:10]}",
        "name": name,
        "language": language,
        "category": category,
        "status": status,
        "components": [{"type": "BODY", "text": body}],
    }
    if rejected_reason:
        payload["rejected_reason"] = rejected_reason
    return payload


def fetcher(*templates: dict, ok: bool = True, error: str | None = None):
    """Stand-in for ``dispatch.fetch_message_templates``."""

    def _fetch(db, account):
        return {"ok": ok, "data": list(templates), "error": error}

    return _fetch


# ---------------------------------------------------------------------------
# 1 — Meta is the authority on category and status
# ---------------------------------------------------------------------------

def test_a_sync_records_the_body_hash_the_placeholders_and_the_time(world, db):
    from app.services.whatsapp import templates as templates_service

    result = templates_service.sync_from_meta(
        db,
        world.quata,
        fetch=fetcher(
            meta_template(
                world.order_template.name,
                category="UTILITY",
                body="Order {{1}} is on its way, arriving {{2}}.",
            ),
            meta_template(world.promo_template.name, category="MARKETING"),
        ),
    )
    assert result["ok"] is True, result
    assert result["alerts"] == []

    row = db.get(WhatsAppTemplate, world.order_template.id)
    db.refresh(row)
    assert row.body_hash and len(row.body_hash) == 64
    assert row.last_synced_at is not None
    assert row.variables == ["1", "2"]
    assert row.provider_template_id


def test_metas_category_overwrites_the_locally_typed_one(world, db):
    from app.services.whatsapp import templates as templates_service

    row = db.get(WhatsAppTemplate, world.order_template.id)
    row.category = "utility"
    db.commit()

    templates_service.sync_from_meta(
        db,
        world.quata,
        fetch=fetcher(meta_template(world.order_template.name, category="MARKETING")),
    )
    db.refresh(row)
    assert row.category == "marketing", "a sync must beat the operator-typed value"

    # Put it back for the tests that follow.
    templates_service.sync_from_meta(
        db,
        world.quata,
        fetch=fetcher(meta_template(world.order_template.name, category="UTILITY")),
    )
    db.refresh(row)
    assert row.category == "utility"


def test_metas_status_overwrites_the_local_one(world, db):
    from app.services.whatsapp import templates as templates_service

    row = db.get(WhatsAppTemplate, world.promo_template.id)
    assert row.status == "approved"

    templates_service.sync_from_meta(
        db,
        world.quata,
        fetch=fetcher(
            meta_template(
                world.promo_template.name,
                category="MARKETING",
                status="REJECTED",
                rejected_reason="INVALID_FORMAT",
            )
        ),
    )
    db.refresh(row)
    assert row.status == "rejected"
    assert row.rejection_reason == "INVALID_FORMAT"


# ---------------------------------------------------------------------------
# 2 — the one that matters: a re-classified template on Quata Verify
# ---------------------------------------------------------------------------

def test_a_reclassified_template_on_verify_alerts_and_is_quarantined(world, db):
    """Meta re-classified the login OTP template to MARKETING.

    The database CHECK refuses ``category='marketing'`` on an
    ``account_purpose='authentication'`` row. That refusal must arrive as
    data: an alert a human has to act on, plus a local row that can no
    longer be selected for sending — never a 500 and never a silent pass.
    """
    from app.services.whatsapp import templates as templates_service

    before_alerts = (
        db.query(WhatsAppAuditLog)
        .filter(WhatsAppAuditLog.action == "template.sync_alert")
        .count()
    )

    result = templates_service.sync_from_meta(
        db,
        world.verify,
        fetch=fetcher(meta_template(world.otp_template.name, category="MARKETING")),
    )

    assert result["ok"] is True, "a refused row is data, not an exception"
    kinds = {a["kind"] for a in result["alerts"]}
    assert "non_auth_category_on_verify" in kinds, result["alerts"]
    alert = next(a for a in result["alerts"] if a["kind"] == "non_auth_category_on_verify")
    assert alert["meta_category"] == "marketing"
    assert alert["template"] == world.otp_template.name
    assert alert["account"] == world.verify.slug
    # A reason a human can act on, not a stack trace.
    assert "Verify" in alert["detail"] or "verification" in alert["detail"]

    row = db.get(WhatsAppTemplate, world.otp_template.id)
    db.refresh(row)
    # The illegal pairing was never written…
    assert row.category == "authentication"
    assert row.account_purpose == "authentication"
    # …and the template can no longer be routed to, because Meta no longer
    # considers it an authentication template.
    assert row.status == "disabled"
    assert row.last_synced_at is not None

    after_alerts = (
        db.query(WhatsAppAuditLog)
        .filter(WhatsAppAuditLog.action == "template.sync_alert")
        .count()
    )
    assert after_alerts > before_alerts, "the alert must be audited, not just returned"

    # Restore for the tests that follow.
    templates_service.sync_from_meta(
        db,
        world.verify,
        fetch=fetcher(meta_template(world.otp_template.name, category="AUTHENTICATION")),
    )
    db.refresh(row)
    assert row.status == "approved"


def test_a_new_non_auth_template_discovered_on_verify_is_refused_as_data(world, db):
    from app.services.whatsapp import templates as templates_service

    name = f"tp_receipt_{uuid.uuid4().hex[:6]}"
    result = templates_service.sync_from_meta(
        db,
        world.verify,
        fetch=fetcher(
            meta_template(world.otp_template.name, category="AUTHENTICATION"),
            meta_template(name, category="UTILITY"),
        ),
    )
    assert result["ok"] is True
    assert result["created"] == 0
    assert {a["kind"] for a in result["alerts"]} == {"non_auth_category_on_verify"}
    assert (
        db.query(WhatsAppTemplate)
        .filter(WhatsAppTemplate.name == name)
        .first()
        is None
    ), "the Verify number must not acquire a utility template"


def test_a_locally_approved_template_meta_does_not_know_is_reported(world, db):
    """Approved here, unknown there, is a send that will fail at the provider."""
    from app.services.whatsapp import templates as templates_service

    promo = db.get(WhatsAppTemplate, world.promo_template.id)
    promo.status = "approved"
    db.commit()

    result = templates_service.sync_from_meta(
        db,
        world.quata,
        fetch=fetcher(meta_template(world.order_template.name, category="UTILITY")),
    )
    missing = [a for a in result["alerts"] if a["kind"] == "approved_locally_missing_at_meta"]
    assert {a["template"] for a in missing} == {world.promo_template.name}
    # Reporting only — a sync never deletes a row from the log.
    db.refresh(promo)
    assert promo.status == "approved"


def test_the_database_refusing_a_row_is_data_not_an_exception(world, db):
    """The belt behind the Python guard, exercised against the real CHECK.

    ``separation_problem`` catches the pairings this build knows about. A
    constraint it does *not* know about must still arrive as a refusal an
    operator can read, mid-sync, without losing the rows already reconciled —
    so the write goes through a SAVEPOINT and a refusal comes back as None.
    """
    from app.services.whatsapp import templates as templates_service

    illegal = WhatsAppTemplate(
        account_id=world.verify.id,
        account_purpose="authentication",
        name=f"tp_illegal_{uuid.uuid4().hex[:6]}",
        language="en",
        # ck_whatsapp_templates_marketing_never_on_verify refuses this row.
        category="marketing",
        intent="illegal",
        status="approved",
        variables=[],
    )
    assert templates_service._write(db, illegal, add=True) is None

    # The session is still usable and nothing was left half-added.
    assert db.query(WhatsAppTemplate).filter(
        WhatsAppTemplate.name == illegal.name
    ).first() is None
    db.commit()


def test_a_failed_fetch_is_reported_not_raised(world, db):
    from app.services.whatsapp import templates as templates_service

    result = templates_service.sync_from_meta(
        db, world.quata, fetch=fetcher(ok=False, error="Access token is not configured.")
    )
    assert result["ok"] is False
    assert result["error"]
    assert result["created"] == result["updated"] == 0


# ---------------------------------------------------------------------------
# 3 — CRUD: an operator cannot hand-approve anything
# ---------------------------------------------------------------------------

def test_a_locally_created_template_starts_unapproved(client, admin_headers, world):
    name = f"tp_new_{uuid.uuid4().hex[:6]}"
    r = client.post(
        "/api/v1/admin/qcp/templates",
        headers=admin_headers,
        json={
            "account": world.quata.slug,
            "name": name,
            "language": "en",
            "category": "utility",
            "intent": "new_thing",
            "body": "Hello {{1}}, your thing is {{2}}.",
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "draft"
    assert body["variables"] == ["1", "2"]
    assert body["body_hash"]
    assert not CREDENTIAL_KEYS & set(body)


def test_an_operator_cannot_declare_a_template_approved(client, admin_headers, world):
    r = client.post(
        "/api/v1/admin/qcp/templates",
        headers=admin_headers,
        json={
            "account": world.quata.slug,
            "name": f"tp_sneaky_{uuid.uuid4().hex[:6]}",
            "language": "en",
            "category": "utility",
            "intent": "sneaky",
            "body": "hi",
            "status": "approved",
        },
    )
    assert r.status_code == 422, r.text


def test_a_non_auth_template_on_verify_is_refused_with_a_reason(client, admin_headers, world):
    r = client.post(
        "/api/v1/admin/qcp/templates",
        headers=admin_headers,
        json={
            "account": world.verify.slug,
            "name": f"tp_bad_{uuid.uuid4().hex[:6]}",
            "language": "en",
            "category": "utility",
            "intent": "bad",
            "body": "hi",
        },
    )
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["reason"] == "non_auth_template_on_verify"


def test_editing_cannot_change_status_or_category_of_a_synced_template(
    client, admin_headers, world
):
    r = client.patch(
        f"/api/v1/admin/qcp/templates/{world.order_template.id}",
        headers=admin_headers,
        json={"status": "approved"},
    )
    assert r.status_code == 422, r.text

    r = client.patch(
        f"/api/v1/admin/qcp/templates/{world.order_template.id}",
        headers=admin_headers,
        json={"category": "marketing"},
    )
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["reason"] == "category_is_owned_by_meta"


def test_retiring_a_template_disables_it(client, admin_headers, world, db):
    name = f"tp_retire_{uuid.uuid4().hex[:6]}"
    created = client.post(
        "/api/v1/admin/qcp/templates",
        headers=admin_headers,
        json={
            "account": world.quata.slug,
            "name": name,
            "language": "en",
            "category": "utility",
            "intent": "retire_me",
            "body": "hi",
        },
    ).json()
    r = client.post(
        f"/api/v1/admin/qcp/templates/{created['id']}/retire", headers=admin_headers
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "disabled"


# ---------------------------------------------------------------------------
# 4 — routing rules
# ---------------------------------------------------------------------------

def _rule(client, admin_headers, world, **overrides):
    payload = {
        "product": world.product_slug,
        "intent": f"intent_{uuid.uuid4().hex[:6]}",
        "purpose": "engagement",
        "template_intent": "order_dispatched",
        "locale": None,
        "priority": 100,
        "fallback_channel": "none",
    }
    payload.update(overrides)
    return client.post(
        "/api/v1/admin/qcp/routing-rules", headers=admin_headers, json=payload
    )


def test_a_new_rule_is_created_inactive(client, admin_headers, world):
    r = _rule(client, admin_headers, world)
    assert r.status_code == 201, r.text
    assert r.json()["is_active"] is False, "a new rule must take no traffic"


def test_a_colliding_rule_is_refused(client, admin_headers, world):
    intent = f"intent_{uuid.uuid4().hex[:6]}"
    assert _rule(client, admin_headers, world, intent=intent).status_code == 201
    clash = _rule(client, admin_headers, world, intent=intent)
    assert clash.status_code == 409, clash.text
    assert clash.json()["detail"]["reason"] == "duplicate_rule"


def test_a_rule_routing_authentication_traffic_to_the_engagement_number_is_refused(
    client, admin_headers, world
):
    r = _rule(
        client, admin_headers, world, purpose="engagement", template_intent="login_otp"
    )
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["reason"] == "auth_traffic_on_engagement_number"


def test_a_rule_for_a_purpose_the_product_may_not_reach_is_refused(
    client, admin_headers, world, db
):
    from app.models import WhatsAppProduct

    product = db.get(WhatsAppProduct, world.product.id)
    product.allowed_purposes = ["engagement"]
    db.commit()
    try:
        r = _rule(
            client,
            admin_headers,
            world,
            purpose="authentication",
            template_intent="login_otp",
        )
        assert r.status_code == 409, r.text
        assert r.json()["detail"]["reason"] == "purpose_not_permitted"
    finally:
        product.allowed_purposes = ["authentication", "engagement"]
        db.commit()


def test_a_rule_cannot_be_activated_onto_an_unapproved_template(
    client, admin_headers, world, db
):
    intent = f"draft_intent_{uuid.uuid4().hex[:6]}"
    template_intent = f"draft_tpl_{uuid.uuid4().hex[:6]}"
    client.post(
        "/api/v1/admin/qcp/templates",
        headers=admin_headers,
        json={
            "account": world.quata.slug,
            "name": f"tp_{template_intent}",
            "language": "en",
            "category": "utility",
            "intent": template_intent,
            "body": "hi",
        },
    )
    created = _rule(
        client, admin_headers, world, intent=intent, template_intent=template_intent
    )
    assert created.status_code == 201, created.text
    r = client.post(
        f"/api/v1/admin/qcp/routing-rules/{created.json()['id']}/activate",
        headers=admin_headers,
    )
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["reason"] == "template_not_approved"
    assert (
        db.get(WhatsAppRoutingRule, created.json()["id"]).is_active is False
    )


def test_a_rule_cannot_be_activated_onto_a_retired_template(
    client, admin_headers, world, db
):
    intent = f"retired_intent_{uuid.uuid4().hex[:6]}"
    created = _rule(
        client,
        admin_headers,
        world,
        intent=intent,
        template_intent=world.order_template.intent,
    )
    assert created.status_code == 201, created.text
    rule_id = created.json()["id"]

    row = db.get(WhatsAppTemplate, world.order_template.id)
    row.status = "disabled"
    db.commit()
    try:
        r = client.post(
            f"/api/v1/admin/qcp/routing-rules/{rule_id}/activate", headers=admin_headers
        )
        assert r.status_code == 409, r.text
        assert r.json()["detail"]["reason"] == "template_not_approved"
    finally:
        row.status = "approved"
        db.commit()

    ok = client.post(
        f"/api/v1/admin/qcp/routing-rules/{rule_id}/activate", headers=admin_headers
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["is_active"] is True


def test_coverage_names_an_intent_with_no_rule(client, admin_headers, world):
    template_intent = f"orphan_{uuid.uuid4().hex[:6]}"
    client.post(
        "/api/v1/admin/qcp/templates",
        headers=admin_headers,
        json={
            "account": world.quata.slug,
            "name": f"tp_{template_intent}",
            "language": "en",
            "category": "utility",
            "intent": template_intent,
            "product": world.product_slug,
            "body": "hi",
        },
    )
    r = client.get(
        f"/api/v1/admin/qcp/routing-rules/coverage?product={world.product_slug}",
        headers=admin_headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert template_intent in body["template_intents_without_rule"]


def test_deleting_a_rule_is_audited(client, admin_headers, world, db):
    created = _rule(client, admin_headers, world)
    rule_id = created.json()["id"]
    r = client.delete(
        f"/api/v1/admin/qcp/routing-rules/{rule_id}", headers=admin_headers
    )
    assert r.status_code == 200, r.text
    assert db.get(WhatsAppRoutingRule, rule_id) is None
    assert (
        db.query(WhatsAppAuditLog)
        .filter(WhatsAppAuditLog.action == "routing_rule.deleted")
        .filter(WhatsAppAuditLog.resource_id == str(rule_id))
        .count()
        == 1
    )


# ---------------------------------------------------------------------------
# 5 — dormancy and secrets
# ---------------------------------------------------------------------------

def test_every_write_is_audited_with_an_actor_and_a_fingerprint(
    client, admin_headers, world, db
):
    name = f"tp_audit_{uuid.uuid4().hex[:6]}"
    created = client.post(
        "/api/v1/admin/qcp/templates",
        headers=admin_headers,
        json={
            "account": world.quata.slug,
            "name": name,
            "language": "en",
            "category": "utility",
            "intent": "audited",
            "body": "hi {{1}}",
        },
    ).json()
    client.patch(
        f"/api/v1/admin/qcp/templates/{created['id']}",
        headers=admin_headers,
        json={"intent": "audited_v2"},
    )
    row = (
        db.query(WhatsAppAuditLog)
        .filter(WhatsAppAuditLog.action == "template.updated")
        .filter(WhatsAppAuditLog.resource_id == str(created["id"]))
        .one()
    )
    assert row.actor_id is not None
    assert row.details["changed"]["intent"] == {"from": "audited", "to": "audited_v2"}
    assert row.details["before_fingerprint"] != row.details["after_fingerprint"]


def test_nothing_here_switches_qcp_on(client, admin_headers, world):
    """The seeded estate must still be dormant after everything above."""
    overview = client.get("/api/v1/admin/qcp/overview", headers=admin_headers).json()
    seeded_accounts = {a["slug"]: a for a in overview["accounts"]}
    for slug in ("quata_verify", "quata"):
        assert seeded_accounts[slug]["is_active"] is False
        assert seeded_accounts[slug]["configured"] is False
    seeded_products = {p["slug"]: p for p in overview["products"]}
    for slug in ("quatapay", "quatafood", "abaqwa", "quatatrade"):
        assert seeded_products[slug]["is_enabled"] is False
        assert seeded_products[slug]["has_api_key"] is False
    assert overview["gates"]["delivery_enabled"] is False


def test_no_response_from_this_module_carries_a_credential(client, admin_headers, world):
    for path in (
        "/api/v1/admin/qcp/routing-rules",
        f"/api/v1/admin/qcp/routing-rules/coverage?product={world.product_slug}",
        "/api/v1/admin/qcp/templates/alerts",
    ):
        body = client.get(path, headers=admin_headers).json()
        blob = repr(body)
        for key in CREDENTIAL_KEYS:
            assert key not in blob, f"{path} leaked {key}"


# ---------------------------------------------------------------------------
# 6 — a verification code in the BODY of a non-authentication template
#
# Redaction keys on ``category`` (which fixed authentication completely) and
# on the *name* of a placeholder (which covers hand-written templates).
# Neither helps for the templates that will actually exist in production:
# Meta's are pulled down with numbered placeholders, so the name signal is
# empty, and a code carried by a Meta-sourced template with an innocent name
# on the engagement number is stored in clear.
#
# The signal that is *not* empty is the body text, which Meta gives us and
# which is written in a human language. So the pairing is refused where the
# template is created or synced, rather than guessed at when a message is
# sent — which is where the previous three attempts failed.
# ---------------------------------------------------------------------------

def test_a_body_that_asks_for_a_verification_code_names_the_problem(world):
    """The detector itself, before any I/O — English and French."""
    from app.services.whatsapp import templates as templates_service

    for body in (
        "Your verification code is {{1}}.",
        "{{1}} is your WhatsApp verification code. Do not share this code.",
        "Your one-time password is {{1}}.",
        "Use OTP {{1}} to continue.",
        "Votre code de vérification est {{1}}.",
        "Votre mot de passe à usage unique est {{1}}. Ne partagez ce code avec personne.",
        "Voici votre code de sécurité : {{1}}.",
        "Votre code PIN temporaire est {{1}}.",
    ):
        problem = templates_service.body_code_problem("utility", body)
        assert problem is not None, body
        severity, reason, detail = problem
        assert severity == templates_service.SIGNAL_BLOCK, (body, problem)
        assert reason == "verification_code_body_needs_auth_category"
        assert detail and "authentication" in detail.lower()


def test_an_ordinary_engagement_body_is_left_alone(world):
    """The constraint that makes this a fix rather than a regression.

    Order ids, ETAs, amounts, customer and restaurant names must keep
    working — and the operator must not be blocked from writing the template
    that carries them.
    """
    from app.services.whatsapp import templates as templates_service

    for body in (
        "Order {{1}} is on its way, arriving {{2}}.",
        "Hi {{1}}, {{2}} has accepted your order. Total {{3}} FCFA.",
        "Votre commande {{1}} de {{2}} arrive vers {{3}}.",
        "Bonjour {{1}}, votre livreur {{2}} est à {{3}} minutes.",
        "Utilisez le code promo {{1}} pour 20% de réduction ce week-end.",
        "Your tracking code is {{1}} — follow your parcel here.",
        "Chez Paul • Douala vous remercie, {{1}}.",
    ):
        assert templates_service.body_code_problem("utility", body) is None, body
        assert templates_service.body_code_problem("marketing", body) is None, body


def test_an_authentication_template_may_of_course_carry_a_code(world):
    from app.services.whatsapp import templates as templates_service

    assert (
        templates_service.body_code_problem(
            "authentication", "Votre code de vérification est {{1}}."
        )
        is None
    )


def test_an_ambiguous_body_warns_rather_than_blocking(world):
    """A false block on a legitimate template is its own outage."""
    from app.services.whatsapp import templates as templates_service

    for body in (
        "Your booking confirmation code is {{1}}.",
        "Votre code de réservation est {{1}}.",
        "Give the driver the code {{1}} on arrival.",
        "Votre code {{1}} pour retirer votre commande.",
    ):
        problem = templates_service.body_code_problem("utility", body)
        assert problem is not None, body
        assert problem[0] == templates_service.SIGNAL_WARN, (body, problem)


def test_creating_a_non_auth_template_that_asks_for_a_code_is_refused(
    client, admin_headers, world
):
    r = client.post(
        "/api/v1/admin/qcp/templates",
        headers=admin_headers,
        json={
            "account": world.quata.slug,
            "name": f"tp_sneaky_code_{uuid.uuid4().hex[:6]}",
            "language": "fr",
            "category": "utility",
            "intent": "order_update",
            "body": "Votre code de vérification est {{1}}.",
        },
    )
    assert r.status_code == 409, r.text
    detail = r.json()["detail"]
    assert detail["reason"] == "verification_code_body_needs_auth_category"
    assert "authentication" in detail["detail"].lower()


def test_editing_a_body_to_carry_a_code_is_refused_too(client, admin_headers, world):
    created = client.post(
        "/api/v1/admin/qcp/templates",
        headers=admin_headers,
        json={
            "account": world.quata.slug,
            "name": f"tp_edit_code_{uuid.uuid4().hex[:6]}",
            "language": "en",
            "category": "utility",
            "intent": f"edit_code_{uuid.uuid4().hex[:6]}",
            "body": "Order {{1}} is on its way.",
        },
    )
    assert created.status_code == 201, created.text
    r = client.patch(
        f"/api/v1/admin/qcp/templates/{created.json()['id']}",
        headers=admin_headers,
        json={"body": "Your one-time password is {{1}}."},
    )
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["reason"] == "verification_code_body_needs_auth_category"


def test_a_warning_body_is_created_and_the_warning_is_returned(
    client, admin_headers, world
):
    r = client.post(
        "/api/v1/admin/qcp/templates",
        headers=admin_headers,
        json={
            "account": world.quata.slug,
            "name": f"tp_warn_{uuid.uuid4().hex[:6]}",
            "language": "en",
            "category": "utility",
            "intent": f"pickup_{uuid.uuid4().hex[:6]}",
            "body": "Give the driver the code {{1}} on arrival.",
        },
    )
    assert r.status_code == 201, r.text
    warnings = r.json()["warnings"]
    assert warnings, "an uncertain body must still be reported"
    assert warnings[0]["code"] == "possible_verification_code_body"


def test_a_meta_sourced_code_template_on_the_engagement_number_is_quarantined(
    world, db
):
    """The production shape of the defect, end to end.

    Meta's own templates are positional, so the placeholder is ``{{1}}`` and
    the *name* carries nothing. The category says ``utility`` and the number
    is the engagement one, so no existing rule fires — and the code would
    land in ``whatsapp_messages.variables`` in clear. The body is the one
    honest signal, and it is enough.
    """
    from app.services.whatsapp import templates as templates_service

    name = f"tp_meta_code_{uuid.uuid4().hex[:6]}"
    result = templates_service.sync_from_meta(
        db,
        world.quata,
        fetch=fetcher(
            meta_template(
                name,
                category="UTILITY",
                language="fr",
                body="Votre code de vérification est {{1}}. Ne le partagez avec personne.",
            )
        ),
    )
    assert result["ok"] is True, result
    alert = next(
        (
            a
            for a in result["alerts"]
            if a["kind"] == "verification_code_body_not_authentication"
        ),
        None,
    )
    assert alert is not None, result["alerts"]
    assert alert["severity"] == "error"
    assert alert["template"] == name
    assert alert["account"] == world.quata.slug

    row = db.query(WhatsAppTemplate).filter(WhatsAppTemplate.name == name).one()
    assert row.status == "disabled", "a code template on QUATA must not be routable"
    assert result["quarantined"] >= 1


def test_a_meta_sourced_code_template_already_approved_here_is_quarantined(world, db):
    from app.services.whatsapp import templates as templates_service

    name = f"tp_meta_flip_{uuid.uuid4().hex[:6]}"
    templates_service.sync_from_meta(
        db,
        world.quata,
        fetch=fetcher(
            meta_template(name, category="UTILITY", body="Order {{1}} is on its way.")
        ),
    )
    row = db.query(WhatsAppTemplate).filter(WhatsAppTemplate.name == name).one()
    assert row.status == "approved"

    templates_service.sync_from_meta(
        db,
        world.quata,
        fetch=fetcher(
            meta_template(
                name,
                category="UTILITY",
                body="{{1}} is your verification code. Do not share this code.",
            )
        ),
    )
    db.refresh(row)
    assert row.status == "disabled"


def test_an_ordinary_meta_sync_raises_no_body_alert(world, db):
    from app.services.whatsapp import templates as templates_service

    result = templates_service.sync_from_meta(
        db,
        world.quata,
        fetch=fetcher(
            meta_template(
                world.order_template.name,
                category="UTILITY",
                body="Commande {{1}} en route, arrivée vers {{2}}.",
            )
        ),
    )
    kinds = {a["kind"] for a in result["alerts"]}
    assert "verification_code_body_not_authentication" not in kinds
    assert "possible_verification_code_body" not in kinds


def test_ordinary_engagement_variables_stay_readable(world):
    """The hard constraint, restated where it could regress.

    Redaction keys on category precisely so the admin console can answer
    "what did we send this customer?". A body-text guard must not have turned
    into a blanket digest.
    """
    from app.services.whatsapp.redaction import redact_variables

    stored = redact_variables(
        {"1": "ORD-88213", "2": "18:40", "3": "12500 FCFA", "4": "Chez Paul"},
        template_category="utility",
        intent="order_dispatched",
        declared_names=["order_id", "eta", "amount", "restaurant"],
    )
    assert stored == {
        "1": "ORD-88213",
        "2": "18:40",
        "3": "12500 FCFA",
        "4": "Chez Paul",
    }


# ---------------------------------------------------------------------------
# 7 — a rule whose product lost the purpose it routes to
# ---------------------------------------------------------------------------

def test_a_rule_left_behind_by_a_revoked_purpose_is_shown_as_blocked(
    client, admin_headers, world, db
):
    """The send is genuinely refused, so nobody is at risk — but the screen
    said the rule was live, which is its own harm: the operator believes an
    OTP path exists that does not."""
    from app.models import WhatsAppProduct

    created = _rule(
        client,
        admin_headers,
        world,
        intent=f"revoked_{uuid.uuid4().hex[:6]}",
        purpose="authentication",
        template_intent=world.otp_template.intent,
        fallback_channel="email",
    )
    assert created.status_code == 201, created.text
    rule_id = created.json()["id"]
    activated = client.post(
        f"/api/v1/admin/qcp/routing-rules/{rule_id}/activate", headers=admin_headers
    )
    assert activated.status_code == 200, activated.text
    assert activated.json()["is_blocked"] is False
    assert activated.json()["is_effectively_live"] is True

    product = db.get(WhatsAppProduct, world.product.id)
    product.allowed_purposes = ["engagement"]
    db.commit()
    try:
        listed = client.get(
            f"/api/v1/admin/qcp/routing-rules?product={world.product_slug}",
            headers=admin_headers,
        )
        assert listed.status_code == 200, listed.text
        row = next(r for r in listed.json()["items"] if r["id"] == rule_id)
        assert row["is_active"] is True, "the stored row is still switched on"
        assert row["is_blocked"] is True, "…but it carries nothing, and must say so"
        assert row["is_effectively_live"] is False
        assert row["blocked_reason"] == "purpose_not_permitted"
        assert world.product_slug in row["blocked_detail"]
    finally:
        product.allowed_purposes = ["authentication", "engagement"]
        db.commit()
        client.post(
            f"/api/v1/admin/qcp/routing-rules/{rule_id}/deactivate",
            headers=admin_headers,
        )


def test_an_unaffected_rule_is_not_shown_as_blocked(client, admin_headers, world):
    created = _rule(client, admin_headers, world)
    assert created.status_code == 201, created.text
    listed = client.get(
        f"/api/v1/admin/qcp/routing-rules?product={world.product_slug}",
        headers=admin_headers,
    )
    row = next(r for r in listed.json()["items"] if r["id"] == created.json()["id"])
    assert row["is_blocked"] is False
    assert row["blocked_reason"] is None


# ---------------------------------------------------------------------------
# 8 — the sync runs without anyone clicking
#
# Meta re-classifying a template to marketing is the exact event the whole
# two-number separation exists to catch. Catching it "whenever somebody next
# opens the screen" is not catching it.
# ---------------------------------------------------------------------------

def _counting_fetcher(seen: list, *templates: dict):
    def _fetch(db, account):
        seen.append(account.slug)
        return {"ok": True, "data": list(templates), "error": None}

    return _fetch


def test_a_scheduled_sync_reconciles_accounts_nobody_clicked(world, db):
    from app.services.whatsapp import templates as templates_service

    seen: list = []
    result = templates_service.scheduled_sync(
        db, fetch=_counting_fetcher(seen), interval_seconds=0
    )
    assert result["ok"] is True, result
    assert set(seen) == {world.verify.slug, world.quata.slug}, seen
    assert {r["account"] for r in result["results"]} == set(seen)


def test_a_scheduled_sync_does_not_re_ask_meta_inside_its_interval(world, db):
    from app.services.whatsapp import templates as templates_service

    templates_service.scheduled_sync(
        db, fetch=_counting_fetcher([]), interval_seconds=0
    )
    seen: list = []
    result = templates_service.scheduled_sync(
        db, fetch=_counting_fetcher(seen), interval_seconds=3600
    )
    assert seen == [], "a sync a moment ago is not due again"
    assert result["due"] == 0
    assert result["results"] == []


def test_a_scheduled_sync_against_a_dormant_install_touches_nothing(world, db):
    """QCP ships dormant. The scheduler must be safe to install on day one and
    must not switch anything on as a side effect."""
    from app.models import WhatsAppAccount
    from app.services.whatsapp import templates as templates_service

    ids = [world.verify.id, world.quata.id]
    db.query(WhatsAppAccount).filter(WhatsAppAccount.id.in_(ids)).update(
        {WhatsAppAccount.is_active: False}, synchronize_session=False
    )
    db.commit()
    seen: list = []
    try:
        result = templates_service.scheduled_sync(
            db, fetch=_counting_fetcher(seen), interval_seconds=0
        )
        assert seen == [], "a dormant install must not dial Meta"
        assert result["ok"] is True
        assert result["due"] == 0
        assert result["results"] == []
    finally:
        db.query(WhatsAppAccount).filter(WhatsAppAccount.id.in_(ids)).update(
            {WhatsAppAccount.is_active: True}, synchronize_session=False
        )
        db.commit()
        restored = db.query(WhatsAppAccount).filter(WhatsAppAccount.id.in_(ids)).all()
        assert all(a.is_active for a in restored)


def test_an_account_with_no_stored_credential_is_skipped_not_dialled(world, db):
    from app.models import WhatsAppAccount
    from app.services.whatsapp import templates as templates_service

    account = db.get(WhatsAppAccount, world.quata.id)
    stored = account.access_token_encrypted
    account.access_token_encrypted = None
    db.commit()
    seen: list = []
    try:
        result = templates_service.scheduled_sync(
            db, fetch=_counting_fetcher(seen), interval_seconds=0
        )
        assert world.quata.slug not in seen
        skipped = {s["account"]: s["reason"] for s in result["skipped"]}
        assert skipped.get(world.quata.slug) == "no_credential"
    finally:
        account.access_token_encrypted = stored
        db.commit()


def test_the_scheduled_sync_endpoint_is_reachable_and_enables_nothing(
    client, admin_headers, world
):
    """The repo schedules background work two ways — the worker loop, and an
    idempotent endpoint hit from cron (``infra/cron/retention-prune.cron``).
    This is the second, and it is what makes the sync run unattended."""
    r = client.post("/api/v1/admin/qcp/templates/sync-due", headers=admin_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert "due" in body and "results" in body

    overview = client.get("/api/v1/admin/qcp/overview", headers=admin_headers).json()
    assert overview["gates"]["delivery_enabled"] is False


def test_the_scheduled_sync_endpoint_needs_authentication(client):
    assert client.post("/api/v1/admin/qcp/templates/sync-due").status_code == 401
