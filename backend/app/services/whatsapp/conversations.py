"""The conversation engine — threads, ownership and the service window.

A conversation is one contact on one account. Four things live here:

**Why this is hard.** ``(account_id, wa_contact_id)`` is unique, so four
products sharing the "QUATA" engagement number share *one* row per customer.
An inbound reply on that number is therefore genuinely ambiguous, and every
heuristic for resolving it is a guess:

* *First touch* — the first product ever to message the number owns every
  later reply. Won by a race, and a race a caller can rig with one cheap
  utility send to a guessable phone number.
* *Last touch* — the product that most recently addressed the contact owns
  the next reply. Strictly worse: no race to win, just one message, at will,
  repeatedly, and it also flipped ``product_id`` out from under the previous
  owner so that product lost the thread it had already been served.

Neither is used. Attribution is now evidence-based and fails closed:

1. ``attribute_inbound()`` prefers Meta's own threading. A reply carries
   ``context.id`` — the wamid of the message it answers — which no other
   product can forge because it only exists once *we* sent that message.
   The inbound goes to the product that owns that outbound row.
2. With no context, the only unambiguous case is "exactly one product has
   addressed this contact inside the service window". Two or more, and the
   message is attributed to **nobody**: it stays out of every product's API
   and is surfaced to the admin console (which sees the whole thread) plus
   an audit row. A human resolving a rare ambiguity is correct; silently
   handing a customer's reply to the wrong company is not.

**Ownership and visibility.** Reading and changing a thread are two
different questions with two different answers, because widening one to fix
attribution must not widen the other:

* ``for_product()`` — may this product *see* the row? Yes when it owns it
  (``product_id``) **or** when it already has a message in it. That second
  clause is what makes attribution non-destructive: deciding who gets the
  *next* inbound never retracts a thread a product has already been served.
* ``owned_by_product()`` — may this product *change* the row? Ownership
  only. ``state``, ``unread_count`` and ``assignee_id`` are one shared row
  for four products, and participation costs one utility send to a guessable
  phone number; if that bought the state verbs it would buy the power to
  close a peer's live customer thread or take its agent off it. It also
  gates naming a ``conversation_id`` on a send, because for free-form that
  is a claim on the service window somebody else's customer opened.

``product_id`` itself only ever moves from NULL to a product —
``adopt_if_unowned()`` — so sending can no longer take a thread from anyone.
Message-level separation is independent of all of this: ``history()``
filters on ``whatsapp_messages.product_id``, so sharing a thread row never
shares a message. Note what ownership deliberately does *not* gate: a
template send addressed by phone number. Every OTP is one of those, and
four products share the Quata Verify number, so gating sends on ownership
would have made a peer's row an account lockout.

**The service window.** Meta allows free-form replies for 24 hours after a
contact's last inbound message. ``service_window_expires_at`` is that
deadline, maintained here so nothing has to recompute it, and
``service_window_open()`` is what a free-form send checks. (On the Verify
number free-form is refused regardless — see ``routing.resolve_route``
check 5 and ``ck_whatsapp_messages_no_freeform_on_verify``.)

**Handover.** ``assign()`` puts a human agent on the thread;
``return_to_ai()`` takes them off. Note the column: v1 uses ``assignee_id``
(the real FK to ``users``). ``assigned_agent`` is the AI-routing seam and
v1 writes NULL to it and never reads it, so "return to AI" means *clear the
human assignee and reopen*, which is exactly the state automation picks a
thread up from.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models import User, WhatsAppConversation, WhatsAppMessage, WhatsAppProduct


STATE_OPEN = "open"
STATE_SNOOZED = "snoozed"
STATE_CLOSED = "closed"
STATES = (STATE_OPEN, STATE_SNOOZED, STATE_CLOSED)

# Meta's free-form reply window.
SERVICE_WINDOW = timedelta(hours=24)

# A conversation may only be handed to a user whose role carries one of
# these. ``settings:manage`` is the permission the WhatsApp admin console
# itself gates on (``routes_admin_whatsapp.PERM``); the two explicit
# ``whatsapp:*`` grants exist so an agent role can be entitled to answer
# customers without being entitled to reconfigure the platform.
WHATSAPP_AGENT_PERMISSIONS = frozenset(
    {"whatsapp:agent", "whatsapp:manage", "settings:manage"}
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_aware(value: Optional[datetime]) -> Optional[datetime]:
    """SQLite hands back naive datetimes; comparisons need them aware."""
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Lookup + ownership
# ---------------------------------------------------------------------------

def _participates(db: Session, *, conversation_id: int, product_id: int) -> bool:
    """Does this product already have a message in this thread?

    Both directions count, and that is the point. A product's own outbound
    row and an inbound row attributed to it are the *evidence* that it has
    been served this thread. Deciding who gets the next inbound must never
    revoke that (see the module docstring, property 3), and a rule derived
    from the message log cannot revoke it, because nothing rewrites a
    message's ``product_id`` after it is written.
    """
    return (
        db.query(WhatsAppMessage.id)
        .filter(
            WhatsAppMessage.conversation_id == conversation_id,
            WhatsAppMessage.product_id == product_id,
        )
        .first()
        is not None
    )


def for_product(
    db: Session, *, product: WhatsAppProduct, conversation_id: int
) -> Optional[WhatsAppConversation]:
    """A conversation, but only if this product has a claim on it.

    Two claims, both verified against stored state — never inferred from the
    request, never from a phone number the caller supplied:

    * it **owns** the thread (``product_id``), or
    * it already has a **message** in the thread.

    The second exists because ``(account_id, wa_contact_id)`` is unique: four
    products on the shared number land on one row, and gating on ownership
    alone meant the loser of that single-owner contest lost access to its own
    conversation — retroactively, the moment another product sent. What a
    product reads out of a shared thread is still only its own, because
    ``history()`` filters messages on ``product_id`` independently.

    A thread nobody owns and nobody has messaged (an inbound-only, still
    unattributed conversation) belongs to no product and stays invisible
    here; the router turns None into a 404 rather than a 403, so a product
    cannot probe for another's threads either.
    """
    row = db.get(WhatsAppConversation, conversation_id)
    if row is None:
        return None
    if row.product_id == product.id:
        return row
    if _participates(db, conversation_id=row.id, product_id=product.id):
        return row
    return None


def owned_by_product(
    db: Session, *, product: WhatsAppProduct, conversation_id: int
) -> Optional[WhatsAppConversation]:
    """A conversation, but only if this product **owns** it.

    ``for_product`` above answers "may this product *see* this thread?" and
    deliberately says yes to a mere participant, because a product must not
    lose sight of a message it was already given. This answers the narrower
    question "may this product *change* this thread?", and participation is
    not enough.

    The difference matters because ``state``, ``unread_count`` and
    ``assignee_id`` are one shared row for all four products on the
    engagement number. Letting a participant write them would mean one cheap
    utility send to a guessable phone number buys the power to close another
    product's live customer thread, zero its unread badge, or take its human
    agent off it. Reading your own messages is a claim on your own data;
    closing the thread is a claim on somebody else's.

    A product with a genuine need to work a thread it does not own has to be
    *given* it — ``product_id`` is NULL until someone sends, and the first
    sender keeps it (``adopt_if_unowned``).
    """
    row = db.get(WhatsAppConversation, conversation_id)
    if row is None or row.product_id != product.id:
        return None
    return row


def list_for_product(
    db: Session,
    *,
    product: WhatsAppProduct,
    state: Optional[str] = None,
    phone_e164: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> list[WhatsAppConversation]:
    """The threads this product owns *or* already has a message in.

    Same two claims as ``for_product`` — a listing that dropped a thread the
    detail endpoint still serves would just make the loss harder to see.
    """
    participating = db.query(WhatsAppMessage.conversation_id).filter(
        WhatsAppMessage.product_id == product.id,
        WhatsAppMessage.conversation_id.isnot(None),
    )
    q = db.query(WhatsAppConversation).filter(
        or_(
            WhatsAppConversation.product_id == product.id,
            WhatsAppConversation.id.in_(participating),
        )
    )
    if state:
        q = q.filter(WhatsAppConversation.state == state)
    if phone_e164:
        q = q.filter(WhatsAppConversation.phone_e164 == phone_e164)
    return (
        q.order_by(WhatsAppConversation.last_inbound_at.desc(), WhatsAppConversation.id.desc())
        .limit(max(min(limit, 200), 1))
        .offset(max(offset, 0))
        .all()
    )


# ---------------------------------------------------------------------------
# Upsert + window arithmetic
# ---------------------------------------------------------------------------

def upsert_conversation(
    db: Session,
    *,
    account_id: int,
    wa_contact_id: str,
    phone_e164: str,
    display_name: Optional[str] = None,
    product_id: Optional[int] = None,
    locale: Optional[str] = None,
) -> WhatsAppConversation:
    """Find or create the thread for (account, contact).

    ``product_id`` is used when the row is *created*, and to adopt a thread
    that belongs to nobody yet (an inbound-only conversation). Moving an
    already-attributed thread from one product to another is not done here
    and is not done anywhere — see ``adopt_if_unowned``. Inbound calls this
    with no product at all, so ingest never touches ownership.
    """
    row = (
        db.query(WhatsAppConversation)
        .filter(
            WhatsAppConversation.account_id == account_id,
            WhatsAppConversation.wa_contact_id == wa_contact_id,
        )
        .first()
    )
    if row is None:
        row = WhatsAppConversation(
            account_id=account_id,
            product_id=product_id,
            wa_contact_id=wa_contact_id,
            phone_e164=phone_e164,
            display_name=display_name,
            state=STATE_OPEN,
            unread_count=0,
            locale=locale,
            meta={},
        )
        db.add(row)
        db.flush()
        return row

    if row.product_id is None and product_id is not None:
        row.product_id = product_id
    if display_name and not row.display_name:
        row.display_name = display_name
    if locale and not row.locale:
        row.locale = locale
    return row


def adopt_if_unowned(
    db: Session, conversation: WhatsAppConversation, *, product_id: int
) -> WhatsAppConversation:
    """Give an **unowned** thread an owner. Never takes an owned one.

    This replaces the two heuristics that came before it, both of which
    decided ownership by *contest*:

    * first-touch — the winner of a race a caller can rig by pre-claiming a
      guessable phone number with one cheap utility send;
    * last-touch — no race at all, just one message, at will, repeatedly.
      It also *moved* ``product_id``, so the previous owner immediately 404'd
      on a thread it had already been served. That is the retroactive loss
      property 3 forbids, and it is why nothing here ever reassigns.

    ``product_id`` now only ever moves NULL → product. Sending cannot take a
    thread from anybody, so there is no silent takeover to audit (property
    4): the only ownership change a send can cause is filling in a blank.
    Who receives an inbound *message* is a separate decision made from
    evidence — see ``attribute_inbound``.
    """
    if conversation.product_id is None:
        conversation.product_id = product_id
        db.flush()
    return conversation


# ---------------------------------------------------------------------------
# Inbound attribution
# ---------------------------------------------------------------------------

# Why a given inbound was (or was not) given to a product. Recorded so the
# admin console can answer "why did nobody get this?" without re-deriving it.
BASIS_CONTEXT = "context"
BASIS_SOLE_ADDRESSEE = "sole_addressee"
BASIS_SOLE_PARTICIPANT = "sole_participant"
BASIS_UNADDRESSED = "unaddressed"
BASIS_AMBIGUOUS = "ambiguous"


def _addressing_products(
    db: Session, conversation: WhatsAppConversation, *, since: Optional[datetime] = None
) -> list[int]:
    """Distinct products that have *reached* this contact on this thread.

    ``suppressed`` is excluded: nothing left the building, so the customer
    cannot be replying to it. Everything else counts — a queued send is
    still an attempt this platform accepted and will deliver.
    """
    q = db.query(WhatsAppMessage.product_id, WhatsAppMessage.created_at).filter(
        WhatsAppMessage.conversation_id == conversation.id,
        WhatsAppMessage.direction == "outbound",
        WhatsAppMessage.status != "suppressed",
        WhatsAppMessage.product_id.isnot(None),
    )
    found: set[int] = set()
    for product_id, created_at in q.all():
        # Filtered in Python, not SQL: ``created_at`` is a server default, so
        # SQLite stores it naive and Postgres stores it aware. Comparing a
        # tz-aware bind parameter against the SQLite form is a string
        # comparison with an offset suffix on one side only.
        if since is not None:
            when = _as_aware(created_at)
            if when is None or when < since:
                continue
        found.add(product_id)
    return sorted(found)


def attribute_inbound(
    db: Session,
    conversation: WhatsAppConversation,
    *,
    context_wamid: Optional[str] = None,
    now: Optional[datetime] = None,
) -> tuple[Optional[int], str, list[int]]:
    """Which product does this new inbound message belong to?

    Returns ``(product_id, basis, candidates)``. ``product_id`` is None when
    the answer is genuinely unknown — that is a supported outcome, not a
    failure, and it is the entire fix.

    **1. Meta's own threading, when it exists.** A reply carries
    ``context.id``: the wamid of the message being answered. A wamid only
    exists because *we* sent that message and Meta gave us the id back, so
    one product cannot manufacture another product's wamid — unlike "who
    sent last", which any enabled product can set to itself for the price of
    one template. When the context resolves to an outbound row on this
    thread, its owner gets the reply. Authoritative, so it beats everything
    below, including the thread's own ``product_id``.

    **2. No context: one candidate, or nobody.** Everything left is a guess,
    so the only case answered is the one with a single possible answer:

    * exactly one product addressed the contact inside the 24h service
      window → that product;
    * nobody did, but exactly one product has *ever* messaged this thread →
      that product. Not a tie-break — there is literally one candidate. This
      is the ordinary "customer replies to a three-day-old order update"
      case, and refusing it would strand single-product threads;
    * two or more → **nobody**. The message is real and it is ambiguous;
      handing it to a guess hands one company's customer reply to another.
      It stays out of every product's API and is surfaced in the admin
      console, which sees the whole thread regardless;
    * nobody has ever messaged this thread → nobody. A cold inbound belongs
      to no product until one answers it.

    Note what is *not* consulted for the no-context case: the thread's
    ``product_id``. Ownership is a claim on the thread; it is not evidence
    about who this particular message is for.
    """
    reference = _as_aware(now) or _now()

    if context_wamid:
        parent = (
            db.query(WhatsAppMessage)
            .filter(
                WhatsAppMessage.provider_message_id == str(context_wamid)[:80],
                WhatsAppMessage.conversation_id == conversation.id,
                WhatsAppMessage.direction == "outbound",
            )
            .first()
        )
        if parent is not None and parent.product_id is not None:
            return parent.product_id, BASIS_CONTEXT, [parent.product_id]

    in_window = _addressing_products(db, conversation, since=reference - SERVICE_WINDOW)
    if len(in_window) == 1:
        return in_window[0], BASIS_SOLE_ADDRESSEE, in_window
    if len(in_window) > 1:
        return None, BASIS_AMBIGUOUS, in_window

    ever = _addressing_products(db, conversation)
    if len(ever) == 1:
        return ever[0], BASIS_SOLE_PARTICIPANT, ever
    if len(ever) > 1:
        return None, BASIS_AMBIGUOUS, ever
    return None, BASIS_UNADDRESSED, []


def wa_contact_id_for(phone_e164: str) -> str:
    """Meta's ``wa_id`` — E.164 without the ``+``.

    Outbound sends know only the phone number, inbound webhooks know only
    the ``wa_id``. Deriving one from the other with the same rule the
    webhook parser uses (``webhooks._to_e164`` inverted) is what makes both
    directions land on a *single* conversation row instead of two.
    """
    digits = "".join(ch for ch in str(phone_e164) if ch.isdigit())
    return (digits or str(phone_e164))[:40]


def phone_e164_for(value: str) -> str:
    """Canonical ``+<digits>`` for a phone as supplied by a caller.

    Query strings decode ``+`` as a space unless it was percent-encoded, so
    ``?phone=+237600000001`` arrives as ``" 237600000001"``. Rebuilding the
    number from its digits means a product that forgot to escape gets the
    right thread instead of an empty list.
    """
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    return f"+{digits}" if digits else str(value).strip()[:24]


def attach_outbound(
    db: Session,
    *,
    product: WhatsAppProduct,
    message_uid: str,
    phone_e164: str,
    thread: Optional[WhatsAppConversation] = None,
) -> Optional[WhatsAppConversation]:
    """Link a just-accepted outbound message to its conversation.

    ``dispatch.send`` deliberately knows nothing about threads — it routes,
    persists and hands off. Attribution is the gateway's job, and doing it
    here (rather than inside dispatch) keeps the choke point free of
    anything that could fail a send.

    Suppressed rows are attached too: "why did this customer never get their
    OTP?" is a conversation-level question, and hiding the refusal from the
    thread is exactly how that becomes unanswerable.

    Every accepted send lands on a thread. A row left with
    ``conversation_id IS NULL`` is a message nobody can answer, page, or
    audit at the thread level, and it used to be the routine outcome of two
    products talking to the same customer. Ownership of the *thread* is a
    separate question from attachment of the *message*, and only the first
    of those two is contested — ``history()``'s own ``product_id`` filter is
    what keeps one product's messages out of another's history, so attaching
    is always safe.
    """
    row = (
        db.query(WhatsAppMessage)
        .filter(WhatsAppMessage.message_uid == message_uid)
        .first()
    )
    if row is None or row.account_id is None:
        return None

    conversation = thread
    if conversation is None:
        conversation = upsert_conversation(
            db,
            account_id=row.account_id,
            wa_contact_id=wa_contact_id_for(phone_e164),
            phone_e164=phone_e164[:24],
            product_id=product.id,
        )
    # Fills in a blank owner; never takes an owned thread from anybody. A
    # suppressed send adopts too — the refusal has to be visible to whoever
    # asked for it — because adoption is no longer a claim on future inbound
    # traffic, so there is nothing left for it to win.
    adopt_if_unowned(db, conversation, product_id=product.id)

    row.conversation_id = conversation.id
    if row.status != "suppressed":
        touch_outbound(db, conversation)
    db.flush()
    return conversation


def touch_inbound(
    db: Session,
    conversation: WhatsAppConversation,
    *,
    at: Optional[datetime] = None,
    now: Optional[datetime] = None,
):
    """Record an inbound message: refresh the 24h window, bump unread.

    ``at`` is Meta's timestamp, which is neither trusted nor ordered:

    * **Clamped forward.** A message cannot have arrived in the future, so a
      skewed timestamp is pulled back to now. Left alone it opened the
      free-form gate arbitrarily far past the real 24h — and a free-form
      send outside Meta's *own* window is refused **and** charged against
      the number's quality rating, which is the exact cost this gate exists
      to avoid.
    * **Monotonic.** Meta redelivers out of sequence. Recomputing the
      deadline unconditionally let an old redelivery drag the window
      backwards (observed: 2026-09-22 → 2023-11-15), after which a
      legitimate reply on a genuinely open thread is refused 409
      ``outside_service_window``. Neither the deadline nor
      ``last_inbound_at`` ever moves back.

    A closed thread reopens — a customer replying to a closed conversation
    is starting a live one, and leaving it closed would hide it from every
    agent queue.
    """
    ceiling = _as_aware(now) or _now()
    when = _as_aware(at) or ceiling
    if when > ceiling:
        when = ceiling

    previous_inbound = _as_aware(conversation.last_inbound_at)
    if previous_inbound is None or when > previous_inbound:
        conversation.last_inbound_at = when

    expires = when + SERVICE_WINDOW
    current_expiry = _as_aware(conversation.service_window_expires_at)
    if current_expiry is None or expires > current_expiry:
        conversation.service_window_expires_at = expires

    conversation.unread_count = (conversation.unread_count or 0) + 1
    if conversation.state == STATE_CLOSED:
        conversation.state = STATE_OPEN
    db.flush()
    return conversation


def touch_outbound(db: Session, conversation: WhatsAppConversation, *, at: Optional[datetime] = None):
    """Record an outbound message. Does not move the service window —
    only the *contact* can reopen it."""
    conversation.last_outbound_at = _as_aware(at) or _now()
    db.flush()
    return conversation


def service_window_open(conversation: WhatsAppConversation, *, now: Optional[datetime] = None) -> bool:
    expires = _as_aware(conversation.service_window_expires_at)
    if expires is None:
        return False
    return expires > (_as_aware(now) or _now())


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------

def open_conversation(db: Session, conversation: WhatsAppConversation) -> WhatsAppConversation:
    conversation.state = STATE_OPEN
    db.flush()
    return conversation


def close_conversation(db: Session, conversation: WhatsAppConversation) -> WhatsAppConversation:
    """Close the thread and drop the unread badge. The assignee is kept so
    the log still answers "who handled this?"."""
    conversation.state = STATE_CLOSED
    conversation.unread_count = 0
    db.flush()
    return conversation


def mark_read(db: Session, conversation: WhatsAppConversation) -> WhatsAppConversation:
    conversation.unread_count = 0
    db.flush()
    return conversation


def _is_whatsapp_agent(user: User) -> bool:
    """Does this user's role carry a WhatsApp-agent entitlement?

    The ``"*"`` wildcard a super_admin holds is deliberately **not** honoured
    here, unlike in ``deps.require_permission``. That wildcard is a grant to
    a human sitting in the cockpit; ``assign`` is reached with a *machine*
    credential, and treating the wildcard as an entitlement would let any
    product park customer conversations on the boss's queue. A super_admin
    who really does handle WhatsApp gets one of the permissions below on
    their role, explicitly.
    """
    role = getattr(user, "role", None)
    if role is None:
        return False
    return any(
        p.permission in WHATSAPP_AGENT_PERMISSIONS for p in (role.permissions or ())
    )


def assign(
    db: Session, conversation: WhatsAppConversation, *, user_id: int
) -> WhatsAppConversation:
    """Hand the thread to a human agent.

    Raises ``ValueError("unknown_agent")`` — the same code the router maps to
    400 — for **every** reason a user cannot take the thread: no such user,
    inactive, soft-deleted, or holding no WhatsApp-agent entitlement.

    They are one answer on purpose. This endpoint authenticates a product's
    API key, not a person, so a per-reason answer is an oracle: a caller
    walks ``assignee_id`` and reads back which ``users.id`` values exist and
    are active in the QuataDigital cockpit. Requiring the entitlement then
    caps what a caller can do with a valid id — customer conversations land
    only on people whose job is to answer them.
    """
    user = db.get(User, user_id)
    if (
        user is None
        or not user.is_active
        or getattr(user, "is_deleted", False)
        or not _is_whatsapp_agent(user)
    ):
        raise ValueError("unknown_agent")
    conversation.assignee_id = user.id
    if conversation.state == STATE_CLOSED:
        conversation.state = STATE_OPEN
    db.flush()
    return conversation


def return_to_ai(db: Session, conversation: WhatsAppConversation) -> WhatsAppConversation:
    """Take the human off the thread and reopen it.

    ``assigned_agent`` (the AI-routing seam) is deliberately left untouched:
    v1 never writes it, so nothing downstream can start depending on a
    half-defined value.
    """
    conversation.assignee_id = None
    if conversation.state != STATE_OPEN:
        conversation.state = STATE_OPEN
    db.flush()
    return conversation


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------

def history(
    db: Session,
    conversation: WhatsAppConversation,
    *,
    limit: int = 50,
    before_id: Optional[int] = None,
    product_id: Optional[int] = None,
) -> list[WhatsAppMessage]:
    """Messages newest-first, keyset-paged on id.

    ``product_id`` is a second, independent scope: the product-facing API
    passes it so a row that somehow carries another product's id can never
    surface in this product's history, even if the conversation itself is
    correctly owned. The admin console omits it and sees the whole thread.
    """
    q = db.query(WhatsAppMessage).filter(
        WhatsAppMessage.conversation_id == conversation.id
    )
    if product_id is not None:
        q = q.filter(WhatsAppMessage.product_id == product_id)
    if before_id:
        q = q.filter(WhatsAppMessage.id < before_id)
    return q.order_by(WhatsAppMessage.id.desc()).limit(max(min(limit, 200), 1)).all()
