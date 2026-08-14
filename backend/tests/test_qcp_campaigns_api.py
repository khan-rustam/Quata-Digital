"""The campaigns console surface: what it refuses, and who may do what.

Three things this module pins that the service tests cannot:

* **The permission split.** Drafting, previewing and reading take
  ``settings:manage``; **start** and **schedule** take ``whatsapp:operate``,
  because those put marketing traffic on the number that carries the fleet's
  login codes. **Stop takes the lower one** — anyone who can see a campaign
  can halt it, because a stop button gated behind a permission the person
  watching the disaster does not hold is not a stop button.
* **Ship-inert, over HTTP.** ``POST /start`` on a dormant platform is a
  refusal with a reason code, not a 500 and not a quiet success.
* **No response carries a secret.** Walked from the OpenAPI spec, the same
  way ``test_whatsapp_write_surface_attack`` walks the rest of QCP.

The router is mounted on the real application when ``app/main.py`` includes
it, and on a bare app carrying only this router otherwise — that one line is
outside this change's file ownership and is reported as a delta, and this
fixture is the same one ``test_qcp_agent_api`` uses for the same reason. The
routes are exercised identically either way, so this suite does not quietly
stop testing anything the day the delta lands.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.db.session import SessionLocal, engine
from app.models import Base, Role, User, WhatsAppConversation

from . import whatsapp_world


API = "/api/v1"
CAMPAIGNS = f"{API}/admin/qcp/campaigns"
CAMPAIGN_INTENT = "promo_weekend"


def _now() -> datetime:
    return datetime.now(timezone.utc)


@pytest.fixture(scope="module")
def campaigns_app(admin_token):
    """The app carrying the campaigns router.

    ``admin_token`` first, so the session database exists and is seeded before
    anything here runs.
    """
    from fastapi import FastAPI

    from app.api.routes_admin_campaigns import router as campaigns_router
    from app.core.config import settings
    from app.main import app as real_app

    Base.metadata.create_all(bind=engine)
    # Asked of the OpenAPI spec rather than of ``app.routes``: this FastAPI
    # version keeps an included router as a single opaque entry rather than
    # flattening its routes, so walking ``app.routes`` would report "not
    # mounted" forever and this suite would never switch over when the delta
    # lands.
    mounted = any(
        path.startswith(f"{settings.API_PREFIX}/admin/qcp/campaigns")
        for path in real_app.openapi().get("paths", {})
    )
    if mounted:
        return real_app
    standalone = FastAPI()
    standalone.include_router(campaigns_router, prefix=settings.API_PREFIX)
    return standalone


@pytest.fixture
def client(campaigns_app):
    from fastapi.testclient import TestClient

    with TestClient(campaigns_app) as c:
        yield c


def _make_user(role_slug: str, label: str) -> dict:
    """A real user on a real role, with a token minted directly.

    Minted rather than logged in so this module does not spend the login rate
    limit the whole suite shares.
    """
    from app.core.security import create_access_token, hash_password

    with SessionLocal() as db:
        role = db.query(Role).filter(Role.slug == role_slug).one()
        user = User(
            email=f"cmp_{uuid.uuid4().hex[:10]}@quatadigital.com",
            full_name=f"{label} {uuid.uuid4().hex[:6]}",
            password_hash=hash_password("NotUsed!2026"),
            is_active=True,
            role_id=role.id,
            must_reset_password=False,
            password_changed_at=_now(),
        )
        db.add(user)
        db.commit()
        token = create_access_token(user.id, password_changed_at=user.password_changed_at)
        return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def admin_headers_scoped():
    """An Admin: holds ``settings:manage``, not ``whatsapp:operate``."""
    return _make_user("admin", "Campaign Admin")


@pytest.fixture(scope="module")
def outsider_headers():
    """A Manager: real staff, no QCP entitlement at all."""
    return _make_user("manager", "Outsider")


@pytest.fixture(scope="module")
def world():
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        built = whatsapp_world.build(db)
        yield built
        whatsapp_world.teardown(db, built)


@pytest.fixture
def live(monkeypatch):
    whatsapp_world.enable_delivery(monkeypatch, enabled=True)


@pytest.fixture
def dormant(monkeypatch):
    whatsapp_world.enable_delivery(monkeypatch, enabled=False)


def _tag() -> str:
    return f"a{uuid.uuid4().hex[:6]}"


def _contacts(world, count: int, tag: str) -> list[str]:
    phones = []
    with SessionLocal() as db:
        for i in range(count):
            phone = f"+237{uuid.uuid4().int % 10**9:09d}"
            db.add(
                WhatsAppConversation(
                    account_id=world.quata.id,
                    wa_contact_id=f"wa_{tag}_{i}",
                    phone_e164=phone,
                    state="open",
                    locale=tag,
                    last_inbound_at=_now(),
                )
            )
            phones.append(phone)
        db.commit()
    return phones


def _create(client, headers, world, tag: str, **overrides) -> dict:
    body = {
        "name": "Weekend promo",
        "product": world.product_slug,
        "intent": CAMPAIGN_INTENT,
        "locale": "en",
        "audience_source": "conversations",
        "audience_filters": {"state": "open", "locale": tag},
        "variables": ["50% off"],
        "messages_per_minute": 20,
    }
    body.update(overrides)
    r = client.post(CAMPAIGNS, json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


# ---------------------------------------------------------------------------
# Access
# ---------------------------------------------------------------------------

def test_the_console_surface_is_closed_to_anonymous_callers(client):
    for method, path in (
        ("get", CAMPAIGNS),
        ("post", CAMPAIGNS),
        ("get", f"{CAMPAIGNS}/opt-outs"),
        ("post", f"{CAMPAIGNS}/run-due"),
        ("post", f"{CAMPAIGNS}/audience-preview"),
    ):
        r = (
            client.get(path)
            if method == "get"
            else client.post(path, json={})
        )
        assert r.status_code in (401, 403), (method, path, r.status_code)


def test_a_staff_account_with_no_qcp_entitlement_is_refused(client, outsider_headers):
    r = client.get(CAMPAIGNS, headers=outsider_headers)
    assert r.status_code == 403


def test_starting_a_campaign_needs_the_fleet_permission_not_the_console_one(
    client, admin_headers_scoped, world, live
):
    """``settings:manage`` drafts. It does not put marketing on the number."""
    tag = _tag()
    _contacts(world, 2, tag)
    campaign = _create(client, admin_headers_scoped, world, tag)
    uid = campaign["campaign_uid"]

    built = client.post(f"{CAMPAIGNS}/{uid}/audience", headers=admin_headers_scoped)
    assert built.status_code == 200, built.text
    assert built.json()["size"] == 2

    r = client.post(f"{CAMPAIGNS}/{uid}/start", headers=admin_headers_scoped)
    assert r.status_code == 403, r.text

    scheduled = client.post(
        f"{CAMPAIGNS}/{uid}/schedule",
        json={"scheduled_at": (_now() + timedelta(hours=1)).isoformat()},
        headers=admin_headers_scoped,
    )
    assert scheduled.status_code == 403, scheduled.text


def test_stop_is_available_to_anyone_who_can_see_the_campaign(
    client, admin_headers_scoped, world, live
):
    """The safe direction takes the lower permission. Deliberately."""
    tag = _tag()
    _contacts(world, 2, tag)
    campaign = _create(client, admin_headers_scoped, world, tag)
    uid = campaign["campaign_uid"]
    client.post(f"{CAMPAIGNS}/{uid}/audience", headers=admin_headers_scoped)

    r = client.post(
        f"{CAMPAIGNS}/{uid}/stop", json={"reason": "wrong list"}, headers=admin_headers_scoped
    )
    assert r.status_code == 200, r.text
    assert r.json()["campaign"]["status"] == "stopped"

    # And twice is a 200, not an error.
    again = client.post(f"{CAMPAIGNS}/{uid}/stop", json={}, headers=admin_headers_scoped)
    assert again.status_code == 200
    assert again.json()["already_stopped"] is True


# ---------------------------------------------------------------------------
# Ship inert
# ---------------------------------------------------------------------------

def test_a_campaign_is_created_as_a_draft(client, admin_headers_scoped, world):
    campaign = _create(client, admin_headers_scoped, world, _tag())
    assert campaign["status"] == "draft"
    assert campaign["account_purpose"] == "engagement"
    assert campaign["started_at"] is None
    assert campaign["results"]["sent"] == 0


def test_start_is_refused_while_qcp_is_dormant(
    client, admin_headers, world, dormant
):
    """The super-admin token holds every permission, so this reaches ``start``."""
    tag = _tag()
    _contacts(world, 2, tag)
    campaign = _create(client, admin_headers, world, tag)
    uid = campaign["campaign_uid"]
    client.post(f"{CAMPAIGNS}/{uid}/audience", headers=admin_headers)

    r = client.post(f"{CAMPAIGNS}/{uid}/start", headers=admin_headers)
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["reason"] == "delivery_disabled"

    state = client.get(f"{CAMPAIGNS}/{uid}", headers=admin_headers).json()
    assert state["status"] == "draft"


def test_run_due_sends_nothing_on_a_dormant_platform(client, admin_headers, dormant):
    """The tick is safe to cron on a switched-off install.

    It is asserted as "nothing was handed off", not as "nothing was looked
    at": the tick still *finds* whatever campaigns exist — including any left
    running by another module in this shared session database — and what
    matters is that every one of them is stopped at the dormancy gate and
    paused with the reason, rather than quietly producing suppressed
    messages.
    """
    r = client.post(f"{CAMPAIGNS}/run-due", headers=admin_headers)
    assert r.status_code == 200, r.text
    for entry in r.json()["campaigns"]:
        assert entry.get("queued", 0) == 0, entry
        assert entry.get("paused") == "delivery_disabled" or "skipped" in entry, entry


def test_the_list_reports_why_nothing_can_send(client, admin_headers, dormant):
    """Empty is the normal state. The screen has to be able to say which empty."""
    r = client.get(CAMPAIGNS, headers=admin_headers)
    assert r.status_code == 200, r.text
    platform = r.json()["platform"]
    assert platform["delivery_enabled"] is False
    assert "audience_sources" in platform
    assert platform["max_messages_per_minute"] == 60


# ---------------------------------------------------------------------------
# Refusals
# ---------------------------------------------------------------------------

def test_a_campaign_on_an_intent_routing_to_verify_is_a_409_with_a_reason(
    client, admin_headers, world
):
    r = client.post(
        CAMPAIGNS,
        json={
            "name": "Promo on the OTP number",
            "product": world.product_slug,
            "intent": "promo_on_verify",
            "locale": "en",
            "audience_source": "conversations",
            "audience_filters": {},
            "variables": ["50% off"],
        },
        headers=admin_headers,
    )
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["reason"] == "campaign_must_be_engagement"


def test_the_create_body_has_no_status_and_no_account_field(client, admin_headers, world):
    """Extra fields are forbidden, so an attempt is a 422 rather than ignored."""
    for extra in ({"status": "running"}, {"account": "quata_verify"}):
        r = client.post(
            CAMPAIGNS,
            json={
                "name": "Sneaky",
                "product": world.product_slug,
                "intent": CAMPAIGN_INTENT,
                "audience_source": "conversations",
                "variables": ["x"],
                **extra,
            },
            headers=admin_headers,
        )
        assert r.status_code == 422, (extra, r.text)


def test_an_audience_preview_writes_nothing_and_names_its_opt_outs(
    client, admin_headers, world
):
    tag = _tag()
    phones = _contacts(world, 3, tag)
    client.post(
        f"{CAMPAIGNS}/opt-outs",
        json={"phone_e164": phones[0], "note": "asked on the phone"},
        headers=admin_headers,
    )

    r = client.post(
        f"{CAMPAIGNS}/audience-preview",
        json={
            "product": world.product_slug,
            "audience_source": "conversations",
            "audience_filters": {"state": "open", "locale": tag},
        },
        headers=admin_headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["matched"] == 3
    assert body["opted_out"] == 1
    assert body["eligible"] == 2
    assert phones[0] not in body["sample"]


def test_an_unknown_audience_filter_is_a_stated_refusal(client, admin_headers, world):
    r = client.post(
        f"{CAMPAIGNS}/audience-preview",
        json={
            "product": world.product_slug,
            "audience_source": "conversations",
            "audience_filters": {"inbound_within_day": 30},
        },
        headers=admin_headers,
    )
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["reason"] == "unknown_audience_filter"


def test_there_is_no_route_that_removes_an_opt_out(campaigns_app):
    """Re-consent is not a console button. See ``consent``.

    Asserted at the contract level — the spec, not one route file — so a
    delete that arrived on some other campaigns path would still fail this.
    """
    paths = campaigns_app.openapi()["paths"]
    opt_out_paths = {p for p in paths if "opt-out" in p}
    assert opt_out_paths, "the opt-out routes are not mounted"
    for path in paths:
        if "/qcp/campaigns" not in path:
            continue
        assert "delete" not in paths[path], path


# ---------------------------------------------------------------------------
# No secret ever leaves
# ---------------------------------------------------------------------------

def test_no_campaign_response_schema_declares_a_secret_bearing_field(campaigns_app):
    """Walked from the routes, the same way the rest of QCP's surface is."""
    spec = campaigns_app.openapi()
    schemas = spec.get("components", {}).get("schemas", {}) or {}

    offenders = []
    for path, operations in spec["paths"].items():
        if "/qcp/campaigns" not in path:
            continue
        for operation in operations.values():
            if not isinstance(operation, dict):
                continue
            for name, schema in schemas.items():
                for field in (schema.get("properties") or {}):
                    lowered = field.lower()
                    if any(
                        mark in lowered
                        for mark in ("token", "secret", "password", "api_key", "apikey")
                    ):
                        offenders.append(f"{name}.{field}")
    assert not offenders, f"secret-bearing campaign fields: {sorted(set(offenders))}"
