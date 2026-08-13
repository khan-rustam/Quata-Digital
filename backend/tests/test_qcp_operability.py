"""Can anybody actually *operate* the QCP AI support layer?

The attack suites ask whether the AI can be made to say something false.
This one asks the three questions that decide whether the feature works at
all once it is switched on — every one of which fails **silently** today,
which is the worst way for a support desk to fail:

1. **Does anything chase an escalation nobody answered?** The alert exists
   (``handover.flag_unanswered``) and one HTTP endpoint calls it, so it
   fires only when a human opens a screen and presses a button. A customer
   escalated at 21:00 waits until somebody happens to look. That is the exact
   outcome this feature exists to prevent, and it is worse than having no AI
   at all, because the customer was *told* a person would come.

2. **Does switching the AI on without a routing rule say anything?** An AI
   reply is a send, and a send needs a route. With no rule the reply is
   refused inside ``dispatch`` and the operator sees an AI that answers
   nobody, with nothing on any screen explaining why. The bilingual case is
   worse still: a rule created for ``en`` alone serves anglophone customers
   and silently strands every francophone one, on a platform whose two
   supported languages are exactly ``en`` and ``fr``.

3. **Is the support entitlement granted to anybody?** ``whatsapp:agent``
   exists in the catalogue and in ``WHATSAPP_AGENT_PERMISSIONS``, and no
   seeded role carries it — so the only people who can work the customer
   queue are Admins holding ``settings:manage``.

Nothing here enables anything. The switches are patched per-test, both
numbers stay inactive, and no test reaches a network.
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
    WhatsAppProduct,
    WhatsAppRoutingRule,
)
from app.scripts import whatsapp_worker
from app.services.whatsapp import conversations as conv
from app.services.whatsapp import handover, settings_store


SUFFIX = uuid.uuid4().hex[:8]

# The two languages Cameroon actually writes in, and the two QCP supports.
# Read off the brake rather than restated, so a third locale added there is
# a failure here rather than a silent bilingual gap.
LOCALES = sorted(handover.SUPPORTED_LANGUAGES)


# ---------------------------------------------------------------------------
# World — one dormant engagement number, one enabled product, no routing rule
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def world(app_instance):
    from fastapi.testclient import TestClient

    from app.services.whatsapp.credentials import encrypt_wa_secret

    with TestClient(app_instance):
        with SessionLocal() as db:
            engagement = WhatsAppAccount(
                slug=f"ops-quata-{SUFFIX}",
                name="QUATA (operability)",
                purpose="engagement",
                phone_number_id=f"PN-OPS-ENG-{SUFFIX}",
                waba_id=f"WABA-OPS-ENG-{SUFFIX}",
                display_phone="+237600008801",
                api_version="v21.0",
                access_token_encrypted=encrypt_wa_secret(f"PYTEST_NOT_REAL_{SUFFIX}"),
                # Inactive: this module must not collide with any other
                # module's world on uq_whatsapp_accounts_active_purpose.
                is_active=False,
                health="unknown",
            )
            product = WhatsAppProduct(
                slug=f"ops-food-{SUFFIX}",
                name="Operability Food",
                is_enabled=True,
                api_key_hash="7" * 64,
                api_key_prefix="qcp_ops_test",
                allowed_purposes=["engagement"],
                default_locale="fr",
            )
            db.add_all([engagement, product])
            db.flush()
            ids = {
                "account_id": engagement.id,
                "product_id": product.id,
                "product_slug": product.slug,
            }
            db.commit()

    yield ids

    with SessionLocal() as db:
        db.query(WhatsAppConversation).filter(
            WhatsAppConversation.account_id == ids["account_id"]
        ).delete(synchronize_session=False)
        db.query(WhatsAppRoutingRule).filter(
            WhatsAppRoutingRule.product_id == ids["product_id"]
        ).delete(synchronize_session=False)
        db.query(WhatsAppProduct).filter(
            WhatsAppProduct.id == ids["product_id"]
        ).update({WhatsAppProduct.is_enabled: False}, synchronize_session=False)
        db.commit()


@pytest.fixture
def db():
    with SessionLocal() as session:
        yield session
        session.rollback()


def _switches(monkeypatch, *, ai_env: bool, fleet: bool, toggle: bool) -> None:
    """Drive the three real gates, never ``ai_replies_enabled`` itself."""
    from app.core.config import settings as env_settings
    from app.services import site_settings

    monkeypatch.setenv(settings_store.ENV_AI_REPLIES, "true" if ai_env else "false")
    monkeypatch.setattr(env_settings, "WHATSAPP_ENABLED", fleet)
    monkeypatch.setattr(
        site_settings,
        "get_setting",
        lambda k, default=None, **kw: (
            "true" if (k == settings_store.KEY_AI_REPLIES_ENABLED and toggle) else default
        ),
    )
    site_settings.invalidate_cache()


@pytest.fixture
def ai_on(monkeypatch):
    _switches(monkeypatch, ai_env=True, fleet=True, toggle=True)


@pytest.fixture
def no_rules(world):
    """Start and finish each routing test with this product unrouted.

    The rules are committed (``ai_reply_readiness`` reads its own session in
    the worker tests), so without this one test's rule silently configures
    the next one's product.
    """
    def _clear():
        with SessionLocal() as db:
            db.query(WhatsAppRoutingRule).filter(
                WhatsAppRoutingRule.product_id == world["product_id"]
            ).delete(synchronize_session=False)
            db.commit()

    _clear()
    yield
    _clear()


def _escalated_thread(db, world, *, minutes_ago: int, locale: str) -> int:
    """A customer told a human would come, waiting ``minutes_ago`` minutes."""
    now = datetime.now(timezone.utc)
    row = WhatsAppConversation(
        account_id=world["account_id"],
        product_id=world["product_id"],
        wa_contact_id=uuid.uuid4().hex[:20],
        phone_e164="+2376000" + uuid.uuid4().hex[:5],
        state="open",
        unread_count=1,
        last_inbound_at=now - timedelta(minutes=minutes_ago),
        service_window_expires_at=now + timedelta(hours=2),
        locale=locale,
        meta={},
    )
    db.add(row)
    db.flush()
    handover.escalate(
        db,
        row,
        reason=handover.R_SENSITIVE,
        now=now - timedelta(minutes=minutes_ago),
    )
    db.commit()
    return row.id


def _add_ai_rule(db, world, *, locale, is_active=True, purpose="engagement") -> None:
    from app.services.whatsapp.ai.turn import AI_REPLY_INTENT

    db.add(
        WhatsAppRoutingRule(
            product_id=world["product_id"],
            intent=AI_REPLY_INTENT,
            purpose=purpose,
            template_intent=AI_REPLY_INTENT,
            locale=locale,
            priority=100,
            is_active=is_active,
            fallback_channel="none",
            conditions={},
        )
    )
    db.commit()


def _unanswered_rows(db, conversation_id: int) -> int:
    return (
        db.query(WhatsAppAuditLog)
        .filter(WhatsAppAuditLog.action == "ai.unanswered")
        .filter(WhatsAppAuditLog.resource_id == str(conversation_id))
        .count()
    )


# ===========================================================================
# 1 — an escalation nobody answered is chased by something on a schedule
# ===========================================================================

@pytest.mark.parametrize("locale", LOCALES)
def test_the_worker_chases_an_escalation_nobody_answered(world, monkeypatch, locale):
    """21:00 in Bamenda, nobody at a screen. Something must still notice.

    The alert already existed; only an HTTP POST called it. This asserts the
    background worker this repo already runs does the sweep itself, in both
    of Cameroon's languages — a chase that only covers anglophone threads is
    not a chase.
    """
    monkeypatch.setattr(settings_store, "delivery_enabled", lambda: False)

    with SessionLocal() as db:
        thread_id = _escalated_thread(db, world, minutes_ago=45, locale=locale)
        assert _unanswered_rows(db, thread_id) == 0

    summary = whatsapp_worker.run_cycle(1, limit=50)

    with SessionLocal() as db:
        assert _unanswered_rows(db, thread_id) == 1, (
            "nothing on a schedule chased the escalation — the customer is "
            "still waiting and no alert was raised"
        )
    assert summary.get("unanswered", 0) >= 1


def test_the_chase_happens_even_though_delivery_is_paused(world, monkeypatch):
    """QCP is dormant today. That is when escalations rot, not when they don't.

    If the sweep sat behind the delivery gate it would never run on the
    fleet's actual configuration — and the sweep sends nothing, so there is
    no reason for it to be behind that gate.
    """
    monkeypatch.setattr(settings_store, "delivery_enabled", lambda: False)

    with SessionLocal() as db:
        thread_id = _escalated_thread(db, world, minutes_ago=90, locale="fr")

    summary = whatsapp_worker.run_cycle(1, limit=50)

    assert summary.get("skipped") == "delivery_disabled"
    with SessionLocal() as db:
        assert _unanswered_rows(db, thread_id) == 1


def test_a_polling_worker_alerts_once_not_once_a_minute(world, monkeypatch):
    """One ignored customer is one row, whatever the cycle interval is."""
    monkeypatch.setattr(settings_store, "delivery_enabled", lambda: False)

    with SessionLocal() as db:
        thread_id = _escalated_thread(db, world, minutes_ago=30, locale="en")

    for cycle in range(1, 4):
        whatsapp_worker.run_cycle(cycle, limit=50)

    with SessionLocal() as db:
        assert _unanswered_rows(db, thread_id) == 1


def test_a_fresh_escalation_is_not_chased_before_its_time(world, monkeypatch):
    """The SLA is ``UNANSWERED_AFTER``; a thread inside it is a queue entry."""
    monkeypatch.setattr(settings_store, "delivery_enabled", lambda: False)

    with SessionLocal() as db:
        thread_id = _escalated_thread(db, world, minutes_ago=1, locale="fr")

    whatsapp_worker.run_cycle(1, limit=50)

    with SessionLocal() as db:
        assert _unanswered_rows(db, thread_id) == 0


def test_the_chase_is_inert_on_a_dormant_install(monkeypatch):
    """Nothing escalated, nothing sent, nothing written. Safe to schedule now."""
    monkeypatch.setattr(settings_store, "delivery_enabled", lambda: False)
    watched = ["ai.unanswered", whatsapp_worker.ACTION_AI_MISCONFIGURED]

    def _count() -> int:
        with SessionLocal() as db:
            return (
                db.query(WhatsAppAuditLog)
                .filter(WhatsAppAuditLog.action.in_(watched))
                .count()
            )

    before = _count()
    whatsapp_worker.run_cycle(1, limit=50)
    whatsapp_worker.run_cycle(2, limit=50)
    assert _count() == before, "an idle sweep wrote audit rows on a dormant install"


# ===========================================================================
# 2 — "on but unroutable" is a loud state, not silence
# ===========================================================================

def test_an_ai_switched_on_with_no_routing_rule_reports_the_gap(world, db, ai_on, no_rules):
    """The operator's actual failure: switched on, answers nobody, says nothing."""
    state = settings_store.ai_reply_readiness(db)

    assert state["enabled"] is True
    assert state["misconfigured"] is True, (
        "the AI is on and cannot route a single reply, and nothing says so"
    )
    assert state["blocker"] == settings_store.AI_BLOCKED_NO_ROUTE
    assert state["can_answer"] is False
    gaps = {row["product"]: row["locales"] for row in state["gaps"]}
    assert gaps.get(world["product_slug"]) == LOCALES


def test_an_english_only_rule_is_still_a_gap_for_francophone_customers(
    world, db, ai_on, no_rules
):
    """Cameroon is bilingual and ``_find_rule`` matches on locale.

    A rule created for ``en`` alone resolves for an anglophone thread and
    returns None for a francophone one, so the AI answers half the country
    and silently ignores the other half. A readiness check that only asked
    "is there a rule?" would call this configured.
    """
    _add_ai_rule(db, world, locale="en")

    state = settings_store.ai_reply_readiness(db)
    gaps = {row["product"]: row["locales"] for row in state["gaps"]}
    assert gaps.get(world["product_slug"]) == ["fr"], (
        "an English-only routing rule was reported as fully configured"
    )
    assert state["misconfigured"] is True
    assert state["blocker"] == settings_store.AI_BLOCKED_NO_ROUTE


def test_a_rule_in_both_languages_clears_the_gap(world, db, ai_on, no_rules):
    """The healthy state, and it takes both locales to reach it."""
    for locale in LOCALES:
        _add_ai_rule(db, world, locale=locale)

    state = settings_store.ai_reply_readiness(db)
    gaps = {row["product"] for row in state["gaps"]}
    assert world["product_slug"] not in gaps
    assert world["product_slug"] in state["routed_products"]


def test_a_locale_agnostic_rule_covers_both_languages(world, db, ai_on, no_rules):
    """A NULL-locale rule is the "any language" rule and must count as both."""
    _add_ai_rule(db, world, locale=None)

    state = settings_store.ai_reply_readiness(db)
    gaps = {row["product"] for row in state["gaps"]}
    assert world["product_slug"] not in gaps


def test_an_inactive_rule_is_not_a_rule(world, db, ai_on, no_rules):
    """``is_active`` defaults to FALSE; a drafted rule routes nothing."""
    _add_ai_rule(db, world, locale=None, is_active=False)

    state = settings_store.ai_reply_readiness(db)
    gaps = {row["product"]: row["locales"] for row in state["gaps"]}
    assert gaps.get(world["product_slug"]) == LOCALES


def test_an_authentication_rule_is_a_gap_not_a_route(world, db, ai_on, no_rules):
    """A rule pointing at Quata Verify is refused at send time by ``turn``.

    Counting it as configured would report a green console for a product
    whose every AI reply is escalated instead of sent.
    """
    _add_ai_rule(db, world, locale=None, purpose="authentication")

    state = settings_store.ai_reply_readiness(db)
    gaps = {row["product"]: row["locales"] for row in state["gaps"]}
    assert gaps.get(world["product_slug"]) == LOCALES


def test_a_switched_off_ai_is_dormant_not_misconfigured(world, db, monkeypatch, no_rules):
    """The fleet's real state today. It must not raise an alarm."""
    _switches(monkeypatch, ai_env=False, fleet=True, toggle=False)

    state = settings_store.ai_reply_readiness(db)
    assert state["enabled"] is False
    assert state["misconfigured"] is False
    assert state["can_answer"] is False
    assert state["blocker"] == settings_store.AI_BLOCKED_SWITCH_OFF


def test_the_worker_reports_the_unroutable_ai_into_the_audit_log(
    world, monkeypatch, ai_on, no_rules
):
    """The console renders the QCP audit log; that is where an operator looks.

    One row per interval, not one per cycle — the misconfiguration lasts
    until somebody fixes it, and a row a minute is a log nobody reads.
    """
    action = whatsapp_worker.ACTION_AI_MISCONFIGURED
    monkeypatch.setattr(settings_store, "delivery_enabled", lambda: False)

    with SessionLocal() as db:
        before = db.query(WhatsAppAuditLog).filter(
            WhatsAppAuditLog.action == action
        ).count()

    for cycle in range(1, 4):
        whatsapp_worker.run_cycle(cycle, limit=50)

    with SessionLocal() as db:
        rows = (
            db.query(WhatsAppAuditLog)
            .filter(WhatsAppAuditLog.action == action)
            .order_by(WhatsAppAuditLog.id.desc())
            .all()
        )
    assert len(rows) == before + 1, (
        "the unroutable AI was either never reported or reported every cycle"
    )
    assert rows[0].outcome == "denied"
    assert rows[0].reason == settings_store.AI_BLOCKED_NO_ROUTE


def test_the_worker_says_nothing_while_the_ai_is_switched_off(monkeypatch):
    """Dormant is not broken. No row, ever, until somebody switches it on."""
    action = whatsapp_worker.ACTION_AI_MISCONFIGURED
    _switches(monkeypatch, ai_env=False, fleet=True, toggle=False)
    monkeypatch.setattr(settings_store, "delivery_enabled", lambda: False)

    with SessionLocal() as db:
        before = db.query(WhatsAppAuditLog).filter(
            WhatsAppAuditLog.action == action
        ).count()

    whatsapp_worker.run_cycle(1, limit=50)

    with SessionLocal() as db:
        after = db.query(WhatsAppAuditLog).filter(
            WhatsAppAuditLog.action == action
        ).count()
    assert after == before


# ===========================================================================
# 3 — the support entitlement is granted to somebody
# ===========================================================================

def test_a_seeded_role_carries_the_support_entitlement(db):
    """``whatsapp:agent`` existed in the catalogue and on no role at all."""
    holders = {
        role.slug
        for role in db.query(Role).all()
        if "whatsapp:agent" in {p.permission for p in role.permissions}
    }
    assert holders, (
        "the support-desk entitlement is granted to nobody, so only Admins "
        "holding settings:manage can work the customer queue"
    )
    assert "support" in holders


def test_the_support_role_may_be_handed_a_customer_thread(world, db):
    """The point of the role: ``conversations.assign`` accepts it."""
    role = db.query(Role).filter(Role.slug == "support").one()
    user = User(
        email=f"ops_support_{uuid.uuid4().hex[:8]}@quatadigital.com",
        full_name="Support Desk",
        password_hash="x" * 20,
        role_id=role.id,
        is_active=True,
    )
    db.add(user)
    db.commit()
    user_id = user.id
    try:
        assert conv._is_whatsapp_agent(user) is True

        thread_id = _escalated_thread(db, world, minutes_ago=20, locale="fr")
        thread = db.get(WhatsAppConversation, thread_id)
        conv.assign(db, thread, user_id=user_id)
        assert thread.assignee_id == user_id
        assert thread.assigned_agent != handover.PENDING_HUMAN
    finally:
        db.rollback()
        db.query(WhatsAppConversation).filter(
            WhatsAppConversation.assignee_id == user_id
        ).update({WhatsAppConversation.assignee_id: None}, synchronize_session=False)
        db.query(User).filter(User.id == user_id).delete(synchronize_session=False)
        db.commit()


def test_the_support_role_reconfigures_nothing(db):
    """Deliberately the smallest QCP entitlement there is.

    It answers customers. It must not carry ``whatsapp:operate`` (which
    switches the fleet's OTP number on), ``settings:manage`` or the wildcard.
    """
    role = db.query(Role).filter(Role.slug == "support").one()
    held = {p.permission for p in role.permissions}
    assert held == {"whatsapp:agent"}


def test_an_admin_can_delegate_the_support_role(db):
    """``_assert_can_assign_role`` refuses a role holding more than the actor.

    If the Admin role does not itself hold ``whatsapp:agent``, only the
    founder can ever staff the support desk — a fresh silent dead end in
    place of the old one. Admin gains nothing by holding it: it already
    passes ``_is_whatsapp_agent`` through ``settings:manage``.
    """
    admin = db.query(Role).filter(Role.slug == "admin").one()
    support = db.query(Role).filter(Role.slug == "support").one()
    admin_perms = {p.permission for p in admin.permissions}
    support_perms = {p.permission for p in support.permissions}

    assert support_perms.issubset(admin_perms)
    assert "rbac:manage" in admin_perms
    # The split this repo made deliberately is untouched.
    assert "whatsapp:operate" not in admin_perms


def test_a_super_admin_is_still_not_an_agent(db):
    """Deliberate and preserved: a master key is not being on shift.

    ``require_permission`` honours ``*`` so the boss can *read* the queue;
    ``conversations._is_whatsapp_agent`` does not, so the boss is refused at
    the moment of claiming — which is what stops a product parking a customer
    thread on the founder. Granting the support role would have quietly
    removed that property, so it is asserted here.
    """
    role = db.query(Role).filter(Role.slug == "super_admin").one()
    held = {p.permission for p in role.permissions}
    assert "*" in held
    assert "whatsapp:agent" not in held

    boss = User(
        email=f"ops_boss_{uuid.uuid4().hex[:8]}@quatadigital.com",
        full_name="Boss",
        password_hash="x" * 20,
        role_id=role.id,
        is_active=True,
    )
    db.add(boss)
    db.flush()
    assert conv._is_whatsapp_agent(boss) is False
    db.rollback()


def test_the_support_permission_is_the_one_the_console_gates_on(db):
    """One list, not two. ``whatsapp:agent`` must be in the accepted set."""
    assert "whatsapp:agent" in conv.WHATSAPP_AGENT_PERMISSIONS
    role = db.query(Role).filter(Role.slug == "support").one()
    assert {p.permission for p in role.permissions} & conv.WHATSAPP_AGENT_PERMISSIONS
