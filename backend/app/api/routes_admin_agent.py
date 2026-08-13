"""QCP — the agent console. What a human support agent actually uses.

``routes_admin_whatsapp.py`` is the operator's surface: the estate, the
credentials, the registry, the switches. This is the *worker's* surface —
the queue, the thread, the reply, and the draft the AI offers. It shares
that module's auth model exactly (bearer token, ``require_permission``, an
audited row per action) and nothing else: no route here touches a
credential, a gate or a registration.

**The permission.** Not ``settings:manage`` and not ``whatsapp:operate``,
but the same set ``conversations.assign`` already accepts —
``WHATSAPP_AGENT_PERMISSIONS``. That is deliberate rather than convenient:
if this console gated on something *wider*, a caller could claim a thread
and then be refused by ``assign`` for lacking the entitlement, which is a
403 discovered after the fact; if it gated on something *narrower*, a person
the platform considers assignable could not work their own queue. One list,
imported, so the two cannot drift.

Note the consequence for a super_admin: ``require_permission`` honours the
``*`` wildcard, but ``conversations._is_whatsapp_agent`` deliberately does
not — a wildcard is a bypass for a human in the cockpit, not an entitlement
to be handed customer conversations. A super_admin holding no explicit
WhatsApp permission can therefore read the queues and is refused at the
moment they try to *take* a thread, with a message saying which permission
their role needs. That refusal is the existing design being surfaced, not a
new rule.

**Every send goes through the existing gateway.** ``dispatch.send`` is the
single entry point for every message QCP has ever sent, and this module adds
no second one: an agent reply is resolved by ``routing.resolve_route`` like
any other, is refused by the same eight checks, and lands in the same
outbox. The one thing done *before* the hand-off is the 24h service-window
check, because that check lives at the HTTP layer for products too
(``routes_whatsapp._send``) and calls the same
``conversations.service_window_open``.

**The Verify number is never agent-answerable, and it is checked twice.**

1. The thread's own account must be the engagement number. That catches the
   ordinary case — an agent looking at an inbound message a customer typed
   to the Quata Verify number, which Meta will deliver whatever we do.
2. The *intent* named on the reply must resolve to an engagement routing
   rule. That catches the case the first check cannot see: a perfectly
   ordinary support thread on QUATA, with an agent naming an intent whose
   rule points at the authentication purpose. Without it, the console could
   address an OTP template from a support conversation.

Neither check is a prompt or a convention; both refuse in code, are audited,
and are pinned by ``tests/test_qcp_agent_api.py``.

**The AI drafts; it never sends.** ``POST .../suggest`` returns text an
agent edits and sends themselves. It is off until its own switch is on, it
is never consulted about a Verify thread, and it withholds any draft
carrying a figure — this module calls no product API, so a number in a
draft was invented, and on a fleet that moves real money an invented balance
is worse than no answer. The AI layer proper is reached through the QCP
package facade (``AI_FACADE_ATTR``, resolved at call time); when it is not
installed this endpoint says so rather than improvising a second
integration.

**No response here carries a staff id.** ``users.id`` leaking to a product
through ``assignee_id`` was found and closed in an earlier round. This
surface does not reopen the class: it emits ``mine`` and a display name, and
nothing it hands to ``dispatch.send`` — not the body, not the intent, not
the idempotency reference — is derived from the agent's identity.
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_client_ip, require_permission
from app.db.session import get_db
from app.models import (
    User,
    WhatsAppAccount,
    WhatsAppAuditLog,
    WhatsAppConversation,
    WhatsAppMessage,
    WhatsAppProduct,
    WhatsAppRoutingRule,
)
from app.models.whatsapp import PURPOSE_ENGAGEMENT
from app.core.config import settings as env_settings
from app.schemas.whatsapp_agent import (
    AgentOwnershipOut,
    AgentQueueItemOut,
    AgentQueueOut,
    AgentReplyIn,
    AgentReplyOut,
    AgentTemplateOut,
    AiStateOut,
    ReturnToAiOut,
    SuggestedReplyOut,
    ThreadMessageOut,
    ThreadOut,
)
from app.services import site_settings
from app.services.whatsapp import audit
from app.services.whatsapp import conversations as conversations_service
from app.services.whatsapp import routing


router = APIRouter(tags=["whatsapp-agent"])

# The entitlement to answer a customer. Imported rather than restated: this
# is the same list ``conversations.assign`` checks an assignee against, and
# a console gating on a different one would either offer work it cannot
# complete or hide work the platform considers this person's.
PERM_AGENT = tuple(sorted(conversations_service.WHATSAPP_AGENT_PERMISSIONS))

# The console's own switch, and it is not the AI layer's. This one governs
# whether an agent may ask for a *draft*; whether the AI answers a customer
# by itself is a separate switch owned by the AI service. Both default off,
# and the key is absent from a database that has never been through the QCP
# console, so a fresh install drafts nothing.
KEY_AI_SUGGESTIONS_ENABLED = "whatsapp.ai_suggestions_enabled"

# Read, never written here: whether automation will actually pick a thread
# up once a human hands it back. Reported on ``return-to-ai`` so an agent is
# told, at the moment they do it, that nobody is on the thread.
KEY_AI_REPLIES_ENABLED = "whatsapp.ai_replies_enabled"

_TRUE = {"1", "true", "yes", "on"}

# How the AI support layer is reached: one name on the QCP package facade,
# resolved at call time. Not an import of a submodule — nothing outside
# ``app/services/whatsapp`` may reach past the facade (asserted by
# ``tests/test_whatsapp_boundaries.py``), and a console that imported the AI
# module directly would be the first exception to that rule.
#
# Resolving late also means this console has no dependency on the AI layer
# existing: the queues, claiming, replying and handover all work with none
# installed, and the suggestion endpoint answers ``ai_unavailable`` instead
# of the console growing a second OpenAI integration of its own (there is one
# already — ``app/services/ai_cv.py`` — and the AI layer follows it).
#
# The contract is one callable:
#
#     suggest_reply(db, conversation, *, messages) -> {
#         "text": str, "model": str, "prompt_version": str,
#         "escalate": bool, "reason": str,
#     }
#
# A decision *object* carrying the same names is accepted too (see
# ``_normalise_draft``), so the AI layer's own ``Decision`` can be returned
# as it stands rather than being re-wrapped for this one caller.
#
# It must not send anything. This endpoint returns a draft.
AI_FACADE_ATTR = "suggest_reply"

# The one action on a decision object that means "there is something to say".
# Anything else — escalate, silent, refused — is an escalation here: a
# console that rendered a draft the AI declined to send would undo the
# decision it just made.
AI_ACTION_REPLY = "reply"

# Audit actions whose subject is a message the AI wrote. The authorship seam
# for the thread view: ``whatsapp_messages`` has no author column, and the
# audit row that recorded the send already knows who asked for it.
AI_AUDIT_PREFIX = "ai."
AGENT_AUDIT_PREFIX = "agent."

# A figure this console cannot vouch for.
#
# Every endpoint here is read-only with respect to the products: nothing in
# this module calls QuataPay, QuataFood, Abaqwa or QuataTrade, so no balance,
# payment, refund, order total or account status has been *fetched* in the
# request that produced a draft. Any number in that draft was therefore
# generated by a language model, and this fleet handles real money in
# Cameroon — a plausible invented amount is worse than no answer.
#
# Three or more consecutive digits (an amount, an order total, an account
# number, and every OTP shape), a currency token, or a percentage. Small
# numbers are left alone deliberately: "one moment" and "8am" are not claims
# about somebody's money, and a rule that blocked them would make the feature
# useless without making it safer.
_FIGURE = re.compile(
    r"\d{3,}|[€$£]\s*\d|\d\s*%|\b\d[\d.,]*\s*(?:FCFA|XAF|CFA|USD|EUR|GBP|F\b)",
    re.IGNORECASE,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_aware(value: Optional[datetime]) -> Optional[datetime]:
    """SQLite hands back naive datetimes; arithmetic needs them aware."""
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _display_name(user: Optional[User]) -> Optional[str]:
    if user is None:
        return None
    return (user.full_name or "").strip() or user.email


# ---------------------------------------------------------------------------
# Audit — same shape as routes_admin_whatsapp, with the human always attached
# ---------------------------------------------------------------------------

def _record(
    db: Session,
    request: Request,
    user: User,
    *,
    action: str,
    resource_id,
    outcome: str = audit.OUTCOME_OK,
    reason: Optional[str] = None,
    details: Optional[dict] = None,
    resource_type: str = "whatsapp_conversation",
    account_id: Optional[int] = None,
    product_id: Optional[int] = None,
) -> None:
    """One audit row per agent action, with the agent on it.

    Every action in this module is a human answering a customer on a number
    that also carries money and identity traffic, so "who said this to that
    person, and when" has to be answerable from the log rather than inferred
    from a message row that has no author column.
    """
    audit.record(
        db,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        outcome=outcome,
        reason=reason,
        actor_id=user.id,
        account_id=account_id,
        product_id=product_id,
        details=details,
        ip_address=get_client_ip(request),
    )


def _deny(
    db: Session,
    request: Request,
    user: User,
    *,
    action: str,
    resource_id,
    reason: str,
    detail: dict,
    http_status: int = status.HTTP_409_CONFLICT,
    account_id: Optional[int] = None,
    product_id: Optional[int] = None,
) -> None:
    """Refuse, on the record, with something an agent can act on. Always raises."""
    _record(
        db,
        request,
        user,
        action=action,
        resource_id=resource_id,
        outcome=audit.OUTCOME_DENIED,
        reason=reason,
        details={k: v for k, v in detail.items() if k != "message"},
        account_id=account_id,
        product_id=product_id,
    )
    db.commit()
    raise HTTPException(http_status, detail)


def _conversation_or_404(db: Session, conversation_id: int) -> WhatsAppConversation:
    row = db.get(WhatsAppConversation, conversation_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")
    return row


# ---------------------------------------------------------------------------
# Serialisation
# ---------------------------------------------------------------------------

def _answerable(
    account: Optional[WhatsAppAccount], product: Optional[WhatsAppProduct]
) -> tuple[bool, Optional[str]]:
    """Can an agent reply on this thread at all?

    The same two refusals the reply route enforces, computed for the queue so
    the console can grey a row out instead of offering a reply box that 409s.
    """
    if account is None or account.purpose != PURPOSE_ENGAGEMENT:
        return False, "verify_number_not_agent_answerable"
    if product is None:
        return False, "conversation_unattributed"
    return True, None


def _ai_state(db: Session) -> AiStateOut:
    """What the AI is doing right now, for the console's banner.

    ``enabled`` and ``kill_switch`` are the same switch read twice, on
    purpose: the screen renders "AI drafting is off" and "the kill switch is
    ON" as two different, both-normal states, and an agent who sees neither
    concludes the tool is broken when drafts stop appearing.

    ``misconfigured``/``blocker``/``gaps`` are the third state, and the reason
    this function takes a session at all: an AI that is switched on and has no
    ``ai_support_reply`` engagement rule answers **nobody**, and until this
    carried it the only trace was an ``ai.misconfigured`` audit row written by
    a background worker. Computed by ``settings_store.ai_reply_readiness``,
    which is the one implementation the worker reads too.
    """
    from app.services.whatsapp import settings_store  # noqa: PLC0415

    on = settings_store.ai_replies_enabled()
    readiness = settings_store.ai_reply_readiness(db)
    return AiStateOut(
        enabled=on,
        kill_switch=not on,
        configured=bool(env_settings.ai_enabled),
        suggestions_enabled=_flag(KEY_AI_SUGGESTIONS_ENABLED),
        model=env_settings.OPENAI_MODEL if env_settings.ai_enabled else None,
        prompt_version=None,
        misconfigured=bool(readiness["misconfigured"]),
        blocker=readiness["blocker"],
        gaps=list(readiness["gaps"]),
    )


def _handover_state(row: WhatsAppConversation, now: datetime) -> tuple[bool, Optional[str], Optional[datetime], bool]:
    """``(escalated, reason, waiting_since, overdue)`` for one thread.

    Read through ``handover`` rather than off the column, so "what does
    ``assigned_agent='pending_human'`` mean" has one implementation.
    """
    from app.services.whatsapp import handover  # noqa: PLC0415

    if (row.assigned_agent or None) != handover.PENDING_HUMAN:
        return False, None, None, False
    since = handover.waiting_since(row)
    reason = None
    blob = row.meta if isinstance(row.meta, dict) else {}
    inner = blob.get("ai")
    if isinstance(inner, dict):
        reason = inner.get("reason")
    overdue = bool(
        row.assignee_id is None and since is not None and (now - since) >= handover.UNANSWERED_AFTER
    )
    return True, reason, since, overdue


def _queue_item(
    row: WhatsAppConversation,
    *,
    account: Optional[WhatsAppAccount],
    product: Optional[WhatsAppProduct],
    holder: Optional[User],
    viewer_id: int,
    now: datetime,
) -> AgentQueueItemOut:
    last_inbound = _as_aware(row.last_inbound_at)
    escalated, handover_reason, waiting_since, overdue = _handover_state(row, now)
    # How long *this customer* has been waiting to be answered. An escalation
    # starts its own clock, because a thread the AI handed over at 09:00 has
    # been waiting since 09:00 whether or not the customer said anything more
    # — and the people who stop talking are precisely the ones a queue sorted
    # by "last message" hides.
    since = waiting_since or last_inbound
    waiting = int((now - since).total_seconds()) if since else 0
    answerable, reason = _answerable(account, product)
    mine = row.assignee_id == viewer_id
    return AgentQueueItemOut(
        escalated=escalated,
        handover_reason=handover_reason,
        waiting_since=waiting_since,
        overdue=overdue,
        conversation_id=row.id,
        phone_e164=row.phone_e164,
        display_name=row.display_name,
        state=row.state,
        product=product.slug if product else None,
        account=account.slug if account else None,
        account_purpose=account.purpose if account else None,
        unread_count=row.unread_count or 0,
        locale=row.locale,
        last_inbound_at=row.last_inbound_at,
        waiting_seconds=max(waiting, 0),
        service_window_open=conversations_service.service_window_open(row, now=now),
        service_window_expires_at=row.service_window_expires_at,
        mine=mine,
        # A name, never an id — and only for somebody else's thread.
        held_by=None if mine else _display_name(holder),
        answerable=answerable,
        answerable_reason=reason,
    )


def _context(db: Session, rows: list[WhatsAppConversation]) -> tuple[dict, dict, dict]:
    """Accounts, products and assignee names for a page of conversations."""
    accounts = {a.id: a for a in db.query(WhatsAppAccount).all()}
    products = {p.id: p for p in db.query(WhatsAppProduct).all()}
    holder_ids = {r.assignee_id for r in rows if r.assignee_id}
    holders = (
        {u.id: u for u in db.query(User).filter(User.id.in_(holder_ids)).all()}
        if holder_ids
        else {}
    )
    return accounts, products, holders


def _serialise(
    db: Session, rows: list[WhatsAppConversation], *, viewer_id: int
) -> list[AgentQueueItemOut]:
    accounts, products, holders = _context(db, rows)
    now = _now()
    return [
        _queue_item(
            row,
            account=accounts.get(row.account_id),
            product=products.get(row.product_id),
            holder=holders.get(row.assignee_id),
            viewer_id=viewer_id,
            now=now,
        )
        for row in rows
    ]


# ---------------------------------------------------------------------------
# The queues
# ---------------------------------------------------------------------------

@router.get("/admin/qcp/agent/queue", response_model=AgentQueueOut)
def qcp_agent_my_queue(
    include_closed: bool = False,
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(*PERM_AGENT)),
):
    """My queue: the threads assigned to me, oldest waiting first.

    Ordered by ``last_inbound_at`` ascending — how long *this customer* has
    been waiting for a reply. Newest-first is the default a list view drifts
    into and it buries the person who has waited longest, which is the one
    person a support queue exists to find.
    """
    query = db.query(WhatsAppConversation).filter(
        WhatsAppConversation.assignee_id == user.id
    )
    if not include_closed:
        query = query.filter(WhatsAppConversation.state != conversations_service.STATE_CLOSED)
    total = query.count()
    rows = (
        query.order_by(
            WhatsAppConversation.last_inbound_at.asc().nullslast(),
            WhatsAppConversation.id.asc(),
        )
        .limit(limit)
        .all()
    )
    return AgentQueueOut(
        items=_serialise(db, rows, viewer_id=user.id), total=total, ai=_ai_state(db)
    )


@router.get("/admin/qcp/agent/queue/unassigned", response_model=AgentQueueOut)
def qcp_agent_unassigned_queue(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(*PERM_AGENT)),
):
    """Waiting on any human: no assignee, not closed, and a customer has
    written. Oldest first, with how long they have waited.

    Threads with no inbound message at all are excluded: nobody is waiting on
    one, and padding the queue with them is how the number at the top of the
    screen stops meaning anything.

    Unanswerable threads are *listed* rather than hidden — an inbound to the
    Quata Verify number is real and somebody should see it — but each row
    carries ``answerable: false`` and the reason, so the console can show it
    without offering a reply box the reply route would refuse.
    """
    query = db.query(WhatsAppConversation).filter(
        WhatsAppConversation.assignee_id.is_(None),
        WhatsAppConversation.state != conversations_service.STATE_CLOSED,
        WhatsAppConversation.last_inbound_at.isnot(None),
    )
    total = query.count()
    rows = (
        query.order_by(
            WhatsAppConversation.last_inbound_at.asc(),
            WhatsAppConversation.id.asc(),
        )
        .limit(limit)
        .all()
    )
    return AgentQueueOut(
        items=_serialise(db, rows, viewer_id=user.id), total=total, ai=_ai_state(db)
    )


@router.get("/admin/qcp/agent/queue/escalations", response_model=AgentQueueOut)
def qcp_agent_escalations(
    overdue_only: bool = False,
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(*PERM_AGENT)),
):
    """Threads automation handed to a person and nobody has picked up.

    This endpoint is the answer to the only question that matters about an
    escalation: *does anyone find out?* A bot that correctly refuses to talk
    about somebody's refund and then leaves them in a queue nobody watches has
    produced the same outcome as a bot that answered wrongly — silence — and
    it is the failure this whole feature exists to prevent.

    Longest wait first, and ``overdue`` marks the ones past
    ``handover.UNANSWERED_AFTER``. ``overdue_only=true`` narrows it to those,
    which is the shape a dashboard tile or an alert wants.

    Read-only. Raising the alert is a separate, deliberate act — see the
    sweep below — so that polling this list cannot spam the audit log.
    """
    from app.services.whatsapp import handover  # noqa: PLC0415

    query = db.query(WhatsAppConversation).filter(
        WhatsAppConversation.assigned_agent == handover.PENDING_HUMAN,
        WhatsAppConversation.assignee_id.is_(None),
        WhatsAppConversation.state != conversations_service.STATE_CLOSED,
    )
    rows = (
        query.order_by(
            WhatsAppConversation.last_inbound_at.asc().nullsfirst(),
            WhatsAppConversation.id.asc(),
        )
        .limit(limit)
        .all()
    )
    items = _serialise(db, rows, viewer_id=user.id)
    if overdue_only:
        items = [item for item in items if item.overdue]
    # Longest wait at the top, whatever order the rows arrived in.
    items.sort(key=lambda item: item.waiting_seconds, reverse=True)
    return AgentQueueOut(items=items, total=len(items), ai=_ai_state(db))


@router.post("/admin/qcp/agent/queue/escalations/sweep", response_model=AgentQueueOut)
def qcp_agent_sweep_escalations(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(*PERM_AGENT)),
):
    """Raise the alert for every escalation nobody has answered in time.

    ``handover.flag_unanswered`` writes exactly **one** audit denial row per
    escalation rather than one per sweep, so a caller polling this every
    minute turns one ignored customer into one row, not a thousand nobody
    reads. Returns what it reported.

    A POST rather than a side effect of the GET above: alerting is an act,
    and an act that happens because somebody opened a screen is an act nobody
    can account for afterwards.
    """
    from app.services.whatsapp import handover  # noqa: PLC0415

    reported = handover.flag_unanswered(db)
    _record(
        db,
        request,
        user,
        action="agent.escalations_swept",
        resource_id="queue",
        resource_type="whatsapp_conversation",
        details={"reported": len(reported)},
    )
    db.commit()
    items = _serialise(db, reported, viewer_id=user.id)
    items.sort(key=lambda item: item.waiting_seconds, reverse=True)
    return AgentQueueOut(items=items, total=len(items), ai=_ai_state(db))


# ---------------------------------------------------------------------------
# Claim / release
# ---------------------------------------------------------------------------

@router.post(
    "/admin/qcp/agent/conversations/{conversation_id}/claim",
    response_model=AgentOwnershipOut,
)
def qcp_agent_claim(
    conversation_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(*PERM_AGENT)),
):
    """Take a waiting thread. Honest about the race.

    Two agents clicking at the same moment must not both be told they own
    it — one of them would then write to a customer the other is already
    writing to. The claim is a guarded ``UPDATE ... WHERE assignee_id IS
    NULL``: exactly one of the two updates a row, and the loser is told who
    holds it rather than getting a success it cannot act on.

    The entitlement is checked *after* the guard and inside the same
    transaction, by calling ``conversations.assign`` — the one implementation
    of "may this person be handed a customer". If it refuses, the claim is
    rolled back entirely, so a caller whose role lacks the permission cannot
    leave a thread parked on themselves.
    """
    row = _conversation_or_404(db, conversation_id)

    if row.assignee_id == user.id:
        _record(
            db,
            request,
            user,
            action="agent.claim_noop",
            resource_id=row.id,
            details={"already_mine": True},
            account_id=row.account_id,
            product_id=row.product_id,
        )
        db.commit()
        return AgentOwnershipOut(
            conversation_id=row.id, state=row.state, mine=True, already_mine=True
        )

    claimed = (
        db.query(WhatsAppConversation)
        .filter(
            WhatsAppConversation.id == row.id,
            WhatsAppConversation.assignee_id.is_(None),
        )
        .update({WhatsAppConversation.assignee_id: user.id}, synchronize_session=False)
    )
    if not claimed:
        db.rollback()
        current = db.get(WhatsAppConversation, conversation_id)
        holder = db.get(User, current.assignee_id) if current.assignee_id else None
        _deny(
            db,
            request,
            user,
            action="agent.claim_denied",
            resource_id=conversation_id,
            reason="already_claimed",
            detail={
                "reason": "already_claimed",
                # A name, not an id: the console has to render this.
                "held_by": _display_name(holder),
                "message": (
                    f"{_display_name(holder) or 'Another agent'} claimed this "
                    "conversation first. Two people answering one customer is "
                    "worse than a queue that waits."
                ),
            },
            account_id=current.account_id if current else None,
        )

    db.refresh(row)
    try:
        # The single implementation of "may this person be handed a customer".
        conversations_service.assign(db, row, user_id=user.id)
    except ValueError:
        db.rollback()
        _deny(
            db,
            request,
            user,
            action="agent.claim_denied",
            resource_id=conversation_id,
            reason="not_a_whatsapp_agent",
            detail={
                "reason": "not_a_whatsapp_agent",
                "message": (
                    "Your role carries no WhatsApp agent entitlement, so a "
                    "customer conversation cannot be assigned to you. One of "
                    f"{', '.join(PERM_AGENT)} is required."
                ),
            },
            http_status=status.HTTP_403_FORBIDDEN,
        )

    _record(
        db,
        request,
        user,
        action="agent.claimed",
        resource_id=row.id,
        details={"state": row.state, "phone": row.phone_e164},
        account_id=row.account_id,
        product_id=row.product_id,
    )
    db.commit()
    db.refresh(row)
    return AgentOwnershipOut(conversation_id=row.id, state=row.state, mine=True)


@router.post(
    "/admin/qcp/agent/conversations/{conversation_id}/release",
    response_model=AgentOwnershipOut,
)
def qcp_agent_release(
    conversation_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(*PERM_AGENT)),
):
    """Put a thread back in the waiting queue.

    Guarded the same way a claim is — ``WHERE assignee_id = me`` — so an
    agent cannot release a colleague's thread out from under them by
    guessing a conversation id.

    The state is deliberately left alone. Release says "not me"; it does not
    say "reopen this", which is what handing the thread back to automation
    means and is a different verb (``return-to-ai``).
    """
    row = _conversation_or_404(db, conversation_id)
    released = (
        db.query(WhatsAppConversation)
        .filter(
            WhatsAppConversation.id == row.id,
            WhatsAppConversation.assignee_id == user.id,
        )
        .update({WhatsAppConversation.assignee_id: None}, synchronize_session=False)
    )
    if not released:
        db.rollback()
        current = db.get(WhatsAppConversation, conversation_id)
        holder = db.get(User, current.assignee_id) if current.assignee_id else None
        _deny(
            db,
            request,
            user,
            action="agent.release_denied",
            resource_id=conversation_id,
            reason="not_your_conversation",
            detail={
                "reason": "not_your_conversation",
                "held_by": _display_name(holder),
                "message": (
                    "This conversation is not assigned to you, so there is "
                    "nothing for you to release."
                ),
            },
        )

    _record(
        db,
        request,
        user,
        action="agent.released",
        resource_id=row.id,
        details={"state": row.state},
        account_id=row.account_id,
        product_id=row.product_id,
    )
    db.commit()
    db.refresh(row)
    return AgentOwnershipOut(conversation_id=row.id, state=row.state, mine=False)


def _require_mine(
    db: Session,
    request: Request,
    user: User,
    row: WhatsAppConversation,
    *,
    action: str,
) -> None:
    """Working a thread means holding it. Refused, audited, otherwise.

    Claim-first is what makes the queue mean anything: an agent who can
    reply without claiming is an agent who can reply on top of a colleague
    mid-sentence, and the customer sees two voices.
    """
    if row.assignee_id == user.id:
        return
    holder = db.get(User, row.assignee_id) if row.assignee_id else None
    _deny(
        db,
        request,
        user,
        action=action,
        resource_id=row.id,
        reason="not_your_conversation",
        detail={
            "reason": "not_your_conversation",
            "held_by": _display_name(holder),
            "message": (
                "Claim this conversation before working it. "
                + (
                    f"{_display_name(holder)} currently holds it."
                    if holder
                    else "Nobody holds it yet."
                )
            ),
        },
        account_id=row.account_id,
        product_id=row.product_id,
    )


def _require_engagement(
    db: Session,
    request: Request,
    user: User,
    row: WhatsAppConversation,
    account: Optional[WhatsAppAccount],
    *,
    action: str,
) -> None:
    """Check 1 of 2: the Verify number is never agent-answerable.

    Not one message, and not one AI draft either — this is called before the
    AI service is consulted, so a conversation on the authentication number
    is never handed to a model at all.

    Inbound to Quata Verify exists: Meta delivers whatever a customer types,
    and the thread is real. What does not exist is a reply from here. The
    number carries the fleet's login codes, its quality rating is what
    QuataFood's account recovery depends on, and free-form on it is refused
    by ``routing`` check 5 and by
    ``ck_whatsapp_messages_no_freeform_on_verify`` regardless — this refusal
    is the first of those layers, not a substitute for them.
    """
    if account is not None and account.purpose == PURPOSE_ENGAGEMENT:
        return
    _deny(
        db,
        request,
        user,
        action=action,
        resource_id=row.id,
        reason="verify_number_not_agent_answerable",
        detail={
            "reason": "verify_number_not_agent_answerable",
            "account_purpose": account.purpose if account else None,
            "message": (
                "This conversation is on the authentication number, which "
                "carries security codes only. Nothing may be sent to it from "
                "the agent console, by a person or by the AI."
            ),
        },
        http_status=status.HTTP_403_FORBIDDEN,
        account_id=row.account_id,
        product_id=row.product_id,
    )


# ---------------------------------------------------------------------------
# Replying
# ---------------------------------------------------------------------------

@router.post(
    "/admin/qcp/agent/conversations/{conversation_id}/reply",
    response_model=AgentReplyOut,
)
def qcp_agent_reply(
    conversation_id: int,
    payload: AgentReplyIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(*PERM_AGENT)),
):
    """Send one reply as the product that owns the thread.

    Through ``dispatch.send`` — the same and only entry point every product
    uses. There is no second send path here, so this reply is resolved by
    ``routing.resolve_route``, refused by the same eight checks, redacted by
    the same rules and recorded in the same outbox. While QCP is dormant the
    honest outcome is ``suppressed``/``delivery_disabled``, and that is what
    is returned rather than a cheerful "sent".

    Five refusals before the gateway is reached, all audited:

    1. the thread is not assigned to me;
    2. it is on the Verify number (check 1 of the two-check ban);
    3. the named intent routes to the authentication purpose (check 2 — this
       is the one that stops an OTP template being addressed from an
       ordinary support thread);
    4. no product owns the thread, so there is nobody to send *as*. Ingest
       leaves an ambiguous inbound unattributed on purpose and guessing an
       owner here would be the same wrong guess ``attribute_inbound``
       refuses to make; the console's reassign route is the way out;
    5. free-form outside the 24h service window. Meta refuses it and charges
       the attempt against the number's quality rating, so it is refused
       locally — the identical check ``routes_whatsapp._send`` makes, using
       the same ``conversations.service_window_open``.
    """
    from app.services.whatsapp import dispatch  # noqa: PLC0415 — see dispatch's docstring

    row = _conversation_or_404(db, conversation_id)
    account = db.get(WhatsAppAccount, row.account_id)

    _require_mine(db, request, user, row, action="agent.reply_denied")
    _require_engagement(db, request, user, row, account, action="agent.reply_denied")

    product = db.get(WhatsAppProduct, row.product_id) if row.product_id else None
    if product is None:
        _deny(
            db,
            request,
            user,
            action="agent.reply_denied",
            resource_id=row.id,
            reason="conversation_unattributed",
            detail={
                "reason": "conversation_unattributed",
                "message": (
                    "No product owns this conversation, so there is nobody to "
                    "send it as. Attribute it first — an ambiguous inbound is "
                    "given to nobody rather than guessed at."
                ),
            },
            account_id=row.account_id,
        )

    window_open = conversations_service.service_window_open(row)
    if payload.kind != "template" and not window_open:
        _deny(
            db,
            request,
            user,
            action="agent.reply_denied",
            resource_id=row.id,
            reason="outside_service_window",
            detail={
                "reason": "outside_service_window",
                "service_window_expires_at": (
                    row.service_window_expires_at.isoformat()
                    if row.service_window_expires_at
                    else None
                ),
                "message": (
                    "The 24-hour service window has closed, so a free-form "
                    "reply cannot go out. Only an approved template may be "
                    "sent until the customer writes again."
                ),
            },
            account_id=row.account_id,
            product_id=product.id,
        )

    # Check 2 of the Verify ban. ``resolve_route`` picks the account from the
    # rule's purpose, so a rule pointing at ``authentication`` would put this
    # message on the Verify number however ordinary the thread looks. Read
    # through routing's own selector — one selection implementation, not two
    # — exactly as ``routes_whatsapp._preview_template`` does, and used only
    # to *refuse*: a resolvable rule is never chosen here.
    rule = routing._find_rule(  # noqa: SLF001
        db, product_id=product.id, intent=payload.intent, locale=row.locale or None
    )
    if rule is not None and rule.purpose != PURPOSE_ENGAGEMENT:
        _deny(
            db,
            request,
            user,
            action="agent.reply_denied",
            resource_id=row.id,
            reason="authentication_intent_forbidden",
            detail={
                "reason": "authentication_intent_forbidden",
                "intent": payload.intent,
                "purpose": rule.purpose,
                "message": (
                    f"'{payload.intent}' routes to the {rule.purpose} number. "
                    "The agent console sends on the engagement number only — "
                    "an authentication template is never addressed by a human "
                    "answering support."
                ),
            },
            http_status=status.HTTP_403_FORBIDDEN,
            account_id=row.account_id,
            product_id=product.id,
        )

    # The idempotency handle. The gateway's derived key buckets by five
    # minutes and a free-form send carries no template name or variables to
    # tell two apart, so without a distinct reference an agent's second
    # sentence inside that bucket comes back ``duplicate: true`` and never
    # reaches the customer. A random token — never anything derived from the
    # agent's identity, which has no business travelling towards a product.
    reference = f"agent:{payload.client_token or uuid.uuid4().hex}"

    result = dispatch.send(
        product_slug=product.slug,
        intent=payload.intent,
        to_phone_e164=row.phone_e164,
        kind=payload.kind,
        locale=row.locale,
        variables=tuple(payload.variables),
        body=payload.body,
        reference=reference,
        source_ip=get_client_ip(request),
    )

    message_uid = result.get("message_uid")
    if message_uid and not result.get("duplicate"):
        conversations_service.attach_outbound(
            db,
            product=product,
            message_uid=message_uid,
            phone_e164=row.phone_e164,
            thread=row,
        )

    _record(
        db,
        request,
        user,
        # Also the authorship record the thread view reads back: this is what
        # makes an outbound row attributable to a person.
        action="agent.reply_sent",
        resource_type="whatsapp_message",
        resource_id=message_uid or f"conversation:{row.id}",
        outcome=audit.OUTCOME_OK if result.get("ok") else audit.OUTCOME_ERROR,
        reason=result.get("reason"),
        details={
            "conversation_id": row.id,
            "kind": payload.kind,
            "intent": payload.intent,
            "status": result.get("status"),
            "service_window_open": window_open,
            # Whose words these were. "A human approved the AI's sentence" and
            # "a human wrote this" are different events and the log has to be
            # able to tell them apart afterwards.
            "from_suggestion": payload.from_suggestion,
            "suggestion_edited": payload.suggestion_edited,
        },
        account_id=row.account_id,
        product_id=product.id,
    )
    db.commit()

    return AgentReplyOut(
        conversation_id=row.id,
        message_uid=message_uid,
        status=str(result.get("status") or "error"),
        duplicate=bool(result.get("duplicate")),
        reason=result.get("reason"),
        kind=payload.kind,
        intent=payload.intent,
        service_window_open=window_open,
        sent_by=_display_name(user) or "agent",
    )


# ---------------------------------------------------------------------------
# Handover back to automation
# ---------------------------------------------------------------------------

@router.post(
    "/admin/qcp/agent/conversations/{conversation_id}/return-to-ai",
    response_model=ReturnToAiOut,
)
def qcp_agent_return_to_ai(
    conversation_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(*PERM_AGENT)),
):
    """Hand the thread back to automation: clear the human, reopen it.

    ``conversations.return_to_ai`` is the existing verb and is called
    unchanged. It clears both halves of the handover — the human
    (``assignee_id``) and the AI-routing seam (``assigned_agent``, which
    ``handover.escalate`` sets while a thread waits for a person) — because
    NULL on both is the state automation picks a thread up from.

    ``ai_replies_enabled`` is reported because QCP ships with the AI
    answering nothing: handing a thread back while that switch is off leaves
    it open with nobody on it, and an agent should be told that at the
    moment they do it rather than discovering it from a customer's third
    message.
    """
    row = _conversation_or_404(db, conversation_id)
    _require_mine(db, request, user, row, action="agent.return_to_ai_denied")

    conversations_service.return_to_ai(db, row)
    ai_on = _flag(KEY_AI_REPLIES_ENABLED)
    _record(
        db,
        request,
        user,
        action="agent.returned_to_ai",
        resource_id=row.id,
        details={"state": row.state, "ai_replies_enabled": ai_on},
        account_id=row.account_id,
        product_id=row.product_id,
    )
    db.commit()
    db.refresh(row)
    return ReturnToAiOut(
        conversation_id=row.id,
        state=row.state,
        mine=False,
        ai_replies_enabled=ai_on,
    )


# ---------------------------------------------------------------------------
# The thread
# ---------------------------------------------------------------------------

def _authors(db: Session, messages: list[WhatsAppMessage]) -> dict:
    """Who wrote each outbound message, read out of the audit log.

    ``whatsapp_messages`` has no author column and deliberately gains none
    here — the audit row that recorded the send already knows who asked for
    it, and a second source of truth for authorship is a second thing to get
    out of step. ``ai.*`` marks the AI layer's own sends, ``agent.*`` with an
    actor marks a human, and an outbound row with neither is the product's
    automation.
    """
    uids = [m.message_uid for m in messages if m.direction == "outbound"]
    if not uids:
        return {}
    rows = (
        db.query(WhatsAppAuditLog)
        .filter(
            WhatsAppAuditLog.resource_type == "whatsapp_message",
            WhatsAppAuditLog.resource_id.in_(uids),
        )
        .order_by(WhatsAppAuditLog.id)
        .all()
    )
    actor_ids = {r.actor_id for r in rows if r.actor_id}
    names = (
        {
            u.id: _display_name(u)
            for u in db.query(User).filter(User.id.in_(actor_ids)).all()
        }
        if actor_ids
        else {}
    )

    resolved: dict = {}
    for entry in rows:
        action = entry.action or ""
        if action.startswith(AI_AUDIT_PREFIX):
            resolved[entry.resource_id] = ("ai", (entry.details or {}).get("model"))
        elif action.startswith(AGENT_AUDIT_PREFIX) and entry.actor_id:
            resolved.setdefault(
                entry.resource_id, ("agent", names.get(entry.actor_id))
            )
    return resolved


@router.get(
    "/admin/qcp/agent/conversations/{conversation_id}/thread", response_model=ThreadOut
)
def qcp_agent_thread(
    conversation_id: int,
    limit: int = Query(default=50, ge=1, le=200),
    before_id: Optional[int] = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(*PERM_AGENT)),
):
    """The whole thread, oldest first, with who said what.

    An agent picking a conversation up mid-flight has to see what the bot
    already told this person or they will contradict it — so ``author``
    distinguishes the customer, the AI, a named colleague and the product's
    own automation, rather than collapsing all three of the last into
    "outbound".

    Not scoped by product: like the operator console, an agent sees the whole
    thread. The message bodies are already redacted at write time (an OTP is
    stored as a digest), so nothing is un-redacted to render this.
    """
    row = _conversation_or_404(db, conversation_id)
    account = db.get(WhatsAppAccount, row.account_id)
    product = db.get(WhatsAppProduct, row.product_id) if row.product_id else None
    holder = db.get(User, row.assignee_id) if row.assignee_id else None
    products = {p.id: p.slug for p in db.query(WhatsAppProduct).all()}

    newest_first = conversations_service.history(
        db, row, limit=limit, before_id=before_id
    )
    authors = _authors(db, newest_first)
    next_before_id = newest_first[-1].id if len(newest_first) == limit else None

    messages = []
    for message in reversed(newest_first):
        if message.direction == "inbound":
            author, label = "customer", row.display_name or row.phone_e164
        else:
            author, label = authors.get(
                message.message_uid, ("automation", products.get(message.product_id))
            )
        messages.append(
            ThreadMessageOut(
                id=message.id,
                message_uid=message.message_uid,
                direction=message.direction,
                kind=message.kind,
                status=message.status,
                intent=message.intent,
                product=products.get(message.product_id),
                account_purpose=message.account_purpose,
                body=message.body,
                variables=message.variables or {},
                author=author,
                author_label=label,
                suppressed_reason=message.suppressed_reason,
                error_code=message.error_code,
                created_at=message.created_at,
                sent_at=message.sent_at,
                delivered_at=message.delivered_at,
                read_at=message.read_at,
            )
        )

    return ThreadOut(
        conversation=_queue_item(
            row,
            account=account,
            product=product,
            holder=holder,
            viewer_id=user.id,
            now=_now(),
        ),
        messages=messages,
        next_before_id=next_before_id,
        ai=_ai_state(db),
        templates=_sendable_templates(db, row, product, account),
    )


def _sendable_templates(
    db: Session,
    row: WhatsAppConversation,
    product: Optional[WhatsAppProduct],
    account: Optional[WhatsAppAccount],
) -> list[AgentTemplateOut]:
    """The approved templates an agent may address on this thread.

    Only reachable ones: this product's own active routing rules whose
    purpose is ``engagement``, resolved to an approved template on the
    engagement number. The Verify number's templates are unreachable here by
    construction, not by filtering — no engagement rule points at one.

    Empty is a real and common answer. It means this customer cannot be
    reached once the 24-hour window closes until they write again, which the
    console says in those words rather than rendering an empty picker.
    """
    # No product owns the thread, or it is not on the engagement number:
    # either way there is nothing an agent may address here.
    if product is None or account is None or account.purpose != PURPOSE_ENGAGEMENT:
        return []
    rules = (
        db.query(WhatsAppRoutingRule)
        .filter(
            WhatsAppRoutingRule.product_id == product.id,
            WhatsAppRoutingRule.is_active == True,  # noqa: E712
            WhatsAppRoutingRule.purpose == PURPOSE_ENGAGEMENT,
        )
        .order_by(WhatsAppRoutingRule.priority.asc(), WhatsAppRoutingRule.id.asc())
        .all()
    )
    out: list[AgentTemplateOut] = []
    seen: set[str] = set()
    for rule in rules:
        if rule.intent in seen or (rule.conditions or {}):
            continue
        template = routing._find_template(  # noqa: SLF001
            db,
            account_id=account.id,
            intent=rule.template_intent,
            language=row.locale or rule.locale or "en",
        )
        if template is None:
            continue
        seen.add(rule.intent)
        out.append(
            AgentTemplateOut(
                intent=rule.intent,
                name=template.name,
                language=template.language,
                category=template.category,
                body=None,
                variables=[str(v) for v in (template.variables or [])],
            )
        )
    return out


# ---------------------------------------------------------------------------
# The suggested reply
# ---------------------------------------------------------------------------

def _flag(key: str) -> bool:
    """A site setting read as a boolean, defaulting to **off**.

    Absent means off, so a database that has never been through the QCP
    console suggests nothing and answers nothing — the same direction
    ``settings_store.delivery_enabled`` defaults in, and for the same reason.
    """
    raw = site_settings.get_setting(key, None)
    return str(raw or "").strip().lower() in _TRUE


def _ai_suggest():
    """The installed AI drafting callable, or None.

    Read off the QCP package facade at call time — the same way every other
    caller outside ``app/services/whatsapp`` reaches into it, and the reason
    this console does not import an AI submodule directly. An absent name is
    a supported state, not an error: it means no AI layer is installed, and
    the endpoint says so rather than improvising one.
    """
    from app.services import whatsapp as qcp  # noqa: PLC0415 — the facade, resolved late

    candidate = getattr(qcp, AI_FACADE_ATTR, None)
    return candidate if callable(candidate) else None


def _normalise_draft(raw) -> dict:
    """One shape out of the AI layer, whichever shape it hands back.

    A mapping is used as given. Anything else is read by attribute, which is
    what lets the AI layer return its own decision object unchanged — it
    already carries ``text``, ``model``, ``prompt_version`` and a ``reason``,
    and re-wrapping those into a dict for this caller alone would be a second
    place for the vocabulary to drift.

    The escalation rule is deliberately *fail-closed*: a decision escalates
    here unless its action explicitly says there is something to say. An
    unrecognised action is not an invitation to render whatever text came
    with it.
    """
    if isinstance(raw, dict):
        return raw
    action = getattr(raw, "action", None)
    return {
        "text": getattr(raw, "text", None),
        "model": getattr(raw, "model", None),
        "prompt_version": getattr(raw, "prompt_version", None),
        "escalate": bool(getattr(raw, "must_escalate", False))
        or (action is not None and action != AI_ACTION_REPLY),
        "reason": getattr(raw, "reason", None),
    }


def _unverified_figures(text: str) -> list[str]:
    """Figures in a draft that nothing in this request can vouch for.

    This module calls no product API, so no balance, payment, refund, order
    total or KYC decision was *fetched* while composing the draft. Any number
    in it therefore came from the model. Returned rather than stripped:
    editing a sentence to remove its number leaves a claim with a hole in it,
    and the correct outcome is that a human answers this one.
    """
    return [match.group(0) for match in _FIGURE.finditer(text or "")]


@router.post(
    "/admin/qcp/agent/conversations/{conversation_id}/suggest",
    response_model=SuggestedReplyOut,
)
def qcp_agent_suggest(
    conversation_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(*PERM_AGENT)),
):
    """Draft a reply for the agent to edit and send. Sends nothing.

    A draft an agent corrects is more useful than full automation and very
    much safer, and this endpoint is built so that the safety does not rest
    on the model's behaviour:

    * **Off by default.** ``whatsapp.ai_suggestions_enabled`` is absent on a
      fresh install, so the console drafts nothing until an operator says so.
      It is a different switch from the AI layer's own reply switch: drafting
      for a human and answering a customer unattended are not the same risk.
    * **Never about a Verify thread.** The engagement check runs before the
      AI is consulted, so a conversation on the authentication number is
      never handed to a model at all.
    * **Never outside the service window.** Free-form prose cannot legally
      leave then, so a free-form draft is not something to hand an agent.
    * **Never a figure.** See ``_unverified_figures``. A draft carrying one
      is withheld and the thread escalates, and the withheld text is not
      returned in any other field.
    * **Never a send.** There is no path from here to ``dispatch``; the agent
      posts the reply themselves, which is also what puts their name on it.

    Audited either way, with the model, the prompt version and *why* it
    answered rather than escalating — which is the question asked first when
    a customer says the bot told them something.
    """
    row = _conversation_or_404(db, conversation_id)
    account = db.get(WhatsAppAccount, row.account_id)

    _require_mine(db, request, user, row, action="agent.suggestion_denied")
    _require_engagement(db, request, user, row, account, action="agent.suggestion_denied")

    if not conversations_service.service_window_open(row):
        _deny(
            db,
            request,
            user,
            action="agent.suggestion_denied",
            resource_id=row.id,
            reason="outside_service_window",
            detail={
                "reason": "outside_service_window",
                "message": (
                    "The 24-hour service window has closed. A free-form draft "
                    "could not be sent, so none is offered — use an approved "
                    "template."
                ),
            },
            account_id=row.account_id,
            product_id=row.product_id,
        )

    if not _flag(KEY_AI_SUGGESTIONS_ENABLED):
        _deny(
            db,
            request,
            user,
            action="agent.suggestion_denied",
            resource_id=row.id,
            reason="ai_suggestions_disabled",
            detail={
                "reason": "ai_suggestions_disabled",
                "message": (
                    "AI drafting is switched off. Turn on "
                    f"'{KEY_AI_SUGGESTIONS_ENABLED}' to let agents ask for a "
                    "suggested reply."
                ),
            },
            account_id=row.account_id,
            product_id=row.product_id,
        )

    suggest = _ai_suggest()
    if suggest is None:
        _deny(
            db,
            request,
            user,
            action="agent.suggestion_denied",
            resource_id=row.id,
            reason="ai_unavailable",
            detail={
                "reason": "ai_unavailable",
                "message": (
                    "No AI support layer is installed, so there is nothing to "
                    "draft with. The console does not improvise one."
                ),
            },
            http_status=status.HTTP_503_SERVICE_UNAVAILABLE,
            account_id=row.account_id,
            product_id=row.product_id,
        )

    history = conversations_service.history(db, row, limit=30)
    try:
        raw = _normalise_draft(suggest(db, row, messages=history) or {})
    except Exception as exc:  # noqa: BLE001 — an AI outage is not an agent's problem
        _deny(
            db,
            request,
            user,
            action="agent.suggestion_denied",
            resource_id=row.id,
            reason="ai_error",
            detail={
                "reason": "ai_error",
                # Type only: a provider error string can carry the prompt back,
                # and the prompt carries the customer's message.
                "error_type": type(exc).__name__,
                "message": (
                    "The AI layer failed to produce a draft. Answer this one "
                    "yourself."
                ),
            },
            http_status=status.HTTP_502_BAD_GATEWAY,
            account_id=row.account_id,
            product_id=row.product_id,
        )

    draft = str(raw.get("text") or "").strip()
    model = raw.get("model")
    prompt_version = raw.get("prompt_version")
    escalate = bool(raw.get("escalate"))
    reason = raw.get("reason")

    figures: list[str] = []
    if not escalate and draft:
        figures = _unverified_figures(draft)
        if figures:
            # Anything touching money escalates rather than being answered,
            # and a number nothing in this request fetched is money-shaped by
            # definition.
            escalate = True
            reason = "unverified_figures"
    if not draft and not escalate:
        escalate = True
        reason = reason or "no_draft"

    withheld = escalate
    _record(
        db,
        request,
        user,
        action="agent.suggestion_withheld" if withheld else "agent.suggestion_served",
        resource_id=row.id,
        details={
            "model": model,
            "prompt_version": prompt_version,
            "decision": "escalated" if withheld else "answered",
            "reason": reason,
            # A count, not the text: the withheld figure was invented and
            # writing it into the audit log would give it a second life.
            "figures_found": len(figures),
        },
        account_id=row.account_id,
        product_id=row.product_id,
    )
    db.commit()

    return SuggestedReplyOut(
        conversation_id=row.id,
        draft=None if withheld else draft,
        escalate=escalate,
        reason=reason,
        model=model if isinstance(model, str) else None,
        prompt_version=prompt_version if isinstance(prompt_version, str) else None,
        service_window_open=True,
    )
