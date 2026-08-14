"""The campaign lifecycle: draft → scheduled → running → stopped/completed.

Every state change in this module is one verb, audited, and refuses rather
than raises. Four properties shape all of it.

**A campaign starts as a draft and nothing here can change that.** ``create``
writes ``status='draft'`` unconditionally; there is no ``status`` parameter,
no "create and send", and no route that composes the two. The same rule the
rest of QCP holds — new templates land ``draft``, new routing rules land
inactive, new accounts land inactive — applied to the one object in the
platform whose whole purpose is to message thousands of people at once.

**Nothing here can send while QCP is dormant.** ``start`` refuses when
``settings_store.delivery_enabled()`` is false, and refuses again if the
product is disabled or the route no longer resolves. The runner re-checks
dormancy before every batch and pauses a campaign mid-flight if the fleet
kill switch is pulled. Dormancy is not a state a campaign can be prepared
around.

**A campaign is routed, not addressed.** ``create`` never picks a phone
number id, a token or a template name. It names a product and an intent, the
same two things a QuataFood order update names, and the send crosses
``routing.resolve_route`` exactly like every other message in QCP. That is
why marketing cannot reach Quata Verify from here: it is not this module's
rule, it is L1 through L4, and this module deliberately does not have its own
opinion that could drift from them. What ``create`` *does* do is resolve the
route once, up front, so an operator finds out that their template is not
approved while they are drafting rather than after pressing send.

**Stop is the important verb.** It is available from every non-terminal
state, it needs no confirmation from anything but the operator, it cancels
every recipient that has not been handed off, and the runner re-reads the
campaign's status before every individual message. See ``stop``.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import (
    WhatsAppAccount,
    WhatsAppMessage,
    WhatsAppProduct,
    WhatsAppRoutingRule,
    WhatsAppTemplate,
)

from .. import audit, settings_store
from . import audience as audience_service
from . import consent
from .models import (
    CAMPAIGN_STATUSES,
    DEFAULT_MESSAGES_PER_MINUTE,
    MAX_MESSAGES_PER_MINUTE,
    PURPOSE_ENGAGEMENT,
    RECIPIENT_CANCELLED,
    RECIPIENT_OPTED_OUT,
    RECIPIENT_PENDING,
    RECIPIENT_QUEUED,
    STATUS_COMPLETED,
    STATUS_DRAFT,
    STATUS_PAUSED,
    STATUS_RUNNING,
    STATUS_SCHEDULED,
    STATUS_STOPPED,
    WhatsAppCampaign,
    WhatsAppCampaignRecipient,
)


# States from which a campaign can still be edited or rebuilt.
EDITABLE_STATUSES = (STATUS_DRAFT, STATUS_SCHEDULED)
# States from which it can be started or resumed.
STARTABLE_STATUSES = (STATUS_DRAFT, STATUS_SCHEDULED, STATUS_PAUSED)
# Terminal. Nothing moves out of these.
TERMINAL_STATUSES = (STATUS_STOPPED, STATUS_COMPLETED)

# The one category a campaign may never carry, restated here only so the
# refusal names it. The database already refuses the row.
CATEGORY_AUTHENTICATION = "authentication"


class CampaignRefused(Exception):
    """A stated refusal: a stable code and a sentence naming the next action."""

    def __init__(self, reason: str, detail: str) -> None:
        super().__init__(reason)
        self.reason = reason
        self.detail = detail


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Route resolution — done at create time so refusals arrive early
# ---------------------------------------------------------------------------

def engagement_account(db: Session) -> Optional[WhatsAppAccount]:
    """The live QUATA number, or None. The only number a campaign may use."""
    return (
        db.query(WhatsAppAccount)
        .filter(WhatsAppAccount.purpose == PURPOSE_ENGAGEMENT)
        .filter(WhatsAppAccount.is_active == True)  # noqa: E712
        .order_by(WhatsAppAccount.id)
        .first()
    )


def _active_rule(
    db: Session, *, product_id: int, intent: str, locale: Optional[str]
) -> Optional[WhatsAppRoutingRule]:
    """The rule ``routing`` would pick for this intent, chosen the same way.

    Same ordering (priority, then id) and the same locale preference — an
    exact locale match beats the any-locale rule. Shared by ``resolve_plan``
    and ``current_route_account`` so a campaign's idea of *which rule* cannot
    drift from the send path's.
    """
    rules = (
        db.query(WhatsAppRoutingRule)
        .filter(WhatsAppRoutingRule.product_id == product_id)
        .filter(WhatsAppRoutingRule.intent == intent)
        .filter(WhatsAppRoutingRule.is_active == True)  # noqa: E712
        .order_by(WhatsAppRoutingRule.priority, WhatsAppRoutingRule.id)
        .all()
    )
    rule = None
    if locale:
        rule = next((r for r in rules if r.locale == locale), None)
    if rule is None:
        rule = next((r for r in rules if r.locale in (None, "")), None)
    return rule


def current_route_account(
    db: Session, campaign: WhatsAppCampaign
) -> Optional[WhatsAppAccount]:
    """The number this campaign's intent resolves to *right now*, or None.

    Deliberately not ``resolve_plan``: this has to answer "which number" even
    when the answer is one a campaign may never use, because that is the case
    it exists to catch. None means the intent no longer resolves to a live
    number at all — a deactivated rule, a conditional one, a number switched
    off — which ``dispatch`` already refuses per message with its own reason
    code, and which is therefore not this function's business.
    """
    rule = _active_rule(
        db,
        product_id=campaign.product_id,
        intent=campaign.intent,
        locale=campaign.locale,
    )
    if rule is None or (rule.conditions or {}):
        return None
    return (
        db.query(WhatsAppAccount)
        .filter(WhatsAppAccount.purpose == rule.purpose)
        .filter(WhatsAppAccount.is_active == True)  # noqa: E712
        .order_by(WhatsAppAccount.id)
        .first()
    )


def assert_route_unchanged(db: Session, campaign: WhatsAppCampaign) -> None:
    """Refuse unless the route still lands on the number this campaign names.

    The campaign *row* is pinned to the engagement number and the composite
    FK plus the CHECK make it unrepresentable otherwise. The **messages** are
    not pinned: ``dispatch`` re-resolves the route for every one of them. So
    two ordinary admin actions — repointing an intent at the other number, or
    activating a rule that outranks the one the campaign was drafted against
    — move a *running* campaign onto whatever number the new rule names,
    Quata Verify included.

    Nothing downstream objects to that, and it is important to be clear about
    why: an approved authentication template on the authentication number is
    a legal send by every rule in ``routing``, at L1, L2, L3 and L4. What
    makes it wrong is that a marketing campaign is behind it, and the only
    thing that knows a campaign is behind it is the campaign. Hence this
    check, here, rather than one more rule in the choke point.
    """
    account = current_route_account(db, campaign)
    if account is None:
        return
    if account.id == campaign.account_id and account.purpose == campaign.account_purpose:
        return

    pinned = db.get(WhatsAppAccount, campaign.account_id)
    raise CampaignRefused(
        "route_changed",
        f"{campaign.intent} now goes out on {account.name} ({account.purpose}), not "
        f"{pinned.name if pinned else 'the number'} ({campaign.account_purpose}) — the "
        "number this campaign was created against. Routing moved underneath it, so "
        "every message still to go would leave on the wrong number. Put the routing "
        "rule back, then create a new campaign.",
    )


def resolve_plan(
    db: Session, *, product: WhatsAppProduct, intent: str, locale: Optional[str]
) -> tuple[WhatsAppAccount, WhatsAppTemplate, WhatsAppRoutingRule]:
    """What this product/intent would send, or a refusal explaining why not.

    Mirrors the first seven checks of ``routing.resolve_route`` in the same
    order, against the same rows, so that the sentence an operator reads while
    drafting is the same decision the send path will make. It deliberately
    does **not** mint a ticket and does not check dormancy — drafting a
    campaign on a dormant platform is the normal state, and ``start`` is where
    dormancy is answered.
    """
    if PURPOSE_ENGAGEMENT not in (product.allowed_purposes or []):
        raise CampaignRefused(
            "purpose_not_permitted",
            f"{product.slug} is not entitled to the QUATA number, which is the "
            "only number a campaign can go out on. Widen its allowed purposes "
            "first, deliberately and on its own.",
        )

    rule = _active_rule(db, product_id=product.id, intent=intent, locale=locale)
    if rule is None or (rule.conditions or {}):
        raise CampaignRefused(
            "no_route",
            f"No active routing rule carries {product.slug}/{intent}"
            f"{f' for locale {locale}' if locale else ''}. A campaign is sent "
            "through the same route as any other message — create and activate "
            "the rule on the Routing screen first.",
        )

    if rule.purpose != PURPOSE_ENGAGEMENT:
        # Unreachable through the console (the rule would have to be an
        # authentication rule and the campaign row could not be written
        # anyway), and refused here so the sentence names the real problem.
        raise CampaignRefused(
            "campaign_must_be_engagement",
            f"{product.slug}/{intent} routes to the '{rule.purpose}' number. A "
            "campaign is marketing and marketing never leaves Quata Verify — "
            "route this intent to QUATA, or use an intent that already does.",
        )

    account = engagement_account(db)
    if account is None:
        raise CampaignRefused(
            "no_account_for_purpose",
            "There is no live QUATA number. A campaign has nowhere to go out "
            "from until the engagement number is configured and switched on.",
        )

    language = (locale or product.default_locale or "en").strip() or "en"
    template = (
        db.query(WhatsAppTemplate)
        .filter(WhatsAppTemplate.account_id == account.id)
        .filter(WhatsAppTemplate.intent == rule.template_intent)
        .filter(WhatsAppTemplate.language == language)
        .filter(WhatsAppTemplate.status == "approved")
        .order_by(WhatsAppTemplate.id)
        .first()
    )
    if template is None:
        raise CampaignRefused(
            "template_not_approved",
            f"No approved '{rule.template_intent}' template in {language} exists "
            f"on {account.name}. Meta owns approval — QCP cannot mark a template "
            "approved, and will not send an unapproved one. Sync from Meta once "
            "it has approved yours.",
        )

    if template.category == CATEGORY_AUTHENTICATION:
        # The composite FK and the CHECK both make this row impossible; the
        # refusal exists so the reason is a sentence rather than a constraint
        # name in a traceback.
        raise CampaignRefused(
            "auth_template_in_campaign",
            f"'{template.name}' is an authentication template. Security codes go "
            "out on Quata Verify and nowhere else, and a campaign can never "
            "carry one.",
        )

    return account, template, rule


# ---------------------------------------------------------------------------
# Create / edit
# ---------------------------------------------------------------------------

def create(
    db: Session,
    *,
    name: str,
    product: WhatsAppProduct,
    intent: str,
    locale: Optional[str],
    audience_source: str,
    audience_filters: Optional[dict],
    variables: Optional[list],
    messages_per_minute: Optional[int],
    actor_id: Optional[int] = None,
    ip_address: Optional[str] = None,
) -> WhatsAppCampaign:
    """Draft a campaign. It sends nothing and it cannot be created running."""
    account, template, _rule = resolve_plan(
        db, product=product, intent=intent, locale=locale
    )

    try:
        cleaned_filters = audience_service.validate(audience_source, audience_filters)
    except audience_service.AudienceRefused as exc:
        raise CampaignRefused(exc.reason, exc.detail) from exc

    values = [str(v) for v in (variables or [])]
    declared = list(template.variables or [])
    if len(values) != len(declared):
        raise CampaignRefused(
            "variable_arity_mismatch",
            f"'{template.name}' takes {len(declared)} variable(s) "
            f"({', '.join(str(d) for d in declared) or 'none'}); "
            f"{len(values)} were supplied. Routing refuses a mismatch at send "
            "time, so the campaign would suppress every message.",
        )

    rate = int(messages_per_minute or DEFAULT_MESSAGES_PER_MINUTE)
    if rate < 1 or rate > MAX_MESSAGES_PER_MINUTE:
        raise CampaignRefused(
            "invalid_rate",
            f"Send rate must be between 1 and {MAX_MESSAGES_PER_MINUTE} messages "
            "per minute. Sending faster than Meta expects is what gets a number "
            "throttled — and this number carries the fleet's login codes.",
        )

    row = WhatsAppCampaign(
        campaign_uid=uuid.uuid4().hex[:32],
        name=name.strip()[:120],
        product_id=product.id,
        intent=intent.strip()[:80],
        locale=(locale or None),
        account_id=account.id,
        account_purpose=account.purpose,
        template_id=template.id,
        audience_source=audience_source,
        audience_filters=cleaned_filters,
        audience_size=0,
        variables=values,
        # Not a parameter. A campaign is a draft.
        status=STATUS_DRAFT,
        messages_per_minute=rate,
    )
    row.created_by_id = actor_id
    db.add(row)
    db.flush()

    audit.record(
        db,
        action="campaign.created",
        resource_type="whatsapp_campaign",
        resource_id=row.campaign_uid,
        outcome=audit.OUTCOME_OK,
        actor_id=actor_id,
        product_id=product.id,
        account_id=account.id,
        details={
            "name": row.name,
            "intent": row.intent,
            "template": template.name,
            "category": template.category,
            "audience_source": audience_source,
            "messages_per_minute": rate,
        },
        ip_address=ip_address,
    )
    return row


def update(
    db: Session,
    campaign: WhatsAppCampaign,
    *,
    changes: dict,
    actor_id: Optional[int] = None,
    ip_address: Optional[str] = None,
) -> WhatsAppCampaign:
    """Edit a draft. Refused once the campaign has ever been startable-live."""
    if campaign.status not in EDITABLE_STATUSES:
        raise CampaignRefused(
            "campaign_not_editable",
            f"This campaign is {campaign.status}. Only a draft or a scheduled "
            "campaign can be edited — stop it and create a new one instead of "
            "changing what a running or finished send meant.",
        )

    product = db.get(WhatsAppProduct, campaign.product_id)
    if product is None:
        raise CampaignRefused(
            "product_disabled", "The product this campaign belongs to no longer exists."
        )

    if "name" in changes and changes["name"]:
        campaign.name = str(changes["name"]).strip()[:120]

    intent = changes.get("intent", campaign.intent)
    locale = changes.get("locale", campaign.locale)
    if "intent" in changes or "locale" in changes:
        account, template, _rule = resolve_plan(
            db, product=product, intent=str(intent), locale=locale
        )
        campaign.intent = str(intent).strip()[:80]
        campaign.locale = locale or None
        campaign.account_id = account.id
        campaign.account_purpose = account.purpose
        campaign.template_id = template.id

    if "audience_source" in changes or "audience_filters" in changes:
        source = changes.get("audience_source", campaign.audience_source)
        filters = changes.get("audience_filters", campaign.audience_filters)
        try:
            campaign.audience_filters = audience_service.validate(source, filters)
        except audience_service.AudienceRefused as exc:
            raise CampaignRefused(exc.reason, exc.detail) from exc
        campaign.audience_source = source
        # The stored audience no longer describes the filters. Clear it rather
        # than leave a list nobody can reconcile with what is on screen.
        _clear_audience(db, campaign)

    if "variables" in changes:
        template = db.get(WhatsAppTemplate, campaign.template_id)
        values = [str(v) for v in (changes["variables"] or [])]
        declared = list((template.variables if template else None) or [])
        if len(values) != len(declared):
            raise CampaignRefused(
                "variable_arity_mismatch",
                f"This campaign's template takes {len(declared)} variable(s); "
                f"{len(values)} were supplied.",
            )
        campaign.variables = values

    if "messages_per_minute" in changes and changes["messages_per_minute"]:
        rate = int(changes["messages_per_minute"])
        if rate < 1 or rate > MAX_MESSAGES_PER_MINUTE:
            raise CampaignRefused(
                "invalid_rate",
                f"Send rate must be between 1 and {MAX_MESSAGES_PER_MINUTE} "
                "messages per minute.",
            )
        campaign.messages_per_minute = rate

    db.flush()
    audit.record(
        db,
        action="campaign.updated",
        resource_type="whatsapp_campaign",
        resource_id=campaign.campaign_uid,
        outcome=audit.OUTCOME_OK,
        actor_id=actor_id,
        product_id=campaign.product_id,
        account_id=campaign.account_id,
        details={"fields": sorted(changes)},
        ip_address=ip_address,
    )
    return campaign


# ---------------------------------------------------------------------------
# Audience
# ---------------------------------------------------------------------------

def _clear_audience(db: Session, campaign: WhatsAppCampaign) -> None:
    db.query(WhatsAppCampaignRecipient).filter(
        WhatsAppCampaignRecipient.campaign_id == campaign.id
    ).delete(synchronize_session=False)
    campaign.audience_size = 0


def build_audience(
    db: Session,
    campaign: WhatsAppCampaign,
    *,
    actor_id: Optional[int] = None,
    ip_address: Optional[str] = None,
) -> dict:
    """Materialise the recipient list. Only before the campaign has run.

    Rebuilding is destructive on purpose: the previous list is discarded and
    re-derived, so what is on screen is always what the current filters
    produce. It is refused once a campaign is running, because a send that
    changes who it is addressed to halfway through is not a thing an operator
    can reason about.
    """
    if campaign.status not in EDITABLE_STATUSES:
        raise CampaignRefused(
            "campaign_not_editable",
            f"This campaign is {campaign.status}. Its audience is fixed — a "
            "running or finished campaign cannot be re-aimed.",
        )

    product = db.get(WhatsAppProduct, campaign.product_id)
    if product is None:
        raise CampaignRefused(
            "product_disabled", "The product this campaign belongs to no longer exists."
        )

    try:
        candidates = audience_service.resolve(
            db,
            source=campaign.audience_source,
            filters=campaign.audience_filters,
            account_id=campaign.account_id,
            product=product,
        )
    except audience_service.AudienceRefused as exc:
        raise CampaignRefused(exc.reason, exc.detail) from exc

    _clear_audience(db, campaign)
    db.flush()

    for candidate in candidates:
        db.add(
            WhatsAppCampaignRecipient(
                campaign_id=campaign.id,
                phone_e164=candidate.phone_e164[:24],
                conversation_id=candidate.conversation_id,
                locale=candidate.locale,
                status=RECIPIENT_PENDING,
            )
        )
    campaign.audience_size = len(candidates)
    db.flush()

    audit.record(
        db,
        action="campaign.audience_built",
        resource_type="whatsapp_campaign",
        resource_id=campaign.campaign_uid,
        outcome=audit.OUTCOME_OK,
        actor_id=actor_id,
        product_id=campaign.product_id,
        account_id=campaign.account_id,
        details={
            "source": campaign.audience_source,
            "filters": campaign.audience_filters,
            "size": campaign.audience_size,
        },
        ip_address=ip_address,
    )
    return {"size": campaign.audience_size, "source": campaign.audience_source}


# ---------------------------------------------------------------------------
# The switches
# ---------------------------------------------------------------------------

def schedule(
    db: Session,
    campaign: WhatsAppCampaign,
    *,
    when: datetime,
    actor_id: Optional[int] = None,
    ip_address: Optional[str] = None,
) -> WhatsAppCampaign:
    """Arm a campaign for a future time. Still sends nothing by itself.

    A scheduled campaign is promoted to running by ``runner.run_due`` — which
    re-checks dormancy, the product gate and the route at that moment. So
    scheduling is not a way to arrange a send that bypasses a switch someone
    turns off in the meantime.
    """
    if campaign.status not in EDITABLE_STATUSES:
        raise CampaignRefused(
            "campaign_not_schedulable",
            f"This campaign is {campaign.status} and cannot be scheduled.",
        )
    _assert_ready(db, campaign)

    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    if when <= _now():
        raise CampaignRefused(
            "schedule_in_the_past",
            "That time has already passed. Schedule a future time, or start the "
            "campaign now.",
        )

    campaign.scheduled_at = when
    campaign.status = STATUS_SCHEDULED
    db.flush()
    audit.record(
        db,
        action="campaign.scheduled",
        resource_type="whatsapp_campaign",
        resource_id=campaign.campaign_uid,
        outcome=audit.OUTCOME_OK,
        actor_id=actor_id,
        product_id=campaign.product_id,
        account_id=campaign.account_id,
        details={"scheduled_at": when.isoformat()},
        ip_address=ip_address,
    )
    return campaign


def _assert_ready(db: Session, campaign: WhatsAppCampaign) -> None:
    """Everything that must be true before a campaign may be armed at all."""
    if campaign.audience_size <= 0:
        raise CampaignRefused(
            "empty_audience",
            "This campaign has no recipients. Build its audience first — an "
            "armed campaign with nobody in it is a switch that looks live and "
            "does nothing.",
        )
    product = db.get(WhatsAppProduct, campaign.product_id)
    if product is None or not product.is_enabled:
        raise CampaignRefused(
            "product_disabled",
            f"{product.slug if product else 'The product'} is not enabled in the "
            "QCP registry, so nothing it asks for can be sent.",
        )
    # Checked before the plan is re-resolved, so a campaign whose intent has
    # been repointed at the other number is told *that*, rather than being
    # told about whatever the new number's templates happen to look like. A
    # campaign paused overnight is the ordinary way this arrives.
    assert_route_unchanged(db, campaign)
    # Re-resolved rather than trusted: the template may have been retired, or
    # Meta may have re-classified and quarantined it, since the draft was made.
    resolve_plan(db, product=product, intent=campaign.intent, locale=campaign.locale)


def start(
    db: Session,
    campaign: WhatsAppCampaign,
    *,
    actor_id: Optional[int] = None,
    ip_address: Optional[str] = None,
) -> WhatsAppCampaign:
    """Begin sending. The only verb in QCP that starts outbound marketing.

    Refused while the platform is dormant. That is the ship-inert rule, and it
    is checked here *and* before every batch: ``delivery_enabled()`` is the
    env kill switch AND the admin toggle, and a campaign is not allowed to be
    the thing that makes a dormant install send.
    """
    if campaign.status in TERMINAL_STATUSES:
        raise CampaignRefused(
            "campaign_finished",
            f"This campaign is {campaign.status}. A stopped or completed "
            "campaign is never restarted — create a new one, so the record of "
            "what was sent stays true.",
        )
    if campaign.status == STATUS_RUNNING:
        return campaign
    if campaign.status not in STARTABLE_STATUSES:
        raise CampaignRefused(
            "campaign_not_startable", f"A {campaign.status} campaign cannot be started."
        )

    if not settings_store.delivery_enabled():
        raise CampaignRefused(
            "delivery_disabled",
            "QCP is dormant: WhatsApp delivery is switched off, so no message "
            "can leave the platform. Nothing has been queued. Turn delivery on "
            "deliberately — the environment kill switch and the admin toggle "
            "must both say yes — and start the campaign again.",
        )

    _assert_ready(db, campaign)

    campaign.status = STATUS_RUNNING
    campaign.started_at = campaign.started_at or _now()
    campaign.stop_reason = None
    campaign.last_error = None
    # Due immediately; the runner paces from here.
    campaign.next_batch_at = _now()
    db.flush()

    audit.record(
        db,
        action="campaign.started",
        resource_type="whatsapp_campaign",
        resource_id=campaign.campaign_uid,
        outcome=audit.OUTCOME_OK,
        actor_id=actor_id,
        product_id=campaign.product_id,
        account_id=campaign.account_id,
        details={
            "audience_size": campaign.audience_size,
            "messages_per_minute": campaign.messages_per_minute,
        },
        ip_address=ip_address,
    )
    return campaign


def pause(
    db: Session,
    campaign: WhatsAppCampaign,
    *,
    actor_id: Optional[int] = None,
    reason: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> WhatsAppCampaign:
    """Hold the send. Recipients stay pending and the campaign can resume."""
    if campaign.status in TERMINAL_STATUSES:
        raise CampaignRefused(
            "campaign_finished", f"This campaign is already {campaign.status}."
        )
    campaign.status = STATUS_PAUSED
    campaign.next_batch_at = None
    if reason:
        campaign.last_error = str(reason)[:500]
    db.flush()
    audit.record(
        db,
        action="campaign.paused",
        resource_type="whatsapp_campaign",
        resource_id=campaign.campaign_uid,
        outcome=audit.OUTCOME_OK,
        actor_id=actor_id,
        product_id=campaign.product_id,
        account_id=campaign.account_id,
        reason=reason,
        ip_address=ip_address,
    )
    return campaign


def stop(
    db: Session,
    campaign: WhatsAppCampaign,
    *,
    actor_id: Optional[int] = None,
    reason: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> dict:
    """Halt a campaign for good, now.

    Somebody will send the wrong thing to the wrong audience; the only
    question is whether they can halt it. So stop is:

    * **available from every non-terminal state** — draft, scheduled, running
      and paused all stop, and stopping an already-stopped campaign is a
      no-op rather than an error, because the person hitting the button twice
      is the person who most needs it to work;
    * **immediate** — it writes ``status='stopped'`` and cancels every
      recipient that has not been handed off, in one statement, and commits
      before returning. ``runner`` re-reads the status from the database
      before *every individual message*, not once per batch, so the longest a
      send can outlive a stop is the one message already in flight;
    * **terminal** — there is no resume. A stopped campaign stays a record of
      what actually went out.

    Returns the counts, because "how many had already gone?" is the first
    question anyone asks after pressing it.
    """
    already_stopped = campaign.status in TERMINAL_STATUSES

    cancelled = 0
    if not already_stopped:
        cancelled = (
            db.query(WhatsAppCampaignRecipient)
            .filter(WhatsAppCampaignRecipient.campaign_id == campaign.id)
            .filter(WhatsAppCampaignRecipient.status == RECIPIENT_PENDING)
            .update({WhatsAppCampaignRecipient.status: RECIPIENT_CANCELLED},
                    synchronize_session=False)
        )
        campaign.status = STATUS_STOPPED
        campaign.stopped_at = _now()
        campaign.finished_at = campaign.finished_at or campaign.stopped_at
        campaign.stopped_by_id = actor_id
        campaign.stop_reason = (reason or "stopped by an operator")[:200]
        campaign.next_batch_at = None
        db.flush()

        audit.record(
            db,
            action="campaign.stopped",
            resource_type="whatsapp_campaign",
            resource_id=campaign.campaign_uid,
            outcome=audit.OUTCOME_OK,
            actor_id=actor_id,
            product_id=campaign.product_id,
            account_id=campaign.account_id,
            reason=campaign.stop_reason,
            details={"cancelled": cancelled},
            ip_address=ip_address,
        )

    sent = (
        db.query(WhatsAppCampaignRecipient)
        .filter(WhatsAppCampaignRecipient.campaign_id == campaign.id)
        .filter(WhatsAppCampaignRecipient.status == RECIPIENT_QUEUED)
        .count()
    )
    return {
        "status": campaign.status,
        "already_stopped": already_stopped,
        "cancelled": cancelled,
        "handed_off": sent,
    }


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------

def results(db: Session, campaign: WhatsAppCampaign) -> dict:
    """Sent, delivered, read, failed, opted out — from the message log itself.

    Delivery state is not copied onto the recipient row. It is read from
    ``whatsapp_messages``, where the Meta status webhook already maintains it,
    so a campaign's "delivered" is the same fact as the message log's and
    cannot drift from it. The recipient table contributes only what happens
    *before* hand-off: who was skipped for consent, who was cancelled by a
    stop, who is still waiting.
    """
    by_recipient_status = dict(
        db.query(
            WhatsAppCampaignRecipient.status,
            func.count(WhatsAppCampaignRecipient.id),
        )
        .filter(WhatsAppCampaignRecipient.campaign_id == campaign.id)
        .group_by(WhatsAppCampaignRecipient.status)
        .all()
    )

    by_message_status = dict(
        db.query(WhatsAppMessage.status, func.count(WhatsAppMessage.id))
        .filter(WhatsAppMessage.campaign_id == campaign.campaign_uid)
        .group_by(WhatsAppMessage.status)
        .all()
    )

    delivered = int(by_message_status.get("delivered", 0))
    read = int(by_message_status.get("read", 0))
    # Meta's status ladder is monotonic: a read message was delivered, and a
    # delivered message was sent. Reporting them as disjoint buckets makes a
    # campaign look like it reached a third of the people it reached.
    sent = (
        int(by_message_status.get("sent", 0))
        + int(by_message_status.get("sending", 0))
        + delivered
        + read
    )
    delivered_total = delivered + read

    return {
        "audience": int(campaign.audience_size or 0),
        "pending": int(by_recipient_status.get(RECIPIENT_PENDING, 0)),
        "queued": int(by_message_status.get("queued", 0)),
        "sent": sent,
        "delivered": delivered_total,
        "read": read,
        "failed": int(by_message_status.get("failed", 0))
        + int(by_recipient_status.get("failed", 0)),
        "suppressed": int(by_message_status.get("suppressed", 0)),
        "opted_out": int(by_recipient_status.get(RECIPIENT_OPTED_OUT, 0)),
        "cancelled": int(by_recipient_status.get(RECIPIENT_CANCELLED, 0)),
    }


def campaign_out(db: Session, campaign: WhatsAppCampaign) -> dict:
    """The one shape a campaign leaves this package in."""
    product = db.get(WhatsAppProduct, campaign.product_id)
    template = (
        db.get(WhatsAppTemplate, campaign.template_id) if campaign.template_id else None
    )
    account = db.get(WhatsAppAccount, campaign.account_id)
    return {
        "campaign_uid": campaign.campaign_uid,
        "name": campaign.name,
        "status": campaign.status,
        "product": product.slug if product else None,
        "product_name": product.name if product else None,
        "product_enabled": bool(product.is_enabled) if product else False,
        "intent": campaign.intent,
        "locale": campaign.locale,
        "account": account.slug if account else None,
        "account_name": account.name if account else None,
        # Always 'engagement'. Rendered anyway, because the number a campaign
        # is on is the single fact this platform exists to keep true.
        "account_purpose": campaign.account_purpose,
        "template": template.name if template else None,
        "template_category": template.category if template else None,
        "template_status": template.status if template else None,
        "variables": list(campaign.variables or []),
        "audience_source": campaign.audience_source,
        "audience_label": audience_service.SOURCE_LABELS.get(campaign.audience_source),
        "audience_filters": campaign.audience_filters or {},
        "audience_size": int(campaign.audience_size or 0),
        "messages_per_minute": campaign.messages_per_minute,
        "scheduled_at": campaign.scheduled_at,
        "started_at": campaign.started_at,
        "finished_at": campaign.finished_at,
        "stopped_at": campaign.stopped_at,
        "stop_reason": campaign.stop_reason,
        "last_error": campaign.last_error,
        "created_at": campaign.created_at,
        "results": results(db, campaign),
    }


def get(db: Session, campaign_uid: str) -> Optional[WhatsAppCampaign]:
    return (
        db.query(WhatsAppCampaign)
        .filter(WhatsAppCampaign.campaign_uid == campaign_uid)
        .first()
    )


def listing(
    db: Session, *, status: Optional[str] = None, limit: int = 50
) -> list[WhatsAppCampaign]:
    query = db.query(WhatsAppCampaign)
    if status:
        if status not in CAMPAIGN_STATUSES:
            raise CampaignRefused(
                "invalid_status",
                f"'{status}' is not a campaign state ({', '.join(CAMPAIGN_STATUSES)}).",
            )
        query = query.filter(WhatsAppCampaign.status == status)
    return (
        query.order_by(WhatsAppCampaign.id.desc()).limit(max(1, min(limit, 200))).all()
    )


def recipients(
    db: Session, campaign: WhatsAppCampaign, *, limit: int = 50
) -> list[dict]:
    rows = (
        db.query(WhatsAppCampaignRecipient)
        .filter(WhatsAppCampaignRecipient.campaign_id == campaign.id)
        .order_by(WhatsAppCampaignRecipient.id)
        .limit(max(1, min(limit, 500)))
        .all()
    )
    return [
        {
            "phone_e164": row.phone_e164,
            "status": row.status,
            "conversation_id": row.conversation_id,
            "message_uid": row.message_uid,
            "last_error": row.last_error,
            "attempted_at": row.attempted_at,
        }
        for row in rows
    ]


def platform_state(db: Session) -> dict:
    """Why a campaign can or cannot send right now, in one shape.

    QCP ships dormant, so "no campaign can be started" is the *correct* state
    on a fresh install. The console needs to be able to say which of the
    several reasons applies, rather than leaving an operator to guess whether
    the platform is off, the number is off, or the product is off.
    """
    account = engagement_account(db)
    enabled_products = (
        db.query(WhatsAppProduct)
        .filter(WhatsAppProduct.is_enabled == True)  # noqa: E712
        .order_by(WhatsAppProduct.slug)
        .all()
    )
    return {
        "delivery_enabled": settings_store.delivery_enabled(),
        "engagement_account": account.slug if account else None,
        "engagement_account_name": account.name if account else None,
        "any_product_enabled": bool(enabled_products),
        "products": [
            {
                "slug": p.slug,
                "name": p.name,
                "is_enabled": p.is_enabled,
                "allowed_purposes": p.allowed_purposes or [],
                "default_locale": p.default_locale,
            }
            for p in enabled_products
        ],
        "audience_sources": [
            {"value": source, "label": audience_service.SOURCE_LABELS[source]}
            for source in audience_service.SOURCES
        ],
        "opt_outs": consent.count(db),
        "max_messages_per_minute": MAX_MESSAGES_PER_MINUTE,
        "max_audience": audience_service.MAX_AUDIENCE,
    }
