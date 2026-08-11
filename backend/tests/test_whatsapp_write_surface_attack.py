"""Adversarial pass over the QCP **write** surface.

``test_whatsapp_admin_write.py`` and ``test_whatsapp_templates.py`` assert
that each route does what it says. This file assumes the opposite and goes
looking: it attacks the write surface the way someone would who wanted a
credential out of it, wanted a non-authentication template onto the Quata
Verify number, or wanted QCP switched on without deciding to switch it on.

Four properties are under attack here, and each one is checked on the paths
the happy-path tests do not walk — the **error** paths.

**1. No endpoint returns a secret, including when it refuses.** A 200 that
carries no token is worth little if the 422 next to it hands the token back.
That is not a hypothetical: FastAPI's default validation-error body echoes the
rejected ``input``, so pasting a token that is one character too long returned
the whole token in the response — and into every access log, browser history
and error tracker between here and the operator. ``app.main`` now redacts the
echo for QCP paths; ``test_a_rejected_credential_is_never_echoed_back`` is the
pin.

**2. The two-number separation cannot be re-opened by a write.** Attempted by
create, by edit, by sync, by routing rule, and by trying to move the account
purpose out from under a template that depends on it.

**3. Privilege.** Every write route is checked against a real logged-in user
who lacks ``settings:manage``, not merely against an anonymous caller.

**4. Dormancy survives the whole attack.** The last test re-reads the estate
after every route above has been exercised and requires it to still be off.
"""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone

import pytest

from app.db.session import SessionLocal
from app.models import (
    Role,
    User,
    WhatsAppAccount,
    WhatsAppAuditLog,
    WhatsAppProduct,
    WhatsAppRoutingRule,
    WhatsAppTemplate,
)


API = "/api/v1"

# Invented here, sent nowhere. Long enough to survive the length validators.
ATTACK_TOKEN = "PYTEST_ATTACK_ACCESS_TOKEN_" + "q" * 30
ATTACK_SECRET = "PYTEST_ATTACK_APP_SECRET_" + "w" * 30
ATTACK_VERIFY = "PYTEST_ATTACK_VERIFY_TOKEN_" + "e" * 30

FULL_CREDENTIALS = {
    "access_token": ATTACK_TOKEN,
    "app_secret": ATTACK_SECRET,
    "webhook_verify_token": ATTACK_VERIFY,
    "phone_number_id": "77712345678901",
    "waba_id": "77798765432109",
    "display_phone": "+237600000077",
}

SECRETS = (ATTACK_TOKEN, ATTACK_SECRET, ATTACK_VERIFY)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _strings(node, out: list) -> None:
    if isinstance(node, dict):
        for value in node.values():
            _strings(value, out)
    elif isinstance(node, list):
        for item in node:
            _strings(item, out)
    elif isinstance(node, str):
        out.append(node)


def assert_no_secret(text_or_body, *, secrets=SECRETS) -> None:
    """Nothing anywhere in this response resembles a credential we supplied.

    Checked against the raw text as well as the parsed tree, because a leak
    inside an unparsed error string is still a leak.
    """
    if isinstance(text_or_body, str):
        haystack = [text_or_body]
    else:
        haystack = []
        _strings(text_or_body, haystack)
    for secret in secrets:
        for value in haystack:
            assert secret not in value, "a credential value left the API"
            # Not "just the first few characters" either.
            assert secret[:10] not in value, "a credential prefix left the API"


def audit_actions(action: str) -> list:
    with SessionLocal() as db:
        return [
            {"outcome": r.outcome, "reason": r.reason, "details": r.details or {}}
            for r in db.query(WhatsAppAuditLog)
            .filter(WhatsAppAuditLog.action == action)
            .order_by(WhatsAppAuditLog.id.desc())
            .all()
        ]


@pytest.fixture(scope="module")
def world(admin_token):
    """One private pair of numbers, inactive and credential-free.

    Depends on ``admin_token`` only to force the session fixture that runs the
    app lifespan: without it a module-scoped fixture can reach the database
    before the tables exist.
    """
    suffix = uuid.uuid4().hex[:8]
    slugs = {"verify": f"atk_verify_{suffix}", "quata": f"atk_quata_{suffix}"}
    with SessionLocal() as db:
        db.add_all(
            [
                WhatsAppAccount(
                    slug=slugs["verify"],
                    name="Attack Verify",
                    purpose="authentication",
                    phone_number_id="",
                    waba_id="",
                    display_phone="",
                    api_version="v21.0",
                    is_active=False,
                    health="unknown",
                ),
                WhatsAppAccount(
                    slug=slugs["quata"],
                    name="Attack QUATA",
                    purpose="engagement",
                    phone_number_id="",
                    waba_id="",
                    display_phone="",
                    api_version="v21.0",
                    is_active=False,
                    health="unknown",
                ),
            ]
        )
        db.commit()
    yield slugs
    with SessionLocal() as db:
        ids = [
            row.id
            for row in db.query(WhatsAppAccount).filter(
                WhatsAppAccount.slug.in_(list(slugs.values()))
            )
        ]
        db.query(WhatsAppTemplate).filter(WhatsAppTemplate.account_id.in_(ids)).delete(
            synchronize_session=False
        )
        db.query(WhatsAppAccount).filter(WhatsAppAccount.id.in_(ids)).update(
            {WhatsAppAccount.is_active: False}, synchronize_session=False
        )
        db.commit()


@pytest.fixture(scope="module")
def product(admin_token):
    """An engagement-only product of our own, disabled and keyless."""
    slug = f"atk_prod_{uuid.uuid4().hex[:8]}"
    with SessionLocal() as db:
        db.add(
            WhatsAppProduct(
                slug=slug,
                name="Attack product",
                is_enabled=False,
                api_key_hash="",
                api_key_prefix="",
                allowed_purposes=["engagement"],
                default_locale="en",
                rate_limit_per_minute=600,
            )
        )
        db.commit()
    return slug


@pytest.fixture(scope="module")
def unprivileged_headers(admin_token):
    """A real, logged-in admin-console user who lacks ``settings:manage``.

    The existing suite checks the write routes against an anonymous caller,
    which only proves the door is shut. The interesting question is whether a
    Manager — a role that exists, has real console access, and is deliberately
    *not* given ``settings:manage`` — can switch on the fleet's OTP number.
    Token minted directly rather than through ``/auth/login`` so this fixture
    cannot spend the login rate limit the whole suite shares.
    """
    from app.core.security import create_access_token, hash_password

    email = f"atk_manager_{uuid.uuid4().hex[:8]}@quatadigital.com"
    with SessionLocal() as db:
        role = db.query(Role).filter(Role.slug == "manager").one()
        user = User(
            email=email,
            full_name="Attack Manager",
            password_hash=hash_password("NotUsed!2026"),
            is_active=True,
            role_id=role.id,
            must_reset_password=False,
            password_changed_at=datetime.now(timezone.utc),
        )
        db.add(user)
        db.commit()
        token = create_access_token(
            user.id, password_changed_at=user.password_changed_at
        )
    return {"Authorization": f"Bearer {token}"}


# ===========================================================================
# 1. Secrets — the error paths
# ===========================================================================

@pytest.mark.parametrize(
    "field,value",
    [
        # One character too long for the validator: the classic paste error.
        ("access_token", ATTACK_TOKEN + "z" * 1100),
        # Same paste error one field down, and past a different validator.
        ("app_secret", ATTACK_SECRET + "s" * 600),
        # The mis-paste that matters most — a token typed into the field next
        # to it. ``waba_id`` is not a secret, so a redaction rule keyed on the
        # field name would miss this one.
        ("waba_id", ATTACK_TOKEN),
    ],
)
def test_a_rejected_credential_is_never_echoed_back(
    client, admin_headers, world, field, value
):
    """A 422 must not hand the value back.

    FastAPI's default validation body carries ``input`` — the rejected value
    verbatim. For this route that value *is* the Meta access token, so the
    refusal disclosed exactly what the success path is careful never to
    disclose, into the response body and every log that records one.
    """
    r = client.put(
        f"{API}/admin/qcp/accounts/{world['quata']}/credentials",
        json={field: value},
        headers=admin_headers,
    )
    assert r.status_code == 422, r.text
    assert_no_secret(r.text)


def test_an_extra_field_carrying_a_secret_is_not_echoed(client, admin_headers, world):
    """``extra="forbid"`` reports the rejected key *and* its value."""
    r = client.put(
        f"{API}/admin/qcp/accounts/{world['quata']}/credentials",
        json={"purpose": ATTACK_TOKEN},
        headers=admin_headers,
    )
    assert r.status_code == 422, r.text
    assert_no_secret(r.text)
    # The operator still has to be told which field was refused.
    assert "purpose" in r.text


def test_a_send_that_fails_validation_never_echoes_the_variables(client):
    """The same echo on the product gateway would return an OTP.

    ``MessageSendIn.variables`` is where a login code travels. A 422 that
    quotes the rejected body puts it in a response and a log, which is the
    disclosure ``redaction.py`` exists to prevent one layer down.
    """
    r = client.post(
        f"{API}/whatsapp/messages/authentication",
        json={"to": "not-a-phone-number", "variables": {"1": "483920"}},
        headers={"X-QCP-Product": "quatafood", "X-QCP-Key": "wrong"},
    )
    assert r.status_code in (401, 422), r.text
    assert "483920" not in r.text


def test_no_error_path_on_the_write_surface_returns_a_stored_credential(
    client, admin_headers, world
):
    """Store real credentials, then walk every refusal this account can produce."""
    ok = client.put(
        f"{API}/admin/qcp/accounts/{world['verify']}/credentials",
        json=FULL_CREDENTIALS,
        headers=admin_headers,
    )
    assert ok.status_code == 200, ok.text
    assert_no_secret(ok.text)

    slug = world["verify"]
    refusals = [
        # confirmation_mismatch
        client.post(
            f"{API}/admin/qcp/accounts/{slug}/enable",
            json={"confirm_slug": "wrong", "justification": "attack attempt"},
            headers=admin_headers,
        ),
        # 404 on an unknown account — the message quotes the slug, not a value
        client.post(
            f"{API}/admin/qcp/accounts/no_such_account/test-connection",
            headers=admin_headers,
        ),
        # 422 — justification too short
        client.post(
            f"{API}/admin/qcp/accounts/{slug}/enable",
            json={"confirm_slug": slug, "justification": "no"},
            headers=admin_headers,
        ),
    ]
    for r in refusals:
        assert r.status_code >= 400, r.text
        assert_no_secret(r.text)

    # And the read surface, which is where a leak would be most durable.
    for path in ("/admin/qcp/overview", "/admin/qcp/products", "/admin/qcp/templates"):
        r = client.get(f"{API}{path}", headers=admin_headers)
        assert r.status_code == 200, r.text
        assert_no_secret(r.text)


@pytest.mark.parametrize(
    "quoted,label",
    [
        (ATTACK_TOKEN, "the whole access token"),
        # Meta truncates values in some error messages. An exact-substring
        # scrub does not fire on a fragment, and a fragment of a credential is
        # the "just the first few characters" disclosure the brief bans.
        (ATTACK_TOKEN[:24], "a truncated access token"),
        # The transport's scrub only knows the access token; the app secret
        # and the verify token are never passed to it.
        (ATTACK_SECRET, "the app secret"),
        (ATTACK_VERIFY, "the webhook verify token"),
    ],
)
def test_a_provider_error_quoting_a_credential_is_scrubbed_on_the_way_out(
    client, admin_headers, world, monkeypatch, quoted, label
):
    """Meta writes this text, not us, so it cannot be trusted with our secrets.

    Checked at every place the string comes to rest: the HTTP response, the
    ``whatsapp_accounts.last_error`` column it is written to, and the audit
    row that records the failed check.
    """
    from app.services.whatsapp import meta

    stored = client.put(
        f"{API}/admin/qcp/accounts/{world['verify']}/credentials",
        json=FULL_CREDENTIALS,
        headers=admin_headers,
    )
    assert stored.status_code == 200, stored.text

    def _leaky(account, *, db):
        return {
            "ok": False,
            "error": f"(#190) Error validating access token: {quoted} has expired",
            "unauthorized": True,
        }

    monkeypatch.setattr(meta, "get_phone_health", _leaky)
    r = client.post(
        f"{API}/admin/qcp/accounts/{world['verify']}/test-connection",
        headers=admin_headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is False
    assert quoted not in r.text, f"{label} left the API"

    with SessionLocal() as db:
        row = (
            db.query(WhatsAppAccount)
            .filter(WhatsAppAccount.slug == world["verify"])
            .one()
        )
        assert quoted not in (row.last_error or ""), f"{label} was persisted"
    assert quoted not in str(audit_actions("account.health_checked")[:1])


def test_a_minted_key_is_stored_as_a_hash_and_is_unrecoverable(
    client, admin_headers, product
):
    """The one plaintext QCP returns is returned once and never stored."""
    r = client.post(
        f"{API}/admin/qcp/products/{product}/api-key", headers=admin_headers
    )
    assert r.status_code == 201, r.text
    body = r.json()
    key = body["api_key"]
    assert body["shown_once"] is True

    with SessionLocal() as db:
        row = db.query(WhatsAppProduct).filter(WhatsAppProduct.slug == product).one()
        stored_hash, stored_prefix = row.api_key_hash, row.api_key_prefix
    assert stored_hash == hashlib.sha256(key.encode("utf-8")).hexdigest()
    assert key not in stored_hash
    # The display label is a digest fragment, not the head of the key.
    assert not key.startswith(stored_prefix)
    assert stored_prefix == f"qcp_{stored_hash[:8]}"

    # No later read produces it, and no audit row holds it.
    for path in (f"/admin/qcp/products", "/admin/qcp/overview"):
        follow = client.get(f"{API}{path}", headers=admin_headers)
        assert key not in follow.text
    with SessionLocal() as db:
        rows = db.query(WhatsAppAuditLog).filter(
            WhatsAppAuditLog.action.in_(
                ["product.api_key_minted", "product.api_key_rotated"]
            )
        ).all()
        for row in rows:
            assert key not in str(row.details or {})


def test_a_minted_key_actually_authenticates_at_the_gateway(client, admin_headers):
    """The minting side and the checking side must agree, byte for byte.

    ``routes_admin_whatsapp._hash_api_key`` (which stores) and
    ``routes_whatsapp._hash_key`` (which checks) are the same one-liner in two
    modules. If they ever drift, every key this console mints is dead on
    arrival and the failure shows up as a product-wide 401 nobody can explain
    from either file alone. This walks the whole loop: mint through the admin
    API, then present the key at the product gateway.
    """
    import hmac
    import time

    slug = f"atk_gateway_{uuid.uuid4().hex[:8]}"
    registered = client.post(
        f"{API}/admin/qcp/products",
        json={"slug": slug, "name": "Gateway loop"},
        headers=admin_headers,
    )
    assert registered.status_code == 201, registered.text

    minted = client.post(
        f"{API}/admin/qcp/products/{slug}/api-key", headers=admin_headers
    )
    assert minted.status_code == 201, minted.text
    key = minted.json()["api_key"]

    enabled = client.post(
        f"{API}/admin/qcp/products/{slug}/enable", headers=admin_headers
    )
    assert enabled.status_code == 200, enabled.text

    try:
        path = f"{API}/whatsapp/health"
        ts = str(int(time.time()))
        material = f"GET\n{path}\n\n{ts}.".encode("utf-8")
        signature = hmac.new(
            hashlib.sha256(key.encode("utf-8")).hexdigest().encode("utf-8"),
            material,
            hashlib.sha256,
        ).hexdigest()
        r = client.get(
            path,
            headers={
                "X-QCP-Product": slug,
                "X-QCP-Key": key,
                "X-QCP-Timestamp": ts,
                "X-QCP-Signature": signature,
            },
        )
        assert r.status_code == 200, r.text
        # And the revoked key stops working immediately.
        revoked = client.delete(
            f"{API}/admin/qcp/products/{slug}/api-key", headers=admin_headers
        )
        assert revoked.status_code == 200, revoked.text
        again = client.get(
            path,
            headers={
                "X-QCP-Product": slug,
                "X-QCP-Key": key,
                "X-QCP-Timestamp": ts,
                "X-QCP-Signature": signature,
            },
        )
        assert again.status_code == 401
    finally:
        client.post(f"{API}/admin/qcp/products/{slug}/disable", headers=admin_headers)


def test_an_empty_key_hash_is_a_denial_not_a_match(client, product):
    """A keyless product cannot authenticate — with any key, or with none."""
    with SessionLocal() as db:
        db.query(WhatsAppProduct).filter(WhatsAppProduct.slug == product).update(
            {WhatsAppProduct.api_key_hash: "", WhatsAppProduct.api_key_prefix: ""}
        )
        db.commit()
    for key in ("", "x", hashlib.sha256(b"").hexdigest()):
        r = client.get(
            f"{API}/whatsapp/health",
            headers={"X-QCP-Product": product, "X-QCP-Key": key},
        )
        assert r.status_code == 401, (key, r.text)


def test_no_qcp_response_model_declares_a_secret_bearing_field(app_instance):
    """Walked from the routes, not from the model list.

    Every response schema reachable from a QCP path is expanded — including
    the ones nested inside another response, which is where a leak would
    survive a shallow check — and any field whose *name* says it carries key
    material fails the build. Presence booleans (``has_access_token``),
    digests (``api_key_fingerprint``) and the non-reversible display label
    (``api_key_prefix``) are the sanctioned shapes and are allowed by name.

    ``ApiKeyMintedOut.api_key`` is the one exception, and it is the one the
    brief asks for: generated in the response, never stored, unrecoverable
    afterwards.
    """
    spec = app_instance.openapi()
    schemas = spec.get("components", {}).get("schemas", {}) or {}

    def refs(node, out: set) -> None:
        if isinstance(node, dict):
            ref = node.get("$ref")
            if isinstance(ref, str) and ref.startswith("#/components/schemas/"):
                name = ref.rsplit("/", 1)[-1]
                if name not in out:
                    out.add(name)
                    refs(schemas.get(name, {}), out)
            for value in node.values():
                refs(value, out)
        elif isinstance(node, list):
            for item in node:
                refs(item, out)

    reachable: set = set()
    for path, operations in spec["paths"].items():
        if "/qcp" not in path and "/whatsapp" not in path:
            continue
        for operation in operations.values():
            if not isinstance(operation, dict):
                continue
            refs(operation.get("responses") or {}, reachable)

    assert reachable, "no QCP response schemas found — the walk is broken"

    allowed = {"ApiKeyMintedOut.api_key"}
    offenders = []
    for name in sorted(reachable):
        for field in (schemas.get(name, {}).get("properties") or {}):
            lowered = field.lower()
            if not any(
                mark in lowered
                for mark in ("token", "secret", "password", "api_key", "apikey", "key")
            ):
                continue
            if (
                lowered.startswith("has_")
                or lowered.endswith(("_hash", "_prefix", "_fingerprint"))
                or lowered in ("body_hash",)
            ):
                continue
            if f"{name}.{field}" not in allowed:
                offenders.append(f"{name}.{field}")
    assert not offenders, f"secret-bearing QCP response fields: {offenders}"


# ===========================================================================
# 2. Separation — every way in
# ===========================================================================

def test_a_non_authentication_template_cannot_be_created_on_verify(
    client, admin_headers, world
):
    for category in ("utility", "marketing"):
        r = client.post(
            f"{API}/admin/qcp/templates",
            json={
                "account": world["verify"],
                "name": f"atk_{category}_{uuid.uuid4().hex[:6]}",
                "category": category,
                "intent": "order_update",
                "body": "Your order {{1}} is ready.",
            },
            headers=admin_headers,
        )
        assert r.status_code == 409, r.text
        assert r.json()["detail"]["reason"] == "non_auth_template_on_verify"
    # Refused, on the record, with the obstacle named.
    denials = audit_actions("template.create_denied")
    assert denials and denials[0]["outcome"] == "denied"


def test_an_authentication_template_cannot_be_created_off_verify(
    client, admin_headers, world
):
    r = client.post(
        f"{API}/admin/qcp/templates",
        json={
            "account": world["quata"],
            "name": f"atk_auth_{uuid.uuid4().hex[:6]}",
            "category": "authentication",
            "intent": "login_otp",
            "body": "Your code is {{1}}.",
        },
        headers=admin_headers,
    )
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["reason"] == "auth_template_off_verify"


def test_an_edit_cannot_walk_a_verify_template_out_of_authentication(
    client, admin_headers, world
):
    """The draft window is the only time category is editable — and even then."""
    name = f"atk_edit_{uuid.uuid4().hex[:6]}"
    created = client.post(
        f"{API}/admin/qcp/templates",
        json={
            "account": world["verify"],
            "name": name,
            "category": "authentication",
            "intent": "login_otp",
            "body": "Your code is {{1}}.",
        },
        headers=admin_headers,
    )
    assert created.status_code == 201, created.text
    template_id = created.json()["id"]

    r = client.patch(
        f"{API}/admin/qcp/templates/{template_id}",
        json={"category": "utility"},
        headers=admin_headers,
    )
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["reason"] == "non_auth_template_on_verify"

    with SessionLocal() as db:
        row = db.get(WhatsAppTemplate, template_id)
        assert row.category == "authentication"


def test_a_template_cannot_be_moved_to_another_account_by_any_write(
    client, admin_headers, world
):
    """``account`` is not editable, so a template cannot be walked across.

    Moving an approved authentication template onto the engagement number
    would put OTP traffic on QUATA without any category ever changing — the
    separation defeated by a field nobody thought of as dangerous.
    """
    r = client.patch(
        f"{API}/admin/qcp/templates/1",
        json={"account": world["quata"]},
        headers=admin_headers,
    )
    assert r.status_code == 422, r.text
    r2 = client.patch(
        f"{API}/admin/qcp/templates/1",
        json={"account_id": 1},
        headers=admin_headers,
    )
    assert r2.status_code == 422, r2.text


def test_an_account_purpose_cannot_be_changed_out_from_under_its_templates(
    client, admin_headers, world, app_instance
):
    """No write anywhere accepts ``purpose`` for an account.

    The composite foreign keys that carry the separation travel through
    ``whatsapp_accounts.purpose``. A number that changed purpose under live
    templates would strand every one of them — so the column is settable by
    nothing, and this asserts that at the contract level rather than by
    reading the one route that obviously refuses it.
    """
    r = client.put(
        f"{API}/admin/qcp/accounts/{world['verify']}/credentials",
        json={"purpose": "engagement"},
        headers=admin_headers,
    )
    assert r.status_code == 422, r.text

    spec = app_instance.openapi()
    for path, ops in spec["paths"].items():
        if "/admin/qcp/accounts/" not in path:
            continue
        for method, op in ops.items():
            ref = (
                (op.get("requestBody") or {})
                .get("content", {})
                .get("application/json", {})
                .get("schema", {})
                .get("$ref")
            )
            if not ref:
                continue
            model = ref.rsplit("/", 1)[-1]
            props = spec["components"]["schemas"][model].get("properties") or {}
            assert "purpose" not in props, f"{method.upper()} {path} accepts purpose"


def test_a_routing_rule_cannot_point_engagement_traffic_at_verify(
    client, admin_headers, world, product
):
    """A product with no authentication grant cannot route to the OTP number."""
    r = client.post(
        f"{API}/admin/qcp/routing-rules",
        json={
            "product": product,
            "intent": "login_otp",
            "purpose": "authentication",
            "template_intent": "login_otp",
        },
        headers=admin_headers,
    )
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["reason"] == "purpose_not_permitted"


def test_a_routing_rule_cannot_carry_an_auth_template_over_the_engagement_number(
    client, admin_headers, world, product
):
    """The pairing the two-number split exists to prevent, attempted directly."""
    intent = f"atk_authint_{uuid.uuid4().hex[:6]}"
    created = client.post(
        f"{API}/admin/qcp/templates",
        json={
            "account": world["verify"],
            "name": intent,
            "category": "authentication",
            "intent": intent,
            "body": "Your code is {{1}}.",
        },
        headers=admin_headers,
    )
    assert created.status_code == 201, created.text

    r = client.post(
        f"{API}/admin/qcp/routing-rules",
        json={
            "product": product,
            "intent": "login",
            "purpose": "engagement",
            "template_intent": intent,
        },
        headers=admin_headers,
    )
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["reason"] == "auth_traffic_on_engagement_number"


def test_a_sync_that_reclassifies_a_verify_template_quarantines_it(
    client, admin_headers, world
):
    """Meta re-classifying a live OTP template is the defect that started this.

    The row is not rewritten (the database would refuse it and the stated
    category is the evidence of what was approved); it stops being
    ``approved``, which is the only status the router selects.
    """
    name = f"atk_sync_{uuid.uuid4().hex[:6]}"
    with SessionLocal() as db:
        account = (
            db.query(WhatsAppAccount)
            .filter(WhatsAppAccount.slug == world["verify"])
            .one()
        )
        db.add(
            WhatsAppTemplate(
                account_id=account.id,
                account_purpose=account.purpose,
                name=name,
                language="en",
                category="authentication",
                intent="login_otp",
                status="approved",
                variables=["1"],
            )
        )
        db.commit()

    from app.services.whatsapp import dispatch

    def _meta_says_marketing(db, account):
        return {
            "ok": True,
            "data": [
                {
                    "name": name,
                    "language": "en",
                    "category": "MARKETING",
                    "status": "APPROVED",
                    "components": [{"type": "BODY", "text": "Your code is {{1}}."}],
                }
            ],
        }

    import app.api.routes_admin_templates as routes

    original = dispatch.fetch_message_templates
    routes.dispatch_service.fetch_message_templates = _meta_says_marketing
    try:
        r = client.post(
            f"{API}/admin/qcp/accounts/{world['verify']}/templates/sync",
            headers=admin_headers,
        )
    finally:
        routes.dispatch_service.fetch_message_templates = original

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["quarantined"] == 1
    assert any(a["kind"] == "non_auth_category_on_verify" for a in body["alerts"])

    with SessionLocal() as db:
        row = db.query(WhatsAppTemplate).filter(WhatsAppTemplate.name == name).one()
        assert row.status == "disabled"
        assert row.category == "authentication"

    alerts = client.get(f"{API}/admin/qcp/templates/alerts", headers=admin_headers)
    assert alerts.status_code == 200
    outstanding = [
        item
        for item in alerts.json()["items"]
        if item["kind"] == "non_auth_category_on_verify"
    ]
    assert outstanding

    # The standing list is the half that matters: the sync that found this may
    # have been run by someone else days ago. It has to name the same three
    # things the sync response named — which template, on which number, and
    # why — or the console renders a row nobody can act on.
    latest = outstanding[0]
    assert latest["template"] == name
    assert latest["account"] == world["verify"]
    assert "authentication" in latest["detail"]


def test_revoking_a_purpose_leaves_no_send_path_behind_it(client, admin_headers):
    """Least privilege is enforced at send time, not only at rule-creation.

    A rule written while a product held ``authentication`` survives the grant
    being taken away — nothing walks the routing table to deactivate it, so
    the console still shows a live rule pointed at the Verify number. What
    must not survive is the **send**, so this stands a product up with exactly
    that history and requires the router to refuse on the product's *current*
    entitlement rather than on what was true when the rule was written.
    """
    from app.services.whatsapp import routing

    slug = f"atk_revoked_{uuid.uuid4().hex[:8]}"
    with SessionLocal() as db:
        row = WhatsAppProduct(
            slug=slug,
            name="Revocation test",
            # Enabled and keyed, i.e. a product that has genuinely migrated —
            # the state in which losing a purpose is dangerous. Private to
            # this test; the seeded estate is untouched.
            is_enabled=True,
            api_key_hash=hashlib.sha256(b"atk").hexdigest(),
            api_key_prefix="qcp_atk",
            allowed_purposes=["authentication", "engagement"],
            default_locale="en",
            rate_limit_per_minute=600,
        )
        db.add(row)
        db.flush()
        db.add(
            WhatsAppRoutingRule(
                product_id=row.id,
                intent="login_otp",
                purpose="authentication",
                template_intent="login_otp",
                locale=None,
                priority=100,
                is_active=True,
                conditions={},
            )
        )
        db.commit()

    revoked = client.put(
        f"{API}/admin/qcp/products/{slug}/purposes",
        json={"purposes": ["engagement"]},
        headers=admin_headers,
    )
    assert revoked.status_code == 200, revoked.text
    assert revoked.json()["may_reach_authentication"] is False

    try:
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
    finally:
        with SessionLocal() as db:
            row = db.query(WhatsAppProduct).filter(WhatsAppProduct.slug == slug).one()
            db.query(WhatsAppRoutingRule).filter(
                WhatsAppRoutingRule.product_id == row.id
            ).delete(synchronize_session=False)
            row.is_enabled = False
            db.commit()


def test_the_overview_states_the_unset_phone_number_id_as_a_security_warning(
    client, admin_headers
):
    """The console's main screen has to say the separation is currently open.

    While ``phone_number_id`` is the seeded empty string the webhook cannot
    tell an envelope for this number from one for the other, and both numbers
    normally share a Meta app — so a correctly signed QUATA payload verifies
    at the Quata Verify webhook. The write surface reported that as a typed
    ``critical``; the *read* surface — the screen an operator actually opens —
    reported an empty field and left the severity to be inferred.
    """
    body = client.get(f"{API}/admin/qcp/overview", headers=admin_headers).json()
    unconfigured = [a for a in body["accounts"] if not a["has_phone_number_id"]]
    assert unconfigured, "expected at least one seeded number with no phone number id"
    for account in unconfigured:
        codes = {w["code"]: w for w in account["security"]}
        warning = codes.get("phone_number_id_unset_webhook_attribution_skipped")
        assert warning is not None, account["slug"]
        assert warning["severity"] == "critical"
        assert "signed" in warning["message"]

    # And a fully configured number carries no such warning, so the badge
    # means something when it appears.
    configured = [a for a in body["accounts"] if a["has_phone_number_id"]]
    for account in configured:
        codes = {w["code"] for w in account["security"]}
        assert "phone_number_id_unset_webhook_attribution_skipped" not in codes


# ===========================================================================
# 3. Privilege
# ===========================================================================

DANGEROUS_WRITES = [
    ("put", "/admin/qcp/accounts/{verify}/credentials", {"access_token": ATTACK_TOKEN}),
    (
        "post",
        "/admin/qcp/accounts/{verify}/enable",
        {"confirm_slug": "x", "justification": "escalation attempt"},
    ),
    ("post", "/admin/qcp/accounts/{verify}/disable", None),
    ("post", "/admin/qcp/accounts/{verify}/test-connection", None),
    ("post", "/admin/qcp/accounts/{verify}/templates/sync", None),
    ("post", "/admin/qcp/products", {"slug": "atk_priv", "name": "x"}),
    ("patch", "/admin/qcp/products/{product}", {"name": "renamed by an outsider"}),
    ("put", "/admin/qcp/products/{product}/purposes", {"purposes": ["engagement"]}),
    (
        "post",
        "/admin/qcp/products/{product}/purposes/authentication",
        {"justification": "escalation attempt"},
    ),
    ("post", "/admin/qcp/products/{product}/api-key", None),
    ("delete", "/admin/qcp/products/{product}/api-key", None),
    ("post", "/admin/qcp/products/{product}/enable", None),
    ("post", "/admin/qcp/products/{product}/disable", None),
    (
        "post",
        "/admin/qcp/templates",
        {
            "account": "{verify}",
            "name": "atk_priv",
            "category": "authentication",
            "intent": "login_otp",
            "body": "code {{1}}",
        },
    ),
    ("patch", "/admin/qcp/templates/1", {"intent": "hijacked"}),
    ("post", "/admin/qcp/templates/1/retire", None),
    (
        "post",
        "/admin/qcp/routing-rules",
        {
            "product": "{product}",
            "intent": "login_otp",
            "purpose": "authentication",
            "template_intent": "login_otp",
        },
    ),
    ("patch", "/admin/qcp/routing-rules/1", {"priority": 1}),
    ("post", "/admin/qcp/routing-rules/1/activate", None),
    ("post", "/admin/qcp/routing-rules/1/deactivate", None),
    ("delete", "/admin/qcp/routing-rules/1", None),
    ("post", "/admin/qcp/conversations/1/reassign", {"product": "{product}"}),
]


@pytest.mark.parametrize("method,path,payload", DANGEROUS_WRITES)
def test_a_console_user_without_settings_manage_can_write_nothing(
    client, unprivileged_headers, world, product, method, path, payload
):
    """A Manager has real console access and must not reach any of this.

    403 before anything happens: the refusal is the permission check, so the
    body is deliberately well-formed — a 422 here would mean validation ran
    first and the route was reachable.
    """
    resolved = path.format(verify=world["verify"], product=product)
    body = payload
    if isinstance(payload, dict):
        body = {
            k: (v.format(verify=world["verify"], product=product) if isinstance(v, str) else v)
            for k, v in payload.items()
        }
    call = getattr(client, method)
    # httpx's ``delete`` takes no body.
    r = (
        call(f"{API}{resolved}", headers=unprivileged_headers)
        if method == "delete"
        else call(f"{API}{resolved}", json=body, headers=unprivileged_headers)
    )
    assert r.status_code == 403, (method, resolved, r.status_code, r.text)


@pytest.mark.parametrize("method,path,payload", DANGEROUS_WRITES)
def test_no_write_route_is_reachable_unauthenticated(
    client, world, product, method, path, payload
):
    resolved = path.format(verify=world["verify"], product=product)
    r = getattr(client, method)(f"{API}{resolved}")
    assert r.status_code == 401, (method, resolved, r.status_code)


def test_the_unprivileged_user_cannot_read_the_console_either(
    client, unprivileged_headers
):
    """Reads are gated on the same permission — an OTP thread is not general
    admin data."""
    for path in ("/admin/qcp/overview", "/admin/qcp/products", "/admin/qcp/templates"):
        r = client.get(f"{API}{path}", headers=unprivileged_headers)
        assert r.status_code == 403, (path, r.status_code)


# ===========================================================================
# 4. Nothing on this surface answers with a stack trace
# ===========================================================================

MALFORMED_BODIES = [
    {},
    {"slug": None},
    # Wrong types where a string is expected.
    {"name": 12345, "slug": ["a", "b"]},
    # Deep nesting, which is where a naive dict walk falls over.
    {"example_payload": {"a": {"b": {"c": {"d": {"e": "f" * 200}}}}}},
    # Non-ASCII, an embedded NUL, a line separator and astral-plane text.
    {"name": "\u062f\u0631\u062f\u0634\u0629\x00\u2028", "intent": "\U0001f642" * 50},
    # A list where an object is expected.
    {"purposes": "authentication"},
    {"purposes": [{"authentication": True}]},
    # Numbers out of range.
    {"priority": -1, "rate_limit_per_minute": 10 ** 12},
]

FUZZ_TARGETS = [
    ("put", "/admin/qcp/accounts/{verify}/credentials"),
    ("post", "/admin/qcp/accounts/{verify}/enable"),
    ("post", "/admin/qcp/products"),
    ("patch", "/admin/qcp/products/{product}"),
    ("put", "/admin/qcp/products/{product}/purposes"),
    ("post", "/admin/qcp/products/{product}/purposes/authentication"),
    ("post", "/admin/qcp/templates"),
    ("patch", "/admin/qcp/templates/1"),
    ("post", "/admin/qcp/routing-rules"),
    ("patch", "/admin/qcp/routing-rules/1"),
    ("post", "/admin/qcp/conversations/1/reassign"),
]


@pytest.mark.parametrize("method,path", FUZZ_TARGETS)
def test_no_write_route_answers_a_malformed_body_with_a_stack_trace(
    client, admin_headers, world, product, method, path
):
    """A refusal must be a refusal. 500 is a refusal nobody can act on.

    Every one of these bodies is nonsense, and the operator has to be told
    *which* field is nonsense — which a 500 never does, while also putting a
    traceback in the log next to whatever else was in the request.
    """
    resolved = path.format(verify=world["verify"], product=product)
    for body in MALFORMED_BODIES:
        r = getattr(client, method)(
            f"{API}{resolved}", json=body, headers=admin_headers
        )
        # ``< 500`` rather than "must be a 4xx": a few of these bodies are
        # legitimately acceptable on some routes (an empty PATCH changes
        # nothing; ``example_payload`` takes an arbitrary object by design),
        # and a route that accepts one of those is behaving correctly. What
        # none of them may produce is a server error.
        assert r.status_code < 500, (method, resolved, body, r.status_code, r.text)
        assert_no_secret(r.text)


def test_a_truncated_or_junk_response_from_meta_does_not_500_the_sync(
    client, admin_headers, world
):
    """Meta's payload is the one input QCP genuinely does not control."""
    import app.api.routes_admin_templates as routes

    junk = [
        {"ok": True, "data": None},
        {"ok": True, "data": ["not-a-dict", 42, None]},
        {"ok": True, "data": [{}]},
        {"ok": True, "data": [{"name": "x", "status": "WHAT_IS_THIS"}]},
        {"ok": True},
        {"ok": False, "error": None},
    ]
    original = routes.dispatch_service.fetch_message_templates
    try:
        for payload in junk:
            routes.dispatch_service.fetch_message_templates = (
                lambda db, account, _p=payload: _p
            )
            r = client.post(
                f"{API}/admin/qcp/accounts/{world['verify']}/templates/sync",
                headers=admin_headers,
            )
            assert r.status_code == 200, (payload, r.text)
    finally:
        routes.dispatch_service.fetch_message_templates = original


# ===========================================================================
# 5. Dormancy, after everything above
# ===========================================================================

def test_qcp_is_still_dormant_after_the_whole_attack(client, admin_headers):
    """The estate this platform ships with must still be off.

    Runs last by file order and re-reads the seeded estate — not the private
    fixtures above — because "nothing I did switched anything on" is only
    worth asserting about the things a real deployment has.
    """
    from app.core.config import settings as env_settings
    from app.services.whatsapp import settings_store

    assert env_settings.WHATSAPP_ENABLED is False
    assert settings_store.delivery_enabled() is False

    r = client.get(f"{API}/admin/qcp/overview", headers=admin_headers)
    assert r.status_code == 200, r.text
    for account in r.json()["accounts"]:
        if account["slug"] in ("quata_verify", "quata"):
            assert account["is_active"] is False, account["slug"]
            assert account["configured"] is False, account["slug"]

    with SessionLocal() as db:
        seeded_ids = []
        for slug in ("quatapay", "quatafood", "abaqwa", "quatatrade"):
            row = (
                db.query(WhatsAppProduct)
                .filter(WhatsAppProduct.slug == slug)
                .one_or_none()
            )
            if row is None:
                continue
            seeded_ids.append(row.id)
            assert row.is_enabled is False, slug
            assert row.api_key_hash == "", slug
        # Scoped to the seeded four: the suite shares one database and other
        # modules legitimately stand up their own live estates to test the
        # send path. What must still be true is that nothing here left a live
        # route on a product a real deployment ships with.
        assert (
            db.query(WhatsAppRoutingRule)
            .filter(WhatsAppRoutingRule.product_id.in_(seeded_ids))
            .filter(WhatsAppRoutingRule.is_active == True)  # noqa: E712
            .count()
            == 0
        )
