"""Three ways a QCP campaign could still hurt the fleet's two Meta numbers.

``test_qcp_campaigns`` covers what a campaign *is*. This module covers three
holes in what a campaign *does while it runs*, each of which ends the same
way — a Meta restriction on a number that carries the login code for every
product in the fleet, and QuataFood's OTP has no email fallback.

1. **A campaign follows a routing change.** The campaign *row* is pinned to
   the engagement number and cannot be written otherwise, but the messages
   are not: ``dispatch`` re-resolves the route per message. An admin who
   repoints an intent, or activates a rule that outranks the old one, moves a
   running campaign onto whatever number the new rule names — Quata Verify
   included — and nothing downstream objects, because an authentication
   template on the authentication number is a legal send by every rule in
   ``routing``. It is wrong only because a *campaign* is behind it.

2. **Opt-out was never checked at the moment of sending.** It is checked when
   the audience is built and again when the runner hands a message to
   ``dispatch`` — but a queued message is not a sent message. It waits in the
   outbox, and a failed one comes back on a backoff. Someone who says STOP in
   that window said stop before the message left.

3. **Nothing counted a person's messages across senders.** One message per
   person per campaign was the only limit, so three campaigns over
   overlapping audiences meant three messages in a day, and an order update
   on top of them meant four.

The transport is never reached: the tests that need the real send path call
``dispatch.send`` with ``dispatch=False``, so a row is resolved, routed,
signed and persisted for real and nothing is handed to Meta.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.db.session import SessionLocal, engine
from app.models import (
    Base,
    WhatsAppConversation,
    WhatsAppMessage,
    WhatsAppRoutingRule,
    WhatsAppTemplate,
)
from app.services.whatsapp import dispatch
from app.services.whatsapp.campaigns import consent, runner, service
from app.services.whatsapp.campaigns.models import (
    MAX_MESSAGES_PER_PERSON_PER_DAY,
    RECIPIENT_CANCELLED,
    RECIPIENT_PENDING,
    RECIPIENT_QUEUED,
    RECIPIENT_SUPPRESSED,
    STATUS_PAUSED,
    STATUS_STOPPED,
    WhatsAppCampaign,
    WhatsAppCampaignRecipient,
)

from . import whatsapp_world


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Fixtures — the same world the rest of the campaign suite uses
# ---------------------------------------------------------------------------

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


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def live(monkeypatch):
    whatsapp_world.enable_delivery(monkeypatch, enabled=True)


@pytest.fixture
def recorder():
    class Recorder:
        def __init__(self) -> None:
            self.calls: list[dict] = []

        def __call__(self, **kwargs):
            self.calls.append(kwargs)
            return {
                "ok": True,
                "status": "queued",
                "duplicate": False,
                "message_uid": uuid.uuid4().hex[:32],
            }

    return Recorder()


def _real_send(**kwargs) -> dict:
    """The real send path, stopping short of the transport."""
    return dispatch.send(**kwargs, dispatch=False)


def _tag() -> str:
    return f"g{uuid.uuid4().hex[:6]}"


def _contacts(db, world, count: int, tag: str) -> list[str]:
    phones = []
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


def _own_route(db, world) -> str:
    """An intent belonging to this test: one marketing template, one live rule.

    Owning the rule is the point — these tests move it, and moving the shared
    world's rule would move it under every other module in the suite.
    """
    intent = f"promo_{uuid.uuid4().hex[:8]}"
    db.add(
        WhatsAppTemplate(
            account_id=world.quata.id,
            account_purpose="engagement",
            product_id=world.product.id,
            name=f"tp_{intent}",
            language="en",
            category="marketing",
            intent=intent,
            status="approved",
            variables=["offer"],
        )
    )
    db.add(
        WhatsAppRoutingRule(
            product_id=world.product.id,
            intent=intent,
            purpose="engagement",
            template_intent=intent,
            locale=None,
            priority=100,
            is_active=True,
            conditions={},
        )
    )
    db.commit()
    return intent


def _rule(db, world, intent: str) -> WhatsAppRoutingRule:
    return (
        db.query(WhatsAppRoutingRule)
        .filter(WhatsAppRoutingRule.product_id == world.product.id)
        .filter(WhatsAppRoutingRule.intent == intent)
        .filter(WhatsAppRoutingRule.locale.is_(None))
        .first()
    )


def _armed(db, world, count: int, *, intent: str, mpm: int = 60):
    tag = _tag()
    phones = _contacts(db, world, count, tag)
    campaign = service.create(
        db,
        name="Weekend promo",
        product=world.product,
        intent=intent,
        locale="en",
        audience_source="conversations",
        audience_filters={"state": "open", "locale": tag},
        variables=["50% off"],
        messages_per_minute=mpm,
    )
    db.commit()
    service.build_audience(db, campaign)
    service.start(db, campaign)
    db.commit()
    return campaign, phones


def _repoint_at_verify(db, world, intent: str) -> None:
    """The ordinary admin action: this intent now goes out on Quata Verify.

    ``template_intent`` moves with it, to the authentication template that
    number carries — which is what makes the resulting send *legal* to every
    check in ``routing`` and therefore invisible without a campaign-level
    guard. The campaign's one variable lands in the slot a login code
    normally occupies.
    """
    rule = _rule(db, world, intent)
    rule.purpose = "authentication"
    rule.template_intent = world.otp_template.intent
    db.commit()


def _campaign_messages(db, campaign) -> list[WhatsAppMessage]:
    return (
        db.query(WhatsAppMessage)
        .filter(WhatsAppMessage.campaign_id == campaign.campaign_uid)
        .all()
    )


def _recipients(db, campaign, status: str) -> int:
    return (
        db.query(WhatsAppCampaignRecipient)
        .filter(WhatsAppCampaignRecipient.campaign_id == campaign.id)
        .filter(WhatsAppCampaignRecipient.status == status)
        .count()
    )


# ---------------------------------------------------------------------------
# 1. A routing change must not carry a running campaign onto Quata Verify
# ---------------------------------------------------------------------------

def test_a_repointed_intent_never_puts_a_campaign_message_on_verify(db, world, live):
    """The whole hole, end to end, through the real send path.

    Nothing is deactivated and nothing is invalid: after the edit,
    ``resolve_route`` happily mints a ticket for an approved authentication
    template on the authentication number. The only thing that knows it is
    wrong is the campaign, which was created against the marketing number.
    """
    intent = _own_route(db, world)
    campaign, _ = _armed(db, world, 3, intent=intent)

    _repoint_at_verify(db, world, intent)
    runner.run_once(db, campaign, send=_real_send)

    on_verify = [m for m in _campaign_messages(db, campaign) if m.account_id == world.verify.id]
    assert on_verify == [], (
        f"{len(on_verify)} campaign message(s) reached Quata Verify — the number "
        "that carries the fleet's login codes"
    )


def test_a_repointed_intent_halts_the_whole_campaign_with_a_readable_reason(
    db, world, live, recorder
):
    """Halted, not skipped. Every remaining message is equally wrong."""
    intent = _own_route(db, world)
    campaign, _ = _armed(db, world, 5, intent=intent)

    _repoint_at_verify(db, world, intent)
    result = runner.run_once(db, campaign, send=recorder)

    assert recorder.calls == [], "the campaign kept sending after routing moved"
    db.expire_all()
    row = service.get(db, campaign.campaign_uid)
    assert row.status == STATUS_STOPPED
    assert result.get("halted") == "route_changed"
    # An admin has to be able to read what happened without opening a log.
    assert "Quata Verify" in (row.stop_reason or "") + (row.last_error or "")
    assert _recipients(db, row, RECIPIENT_PENDING) == 0
    assert _recipients(db, row, RECIPIENT_CANCELLED) == 5


def test_a_newly_activated_rule_that_outranks_the_old_one_halts_the_campaign(
    db, world, live, recorder
):
    """The second way in: nobody edited the campaign's rule at all.

    A more specific rule is activated for the locale the campaign runs in.
    ``routing`` prefers it, so the campaign silently follows it.
    """
    intent = _own_route(db, world)
    campaign, _ = _armed(db, world, 3, intent=intent)

    db.add(
        WhatsAppRoutingRule(
            product_id=world.product.id,
            intent=intent,
            purpose="authentication",
            template_intent=world.otp_template.intent,
            locale="en",
            priority=1,
            is_active=True,
            conditions={},
        )
    )
    db.commit()

    result = runner.run_once(db, campaign, send=recorder)

    assert recorder.calls == []
    assert result.get("halted") == "route_changed"
    db.expire_all()
    assert service.get(db, campaign.campaign_uid).status == STATUS_STOPPED


def test_the_route_is_re_checked_between_two_messages_of_one_batch(db, world, live):
    """Per message, like the stop button — not once per batch.

    The edit lands from a second session part-way through a batch, which is
    what an admin saving the Routing screen looks like to a running worker.
    """
    intent = _own_route(db, world)
    campaign, _ = _armed(db, world, 6, intent=intent, mpm=60)
    calls: list[str] = []

    def repointing_send(**kwargs):
        calls.append(kwargs["to_phone_e164"])
        if len(calls) == 1:
            other = SessionLocal()
            try:
                _repoint_at_verify(other, world, intent)
            finally:
                other.close()
        return {
            "ok": True,
            "status": "queued",
            "duplicate": False,
            "message_uid": uuid.uuid4().hex[:32],
        }

    runner.run_once(db, campaign, send=repointing_send)

    assert len(calls) == 1, f"the batch ran on after routing moved: {calls}"
    db.expire_all()
    row = service.get(db, campaign.campaign_uid)
    assert row.status == STATUS_STOPPED
    assert _recipients(db, row, RECIPIENT_CANCELLED) == 5


def test_a_paused_campaign_whose_route_moved_cannot_be_resumed(db, world, live):
    """The pause/resume path is the same door, opened later."""
    intent = _own_route(db, world)
    campaign, _ = _armed(db, world, 2, intent=intent)
    service.pause(db, campaign, reason="operator")
    db.commit()
    assert campaign.status == STATUS_PAUSED

    _repoint_at_verify(db, world, intent)

    with pytest.raises(service.CampaignRefused) as exc:
        service.start(db, campaign)
    assert exc.value.reason == "route_changed"


def test_an_unchanged_route_is_not_treated_as_a_change(db, world, live, recorder):
    """The guard must not halt an ordinary campaign — it would ship inert."""
    intent = _own_route(db, world)
    campaign, phones = _armed(db, world, 3, intent=intent)

    result = runner.run_once(db, campaign, send=recorder)

    assert sorted(c["to_phone_e164"] for c in recorder.calls) == sorted(phones)
    assert result.get("halted") is None


# ---------------------------------------------------------------------------
# 2. Opt-out, checked at the moment of sending
# ---------------------------------------------------------------------------

def test_a_queued_campaign_message_never_leaves_after_the_person_opts_out(
    db, world, live
):
    """The last check is the one that counts.

    The message is in the outbox, not on the wire. A worker — or a retry
    hours later — would still deliver it, and the customer would receive a
    marketing message after asking to stop, which is precisely the report
    that gets a number restricted.
    """
    intent = _own_route(db, world)
    campaign, phones = _armed(db, world, 1, intent=intent)
    runner.run_once(db, campaign, send=_real_send)

    queued = _campaign_messages(db, campaign)
    assert len(queued) == 1 and queued[0].status == "queued"

    consent.record(db, phones[0], source="admin")
    db.commit()

    db.expire_all()
    row = _campaign_messages(db, campaign)[0]
    assert row.status == "suppressed", "an opted-out person's message was still deliverable"
    assert row.suppressed_reason == "opted_out"
    assert row.next_attempt_at is None


def test_an_inbound_stop_stops_a_message_that_is_already_queued(db, world, live):
    """The customer's own word, through the sweep, reaching the outbox."""
    intent = _own_route(db, world)
    campaign, phones = _armed(db, world, 1, intent=intent)
    runner.run_once(db, campaign, send=_real_send)

    db.add(
        WhatsAppMessage(
            message_uid=uuid.uuid4().hex[:32],
            account_id=world.quata.id,
            account_purpose="engagement",
            direction="inbound",
            kind="text",
            from_phone_e164=phones[0],
            body="ARRÊT",
            status="delivered",
        )
    )
    db.commit()

    consent.sweep(db)
    db.commit()

    db.expire_all()
    row = _campaign_messages(db, campaign)[0]
    assert row.status == "suppressed"
    assert row.suppressed_reason == "opted_out"


def test_an_opt_out_never_touches_a_message_that_is_not_a_campaign(db, world, live):
    """A login code is not marketing and an opt-out must not cancel one.

    The customer asked the marketing to stop. Suppressing their own PIN reset
    because of it would be this package overreaching into the send path it
    does not own.
    """
    phone = f"+237{uuid.uuid4().int % 10**9:09d}"
    otp = WhatsAppMessage(
        message_uid=uuid.uuid4().hex[:32],
        account_id=world.verify.id,
        account_purpose="authentication",
        product_id=world.product.id,
        template_id=world.otp_template.id,
        direction="outbound",
        kind="template",
        intent="login_otp",
        to_phone_e164=phone,
        status="queued",
        next_attempt_at=_now(),
    )
    db.add(otp)
    db.commit()

    consent.record(db, phone, source="admin")
    db.commit()

    db.refresh(otp)
    assert otp.status == "queued"


# ---------------------------------------------------------------------------
# 3. Three messages per person per rolling day, counted across every sender
# ---------------------------------------------------------------------------

def _already_messaged(db, world, phone: str, count: int, *, age_hours: int = 1) -> None:
    """Messages this person has already had, from senders that are not us."""
    when = _now() - timedelta(hours=age_hours)
    for i in range(count):
        db.add(
            WhatsAppMessage(
                message_uid=uuid.uuid4().hex[:32],
                account_id=world.quata.id,
                account_purpose="engagement",
                product_id=world.product.id,
                direction="outbound",
                kind="text",
                intent="support_reply",
                to_phone_e164=phone,
                status="sent",
                # Someone else's send: an order update, a support reply, or
                # another campaign entirely.
                campaign_id=uuid.uuid4().hex[:32] if i == 0 else None,
                created_at=when,
            )
        )
    db.commit()


def test_a_person_at_the_daily_cap_is_left_out_and_everyone_else_is_not(
    db, world, live, recorder
):
    """Three in twenty-four hours is the fleet's ceiling, counted everywhere.

    The prior messages here are not campaign sends — one carries another
    campaign's id, the rest carry none at all. A cap that only counted this
    campaign's own sends would let all four through.
    """
    intent = _own_route(db, world)
    tag = _tag()
    phones = _contacts(db, world, 2, tag)
    _already_messaged(db, world, phones[0], MAX_MESSAGES_PER_PERSON_PER_DAY)
    _already_messaged(db, world, phones[1], MAX_MESSAGES_PER_PERSON_PER_DAY - 1)

    campaign = service.create(
        db,
        name="Weekend promo",
        product=world.product,
        intent=intent,
        locale="en",
        audience_source="conversations",
        audience_filters={"state": "open", "locale": tag},
        variables=["50% off"],
        messages_per_minute=60,
    )
    db.commit()
    service.build_audience(db, campaign)
    service.start(db, campaign)
    db.commit()

    runner.run_once(db, campaign, send=recorder)

    assert [c["to_phone_e164"] for c in recorder.calls] == [phones[1]]
    capped = (
        db.query(WhatsAppCampaignRecipient)
        .filter(WhatsAppCampaignRecipient.campaign_id == campaign.id)
        .filter(WhatsAppCampaignRecipient.phone_e164 == phones[0])
        .first()
    )
    assert capped.status == RECIPIENT_SUPPRESSED
    assert capped.last_error == "daily_cap_reached"


def test_the_cap_window_rolls_so_yesterdays_messages_do_not_block_today(
    db, world, live, recorder
):
    """A ceiling that never forgets is a permanent block, not a daily cap."""
    intent = _own_route(db, world)
    tag = _tag()
    phones = _contacts(db, world, 1, tag)
    _already_messaged(
        db, world, phones[0], MAX_MESSAGES_PER_PERSON_PER_DAY, age_hours=25
    )

    campaign = service.create(
        db,
        name="Weekend promo",
        product=world.product,
        intent=intent,
        locale="en",
        audience_source="conversations",
        audience_filters={"state": "open", "locale": tag},
        variables=["50% off"],
        messages_per_minute=60,
    )
    db.commit()
    service.build_audience(db, campaign)
    service.start(db, campaign)
    db.commit()

    runner.run_once(db, campaign, send=recorder)
    assert [c["to_phone_e164"] for c in recorder.calls] == phones


def test_three_campaigns_in_a_day_are_the_cap_and_a_fourth_is_refused(
    db, world, live
):
    """The reported scenario, run for real: overlapping audiences, one day.

    Each campaign obeys "one message per person per campaign" and none of
    them can see the others. The cap is what counts them.
    """
    intent = _own_route(db, world)
    tag = _tag()
    phone = _contacts(db, world, 1, tag)[0]

    def _run() -> WhatsAppCampaign:
        campaign = service.create(
            db,
            name="Weekend promo",
            product=world.product,
            intent=intent,
            locale="en",
            audience_source="conversations",
            audience_filters={"state": "open", "locale": tag},
            variables=["50% off"],
            messages_per_minute=60,
        )
        db.commit()
        service.build_audience(db, campaign)
        service.start(db, campaign)
        db.commit()
        runner.run_once(db, campaign, send=_real_send)
        return campaign

    sent = [_run() for _ in range(MAX_MESSAGES_PER_PERSON_PER_DAY)]
    for campaign in sent:
        assert _recipients(db, campaign, RECIPIENT_QUEUED) == 1

    fourth = _run()
    assert _recipients(db, fourth, RECIPIENT_QUEUED) == 0
    assert _recipients(db, fourth, RECIPIENT_SUPPRESSED) == 1
    assert (
        db.query(WhatsAppMessage)
        .filter(WhatsAppMessage.campaign_id == fourth.campaign_uid)
        .count()
        == 0
    ), "a fourth message was written for a person already at the daily cap"
