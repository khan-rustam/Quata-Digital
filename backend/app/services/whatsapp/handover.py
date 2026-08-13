"""Escalation and handover — when QCP's AI support layer must fetch a human.

This module is the *brake*, not the engine. It never composes a reply and it
never sends one; it answers one question — "may automation speak here, or is
this a human's job?" — and owns the state that makes the answer stick.

**Why the brake is a separate module.** The AI is talking to real customers
in Cameroon on a number that also carries money and identity traffic. A
plausible invented sentence about a balance, a refund or a KYC decision is
worse than no answer at all, and a prompt is not a control: it is text the
model may ignore, and text an inbound message can argue with. So every rule
below is code, applied to the *inputs* of the model and to the *output* of
the send path, and is not reachable from anything the customer or the model
can write.

The bias is one-directional and deliberate: **when in doubt, a human.** A
needless escalation costs a slightly busier queue. A wrong automated answer
about money costs money, and this fleet handles real money.

Four things live here.

**1. The kill switch** (``settings_store.ai_replies_enabled``, re-exported
here). Three independent gates must all agree before automation may reply at
all:

    env(QCP_AI_REPLIES_ENABLED) AND env(WHATSAPP_ENABLED) AND db(whatsapp.ai_replies_enabled)

One implementation, in ``settings_store``, read by this module *and* by the
drafting engine — during the build it was spelled twice, composed differently,
which is how two guards for one rule drift until the looser one wins.
A missing ``OPENAI_API_KEY`` is handled separately in ``decide`` (it escalates,
because a customer with no model available needs a person, not silence).

Same shape as ``settings_store.delivery_enabled`` and for the same audited
reason — a database toggle must never be able to start something on its own.
The DB key is absent by default, so a database that has never been through
the QCP console has the AI **off**, which is how this ships. Turning it off
stops automation and *only* automation: assignment, ``return_to_ai``, close,
and every human verb keep working, and a switched-off AI escalates rather
than going quiet, so customers end up with people instead of with silence.

**2. The escalation triggers** (``decide``). Unsafe classification, low
confidence, "give me a human", the same question three times (a customer who
has asked three times has not been helped), an unrecognised language, a
message the engine could not parse, the provider erroring or timing out, the
AI being off — and, independently of anything the model said, a code-side
scan for money, KYC, fraud, complaints, legal threats and distress. The
classifier's own verdict is *one* input among these, never the last word:
``sensitive_topics()`` re-reads the customer's text here, so a model that has
been talked into calling "where is my refund?" safe and high-confidence still
does not get to answer it.

**3. The hard gates** (also ``decide``, checked first). The Verify number —
the AI may never send there, not one message, so an inbound on it escalates
instead. A message attributed to **nobody**: that is the ambiguous case the
ownership model in ``conversations.py`` deliberately refuses to guess, and
guessing it with a bot is worse than guessing it with a person. A thread a
human already holds, or one already queued for a human. And a closed service
window, where only an approved template may legally go out and choosing one
is not the AI's job.

**4. The handover mechanics.** ``escalate()`` marks the thread
``assigned_agent='pending_human'`` — the AI-routing seam
``conversations.py`` documented and left NULL in v1 — and reopens it, so an
escalation is visible in the queue rather than dependent on a human noticing
an unread badge. ``conversations.assign()`` clears that flag as it binds the
real human, and ``decide()`` sees ``assignee_id`` before anything else, so
the bot goes silent on the very next decision: a customer never receives a
bot message after a human has taken over. ``conversations.return_to_ai()``
clears both and hands the thread back. And because "escalated" is worthless
if nobody looks, ``unanswered_escalations()`` / ``flag_unanswered()`` turn a
thread nobody picked up into a reported problem — an unanswered WhatsApp
customer is the failure mode this whole feature exists to fix.

Finally ``guard_ai_send()`` is the last line of defence at the send itself:
engagement number only, free-form text only, never an authentication-shaped
intent, never anything OTP-shaped, and never a money figure that did not come
from a product API in this request. It raises rather than returning a flag,
because the only correct handling of "the AI tried to send an OTP" is that
nothing leaves the building.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional, Sequence

from sqlalchemy.orm import Session

from app.core.config import settings as env_settings
from app.models import WhatsAppConversation, WhatsAppMessage

from . import audit, conversations, settings_store
from .redaction import looks_like_authentication_intent


# ---------------------------------------------------------------------------
# Switch
# ---------------------------------------------------------------------------

# The switch has **one** implementation, in ``settings_store`` beside QCP's
# other runtime switches, and the drafting engine reads that same one. It is
# not re-derived here and it is not imported *from the engine*: this module is
# the brake, and a brake that imports the engine can be released by editing
# the engine. Both names are re-exported because callers and tests refer to
# them through this module.
ENV_AI_REPLIES = settings_store.ENV_AI_REPLIES
KEY_AI_REPLIES_ENABLED = settings_store.KEY_AI_REPLIES_ENABLED

_TRUE = {"1", "true", "yes", "on"}


def ai_replies_enabled() -> bool:
    """May automation reply at all? See ``settings_store.ai_replies_enabled``.

    Three gates that must all agree — the AI's own env floor, the fleet kill
    switch, and the admin toggle (absent → false, which is how this ships).

    A missing ``OPENAI_API_KEY`` is deliberately *not* one of them; it is
    handled a line lower, in ``decide``, because "no key" and "switched off"
    deserve different outcomes. Switched off means the operator has said the
    AI answers nobody. No key means it cannot — and the customer should get a
    human, not silence.

    Nothing this reads is consulted by ``assign``, ``return_to_ai``, ``close``
    or the agent console, so switching the AI off leaves the human queue
    working.
    """
    return settings_store.ai_replies_enabled()


def ai_can_draft() -> bool:
    """Is there a model to call at all? Same key as ``ai_cv``."""
    return bool(env_settings.ai_enabled)


# ---------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------

# The value written to ``whatsapp_conversations.assigned_agent`` while a
# thread is queued for a human. The column is the AI-routing seam
# ``conversations.py`` reserved; this is the only writer of a non-NULL value,
# and ``assign`` / ``return_to_ai`` / ``close_conversation`` are the only
# clearers.
PENDING_HUMAN = "pending_human"

ACT_ANSWER = "answer"
ACT_ESCALATE = "escalate"
ACT_HOLD = "hold"

# Reasons. Stable strings: they are written to the audit log and read by the
# admin console, so they are API.
R_NO_TRIGGER = "no_escalation_trigger"
R_HUMAN_ASSIGNED = "human_assigned"
R_AWAITING_HUMAN = "awaiting_human"
R_NOT_ENGAGEMENT = "not_engagement_number"
R_UNATTRIBUTED = "unattributed"
R_AI_DISABLED = "ai_disabled"
R_OUTSIDE_WINDOW = "outside_service_window"
R_PROVIDER_ERROR = "provider_error"
R_UNPARSEABLE = "unparseable"
R_UNSAFE = "classifier_unsafe"
R_SENSITIVE = "sensitive_topic"
R_HUMAN_REQUESTED = "human_requested"
R_LANGUAGE = "unsupported_language"
R_UNGROUNDED = "ungrounded_fact"
R_LOW_CONFIDENCE = "low_confidence"
R_REPEATED = "repeated_question"

# Highest-priority trigger first. ``Decision.reason`` is the first of these
# that fired; ``Decision.triggers`` carries all of them, because an operator
# reading the audit row wants the whole picture and not just the winner.
_PRIORITY = (
    R_NOT_ENGAGEMENT,
    R_UNATTRIBUTED,
    R_AI_DISABLED,
    R_OUTSIDE_WINDOW,
    R_PROVIDER_ERROR,
    R_UNPARSEABLE,
    R_UNSAFE,
    R_SENSITIVE,
    R_HUMAN_REQUESTED,
    R_LANGUAGE,
    R_UNGROUNDED,
    R_LOW_CONFIDENCE,
    R_REPEATED,
)

# Below this, the model does not get to guess in front of a customer.
MIN_CONFIDENCE = 0.75

# A customer who has asked the same thing this many times has not been
# helped, whatever the model's confidence says.
REPEAT_LIMIT = 3
REPEAT_WINDOW = timedelta(hours=24)
# Bounds the history scan; far more than any real repeat run.
_REPEAT_SCAN = 20

# What the support layer is allowed to answer in. Cameroon is bilingual and
# QCP's own locales are ``en``/``fr``; anything else — including a message
# the engine could not identify — is a human's job, because an answer in the
# wrong language is indistinguishable from no answer.
SUPPORTED_LANGUAGES = frozenset({"en", "fr"})

# How long a customer may wait on an unclaimed escalation before it is a
# reported problem rather than a queue entry.
UNANSWERED_AFTER = timedelta(minutes=15)
# Bounds one sweep. Open, unclaimed escalations are meant to be a short list;
# if this ever truncates, the queue itself is the incident.
_SCAN_CAP = 1000

TOPIC_MONEY = "money"
TOPIC_KYC = "kyc"
TOPIC_FRAUD = "fraud"
TOPIC_COMPLAINT = "complaint"
TOPIC_LEGAL = "legal"
TOPIC_DISTRESS = "distress"
TOPIC_ACCOUNT = "account_status"

# Stems, matched at a word boundary with any suffix, against accent-stripped
# lowercase text — so ``rembours`` catches "remboursement" and ``bloqu``
# catches "bloquée". English and French, because that is what arrives.
#
# This list is intentionally broad. Every entry costs at most one needless
# escalation; every omission risks an invented fact about somebody's money.
_TOPIC_STEMS: dict[str, tuple[str, ...]] = {
    TOPIC_MONEY: (
        "money", "argent", "balance", "solde", "refund", "rembours", "payment",
        "paiement", "transfer", "transfert", "withdraw", "retrait", "deposit",
        "depot", "momo", "mobile money", "orange money", "mtn money", "xaf",
        "fcfa", "invoice", "facture", "wallet", "portefeuille", "charged",
        "debit", "credit", "how much", "combien", "overcharg", "double charg",
        "total",
    ),
    TOPIC_KYC: (
        "kyc", "identit", "cni", "passport", "passeport", "verificat",
        "selfie", "justificatif", "proof of address", "id document",
    ),
    TOPIC_FRAUD: (
        "fraud", "fraude", "scam", "arnaque", "stolen", "vole par", "hack",
        "pirat", "unauthoris", "unauthoriz", "non autorise", "chargeback",
        "dispute", "litige", "phishing", "voleur",
    ),
    TOPIC_COMPLAINT: (
        "complain", "reclamation", "scandal", "unacceptable", "inacceptable",
        "worst", "terrible", "furieux", "en colere",
    ),
    TOPIC_LEGAL: (
        "lawyer", "avocat", "sue you", "court", "tribunal", "police",
        "gendarmerie", "plaint", "poursuite", "legal action", "justice",
        "regulator", "consumer protection",
    ),
    TOPIC_DISTRESS: (
        "suicide", "kill myself", "end my life", "me suicider", "veux mourir",
        "want to die", "self harm",
    ),
    TOPIC_ACCOUNT: (
        "suspend", "blocked", "bloqu", "banned", "banni", "locked out",
        "verrouill", "desactiv", "deactivat", "disabled my", "closed my account",
        "compte ferme",
    ),
}


def _fold(text: object) -> str:
    """Lowercase, accent-stripped, whitespace-collapsed.

    Accents are stripped so one unaccented stem covers both how a Cameroonian
    customer types French on a phone keyboard and how it is spelled.
    """
    raw = unicodedata.normalize("NFKD", str(text or ""))
    raw = "".join(ch for ch in raw if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", raw.lower()).strip()


_TOPIC_PATTERNS: dict[str, tuple[re.Pattern, ...]] = {
    topic: tuple(re.compile(rf"\b{re.escape(stem)}\w*") for stem in stems)
    for topic, stems in _TOPIC_STEMS.items()
}


# "Get me a person." Read from code for the same reason the topics above are:
# a customer who has asked for a human has asked, and whether a model agrees
# is not a relevant opinion. English and French, accent-folded, and phrased
# as fragments because this is matched with ``in`` against folded text rather
# than at a word boundary — "parler à un agent" and "parler a un conseiller"
# must both hit.
_HUMAN_REQUESTS = (
    "real person", "a human", "human being", "human agent", "speak to someone",
    "speak to a person", "talk to someone", "talk to a person", "talk to a human",
    "speak to an agent", "talk to an agent", "customer service", "customer support",
    "not a bot", "stop the bot", "are you a bot", "is this a bot", "your manager",
    "supervisor",
    "un humain", "une personne", "un vrai agent", "un agent", "un conseiller",
    "parler a quelqu un", "parler a une personne", "parler a un", "service client",
    "pas un robot", "un robot", "votre superieur", "responsable",
)


def asks_for_human(text: object) -> bool:
    """Has this customer asked for a person?

    Independent of the classifier and of the model, exactly like
    ``sensitive_topics``. A customer who types "stop, I want to talk to a real
    person" has made a decision; a bot that keeps replying because its own
    intent model scored the sentence as ``greeting`` has overruled them.
    """
    folded = _fold(text)
    if not folded:
        return False
    stripped = re.sub(r"[^a-z0-9 ]+", " ", folded)
    stripped = re.sub(r"\s+", " ", stripped)
    return any(needle in stripped for needle in _HUMAN_REQUESTS)


def sensitive_topics(text: object) -> tuple[str, ...]:
    """Which "fetch a human" subjects this message touches, read from code.

    Independent of the model on purpose. The classifier is one opinion about
    the message; this is another, and it cannot be argued with by the message
    itself. Anything it returns escalates.
    """
    folded = _fold(text)
    if not folded:
        return ()
    return tuple(
        topic
        for topic in _TOPIC_STEMS
        if any(pattern.search(folded) for pattern in _TOPIC_PATTERNS[topic])
    )


# ---------------------------------------------------------------------------
# Inputs and outputs
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Signals:
    """What the AI engine observed about one inbound message.

    Every default is the *safe* value, so ``Signals()`` — an engine that
    crashed, returned nothing, or has not been wired up yet — escalates
    rather than answers. ``understood=False`` and ``confidence=0.0`` are what
    make that true.
    """

    #: The engine parsed the message into something it can act on.
    understood: bool = False
    #: The safety classifier flagged it (abuse, injection, self-harm, …).
    unsafe: bool = False
    #: 0..1. Below ``MIN_CONFIDENCE`` a human answers.
    confidence: float = 0.0
    #: ISO-639-1, e.g. "en"/"fr". None means "could not tell".
    language: Optional[str] = None
    #: The customer asked for a person.
    wants_human: bool = False
    #: The model provider errored, timed out, or rate-limited.
    provider_error: bool = False
    #: Subjects the classifier itself identified; merged with the code scan.
    topics: tuple[str, ...] = ()
    #: The draft reply states a fact (a balance, a total, a status, …).
    asserts_facts: bool = False
    #: …and every such value came from a product API call in this request.
    facts_from_product_api: bool = False


@dataclass(frozen=True)
class Decision:
    """May the AI speak, and if not, whose problem is it now?"""

    action: str
    reason: str
    triggers: tuple[str, ...] = ()
    detail: dict = field(default_factory=dict)

    @property
    def may_reply(self) -> bool:
        return self.action == ACT_ANSWER

    @property
    def needs_human(self) -> bool:
        return self.action == ACT_ESCALATE


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _decision(triggers: Sequence[str], detail: dict) -> Decision:
    ordered = tuple(t for t in _PRIORITY if t in set(triggers))
    if not ordered:
        return Decision(action=ACT_ANSWER, reason=R_NO_TRIGGER, triggers=(), detail=detail)
    return Decision(action=ACT_ESCALATE, reason=ordered[0], triggers=ordered, detail=detail)


# ---------------------------------------------------------------------------
# The decision
# ---------------------------------------------------------------------------

def _normalise_question(text: object) -> str:
    """Fold a message to its bare words so "…???" is the same question."""
    return re.sub(r"[^a-z0-9 ]+", " ", _fold(text)).strip()


def repeat_count(
    db: Session,
    conversation: WhatsAppConversation,
    *,
    text: object,
    within: timedelta = REPEAT_WINDOW,
    now: Optional[datetime] = None,
) -> int:
    """How many times this contact has asked *this* recently.

    Counts persisted inbound rows only, so the caller gets the current
    message included once ingest has stored it (which is the order the
    webhook path runs in). A row whose timestamp cannot be read is counted:
    over-counting escalates, under-counting answers, and only one of those
    two mistakes is safe.
    """
    target = _normalise_question(text)
    if not target:
        return 0
    reference = conversations._as_aware(now) or _now()
    floor = reference - within

    rows = (
        db.query(WhatsAppMessage.body, WhatsAppMessage.created_at)
        .filter(
            WhatsAppMessage.conversation_id == conversation.id,
            WhatsAppMessage.direction == "inbound",
        )
        .order_by(WhatsAppMessage.id.desc())
        .limit(_REPEAT_SCAN)
        .all()
    )
    count = 0
    for body, created_at in rows:
        when = conversations._as_aware(created_at)
        if when is not None and when < floor:
            continue
        if _normalise_question(body) == target:
            count += 1
    return count


def decide(
    db: Session,
    conversation: WhatsAppConversation,
    *,
    signals: Signals = Signals(),
    account_purpose: Optional[str] = None,
    product_id: Optional[int] = None,
    text: object = "",
    now: Optional[datetime] = None,
) -> Decision:
    """May the AI answer this inbound message?

    ``account_purpose`` is the *account's* purpose, read from the row the
    message arrived on — not from anything the caller composed. ``product_id``
    is the attribution ``conversations.attribute_inbound`` returned for this
    message, and ``None`` is one of its supported answers.

    Three outcomes:

    * ``ACT_HOLD`` — say nothing, and do not queue anybody. A human already
      holds the thread, or one has already been asked for.
    * ``ACT_ESCALATE`` — say nothing, and a human is needed.
    * ``ACT_ANSWER`` — nothing fired. The engine may compose a reply, which
      still has to survive ``guard_ai_send``.
    """
    reference = conversations._as_aware(now) or _now()

    # --- hold gates: somebody is already on it -----------------------------
    # First, and before every other consideration. This is what makes "a
    # human took over" mean *immediately* rather than *eventually*.
    if conversation.assignee_id is not None:
        return Decision(action=ACT_HOLD, reason=R_HUMAN_ASSIGNED, detail={})
    if (conversation.assigned_agent or None) == PENDING_HUMAN:
        return Decision(action=ACT_HOLD, reason=R_AWAITING_HUMAN, detail={})

    triggers: list[str] = []

    # --- hard gates --------------------------------------------------------
    # The Verify number carries security codes and nothing else. An inbound
    # on it is often "I did not request this code", which is a fraud report,
    # so it goes to a person rather than being dropped.
    if str(account_purpose or "").strip().lower() != "engagement":
        triggers.append(R_NOT_ENGAGEMENT)
    # Attributed to nobody: two products are in play and the ownership model
    # refuses to guess. A bot guessing is strictly worse than a human
    # resolving it.
    if product_id is None:
        triggers.append(R_UNATTRIBUTED)
    # Switched off, or no model to call. Both mean automation is not going to
    # answer this person, and both must therefore reach a human rather than
    # ending in silence.
    if not (ai_replies_enabled() and ai_can_draft()):
        triggers.append(R_AI_DISABLED)
    # Outside Meta's 24h window only an approved template may go out, and
    # picking one is a product decision, not a support-bot decision. The
    # gateway refuses free-form here too; this is not a route around it.
    if not conversations.service_window_open(conversation, now=reference):
        triggers.append(R_OUTSIDE_WINDOW)

    # --- engine health -----------------------------------------------------
    if signals.provider_error:
        triggers.append(R_PROVIDER_ERROR)
    if not signals.understood:
        triggers.append(R_UNPARSEABLE)

    # --- classification ----------------------------------------------------
    if signals.unsafe:
        triggers.append(R_UNSAFE)
    # Either the engine spotted it or the text says so. The second half is
    # what makes "I want a human" a control rather than a suggestion: it is
    # read from the customer's own words by code, so an engine that has been
    # talked into scoring the sentence as a cheerful greeting cannot bury it.
    if signals.wants_human or asks_for_human(text):
        triggers.append(R_HUMAN_REQUESTED)
    language = str(signals.language or "").strip().lower().split("-")[0]
    if language not in SUPPORTED_LANGUAGES:
        triggers.append(R_LANGUAGE)
    try:
        confidence = float(signals.confidence)
    except (TypeError, ValueError):
        confidence = 0.0
    if confidence < MIN_CONFIDENCE:
        triggers.append(R_LOW_CONFIDENCE)

    # --- subject matter, read from the text and not from the model ---------
    topics = tuple(sorted(set(signals.topics or ()) | set(sensitive_topics(text))))
    if topics:
        triggers.append(R_SENSITIVE)

    # A stated fact that did not come from a product API in this request is
    # an invented one. About a balance or a refund that is worse than silence.
    if signals.asserts_facts and not signals.facts_from_product_api:
        triggers.append(R_UNGROUNDED)

    # --- has this already failed? ------------------------------------------
    repeats = repeat_count(db, conversation, text=text, now=reference)
    if repeats >= REPEAT_LIMIT:
        triggers.append(R_REPEATED)

    detail: dict = {"confidence": round(confidence, 3)}
    if topics:
        detail["topics"] = list(topics)
    if repeats:
        detail["repeats"] = repeats
    return _decision(triggers, detail)


# ---------------------------------------------------------------------------
# Handover state
# ---------------------------------------------------------------------------

_META_KEY = "ai"


def _ai_meta(conversation: WhatsAppConversation) -> dict:
    blob = conversation.meta if isinstance(conversation.meta, dict) else {}
    inner = blob.get(_META_KEY)
    return dict(inner) if isinstance(inner, dict) else {}


def _write_ai_meta(conversation: WhatsAppConversation, values: Optional[dict]) -> None:
    """Replace the ``meta['ai']`` block.

    Reassigned rather than mutated in place: ``whatsapp_conversations.meta``
    is a plain JSON column with no mutation tracking, so an in-place edit is
    a change SQLAlchemy never flushes.
    """
    blob = dict(conversation.meta) if isinstance(conversation.meta, dict) else {}
    if values:
        blob[_META_KEY] = values
    else:
        blob.pop(_META_KEY, None)
    conversation.meta = blob


def waiting_since(conversation: WhatsAppConversation) -> Optional[datetime]:
    """When the customer started waiting on a human, or None if they are not.

    The clock starts at the *first* escalation and is not restarted by later
    ones — a customer who has been ignored for two hours and asked again is
    not a fresh case.
    """
    if (conversation.assigned_agent or None) != PENDING_HUMAN:
        return None
    raw = _ai_meta(conversation).get("escalated_at")
    if raw:
        try:
            return conversations._as_aware(datetime.fromisoformat(str(raw)))
        except ValueError:
            pass
    # Flagged with no readable clock: fall back to the customer's last
    # message, and if there is none, treat it as maximally overdue rather
    # than invisible.
    return conversations._as_aware(conversation.last_inbound_at) or datetime.min.replace(
        tzinfo=timezone.utc
    )


def escalate(
    db: Session,
    conversation: WhatsAppConversation,
    *,
    reason: str,
    detail: Optional[dict] = None,
    now: Optional[datetime] = None,
) -> WhatsAppConversation:
    """Queue this thread for a human. Idempotent.

    Writes the AI seam (``assigned_agent``) and **not** ``assignee_id``: an
    escalation is a request for a person, not an assignment to one. Nothing
    here picks a human — ``conversations.assign`` is the only thing that
    binds a real, entitled user.

    A closed thread reopens, for the same reason ``assign`` reopens one: a
    customer waiting on a human must not sit in a closed queue where no
    agent will look.
    """
    stamp = conversations._as_aware(now) or _now()
    existing = _ai_meta(conversation)
    already = (conversation.assigned_agent or None) == PENDING_HUMAN

    values = {
        "escalated_at": (existing.get("escalated_at") if already else None)
        or stamp.isoformat(),
        "reason": str(reason)[:60],
        "detail": detail or {},
    }
    if already and existing.get("reported_at"):
        # Keep the "already reported" mark so a re-escalation of a thread
        # that is *still* unanswered does not re-alert.
        values["reported_at"] = existing["reported_at"]

    conversation.assigned_agent = PENDING_HUMAN
    _write_ai_meta(conversation, values)
    if conversation.state != conversations.STATE_OPEN:
        conversation.state = conversations.STATE_OPEN
    db.flush()
    return conversation


def clear_handover(conversation: WhatsAppConversation) -> None:
    """Drop the pending-human flag and its bookkeeping.

    Called from ``conversations.assign`` (a human took it), ``return_to_ai``
    (handed back) and ``close_conversation`` (done) — the three events that
    end a wait. It takes no session: those three flush for themselves, and
    this must never be able to commit half a handover.
    """
    conversation.assigned_agent = None
    _write_ai_meta(conversation, None)


def unanswered_escalations(
    db: Session,
    *,
    older_than: timedelta = UNANSWERED_AFTER,
    now: Optional[datetime] = None,
    account_id: Optional[int] = None,
    limit: int = 100,
) -> list[WhatsAppConversation]:
    """Threads queued for a human that nobody has picked up. Longest wait first.

    An escalation that sits in a queue nobody watches is the same outcome as
    no escalation at all, which is the failure this feature exists to fix. A
    closed thread is excluded (somebody dealt with it) and so is an assigned
    one (somebody has it).

    The age filter runs in Python, not SQL: the clock lives in a JSON blob,
    and SQLite and Postgres do not agree on how to compare a timestamp inside
    one. The rows it filters are only the open unclaimed escalations, so the
    scan is small by construction.
    """
    reference = conversations._as_aware(now) or _now()
    cutoff = reference - older_than

    q = db.query(WhatsAppConversation).filter(
        WhatsAppConversation.assigned_agent == PENDING_HUMAN,
        WhatsAppConversation.assignee_id.is_(None),
        WhatsAppConversation.state != conversations.STATE_CLOSED,
    )
    if account_id is not None:
        q = q.filter(WhatsAppConversation.account_id == account_id)

    # Oldest inbound first, so if the cap ever truncates it truncates the
    # *newest* rows — the ones least likely to be overdue.
    q = q.order_by(
        WhatsAppConversation.last_inbound_at.asc(), WhatsAppConversation.id.asc()
    ).limit(_SCAN_CAP)

    overdue = []
    for row in q.all():
        since = waiting_since(row)
        if since is not None and since <= cutoff:
            overdue.append((since, row))
    overdue.sort(key=lambda pair: pair[0])
    return [row for _, row in overdue[: max(min(limit, 500), 1)]]


def flag_unanswered(
    db: Session,
    *,
    older_than: timedelta = UNANSWERED_AFTER,
    now: Optional[datetime] = None,
    account_id: Optional[int] = None,
    limit: int = 100,
) -> list[WhatsAppConversation]:
    """Report every overdue escalation **once**, and return what was reported.

    One audit denial row per escalation, not per sweep: a caller that polls
    every minute must not turn one ignored customer into a thousand rows
    nobody reads. The mark is cleared with the rest of the handover state,
    so a second escalation of the same thread reports again.
    """
    reported: list[WhatsAppConversation] = []
    stamp = conversations._as_aware(now) or _now()
    for row in unanswered_escalations(
        db, older_than=older_than, now=stamp, account_id=account_id, limit=limit
    ):
        values = _ai_meta(row)
        if values.get("reported_at"):
            continue
        since = waiting_since(row)
        audit.record(
            db,
            action="ai.unanswered",
            resource_type="whatsapp_conversation",
            resource_id=str(row.id),
            outcome=audit.OUTCOME_DENIED,
            reason="escalation_unclaimed",
            account_id=row.account_id,
            product_id=row.product_id,
            details={
                "escalated_for": values.get("reason"),
                "waiting_minutes": int((stamp - since).total_seconds() // 60) if since else None,
            },
        )
        values["reported_at"] = stamp.isoformat()
        _write_ai_meta(row, values)
        reported.append(row)
    db.flush()
    return reported


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------

_ACTION_BY_OUTCOME = {
    ACT_ANSWER: "ai.answered",
    ACT_ESCALATE: "ai.escalated",
    ACT_HOLD: "ai.held",
}


def apply(
    db: Session,
    conversation: WhatsAppConversation,
    decision: Decision,
    *,
    product_id: Optional[int] = None,
    model: Optional[str] = None,
    prompt_version: Optional[str] = None,
    now: Optional[datetime] = None,
) -> Decision:
    """Carry out a decision: escalate if it says so, and audit it either way.

    Every AI turn writes a row — including the ones where it answered — with
    the model, the prompt version and *why it answered rather than
    escalated*. "The bot replied and we do not know on what basis" is not an
    acceptable state for a number that also carries money traffic.

    The customer's own words are never in the row. The reason, the trigger
    list and the topic *names* are enough to reconstruct the decision, and
    the message itself is already stored (redacted) on its own row.
    """
    if decision.needs_human:
        escalate(db, conversation, reason=decision.reason, detail=decision.detail, now=now)

    audit.record(
        db,
        action=_ACTION_BY_OUTCOME.get(decision.action, "ai.held"),
        resource_type="whatsapp_conversation",
        resource_id=str(conversation.id),
        outcome=audit.OUTCOME_DENIED if decision.needs_human else audit.OUTCOME_OK,
        reason=decision.reason,
        product_id=product_id,
        account_id=conversation.account_id,
        details={
            "action": decision.action,
            "triggers": list(decision.triggers),
            "model": model,
            "prompt_version": prompt_version,
            **decision.detail,
        },
    )
    return decision


# ---------------------------------------------------------------------------
# The send guard
# ---------------------------------------------------------------------------

class AiSendRefused(RuntimeError):
    """The AI tried to send something it may never send."""


# A bare 4–8 digit run, or a code word anywhere. Either shape is an
# authentication code as far as this guard is concerned.
_OTP_SHAPED = re.compile(r"\b\d[\d \-]{2,10}\d\b")
_CODE_WORD = re.compile(r"\b(code|otp|pin|passcode|password|mot de passe)\b")
# A figure with a currency next to it, in either order. Also used to *remove*
# amounts before the OTP scan: "2000 FCFA" is a price, not a login code, and
# without this every grounded amount would trip the code rule instead.
_MONEY_SHAPED = re.compile(
    r"(\b\d[\d.,\s]*\s*(xaf|fcfa|cfa|usd|eur)\b)"
    r"|(\b(xaf|fcfa|cfa|usd|eur)\s*[\d.,]+)"
    r"|([€$£]\s*[\d.,]+)"
)


def guard_ai_send(
    *,
    account_purpose: Optional[str],
    kind: str,
    intent: Optional[str] = None,
    body: Optional[str] = None,
    grounded: bool = False,
) -> None:
    """Last check before an AI-composed message reaches the send path.

    Raises ``AiSendRefused``. It raises rather than returning a flag because
    every condition below is a bug or an attack, and the only correct
    handling of "the AI tried to send an OTP" is that nothing leaves the
    building and somebody is told.

    Four refusals:

    * **Not the engagement number.** The AI may never send on Quata Verify.
      Not one message, and not because a prompt said so — because this
      function does, and it reads the *account's* purpose rather than
      anything the caller composed.
    * **Not free-form text.** Templates are pre-approved messages a product
      owns; picking one is not the support bot's decision, and an
      authentication template is exactly the thing it must never pick.
    * **Nothing OTP-shaped**, by intent (reusing the same vocabulary
      ``redaction`` uses to spot a security code) or by body. A support reply
      containing a bare 4–8 digit run is refused: the cost is one escalated
      conversation, and the alternative is a bot that can be talked into
      reciting a login code.
    * **No money figure that is not grounded.** ``grounded=True`` is the
      caller asserting that every figure in this body came from a product API
      response in *this* request. It is not a default and it is not
      something the model can set.
    """
    if str(account_purpose or "").strip().lower() != "engagement":
        raise AiSendRefused(
            "ai_send_not_engagement: the AI may only send on the engagement number"
        )
    if str(kind or "").strip().lower() != "text":
        raise AiSendRefused(f"ai_send_not_freeform: the AI may not send kind={kind!r}")
    if looks_like_authentication_intent(intent):
        raise AiSendRefused(f"ai_send_authentication_intent: {intent!r}")

    folded = _fold(body)
    if not folded:
        return
    if not grounded and _MONEY_SHAPED.search(folded):
        raise AiSendRefused(
            "ai_send_ungrounded_amount: a figure that did not come from a product API"
        )
    # Amounts are taken out before the code scan so a legitimate, grounded
    # "2,000 XAF" is not read as a six-digit login code. A code *word* still
    # counts wherever it appears, so this cannot be used to smuggle one.
    residual = _MONEY_SHAPED.sub(" ", folded)
    if _CODE_WORD.search(folded) or _OTP_SHAPED.search(residual):
        raise AiSendRefused("ai_send_otp_shaped: the reply looks like a security code")
