"""Storage for QCP campaigns — the marketing side of the platform.

Three tables, and the first one carries the whole point.

``whatsapp_campaigns`` is deliberately shaped like ``whatsapp_messages``: it
denormalises ``account_purpose`` and holds the same two composite foreign
keys, one to ``whatsapp_accounts(id, purpose)`` and one to
``whatsapp_templates(id, account_purpose)``. On top of that it carries a
CHECK that pins ``account_purpose = 'engagement'``. A campaign row naming the
Quata Verify number, or naming a template bound to it, therefore has nothing
to point at and cannot be inserted. Marketing on the verification number is
not "refused by the campaign service" — it is unrepresentable, exactly as it
already is for a message.

*(Dialect caveat, identical to ``app/models/whatsapp.py``: composite FKs are
enforced by Postgres. SQLite does not enable ``PRAGMA foreign_keys`` in this
repo, so in dev that layer is inert and the CHECK plus ``resolve_route`` carry
it.)*

``whatsapp_opt_outs`` is the second table and it is intentionally
number-wide, not per-product and not per-campaign. Both Meta numbers are
shared by every QUATA product; a customer who says STOP is telling QCP to
stop, and scoping their answer to whichever product happened to be sending
would be a technicality they never agreed to. There is also no service
function that deletes a row here — see ``consent``.

``whatsapp_campaign_recipients`` is the per-send ledger. It holds *who* and
*what happened at hand-off*; it deliberately does not duplicate delivery
state, because ``whatsapp_messages`` already owns that and the webhook
already updates it. Results are read by joining on ``campaign_id``, so
"delivered" on a campaign screen is the same fact as "delivered" everywhere
else in QCP rather than a second copy that can drift.

No ``SoftDeleteMixin``, for the reason the rest of QCP has none: the global
soft-delete loader filter would silently hide rows, and a record of who was
messaged must never disappear.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


# The only purpose a campaign may ever name.
PURPOSE_ENGAGEMENT = "engagement"

# Campaign lifecycle. ``draft`` is where every campaign starts and there is no
# constructor that produces anything else.
STATUS_DRAFT = "draft"
STATUS_SCHEDULED = "scheduled"
STATUS_RUNNING = "running"
STATUS_PAUSED = "paused"
STATUS_STOPPED = "stopped"
STATUS_COMPLETED = "completed"

CAMPAIGN_STATUSES = (
    STATUS_DRAFT,
    STATUS_SCHEDULED,
    STATUS_RUNNING,
    STATUS_PAUSED,
    STATUS_STOPPED,
    STATUS_COMPLETED,
)

# Per-recipient hand-off outcome. Delivery state past the hand-off lives on
# ``whatsapp_messages`` and is never copied here.
RECIPIENT_PENDING = "pending"
RECIPIENT_QUEUED = "queued"
RECIPIENT_SUPPRESSED = "suppressed"
RECIPIENT_FAILED = "failed"
RECIPIENT_OPTED_OUT = "opted_out"
RECIPIENT_CANCELLED = "cancelled"

RECIPIENT_STATUSES = (
    RECIPIENT_PENDING,
    RECIPIENT_QUEUED,
    RECIPIENT_SUPPRESSED,
    RECIPIENT_FAILED,
    RECIPIENT_OPTED_OUT,
    RECIPIENT_CANCELLED,
)

# How an opt-out was learned. ``inbound_keyword`` is the customer's own word.
OPT_OUT_INBOUND = "inbound_keyword"
OPT_OUT_ADMIN = "admin"
OPT_OUT_SOURCES = (OPT_OUT_INBOUND, OPT_OUT_ADMIN)

# The pacing quantum, in messages per minute. The ceiling is deliberately low:
# a new WABA sits in Meta's lowest messaging tier, and a burst is what gets a
# number throttled or restricted. Raising it is a schema change, on purpose.
MAX_MESSAGES_PER_MINUTE = 60
DEFAULT_MESSAGES_PER_MINUTE = 20

# The fleet's per-person ceiling: at most three messages to one number in any
# rolling twenty-four hours, counted across **every** sender rather than per
# campaign. One message per person per campaign is not a limit — three
# campaigns over overlapping audiences on one day is three messages, and an
# order update on top of them is a fourth. The person on the other end counts
# messages from a number, not from a campaign, and so does Meta.
MAX_MESSAGES_PER_PERSON_PER_DAY = 3
PERSON_CAP_WINDOW_HOURS = 24


class WhatsAppCampaign(Base, TimestampMixin):
    """One marketing send: an audience, a route, a schedule and a stop button.

    A campaign does not carry a template body or a Meta credential. It names
    a *product* and an *intent*, which is what every other send in QCP names,
    so it resolves through ``routing.resolve_route`` like everything else and
    inherits every check that lives there. ``template_id`` below is a
    snapshot of what that resolution produced when the campaign was created —
    it is shown to the operator and it anchors the composite FK, but it is
    never what decides the send. The route is re-resolved on every message.
    """

    __tablename__ = "whatsapp_campaigns"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Public id, and the value written into ``whatsapp_messages.campaign_id``
    # — the seam that table has carried since the platform was built.
    campaign_uid: Mapped[str] = mapped_column(String(40), unique=True, index=True)

    name: Mapped[str] = mapped_column(String(120), nullable=False)

    product_id: Mapped[int] = mapped_column(
        ForeignKey("whatsapp_products.id"), nullable=False
    )
    # What the product would ask QCP for. Routing rules match on this.
    intent: Mapped[str] = mapped_column(String(80), nullable=False)
    locale: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)

    account_id: Mapped[int] = mapped_column(Integer, nullable=False)
    account_purpose: Mapped[str] = mapped_column(String(20), nullable=False)
    template_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    audience_source: Mapped[str] = mapped_column(String(30), nullable=False)
    audience_filters: Mapped[Optional[dict]] = mapped_column(JSON, default=dict, nullable=True)
    audience_size: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # The template's variable values, identical for every recipient. Campaigns
    # do not personalise in v1: a per-recipient variable would need a customer
    # database QCP does not have and must not invent.
    variables: Mapped[Optional[list]] = mapped_column(JSON, default=list, nullable=True)

    status: Mapped[str] = mapped_column(
        String(20), default=STATUS_DRAFT, nullable=False, index=True
    )

    messages_per_minute: Mapped[int] = mapped_column(
        Integer, default=DEFAULT_MESSAGES_PER_MINUTE, nullable=False
    )
    # When the runner may next take a batch. The pacing state, kept in the
    # row rather than in a worker's memory so a restart cannot burst.
    next_batch_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )

    scheduled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    stopped_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    stopped_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    stop_reason: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    created_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    last_error: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    __table_args__ = (
        ForeignKeyConstraint(
            ["account_id", "account_purpose"],
            ["whatsapp_accounts.id", "whatsapp_accounts.purpose"],
            name="fk_whatsapp_campaigns_account_purpose",
        ),
        # ← the same invariant ``whatsapp_messages`` carries: the template
        # must be bound to a number of this purpose.
        ForeignKeyConstraint(
            ["template_id", "account_purpose"],
            ["whatsapp_templates.id", "whatsapp_templates.account_purpose"],
            name="fk_whatsapp_campaigns_template_purpose",
        ),
        # ← and the one that is specific to campaigns. A campaign is
        # marketing. Marketing never leaves Quata Verify, so a campaign row
        # may only ever name the engagement number.
        CheckConstraint(
            "account_purpose = 'engagement'",
            name="ck_whatsapp_campaigns_engagement_only",
        ),
        CheckConstraint(
            "status IN ('draft','scheduled','running','paused','stopped','completed')",
            name="ck_whatsapp_campaigns_status",
        ),
        CheckConstraint(
            "messages_per_minute >= 1 AND messages_per_minute <= 60",
            name="ck_whatsapp_campaigns_rate",
        ),
        # The runner's hot query.
        Index("ix_whatsapp_campaigns_status_next_batch", "status", "next_batch_at"),
        Index("ix_whatsapp_campaigns_product_created", "product_id", "created_at"),
    )


class WhatsAppCampaignRecipient(Base, TimestampMixin):
    """One address in one campaign, and what happened when QCP handed it off.

    The unique constraint on ``(campaign_id, phone_e164)`` is doing real work:
    an audience rebuild, a restart mid-flight and a double-click on Start all
    converge on the same row rather than producing a second message. The
    outbound idempotency key the runner derives from ``(campaign_uid, phone)``
    is the second half of that guarantee, inside ``dispatch``.
    """

    __tablename__ = "whatsapp_campaign_recipients"

    id: Mapped[int] = mapped_column(primary_key=True)
    campaign_id: Mapped[int] = mapped_column(
        ForeignKey("whatsapp_campaigns.id"), nullable=False, index=True
    )

    phone_e164: Mapped[str] = mapped_column(String(24), nullable=False)
    conversation_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("whatsapp_conversations.id"), nullable=True
    )
    locale: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)

    status: Mapped[str] = mapped_column(
        String(20), default=RECIPIENT_PENDING, nullable=False
    )
    # QCP's own message id, so the row can be joined to the message log.
    message_uid: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    # A routing reason code or a transport failure — never Meta's raw text.
    last_error: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    attempted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        UniqueConstraint(
            "campaign_id", "phone_e164", name="uq_whatsapp_campaign_recipient"
        ),
        CheckConstraint(
            "status IN ('pending','queued','suppressed','failed','opted_out','cancelled')",
            name="ck_whatsapp_campaign_recipients_status",
        ),
        Index("ix_whatsapp_campaign_recipients_campaign_status", "campaign_id", "status"),
    )


class WhatsAppOptOut(Base, TimestampMixin):
    """A number that must never receive a campaign again.

    One row per phone, for the whole platform. Not per product, not per
    campaign: the customer is talking to a WhatsApp number, that number is
    shared by every QUATA product, and Meta counts the block reports against
    it. Narrowing the scope of "stop" to the product that happened to be
    sending would be a distinction the customer never made.

    Nothing in ``consent`` deletes one of these.
    """

    __tablename__ = "whatsapp_opt_outs"

    id: Mapped[int] = mapped_column(primary_key=True)
    phone_e164: Mapped[str] = mapped_column(String(24), unique=True, index=True)

    source: Mapped[str] = mapped_column(String(20), nullable=False)
    # The wording that was matched, or the message_uid it was matched in.
    # Never the whole message body.
    evidence: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    note: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    actor_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "source IN ('inbound_keyword','admin')", name="ck_whatsapp_opt_outs_source"
        ),
        Index("ix_whatsapp_opt_outs_created", "created_at"),
    )
