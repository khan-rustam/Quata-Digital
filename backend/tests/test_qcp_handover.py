"""The AI support layer's escalation and handover rules.

This is the safety-critical half of QCP's AI layer: the part that decides a
**human** is needed. The AI half may only run in the space this module
leaves it, so everything here is written from the pessimistic direction —
the question under test is never "did the AI answer?" but "could the AI ever
answer when it should not have?".

Four families of property:

1. **The kill switch.** AI replies are off unless three independent gates
   agree (env kill switch, an OpenAI key, an admin DB toggle that defaults
   to false). Turning it off must not touch human agents.
2. **The escalation triggers.** Unsafe, low confidence, "give me a human",
   a question asked three times, an unrecognised language, an unparseable
   message, the provider erroring, and — enforced in *code*, not in a
   prompt — anything about money, KYC, fraud, a complaint, a legal threat
   or a distressed customer.
3. **The hard gates.** The Verify number, a conversation attributed to
   nobody, a thread a human already holds, a thread already queued for a
   human, and a closed service window. None of these are advisory.
4. **The handover mechanics.** A human claims a thread and the bot goes
   silent *immediately*; ``return_to_ai`` hands it back; and a thread that
   nobody picks up becomes visible as a problem instead of sitting silently
   with a customer waiting on the other end.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.db.session import SessionLocal
from app.models import (
    Role,
    RolePermission,
    User,
    WhatsAppAccount,
    WhatsAppAuditLog,
    WhatsAppConversation,
    WhatsAppMessage,
    WhatsAppProduct,
)
from app.services.whatsapp import conversations as conv
from app.services.whatsapp import handover


SUFFIX = uuid.uuid4().hex[:8]


# ---------------------------------------------------------------------------
# World
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def world(app_instance):
    """One engagement number, one Verify number, one product, two users.

    Both accounts are created **inactive** so this module stays clear of
    ``uq_whatsapp_accounts_active_purpose`` (one live number per purpose)
    and therefore cannot collide with any other module's world. Nothing
    here sends, so liveness is irrelevant.
    """
    from fastapi.testclient import TestClient

    with TestClient(app_instance):  # lifespan → create_all + seed
        with SessionLocal() as db:
            engagement = WhatsAppAccount(
                slug=f"ho_quata_{SUFFIX}",
                name="QUATA (handover tests)",
                purpose="engagement",
                phone_number_id=f"PN_HO_ENG_{SUFFIX}",
                waba_id=f"WABA_HO_ENG_{SUFFIX}",
                display_phone="+237600007001",
                is_active=False,
            )
            verify = WhatsAppAccount(
                slug=f"ho_verify_{SUFFIX}",
                name="Quata Verify (handover tests)",
                purpose="authentication",
                phone_number_id=f"PN_HO_VER_{SUFFIX}",
                waba_id=f"WABA_HO_VER_{SUFFIX}",
                display_phone="+237600007002",
                is_active=False,
            )
            db.add_all([engagement, verify])
            db.flush()

            product = WhatsAppProduct(
                slug=f"ho_pay_{SUFFIX}",
                name="Handover Pay",
                is_enabled=True,
                api_key_hash="1" * 64,
                api_key_prefix="qcp_ho_a1",
                allowed_purposes=["engagement"],
                default_locale="en",
            )
            db.add(product)
            db.flush()

            agent_role = Role(slug=f"ho_agent_{SUFFIX}", name="Handover Agent", description="t")
            plain_role = Role(slug=f"ho_plain_{SUFFIX}", name="Handover Plain", description="t")
            db.add_all([agent_role, plain_role])
            db.flush()
            db.add(
                RolePermission(
                    role_id=agent_role.id,
                    permission=sorted(conv.WHATSAPP_AGENT_PERMISSIONS)[0],
                )
            )
            agent = User(
                email=f"ho_agent_{SUFFIX}@example.test",
                password_hash="x" * 20,
                full_name="Handover Agent",
                role_id=agent_role.id,
                is_active=True,
            )
            plain = User(
                email=f"ho_plain_{SUFFIX}@example.test",
                password_hash="x" * 20,
                full_name="Handover Plain",
                role_id=plain_role.id,
                is_active=True,
            )
            db.add_all([agent, plain])
            db.flush()

            ids = {
                "engagement_id": engagement.id,
                "verify_id": verify.id,
                "product_id": product.id,
                "agent_id": agent.id,
                "plain_id": plain.id,
                "role_ids": [agent_role.id, plain_role.id],
                "user_ids": [agent.id, plain.id],
            }
            db.commit()

    yield ids

    with SessionLocal() as db:
        db.query(WhatsAppConversation).filter(
            WhatsAppConversation.assignee_id.in_(ids["user_ids"])
        ).update({WhatsAppConversation.assignee_id: None}, synchronize_session=False)
        db.query(User).filter(User.id.in_(ids["user_ids"])).delete(synchronize_session=False)
        db.query(RolePermission).filter(
            RolePermission.role_id.in_(ids["role_ids"])
        ).delete(synchronize_session=False)
        db.query(Role).filter(Role.id.in_(ids["role_ids"])).delete(synchronize_session=False)
        db.commit()


@pytest.fixture
def db():
    with SessionLocal() as session:
        yield session


@pytest.fixture
def ai_on(monkeypatch):
    """Flip all three gates the kill switch reads.

    Deliberately not a patch of ``ai_replies_enabled`` itself: every test
    that needs the AI on therefore also re-proves that the composite switch
    can actually be turned on, so a broken gate cannot hide behind a stub.
    """
    _set_switches(monkeypatch, env=True, key=True, toggle=True)


def _set_switches(
    monkeypatch, *, env: bool, key: bool, toggle: bool, ai_env: bool = True
) -> None:
    """Set all four gates ``ai_replies_enabled`` reads.

    ``ai_env`` is the AI's own env switch, which ``ai/provider.py`` reads by
    the same name; the other three are the fleet kill switch, the OpenAI key
    and the admin DB toggle.
    """
    from app.core.config import settings as env_settings
    from app.services import site_settings

    monkeypatch.setenv(handover.ENV_AI_REPLIES, "true" if ai_env else "false")
    monkeypatch.setattr(env_settings, "WHATSAPP_ENABLED", env)
    monkeypatch.setattr(env_settings, "OPENAI_API_KEY", "sk-pytest-not-a-real-key" if key else "")
    monkeypatch.setattr(
        site_settings,
        "get_setting",
        lambda k, default=None, **kw: (
            "true" if (k == handover.KEY_AI_REPLIES_ENABLED and toggle) else default
        ),
    )
    site_settings.invalidate_cache()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _phone() -> str:
    return "+2376" + str(uuid.uuid4().int)[:8]


def _thread(db, world, *, phone=None, purpose="engagement", open_window=True, **kw):
    phone = phone or _phone()
    account_id = world["engagement_id"] if purpose == "engagement" else world["verify_id"]
    row = WhatsAppConversation(
        account_id=account_id,
        product_id=kw.pop("product_id", world["product_id"]),
        wa_contact_id=conv.wa_contact_id_for(phone),
        phone_e164=phone,
        state=kw.pop("state", "open"),
        unread_count=0,
        meta={},
        **kw,
    )
    if open_window:
        now = datetime.now(timezone.utc)
        row.last_inbound_at = now
        row.service_window_expires_at = now + timedelta(hours=23)
    db.add(row)
    db.flush()
    return row


def _inbound(db, world, conversation, *, body: str, minutes_ago: int = 0):
    when = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    row = WhatsAppMessage(
        message_uid=uuid.uuid4().hex[:32],
        account_id=world["engagement_id"],
        account_purpose="engagement",
        conversation_id=conversation.id,
        product_id=world["product_id"],
        direction="inbound",
        kind="text",
        body=body,
        from_phone_e164=conversation.phone_e164,
        status="delivered",
        created_at=when,
        updated_at=when,
    )
    db.add(row)
    db.flush()
    return row


def _signals(**over):
    """A clean, high-confidence, English, safe classification."""
    base = dict(
        understood=True,
        unsafe=False,
        confidence=0.95,
        language="en",
        wants_human=False,
        provider_error=False,
        topics=(),
        asserts_facts=False,
        facts_from_product_api=False,
    )
    base.update(over)
    return handover.Signals(**base)


def _decide(db, world, conversation, *, text="what time do you close?", **over):
    kwargs = dict(
        signals=_signals(),
        account_purpose="engagement",
        product_id=world["product_id"],
        text=text,
    )
    kwargs.update(over)
    return handover.decide(db, conversation, **kwargs)


# ---------------------------------------------------------------------------
# 1. The kill switch
# ---------------------------------------------------------------------------

def test_ai_replies_are_off_by_default(db, world, monkeypatch):
    """Ships inert: delivery on and a key present is still not consent."""
    _set_switches(monkeypatch, env=True, key=True, toggle=False)
    assert handover.ai_replies_enabled() is False

    decision = _decide(db, world, _thread(db, world))
    assert decision.may_reply is False
    assert decision.reason == handover.R_AI_DISABLED
    assert decision.needs_human is True


def test_the_env_kill_switch_beats_the_database_toggle(db, world, monkeypatch):
    _set_switches(monkeypatch, env=False, key=True, toggle=True)
    assert handover.ai_replies_enabled() is False


def test_without_an_openai_key_the_customer_gets_a_human_not_silence(db, world, monkeypatch):
    """No key is a missing *capability*, not an operator's instruction.

    The switch stays where the operator left it — it answers "is the AI
    supposed to be replying?" — but ``decide`` still refuses to answer,
    because there is no model to answer with. The difference matters: "the
    switch is off" is a deliberate silence, and "there is no key" is a
    customer nobody is going to serve unless a person is fetched.
    """
    _set_switches(monkeypatch, env=True, key=False, toggle=True)
    assert handover.ai_replies_enabled() is True
    assert handover.ai_can_draft() is False

    thread = _thread(db, world)
    decision = _decide(db, world, thread, text="what time do you open")
    assert decision.action == handover.ACT_ESCALATE
    assert handover.R_AI_DISABLED in decision.triggers


def test_the_ai_env_switch_alone_stops_the_bot(monkeypatch):
    _set_switches(monkeypatch, env=True, key=True, toggle=True, ai_env=False)
    assert handover.ai_replies_enabled() is False


def test_all_three_gates_together_are_what_turns_it_on(monkeypatch):
    _set_switches(monkeypatch, env=True, key=True, toggle=True)
    assert handover.ai_replies_enabled() is True


@pytest.mark.parametrize("ai_env", [True, False])
@pytest.mark.parametrize("env", [True, False])
@pytest.mark.parametrize("key", [True, False])
@pytest.mark.parametrize("toggle", [True, False])
def test_the_brake_is_never_looser_than_the_engine(monkeypatch, ai_env, env, key, toggle):
    """Two modules spell this switch; they must not disagree in the unsafe
    direction.

    ``ai/provider.py`` carries the drafting engine's own copy, read from the
    same env var and the same ``site_settings`` key. This module re-derives
    it rather than importing it — a brake that imports the engine can be
    released by editing the engine — which makes "they never diverge" a
    property worth asserting rather than assuming. The asymmetry is
    deliberate: the brake may be *stricter* (it also requires the fleet kill
    switch and a key), never looser.
    """
    engine = pytest.importorskip("app.services.whatsapp.ai.provider")
    _set_switches(monkeypatch, env=env, key=key, toggle=toggle, ai_env=ai_env)
    assert not (handover.ai_replies_enabled() and not engine.ai_replies_enabled())


def test_the_kill_switch_does_not_stop_human_agents(db, world, monkeypatch):
    """The whole point of a *reply* switch: customers keep their humans."""
    _set_switches(monkeypatch, env=True, key=True, toggle=False)
    thread = _thread(db, world)

    handover.escalate(db, thread, reason=handover.R_AI_DISABLED)
    assert thread.assigned_agent == handover.PENDING_HUMAN

    conv.assign(db, thread, user_id=world["agent_id"])
    assert thread.assignee_id == world["agent_id"]

    conv.return_to_ai(db, thread)
    assert thread.assignee_id is None
    db.rollback()


# ---------------------------------------------------------------------------
# 2. Escalation triggers
# ---------------------------------------------------------------------------

def test_a_clean_question_inside_every_gate_is_answered(db, world, ai_on):
    decision = _decide(db, world, _thread(db, world))
    assert decision.may_reply is True
    assert decision.reason == handover.R_NO_TRIGGER
    assert decision.triggers == ()


@pytest.mark.parametrize(
    "over,reason",
    [
        (dict(unsafe=True), handover.R_UNSAFE),
        (dict(confidence=0.10), handover.R_LOW_CONFIDENCE),
        (dict(wants_human=True), handover.R_HUMAN_REQUESTED),
        (dict(language="de"), handover.R_LANGUAGE),
        (dict(language=None), handover.R_LANGUAGE),
        (dict(understood=False), handover.R_UNPARSEABLE),
        (dict(provider_error=True), handover.R_PROVIDER_ERROR),
        (dict(topics=("kyc",)), handover.R_SENSITIVE),
        (dict(asserts_facts=True), handover.R_UNGROUNDED),
    ],
)
def test_every_classifier_signal_that_must_escalate_does(db, world, ai_on, over, reason):
    decision = _decide(db, world, _thread(db, world), signals=_signals(**over))
    assert decision.may_reply is False
    assert decision.needs_human is True
    assert reason in decision.triggers


def test_an_empty_classification_fails_closed(db, world, ai_on):
    """``Signals()`` — an engine that returned nothing — must not answer."""
    decision = _decide(db, world, _thread(db, world), signals=handover.Signals())
    assert decision.may_reply is False
    assert handover.R_UNPARSEABLE in decision.triggers


def test_a_fact_sourced_from_a_product_api_is_not_an_ungrounded_fact(db, world, ai_on):
    decision = _decide(
        db,
        world,
        _thread(db, world),
        signals=_signals(asserts_facts=True, facts_from_product_api=True),
    )
    assert decision.may_reply is True


@pytest.mark.parametrize(
    "text,topic",
    [
        ("where is my refund?", handover.TOPIC_MONEY),
        ("mon remboursement n'est pas arrivé", handover.TOPIC_MONEY),
        ("what is my balance", handover.TOPIC_MONEY),
        ("je veux voir mon solde momo", handover.TOPIC_MONEY),
        ("my kyc is still pending", handover.TOPIC_KYC),
        ("ma verification d'identite est bloquee", handover.TOPIC_KYC),
        ("someone hacked my account", handover.TOPIC_FRAUD),
        ("c'est une arnaque", handover.TOPIC_FRAUD),
        ("this is my third complaint", handover.TOPIC_COMPLAINT),
        ("je vais porter plainte", handover.TOPIC_LEGAL),
        ("my lawyer will call you", handover.TOPIC_LEGAL),
        ("i will kill myself if you take my money", handover.TOPIC_DISTRESS),
        ("my account is suspended", handover.TOPIC_ACCOUNT),
    ],
)
def test_sensitive_text_escalates_even_when_the_classifier_says_it_is_fine(
    db, world, ai_on, text, topic
):
    """The safety rule is enforced in code, not in a prompt.

    A confident, safe, well-understood classification of "where is my
    refund?" is exactly what a prompt-injected or simply wrong model
    produces. The scan below is independent of it.
    """
    assert topic in handover.sensitive_topics(text)

    decision = _decide(db, world, _thread(db, world), text=text, signals=_signals())
    assert decision.may_reply is False
    assert handover.R_SENSITIVE in decision.triggers
    assert topic in decision.detail["topics"]


def test_an_ordinary_support_question_is_not_flagged_sensitive():
    assert handover.sensitive_topics("what time do you open on saturday?") == ()
    assert handover.sensitive_topics("comment changer mon nom sur l'application ?") == ()


def test_asking_the_same_thing_three_times_means_the_ai_has_not_helped(db, world, ai_on):
    thread = _thread(db, world)
    text = "how do I change my delivery address"
    for minutes in (30, 20):
        _inbound(db, world, thread, body=text, minutes_ago=minutes)
    assert _decide(db, world, thread, text=text).may_reply is True

    _inbound(db, world, thread, body="How do I change my delivery address???", minutes_ago=1)
    decision = _decide(db, world, thread, text=text)
    assert decision.may_reply is False
    assert handover.R_REPEATED in decision.triggers
    db.rollback()


def test_three_different_questions_are_not_a_repeat(db, world, ai_on):
    thread = _thread(db, world)
    for i, body in enumerate(("where are you located", "do you deliver", "what are your hours")):
        _inbound(db, world, thread, body=body, minutes_ago=30 - i)
    assert _decide(db, world, thread, text="what are your hours").may_reply is True
    db.rollback()


def test_an_old_repeat_is_outside_the_window(db, world, ai_on):
    thread = _thread(db, world)
    text = "is my order coming"
    for minutes in (60 * 40, 60 * 39, 5):
        _inbound(db, world, thread, body=text, minutes_ago=minutes)
    assert _decide(db, world, thread, text=text).may_reply is True
    db.rollback()


def test_every_trigger_is_collected_not_just_the_first(db, world, ai_on):
    decision = _decide(
        db,
        world,
        _thread(db, world),
        text="where is my refund",
        signals=_signals(unsafe=True, confidence=0.1),
    )
    assert {handover.R_UNSAFE, handover.R_LOW_CONFIDENCE, handover.R_SENSITIVE} <= set(
        decision.triggers
    )


# ---------------------------------------------------------------------------
# 3. Hard gates
# ---------------------------------------------------------------------------

def test_the_ai_never_answers_on_the_verify_number(db, world, ai_on):
    thread = _thread(db, world, purpose="authentication")
    decision = _decide(db, world, thread, account_purpose="authentication")
    assert decision.may_reply is False
    assert decision.reason == handover.R_NOT_ENGAGEMENT
    # A customer texting the OTP number is often reporting fraud — a human
    # has to see it, so this is an escalation and not a silent drop.
    assert decision.needs_human is True


def test_an_unknown_account_purpose_is_treated_as_not_engagement(db, world, ai_on):
    decision = _decide(db, world, _thread(db, world), account_purpose=None)
    assert decision.may_reply is False
    assert decision.reason == handover.R_NOT_ENGAGEMENT


def test_a_message_attributed_to_nobody_is_for_a_human(db, world, ai_on):
    """The ambiguous case the ownership model deliberately refuses to guess."""
    thread = _thread(db, world, product_id=None)
    decision = _decide(db, world, thread, product_id=None)
    assert decision.may_reply is False
    assert decision.reason == handover.R_UNATTRIBUTED
    assert decision.needs_human is True


def test_outside_the_service_window_the_ai_does_not_reply(db, world, ai_on):
    thread = _thread(db, world, open_window=False)
    thread.last_inbound_at = datetime.now(timezone.utc) - timedelta(hours=30)
    thread.service_window_expires_at = datetime.now(timezone.utc) - timedelta(hours=6)
    db.flush()
    decision = _decide(db, world, thread)
    assert decision.may_reply is False
    assert decision.reason == handover.R_OUTSIDE_WINDOW
    db.rollback()


# ---------------------------------------------------------------------------
# 4. Handover mechanics
# ---------------------------------------------------------------------------

def test_escalation_marks_the_thread_and_reopens_it(db, world, ai_on):
    thread = _thread(db, world, state="closed")
    handover.escalate(db, thread, reason=handover.R_SENSITIVE, detail={"topics": ["money"]})

    assert thread.assigned_agent == handover.PENDING_HUMAN
    # Nobody is on it yet — an escalation is a request for a human, not an
    # assignment to one.
    assert thread.assignee_id is None
    # A customer waiting on a human must not sit in a closed queue.
    assert thread.state == conv.STATE_OPEN
    assert handover.waiting_since(thread) is not None
    db.rollback()


def test_escalating_twice_keeps_the_original_wait_clock(db, world, ai_on):
    thread = _thread(db, world)
    first = datetime.now(timezone.utc) - timedelta(hours=2)
    handover.escalate(db, thread, reason=handover.R_UNSAFE, now=first)
    started = handover.waiting_since(thread)

    handover.escalate(db, thread, reason=handover.R_LOW_CONFIDENCE)
    assert handover.waiting_since(thread) == started
    db.rollback()


def test_a_thread_already_waiting_for_a_human_is_held_not_re_escalated(db, world, ai_on):
    thread = _thread(db, world)
    handover.escalate(db, thread, reason=handover.R_HUMAN_REQUESTED)
    decision = _decide(db, world, thread)
    assert decision.may_reply is False
    assert decision.action == handover.ACT_HOLD
    assert decision.reason == handover.R_AWAITING_HUMAN
    db.rollback()


def test_when_a_human_claims_the_thread_the_bot_goes_silent_immediately(db, world, ai_on):
    """Not eventually. The very next decision must be silence."""
    thread = _thread(db, world)
    assert _decide(db, world, thread).may_reply is True

    conv.assign(db, thread, user_id=world["agent_id"])

    decision = _decide(db, world, thread)
    assert decision.may_reply is False
    assert decision.action == handover.ACT_HOLD
    assert decision.reason == handover.R_HUMAN_ASSIGNED
    db.rollback()


def test_claiming_an_escalated_thread_clears_the_pending_flag(db, world, ai_on):
    thread = _thread(db, world)
    handover.escalate(db, thread, reason=handover.R_SENSITIVE)
    conv.assign(db, thread, user_id=world["agent_id"])

    assert thread.assigned_agent is None
    assert thread.assignee_id == world["agent_id"]
    db.rollback()


def test_return_to_ai_hands_the_thread_back(db, world, ai_on):
    thread = _thread(db, world)
    handover.escalate(db, thread, reason=handover.R_LOW_CONFIDENCE)
    conv.assign(db, thread, user_id=world["agent_id"])
    conv.return_to_ai(db, thread)

    assert thread.assignee_id is None
    assert thread.assigned_agent is None
    assert thread.state == conv.STATE_OPEN
    assert _decide(db, world, thread).may_reply is True
    db.rollback()


def test_closing_a_thread_resolves_the_handover_state(db, world, ai_on):
    """Otherwise one escalation strands the thread on the human queue for good."""
    thread = _thread(db, world)
    handover.escalate(db, thread, reason=handover.R_SENSITIVE)
    conv.close_conversation(db, thread)
    assert thread.assigned_agent is None
    db.rollback()


def test_assign_still_refuses_a_user_without_the_entitlement(db, world):
    """Regression pin: the handover seam must not have widened ``assign``."""
    thread = _thread(db, world)
    with pytest.raises(ValueError) as unknown:
        conv.assign(db, thread, user_id=999_999_999)
    with pytest.raises(ValueError) as not_an_agent:
        conv.assign(db, thread, user_id=world["plain_id"])
    assert str(unknown.value) == str(not_an_agent.value) == "unknown_agent"
    assert thread.assignee_id is None
    db.rollback()


def test_the_handover_seam_does_not_move_the_service_window_or_ownership(db, world, ai_on):
    """Regression pin for the two properties conversations.py already proves."""
    thread = _thread(db, world)
    expiry = thread.service_window_expires_at
    owner = thread.product_id

    handover.escalate(db, thread, reason=handover.R_UNSAFE)
    conv.assign(db, thread, user_id=world["agent_id"])
    conv.return_to_ai(db, thread)

    assert thread.service_window_expires_at == expiry
    assert thread.product_id == owner
    db.rollback()


# ---------------------------------------------------------------------------
# 5. Nobody picked it up
# ---------------------------------------------------------------------------

def test_an_unclaimed_escalation_becomes_visible_as_a_problem(db, world, ai_on):
    stale = _thread(db, world)
    fresh = _thread(db, world)
    claimed = _thread(db, world)
    closed = _thread(db, world)
    long_ago = datetime.now(timezone.utc) - timedelta(hours=3)

    handover.escalate(db, stale, reason=handover.R_SENSITIVE, now=long_ago)
    handover.escalate(db, fresh, reason=handover.R_SENSITIVE)
    handover.escalate(db, claimed, reason=handover.R_SENSITIVE, now=long_ago)
    conv.assign(db, claimed, user_id=world["agent_id"])
    handover.escalate(db, closed, reason=handover.R_SENSITIVE, now=long_ago)
    conv.close_conversation(db, closed)

    waiting = handover.unanswered_escalations(db, account_id=world["engagement_id"])
    ids = [row.id for row in waiting]
    assert stale.id in ids
    assert fresh.id not in ids      # not yet late
    assert claimed.id not in ids    # a human has it
    assert closed.id not in ids     # handled
    db.rollback()


def test_the_longest_wait_is_reported_first(db, world, ai_on):
    older = _thread(db, world)
    newer = _thread(db, world)
    now = datetime.now(timezone.utc)
    handover.escalate(db, older, reason=handover.R_UNSAFE, now=now - timedelta(hours=5))
    handover.escalate(db, newer, reason=handover.R_UNSAFE, now=now - timedelta(hours=1))

    waiting = handover.unanswered_escalations(db, account_id=world["engagement_id"])
    ids = [row.id for row in waiting]
    assert ids.index(older.id) < ids.index(newer.id)
    db.rollback()


def test_an_unanswered_customer_is_reported_once_not_every_sweep(db, world, ai_on):
    thread = _thread(db, world)
    handover.escalate(
        db, thread, reason=handover.R_SENSITIVE, now=datetime.now(timezone.utc) - timedelta(hours=4)
    )

    assert [r.id for r in handover.flag_unanswered(db, account_id=world["engagement_id"])] == [
        thread.id
    ]
    assert handover.flag_unanswered(db, account_id=world["engagement_id"]) == []

    rows = (
        db.query(WhatsAppAuditLog)
        .filter(
            WhatsAppAuditLog.action == "ai.unanswered",
            WhatsAppAuditLog.resource_id == str(thread.id),
        )
        .all()
    )
    assert len(rows) == 1
    assert rows[0].outcome == "denied"
    db.rollback()


# ---------------------------------------------------------------------------
# 6. The audit trail
# ---------------------------------------------------------------------------

def test_an_answer_is_audited_with_the_model_and_prompt_version(db, world, ai_on):
    thread = _thread(db, world)
    decision = handover.apply(
        db,
        thread,
        _decide(db, world, thread),
        product_id=world["product_id"],
        model="gpt-4o-mini",
        prompt_version="qcp-support-v1",
    )
    assert decision.may_reply is True

    row = (
        db.query(WhatsAppAuditLog)
        .filter(WhatsAppAuditLog.resource_id == str(thread.id))
        .order_by(WhatsAppAuditLog.id.desc())
        .first()
    )
    assert row.action == "ai.answered"
    assert row.reason == handover.R_NO_TRIGGER
    assert row.details["model"] == "gpt-4o-mini"
    assert row.details["prompt_version"] == "qcp-support-v1"
    db.rollback()


def test_an_escalation_is_audited_with_its_triggers_and_no_customer_text(db, world, ai_on):
    thread = _thread(db, world)
    text = "where is my refund, this is a scam"
    handover.apply(
        db,
        thread,
        _decide(db, world, thread, text=text, signals=_signals(confidence=0.2)),
        product_id=world["product_id"],
        model="gpt-4o-mini",
        prompt_version="qcp-support-v1",
    )
    row = (
        db.query(WhatsAppAuditLog)
        .filter(WhatsAppAuditLog.resource_id == str(thread.id))
        .order_by(WhatsAppAuditLog.id.desc())
        .first()
    )
    assert row.action == "ai.escalated"
    assert row.outcome == "denied"
    assert handover.R_SENSITIVE in row.details["triggers"]
    assert handover.R_LOW_CONFIDENCE in row.details["triggers"]
    # The customer's own words are PII and never belong in the audit row.
    assert "refund" not in str(row.details)
    assert thread.assigned_agent == handover.PENDING_HUMAN
    db.rollback()


def test_apply_never_marks_a_held_thread_as_needing_a_second_human(db, world, ai_on):
    thread = _thread(db, world)
    conv.assign(db, thread, user_id=world["agent_id"])
    handover.apply(db, thread, _decide(db, world, thread), product_id=world["product_id"])
    assert thread.assigned_agent is None
    assert thread.assignee_id == world["agent_id"]
    db.rollback()


# ---------------------------------------------------------------------------
# 7. The last line of defence on the send itself
# ---------------------------------------------------------------------------

def test_the_send_guard_refuses_the_verify_number(db, world):
    with pytest.raises(handover.AiSendRefused) as exc:
        handover.guard_ai_send(account_purpose="authentication", kind="text", body="hello")
    assert "engagement" in str(exc.value)


@pytest.mark.parametrize("kind", ["template", "interactive", "media", "reaction", "system"])
def test_the_send_guard_only_allows_free_form_text(kind):
    with pytest.raises(handover.AiSendRefused):
        handover.guard_ai_send(account_purpose="engagement", kind=kind, body="hello")


@pytest.mark.parametrize("intent", ["login_otp", "verify_phone", "auth_code", "2fa_challenge"])
def test_the_send_guard_refuses_an_authentication_shaped_intent(intent):
    with pytest.raises(handover.AiSendRefused):
        handover.guard_ai_send(
            account_purpose="engagement", kind="text", intent=intent, body="hello"
        )


@pytest.mark.parametrize(
    "body",
    [
        "Your code is 483920",
        "votre code de verification est 4839",
        "OTP: 12345",
        "Use 837465 to log in",
    ],
)
def test_the_send_guard_refuses_anything_otp_shaped(body):
    with pytest.raises(handover.AiSendRefused):
        handover.guard_ai_send(account_purpose="engagement", kind="text", body=body)


@pytest.mark.parametrize(
    "body",
    [
        "Your balance is 15,000 XAF",
        "We refunded 2000 FCFA yesterday",
        "Your order total was 7500 CFA",
    ],
)
def test_the_send_guard_refuses_an_invented_money_figure(body):
    with pytest.raises(handover.AiSendRefused):
        handover.guard_ai_send(account_purpose="engagement", kind="text", body=body)
    # The same sentence is allowed only when the figure came from a product
    # API in this request — that is what ``grounded`` asserts.
    handover.guard_ai_send(
        account_purpose="engagement", kind="text", body=body, grounded=True
    )


def test_the_send_guard_allows_an_ordinary_support_reply():
    handover.guard_ai_send(
        account_purpose="engagement",
        kind="text",
        body="We're open Monday to Saturday, 8am to 6pm. Anything else I can help with?",
    )
