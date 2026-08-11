"""QCP product-facing gateway: authentication, isolation, routing, threads.

Two properties are what this file exists to pin down:

1. **A product may only act on its own conversations.** Verified, not
   assumed — every conversation route is exercised with a second product's
   valid credentials and must answer 404.
2. **A product cannot select the account.** There is no request field that
   names one (the send schema forbids extras), and the number that actually
   carries a message is a function of the routing rules alone. A product
   asking for a promotion on the authentication purpose is refused; nothing
   ever leaves Quata Verify that is not an approved authentication template.

Delivery is deliberately stubbed: ``dispatch.schedule`` is a no-op for the
whole module, so nothing here touches Meta and row states are deterministic.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.core.config import settings as env_settings
from app.db.session import SessionLocal
from app.models import (
    Role,
    RolePermission,
    SiteSetting,
    User,
    WhatsAppAccount,
    WhatsAppConversation,
    WhatsAppMessage,
    WhatsAppProduct,
    WhatsAppRoutingRule,
    WhatsAppTemplate,
)
from app.services import site_settings
from app.services.whatsapp import dispatch


SUFFIX = uuid.uuid4().hex[:6]

ALPHA = f"gwalpha{SUFFIX}"
BETA = f"gwbeta{SUFFIX}"
ALPHA_KEY = f"qcp_live_{uuid.uuid4().hex}"
BETA_KEY = f"qcp_live_{uuid.uuid4().hex}"

PHONE = "+237600000001"
OTHER_PHONE = "+237600000002"

# App secret for the engagement number, so this module can post a *real*
# signed inbound webhook rather than faking the ingest path. The inbound
# half is where cross-product attribution is actually decided.
WEBHOOK_SECRET = f"gw-app-secret-{SUFFIX}"


def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module", autouse=True)
def _no_delivery():
    """Never hand a message to the transport during these tests."""
    original = dispatch.schedule
    dispatch.schedule = lambda *a, **k: None
    yield
    dispatch.schedule = original


@pytest.fixture(scope="module")
def world(app_instance):
    """Two active accounts, two products, three templates, five rules.

    Built directly against the DB rather than through the admin API so this
    file tests the *product* surface in isolation from the console.
    """
    from fastapi.testclient import TestClient

    # Entering the client once runs the app lifespan, which creates the
    # tables and seeds the admin user these tests assign work to.
    with TestClient(app_instance):
        pass

    was_enabled = env_settings.WHATSAPP_ENABLED
    env_settings.WHATSAPP_ENABLED = True

    db = SessionLocal()
    try:
        # --- the DB half of the delivery gate ------------------------------
        row = (
            db.query(SiteSetting)
            .filter(SiteSetting.key == "whatsapp.delivery_enabled")
            .first()
        )
        if row is None:
            row = SiteSetting(
                key="whatsapp.delivery_enabled",
                group="whatsapp",
                label="WhatsApp delivery",
                field_type="toggle",
            )
            db.add(row)
        previous_toggle = row.value
        row.value = "true"

        # --- the two numbers -------------------------------------------------
        # Dedicated rows, not the seeded quata_verify/quata pair: those must
        # stay dormant and credential-free (test_whatsapp_schema asserts it),
        # and the partial unique index allows one *active* account per purpose,
        # which these two claim for the duration of this module.
        from app.services.whatsapp.credentials import encrypt_wa_secret

        accounts = {}
        for name, purpose, display in (
            ("Verify (gateway test)", "authentication", "+237600009999"),
            ("Engagement (gateway test)", "engagement", "+237600008888"),
        ):
            acc = WhatsAppAccount(
                slug=f"gw_{purpose}_{SUFFIX}",
                name=name,
                purpose=purpose,
                phone_number_id=f"pnid_{purpose}_{SUFFIX}",
                waba_id=f"waba_{purpose}_{SUFFIX}",
                display_phone=display,
                app_secret_encrypted=encrypt_wa_secret(WEBHOOK_SECRET),
                is_active=True,
            )
            db.add(acc)
            accounts[purpose] = acc
        db.flush()

        # --- two products, both fully entitled ------------------------------
        products = {}
        for slug, key in ((ALPHA, ALPHA_KEY), (BETA, BETA_KEY)):
            product = WhatsAppProduct(
                slug=slug,
                name=slug,
                is_enabled=True,
                api_key_hash=_hash(key),
                api_key_prefix=key[:12],
                # Deliberately generous: the isolation and account-selection
                # properties must hold even for a product allowed everywhere.
                allowed_purposes=["authentication", "engagement"],
                default_locale="en",
            )
            db.add(product)
            products[slug] = product
        db.flush()

        verify = accounts["authentication"]
        engage = accounts["engagement"]

        templates = {}
        for intent, category, account, variables in (
            ("login_otp", "authentication", verify, ["code"]),
            ("order_dispatched", "utility", engage, ["order"]),
            ("promo_drop", "marketing", engage, []),
        ):
            tpl = WhatsAppTemplate(
                account_id=account.id,
                account_purpose=account.purpose,
                name=f"{intent}_{SUFFIX}",
                language="en",
                category=category,
                intent=intent,
                status="approved",
                variables=variables,
            )
            db.add(tpl)
            templates[intent] = tpl
        db.flush()

        alpha = products[ALPHA]
        beta = products[BETA]
        rules = [
            # (product, intent, purpose, template_intent)
            (alpha, "login_otp", "authentication", "login_otp"),
            (alpha, "order_dispatched", "engagement", "order_dispatched"),
            (alpha, "promo_drop", "engagement", "promo_drop"),
            # A misconfigured rule that tries to push a promotion out of the
            # authentication number. It must never resolve.
            (alpha, "promo_via_verify", "authentication", "promo_drop"),
            (beta, "order_dispatched", "engagement", "order_dispatched"),
        ]
        for product, intent, purpose, template_intent in rules:
            db.add(
                WhatsAppRoutingRule(
                    product_id=product.id,
                    intent=intent,
                    purpose=purpose,
                    template_intent=template_intent,
                    locale=None,
                    is_active=True,
                    conditions={},
                )
            )
        db.commit()

        state = {
            "alpha_id": alpha.id,
            "beta_id": beta.id,
            "verify_id": verify.id,
            "engage_id": engage.id,
            "engage_slug": engage.slug,
            "engage_phone_number_id": engage.phone_number_id,
            "template_ids": {k: v.id for k, v in templates.items()},
        }
    finally:
        db.close()

    site_settings.invalidate_cache()
    yield state

    db = SessionLocal()
    try:
        setting = (
            db.query(SiteSetting)
            .filter(SiteSetting.key == "whatsapp.delivery_enabled")
            .first()
        )
        if setting is not None:
            setting.value = previous_toggle
        account_ids = [state["verify_id"], state["engage_id"]]
        # Reverse dependency order: messages → conversations → rules →
        # templates → products → accounts.
        db.query(WhatsAppMessage).filter(
            WhatsAppMessage.account_id.in_(account_ids)
        ).delete(synchronize_session=False)
        db.query(WhatsAppConversation).filter(
            WhatsAppConversation.account_id.in_(account_ids)
        ).delete(synchronize_session=False)
        db.query(WhatsAppRoutingRule).filter(
            WhatsAppRoutingRule.product_id.in_([state["alpha_id"], state["beta_id"]])
        ).delete(synchronize_session=False)
        db.query(WhatsAppTemplate).filter(
            WhatsAppTemplate.account_id.in_(account_ids)
        ).delete(synchronize_session=False)
        for pid in (state["alpha_id"], state["beta_id"]):
            product = db.get(WhatsAppProduct, pid)
            if product is not None:
                db.delete(product)
        db.flush()
        db.query(WhatsAppAccount).filter(WhatsAppAccount.id.in_(account_ids)).delete(
            synchronize_session=False
        )
        db.commit()
    finally:
        db.close()
    site_settings.invalidate_cache()
    env_settings.WHATSAPP_ENABLED = was_enabled


# ---------------------------------------------------------------------------
# Signed-request helpers
# ---------------------------------------------------------------------------

def _sign(
    slug: str,
    key: str,
    body: bytes,
    *,
    method: str = "POST",
    path: str = "",
    idempotency_key: str | None = None,
) -> dict:
    """Sign the bound request: verb, routed path, idempotency key, then body.

    ``path`` is the full routed path including the ``/api/v1`` prefix and
    *excluding* any query string, which is what ``request.url.path`` gives
    the verifier.
    """
    ts = str(int(time.time()))
    material = (
        f"{method.upper()}\n{path}\n{idempotency_key or ''}\n{ts}."
    ).encode("utf-8") + body
    signature = hmac.new(_hash(key).encode("utf-8"), material, hashlib.sha256).hexdigest()
    headers = {
        "X-QCP-Product": slug,
        "X-QCP-Key": key,
        "X-QCP-Timestamp": ts,
        "X-QCP-Signature": signature,
        "Content-Type": "application/json",
    }
    if idempotency_key:
        headers["X-QCP-Idempotency-Key"] = idempotency_key
    return headers


def _post(client, path: str, payload: dict, *, slug=ALPHA, key=ALPHA_KEY, idempotency_key=None):
    body = json.dumps(payload).encode("utf-8")
    full = f"/api/v1{path}"
    return client.post(
        full,
        content=body,
        headers=_sign(
            slug, key, body, method="POST", path=full, idempotency_key=idempotency_key
        ),
    )


def _get(client, path: str, *, slug=ALPHA, key=ALPHA_KEY):
    full = f"/api/v1{path}"
    # The query string is not part of the signed material — ``request.url.path``
    # stops at the '?'. Splitting here rather than signing ``full`` keeps the
    # helper honest about the actual contract.
    return client.get(
        full, headers=_sign(slug, key, b"", method="GET", path=full.split("?", 1)[0])
    )


def _inbound(
    client,
    state,
    *,
    phone: str,
    text: str,
    timestamp: int | None = None,
    context_wamid: str | None = None,
):
    """Post a genuine, Meta-signed inbound text on the engagement number.

    ``context_wamid`` reproduces what Meta puts on the message when the
    customer used *reply* on a specific bubble: ``context.id`` is the wamid
    of the message being answered.
    """
    wa_id = phone.lstrip("+")
    message = {
        "from": wa_id,
        "id": f"wamid.GW{uuid.uuid4().hex.upper()}",
        "timestamp": str(timestamp if timestamp is not None else int(time.time())),
        "type": "text",
        "text": {"body": text},
    }
    if context_wamid:
        message["context"] = {"from": "237600008888", "id": context_wamid}
    envelope = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": f"waba_engagement_{SUFFIX}",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "+237600008888",
                                "phone_number_id": state["engage_phone_number_id"],
                            },
                            "messages": [message],
                        },
                    }
                ],
            }
        ],
    }
    raw = json.dumps(envelope, separators=(",", ":")).encode("utf-8")
    signature = "sha256=" + hmac.new(
        WEBHOOK_SECRET.encode("utf-8"), raw, hashlib.sha256
    ).hexdigest()
    return client.post(
        f"/api/v1/whatsapp/webhook/{state['engage_slug']}",
        content=raw,
        headers={"Content-Type": "application/json", "X-Hub-Signature-256": signature},
    )


def _thread_for(state, *, product_key: str, phone: str, account_key: str = "engage_id"):
    """Create a conversation owned by one product, with a live 24h window."""
    db = SessionLocal()
    try:
        row = WhatsAppConversation(
            account_id=state[account_key],
            product_id=state[product_key],
            wa_contact_id=phone.lstrip("+") + uuid.uuid4().hex[:4],
            phone_e164=phone,
            state="open",
            last_inbound_at=datetime.now(timezone.utc),
            service_window_expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        )
        db.add(row)
        db.commit()
        return row.id
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

def test_send_requires_credentials(client, world):
    r = client.post("/api/v1/whatsapp/messages", json={"intent": "login_otp", "to": PHONE})
    assert r.status_code == 401


def test_unknown_product_and_wrong_key_are_indistinguishable(client, world):
    body = json.dumps({"intent": "login_otp", "to": PHONE, "variables": ["123456"]}).encode()
    path = "/api/v1/whatsapp/messages"
    wrong_key = client.post(
        path, content=body, headers=_sign(ALPHA, "not-the-key", body, path=path)
    )
    unknown = client.post(
        path,
        content=body,
        headers=_sign("no-such-product", ALPHA_KEY, body, path=path),
    )
    assert wrong_key.status_code == 401
    assert unknown.status_code == 401
    assert wrong_key.json()["detail"] == unknown.json()["detail"]


def test_missing_signature_is_rejected(client, world):
    body = json.dumps({"intent": "login_otp", "to": PHONE, "variables": ["123456"]}).encode()
    r = client.post(
        "/api/v1/whatsapp/messages",
        content=body,
        headers={
            "X-QCP-Product": ALPHA,
            "X-QCP-Key": ALPHA_KEY,
            "Content-Type": "application/json",
        },
    )
    assert r.status_code == 401


def test_a_captured_signature_does_not_replay_onto_another_route(client, world):
    """One empty-body GET signature used to unlock every empty-body route.

    ``/whatsapp/health``, ``/whatsapp/conversations`` and the three
    ``/open|/close|/return-to-ai`` lifecycle POSTs all carry an empty body, so
    signing ``f"{ts}." + body`` alone made a single captured pair valid for all
    of them for the whole skew window — a read credential became a write one.
    """
    captured = _sign(ALPHA, ALPHA_KEY, b"", method="GET", path="/api/v1/whatsapp/health")
    assert client.get("/api/v1/whatsapp/health", headers=captured).status_code == 200

    # Same verb, different path.
    assert client.get("/api/v1/whatsapp/conversations", headers=captured).status_code == 401
    # Same (empty) body, different verb and path — the lifecycle write.
    assert (
        client.post("/api/v1/whatsapp/conversations/1/close", headers=captured).status_code
        == 401
    )


def test_the_idempotency_key_is_covered_by_the_signature(client, world):
    """It decides new-message vs duplicate, and it used to be unsigned.

    An attacker able to rewrite that one header on a signed send could make a
    fresh OTP collapse into an earlier message, or replay one send under a new
    key as a second charge-bearing message.
    """
    payload = {"intent": "login_otp", "to": "+237600000411", "variables": ["777111"]}
    body = json.dumps(payload).encode("utf-8")
    headers = _sign(
        ALPHA,
        ALPHA_KEY,
        body,
        method="POST",
        path="/api/v1/whatsapp/messages",
        idempotency_key="signed-key-1",
    )
    assert (
        client.post("/api/v1/whatsapp/messages", content=body, headers=headers).status_code
        == 202
    )

    tampered = dict(headers)
    tampered["X-QCP-Idempotency-Key"] = "swapped-key-1"
    assert (
        client.post("/api/v1/whatsapp/messages", content=body, headers=tampered).status_code
        == 401
    )

    stripped = dict(headers)
    stripped.pop("X-QCP-Idempotency-Key")
    assert (
        client.post("/api/v1/whatsapp/messages", content=body, headers=stripped).status_code
        == 401
    )


# ---------------------------------------------------------------------------
# A product cannot select the account
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "field",
    ["account_slug", "account_id", "purpose", "phone_number_id", "template", "waba_id"],
)
def test_account_selecting_fields_are_refused(client, world, field):
    """There is no request field through which a caller can name a number."""
    r = _post(
        client,
        "/whatsapp/messages",
        {"intent": "login_otp", "to": PHONE, "variables": ["123456"], field: "quata_verify"},
    )
    assert r.status_code == 422, r.text


def test_intent_alone_decides_the_number(client, world):
    """Same caller, two intents, two different numbers — chosen server-side."""
    otp = _post(
        client,
        "/whatsapp/messages",
        {"intent": "login_otp", "to": PHONE, "variables": ["123456"]},
    )
    promo = _post(
        client,
        "/whatsapp/messages",
        {"intent": "promo_drop", "to": PHONE, "variables": []},
    )
    assert otp.status_code == 202, otp.text
    assert promo.status_code == 202, promo.text

    db = SessionLocal()
    try:
        otp_row = (
            db.query(WhatsAppMessage)
            .filter(WhatsAppMessage.message_uid == otp.json()["message_uid"])
            .one()
        )
        promo_row = (
            db.query(WhatsAppMessage)
            .filter(WhatsAppMessage.message_uid == promo.json()["message_uid"])
            .one()
        )
        assert otp_row.account_id == world["verify_id"]
        assert otp_row.account_purpose == "authentication"
        assert promo_row.account_id == world["engage_id"]
        assert promo_row.account_purpose == "engagement"
    finally:
        db.close()


def test_marketing_can_never_leave_the_verify_number(client, world):
    """A rule pointing a marketing intent at the authentication purpose is
    refused, and nothing marketing-shaped is ever queued on Verify."""
    r = _post(client, "/whatsapp/messages", {"intent": "promo_via_verify", "to": PHONE})
    assert r.status_code == 202, r.text
    payload = r.json()
    assert payload["status"] == "suppressed"
    assert payload["reason"] == "template_not_approved"

    db = SessionLocal()
    try:
        leaked = (
            db.query(WhatsAppMessage)
            .filter(
                WhatsAppMessage.account_id == world["verify_id"],
                WhatsAppMessage.product_id == world["alpha_id"],
                WhatsAppMessage.intent == "promo_via_verify",
                WhatsAppMessage.status.notin_(["suppressed"]),
            )
            .all()
        )
        assert leaked == []
        # And the refusal is on the record, with no human actor.
        from app.models import WhatsAppAuditLog

        denial = (
            db.query(WhatsAppAuditLog)
            .filter(
                WhatsAppAuditLog.product_id == world["alpha_id"],
                WhatsAppAuditLog.outcome == "denied",
            )
            .order_by(WhatsAppAuditLog.id.desc())
            .first()
        )
        assert denial is not None
        assert denial.actor_id is None
        assert denial.reason == "template_not_approved"
    finally:
        db.close()


def test_free_form_on_the_verify_number_is_refused(client, world):
    """Even inside a live 24h window, Verify emits templates and nothing else."""
    thread_id = _thread_for(world, product_key="alpha_id", phone=PHONE, account_key="verify_id")
    r = _post(
        client,
        "/whatsapp/messages",
        {
            "intent": "login_otp",
            "to": PHONE,
            "kind": "text",
            "conversation_id": thread_id,
            "body": "hello there",
        },
    )
    assert r.status_code == 202, r.text
    assert r.json()["reason"] == "freeform_on_auth_account"


def test_category_endpoint_cannot_redirect_a_route(client, world):
    """Declaring the wrong category refuses the send; it never moves it."""
    r = _post(
        client,
        "/whatsapp/messages/authentication",
        {"intent": "order_dispatched", "to": PHONE, "variables": ["A-1"]},
    )
    assert r.status_code == 409, r.text
    assert r.json()["detail"] == "category_mismatch"


def test_category_endpoint_accepts_a_matching_route(client, world):
    r = _post(
        client,
        "/whatsapp/messages/utility",
        {"intent": "order_dispatched", "to": PHONE, "variables": ["A-2"]},
    )
    assert r.status_code == 202, r.text
    db = SessionLocal()
    try:
        row = (
            db.query(WhatsAppMessage)
            .filter(WhatsAppMessage.message_uid == r.json()["message_uid"])
            .one()
        )
        assert row.account_id == world["engage_id"]
    finally:
        db.close()


def test_health_never_names_an_account(client, world):
    r = _get(client, "/whatsapp/health")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["product"] == ALPHA
    assert set(body["purpose_available"]) == {"authentication", "engagement"}
    blob = json.dumps(body)
    for secret in ("quata_verify", "pnid_", "waba_", "+2376000099", "+2376000088"):
        assert secret not in blob


# ---------------------------------------------------------------------------
# Cross-product isolation
# ---------------------------------------------------------------------------

def test_cross_product_conversation_access_is_refused(client, world):
    """Beta holds valid credentials and still cannot touch Alpha's thread."""
    thread_id = _thread_for(world, product_key="alpha_id", phone=PHONE)

    # Alpha can.
    assert _get(client, f"/whatsapp/conversations/{thread_id}").status_code == 200

    # Beta cannot — on any verb, and with 404 rather than 403 so the reply
    # does not confirm the conversation exists.
    reads = [
        _get(client, f"/whatsapp/conversations/{thread_id}", slug=BETA, key=BETA_KEY),
        _get(client, f"/whatsapp/conversations/{thread_id}/messages", slug=BETA, key=BETA_KEY),
    ]
    writes = [
        _post(client, f"/whatsapp/conversations/{thread_id}/close", {}, slug=BETA, key=BETA_KEY),
        _post(client, f"/whatsapp/conversations/{thread_id}/open", {}, slug=BETA, key=BETA_KEY),
        _post(
            client,
            f"/whatsapp/conversations/{thread_id}/return-to-ai",
            {},
            slug=BETA,
            key=BETA_KEY,
        ),
        _post(
            client,
            f"/whatsapp/conversations/{thread_id}/assign",
            {"assignee_id": 1},
            slug=BETA,
            key=BETA_KEY,
        ),
    ]
    for r in reads + writes:
        assert r.status_code == 404, r.text
        assert r.json()["detail"] == "conversation_not_found"


def test_cross_product_listing_is_scoped(client, world):
    _thread_for(world, product_key="alpha_id", phone=PHONE)
    alpha = _get(client, "/whatsapp/conversations").json()
    beta = _get(client, "/whatsapp/conversations", slug=BETA, key=BETA_KEY).json()
    assert alpha
    assert all(c["id"] not in {b["id"] for b in beta} for c in alpha)


def test_cross_product_write_does_not_mutate(client, world):
    """A refused cross-product close leaves the thread exactly as it was."""
    thread_id = _thread_for(world, product_key="alpha_id", phone=PHONE)
    assert (
        _post(
            client, f"/whatsapp/conversations/{thread_id}/close", {}, slug=BETA, key=BETA_KEY
        ).status_code
        == 404
    )
    db = SessionLocal()
    try:
        assert db.get(WhatsAppConversation, thread_id).state == "open"
    finally:
        db.close()


def test_cross_product_message_lookup_is_refused(client, world):
    sent = _post(
        client,
        "/whatsapp/messages",
        {"intent": "order_dispatched", "to": PHONE, "variables": ["A-3"]},
    )
    uid = sent.json()["message_uid"]
    assert _get(client, f"/whatsapp/messages/{uid}").status_code == 200
    stolen = _get(client, f"/whatsapp/messages/{uid}", slug=BETA, key=BETA_KEY)
    assert stolen.status_code == 404


def test_unattributed_conversation_belongs_to_nobody(client, world):
    """An inbound-only thread (product_id NULL) is invisible to every product."""
    db = SessionLocal()
    try:
        row = WhatsAppConversation(
            account_id=world["engage_id"],
            product_id=None,
            wa_contact_id="237600000777",
            phone_e164="+237600000777",
            state="open",
        )
        db.add(row)
        db.commit()
        orphan_id = row.id
    finally:
        db.close()
    assert _get(client, f"/whatsapp/conversations/{orphan_id}").status_code == 404
    assert (
        _get(client, f"/whatsapp/conversations/{orphan_id}", slug=BETA, key=BETA_KEY).status_code
        == 404
    )


# ---------------------------------------------------------------------------
# Conversation engine
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def agents(world):
    """Two active internal users: one is a WhatsApp agent, one is not.

    The entitlement is what makes a user assignable. Without it ``assign``
    is an oracle: a machine credential learns which ``users.id`` values
    exist and are active by watching 400 flip to 200.
    """
    from app.services.whatsapp import conversations as conv

    db = SessionLocal()
    try:
        agent_role = Role(
            slug=f"gw_agent_{SUFFIX}", name="Gateway Agent", description="test"
        )
        plain_role = Role(
            slug=f"gw_plain_{SUFFIX}", name="Gateway Plain", description="test"
        )
        db.add_all([agent_role, plain_role])
        db.flush()
        db.add(
            RolePermission(
                role_id=agent_role.id,
                permission=sorted(conv.WHATSAPP_AGENT_PERMISSIONS)[0],
            )
        )
        users = {}
        for key, role in (("agent", agent_role), ("plain", plain_role)):
            user = User(
                email=f"gw_{key}_{SUFFIX}@example.test",
                password_hash="x" * 20,
                full_name=f"Gateway {key}",
                role_id=role.id,
                is_active=True,
            )
            db.add(user)
            users[key] = user
        db.flush()
        super_admin = (
            db.query(User)
            .join(Role, User.role_id == Role.id)
            .filter(Role.slug == "super_admin", User.is_active.is_(True))
            .first()
        )
        ids = {
            "agent_id": users["agent"].id,
            "plain_id": users["plain"].id,
            "super_admin_id": super_admin.id if super_admin else None,
            "role_ids": [agent_role.id, plain_role.id],
            "user_ids": [users["agent"].id, users["plain"].id],
        }
        db.commit()
    finally:
        db.close()

    yield ids

    db = SessionLocal()
    try:
        db.query(WhatsAppConversation).filter(
            WhatsAppConversation.assignee_id.in_(ids["user_ids"])
        ).update({WhatsAppConversation.assignee_id: None}, synchronize_session=False)
        db.query(User).filter(User.id.in_(ids["user_ids"])).delete(
            synchronize_session=False
        )
        db.query(RolePermission).filter(
            RolePermission.role_id.in_(ids["role_ids"])
        ).delete(synchronize_session=False)
        db.query(Role).filter(Role.id.in_(ids["role_ids"])).delete(
            synchronize_session=False
        )
        db.commit()
    finally:
        db.close()


def test_close_open_assign_and_return_to_ai(client, world, agents):
    thread_id = _thread_for(world, product_key="alpha_id", phone=OTHER_PHONE)
    agent_id = agents["agent_id"]

    closed = _post(client, f"/whatsapp/conversations/{thread_id}/close", {})
    assert closed.status_code == 200, closed.text
    assert closed.json()["state"] == "closed"
    assert closed.json()["unread_count"] == 0

    assigned = _post(
        client, f"/whatsapp/conversations/{thread_id}/assign", {"assignee_id": agent_id}
    )
    assert assigned.status_code == 200, assigned.text
    assert assigned.json()["assignee_id"] == agent_id
    # Assigning a closed thread reopens it — a customer waiting on a human
    # must not sit in a closed queue.
    assert assigned.json()["state"] == "open"

    back = _post(client, f"/whatsapp/conversations/{thread_id}/return-to-ai", {})
    assert back.status_code == 200, back.text
    assert back.json()["assignee_id"] is None
    assert back.json()["state"] == "open"

    db = SessionLocal()
    try:
        row = db.get(WhatsAppConversation, thread_id)
        # The AI seam stays NULL in v1.
        assert row.assigned_agent is None
    finally:
        db.close()


def test_assign_to_unknown_agent_is_refused(client, world):
    thread_id = _thread_for(world, product_key="alpha_id", phone=OTHER_PHONE)
    r = _post(
        client, f"/whatsapp/conversations/{thread_id}/assign", {"assignee_id": 999_999_999}
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "unknown_agent"


def test_assign_is_not_a_user_enumeration_oracle(client, world, agents):
    """A user that exists but is not a WhatsApp agent answers exactly like a
    user that does not exist.

    ``assign`` is reachable with a *machine* credential. If "no such user"
    and "not an agent" differ, any product can walk ``users.id`` and learn
    which internal accounts exist and are active in the cockpit — and then
    park customer conversations on them.
    """
    thread_id = _thread_for(world, product_key="alpha_id", phone=OTHER_PHONE)

    def _assign(assignee_id):
        return _post(
            client,
            f"/whatsapp/conversations/{thread_id}/assign",
            {"assignee_id": assignee_id},
        )

    missing = _assign(999_999_999)
    unentitled = _assign(agents["plain_id"])
    assert unentitled.status_code == missing.status_code == 400, unentitled.text
    assert unentitled.json()["detail"] == missing.json()["detail"] == "unknown_agent"

    # The refusal is total — nothing was parked on the unentitled user.
    db = SessionLocal()
    try:
        assert db.get(WhatsAppConversation, thread_id).assignee_id is None
    finally:
        db.close()

    # A super admin holds the "*" wildcard but is not a WhatsApp agent, and
    # a machine credential must not be able to park a customer on the boss.
    if agents["super_admin_id"] is not None:
        boss = _assign(agents["super_admin_id"])
        assert boss.status_code == 400, boss.text
        assert boss.json()["detail"] == "unknown_agent"

    # And the entitled agent still works.
    ok = _assign(agents["agent_id"])
    assert ok.status_code == 200, ok.text
    assert ok.json()["assignee_id"] == agents["agent_id"]


def test_history_is_scoped_to_the_thread(client, world):
    thread_id = _thread_for(world, product_key="alpha_id", phone=OTHER_PHONE)
    sent = _post(
        client,
        "/whatsapp/messages",
        {
            "intent": "order_dispatched",
            "to": OTHER_PHONE,
            "variables": ["A-4"],
            "conversation_id": thread_id,
        },
    )
    assert sent.status_code == 202, sent.text
    uid = sent.json()["message_uid"]

    history = _get(client, f"/whatsapp/conversations/{thread_id}/messages")
    assert history.status_code == 200, history.text
    body = history.json()
    assert body["conversation_id"] == thread_id
    assert [m["message_uid"] for m in body["messages"]] == [uid]

    stolen = _get(
        client, f"/whatsapp/conversations/{thread_id}/messages", slug=BETA, key=BETA_KEY
    )
    assert stolen.status_code == 404


def test_two_products_messaging_one_contact_do_not_share_history(client, world):
    """``(account_id, wa_contact_id)`` is unique, so both products would
    otherwise land in the same thread — and one would read the other's
    messages out of it.

    Beta writes first, so Beta's send fills in the blank owner and the thread
    row is Beta's for good (``conversations.adopt_if_unowned`` — ownership
    only ever moves NULL → product, so Alpha's later send cannot take it).
    Both products can *reach* the shared row, because each has a message in
    it and losing sight of a message you were already served is the
    retroactive loss this design forbids. Separation is enforced one level
    down, on the messages: ``history()`` filters on
    ``whatsapp_messages.product_id``, so neither product ever reads the
    other's message out of the row they share.
    """
    shared = "+237600000333"
    theirs = _post(
        client,
        "/whatsapp/messages",
        {"intent": "order_dispatched", "to": shared, "variables": ["B-9"]},
        slug=BETA,
        key=BETA_KEY,
    )
    mine = _post(
        client,
        "/whatsapp/messages",
        {"intent": "order_dispatched", "to": shared, "variables": ["A-9"]},
    )
    assert mine.status_code == 202, mine.text
    assert theirs.status_code == 202, theirs.text

    listing = _get(client, f"/whatsapp/conversations?phone={shared}").json()
    assert len(listing) == 1
    thread_id = listing[0]["id"]

    uids = {
        m["message_uid"]
        for m in _get(client, f"/whatsapp/conversations/{thread_id}/messages").json()[
            "messages"
        ]
    }
    assert mine.json()["message_uid"] in uids
    assert theirs.json()["message_uid"] not in uids

    # Beta keeps access to the shared row — it has a message in it, and a
    # send by Alpha must never retract a thread Beta was already served.
    beta_view = _get(
        client, f"/whatsapp/conversations/{thread_id}", slug=BETA, key=BETA_KEY
    )
    assert beta_view.status_code == 200, beta_view.text
    # Reaching the row is not reading the thread. Beta sees exactly its own
    # message and nothing of Alpha's — the message-level filter is what
    # actually separates two products sharing one contact.
    beta_uids = {
        m["message_uid"]
        for m in _get(
            client,
            f"/whatsapp/conversations/{thread_id}/messages",
            slug=BETA,
            key=BETA_KEY,
        ).json()["messages"]
    }
    assert beta_uids == {theirs.json()["message_uid"]}


def test_an_ambiguous_inbound_reply_belongs_to_nobody(client, world):
    """Two products addressed this contact, so a context-less reply is for
    *neither* of them until a human says otherwise.

    ``(account_id, wa_contact_id)`` is unique, so both products share one
    thread row. Every rule for splitting a bare reply between them is a
    guess a caller can rig: *first touch* is won by pre-claiming a guessable
    phone with one cheap utility send, *last touch* needs no race at all —
    one message, at will, repeatedly. Handing a customer's reply to the
    wrong company is worse than handing it to nobody, so an ambiguous
    inbound is attributed to nobody, stays out of both products' APIs, and
    is raised as a ``conversation.inbound_unattributed`` denial for an
    operator. (A customer who actually taps *reply* carries ``context.id``,
    which is unforgeable and is attributed — see
    ``test_a_reply_with_meta_context_reaches_only_the_product_that_sent_it``.)
    """
    shared = "+237600007777"
    alpha_send = _post(
        client,
        "/whatsapp/messages",
        {"intent": "order_dispatched", "to": shared, "variables": ["A-77"]},
    )
    beta_send = _post(
        client,
        "/whatsapp/messages",
        {"intent": "order_dispatched", "to": shared, "variables": ["B-77"]},
        slug=BETA,
        key=BETA_KEY,
    )
    assert alpha_send.status_code == 202, alpha_send.text
    assert beta_send.status_code == 202, beta_send.text

    db = SessionLocal()
    try:
        beta_row = (
            db.query(WhatsAppMessage)
            .filter(WhatsAppMessage.message_uid == beta_send.json()["message_uid"])
            .one()
        )
        # An accepted send by an enabled product is never orphaned.
        assert beta_row.conversation_id is not None
    finally:
        db.close()

    reply = _inbound(client, world, phone=shared, text="my BETA order is late")
    assert reply.status_code == 200, reply.text

    listing = _get(
        client, f"/whatsapp/conversations?phone={shared}", slug=BETA, key=BETA_KEY
    ).json()
    assert len(listing) == 1
    thread_id = listing[0]["id"]

    beta_history = _get(
        client, f"/whatsapp/conversations/{thread_id}/messages", slug=BETA, key=BETA_KEY
    )
    assert beta_history.status_code == 200, beta_history.text
    messages = beta_history.json()["messages"]
    # Beta spoke last. Under last-touch it would be handed the reply; it is
    # not, because "spoke last" is the property one message buys at will.
    assert [m["direction"] for m in messages].count("inbound") == 0
    assert beta_send.json()["message_uid"] in {m["message_uid"] for m in messages}
    # Beta reads its own outbound — and nothing of Alpha's.
    assert alpha_send.json()["message_uid"] not in {m["message_uid"] for m in messages}

    # Alpha, which spoke first, does not get it either.
    stolen = _get(client, f"/whatsapp/conversations/{thread_id}/messages")
    assert stolen.status_code == 200, stolen.text
    assert [m["direction"] for m in stolen.json()["messages"]].count("inbound") == 0
    assert beta_send.json()["message_uid"] not in {
        m["message_uid"] for m in stolen.json()["messages"]
    }

    # Nothing was destroyed: Alpha's own message is still its own.
    own = _get(client, f"/whatsapp/messages/{alpha_send.json()['message_uid']}")
    assert own.status_code == 200, own.text

    from app.models import WhatsAppAuditLog

    db = SessionLocal()
    try:
        # The reply is stored — dropped on the floor would be worse than
        # misattributed — with no product on it, and an operator is told.
        orphan = (
            db.query(WhatsAppMessage)
            .filter(
                WhatsAppMessage.conversation_id == thread_id,
                WhatsAppMessage.direction == "inbound",
            )
            .one()
        )
        assert orphan.product_id is None
        denial = (
            db.query(WhatsAppAuditLog)
            .filter(
                WhatsAppAuditLog.action == "conversation.inbound_unattributed",
                WhatsAppAuditLog.resource_id == str(thread_id),
            )
            .one()
        )
        assert denial.outcome == "denied"
        assert sorted(denial.details["candidate_product_ids"]) == sorted(
            [world["alpha_id"], world["beta_id"]]
        )
    finally:
        db.close()


def test_send_into_another_products_thread_is_refused(client, world):
    thread_id = _thread_for(world, product_key="alpha_id", phone=PHONE)
    r = _post(
        client,
        "/whatsapp/messages",
        {
            "intent": "order_dispatched",
            "to": PHONE,
            "variables": ["B-1"],
            "conversation_id": thread_id,
        },
        slug=BETA,
        key=BETA_KEY,
    )
    assert r.status_code == 404
    assert r.json()["detail"] == "conversation_not_found"


def test_free_form_outside_the_service_window_is_refused(client, world):
    db = SessionLocal()
    try:
        row = WhatsAppConversation(
            account_id=world["engage_id"],
            product_id=world["alpha_id"],
            wa_contact_id="237600000555",
            phone_e164="+237600000555",
            state="open",
            last_inbound_at=datetime.now(timezone.utc) - timedelta(hours=30),
            service_window_expires_at=datetime.now(timezone.utc) - timedelta(hours=6),
        )
        db.add(row)
        db.commit()
        stale_id = row.id
    finally:
        db.close()

    r = _post(
        client,
        "/whatsapp/messages",
        {
            "intent": "order_dispatched",
            "to": "+237600000555",
            "kind": "text",
            "conversation_id": stale_id,
            "body": "still there?",
        },
    )
    assert r.status_code == 409
    assert r.json()["detail"] == "outside_service_window"


def test_service_window_is_monotonic_and_clamped_to_now(client, world):
    """``when`` comes from Meta verbatim, and Meta redelivers out of order.

    Backwards: an out-of-order redelivery of an older message must not drag
    the window back and start refusing 409 on a thread that is genuinely
    open. Forwards: a skewed timestamp must not open the free-form gate past
    the real 24h — a free-form send outside Meta's own window is refused
    *and* charged against the number's quality rating, which is exactly what
    the gateway guard exists to avoid.
    """
    from app.services.whatsapp import conversations as conv

    now = datetime.now(timezone.utc)
    db = SessionLocal()
    try:
        row = WhatsAppConversation(
            account_id=world["engage_id"],
            product_id=world["alpha_id"],
            wa_contact_id=f"237600000666{SUFFIX}",
            phone_e164="+237600000666",
            state="open",
        )
        db.add(row)
        db.commit()

        conv.touch_inbound(db, row, at=now - timedelta(hours=1))
        db.commit()
        first_window = conv._as_aware(row.service_window_expires_at)
        first_inbound = conv._as_aware(row.last_inbound_at)
        assert first_window is not None

        # Meta redelivers an *older* message out of sequence.
        conv.touch_inbound(db, row, at=now - timedelta(hours=10))
        db.commit()
        assert conv._as_aware(row.service_window_expires_at) == first_window
        assert conv._as_aware(row.last_inbound_at) == first_inbound
        assert conv.service_window_open(row) is True

        # A timestamp far in the future must not buy free-form time we do
        # not have.
        conv.touch_inbound(db, row, at=now + timedelta(days=400))
        db.commit()
        ceiling = datetime.now(timezone.utc) + conv.SERVICE_WINDOW + timedelta(minutes=1)
        assert conv._as_aware(row.service_window_expires_at) <= ceiling
        assert conv._as_aware(row.last_inbound_at) <= datetime.now(timezone.utc)
    finally:
        db.close()


def test_free_form_without_a_thread_is_refused(client, world):
    r = _post(
        client,
        "/whatsapp/messages",
        {"intent": "order_dispatched", "to": PHONE, "kind": "text", "body": "hi"},
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "conversation_required"


# ---------------------------------------------------------------------------
# Idempotency + variable arity
# ---------------------------------------------------------------------------

def test_repeat_idempotency_key_is_a_duplicate_not_a_second_send(client, world):
    key = f"otp-{uuid.uuid4().hex}"
    payload = {"intent": "login_otp", "to": PHONE, "variables": ["424242"]}
    first = _post(client, "/whatsapp/messages", payload, idempotency_key=key)
    second = _post(client, "/whatsapp/messages", payload, idempotency_key=key)

    assert first.status_code == 202, first.text
    assert first.json()["duplicate"] is False
    assert second.status_code == 200, second.text
    assert second.json()["duplicate"] is True
    assert second.json()["message_uid"] == first.json()["message_uid"]


def test_variable_arity_mismatch_is_suppressed(client, world):
    r = _post(
        client,
        "/whatsapp/messages",
        {"intent": "login_otp", "to": PHONE, "variables": ["1", "2", "3"]},
    )
    assert r.status_code == 202, r.text
    assert r.json()["reason"] == "variable_arity_mismatch"


def test_the_otp_is_never_stored_in_clear(client, world):
    code = "998877"
    r = _post(
        client, "/whatsapp/messages", {"intent": "login_otp", "to": PHONE, "variables": [code]}
    )
    assert r.status_code == 202, r.text
    db = SessionLocal()
    try:
        row = (
            db.query(WhatsAppMessage)
            .filter(WhatsAppMessage.message_uid == r.json()["message_uid"])
            .one()
        )
        assert code not in json.dumps(row.variables or {})
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Dormancy
# ---------------------------------------------------------------------------

def test_env_kill_switch_beats_the_db_toggle(client, world):
    """`WHATSAPP_ENABLED=false` silences QCP even with every DB row set live."""
    env_settings.WHATSAPP_ENABLED = False
    try:
        r = _post(
            client,
            "/whatsapp/messages",
            {"intent": "login_otp", "to": PHONE, "variables": ["111111"]},
        )
        assert r.status_code == 202, r.text
        assert r.json()["status"] == "suppressed"
        assert r.json()["reason"] == "delivery_disabled"
    finally:
        env_settings.WHATSAPP_ENABLED = True


def test_a_malformed_timestamp_is_a_401_not_a_500(client, world):
    """``abs(time.time() - sent_at)`` converts the int to a float.

    ``int("9" * 400)`` parses fine and then overflows that conversion, so a
    header the caller controls raised OverflowError out of the dependency —
    a 500 on a parse, and an unhandled-error alert per attempt.
    """
    body = json.dumps({"intent": "login_otp", "to": PHONE, "variables": ["123456"]}).encode()
    headers = _sign(ALPHA, ALPHA_KEY, body, method="POST", path="/api/v1/whatsapp/messages")
    headers["X-QCP-Timestamp"] = "9" * 400
    r = client.post("/api/v1/whatsapp/messages", content=body, headers=headers)
    assert r.status_code == 401, r.text
    assert r.json()["detail"] == "Invalid signature timestamp"


# ---------------------------------------------------------------------------
# Rate limiting — authentication sends have their own budget
# ---------------------------------------------------------------------------
#
# QuataFood login OTP, payment-PIN reset and phone-change verification have no
# email fallback, so an OTP send that 429s is a lockout, not a slowdown. The
# tests below are about *who can spend whose budget*, which is why they run
# through a client whose socket peer is a trusted proxy: that is the shape
# production runs in, and the only shape in which callers are distinguishable
# at all.

@pytest.fixture
def proxied(app_instance):
    """A client behind a trusted hop, so ``X-Forwarded-For`` is honoured.

    ``10.0.0.9`` is inside the default ``TRUSTED_PROXIES``, so each request's
    ``X-Forwarded-For`` names the caller — exactly what nginx supplies in
    production. Without this, every caller shares one socket address.
    """
    from fastapi.testclient import TestClient

    with TestClient(app_instance, client=("10.0.0.9", 44444)) as c:
        yield c


def _via(client, method, path, *, xff, slug=ALPHA, key=ALPHA_KEY, payload=None):
    body = json.dumps(payload).encode("utf-8") if payload is not None else b""
    full = f"/api/v1{path}"
    headers = _sign(slug, key, body, method=method, path=full)
    headers["X-Forwarded-For"] = xff
    if method == "GET":
        return client.get(full, headers=headers)
    return client.post(full, content=body, headers=headers)


def _otp(code: str) -> dict:
    """A distinct OTP send. Identical sends dedupe into one message, and a
    duplicate answers 200 — which would hide whether the limiter let it
    through."""
    return {"intent": "login_otp", "to": PHONE, "variables": [code]}


def test_ordinary_traffic_cannot_exhaust_the_otp_budget(proxied, world, monkeypatch):
    """All twelve routes shared one bucket, so a product's own status polling
    could spend the budget its login OTP needs."""
    from app.api import routes_whatsapp

    monkeypatch.setattr(routes_whatsapp, "QCP_RATE_LIMIT", "3/minute")
    ip = "198.51.100.11"

    polls = [_via(proxied, "GET", "/whatsapp/health", xff=ip).status_code for _ in range(4)]
    assert polls == [200, 200, 200, 429], polls

    otp = _via(
        proxied,
        "POST",
        "/whatsapp/messages/authentication",
        xff=ip,
        payload=_otp("610001"),
    )
    assert otp.status_code == 202, otp.text


def test_naming_a_product_does_not_spend_its_otp_budget(proxied, world, monkeypatch):
    """``X-QCP-Product`` is unauthenticated at the limiter, so a stranger that
    merely *names* quatafood must not be able to burn quatafood's OTP budget."""
    from app.api import routes_whatsapp

    monkeypatch.setattr(routes_whatsapp, "QCP_RATE_LIMIT", "3/minute")
    stranger_ip, real_ip = "203.0.113.7", "198.51.100.12"

    stranger = [
        _via(
            proxied,
            "POST",
            "/whatsapp/messages/authentication",
            xff=stranger_ip,
            key="not-the-key",
            payload=_otp("610002"),
        ).status_code
        for _ in range(5)
    ]
    assert stranger[:3] == [401, 401, 401], stranger
    assert stranger[3:] == [429, 429], stranger

    otp = _via(
        proxied,
        "POST",
        "/whatsapp/messages/authentication",
        xff=real_ip,
        payload=_otp("610003"),
    )
    assert otp.status_code == 202, otp.text


def test_otp_route_still_limits_guesses_before_the_database(proxied, world, monkeypatch):
    """The property the dedicated budget must not cost: the limiter runs before
    the product SELECT and the ``last_seen_at`` commit, so guessing stays cheap
    on the authentication route too."""
    from app.api import routes_whatsapp

    monkeypatch.setattr(routes_whatsapp, "QCP_RATE_LIMIT", "3/minute")
    slug = f"pytest-otp-{uuid.uuid4().hex[:10]}"
    codes = [
        _via(
            proxied,
            "POST",
            "/whatsapp/messages/authentication",
            xff="203.0.113.8",
            slug=slug,
            key="not-a-real-key",
            payload=_otp("610004"),
        ).status_code
        for _ in range(5)
    ]
    assert codes[:3] == [401, 401, 401], codes
    assert codes[3:] == [429, 429], codes


def test_a_disabled_product_cannot_read_conversations(client, world):
    db = SessionLocal()
    try:
        product = db.get(WhatsAppProduct, world["beta_id"])
        product.is_enabled = False
        db.commit()
    finally:
        db.close()
    try:
        r = _get(client, "/whatsapp/conversations", slug=BETA, key=BETA_KEY)
        assert r.status_code == 403
        assert r.json()["detail"] == "product_disabled"
    finally:
        db = SessionLocal()
        try:
            product = db.get(WhatsAppProduct, world["beta_id"])
            product.is_enabled = True
            db.commit()
        finally:
            db.close()


# ---------------------------------------------------------------------------
# Adversarial: thread ownership on the shared engagement number
#
# Every test below is written from the attacker's side. Alpha is the product
# genuinely working a customer; Beta is an enabled peer on the same number
# that wants that customer's replies, or wants Alpha to lose them. Beta holds
# nothing but its own valid credentials and the customer's phone number —
# which is not a secret, it is a phone number.
# ---------------------------------------------------------------------------

def _stamp_wamid(message_uid: str) -> str:
    """Give an accepted outbound row the wamid Meta would have returned.

    Delivery is stubbed for this module, so nothing ever calls the Graph API
    and no row gets a ``provider_message_id`` on its own. A real send gets
    one, and it is what a customer's *reply* points ``context.id`` at.
    """
    wamid = f"wamid.OUT{uuid.uuid4().hex.upper()}"
    db = SessionLocal()
    try:
        row = (
            db.query(WhatsAppMessage)
            .filter(WhatsAppMessage.message_uid == message_uid)
            .one()
        )
        row.provider_message_id = wamid
        db.commit()
    finally:
        db.close()
    return wamid


def _inbound_uids(client, thread_id, *, slug, key):
    body = _get(
        client, f"/whatsapp/conversations/{thread_id}/messages", slug=slug, key=key
    )
    assert body.status_code == 200, body.text
    return [m["message_uid"] for m in body.json()["messages"] if m["direction"] == "inbound"]


def _thread_id_for_phone(client, phone, *, slug=ALPHA, key=ALPHA_KEY):
    listing = _get(client, f"/whatsapp/conversations?phone={phone}", slug=slug, key=key)
    assert listing.status_code == 200, listing.text
    rows = listing.json()
    assert len(rows) == 1, rows
    return rows[0]["id"]


def test_a_reply_with_meta_context_reaches_only_the_product_that_sent_it(client, world):
    """The customer taps *reply* on Alpha's bubble. Beta must not read it.

    Beta has sent to this contact too — and sent *last*, which is the
    property last-touch attribution handed the thread to. Meta's own
    ``context.id`` says otherwise, and it is the one signal Beta cannot
    manufacture: a wamid exists only because Meta handed it back for a send
    we made, on this thread.
    """
    shared = "+237600009101"
    alpha_send = _post(
        client,
        "/whatsapp/messages",
        {"intent": "order_dispatched", "to": shared, "variables": ["A-101"]},
    )
    assert alpha_send.status_code == 202, alpha_send.text
    alpha_wamid = _stamp_wamid(alpha_send.json()["message_uid"])

    beta_send = _post(
        client,
        "/whatsapp/messages",
        {"intent": "order_dispatched", "to": shared, "variables": ["B-101"]},
        slug=BETA,
        key=BETA_KEY,
    )
    assert beta_send.status_code == 202, beta_send.text

    reply = _inbound(
        client, world, phone=shared, text="where is A-101?", context_wamid=alpha_wamid
    )
    assert reply.status_code == 200, reply.text

    thread_id = _thread_id_for_phone(client, shared)
    assert len(_inbound_uids(client, thread_id, slug=ALPHA, key=ALPHA_KEY)) == 1
    assert _inbound_uids(client, thread_id, slug=BETA, key=BETA_KEY) == []


def test_a_forged_context_id_wins_nothing(client, world):
    """Beta cannot invent a wamid to claim Alpha's reply.

    The attacker's best guess at ``context.id`` is a well-formed wamid it
    made up. It resolves to no outbound row, so attribution falls through to
    the no-context rules — where two addressees means nobody, not Beta.
    """
    shared = "+237600009102"
    for slug, key, var in ((ALPHA, ALPHA_KEY, "A-102"), (BETA, BETA_KEY, "B-102")):
        r = _post(
            client,
            "/whatsapp/messages",
            {"intent": "order_dispatched", "to": shared, "variables": [var]},
            slug=slug,
            key=key,
        )
        assert r.status_code == 202, r.text

    reply = _inbound(
        client,
        world,
        phone=shared,
        text="hello",
        context_wamid=f"wamid.FORGED{uuid.uuid4().hex.upper()}",
    )
    assert reply.status_code == 200, reply.text

    thread_id = _thread_id_for_phone(client, shared)
    assert _inbound_uids(client, thread_id, slug=ALPHA, key=ALPHA_KEY) == []
    assert _inbound_uids(client, thread_id, slug=BETA, key=BETA_KEY) == []


def test_a_context_id_from_another_thread_is_not_honoured(client, world):
    """A real wamid, replayed onto a thread it does not belong to.

    Beta owns a legitimate wamid — its own send to *another* customer. If
    ``context.id`` were resolved globally, Beta could take any reply on any
    thread by getting that id into the envelope. It is resolved against
    *this* conversation only, so the replay buys nothing and the reply falls
    through to the ambiguity rule.
    """
    beta_own = "+237600009103"
    theirs = _post(
        client,
        "/whatsapp/messages",
        {"intent": "order_dispatched", "to": beta_own, "variables": ["B-103"]},
        slug=BETA,
        key=BETA_KEY,
    )
    assert theirs.status_code == 202, theirs.text
    foreign_wamid = _stamp_wamid(theirs.json()["message_uid"])

    shared = "+237600009104"
    for slug, key, var in ((ALPHA, ALPHA_KEY, "A-104"), (BETA, BETA_KEY, "B-104")):
        r = _post(
            client,
            "/whatsapp/messages",
            {"intent": "order_dispatched", "to": shared, "variables": [var]},
            slug=slug,
            key=key,
        )
        assert r.status_code == 202, r.text

    reply = _inbound(
        client, world, phone=shared, text="hello", context_wamid=foreign_wamid
    )
    assert reply.status_code == 200, reply.text

    thread_id = _thread_id_for_phone(client, shared)
    assert _inbound_uids(client, thread_id, slug=ALPHA, key=ALPHA_KEY) == []
    assert _inbound_uids(client, thread_id, slug=BETA, key=BETA_KEY) == []


def test_a_cheap_send_cannot_take_a_thread_however_often_it_is_repeated(client, world):
    """Last-touch was one message, at will, repeatedly. Try it ten times.

    ``product_id`` only ever moves NULL → product, so Alpha's ownership must
    survive any number of Beta sends, and each one must be individually
    unable to move it — not merely the last one.
    """
    shared = "+237600009105"
    mine = _post(
        client,
        "/whatsapp/messages",
        {"intent": "order_dispatched", "to": shared, "variables": ["A-105"]},
    )
    assert mine.status_code == 202, mine.text
    thread_id = _thread_id_for_phone(client, shared)

    def _owner():
        db = SessionLocal()
        try:
            return db.get(WhatsAppConversation, thread_id).product_id
        finally:
            db.close()

    assert _owner() == world["alpha_id"]
    for n in range(10):
        r = _post(
            client,
            "/whatsapp/messages",
            {"intent": "order_dispatched", "to": shared, "variables": [f"B-105-{n}"]},
            slug=BETA,
            key=BETA_KEY,
        )
        assert r.status_code == 202, r.text
        assert _owner() == world["alpha_id"], f"Beta took the thread on send {n}"

    # And a context-less reply still does not fall to the last speaker.
    assert _inbound(client, world, phone=shared, text="?").status_code == 200
    assert _inbound_uids(client, thread_id, slug=BETA, key=BETA_KEY) == []


def test_beta_cannot_retract_a_reply_alpha_has_already_been_given(client, world):
    """The retroactive-loss attack: let Alpha earn the reply, then take it.

    Alpha alone addresses the contact, so the reply is Alpha's
    (``sole_addressee``). Beta then sends — under last-touch that flipped
    ``product_id`` and Alpha 404'd on a thread it had already been served.
    Alpha must still read that inbound afterwards, and the message's own
    ``product_id`` must not have been rewritten.
    """
    shared = "+237600009106"
    mine = _post(
        client,
        "/whatsapp/messages",
        {"intent": "order_dispatched", "to": shared, "variables": ["A-106"]},
    )
    assert mine.status_code == 202, mine.text
    assert _inbound(client, world, phone=shared, text="yes thanks").status_code == 200

    thread_id = _thread_id_for_phone(client, shared)
    before = _inbound_uids(client, thread_id, slug=ALPHA, key=ALPHA_KEY)
    assert len(before) == 1

    for n in range(3):
        r = _post(
            client,
            "/whatsapp/messages",
            {"intent": "order_dispatched", "to": shared, "variables": [f"B-106-{n}"]},
            slug=BETA,
            key=BETA_KEY,
        )
        assert r.status_code == 202, r.text

    assert _get(client, f"/whatsapp/conversations/{thread_id}").status_code == 200
    assert _inbound_uids(client, thread_id, slug=ALPHA, key=ALPHA_KEY) == before
    assert _inbound_uids(client, thread_id, slug=BETA, key=BETA_KEY) == []
    assert _thread_id_for_phone(client, shared) == thread_id


def test_a_stranger_product_cannot_mutate_the_thread_it_shares(client, world):
    """Reaching a shared row is not authority over it.

    ``for_product`` was widened to *read* access on prior participation so a
    product cannot lose sight of a message it was already given. The state
    verbs are a different question: they are the owner's. Beta buys
    participation with one cheap utility send to a phone number it can
    guess — if that also bought ``close``/``assign``/``return-to-ai``, an
    attacker could shut Alpha's live customer thread, zero its unread badge,
    or kick Alpha's human agent off it, all with no ownership at all.
    """
    shared = "+237600009107"
    assert (
        _post(
            client,
            "/whatsapp/messages",
            {"intent": "order_dispatched", "to": shared, "variables": ["A-107"]},
        ).status_code
        == 202
    )
    assert _inbound(client, world, phone=shared, text="hi").status_code == 200
    thread_id = _thread_id_for_phone(client, shared)

    db = SessionLocal()
    try:
        row = db.get(WhatsAppConversation, thread_id)
        row.assignee_id = None
        row.state = "open"
        db.commit()
    finally:
        db.close()

    # One cheap message buys Beta a foothold in the row...
    assert (
        _post(
            client,
            "/whatsapp/messages",
            {"intent": "order_dispatched", "to": shared, "variables": ["B-107"]},
            slug=BETA,
            key=BETA_KEY,
        ).status_code
        == 202
    )
    assert _get(client, f"/whatsapp/conversations/{thread_id}", slug=BETA, key=BETA_KEY).status_code == 200

    # ...and nothing else.
    for verb in ("close", "open", "return-to-ai"):
        r = _post(
            client,
            f"/whatsapp/conversations/{thread_id}/{verb}",
            {},
            slug=BETA,
            key=BETA_KEY,
        )
        assert r.status_code == 404, f"{verb}: {r.status_code} {r.text}"
        assert r.json()["detail"] == "conversation_not_found"

    assigned = _post(
        client,
        f"/whatsapp/conversations/{thread_id}/assign",
        {"assignee_id": 1},
        slug=BETA,
        key=BETA_KEY,
    )
    assert assigned.status_code == 404, assigned.text

    db = SessionLocal()
    try:
        row = db.get(WhatsAppConversation, thread_id)
        assert row.state == "open"
        assert row.assignee_id is None
        assert row.unread_count >= 1
    finally:
        db.close()

    # The owner is unaffected: Alpha can still work its own thread.
    assert _post(client, f"/whatsapp/conversations/{thread_id}/close", {}).status_code == 200


def test_the_admin_console_still_sees_the_whole_ambiguous_thread(
    client, world, admin_headers
):
    """Nobody's message is not nobody's problem.

    An ambiguous inbound is deliberately invisible to both products. If it
    were also invisible to the console it would simply be lost, and the
    design would be a silent drop dressed up as a security property.
    """
    shared = "+237600009108"
    sends = {}
    for slug, key, var in ((ALPHA, ALPHA_KEY, "A-108"), (BETA, BETA_KEY, "B-108")):
        r = _post(
            client,
            "/whatsapp/messages",
            {"intent": "order_dispatched", "to": shared, "variables": [var]},
            slug=slug,
            key=key,
        )
        assert r.status_code == 202, r.text
        sends[slug] = r.json()["message_uid"]

    assert _inbound(client, world, phone=shared, text="nobody owns me").status_code == 200
    thread_id = _thread_id_for_phone(client, shared)

    view = client.get(
        f"/api/v1/admin/qcp/conversations/{thread_id}", headers=admin_headers
    )
    assert view.status_code == 200, view.text
    body = view.json()
    uids = {m["message_uid"] for m in body["messages"]}
    assert set(sends.values()) <= uids
    bodies = [m["body"] for m in body["messages"] if m["direction"] == "inbound"]
    assert bodies == ["nobody owns me"]


def test_a_normal_support_conversation_still_works_end_to_end(client, world):
    """The case that must not be broken by any of the above.

    One product, one customer, no contention: QuataFood messages a customer,
    the customer replies (no ``context`` — most people just type), the
    product reads the reply and answers inside the service window. If this
    fails, the platform delivers nothing and leaks nothing, which is not a
    fix.
    """
    customer = "+237600009109"
    first = _post(
        client,
        "/whatsapp/messages",
        {"intent": "order_dispatched", "to": customer, "variables": ["A-109"]},
    )
    assert first.status_code == 202, first.text

    assert (
        _inbound(client, world, phone=customer, text="it never arrived").status_code
        == 200
    )

    thread_id = _thread_id_for_phone(client, customer)
    detail = _get(client, f"/whatsapp/conversations/{thread_id}")
    assert detail.status_code == 200, detail.text
    assert detail.json()["service_window_open"] is True
    assert detail.json()["unread_count"] == 1

    history = _get(client, f"/whatsapp/conversations/{thread_id}/messages").json()
    inbound = [m for m in history["messages"] if m["direction"] == "inbound"]
    assert len(inbound) == 1
    # ``MessageOut`` deliberately carries no body — the product-facing API
    # never echoes message text back. Check the stored row instead, so this
    # asserts the customer's actual words reached the right thread.
    db = SessionLocal()
    try:
        row = (
            db.query(WhatsAppMessage)
            .filter(WhatsAppMessage.message_uid == inbound[0]["message_uid"])
            .one()
        )
        assert row.body == "it never arrived"
        assert row.product_id == world["alpha_id"]
    finally:
        db.close()

    # The open service window is what a free-form reply needs.
    answer = _post(
        client,
        "/whatsapp/messages",
        {
            "intent": "order_dispatched",
            "kind": "text",
            "body": "So sorry — a new one is on its way.",
            "to": customer,
            "conversation_id": thread_id,
        },
    )
    assert answer.status_code == 202, answer.text

    final = _get(client, f"/whatsapp/conversations/{thread_id}/messages").json()
    assert answer.json()["message_uid"] in {m["message_uid"] for m in final["messages"]}


def test_a_reply_to_a_stale_single_product_thread_still_lands(client, world):
    """The service window closing must not orphan the reply.

    Only one product has ever spoken on this thread, but its send is three
    days old, so the in-window candidate set is empty. ``sole_participant``
    is what keeps "customer replies to an old order update" working; without
    it every quiet single-product thread would start dead-lettering real
    customer messages into the console.
    """
    customer = "+237600009110"
    sent = _post(
        client,
        "/whatsapp/messages",
        {"intent": "order_dispatched", "to": customer, "variables": ["A-110"]},
    )
    assert sent.status_code == 202, sent.text
    thread_id = _thread_id_for_phone(client, customer)

    db = SessionLocal()
    try:
        row = (
            db.query(WhatsAppMessage)
            .filter(WhatsAppMessage.message_uid == sent.json()["message_uid"])
            .one()
        )
        row.created_at = datetime.now(timezone.utc) - timedelta(days=3)
        db.commit()
    finally:
        db.close()

    assert _inbound(client, world, phone=customer, text="still waiting").status_code == 200
    assert len(_inbound_uids(client, thread_id, slug=ALPHA, key=ALPHA_KEY)) == 1


def test_a_stranger_product_cannot_ride_the_owners_service_window(client, world):
    """Free-form prose is the strongest thing a product can send.

    It carries no approved template, so its text is whatever the caller
    typed, and it is only possible while the 24h window is open. Alpha's
    customer opened that window by replying to *Alpha*. Beta buys
    participation in the shared row with one cheap utility send — if that
    also let it name the thread on a free-form send, it could put arbitrary
    text on that customer's phone, from the QUATA number, off the back of a
    conversation it has no part in.
    """
    customer = "+237600009111"
    assert (
        _post(
            client,
            "/whatsapp/messages",
            {"intent": "order_dispatched", "to": customer, "variables": ["A-111"]},
        ).status_code
        == 202
    )
    assert _inbound(client, world, phone=customer, text="what now?").status_code == 200
    thread_id = _thread_id_for_phone(client, customer)
    assert _get(client, f"/whatsapp/conversations/{thread_id}").json()[
        "service_window_open"
    ] is True

    assert (
        _post(
            client,
            "/whatsapp/messages",
            {"intent": "order_dispatched", "to": customer, "variables": ["B-111"]},
            slug=BETA,
            key=BETA_KEY,
        ).status_code
        == 202
    )

    intruded = _post(
        client,
        "/whatsapp/messages",
        {
            "intent": "order_dispatched",
            "kind": "text",
            "body": "Hi, this is not the company you were talking to.",
            "to": customer,
            "conversation_id": thread_id,
        },
        slug=BETA,
        key=BETA_KEY,
    )
    assert intruded.status_code == 404, intruded.text
    assert intruded.json()["detail"] == "conversation_not_found"

    db = SessionLocal()
    try:
        assert (
            db.query(WhatsAppMessage)
            .filter(
                WhatsAppMessage.conversation_id == thread_id,
                WhatsAppMessage.direction == "outbound",
                WhatsAppMessage.kind == "text",
            )
            .count()
            == 0
        ), "free-form prose was queued into a thread the sender does not own"
    finally:
        db.close()

    # The owner's own free-form reply is unaffected.
    assert (
        _post(
            client,
            "/whatsapp/messages",
            {
                "intent": "order_dispatched",
                "kind": "text",
                "body": "Checking now, one moment.",
                "to": customer,
                "conversation_id": thread_id,
            },
        ).status_code
        == 202
    )


def test_a_stranger_product_does_not_read_the_owners_agent_off_the_shared_row(
    client, world, agents
):
    """``conversations.assign`` refuses every bad assignee with one answer so
    a machine credential cannot walk ``users.id`` and learn which internal
    accounts exist, are active, and answer WhatsApp.

    A shared conversation row carries ``assignee_id`` — a user id that is by
    construction all three. Handing it to a product that merely participates
    in the row gives away for free exactly what that oracle-hardening exists
    to withhold, so the cross-product fields are blanked for a non-owner.
    """
    shared = "+237600009112"
    assert (
        _post(
            client,
            "/whatsapp/messages",
            {"intent": "order_dispatched", "to": shared, "variables": ["A-112"]},
        ).status_code
        == 202
    )
    thread_id = _thread_id_for_phone(client, shared)
    assert (
        _post(
            client,
            f"/whatsapp/conversations/{thread_id}/assign",
            {"assignee_id": agents["agent_id"]},
        ).status_code
        == 200
    )
    assert _inbound(client, world, phone=shared, text="anyone there?").status_code == 200

    assert (
        _post(
            client,
            "/whatsapp/messages",
            {"intent": "order_dispatched", "to": shared, "variables": ["B-112"]},
            slug=BETA,
            key=BETA_KEY,
        ).status_code
        == 202
    )

    theirs = _get(
        client, f"/whatsapp/conversations/{thread_id}", slug=BETA, key=BETA_KEY
    )
    assert theirs.status_code == 200, theirs.text
    assert theirs.json()["assignee_id"] is None
    # Nor how busy the owner's customer is with the owner.
    assert theirs.json()["unread_count"] == 0

    # The owner reads its own row in full.
    mine = _get(client, f"/whatsapp/conversations/{thread_id}").json()
    assert mine["assignee_id"] == agents["agent_id"]
    assert mine["unread_count"] == 1

    # Same rule through the listing, which returns the same shape.
    listed = [
        c
        for c in _get(
            client, f"/whatsapp/conversations?phone={shared}", slug=BETA, key=BETA_KEY
        ).json()
        if c["id"] == thread_id
    ]
    assert len(listed) == 1
    assert listed[0]["assignee_id"] is None


def test_a_second_products_otp_is_not_blocked_by_the_first_ones_thread(client, world):
    """The property nothing above may cost: an OTP always goes out.

    All four products send their security codes through the *same* Quata
    Verify number, so ``(account_id, wa_contact_id)`` puts them on one
    conversation row per customer, owned by whichever product got there
    first. QuataFood login, payment-PIN reset and phone-change verification
    have no email fallback — a send refused, deferred or dropped because a
    peer owns the row is a user locked out of their account. Ownership
    governs who may *name* a thread and who may change it; it must never
    gate a template send by phone number, which is what every OTP is.
    """
    db = SessionLocal()
    try:
        rule = WhatsAppRoutingRule(
            product_id=world["beta_id"],
            intent="login_otp",
            purpose="authentication",
            template_intent="login_otp",
            locale=None,
            is_active=True,
            conditions={},
        )
        db.add(rule)
        db.commit()
        rule_id = rule.id
    finally:
        db.close()

    try:
        customer = "+237600009113"
        first = _post(
            client,
            "/whatsapp/messages/authentication",
            {"intent": "login_otp", "to": customer, "variables": ["111222"]},
        )
        assert first.status_code == 202, first.text
        assert first.json()["status"] != "suppressed", first.text

        second = _post(
            client,
            "/whatsapp/messages/authentication",
            {"intent": "login_otp", "to": customer, "variables": ["333444"]},
            slug=BETA,
            key=BETA_KEY,
        )
        assert second.status_code == 202, second.text
        assert second.json()["status"] != "suppressed", second.text

        db = SessionLocal()
        try:
            rows = {
                r.message_uid: r
                for r in db.query(WhatsAppMessage).filter(
                    WhatsAppMessage.message_uid.in_(
                        [first.json()["message_uid"], second.json()["message_uid"]]
                    )
                )
            }
            assert len(rows) == 2
            for r in rows.values():
                # Both on the Verify number, both threaded, neither orphaned.
                assert r.account_id == world["verify_id"]
                assert r.conversation_id is not None
            thread_ids = {r.conversation_id for r in rows.values()}
            assert len(thread_ids) == 1, "the Verify thread is shared, as designed"
            thread = db.get(WhatsAppConversation, thread_ids.pop())
            # Alpha sent first and keeps the row; Beta's OTP went anyway.
            assert thread.product_id == world["alpha_id"]
            assert (
                rows[second.json()["message_uid"]].product_id == world["beta_id"]
            )
        finally:
            db.close()
    finally:
        db = SessionLocal()
        try:
            db.query(WhatsAppRoutingRule).filter(
                WhatsAppRoutingRule.id == rule_id
            ).delete(synchronize_session=False)
            db.commit()
        finally:
            db.close()
