"""Pydantic IO for the QCP **agent console** — the human side of handover.

``schemas/whatsapp.py`` holds the product-facing contract and
``schemas/whatsapp_admin.py`` the operator-facing one. This file holds the
shapes a support agent's screen is built from: their queue, the queue nobody
is on yet, one thread with its authorship, the reply they send and the draft
the AI offers them.

Three rules shape everything here, and each is structural rather than
advisory.

**No shape below carries a staff id.** ``users.id`` leaking through
``assignee_id`` was found and closed in an earlier round — the product API
now blanks it for a non-owner — and this surface does not reopen the class
of bug by carrying one at all. A queue row says ``mine`` and, when somebody
else holds it, their display name. That is what a console needs to render;
an integer primary key is not, and one that is never serialised cannot be
handed to a product later by accident.

**A draft is described, never assumed.** ``SuggestedReplyOut`` carries
``auto_sent: False`` in the contract, the model and prompt version that
produced the text, and ``reason`` — why the AI answered rather than
escalating. ``draft`` is ``None`` whenever the answer is "a human should
take this", and the *withheld text does not travel*: an escalation carries
no body for a console to render "just this once".

**A reply states its own kind.** Free-form is legal only inside Meta's 24h
service window; outside it, only an approved template may go out. The two
are different bodies here (``kind="text"`` with prose, ``kind="template"``
with an intent and variables) rather than one body with optional fields, so
"which of the two is this" is answered by validation rather than by the
route guessing from what happens to be filled in.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# Same shape as the routing intents products use — a lowercase slug. An agent
# never types one (the console offers the intents its templates declare), but
# the pattern is what stops a free-text field reaching ``resolve_route``.
_INTENT = r"^[a-z][a-z0-9_]{2,79}$"

# The conventional intent for a support agent's free-form reply. Named here
# rather than defaulted inside the route so the console and the routing rule
# an operator has to create are described in one place.
DEFAULT_AGENT_INTENT = "support_reply"


# ---------------------------------------------------------------------------
# Queues
# ---------------------------------------------------------------------------

class AgentQueueItemOut(BaseModel):
    """One waiting conversation.

    ``waiting_seconds`` is computed from ``last_inbound_at``, not from the
    row's creation: what matters is how long *this customer* has been
    waiting for an answer, which is what makes an oldest-first queue mean
    anything.

    ``answerable`` folds the two refusals an agent would otherwise discover
    by having a reply rejected — the Verify number is never agent-answerable,
    and a thread no product owns has nobody to send as — so the console can
    show why a row cannot be worked instead of offering a reply box that
    409s.
    """

    conversation_id: int
    phone_e164: str
    display_name: Optional[str] = None
    state: str
    product: Optional[str] = None
    account: Optional[str] = None
    account_purpose: Optional[str] = None
    unread_count: int = 0
    locale: Optional[str] = None
    last_inbound_at: Optional[datetime] = None
    waiting_seconds: int = 0
    service_window_open: bool = False
    service_window_expires_at: Optional[datetime] = None
    # Whose thread is it? A name, never an id — see the module docstring.
    mine: bool = False
    held_by: Optional[str] = None
    answerable: bool = True
    answerable_reason: Optional[str] = None

    # ---- handover state -------------------------------------------------
    # Automation stopped and asked for a person. ``waiting_since`` is when it
    # first did so, which is *not* ``last_inbound_at``: a thread escalated at
    # 09:00 has been waiting since 09:00 even if the customer has said nothing
    # more, and sorting a queue by the customer's last word hides exactly the
    # people who gave up talking.
    escalated: bool = False
    handover_reason: Optional[str] = None
    waiting_since: Optional[datetime] = None
    # Nobody has picked this up inside ``handover.UNANSWERED_AFTER``. The
    # whole point of the flag: an escalation nobody looks at is the same
    # outcome as no escalation, which is the failure this feature exists for.
    overdue: bool = False


class AiStateOut(BaseModel):
    """What the AI is doing, reported next to the work it did or did not do.

    ``enabled`` and ``kill_switch`` are two readings of one switch and both
    are carried, because a console that shows neither leaves an agent to
    conclude the screen is broken when drafts stop appearing.
    """

    enabled: bool = False
    kill_switch: bool = True
    # Can it draft at all — i.e. is there a key? Distinct from the switch: no
    # key with the switch on means customers reach a human, not silence.
    configured: bool = False
    suggestions_enabled: bool = False
    model: Optional[str] = None
    prompt_version: Optional[str] = None
    # A **third** state, and not a rename of either of the two above: the
    # switch is on, the key is there, and no reply can route anywhere — so the
    # AI answers nobody and every screen said it was healthy. An AI reply is a
    # send, a send needs an ``ai_support_reply`` engagement rule, and a
    # missing rule is refused deep inside ``dispatch`` where the operator who
    # just flipped the switch will never look. ``blocker`` is one of
    # ``settings_store.AI_BLOCKED_*``; ``gaps`` names the exact product and
    # the exact languages, because a rule created for ``en`` alone strands
    # every francophone customer and that is the failure mode that hides.
    misconfigured: bool = False
    blocker: Optional[str] = None
    gaps: list[dict] = Field(default_factory=list)


class AgentQueueOut(BaseModel):
    items: list[AgentQueueItemOut]
    total: int
    # Oldest first, always. Stated in the contract because a console that
    # re-sorted newest-first would bury the customer who has waited longest,
    # which is the one person a support queue exists for.
    ordering: Literal["oldest_first"] = "oldest_first"
    ai: AiStateOut = Field(default_factory=AiStateOut)


# ---------------------------------------------------------------------------
# Ownership
# ---------------------------------------------------------------------------

class AgentOwnershipOut(BaseModel):
    """The result of claiming, releasing or handing a thread back.

    ``mine`` is the honest answer to "do I own this now?", which is the
    question a claim actually asks: two agents clicking at once must not both
    be told yes. The loser of that race gets a 409 naming ``held_by``, not a
    quiet success.
    """

    conversation_id: int
    state: str
    mine: bool
    held_by: Optional[str] = None
    already_mine: bool = False


class ReturnToAiOut(AgentOwnershipOut):
    """Handing a thread back to automation.

    ``ai_replies_enabled`` is reported rather than assumed: QCP ships with
    the AI answering nothing, so returning a thread to it while that switch
    is off leaves the customer with nobody on the thread. An agent should be
    told that at the moment they do it.
    """

    ai_replies_enabled: bool = False


# ---------------------------------------------------------------------------
# Replying
# ---------------------------------------------------------------------------

class AgentReplyIn(BaseModel):
    """One reply, sent as the product that owns the thread.

    ``kind`` decides which half of the model is legal, and the validator
    below enforces it rather than letting the route infer intent from which
    fields happen to be populated:

    * ``text`` — prose, legal only inside Meta's 24h service window. Carries
      no template variables, because there is no template.
    * ``template`` — an approved template addressed by ``intent``. The only
      thing that may go out once the window has closed.

    ``client_token`` is the console's idempotency handle. Without one the
    gateway derives a key that buckets by five minutes, and a free-form send
    carries no template name or variables to tell two of them apart — so an
    agent's second sentence inside five minutes would come back
    ``duplicate: true`` and never reach the customer. A fresh token per
    composed message is the correct behaviour; re-sending the *same* token is
    what makes a double-clicked button harmless.
    """

    model_config = ConfigDict(extra="forbid")

    kind: Literal["text", "template"] = "text"
    body: Optional[str] = Field(default=None, min_length=1, max_length=4096)
    intent: str = Field(default=DEFAULT_AGENT_INTENT, pattern=_INTENT)
    variables: list[str] = Field(default_factory=list, max_length=20)
    client_token: Optional[str] = Field(default=None, min_length=8, max_length=80)

    # Did a human send the AI's words, or their own? Audited, never trusted:
    # nothing about the send changes on these, they only make the log able to
    # answer "the bot told me…" honestly. A console that lied about them would
    # only be lying to its own audit trail.
    from_suggestion: bool = False
    suggestion_edited: bool = False

    @field_validator("variables")
    @classmethod
    def _bounded_variables(cls, value: list[str]) -> list[str]:
        for item in value:
            if len(item) > 500:
                raise ValueError("A template variable may not exceed 500 characters.")
        return value

    @model_validator(mode="after")
    def _coherent(self) -> "AgentReplyIn":
        if self.kind == "text":
            if not (self.body or "").strip():
                raise ValueError("A text reply needs a body.")
            if self.variables:
                raise ValueError("A text reply carries no template variables.")
        else:
            if self.body is not None:
                raise ValueError("A template reply carries no free-form body.")
        return self


class AgentReplyOut(BaseModel):
    """What the gateway did with the reply.

    Deliberately reports the gateway's own answer rather than a cheerful
    one. QCP ships dormant, so the honest ``status`` for a reply today is
    ``suppressed`` with ``reason="delivery_disabled"`` — and an agent seeing
    that is the difference between "the customer did not get this" and a
    console that says "sent" to a message nobody received.
    """

    conversation_id: int
    message_uid: Optional[str] = None
    status: str
    duplicate: bool = False
    reason: Optional[str] = None
    kind: str
    intent: str
    service_window_open: bool
    # The agent's display name, never their id.
    sent_by: str


# ---------------------------------------------------------------------------
# The thread
# ---------------------------------------------------------------------------

class ThreadMessageOut(BaseModel):
    """One message, with who said it.

    ``author`` is the field this shape exists for. An agent picking up a
    thread mid-conversation has to see what the bot already told this
    person, or they will contradict it — and "outbound" alone does not say
    whether a message came from the AI, from a colleague, or from the
    product's own automation.

    Authorship is *derived from the audit log*, not from a column: the
    message table has no author, and the audit row that recorded the send
    already carries the actor. ``ai.*`` actions mark an AI reply, an
    ``agent.*`` action with an actor marks a human, and an outbound row with
    neither is the product's own automation.
    """

    id: int
    message_uid: str
    direction: str
    kind: str
    status: str
    intent: Optional[str] = None
    product: Optional[str] = None
    account_purpose: Optional[str] = None
    # Already redacted at write time — an OTP is stored as a digest.
    body: Optional[str] = None
    variables: dict = Field(default_factory=dict)
    author: Literal["customer", "ai", "agent", "automation"]
    # A display name for a human, the model for the AI, the product slug for
    # automation. Never an id.
    author_label: Optional[str] = None
    suppressed_reason: Optional[str] = None
    error_code: Optional[str] = None
    created_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    read_at: Optional[datetime] = None


class ThreadOut(BaseModel):
    conversation: AgentQueueItemOut
    # Oldest first: an agent reads a conversation forwards.
    messages: list[ThreadMessageOut]
    next_before_id: Optional[int] = None
    ai: AiStateOut = Field(default_factory=AiStateOut)
    # Approved templates that may go out on this thread once the 24h window
    # has closed. Empty is a real answer and the console says so — it means
    # this customer cannot be reached until they write again.
    templates: list["AgentTemplateOut"] = Field(default_factory=list)


class AgentTemplateOut(BaseModel):
    """One approved template, addressed by the intent that routes to it.

    ``intent`` is what the reply endpoint takes, not ``name``: a template is
    reached through a routing rule, and naming the template directly would be
    a second way to address a send.
    """

    intent: str
    name: str
    language: Optional[str] = None
    category: Optional[str] = None
    body: Optional[str] = None
    variables: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# The suggested reply
# ---------------------------------------------------------------------------

class SuggestedReplyOut(BaseModel):
    """A draft for an agent to edit and send. Never a message.

    ``auto_sent`` is pinned ``False`` in the contract rather than merely
    absent, the same way ``ConnectionTestOut.sent_message`` is: this endpoint
    has no send path, and the console should be able to say so.

    ``draft`` is ``None`` whenever the answer is "a human should take this" —
    an escalating topic (money, KYC, fraud, a complaint, a legal threat, a
    distressed customer) or a draft carrying a figure. The withheld text is
    not carried in any other field: an escalation that shipped its own body
    would be one console tweak away from being sent anyway.
    """

    conversation_id: int
    draft: Optional[str] = None
    escalate: bool = False
    # Why it answered, or why it escalated. Audited alongside the draft.
    reason: Optional[str] = None
    model: Optional[str] = None
    prompt_version: Optional[str] = None
    service_window_open: bool = True
    auto_sent: Literal[False] = False
    notice: str = (
        "A draft, not a message. Read it against the thread, correct anything "
        "it asserts, and send it yourself — nothing here has reached the "
        "customer."
    )
