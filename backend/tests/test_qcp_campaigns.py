"""QCP campaigns: the separation, the consent, the pace and the stop button.

Five properties, and each one is a way a real WhatsApp platform gets its
number restricted rather than a unit test of a function:

1. **A campaign cannot reach Quata Verify.** Not by naming it, not by routing
   to it, not by carrying an authentication template. Asserted at the storage
   layer (the row will not insert) and at the service layer (the refusal names
   the number).
2. **A customer who says STOP is never messaged again** — in English or in
   French, and honoured mid-flight, not only when the audience was built.
3. **It ships inert.** A campaign is created ``draft``; ``start`` refuses
   while QCP is dormant; a running campaign pauses itself if the kill switch
   is pulled underneath it.
4. **It is paced.** A batch is bounded by the campaign's rate, the next batch
   is not due until the clock says so, and the pace survives a restart.
5. **Stop is immediate.** A stop landing between two messages of a batch stops
   *that* batch, not the next one.

The transport is never reached. ``run_once`` takes its ``send`` as a
parameter — the same shape ``templates.sync_from_meta`` takes its ``fetch`` —
so most of these drive a recording stand-in, and the two that need the real
thing call ``dispatch.send`` with ``dispatch=False``: the row is resolved,
routed and persisted for real, and nothing is handed to Meta.

Audience isolation: every test tags its contacts with a unique conversation
locale and filters on it, because the module shares one engagement number and
one session database with everything else in the suite.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.exc import IntegrityError

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
    RECIPIENT_CANCELLED,
    RECIPIENT_OPTED_OUT,
    RECIPIENT_PENDING,
    RECIPIENT_QUEUED,
    RECIPIENT_SUPPRESSED,
    STATUS_DRAFT,
    STATUS_PAUSED,
    STATUS_RUNNING,
    STATUS_STOPPED,
    WhatsAppCampaign,
    WhatsAppCampaignRecipient,
    WhatsAppOptOut,
)

from . import whatsapp_world


def _now() -> datetime:
    return datetime.now(timezone.utc)


# The world's marketing intent: an active engagement rule pointing at an
# approved, marketing-category template on QUATA. Exactly what a campaign is.
CAMPAIGN_INTENT = "promo_weekend"
# The world's trap: the same marketing template, routed to Quata Verify.
VERIFY_INTENT = "promo_on_verify"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def world():
    """Two numbers, one product, three templates — the shared QCP world.

    ``create_all`` runs first: the campaign tables live in
    ``services/whatsapp/campaigns/models.py`` and register on ``Base`` the
    moment this module imports the package.
    """
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
    """Delivery on — the env kill switch and the admin toggle both."""
    whatsapp_world.enable_delivery(monkeypatch, enabled=True)


@pytest.fixture
def dormant(monkeypatch):
    whatsapp_world.enable_delivery(monkeypatch, enabled=False)


@pytest.fixture
def recorder():
    """A stand-in for ``dispatch.send``: records, never touches the network."""

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


def _tag() -> str:
    """A unique conversation locale, used to isolate one test's audience."""
    return f"t{uuid.uuid4().hex[:6]}"


def _contacts(db, world, count: int, tag: str, *, account=None) -> list[str]:
    """Real conversations on a real number — QCP's own audience data."""
    account = account or world.quata
    phones = []
    for i in range(count):
        phone = f"+237{uuid.uuid4().int % 10**9:09d}"
        db.add(
            WhatsAppConversation(
                account_id=account.id,
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


def _draft(db, world, tag: str, **overrides) -> WhatsAppCampaign:
    kwargs = dict(
        name="Weekend promo",
        product=world.product,
        intent=CAMPAIGN_INTENT,
        locale="en",
        audience_source="conversations",
        audience_filters={"state": "open", "locale": tag},
        variables=["50% off"],
        messages_per_minute=60,
    )
    kwargs.update(overrides)
    row = service.create(db, **kwargs)
    db.commit()
    return row


def _armed(db, world, count: int, *, mpm: int = 60) -> tuple[WhatsAppCampaign, list[str]]:
    tag = _tag()
    phones = _contacts(db, world, count, tag)
    campaign = _draft(db, world, tag, messages_per_minute=mpm)
    service.build_audience(db, campaign)
    service.start(db, campaign)
    db.commit()
    return campaign, phones


def _real_send(**kwargs) -> dict:
    """The real send path, stopping short of the transport.

    ``dispatch=False`` means the row is resolved through
    ``routing.resolve_route``, signed into a ticket and persisted exactly as
    any other QCP message — and then not handed off. Everything this package
    is responsible for happens; nothing reaches Meta.
    """
    return dispatch.send(**kwargs, dispatch=False)


# ---------------------------------------------------------------------------
# 1. The separation — a campaign cannot reach Quata Verify
# ---------------------------------------------------------------------------

def test_a_campaign_row_naming_the_verify_number_cannot_be_inserted(world):
    """L1, at rest: the CHECK makes marketing-on-Verify unrepresentable.

    The campaign equivalent of the constraint ``whatsapp_messages`` already
    carries, asserted the same way — by trying it.
    """
    db = SessionLocal()
    try:
        db.add(
            WhatsAppCampaign(
                campaign_uid=uuid.uuid4().hex[:32],
                name="attack",
                product_id=world.product.id,
                intent=CAMPAIGN_INTENT,
                account_id=world.verify.id,
                account_purpose="authentication",
                template_id=world.otp_template.id,
                audience_source="conversations",
                audience_filters={},
                variables=[],
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()
    finally:
        db.rollback()
        db.close()


def test_a_campaign_cannot_be_created_on_an_intent_that_routes_to_verify(db, world):
    """L2: refused before a row is attempted, in a sentence naming the number."""
    with pytest.raises(service.CampaignRefused) as exc:
        service.create(
            db,
            name="Promo on the OTP number",
            product=world.product,
            intent=VERIFY_INTENT,
            locale="en",
            audience_source="conversations",
            audience_filters={},
            variables=["50% off"],
            messages_per_minute=10,
        )
    assert exc.value.reason == "campaign_must_be_engagement"
    assert "Quata Verify" in exc.value.detail


def test_a_campaign_cannot_use_a_template_meta_has_not_approved(db, world):
    """Meta owns approval and nothing in this package can fake it."""
    intent = f"unapproved_{uuid.uuid4().hex[:6]}"
    db.add(
        WhatsAppTemplate(
            account_id=world.quata.id,
            account_purpose="engagement",
            product_id=world.product.id,
            name=f"tp_{intent}",
            language="en",
            category="marketing",
            intent=intent,
            status="pending_approval",
            variables=[],
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

    with pytest.raises(service.CampaignRefused) as exc:
        service.create(
            db,
            name="Too early",
            product=world.product,
            intent=intent,
            locale="en",
            audience_source="conversations",
            audience_filters={},
            variables=[],
            messages_per_minute=10,
        )
    assert exc.value.reason == "template_not_approved"


def test_the_campaign_send_call_names_a_product_and_an_intent_and_nothing_else(
    db, world, live, recorder
):
    """The runner asks for a route, exactly like every other QCP caller.

    If this ever grows a ``phone_number_id`` or a ``template_name``, campaigns
    have stopped crossing ``resolve_route`` and the separation is no longer
    enforced for them.
    """
    campaign, _ = _armed(db, world, 1)
    runner.run_once(db, campaign, send=recorder)

    assert recorder.calls, "nothing was handed off"
    call = recorder.calls[0]
    assert call["product_slug"] == world.product_slug
    assert call["intent"] == CAMPAIGN_INTENT
    assert set(call) == {
        "product_slug",
        "intent",
        "to_phone_e164",
        "variables",
        "kind",
        "locale",
        "reference",
        "idempotency_key",
    }


def test_a_route_that_stops_carrying_traffic_suppresses_rather_than_sends(
    db, world, live
):
    """The send path refuses on its own terms and the campaign reports it.

    The rule is deactivated mid-flight, which is what an operator pulling a
    route out from under a running campaign looks like. Nothing here catches
    it specially: ``dispatch`` returns ``suppressed``/``no_route`` and the
    recipient row records the choke point's own reason code.
    """
    campaign, _ = _armed(db, world, 1)
    rule = (
        db.query(WhatsAppRoutingRule)
        .filter(WhatsAppRoutingRule.product_id == world.product.id)
        .filter(WhatsAppRoutingRule.intent == CAMPAIGN_INTENT)
        .first()
    )
    rule.is_active = False
    db.commit()
    try:
        runner.run_once(db, campaign, send=_real_send)
        row = (
            db.query(WhatsAppCampaignRecipient)
            .filter(WhatsAppCampaignRecipient.campaign_id == campaign.id)
            .first()
        )
        assert row.status == RECIPIENT_SUPPRESSED
        assert row.last_error == "no_route"
    finally:
        rule.is_active = True
        db.commit()


# ---------------------------------------------------------------------------
# 2. Consent
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "text",
    ["STOP", "stop.", " Stop ", "UNSUBSCRIBE", "ARRÊT", "arret", "Désabonner", "ANNULER"],
)
def test_both_languages_are_recognised_as_an_opt_out(text):
    """Cameroon is francophone and anglophone. So is this keyword list."""
    assert consent.matched_stop_word(text) is not None


@pytest.mark.parametrize(
    "text",
    [
        "please don't stop sending me offers",
        "stop by the shop tomorrow",
        "je ne veux pas arreter mes commandes",
        "",
        None,
    ],
)
def test_a_message_that_merely_contains_a_stop_word_is_not_an_opt_out(text):
    """Exact match, not substring: the opposite error shrinks audiences silently."""
    assert consent.matched_stop_word(text) is None


def test_an_inbound_stop_becomes_an_opt_out_without_touching_the_webhook(db, world):
    """The evidence is already in ``whatsapp_messages``; the sweep reads it."""
    phone = f"+237{uuid.uuid4().int % 10**9:09d}"
    db.add(
        WhatsAppMessage(
            message_uid=uuid.uuid4().hex[:32],
            account_id=world.quata.id,
            account_purpose="engagement",
            direction="inbound",
            kind="text",
            from_phone_e164=phone,
            body="STOP",
            status="delivered",
        )
    )
    db.commit()

    result = consent.sweep(db)
    db.commit()
    assert result["opted_out"] >= 1
    assert consent.is_opted_out(db, phone) is True


def test_an_opt_out_is_idempotent_and_never_becomes_a_second_row(db):
    phone = f"+237{uuid.uuid4().int % 10**9:09d}"
    _, first = consent.record(db, phone, source="admin")
    _, second = consent.record(db, phone, source="admin")
    db.commit()
    assert (first, second) == (True, False)
    assert (
        db.query(WhatsAppOptOut).filter(WhatsAppOptOut.phone_e164 == phone).count() == 1
    )


def test_an_opted_out_contact_is_left_out_of_a_new_audience(db, world):
    tag = _tag()
    phones = _contacts(db, world, 3, tag)
    consent.record(db, phones[0], source="admin")
    db.commit()

    campaign = _draft(db, world, tag)
    service.build_audience(db, campaign)
    db.commit()

    built = {
        row.phone_e164
        for row in db.query(WhatsAppCampaignRecipient).filter(
            WhatsAppCampaignRecipient.campaign_id == campaign.id
        )
    }
    assert phones[0] not in built
    assert {phones[1], phones[2]} <= built


def test_a_stop_that_arrives_mid_campaign_is_honoured_before_the_next_message(
    db, world, live, recorder
):
    """The one that matters: consent is re-checked immediately before each send.

    An audience built before the customer replied must not keep sending to
    them. The runner sweeps inbound messages at the top of every batch and
    checks the opt-out list again per recipient.
    """
    tag = _tag()
    phones = _contacts(db, world, 4, tag)
    campaign = _draft(db, world, tag, messages_per_minute=6)  # one per batch
    service.build_audience(db, campaign)
    service.start(db, campaign)
    db.commit()

    runner.run_once(db, campaign, send=recorder)
    assert len(recorder.calls) == 1

    # The second contact replies, in French, exactly as they would.
    db.add(
        WhatsAppMessage(
            message_uid=uuid.uuid4().hex[:32],
            account_id=world.quata.id,
            account_purpose="engagement",
            direction="inbound",
            kind="text",
            from_phone_e164=phones[1],
            body="arrêt",
            status="delivered",
        )
    )
    db.commit()

    for _ in range(2):
        campaign.next_batch_at = _now() - timedelta(seconds=1)
        db.commit()
        runner.run_once(db, campaign, send=recorder)

    assert phones[1] not in [call["to_phone_e164"] for call in recorder.calls]
    skipped = (
        db.query(WhatsAppCampaignRecipient)
        .filter(WhatsAppCampaignRecipient.campaign_id == campaign.id)
        .filter(WhatsAppCampaignRecipient.phone_e164 == phones[1])
        .first()
    )
    assert skipped.status == RECIPIENT_OPTED_OUT


# ---------------------------------------------------------------------------
# 3. It ships inert
# ---------------------------------------------------------------------------

def test_a_new_campaign_is_a_draft(db, world):
    campaign = _draft(db, world, _tag())
    assert campaign.status == STATUS_DRAFT
    assert campaign.started_at is None


def test_a_campaign_cannot_start_while_qcp_is_dormant(db, world, dormant):
    """The ship-inert rule, stated where an operator meets it."""
    tag = _tag()
    _contacts(db, world, 2, tag)
    campaign = _draft(db, world, tag)
    service.build_audience(db, campaign)
    db.commit()

    with pytest.raises(service.CampaignRefused) as exc:
        service.start(db, campaign)
    assert exc.value.reason == "delivery_disabled"
    assert campaign.status == STATUS_DRAFT


def test_pulling_the_kill_switch_pauses_a_running_campaign(
    db, world, monkeypatch, recorder
):
    """Dormancy is re-checked before every batch, not only at start."""
    whatsapp_world.enable_delivery(monkeypatch, enabled=True)
    campaign, _ = _armed(db, world, 3, mpm=6)

    whatsapp_world.enable_delivery(monkeypatch, enabled=False)
    result = runner.run_once(db, campaign, send=recorder)

    assert result.get("paused") == "delivery_disabled"
    assert recorder.calls == []
    assert campaign.status == STATUS_PAUSED


def test_a_campaign_with_no_audience_cannot_be_armed(db, world, live):
    campaign = _draft(db, world, _tag())
    with pytest.raises(service.CampaignRefused) as exc:
        service.start(db, campaign)
    assert exc.value.reason == "empty_audience"


# ---------------------------------------------------------------------------
# 4. Pace
# ---------------------------------------------------------------------------

def test_a_batch_is_bounded_by_the_campaigns_rate(db, world, live, recorder):
    """60 a minute is ten per ten-second batch, not the whole audience at once."""
    campaign, _ = _armed(db, world, 25, mpm=60)

    runner.run_once(db, campaign, send=recorder)
    assert runner.batch_size(60) == 10
    assert len(recorder.calls) == 10

    # The next batch is not due yet, so a second tick sends nothing at all.
    second = runner.run_once(db, campaign, send=recorder)
    assert second.get("paced") is True
    assert len(recorder.calls) == 10


def test_the_pace_survives_a_restart_because_it_is_stored_on_the_row(
    db, world, live, recorder
):
    """``next_batch_at`` is a column, not a worker's memory: no burst on reboot."""
    campaign, _ = _armed(db, world, 5, mpm=6)

    runner.run_once(db, campaign, send=recorder)
    assert campaign.next_batch_at is not None

    fresh = SessionLocal()
    try:
        reloaded = service.get(fresh, campaign.campaign_uid)
        assert runner.run_once(fresh, reloaded, send=recorder).get("paced") is True
    finally:
        fresh.close()
    assert len(recorder.calls) == 1


def test_the_send_rate_ceiling_is_enforced(db, world):
    with pytest.raises(service.CampaignRefused) as exc:
        _draft(db, world, _tag(), messages_per_minute=5000)
    assert exc.value.reason == "invalid_rate"


# ---------------------------------------------------------------------------
# 5. Stop
# ---------------------------------------------------------------------------

def test_stop_halts_a_batch_between_two_messages(db, world, live):
    """Stop is checked per message: a batch in flight does not finish.

    The stop lands from a *second session*, part-way through the batch —
    which is exactly what a console click looks like to a running worker.
    """
    campaign, _ = _armed(db, world, 10, mpm=60)
    uid = campaign.campaign_uid
    calls: list[str] = []

    def stopping_send(**kwargs):
        calls.append(kwargs["to_phone_e164"])
        if len(calls) == 1:
            other = SessionLocal()
            try:
                service.stop(other, service.get(other, uid), reason="wrong audience")
                other.commit()
            finally:
                other.close()
        return {
            "ok": True,
            "status": "queued",
            "duplicate": False,
            "message_uid": uuid.uuid4().hex[:32],
        }

    result = runner.run_once(db, campaign, send=stopping_send)

    assert len(calls) == 1, f"stop did not halt the batch: {calls}"
    assert result["stopped_mid_batch"] is True

    db.expire_all()
    row = service.get(db, uid)
    assert row.status == STATUS_STOPPED
    assert row.stop_reason == "wrong audience"

    def _count(status: str) -> int:
        return (
            db.query(WhatsAppCampaignRecipient)
            .filter(WhatsAppCampaignRecipient.campaign_id == row.id)
            .filter(WhatsAppCampaignRecipient.status == status)
            .count()
        )

    assert _count(RECIPIENT_PENDING) == 0
    assert _count(RECIPIENT_CANCELLED) == 9
    assert _count(RECIPIENT_QUEUED) == 1


def test_stopping_twice_is_not_an_error(db, world, live):
    tag = _tag()
    _contacts(db, world, 2, tag)
    campaign = _draft(db, world, tag)
    service.build_audience(db, campaign)
    db.commit()

    first = service.stop(db, campaign, reason="mistake")
    db.commit()
    second = service.stop(db, campaign, reason="mistake")
    db.commit()

    assert first["already_stopped"] is False
    assert second["already_stopped"] is True
    assert campaign.status == STATUS_STOPPED


def test_a_stopped_campaign_can_never_be_restarted(db, world, live):
    tag = _tag()
    _contacts(db, world, 2, tag)
    campaign = _draft(db, world, tag)
    service.build_audience(db, campaign)
    service.stop(db, campaign)
    db.commit()

    with pytest.raises(service.CampaignRefused) as exc:
        service.start(db, campaign)
    assert exc.value.reason == "campaign_finished"


# ---------------------------------------------------------------------------
# 6. Results, and the real send path
# ---------------------------------------------------------------------------

def test_results_are_read_from_the_message_log_not_copied(db, world, live):
    """"Sent" on a campaign screen is the message log's own fact."""
    campaign, _ = _armed(db, world, 2, mpm=60)
    runner.run_once(db, campaign, send=_real_send)

    stats = service.results(db, campaign)
    assert stats["audience"] == 2
    assert stats["pending"] == 0
    assert stats["opted_out"] == 0
    # `dispatch=False` leaves the rows in the outbox, which is what the
    # message log says and therefore what the campaign reports.
    assert stats["queued"] == 2
    assert stats["sent"] == 0


def test_the_real_send_path_produces_ordinary_messages_on_the_engagement_number(
    db, world, live
):
    """A campaign is not a second send path: the rows are QCP's normal rows.

    They carry the campaign's uid in ``whatsapp_messages.campaign_id`` — the
    seam that column has been reserved for since the platform was built, and
    whose first writer this is.
    """
    campaign, _ = _armed(db, world, 2, mpm=60)
    runner.run_once(db, campaign, send=_real_send)

    rows = (
        db.query(WhatsAppMessage)
        .filter(WhatsAppMessage.campaign_id == campaign.campaign_uid)
        .all()
    )
    assert len(rows) == 2
    for row in rows:
        assert row.account_purpose == "engagement"
        assert row.account_id == world.quata.id
        assert row.template_id == world.promo_template.id
        assert row.kind == "template"


def test_a_replayed_batch_cannot_message_the_same_person_twice(db, world, live):
    """The idempotency key is derived from (campaign, phone): a rerun is inert."""
    campaign, _ = _armed(db, world, 2, mpm=60)
    runner.run_once(db, campaign, send=_real_send)

    def _messages() -> int:
        return (
            db.query(WhatsAppMessage)
            .filter(WhatsAppMessage.campaign_id == campaign.campaign_uid)
            .count()
        )

    before = _messages()
    assert before == 2

    # Put every recipient back to pending — the shape a crash mid-batch leaves
    # behind — and run the campaign again.
    db.query(WhatsAppCampaignRecipient).filter(
        WhatsAppCampaignRecipient.campaign_id == campaign.id
    ).update(
        {WhatsAppCampaignRecipient.status: RECIPIENT_PENDING}, synchronize_session=False
    )
    campaign.status = STATUS_RUNNING
    campaign.next_batch_at = _now() - timedelta(seconds=60)
    db.commit()

    runner.run_once(db, campaign, send=_real_send)
    assert _messages() == 2


# ---------------------------------------------------------------------------
# 7. Audience
# ---------------------------------------------------------------------------

def test_an_unknown_audience_filter_is_refused_rather_than_ignored(db, world):
    """A mistyped filter that silently widens an audience is the failure mode."""
    with pytest.raises(service.CampaignRefused) as exc:
        _draft(db, world, _tag(), audience_filters={"inbound_within_day": 30})
    assert exc.value.reason == "unknown_audience_filter"


def test_an_audience_is_never_built_from_the_verification_number(db, world):
    """Contacts of Quata Verify are people who received a login code."""
    tag = _tag()
    engagement = _contacts(db, world, 1, tag)
    verify_only = _contacts(db, world, 1, tag, account=world.verify)

    campaign = _draft(db, world, tag)
    service.build_audience(db, campaign)
    db.commit()

    built = {
        row.phone_e164
        for row in db.query(WhatsAppCampaignRecipient).filter(
            WhatsAppCampaignRecipient.campaign_id == campaign.id
        )
    }
    assert built == set(engagement)
    assert verify_only[0] not in built


def test_an_audience_cannot_be_re_aimed_once_the_campaign_is_running(db, world, live):
    campaign, _ = _armed(db, world, 2)
    with pytest.raises(service.CampaignRefused) as exc:
        service.build_audience(db, campaign)
    assert exc.value.reason == "campaign_not_editable"
