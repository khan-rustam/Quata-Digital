"""The QCP agent console — what a human support agent actually uses.

QCP's conversation engine has always had the handover verbs (``assign``,
``return_to_ai``) and no surface a human could reach them from. This is that
surface, and what is pinned here is mostly what it *refuses*:

**The AI and the agent console both stop at the Verify number.** The
authentication number carries the fleet's login codes and nothing but
approved authentication templates ever leaves it. An agent replying from the
console is refused on a Verify thread, and refused again if the *intent* they
name routes to the authentication purpose — two independent checks, because
the first one only knows which thread they are on and the second is what
stops an OTP template being addressed from a support conversation.

**A draft is not an answer.** The suggested-reply endpoint returns text an
agent edits and sends; it never sends anything itself, it is off until a
switch is turned on, and it withholds any draft carrying a figure. The
console fetched no product data in the request, so a number in a draft was
invented — and on this fleet an invented balance is worse than no answer.

**Claiming is honest about the race.** Two agents clicking at once must not
both believe they own the thread; the loser is told who holds it.

**No response here carries a staff id.** Products were leaking ``users.id``
through ``assignee_id`` in an earlier round and that was closed. This module
never emits one at all — the console is told ``mine`` and a display name.

Isolation note: ``conftest.py`` runs one SQLite database for the whole
session, so everything here uses unique slugs, and the ``world`` fixture
stands its own numbers down on the way out.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.db.session import SessionLocal
from app.models import (
    Role,
    User,
    WhatsAppAccount,
    WhatsAppAuditLog,
    WhatsAppConversation,
    WhatsAppMessage,
)
from tests import whatsapp_world


API = "/api/v1"
AGENT = f"{API}/admin/qcp/agent"

# Keys that would put an internal staff id on the wire. None may appear
# anywhere in any response from this module.
STAFF_ID_KEYS = {"assignee_id", "agent_id", "user_id", "actor_id", "staff_id"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def agent_app(request):
    """The app carrying the agent router.

    The real application when ``app/main.py`` mounts the router (that one
    line is outside this change's file ownership and is reported as a
    delta), and a bare app carrying only this router otherwise — so the
    routes are exercised identically either way and this suite does not
    quietly stop testing anything the day the delta lands.
    """
    from fastapi import FastAPI

    from app.api.routes_admin_agent import router as agent_router
    from app.core.config import settings
    from app.main import app as real_app

    mounted = any(
        getattr(route, "path", "").startswith(f"{settings.API_PREFIX}/admin/qcp/agent")
        for route in real_app.routes
    )
    if mounted:
        return real_app
    standalone = FastAPI()
    standalone.include_router(agent_router, prefix=settings.API_PREFIX)
    return standalone


@pytest.fixture
def client(agent_app, admin_token):
    """A client for the agent app. ``admin_token`` first, so the session
    database is created and seeded before anything here runs."""
    from fastapi.testclient import TestClient

    with TestClient(agent_app) as c:
        yield c


def _make_user(role_slug: str, label: str) -> tuple[int, dict, str]:
    """A real user on a real role, with a token minted directly.

    Minted rather than logged in so this module does not spend the login
    rate limit the whole suite shares.
    """
    from app.core.security import create_access_token, hash_password

    name = f"{label} {uuid.uuid4().hex[:6]}"
    with SessionLocal() as db:
        role = db.query(Role).filter(Role.slug == role_slug).one()
        user = User(
            email=f"ag_{uuid.uuid4().hex[:10]}@quatadigital.com",
            full_name=name,
            password_hash=hash_password("NotUsed!2026"),
            is_active=True,
            role_id=role.id,
            must_reset_password=False,
            password_changed_at=_now(),
        )
        db.add(user)
        db.commit()
        token = create_access_token(user.id, password_changed_at=user.password_changed_at)
        return user.id, {"Authorization": f"Bearer {token}"}, name


@pytest.fixture(scope="module")
def agent_a():
    """An Admin — holds ``settings:manage``, which is one of the three
    entitlements ``conversations.assign`` accepts."""
    return _make_user("admin", "Agent A")


@pytest.fixture(scope="module")
def agent_b():
    return _make_user("admin", "Agent B")


@pytest.fixture(scope="module")
def outsider():
    """A Manager: a real staff account with no WhatsApp entitlement at all."""
    return _make_user("manager", "Outsider")


@pytest.fixture(scope="module")
def world():
    with SessionLocal() as db:
        built = whatsapp_world.build(db)
        yield built
        whatsapp_world.teardown(db, built)


def _conversation(
    world,
    *,
    verify: bool = False,
    inbound_minutes_ago: int | None = 10,
    product: bool = True,
    assignee_id: int | None = None,
    state: str = "open",
) -> int:
    with SessionLocal() as db:
        last_inbound = (
            _now() - timedelta(minutes=inbound_minutes_ago)
            if inbound_minutes_ago is not None
            else None
        )
        row = WhatsAppConversation(
            account_id=world.verify.id if verify else world.quata.id,
            product_id=world.product.id if product else None,
            wa_contact_id=uuid.uuid4().hex[:20],
            phone_e164=f"+2376{uuid.uuid4().int % 10**8:08d}",
            display_name="Test Customer",
            state=state,
            assignee_id=assignee_id,
            unread_count=1,
            locale="en",
            last_inbound_at=last_inbound,
            service_window_expires_at=(
                last_inbound + timedelta(hours=24) if last_inbound else None
            ),
            meta={},
        )
        db.add(row)
        db.commit()
        return row.id


def _audit(action: str, resource_id) -> list[WhatsAppAuditLog]:
    with SessionLocal() as db:
        return (
            db.query(WhatsAppAuditLog)
            .filter(
                WhatsAppAuditLog.action == action,
                WhatsAppAuditLog.resource_id == str(resource_id),
            )
            .all()
        )


def _messages(conversation_id: int) -> list[WhatsAppMessage]:
    with SessionLocal() as db:
        return (
            db.query(WhatsAppMessage)
            .filter(WhatsAppMessage.conversation_id == conversation_id)
            .order_by(WhatsAppMessage.id)
            .all()
        )


def _keys(node, found: set) -> set:
    if isinstance(node, dict):
        for key, value in node.items():
            found.add(key)
            _keys(value, found)
    elif isinstance(node, list):
        for item in node:
            _keys(item, found)
    return found


def _claim(client, conversation_id: int, headers) -> None:
    r = client.post(f"{AGENT}/conversations/{conversation_id}/claim", headers=headers)
    assert r.status_code == 200, r.text


# ---------------------------------------------------------------------------
# Authentication and entitlement
# ---------------------------------------------------------------------------

ROUTES = [
    ("get", "/queue"),
    ("get", "/queue/unassigned"),
    ("post", "/conversations/1/claim"),
    ("post", "/conversations/1/release"),
    ("post", "/conversations/1/reply"),
    ("post", "/conversations/1/return-to-ai"),
    ("get", "/conversations/1/thread"),
    ("post", "/conversations/1/suggest"),
]


@pytest.mark.parametrize("method,path", ROUTES)
def test_every_agent_route_requires_authentication(client, method, path):
    assert getattr(client, method)(f"{AGENT}{path}").status_code == 401


@pytest.mark.parametrize("method,path", ROUTES)
def test_a_staff_account_without_the_entitlement_is_refused(
    client, outsider, method, path
):
    """A Manager is a real, active staff account. The agent console is not
    "any logged-in employee" — it answers customers on the fleet's number."""
    _uid, headers, _name = outsider
    assert getattr(client, method)(f"{AGENT}{path}", headers=headers).status_code == 403


def test_the_super_admin_wildcard_is_not_an_agent_entitlement(
    client, world, admin_headers
):
    """``conversations._is_whatsapp_agent`` deliberately does not honour
    ``*``. The console must say so rather than 500 or park a customer on
    somebody who was never entitled to answer."""
    conversation_id = _conversation(world)
    r = client.post(f"{AGENT}/conversations/{conversation_id}/claim", headers=admin_headers)
    assert r.status_code == 403, r.text
    assert r.json()["detail"]["reason"] == "not_a_whatsapp_agent"
    with SessionLocal() as db:
        assert db.get(WhatsAppConversation, conversation_id).assignee_id is None


# ---------------------------------------------------------------------------
# The queues
# ---------------------------------------------------------------------------

def test_the_unassigned_queue_is_oldest_first_and_says_how_long(client, world, agent_a):
    """A queue sorted newest-first buries the customer who has waited
    longest, which is the one person a support queue exists for."""
    _uid, headers, _name = agent_a
    oldest = _conversation(world, inbound_minutes_ago=240)
    middle = _conversation(world, inbound_minutes_ago=90)
    newest = _conversation(world, inbound_minutes_ago=5)

    r = client.get(f"{AGENT}/queue/unassigned", headers=headers)
    assert r.status_code == 200, r.text
    order = [item["conversation_id"] for item in r.json()["items"]]
    assert order.index(oldest) < order.index(middle) < order.index(newest)

    by_id = {item["conversation_id"]: item for item in r.json()["items"]}
    assert by_id[oldest]["waiting_seconds"] > by_id[newest]["waiting_seconds"]
    assert by_id[oldest]["waiting_seconds"] >= 240 * 60 - 120


def test_my_queue_holds_only_my_threads_oldest_first(client, world, agent_a, agent_b):
    _uid_a, headers_a, _ = agent_a
    _uid_b, headers_b, _ = agent_b
    older = _conversation(world, inbound_minutes_ago=180)
    newer = _conversation(world, inbound_minutes_ago=20)
    theirs = _conversation(world, inbound_minutes_ago=60)
    _claim(client, older, headers_a)
    _claim(client, newer, headers_a)
    _claim(client, theirs, headers_b)

    mine = [i["conversation_id"] for i in client.get(f"{AGENT}/queue", headers=headers_a).json()["items"]]
    assert theirs not in mine
    assert mine.index(older) < mine.index(newer)

    # And they are gone from the unassigned queue.
    waiting = [
        i["conversation_id"]
        for i in client.get(f"{AGENT}/queue/unassigned", headers=headers_a).json()["items"]
    ]
    assert older not in waiting and newer not in waiting and theirs not in waiting


def test_no_agent_response_carries_a_staff_id(client, world, agent_a):
    _uid, headers, _name = agent_a
    conversation_id = _conversation(world)
    _claim(client, conversation_id, headers)
    documents = [
        client.get(f"{AGENT}/queue", headers=headers).json(),
        client.get(f"{AGENT}/queue/unassigned", headers=headers).json(),
        client.get(f"{AGENT}/conversations/{conversation_id}/thread", headers=headers).json(),
        client.post(f"{AGENT}/conversations/{conversation_id}/release", headers=headers).json(),
    ]
    for document in documents:
        leaked = STAFF_ID_KEYS & _keys(document, set())
        assert not leaked, f"agent console emitted a staff id: {leaked}"


# ---------------------------------------------------------------------------
# Claim / release
# ---------------------------------------------------------------------------

def test_two_agents_claiming_at_once_do_not_both_own_it(
    client, world, agent_a, agent_b
):
    _uid_a, headers_a, name_a = agent_a
    _uid_b, headers_b, _name_b = agent_b
    conversation_id = _conversation(world)

    first = client.post(f"{AGENT}/conversations/{conversation_id}/claim", headers=headers_a)
    assert first.status_code == 200, first.text
    assert first.json()["mine"] is True

    second = client.post(f"{AGENT}/conversations/{conversation_id}/claim", headers=headers_b)
    assert second.status_code == 409, second.text
    body = second.json()["detail"]
    assert body["reason"] == "already_claimed"
    assert body["held_by"] == name_a

    with SessionLocal() as db:
        assert db.get(WhatsAppConversation, conversation_id).assignee_id == _uid_a
    assert _audit("agent.claimed", conversation_id)
    assert _audit("agent.claim_denied", conversation_id)


def test_reclaiming_my_own_thread_is_idempotent(client, world, agent_a):
    _uid, headers, _name = agent_a
    conversation_id = _conversation(world)
    _claim(client, conversation_id, headers)
    again = client.post(f"{AGENT}/conversations/{conversation_id}/claim", headers=headers)
    assert again.status_code == 200
    assert again.json()["mine"] is True
    assert again.json()["already_mine"] is True


def test_release_returns_the_thread_to_the_waiting_queue(client, world, agent_a):
    _uid, headers, _name = agent_a
    conversation_id = _conversation(world)
    _claim(client, conversation_id, headers)
    r = client.post(f"{AGENT}/conversations/{conversation_id}/release", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["mine"] is False
    waiting = [
        i["conversation_id"]
        for i in client.get(f"{AGENT}/queue/unassigned", headers=headers).json()["items"]
    ]
    assert conversation_id in waiting
    assert _audit("agent.released", conversation_id)


def test_releasing_a_thread_i_do_not_hold_is_refused(client, world, agent_a, agent_b):
    _uid_a, headers_a, _ = agent_a
    _uid_b, headers_b, _ = agent_b
    conversation_id = _conversation(world)
    _claim(client, conversation_id, headers_a)
    r = client.post(f"{AGENT}/conversations/{conversation_id}/release", headers=headers_b)
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["reason"] == "not_your_conversation"
    with SessionLocal() as db:
        assert db.get(WhatsAppConversation, conversation_id).assignee_id == _uid_a


# ---------------------------------------------------------------------------
# Replying — through the existing gateway, never around it
# ---------------------------------------------------------------------------

def test_a_reply_goes_through_the_gateway_and_is_audited(client, world, agent_a):
    """QCP is dormant, so the gateway suppresses the send — and that is the
    point: the agent console reaches Meta only through the same choke point
    every product does, so it inherits every one of its refusals."""
    _uid, headers, name = agent_a
    conversation_id = _conversation(world)
    _claim(client, conversation_id, headers)

    r = client.post(
        f"{AGENT}/conversations/{conversation_id}/reply",
        json={"kind": "text", "body": "Bonjour, how can we help?"},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["message_uid"]
    assert body["status"] == "suppressed"
    assert body["reason"] == "delivery_disabled"
    assert body["sent_by"] == name

    rows = _messages(conversation_id)
    assert len(rows) == 1
    assert rows[0].direction == "outbound"
    assert rows[0].account_purpose == "engagement"
    assert _audit("agent.reply_sent", body["message_uid"])


def test_two_different_replies_in_a_row_both_land(client, world, agent_a):
    """The gateway's derived idempotency key buckets by five minutes and a
    free-form send carries no template or variables to tell two apart, so an
    agent's second sentence would be swallowed as a duplicate."""
    _uid, headers, _name = agent_a
    conversation_id = _conversation(world)
    _claim(client, conversation_id, headers)
    first = client.post(
        f"{AGENT}/conversations/{conversation_id}/reply",
        json={"kind": "text", "body": "One moment please."},
        headers=headers,
    ).json()
    second = client.post(
        f"{AGENT}/conversations/{conversation_id}/reply",
        json={"kind": "text", "body": "Thank you for waiting."},
        headers=headers,
    ).json()
    assert first["message_uid"] != second["message_uid"]
    assert second["duplicate"] is False
    assert len(_messages(conversation_id)) == 2


def test_free_form_outside_the_service_window_is_refused(client, world, agent_a):
    _uid, headers, _name = agent_a
    conversation_id = _conversation(world, inbound_minutes_ago=60 * 30)
    _claim(client, conversation_id, headers)
    r = client.post(
        f"{AGENT}/conversations/{conversation_id}/reply",
        json={"kind": "text", "body": "Sorry for the delay."},
        headers=headers,
    )
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["reason"] == "outside_service_window"
    assert _messages(conversation_id) == []
    assert _audit("agent.reply_denied", conversation_id)


def test_a_template_may_still_go_out_after_the_window_closes(client, world, agent_a):
    _uid, headers, _name = agent_a
    conversation_id = _conversation(world, inbound_minutes_ago=60 * 30)
    _claim(client, conversation_id, headers)
    r = client.post(
        f"{AGENT}/conversations/{conversation_id}/reply",
        json={
            "kind": "template",
            "intent": "order_dispatched",
            "variables": ["A-1001", "18:00"],
        },
        headers=headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["message_uid"]
    assert _messages(conversation_id)


def test_the_agent_console_never_replies_on_the_verify_number(client, world, agent_a):
    """Not one message. The Verify number carries the fleet's login codes."""
    _uid, headers, _name = agent_a
    conversation_id = _conversation(world, verify=True)
    _claim(client, conversation_id, headers)
    for payload in (
        {"kind": "text", "body": "Hello"},
        {"kind": "template", "intent": "login_otp", "variables": ["123456"]},
    ):
        r = client.post(
            f"{AGENT}/conversations/{conversation_id}/reply", json=payload, headers=headers
        )
        assert r.status_code == 403, r.text
        assert r.json()["detail"]["reason"] == "verify_number_not_agent_answerable"
    assert _messages(conversation_id) == []
    assert _audit("agent.reply_denied", conversation_id)


def test_an_authentication_intent_is_refused_from_an_engagement_thread(
    client, world, agent_a
):
    """The second, independent check. The thread is on QUATA, so the check
    above passes — but ``promo_on_verify`` is a routing rule whose purpose is
    ``authentication``, so the send would resolve onto the Verify number."""
    _uid, headers, _name = agent_a
    conversation_id = _conversation(world)
    _claim(client, conversation_id, headers)
    r = client.post(
        f"{AGENT}/conversations/{conversation_id}/reply",
        json={"kind": "template", "intent": "promo_on_verify", "variables": ["x"]},
        headers=headers,
    )
    assert r.status_code == 403, r.text
    assert r.json()["detail"]["reason"] == "authentication_intent_forbidden"
    assert _messages(conversation_id) == []


def test_replying_to_a_thread_i_do_not_hold_is_refused(client, world, agent_a, agent_b):
    _uid_a, headers_a, _ = agent_a
    _uid_b, headers_b, _ = agent_b
    conversation_id = _conversation(world)
    _claim(client, conversation_id, headers_a)
    r = client.post(
        f"{AGENT}/conversations/{conversation_id}/reply",
        json={"kind": "text", "body": "I will take this one."},
        headers=headers_b,
    )
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["reason"] == "not_your_conversation"
    assert _messages(conversation_id) == []


def test_an_unattributed_thread_cannot_be_answered_yet(client, world, agent_a):
    """Ingest leaves an ambiguous inbound owned by nobody. There is no
    product to send as, and guessing one is exactly what attribution
    refuses to do."""
    _uid, headers, _name = agent_a
    conversation_id = _conversation(world, product=False)
    _claim(client, conversation_id, headers)
    r = client.post(
        f"{AGENT}/conversations/{conversation_id}/reply",
        json={"kind": "text", "body": "Hello"},
        headers=headers,
    )
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["reason"] == "conversation_unattributed"
    assert _messages(conversation_id) == []


# ---------------------------------------------------------------------------
# The thread
# ---------------------------------------------------------------------------

def test_the_thread_says_who_said_what(client, world, agent_a):
    """An agent picking a thread up mid-conversation must be able to see
    what the bot already told this person, or they will contradict it."""
    _uid, headers, name = agent_a
    conversation_id = _conversation(world)
    _claim(client, conversation_id, headers)

    with SessionLocal() as db:
        db.add(
            WhatsAppMessage(
                message_uid=uuid.uuid4().hex,
                account_id=world.quata.id,
                account_purpose="engagement",
                conversation_id=conversation_id,
                product_id=world.product.id,
                direction="inbound",
                kind="text",
                body="Where is my order?",
                status="delivered",
            )
        )
        ai_uid = uuid.uuid4().hex
        db.add(
            WhatsAppMessage(
                message_uid=ai_uid,
                account_id=world.quata.id,
                account_purpose="engagement",
                conversation_id=conversation_id,
                product_id=world.product.id,
                direction="outbound",
                kind="text",
                body="It is on the way.",
                status="sent",
            )
        )
        db.flush()
        # The AI layer's authorship seam: an audit row under an ``ai.``
        # action naming the message it wrote.
        db.add(
            WhatsAppAuditLog(
                action="ai.reply_sent",
                resource_type="whatsapp_message",
                resource_id=ai_uid,
                outcome="ok",
                details={"model": "gpt-test", "prompt_version": "qcp-support-v1"},
            )
        )
        db.commit()

    reply = client.post(
        f"{AGENT}/conversations/{conversation_id}/reply",
        json={"kind": "text", "body": "Checking that for you now."},
        headers=headers,
    ).json()

    thread = client.get(f"{AGENT}/conversations/{conversation_id}/thread", headers=headers)
    assert thread.status_code == 200, thread.text
    by_uid = {m["message_uid"]: m for m in thread.json()["messages"]}
    assert by_uid[ai_uid]["author"] == "ai"
    assert by_uid[reply["message_uid"]]["author"] == "agent"
    assert by_uid[reply["message_uid"]]["author_label"] == name
    inbound = [m for m in thread.json()["messages"] if m["direction"] == "inbound"]
    assert inbound and all(m["author"] == "customer" for m in inbound)


# ---------------------------------------------------------------------------
# The suggested reply
# ---------------------------------------------------------------------------

def _install_ai(monkeypatch, suggest=None):
    """Stand a stub in front of the documented seam — the package facade.

    The console reads one name off ``app.services.whatsapp`` rather than
    importing an AI submodule, because nothing outside that package may
    reach past the facade (``test_whatsapp_boundaries``). Patching the same
    name here is therefore the real path, and ``suggest=None`` — the name
    present but not callable — is exactly the "no AI layer installed" state,
    deterministic whether or not one has landed.
    """
    import app.api.routes_admin_agent as routes
    from app.services import whatsapp as qcp

    calls: list = []

    def _suggest(db, conversation, *, messages):
        calls.append(conversation.id)
        return suggest(db, conversation, messages=messages)

    monkeypatch.setattr(
        qcp, routes.AI_FACADE_ATTR, _suggest if suggest else None, raising=False
    )
    return calls


def _enable_suggestions(monkeypatch, *, enabled: bool = True) -> None:
    import app.api.routes_admin_agent as routes
    from app.services import site_settings

    monkeypatch.setattr(
        site_settings,
        "get_setting",
        lambda key, default=None, **kw: (
            "true" if key == routes.KEY_AI_SUGGESTIONS_ENABLED and enabled else default
        ),
    )
    site_settings.invalidate_cache()


def test_suggestions_are_off_until_their_own_switch_is_on(client, world, agent_a):
    """Ships inert. The AI drafts nothing until an operator says so."""
    _uid, headers, _name = agent_a
    conversation_id = _conversation(world)
    _claim(client, conversation_id, headers)
    r = client.post(f"{AGENT}/conversations/{conversation_id}/suggest", headers=headers)
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["reason"] == "ai_suggestions_disabled"
    assert _audit("agent.suggestion_denied", conversation_id)


def test_with_no_ai_layer_installed_the_console_invents_nothing(
    client, world, agent_a, monkeypatch
):
    _uid, headers, _name = agent_a
    conversation_id = _conversation(world)
    _claim(client, conversation_id, headers)
    _enable_suggestions(monkeypatch)
    _install_ai(monkeypatch, suggest=None)
    r = client.post(f"{AGENT}/conversations/{conversation_id}/suggest", headers=headers)
    assert r.status_code == 503, r.text
    assert r.json()["detail"]["reason"] == "ai_unavailable"


def test_a_draft_is_returned_with_its_model_and_prompt_version(
    client, world, agent_a, monkeypatch
):
    _uid, headers, _name = agent_a
    conversation_id = _conversation(world)
    _claim(client, conversation_id, headers)
    _enable_suggestions(monkeypatch)
    _install_ai(
        monkeypatch,
        suggest=lambda db, conversation, *, messages: {
            "text": "Thanks for reaching out — an agent is checking your order now.",
            "model": "gpt-test",
            "prompt_version": "qcp-support-v1",
            "escalate": False,
            "reason": "general_enquiry",
        },
    )
    r = client.post(f"{AGENT}/conversations/{conversation_id}/suggest", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["draft"].startswith("Thanks for reaching out")
    assert body["model"] == "gpt-test"
    assert body["prompt_version"] == "qcp-support-v1"
    assert body["auto_sent"] is False
    assert _messages(conversation_id) == []

    rows = _audit("agent.suggestion_served", conversation_id)
    assert rows, "every AI draft is audited"
    details = rows[-1].details or {}
    assert details["model"] == "gpt-test"
    assert details["prompt_version"] == "qcp-support-v1"
    assert details["decision"] == "answered"
    assert details["reason"] == "general_enquiry"


def test_a_decision_object_is_accepted_and_fails_closed(
    client, world, agent_a, monkeypatch
):
    """The AI layer answers with a decision object, not a dict, and this
    console reads it as it stands. An action that is not "reply" — silent,
    refused, anything unrecognised — escalates: rendering the text attached
    to a decision the AI declined to send would undo it."""
    from dataclasses import dataclass

    @dataclass
    class _Decision:
        action: str
        reason: str
        text: str | None
        model: str
        prompt_version: str
        must_escalate: bool

    _uid, headers, _name = agent_a
    conversation_id = _conversation(world)
    _claim(client, conversation_id, headers)
    _enable_suggestions(monkeypatch)

    _install_ai(
        monkeypatch,
        suggest=lambda db, conversation, *, messages: _Decision(
            action="reply",
            reason="order_status",
            text="Your order is being prepared now.",
            model="gpt-test",
            prompt_version="qcp-support-2026-08-a",
            must_escalate=False,
        ),
    )
    served = client.post(f"{AGENT}/conversations/{conversation_id}/suggest", headers=headers)
    assert served.status_code == 200, served.text
    assert served.json()["draft"] == "Your order is being prepared now."
    assert served.json()["prompt_version"] == "qcp-support-2026-08-a"

    _install_ai(
        monkeypatch,
        suggest=lambda db, conversation, *, messages: _Decision(
            action="silent",
            reason="ai_disabled",
            text="Something the AI decided not to say.",
            model="gpt-test",
            prompt_version="qcp-support-2026-08-a",
            must_escalate=False,
        ),
    )
    withheld = client.post(f"{AGENT}/conversations/{conversation_id}/suggest", headers=headers)
    assert withheld.status_code == 200, withheld.text
    assert withheld.json()["draft"] is None
    assert withheld.json()["escalate"] is True
    assert "decided not to say" not in withheld.text


def test_a_draft_carrying_a_figure_is_withheld(client, world, agent_a, monkeypatch):
    """No product API was called in this request, so a number in the draft
    was invented. On this fleet that is worse than no answer."""
    _uid, headers, _name = agent_a
    conversation_id = _conversation(world)
    _claim(client, conversation_id, headers)
    _enable_suggestions(monkeypatch)
    _install_ai(
        monkeypatch,
        suggest=lambda db, conversation, *, messages: {
            "text": "Your balance is 12,500 FCFA and the refund was sent.",
            "model": "gpt-test",
            "prompt_version": "qcp-support-v1",
            "escalate": False,
        },
    )
    r = client.post(f"{AGENT}/conversations/{conversation_id}/suggest", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["draft"] is None
    assert body["escalate"] is True
    assert body["reason"] == "unverified_figures"
    assert "12,500" not in r.text and "12500" not in r.text
    rows = _audit("agent.suggestion_withheld", conversation_id)
    assert rows and (rows[-1].details or {})["decision"] == "escalated"


def test_an_escalating_topic_produces_no_draft_at_all(
    client, world, agent_a, monkeypatch
):
    _uid, headers, _name = agent_a
    conversation_id = _conversation(world)
    _claim(client, conversation_id, headers)
    _enable_suggestions(monkeypatch)
    _install_ai(
        monkeypatch,
        suggest=lambda db, conversation, *, messages: {
            "text": "I can process that refund for you.",
            "model": "gpt-test",
            "prompt_version": "qcp-support-v1",
            "escalate": True,
            "reason": "money",
        },
    )
    r = client.post(f"{AGENT}/conversations/{conversation_id}/suggest", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["draft"] is None
    assert r.json()["escalate"] is True
    assert r.json()["reason"] == "money"
    assert "refund for you" not in r.text


def test_the_ai_is_never_consulted_about_a_verify_thread(
    client, world, agent_a, monkeypatch
):
    _uid, headers, _name = agent_a
    conversation_id = _conversation(world, verify=True)
    _claim(client, conversation_id, headers)
    _enable_suggestions(monkeypatch)
    calls = _install_ai(
        monkeypatch,
        suggest=lambda db, conversation, *, messages: {
            "text": "hello",
            "model": "gpt-test",
            "prompt_version": "qcp-support-v1",
        },
    )
    r = client.post(f"{AGENT}/conversations/{conversation_id}/suggest", headers=headers)
    assert r.status_code == 403, r.text
    assert r.json()["detail"]["reason"] == "verify_number_not_agent_answerable"
    assert calls == [], "the AI was handed a conversation on the Verify number"


def test_a_draft_is_refused_once_the_service_window_has_closed(
    client, world, agent_a, monkeypatch
):
    """Free-form prose cannot legally leave outside the 24h window, so a
    free-form draft is not something to hand an agent."""
    _uid, headers, _name = agent_a
    conversation_id = _conversation(world, inbound_minutes_ago=60 * 30)
    _claim(client, conversation_id, headers)
    _enable_suggestions(monkeypatch)
    calls = _install_ai(
        monkeypatch,
        suggest=lambda db, conversation, *, messages: {"text": "hi", "model": "m"},
    )
    r = client.post(f"{AGENT}/conversations/{conversation_id}/suggest", headers=headers)
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["reason"] == "outside_service_window"
    assert calls == []


# ---------------------------------------------------------------------------
# Handover back
# ---------------------------------------------------------------------------

def test_return_to_ai_clears_the_human_and_reopens(client, world, agent_a):
    _uid, headers, _name = agent_a
    conversation_id = _conversation(world, state="snoozed")
    _claim(client, conversation_id, headers)
    r = client.post(
        f"{AGENT}/conversations/{conversation_id}/return-to-ai", headers=headers
    )
    assert r.status_code == 200, r.text
    assert r.json()["state"] == "open"
    assert r.json()["mine"] is False
    # Reported, not assumed: handing a thread back to an AI that is switched
    # off leaves nobody on it.
    assert r.json()["ai_replies_enabled"] is False
    with SessionLocal() as db:
        row = db.get(WhatsAppConversation, conversation_id)
        assert row.assignee_id is None
        assert row.state == "open"
    assert _audit("agent.returned_to_ai", conversation_id)


def test_returning_a_thread_i_do_not_hold_is_refused(client, world, agent_a, agent_b):
    _uid_a, headers_a, _ = agent_a
    _uid_b, headers_b, _ = agent_b
    conversation_id = _conversation(world)
    _claim(client, conversation_id, headers_a)
    r = client.post(
        f"{AGENT}/conversations/{conversation_id}/return-to-ai", headers=headers_b
    )
    assert r.status_code == 409, r.text
    with SessionLocal() as db:
        assert db.get(WhatsAppConversation, conversation_id).assignee_id == _uid_a


# ---------------------------------------------------------------------------
# Dormancy
# ---------------------------------------------------------------------------

def test_the_agent_console_switches_nothing_on(client, world, agent_a):
    """Nothing in this module flips a gate. Working the queue must not be
    the act that puts QCP live."""
    from app.services.whatsapp import settings_store

    _uid, headers, _name = agent_a
    conversation_id = _conversation(world)
    _claim(client, conversation_id, headers)
    client.post(
        f"{AGENT}/conversations/{conversation_id}/reply",
        json={"kind": "text", "body": "Hello there."},
        headers=headers,
    )
    client.post(f"{AGENT}/conversations/{conversation_id}/return-to-ai", headers=headers)
    assert settings_store.delivery_enabled() is False
    with SessionLocal() as db:
        product = db.get(type(world.product), world.product.id)
        assert product.is_enabled is True  # the world's own product, unchanged
        assert (
            db.query(WhatsAppAccount)
            .filter(WhatsAppAccount.slug.notin_([world.verify.slug, world.quata.slug]))
            .filter(WhatsAppAccount.is_active.is_(True))
            .count()
            == 0
        )
