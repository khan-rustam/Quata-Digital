"""The QCP admin **write** surface.

Until this existed the console had five routes and all five were GET: an
engineer configured QCP by inserting rows by hand. That absence is what
produced the worst defect this platform has had — ``whatsapp_templates.category``
was operator-typed data that no form validated, so a ``utility`` row could sit
on the Quata Verify number and Meta re-classifying it to ``MARKETING`` would
never be noticed. A CHECK constraint stops the row; only a real write API
stops the *practice*.

What is pinned here:

**No response ever carries a credential value.** Not the access token, not the
app secret, not a stored API key, not "the first few characters". Every write
response is walked to the leaves and checked against the plaintexts the test
itself supplied, so a future field that leaks one fails here rather than in
production. The single sanctioned exception — the plaintext of a *just-minted*
product key, returned once and never stored — is asserted to be absent from
every subsequent read.

**Nothing here switches QCP on.** The platform ships dormant: two seeded
accounts inactive, four seeded products disabled, delivery off. Every route
below is exercised and the dormancy of the seeded estate is re-asserted at the
end. A write API whose side effect is going live is not dormant.

**Refusals are refusals, not 500s.** The storage engine forbids a second
active number per purpose and a duplicate product slug. Both are surfaced as
an audited 409 naming what is in the way, because an IntegrityError traceback
tells an operator nothing they can act on.

**Least privilege survives contact with a form.** QuataFood owns the fleet's
only WhatsApp authentication path; QuataPay moved to email OTP on 2026-06-03.
Granting ``authentication`` to a product is a separate route with a mandatory
justification, and the ordinary "set purposes" route refuses to add it.

Isolation note: ``conftest.py`` runs one SQLite database for the whole
session, so everything here uses unique slugs, and the ``world`` fixture
stands its own numbers down on the way out — ``uq_whatsapp_accounts_active_purpose``
(at most one *active* number per purpose) is the one genuinely global
constraint in the schema.
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
    WhatsAppConversation,
    WhatsAppMessage,
    WhatsAppProduct,
)


API = "/api/v1"

# Obviously fake, and nothing in the suite ever sends them anywhere.
TOKEN = "PYTEST_NOT_A_REAL_ACCESS_TOKEN_" + "x" * 24
APP_SECRET = "PYTEST_NOT_A_REAL_APP_SECRET_" + "y" * 20
VERIFY_TOKEN = "PYTEST_NOT_A_REAL_VERIFY_TOKEN_" + "z" * 18

FULL_CREDENTIALS = {
    "access_token": TOKEN,
    "app_secret": APP_SECRET,
    "webhook_verify_token": VERIFY_TOKEN,
    "phone_number_id": "10203040506070",
    "waba_id": "60504030201000",
    "display_phone": "+237600000009",
}

# Column names that carry a value. None may appear as a key anywhere in any
# write response — mirrors ``test_whatsapp_admin_console.CREDENTIAL_KEYS``.
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
# Helpers
# ---------------------------------------------------------------------------

def _leaves(node, *, keys: set, values: list) -> None:
    """Collect every key and every scalar in a JSON document."""
    if isinstance(node, dict):
        for key, value in node.items():
            keys.add(key)
            _leaves(value, keys=keys, values=values)
    elif isinstance(node, list):
        for item in node:
            _leaves(item, keys=keys, values=values)
    else:
        values.append(node)


def assert_discloses_nothing(body, *, secrets=(TOKEN, APP_SECRET, VERIFY_TOKEN)) -> None:
    """No credential key, and no credential value, anywhere in the document.

    Checked on the *whole* tree rather than the top level: nesting a token
    one level down is exactly how a leak survives a shallow assertion.
    """
    keys: set = set()
    values: list = []
    _leaves(body, keys=keys, values=values)
    assert CREDENTIAL_KEYS.isdisjoint(keys), f"credential key in response: {keys}"
    for secret in secrets:
        for value in values:
            if isinstance(value, str):
                assert secret not in value, "a credential value left the API"
                # Not "just the first few characters" either.
                assert secret[:8] not in value


def fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


def audit_rows(action: str, resource_id=None) -> list:
    with SessionLocal() as db:
        q = db.query(WhatsAppAuditLog).filter(WhatsAppAuditLog.action == action)
        if resource_id is not None:
            q = q.filter(WhatsAppAuditLog.resource_id == str(resource_id))
        return [
            {
                "actor_id": r.actor_id,
                "outcome": r.outcome,
                "reason": r.reason,
                "details": r.details or {},
                "resource_id": r.resource_id,
            }
            for r in q.order_by(WhatsAppAuditLog.id.desc()).all()
        ]


def account_row(slug: str) -> dict:
    with SessionLocal() as db:
        row = db.query(WhatsAppAccount).filter(WhatsAppAccount.slug == slug).one()
        return {
            "is_active": row.is_active,
            "phone_number_id": row.phone_number_id,
            "waba_id": row.waba_id,
            "display_phone": row.display_phone,
            "access_token_encrypted": row.access_token_encrypted,
            "app_secret_encrypted": row.app_secret_encrypted,
            "webhook_verify_token_encrypted": row.webhook_verify_token_encrypted,
        }


def product_row(slug: str) -> dict:
    with SessionLocal() as db:
        row = db.query(WhatsAppProduct).filter(WhatsAppProduct.slug == slug).one()
        return {
            "id": row.id,
            "is_enabled": row.is_enabled,
            "api_key_hash": row.api_key_hash,
            "api_key_prefix": row.api_key_prefix,
            "allowed_purposes": list(row.allowed_purposes or []),
        }


@pytest.fixture(scope="module")
def admin_user_id():
    with SessionLocal() as db:
        return db.query(User).filter(User.email == "admin@quatadigital.com").one().id


@pytest.fixture(scope="module")
def world():
    """Three private numbers: two authentication, one engagement.

    Two authentication numbers because the partial unique index allows only
    one *active* per purpose, and that refusal is one of the things under
    test. All three arrive inactive and credential-free, exactly as the
    seeder leaves the real ones.
    """
    suffix = uuid.uuid4().hex[:8]
    slugs = {
        "verify": f"wr_verify_{suffix}",
        "spare": f"wr_spare_{suffix}",
        "quata": f"wr_quata_{suffix}",
    }
    with SessionLocal() as db:
        # One active number per purpose is global; take the field first, the
        # same way ``tests/whatsapp_world.build`` does.
        db.query(WhatsAppAccount).filter(WhatsAppAccount.is_active == True).update(  # noqa: E712
            {WhatsAppAccount.is_active: False}, synchronize_session=False
        )
        db.add_all(
            [
                WhatsAppAccount(
                    slug=slugs["verify"],
                    name="Write-test Verify",
                    purpose="authentication",
                    phone_number_id="",
                    waba_id="",
                    display_phone="",
                    api_version="v21.0",
                    is_active=False,
                    health="unknown",
                ),
                WhatsAppAccount(
                    slug=slugs["spare"],
                    name="Write-test Verify (spare)",
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
                    name="Write-test QUATA",
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
        db.query(WhatsAppAccount).filter(
            WhatsAppAccount.slug.in_(list(slugs.values()))
        ).update({WhatsAppAccount.is_active: False}, synchronize_session=False)
        db.commit()


def register_product(client, admin_headers, **overrides) -> str:
    slug = overrides.pop("slug", None) or f"wr_prod_{uuid.uuid4().hex[:8]}"
    payload = {"slug": slug, "name": "Write-test product", **overrides}
    r = client.post(f"{API}/admin/qcp/products", json=payload, headers=admin_headers)
    assert r.status_code == 201, r.text
    return slug


# ---------------------------------------------------------------------------
# Authentication and permissions
# ---------------------------------------------------------------------------

WRITE_ROUTES = [
    ("put", "/admin/qcp/accounts/quata/credentials"),
    ("post", "/admin/qcp/accounts/quata/enable"),
    ("post", "/admin/qcp/accounts/quata/disable"),
    ("post", "/admin/qcp/accounts/quata/test-connection"),
    ("post", "/admin/qcp/products"),
    ("patch", "/admin/qcp/products/quatapay"),
    ("put", "/admin/qcp/products/quatapay/purposes"),
    ("post", "/admin/qcp/products/quatapay/purposes/authentication"),
    ("post", "/admin/qcp/products/quatapay/api-key"),
    ("delete", "/admin/qcp/products/quatapay/api-key"),
    ("post", "/admin/qcp/products/quatapay/enable"),
    ("post", "/admin/qcp/products/quatapay/disable"),
    ("post", "/admin/qcp/conversations/1/reassign"),
]


@pytest.mark.parametrize("method,path", WRITE_ROUTES)
def test_every_write_route_requires_authentication(client, method, path):
    """No write is reachable without a token — checked before validation.

    An unauthenticated caller must not be able to tell a well-formed body
    from a malformed one, so this sends none at all and still expects 401.
    """
    assert getattr(client, method)(f"{API}{path}").status_code == 401


# ---------------------------------------------------------------------------
# The dangerous subset needs more than "can edit site settings"
# ---------------------------------------------------------------------------
#
# ``settings:manage`` is held by every Admin and is what gates the contact
# address on the marketing site. It also used to gate switching on the number
# that carries QuataFood's login OTP, minting a gateway credential and giving
# a product the authentication purpose. Those three actions reach the whole
# fleet, not this website, so they now take ``whatsapp:operate``, which only
# Super Admin is seeded with.

@pytest.fixture(scope="module")
def site_admin_headers():
    """A real Admin: holds ``settings:manage``, not ``whatsapp:operate``.

    This is the role the split is *about* — not an anonymous caller and not
    an unprivileged one. They can still work the QCP console; the question is
    whether they can commission the fleet's OTP number from it.

    Token minted directly rather than through ``/auth/login`` so this fixture
    does not spend the login rate limit the whole suite shares.
    """
    from app.core.security import create_access_token, hash_password

    email = f"wr_admin_{uuid.uuid4().hex[:8]}@quatadigital.com"
    with SessionLocal() as db:
        role = db.query(Role).filter(Role.slug == "admin").one()
        held = {p.permission for p in role.permissions}
        assert "settings:manage" in held, "the Admin role must still hold settings:manage"
        assert "whatsapp:operate" not in held, (
            "the Admin role must not hold the QCP operate permission"
        )
        user = User(
            email=email,
            full_name="Write-test Admin",
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


@pytest.fixture(scope="module")
def flow_account():
    """A private engagement number for the end-to-end setup rehearsal.

    Its own row rather than one of ``world``'s, because the rehearsal
    configures and switches it on, and the tests below depend on ``world``'s
    numbers arriving credential-free. Teardown stands it down whatever
    happens — ``uq_whatsapp_accounts_active_purpose`` allows one active
    number per purpose for the whole session.
    """
    slug = f"wr_flow_{uuid.uuid4().hex[:8]}"
    with SessionLocal() as db:
        db.add(
            WhatsAppAccount(
                slug=slug,
                name="Write-test flow number",
                purpose="engagement",
                phone_number_id="",
                waba_id="",
                display_phone="",
                api_version="v21.0",
                is_active=False,
                health="unknown",
            )
        )
        db.commit()
    yield slug
    with SessionLocal() as db:
        db.query(WhatsAppAccount).filter(WhatsAppAccount.slug == slug).update(
            {WhatsAppAccount.is_active: False}, synchronize_session=False
        )
        db.commit()


@pytest.fixture(scope="module")
def dangerous_product(admin_token):
    """A product with a key and no authentication grant, for the 403 checks."""
    headers = {"Authorization": f"Bearer {admin_token}"}
    from fastapi.testclient import TestClient
    from app.main import app

    slug = f"wr_perm_{uuid.uuid4().hex[:8]}"
    with TestClient(app) as c:
        r = c.post(
            f"{API}/admin/qcp/products",
            json={"slug": slug, "name": "Permission-test product"},
            headers=headers,
        )
        assert r.status_code == 201, r.text
        assert (
            c.post(f"{API}/admin/qcp/products/{slug}/api-key", headers=headers).status_code
            == 201
        )
    return slug


def _dangerous_calls(account_slug: str, product_slug: str):
    return [
        (
            "account_enable",
            "post",
            f"/admin/qcp/accounts/{account_slug}/enable",
            {"confirm_slug": account_slug, "justification": "escalation attempt"},
        ),
        ("account_disable", "post", f"/admin/qcp/accounts/{account_slug}/disable", None),
        ("api_key_mint", "post", f"/admin/qcp/products/{product_slug}/api-key", None),
        ("api_key_revoke", "delete", f"/admin/qcp/products/{product_slug}/api-key", None),
        (
            "authentication_grant",
            "post",
            f"/admin/qcp/products/{product_slug}/purposes/authentication",
            {"justification": "escalation attempt with a sentence attached"},
        ),
    ]


@pytest.mark.parametrize(
    "name",
    [
        "account_enable",
        "account_disable",
        "api_key_mint",
        "api_key_revoke",
        "authentication_grant",
    ],
)
def test_a_site_admin_cannot_perform_the_dangerous_qcp_actions(
    client, site_admin_headers, world, dangerous_product, name
):
    """Every Admin holds ``settings:manage``. None of them may do these.

    A restricted Quata Verify number locks QuataFood users out of their
    accounts — login OTP, payment-PIN reset and phone-change verification
    have no email fallback — so "can edit the site's contact address" is not
    the right ticket for switching it on.
    """
    calls = {c[0]: c for c in _dangerous_calls(world["quata"], dangerous_product)}
    _label, method, path, body = calls[name]
    call = getattr(client, method)
    r = (
        call(f"{API}{path}", headers=site_admin_headers)
        if body is None
        else call(f"{API}{path}", json=body, headers=site_admin_headers)
    )
    assert r.status_code == 403, r.text
    # Refused on the permission, before anything was decided about the body.
    assert "permission" in r.text.lower()


def test_the_refused_admin_changed_nothing(
    client, site_admin_headers, world, dangerous_product
):
    """A 403 that still mutated would be worse than no gate at all."""
    before_key = product_row(dangerous_product)["api_key_hash"]
    before_purposes = product_row(dangerous_product)["allowed_purposes"]
    for _name, method, path, body in _dangerous_calls(
        world["quata"], dangerous_product
    ):
        call = getattr(client, method)
        r = (
            call(f"{API}{path}", headers=site_admin_headers)
            if body is None
            else call(f"{API}{path}", json=body, headers=site_admin_headers)
        )
        assert r.status_code == 403, (path, r.text)

    assert account_row(world["quata"])["is_active"] is False
    after = product_row(dangerous_product)
    assert after["api_key_hash"] == before_key
    assert after["allowed_purposes"] == before_purposes


def test_a_site_admin_can_still_do_the_ordinary_qcp_work(
    client, site_admin_headers, world
):
    """The split must not take the console away from the people running it.

    Reading the estate, storing credentials, registering a product and
    correcting its details are all still ``settings:manage``. Only the
    fleet-reaching actions moved.
    """
    assert (
        client.get(f"{API}/admin/qcp/overview", headers=site_admin_headers).status_code
        == 200
    )
    assert (
        client.put(
            f"{API}/admin/qcp/accounts/{world['quata']}/credentials",
            json={"api_version": "v21.0"},
            headers=site_admin_headers,
        ).status_code
        == 200
    )
    slug = f"wr_sa_{uuid.uuid4().hex[:8]}"
    assert (
        client.post(
            f"{API}/admin/qcp/products",
            json={"slug": slug, "name": "Site-admin product"},
            headers=site_admin_headers,
        ).status_code
        == 201
    )
    assert (
        client.patch(
            f"{API}/admin/qcp/products/{slug}",
            json={"name": "Site-admin product, renamed"},
            headers=site_admin_headers,
        ).status_code
        == 200
    )


def test_a_super_admin_can_still_complete_the_whole_setup_flow(
    client, admin_headers, flow_account
):
    """The lockout check. A split that leaves QCP unconfigurable is worse.

    Runs the commissioning sequence end to end as the seeded Super Admin —
    credentials, switch the number on, register a product, mint its key,
    grant it authentication, switch it on — then stands the number back down.
    """
    r = client.put(
        f"{API}/admin/qcp/accounts/{flow_account}/credentials",
        json=FULL_CREDENTIALS,
        headers=admin_headers,
    )
    assert r.status_code == 200, r.text

    r = client.post(
        f"{API}/admin/qcp/accounts/{flow_account}/enable",
        json={"confirm_slug": flow_account, "justification": "go-live rehearsal"},
        headers=admin_headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["is_active"] is True

    slug = register_product(client, admin_headers)
    assert (
        client.post(
            f"{API}/admin/qcp/products/{slug}/api-key", headers=admin_headers
        ).status_code
        == 201
    )
    r = client.post(
        f"{API}/admin/qcp/products/{slug}/purposes/authentication",
        json={"justification": "rehearsal: this product owns an OTP path"},
        headers=admin_headers,
    )
    assert r.status_code == 200, r.text
    assert (
        client.post(
            f"{API}/admin/qcp/products/{slug}/enable", headers=admin_headers
        ).status_code
        == 200
    )

    # Put the rehearsal back where it started.
    assert (
        client.post(
            f"{API}/admin/qcp/accounts/{flow_account}/disable", headers=admin_headers
        ).status_code
        == 200
    )
    assert account_row(flow_account)["is_active"] is False


# ---------------------------------------------------------------------------
# Accounts — credentials
# ---------------------------------------------------------------------------

def test_setting_credentials_stores_them_encrypted_and_returns_no_value(
    client, admin_headers, world
):
    slug = world["quata"]
    r = client.put(
        f"{API}/admin/qcp/accounts/{slug}/credentials",
        json=FULL_CREDENTIALS,
        headers=admin_headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert_discloses_nothing(body)

    states = {c["field"]: c for c in body["credentials"]}
    assert states["access_token"]["configured"] is True
    assert states["access_token"]["length"] == len(TOKEN)
    assert states["access_token"]["fingerprint"] == fingerprint(TOKEN)
    assert states["app_secret"]["fingerprint"] == fingerprint(APP_SECRET)
    assert body["configured"] is True
    # Configuring is not switching on.
    assert body["is_active"] is False

    stored = account_row(slug)
    for column, plaintext in (
        ("access_token_encrypted", TOKEN),
        ("app_secret_encrypted", APP_SECRET),
        ("webhook_verify_token_encrypted", VERIFY_TOKEN),
    ):
        assert stored[column]
        assert plaintext not in stored[column], "credential stored in clear"
    from app.services.whatsapp import credentials as creds

    assert creds.decrypt_wa_secret(stored["access_token_encrypted"]) == TOKEN


def test_a_credential_write_is_audited_as_old_fingerprint_to_new(
    client, admin_headers, world, admin_user_id
):
    slug = world["quata"]
    before = fingerprint(TOKEN)
    rotated = TOKEN.replace("x", "q")

    r = client.put(
        f"{API}/admin/qcp/accounts/{slug}/credentials",
        json={"access_token": rotated},
        headers=admin_headers,
    )
    assert r.status_code == 200, r.text
    assert_discloses_nothing(r.json(), secrets=(TOKEN, rotated))

    rows = audit_rows("account.credentials_set")
    assert rows, "no audit row for a credential write"
    latest = rows[0]
    assert latest["actor_id"] == admin_user_id
    changed = {c["field"]: c for c in latest["details"]["changed"]}
    assert changed["access_token"]["from"] == before
    assert changed["access_token"]["to"] == fingerprint(rotated)
    # The audit trail describes the change; it never holds the credential.
    assert rotated not in str(latest["details"])

    # Put the shared fixture value back for the tests that follow.
    client.put(
        f"{API}/admin/qcp/accounts/{slug}/credentials",
        json={"access_token": TOKEN},
        headers=admin_headers,
    )


def test_an_unset_phone_number_id_is_reported_as_a_security_state(
    client, admin_headers, world
):
    """Not an incomplete form — a hole.

    While ``phone_number_id`` is the seeded empty string the webhook skips
    cross-number attribution, and both numbers normally share one app
    secret, so a QUATA envelope verifies at the Quata Verify webhook.
    """
    slug = world["verify"]
    r = client.put(
        f"{API}/admin/qcp/accounts/{slug}/credentials",
        json={"access_token": TOKEN},
        headers=admin_headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["webhook_cross_number_attribution"] is False
    critical = [w for w in body["security"] if w["severity"] == "critical"]
    assert any("phone_number_id" in w["code"] for w in critical), body["security"]
    assert "phone_number_id" in body["blocking"]

    # Setting it closes the hole and the report says so.
    r = client.put(
        f"{API}/admin/qcp/accounts/{slug}/credentials",
        json={"phone_number_id": "11223344556677"},
        headers=admin_headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["webhook_cross_number_attribution"] is True


def test_an_unknown_account_is_a_404_not_a_create(client, admin_headers):
    r = client.put(
        f"{API}/admin/qcp/accounts/not_a_real_number/credentials",
        json={"access_token": TOKEN},
        headers=admin_headers,
    )
    assert r.status_code == 404


def test_an_empty_credential_body_is_refused(client, admin_headers, world):
    r = client.put(
        f"{API}/admin/qcp/accounts/{world['quata']}/credentials",
        json={},
        headers=admin_headers,
    )
    assert r.status_code == 422


def test_an_account_purpose_cannot_be_rewritten_through_the_credential_route(
    client, admin_headers, world
):
    """``purpose`` is the column the whole separation travels through."""
    r = client.put(
        f"{API}/admin/qcp/accounts/{world['quata']}/credentials",
        json={"access_token": TOKEN, "purpose": "authentication"},
        headers=admin_headers,
    )
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# Accounts — enabling
# ---------------------------------------------------------------------------

def test_an_account_cannot_be_switched_on_until_it_is_fully_configured(
    client, admin_headers, world
):
    slug = world["spare"]
    r = client.post(
        f"{API}/admin/qcp/accounts/{slug}/enable",
        json={"confirm_slug": slug, "justification": "go-live rehearsal"},
        headers=admin_headers,
    )
    assert r.status_code == 409, r.text
    detail = r.json()["detail"]
    assert detail["reason"] == "not_configured"
    # Actionable: it names the fields, not just "invalid".
    assert "access_token" in detail["blocking"]
    assert account_row(slug)["is_active"] is False

    denials = audit_rows("account.enable_denied", resource_id=slug)
    assert denials and denials[0]["outcome"] == "denied"
    assert denials[0]["reason"] == "not_configured"


def test_switching_a_number_on_needs_its_own_slug_typed_back(
    client, admin_headers, world
):
    slug = world["quata"]
    client.put(
        f"{API}/admin/qcp/accounts/{slug}/credentials",
        json=FULL_CREDENTIALS,
        headers=admin_headers,
    )
    r = client.post(
        f"{API}/admin/qcp/accounts/{slug}/enable",
        json={"confirm_slug": "something_else", "justification": "fat fingers"},
        headers=admin_headers,
    )
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["reason"] == "confirmation_mismatch"
    assert account_row(slug)["is_active"] is False


def test_switching_a_fully_configured_number_on_is_audited_loudly(
    client, admin_headers, world, admin_user_id
):
    slug = world["quata"]
    client.put(
        f"{API}/admin/qcp/accounts/{slug}/credentials",
        json=FULL_CREDENTIALS,
        headers=admin_headers,
    )
    r = client.post(
        f"{API}/admin/qcp/accounts/{slug}/enable",
        json={"confirm_slug": slug, "justification": "QCP go-live for engagement"},
        headers=admin_headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["is_active"] is True
    assert_discloses_nothing(body)
    assert account_row(slug)["is_active"] is True

    rows = audit_rows("account.enabled", resource_id=slug)
    assert rows, "enabling a number must be audited"
    assert rows[0]["actor_id"] == admin_user_id
    assert rows[0]["details"]["justification"] == "QCP go-live for engagement"
    assert rows[0]["details"]["purpose"] == "engagement"

    r = client.post(f"{API}/admin/qcp/accounts/{slug}/disable", headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.json()["is_active"] is False
    assert audit_rows("account.disabled", resource_id=slug)


def test_a_second_active_number_for_one_purpose_is_a_409_not_a_500(
    client, admin_headers, world
):
    """The partial unique index refuses it. The API must say so in English."""
    first, second = world["verify"], world["spare"]
    for slug in (first, second):
        client.put(
            f"{API}/admin/qcp/accounts/{slug}/credentials",
            json=FULL_CREDENTIALS,
            headers=admin_headers,
        )
    r = client.post(
        f"{API}/admin/qcp/accounts/{first}/enable",
        json={"confirm_slug": first, "justification": "primary verify number"},
        headers=admin_headers,
    )
    assert r.status_code == 200, r.text

    r = client.post(
        f"{API}/admin/qcp/accounts/{second}/enable",
        json={"confirm_slug": second, "justification": "second verify number"},
        headers=admin_headers,
    )
    assert r.status_code == 409, r.text
    detail = r.json()["detail"]
    assert detail["reason"] == "another_account_active_for_purpose"
    # Names the incumbent, so the operator knows what to switch off.
    assert detail["conflict"] == first
    assert account_row(second)["is_active"] is False

    client.post(f"{API}/admin/qcp/accounts/{first}/disable", headers=admin_headers)


# ---------------------------------------------------------------------------
# Accounts — test connection
# ---------------------------------------------------------------------------

def test_testing_an_unconfigured_number_never_reaches_the_network(
    client, admin_headers, world, monkeypatch
):
    from app.services.whatsapp import dispatch

    def _explode(*args, **kwargs):
        raise AssertionError("the transport must not be reached")

    monkeypatch.setattr(dispatch, "fetch_phone_health", _explode)
    with SessionLocal() as db:
        db.query(WhatsAppAccount).filter(
            WhatsAppAccount.slug == world["spare"]
        ).update({WhatsAppAccount.access_token_encrypted: None})
        db.commit()

    r = client.post(
        f"{API}/admin/qcp/accounts/{world['spare']}/test-connection",
        headers=admin_headers,
    )
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["reason"] == "not_configured"


def test_a_connection_test_asks_meta_and_messages_nobody(
    client, admin_headers, world, monkeypatch, admin_user_id
):
    from app.services.whatsapp import dispatch

    calls = []

    # Same signature as the real ``dispatch.fetch_phone_health``, which takes
    # the console's actor so its own ``account.health_checked`` row is
    # attributable rather than looking machine-made.
    def _fake(db, account, *, actor_id=None):
        calls.append(account.slug)
        account.health = "ok"
        account.quality_rating = "GREEN"
        account.messaging_limit = "TIER_1K"
        db.commit()
        return {
            "ok": True,
            "quality_rating": "GREEN",
            "messaging_limit": "TIER_1K",
            "verified_name": "QUATA",
        }

    monkeypatch.setattr(dispatch, "fetch_phone_health", _fake)
    slug = world["quata"]
    client.put(
        f"{API}/admin/qcp/accounts/{slug}/credentials",
        json=FULL_CREDENTIALS,
        headers=admin_headers,
    )
    r = client.post(
        f"{API}/admin/qcp/accounts/{slug}/test-connection", headers=admin_headers
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert calls == [slug]
    assert body["ok"] is True
    assert body["quality_rating"] == "GREEN"
    # Pinned in the contract: a "test" that could message a customer is not one.
    assert body["sent_message"] is False
    assert_discloses_nothing(body)
    # Still off. Checking a number is not commissioning it.
    assert body["account"]["is_active"] is False

    rows = audit_rows("account.test_connection", resource_id=slug)
    assert rows and rows[0]["actor_id"] == admin_user_id


# ---------------------------------------------------------------------------
# Products — registration
# ---------------------------------------------------------------------------

def test_a_newly_registered_product_is_dormant_keyless_and_engagement_only(
    client, admin_headers, admin_user_id
):
    slug = register_product(client, admin_headers)
    r = client.get(f"{API}/admin/qcp/products", headers=admin_headers)
    item = {p["slug"]: p for p in r.json()["items"]}[slug]
    assert item["is_enabled"] is False
    assert item["has_api_key"] is False
    assert item["allowed_purposes"] == ["engagement"]

    rows = audit_rows("product.registered", resource_id=slug)
    assert rows and rows[0]["actor_id"] == admin_user_id


def test_registering_a_duplicate_slug_is_a_409_not_a_500(client, admin_headers):
    slug = register_product(client, admin_headers)
    r = client.post(
        f"{API}/admin/qcp/products",
        json={"slug": slug, "name": "Impostor"},
        headers=admin_headers,
    )
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["reason"] == "slug_taken"


def test_a_product_cannot_smuggle_purposes_or_a_key_into_registration(
    client, admin_headers
):
    for extra in (
        {"allowed_purposes": ["authentication"]},
        {"is_enabled": True},
        {"api_key_hash": "0" * 64},
    ):
        r = client.post(
            f"{API}/admin/qcp/products",
            json={"slug": f"wr_x_{uuid.uuid4().hex[:8]}", "name": "X", **extra},
            headers=admin_headers,
        )
        assert r.status_code == 422, (extra, r.text)


# ---------------------------------------------------------------------------
# Products — correcting a registration
# ---------------------------------------------------------------------------
#
# Until this route existed, a product's name, description and rate limit were
# whatever was typed into the registration form, for ever: a typo in the name
# the console displays was permanent, and a throughput cap set wrong could
# only be fixed with an UPDATE by hand — which is the practice the whole write
# surface exists to end.

def test_a_products_name_description_and_rate_limit_can_be_corrected(
    client, admin_headers
):
    slug = register_product(
        client, admin_headers, name="Qautapay", description="Typo'd at registration"
    )
    r = client.patch(
        f"{API}/admin/qcp/products/{slug}",
        json={
            "name": "QuataPay",
            "description": "Payments",
            "rate_limit_per_minute": 1200,
        },
        headers=admin_headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["name"] == "QuataPay"
    assert body["description"] == "Payments"
    assert body["rate_limit_per_minute"] == 1200
    assert_discloses_nothing(body)

    item = {
        p["slug"]: p
        for p in client.get(f"{API}/admin/qcp/products", headers=admin_headers).json()[
            "items"
        ]
    }[slug]
    assert item["name"] == "QuataPay"
    assert item["rate_limit_per_minute"] == 1200


def test_an_edit_changes_nothing_it_was_not_asked_to_change(client, admin_headers):
    """Partial: correcting the name must not reset the rate limit."""
    slug = register_product(client, admin_headers, rate_limit_per_minute=90)
    r = client.patch(
        f"{API}/admin/qcp/products/{slug}",
        json={"name": "Renamed only"},
        headers=admin_headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["rate_limit_per_minute"] == 90
    assert r.json()["is_enabled"] is False
    assert r.json()["allowed_purposes"] == ["engagement"]


def test_a_rate_limit_change_is_audited_as_old_to_new(
    client, admin_headers, admin_user_id
):
    """It caps what a product may send, so "who widened it" must be answerable."""
    slug = register_product(client, admin_headers, rate_limit_per_minute=600)
    r = client.patch(
        f"{API}/admin/qcp/products/{slug}",
        json={"rate_limit_per_minute": 6000},
        headers=admin_headers,
    )
    assert r.status_code == 200, r.text

    rows = audit_rows("product.rate_limit_changed", resource_id=slug)
    assert rows, "a throughput change must be audited under its own action"
    assert rows[0]["actor_id"] == admin_user_id
    changed = {c["field"]: c for c in rows[0]["details"]["changed"]}
    assert changed["rate_limit_per_minute"]["from"] == 600
    assert changed["rate_limit_per_minute"]["to"] == 6000

    updates = audit_rows("product.updated", resource_id=slug)
    assert updates and updates[0]["actor_id"] == admin_user_id


def test_an_edit_cannot_reach_the_slug_the_key_or_the_switches(client, admin_headers):
    """The identity a product authenticates with, and every gate, stay put."""
    slug = register_product(client, admin_headers)
    for extra in (
        {"slug": "renamed_product"},
        {"is_enabled": True},
        {"api_key_hash": "0" * 64},
        {"allowed_purposes": ["authentication"]},
    ):
        r = client.patch(
            f"{API}/admin/qcp/products/{slug}", json=extra, headers=admin_headers
        )
        assert r.status_code == 422, (extra, r.text)
    stored = product_row(slug)
    assert stored["is_enabled"] is False
    assert stored["allowed_purposes"] == ["engagement"]


def test_an_empty_or_impossible_edit_is_refused(client, admin_headers):
    slug = register_product(client, admin_headers)
    for payload in (
        {},
        {"name": None},
        {"name": ""},
        {"rate_limit_per_minute": 0},
        {"rate_limit_per_minute": None},
    ):
        r = client.patch(
            f"{API}/admin/qcp/products/{slug}", json=payload, headers=admin_headers
        )
        assert r.status_code == 422, (payload, r.text)


def test_editing_an_unknown_product_is_a_404_not_a_create(client, admin_headers):
    r = client.patch(
        f"{API}/admin/qcp/products/not_a_real_product",
        json={"name": "Ghost"},
        headers=admin_headers,
    )
    assert r.status_code == 404
    with SessionLocal() as db:
        assert (
            db.query(WhatsAppProduct)
            .filter(WhatsAppProduct.slug == "not_a_real_product")
            .first()
            is None
        )


def test_a_rejected_edit_never_echoes_what_was_rejected(client, admin_headers):
    """The refusal path of a new route is a disclosure path like any other."""
    slug = register_product(client, admin_headers)
    r = client.patch(
        f"{API}/admin/qcp/products/{slug}",
        json={"name": "Fine", "access_token": TOKEN},
        headers=admin_headers,
    )
    assert r.status_code == 422, r.text
    assert TOKEN not in r.text
    assert TOKEN[:8] not in r.text


# ---------------------------------------------------------------------------
# Products — API keys
# ---------------------------------------------------------------------------

def test_a_minted_key_is_shown_once_and_stored_only_as_a_hash(
    client, admin_headers, admin_user_id
):
    slug = register_product(client, admin_headers)
    r = client.post(f"{API}/admin/qcp/products/{slug}/api-key", headers=admin_headers)
    assert r.status_code == 201, r.text
    body = r.json()
    plaintext = body["api_key"]
    assert plaintext.startswith("qcp_")
    assert body["shown_once"] is True

    stored = product_row(slug)
    assert stored["api_key_hash"] == hashlib.sha256(plaintext.encode()).hexdigest()
    assert plaintext not in stored["api_key_hash"]
    # The display prefix is a digest fragment, not the head of the key.
    assert stored["api_key_prefix"] not in plaintext

    # And it is never obtainable again.
    listing = client.get(f"{API}/admin/qcp/products", headers=admin_headers)
    assert plaintext not in listing.text
    item = {p["slug"]: p for p in listing.json()["items"]}[slug]
    assert item["has_api_key"] is True

    rows = audit_rows("product.api_key_minted", resource_id=slug)
    assert rows and rows[0]["actor_id"] == admin_user_id
    assert plaintext not in str(rows[0]["details"])


def test_rotating_a_key_retires_the_old_one_at_the_gateway(client, admin_headers):
    """Proved at the gateway, not just in the column.

    ``require_signature`` is on by default, so a *valid* key still gets a 401
    — but a different one: "Missing request signature" means the key
    authenticated, "Invalid QCP credentials" means it did not. That is what
    separates a retired key from a live one here.
    """
    slug = register_product(client, admin_headers)
    first = client.post(
        f"{API}/admin/qcp/products/{slug}/api-key", headers=admin_headers
    ).json()["api_key"]

    def gateway(key):
        return client.get(
            f"{API}/whatsapp/health", headers={"X-QCP-Product": slug, "X-QCP-Key": key}
        ).json()["detail"]

    assert gateway(first) == "Missing request signature"

    second = client.post(
        f"{API}/admin/qcp/products/{slug}/api-key", headers=admin_headers
    ).json()["api_key"]
    assert second != first
    assert gateway(first) == "Invalid QCP credentials"
    assert gateway(second) == "Missing request signature"
    assert audit_rows("product.api_key_rotated", resource_id=slug)


def test_a_revoked_key_leaves_the_product_unable_to_authenticate(
    client, admin_headers
):
    slug = register_product(client, admin_headers)
    key = client.post(
        f"{API}/admin/qcp/products/{slug}/api-key", headers=admin_headers
    ).json()["api_key"]

    r = client.delete(f"{API}/admin/qcp/products/{slug}/api-key", headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.json()["has_api_key"] is False
    # An empty hash is an explicit denial: no sha256 hex digest equals "".
    assert product_row(slug)["api_key_hash"] == ""
    assert (
        client.get(
            f"{API}/whatsapp/health", headers={"X-QCP-Product": slug, "X-QCP-Key": key}
        ).json()["detail"]
        == "Invalid QCP credentials"
    )
    # And an empty presented key cannot match the empty stored one either.
    assert (
        client.get(
            f"{API}/whatsapp/health", headers={"X-QCP-Product": slug, "X-QCP-Key": ""}
        ).json()["detail"]
        == "Invalid QCP credentials"
    )
    assert audit_rows("product.api_key_revoked", resource_id=slug)


def test_revoking_a_key_disables_the_product_it_belonged_to(client, admin_headers):
    """A product left enabled with no key is a lie the console would show."""
    slug = register_product(client, admin_headers)
    client.post(f"{API}/admin/qcp/products/{slug}/api-key", headers=admin_headers)
    assert (
        client.post(f"{API}/admin/qcp/products/{slug}/enable", headers=admin_headers).status_code
        == 200
    )
    client.delete(f"{API}/admin/qcp/products/{slug}/api-key", headers=admin_headers)
    assert product_row(slug)["is_enabled"] is False


# ---------------------------------------------------------------------------
# Products — enable/disable
# ---------------------------------------------------------------------------

def test_a_keyless_product_cannot_be_enabled(client, admin_headers):
    slug = register_product(client, admin_headers)
    r = client.post(f"{API}/admin/qcp/products/{slug}/enable", headers=admin_headers)
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["reason"] == "no_api_key"
    assert product_row(slug)["is_enabled"] is False


def test_enabling_and_disabling_a_product_is_audited(
    client, admin_headers, admin_user_id
):
    slug = register_product(client, admin_headers)
    client.post(f"{API}/admin/qcp/products/{slug}/api-key", headers=admin_headers)

    r = client.post(f"{API}/admin/qcp/products/{slug}/enable", headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.json()["is_enabled"] is True
    rows = audit_rows("product.enabled", resource_id=slug)
    assert rows and rows[0]["actor_id"] == admin_user_id

    r = client.post(f"{API}/admin/qcp/products/{slug}/disable", headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.json()["is_enabled"] is False
    assert audit_rows("product.disabled", resource_id=slug)


# ---------------------------------------------------------------------------
# Products — purposes
# ---------------------------------------------------------------------------

def test_the_ordinary_purposes_route_refuses_to_grant_authentication(
    client, admin_headers
):
    slug = register_product(client, admin_headers)
    r = client.put(
        f"{API}/admin/qcp/products/{slug}/purposes",
        json={"purposes": ["engagement", "authentication"]},
        headers=admin_headers,
    )
    assert r.status_code == 409, r.text
    detail = r.json()["detail"]
    assert detail["reason"] == "authentication_grant_requires_dedicated_action"
    # Actionable: it says where to go instead.
    assert "purposes/authentication" in detail["message"]
    assert product_row(slug)["allowed_purposes"] == ["engagement"]

    denials = audit_rows("product.authentication_grant_denied", resource_id=slug)
    assert denials and denials[0]["outcome"] == "denied"


def test_granting_authentication_is_a_distinct_justified_audited_action(
    client, admin_headers, admin_user_id
):
    slug = register_product(client, admin_headers)
    r = client.post(
        f"{API}/admin/qcp/products/{slug}/purposes/authentication",
        json={"justification": "owns an OTP path, signed off by the CTO"},
        headers=admin_headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "authentication" in body["allowed_purposes"]
    assert body["may_reach_authentication"] is True
    assert sorted(product_row(slug)["allowed_purposes"]) == [
        "authentication",
        "engagement",
    ]

    rows = audit_rows("product.authentication_granted", resource_id=slug)
    assert rows and rows[0]["actor_id"] == admin_user_id
    assert rows[0]["details"]["justification"].startswith("owns an OTP path")

    # Revoking is the safe direction, so it needs no ceremony — but it is
    # still audited.
    r = client.put(
        f"{API}/admin/qcp/products/{slug}/purposes",
        json={"purposes": ["engagement"]},
        headers=admin_headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["allowed_purposes"] == ["engagement"]
    assert audit_rows("product.authentication_revoked", resource_id=slug)


def test_granting_authentication_without_a_justification_is_refused(
    client, admin_headers
):
    slug = register_product(client, admin_headers)
    for payload in ({}, {"justification": "  "}, {"justification": "why"}):
        r = client.post(
            f"{API}/admin/qcp/products/{slug}/purposes/authentication",
            json=payload,
            headers=admin_headers,
        )
        assert r.status_code == 422, (payload, r.text)
    assert product_row(slug)["allowed_purposes"] == ["engagement"]


# ---------------------------------------------------------------------------
# Conversations — reassigning an unattributed inbound
# ---------------------------------------------------------------------------

@pytest.fixture
def unattributed(world):
    """A thread ingest could not attribute, with one orphan inbound message.

    This is the state ``attribute_inbound`` deliberately produces for an
    ambiguous reply: a real customer message that belongs to nobody.
    """
    def _make(account_slug: str):
        phone = "+2376" + uuid.uuid4().hex[:8].translate(
            str.maketrans("abcdef", "012345")
        )
        with SessionLocal() as db:
            account = (
                db.query(WhatsAppAccount)
                .filter(WhatsAppAccount.slug == account_slug)
                .one()
            )
            conversation = WhatsAppConversation(
                account_id=account.id,
                product_id=None,
                wa_contact_id=phone.lstrip("+"),
                phone_e164=phone,
                display_name="Unattributed customer",
                state="open",
            )
            db.add(conversation)
            db.flush()
            db.add(
                WhatsAppMessage(
                    message_uid=uuid.uuid4().hex,
                    account_id=account.id,
                    account_purpose=account.purpose,
                    conversation_id=conversation.id,
                    product_id=None,
                    direction="inbound",
                    kind="text",
                    status="delivered",
                    from_phone_e164=phone,
                    body="is my order coming?",
                )
            )
            db.commit()
            return conversation.id

    return _make


def _enabled_product(client, admin_headers) -> str:
    slug = register_product(client, admin_headers)
    client.post(f"{API}/admin/qcp/products/{slug}/api-key", headers=admin_headers)
    client.post(f"{API}/admin/qcp/products/{slug}/enable", headers=admin_headers)
    return slug


def test_an_unattributed_conversation_can_be_handed_to_a_product(
    client, admin_headers, world, unattributed, admin_user_id
):
    conversation_id = unattributed(world["quata"])
    slug = _enabled_product(client, admin_headers)

    r = client.post(
        f"{API}/admin/qcp/conversations/{conversation_id}/reassign",
        json={"product": slug, "reason": "customer named their food order"},
        headers=admin_headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["product"] == slug
    # The orphan inbound is handed over too — a thread whose messages stay
    # unattributed reads as empty to the product that was just given it.
    assert body["messages_attributed"] == 1

    with SessionLocal() as db:
        row = db.get(WhatsAppConversation, conversation_id)
        product_id = product_row(slug)["id"]
        assert row.product_id == product_id
        orphans = (
            db.query(WhatsAppMessage)
            .filter(
                WhatsAppMessage.conversation_id == conversation_id,
                WhatsAppMessage.product_id.is_(None),
            )
            .count()
        )
        assert orphans == 0

    rows = audit_rows("conversation.reassigned", resource_id=conversation_id)
    assert rows and rows[0]["actor_id"] == admin_user_id


def test_an_already_attributed_conversation_is_never_taken_from_its_owner(
    client, admin_headers, world, unattributed
):
    conversation_id = unattributed(world["quata"])
    first = _enabled_product(client, admin_headers)
    second = _enabled_product(client, admin_headers)
    client.post(
        f"{API}/admin/qcp/conversations/{conversation_id}/reassign",
        json={"product": first},
        headers=admin_headers,
    )

    r = client.post(
        f"{API}/admin/qcp/conversations/{conversation_id}/reassign",
        json={"product": second},
        headers=admin_headers,
    )
    assert r.status_code == 409, r.text
    detail = r.json()["detail"]
    assert detail["reason"] == "already_attributed"
    assert detail["conflict"] == first
    with SessionLocal() as db:
        assert db.get(WhatsAppConversation, conversation_id).product_id == product_row(
            first
        )["id"]


def test_a_verify_thread_cannot_be_handed_to_an_engagement_only_product(
    client, admin_headers, world, unattributed
):
    """The separation, carried into the one route that assigns ownership."""
    conversation_id = unattributed(world["verify"])
    slug = _enabled_product(client, admin_headers)  # engagement-only

    r = client.post(
        f"{API}/admin/qcp/conversations/{conversation_id}/reassign",
        json={"product": slug},
        headers=admin_headers,
    )
    assert r.status_code == 409, r.text
    detail = r.json()["detail"]
    assert detail["reason"] == "purpose_not_permitted"
    assert detail["purpose"] == "authentication"
    with SessionLocal() as db:
        assert db.get(WhatsAppConversation, conversation_id).product_id is None
    assert audit_rows("conversation.reassign_denied", resource_id=conversation_id)


def test_a_disabled_product_cannot_be_handed_a_customer(
    client, admin_headers, world, unattributed
):
    """It could not read the thread, so the customer stays unanswered."""
    conversation_id = unattributed(world["quata"])
    slug = register_product(client, admin_headers)
    r = client.post(
        f"{API}/admin/qcp/conversations/{conversation_id}/reassign",
        json={"product": slug},
        headers=admin_headers,
    )
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["reason"] == "product_disabled"


def test_reassigning_to_an_unknown_product_or_thread_is_a_404(
    client, admin_headers, world, unattributed
):
    conversation_id = unattributed(world["quata"])
    r = client.post(
        f"{API}/admin/qcp/conversations/{conversation_id}/reassign",
        json={"product": "not_a_real_product"},
        headers=admin_headers,
    )
    assert r.status_code == 404
    r = client.post(
        f"{API}/admin/qcp/conversations/99999999/reassign",
        json={"product": "quatafood"},
        headers=admin_headers,
    )
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# The dormancy guarantee
# ---------------------------------------------------------------------------

def test_nothing_in_this_module_switched_qcp_on(client, admin_headers):
    """Run last by file order: the seeded estate must still be dormant.

    Every route above has been exercised. If any of them touches a seeded
    row, or flips a global gate, this is where it shows.
    """
    body = client.get(f"{API}/admin/qcp/overview", headers=admin_headers).json()
    assert body["gates"]["env_enabled"] is False
    assert body["gates"]["delivery_enabled"] is False

    accounts = {a["slug"]: a for a in body["accounts"]}
    for slug in ("quata_verify", "quata"):
        assert accounts[slug]["is_active"] is False
        assert accounts[slug]["configured"] is False
        assert accounts[slug]["has_access_token"] is False

    products = {p["slug"]: p for p in body["products"]}
    for slug in ("quatapay", "quatafood", "abaqwa", "quatatrade"):
        assert products[slug]["is_enabled"] is False
        assert products[slug]["has_api_key"] is False
    # Least privilege as seeded, untouched by anything above.
    assert products["quatafood"]["allowed_purposes"] == [
        "authentication",
        "engagement",
    ]
    for slug in ("quatapay", "abaqwa", "quatatrade"):
        assert products[slug]["allowed_purposes"] == ["engagement"]
