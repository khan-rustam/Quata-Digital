"""Storage for QCP — the Quata Communications Platform.

QCP is the single WhatsApp backbone for every QUATA product. Products call
QCP; only QCP talks to Meta. Two Meta numbers exist and the separation
between them is the whole point of this schema:

* **Quata Verify** (``purpose='authentication'``) — OTP, login codes, PIN
  resets, device verification. Templates of the ``authentication`` category
  only; transaction and security alerts live on QUATA as utility.
* **QUATA** (``purpose='engagement'``) — support, AI, campaigns, order and
  delivery updates, promotions.

Meta restricts numbers that send marketing on an authentication template, so
the separation is enforced by the *storage engine*, not by convention:

* ``whatsapp_templates`` carries the account's ``purpose`` denormalised and
  holds a composite FK to ``whatsapp_accounts(id, purpose)``. Three CHECK
  constraints then pin the separation — an ``authentication`` template can
  only live on the Verify number, a ``marketing`` template can never live
  there, and the Verify number takes the ``authentication`` category and
  nothing else.
* ``whatsapp_messages`` carries the same denormalised ``account_purpose`` and
  holds *two* composite FKs against it — one to the account, one to the
  template. A row naming the Verify account and a marketing template has no
  ``(template_id, 'authentication')`` pair to point at, so the INSERT fails.

**Dialect caveat.** Composite FKs are enforced by Postgres (production).
SQLite (dev/test) does not enable ``PRAGMA foreign_keys`` in this repo, so in
dev the FK layer of the invariant is inert and the CHECK layer plus
``app.services.whatsapp.routing.resolve_route()`` carry it. CHECK constraints
are enforced by both dialects. No native PG ENUMs are used anywhere — every
"enum" is ``String(N)`` + ``CheckConstraint``, matching how the rest of this
codebase does it (see ``notification.py``).

No ``SoftDeleteMixin`` on any table here: the global soft-delete loader
filter in ``db/session.py`` would silently hide QCP rows, and a message log
must never disappear.
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


# Purposes. These two strings are the invariant; nothing else may be stored.
PURPOSE_AUTHENTICATION = "authentication"
PURPOSE_ENGAGEMENT = "engagement"


class WhatsAppAccount(Base, TimestampMixin):
    """One Meta WhatsApp Business number. There are exactly two live ones.

    ``is_active`` defaults to FALSE and the partial unique index allows at
    most one *live* number per purpose, while still letting a retired number
    sit alongside its replacement.

    Credentials are Fernet-encrypted at rest (see
    ``app.services.whatsapp.credentials``) and are never returned by any API.
    """

    __tablename__ = "whatsapp_accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    purpose: Mapped[str] = mapped_column(String(20), index=True)

    phone_number_id: Mapped[str] = mapped_column(String(40))
    waba_id: Mapped[str] = mapped_column(String(40))
    display_phone: Mapped[str] = mapped_column(String(32))

    access_token_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    app_secret_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    webhook_verify_token_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    api_version: Mapped[str] = mapped_column(String(12), default="v21.0", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)

    health: Mapped[str] = mapped_column(String(20), default="unknown", nullable=False)
    quality_rating: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    messaging_limit: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    last_checked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Never contains a token — see credentials.py / meta.py scrubbing.
    last_error: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    __table_args__ = (
        # Anchor for the composite FKs that carry the invariant.
        UniqueConstraint("id", "purpose", name="uq_whatsapp_accounts_id_purpose"),
        CheckConstraint(
            "purpose IN ('authentication','engagement')",
            name="ck_whatsapp_accounts_purpose",
        ),
        CheckConstraint(
            "health IN ('unknown','ok','degraded','unauthorized')",
            name="ck_whatsapp_accounts_health",
        ),
        Index(
            "uq_whatsapp_accounts_active_purpose",
            "purpose",
            unique=True,
            sqlite_where=text("is_active = 1"),
            postgresql_where=text("is_active"),
        ),
    )


class WhatsAppProduct(Base, TimestampMixin):
    """A QUATA product entitled to call QCP — the plugin registry.

    ``is_enabled`` defaults to FALSE: that flag *is* the per-product
    migration gate. QuataFood/QuataPay keep sending exactly as they do today
    until an admin flips it.

    Deliberately NOT called ``products`` — that table name belongs to the CMS
    marketing catalogue (``app/models/product.py``).
    """

    __tablename__ = "whatsapp_products"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    is_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)

    # sha256 hex of the QCP key. The plaintext key is shown once at creation
    # and never stored. Empty = no key has ever been issued: no sha256 hex
    # digest can equal "", so a seeded product cannot authenticate until an
    # admin mints one.
    api_key_hash: Mapped[str] = mapped_column(String(128), default="", nullable=False)
    api_key_prefix: Mapped[str] = mapped_column(String(12), default="", nullable=False)

    # Which account purposes this product may reach *at all*.
    allowed_purposes: Mapped[Optional[list]] = mapped_column(
        JSON, default=lambda: [PURPOSE_ENGAGEMENT], nullable=True
    )
    default_locale: Mapped[str] = mapped_column(String(10), default="en", nullable=False)
    rate_limit_per_minute: Mapped[int] = mapped_column(Integer, default=600, nullable=False)

    webhook_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    webhook_secret_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # sha256[:16] of the plugin spec last synced — makes drift visible.
    registry_version: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class WhatsAppTemplate(Base, TimestampMixin):
    """A Meta message template, bound to exactly one account for its life.

    ``account_purpose`` is denormalised on purpose: it is the column the
    composite FKs travel through, and it is what makes "marketing on the
    Verify number" unrepresentable rather than merely discouraged.

    The Verify number takes ``category='authentication'`` and nothing else.
    ``utility`` used to be allowed on both numbers on the argument that
    transaction and security alerts belong on Verify — but ``category`` was
    operator-typed data that no code path in QCP wrote and nothing synced
    back from Meta, so a row saying ``utility`` stayed ``utility`` here even
    after Meta re-classified the template as ``MARKETING``. QCP would then
    keep sending marketing from the verification number, which is exactly
    what the split exists to prevent. Transaction and security alerts live on
    QUATA as ``utility``, which is where Meta expects them.

    ``category`` and ``status`` are now **owned by Meta**:
    ``services/whatsapp/templates.sync_from_meta`` overwrites both on every
    reconcile, stamps ``last_synced_at`` and ``body_hash``, and refuses to
    let a local edit make a template look more sendable than Meta says it
    is. When a sync finds a category the CHECKs above forbid on this row's
    number, no illegal row is written: the local row's ``status`` drops to
    ``disabled`` (which is what stops ``routing._find_template`` selecting
    it) and an audited alert is raised for a human.
    """

    __tablename__ = "whatsapp_templates"

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(Integer, nullable=False)
    account_purpose: Mapped[str] = mapped_column(String(20), nullable=False)

    product_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("whatsapp_products.id"), nullable=True
    )

    name: Mapped[str] = mapped_column(String(120))
    language: Mapped[str] = mapped_column(String(10), default="en", nullable=False)
    # Meta's three categories.
    category: Mapped[str] = mapped_column(String(20), nullable=False)
    # Plugin-declared, e.g. "login_otp", "order_dispatched".
    intent: Mapped[str] = mapped_column(String(80), index=True)
    status: Mapped[str] = mapped_column(
        String(20), index=True, default="pending_approval", nullable=False
    )

    provider_template_id: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    # sha256 of the approved body — detects drift after a re-approval.
    body_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    variables: Mapped[Optional[list]] = mapped_column(JSON, default=list, nullable=True)
    example_payload: Mapped[Optional[dict]] = mapped_column(JSON, default=dict, nullable=True)
    rejection_reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    # Seam only — v1 never writes it.
    flow_id: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["account_id", "account_purpose"],
            ["whatsapp_accounts.id", "whatsapp_accounts.purpose"],
            name="fk_whatsapp_templates_account_purpose",
        ),
        # Anchor for whatsapp_messages' composite FK.
        UniqueConstraint("id", "account_purpose", name="uq_whatsapp_templates_id_purpose"),
        UniqueConstraint(
            "account_id", "name", "language", name="uq_whatsapp_templates_account_name_lang"
        ),
        CheckConstraint(
            "category <> 'authentication' OR account_purpose = 'authentication'",
            name="ck_whatsapp_templates_auth_only_on_verify",
        ),
        CheckConstraint(
            "category <> 'marketing' OR account_purpose = 'engagement'",
            name="ck_whatsapp_templates_marketing_never_on_verify",
        ),
        # The Verify number accepts the authentication category and nothing
        # else. Ordered after the marketing CHECK so a marketing-on-Verify
        # row still fails with the constraint that names its actual sin.
        CheckConstraint(
            "account_purpose <> 'authentication' OR category = 'authentication'",
            name="ck_whatsapp_templates_verify_is_auth_only",
        ),
        CheckConstraint(
            "category IN ('authentication','marketing','utility')",
            name="ck_whatsapp_templates_category",
        ),
        CheckConstraint(
            "status IN ('draft','pending_approval','approved','rejected','paused','disabled')",
            name="ck_whatsapp_templates_status",
        ),
        Index("ix_whatsapp_templates_account_status", "account_id", "status"),
        Index("ix_whatsapp_templates_product_intent", "product_id", "intent"),
    )


class WhatsAppConversation(Base, TimestampMixin):
    """One WhatsApp thread with one contact on one account.

    Inbound to the Verify number still creates a conversation — Meta will
    deliver whatever a user types. What is forbidden is *sending* free-form
    from that number; see ``ck_whatsapp_messages_no_freeform_on_verify``.
    """

    __tablename__ = "whatsapp_conversations"

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("whatsapp_accounts.id"), nullable=False)
    product_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("whatsapp_products.id"), nullable=True
    )

    wa_contact_id: Mapped[str] = mapped_column(String(40))
    phone_e164: Mapped[str] = mapped_column(String(24), index=True)
    display_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)

    state: Mapped[str] = mapped_column(String(20), default="open", nullable=False)
    assignee_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    # AI seam — v1 writes NULL and never reads it.
    assigned_agent: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)

    last_inbound_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    last_outbound_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # last_inbound_at + 24h — Meta's free-form service window.
    service_window_expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )

    unread_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locale: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    meta: Mapped[Optional[dict]] = mapped_column(JSON, default=dict, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "account_id", "wa_contact_id", name="uq_whatsapp_conversations_account_contact"
        ),
        CheckConstraint(
            "state IN ('open','snoozed','closed')", name="ck_whatsapp_conversations_state"
        ),
        Index(
            "ix_whatsapp_conversations_account_state_inbound",
            "account_id",
            "state",
            "last_inbound_at",
        ),
    )


class WhatsAppMessage(Base, TimestampMixin):
    """The outbound outbox and the full message log.

    ``account_purpose`` is denormalised so the two composite FKs below can
    exist. Together they are the enforcement: a message row cannot name an
    account of one purpose and a template bound to the other.

    ``body`` and ``variables`` are stored **redacted** — an OTP is persisted
    as ``{"code": "sha256:ab12…"}``, never in clear.
    """

    __tablename__ = "whatsapp_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    # QCP's public id handed back to products (mirrors NotificationEvent.event_id).
    message_uid: Mapped[str] = mapped_column(String(40), unique=True, index=True)

    account_id: Mapped[int] = mapped_column(Integer, nullable=False)
    account_purpose: Mapped[str] = mapped_column(String(20), nullable=False)

    conversation_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("whatsapp_conversations.id"), nullable=True
    )
    product_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("whatsapp_products.id"), nullable=True
    )
    template_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    direction: Mapped[str] = mapped_column(String(10), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    intent: Mapped[Optional[str]] = mapped_column(String(80), nullable=True, index=True)

    to_phone_e164: Mapped[Optional[str]] = mapped_column(String(24), nullable=True, index=True)
    from_phone_e164: Mapped[Optional[str]] = mapped_column(String(24), nullable=True)

    body: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    variables: Mapped[Optional[dict]] = mapped_column(JSON, default=dict, nullable=True)
    media: Mapped[Optional[dict]] = mapped_column(JSON, default=dict, nullable=True)

    provider_message_id: Mapped[Optional[str]] = mapped_column(
        String(80), unique=True, index=True, nullable=True
    )
    idempotency_key: Mapped[Optional[str]] = mapped_column(
        String(200), unique=True, index=True, nullable=True
    )

    status: Mapped[str] = mapped_column(String(20), index=True, default="queued", nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    # NULL once terminal.
    next_attempt_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )

    last_error: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    error_code: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    suppressed_reason: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    pricing_category: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    # Campaigns seam — v1 never writes it.
    campaign_id: Mapped[Optional[str]] = mapped_column(String(40), nullable=True, index=True)
    source_ip: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)

    __table_args__ = (
        ForeignKeyConstraint(
            ["account_id", "account_purpose"],
            ["whatsapp_accounts.id", "whatsapp_accounts.purpose"],
            name="fk_whatsapp_messages_account_purpose",
        ),
        # ← THE INVARIANT. A template can only be used on the account whose
        # purpose it was bound to at creation.
        ForeignKeyConstraint(
            ["template_id", "account_purpose"],
            ["whatsapp_templates.id", "whatsapp_templates.account_purpose"],
            name="fk_whatsapp_messages_template_purpose",
        ),
        CheckConstraint(
            "direction = 'inbound' OR kind <> 'template' OR template_id IS NOT NULL",
            name="ck_whatsapp_messages_template_required",
        ),
        CheckConstraint(
            "account_purpose <> 'authentication' OR direction = 'inbound' OR kind = 'template'",
            name="ck_whatsapp_messages_no_freeform_on_verify",
        ),
        CheckConstraint(
            "direction IN ('inbound','outbound')", name="ck_whatsapp_messages_direction"
        ),
        CheckConstraint(
            "kind IN ('template','text','interactive','media','reaction','system')",
            name="ck_whatsapp_messages_kind",
        ),
        CheckConstraint(
            "status IN ('queued','sending','sent','delivered','read','failed','suppressed')",
            name="ck_whatsapp_messages_status",
        ),
        # The sweeper's hot query.
        Index("ix_whatsapp_messages_status_next_attempt", "status", "next_attempt_at"),
        Index("ix_whatsapp_messages_conversation_created", "conversation_id", "created_at"),
        Index("ix_whatsapp_messages_product_created", "product_id", "created_at"),
        Index("ix_whatsapp_messages_account_created", "account_id", "created_at"),
    )


class WhatsAppRoutingRule(Base, TimestampMixin):
    """What a product's intent resolves to — the routing table.

    ``fallback_channel`` is the direct answer to the audited QuataFood
    finding: a phone-change verification with no fallback is now a visible,
    auditable field rather than an accident nobody can see from the code.

    ``is_active`` defaults to FALSE. A synced rule takes no traffic until an
    admin turns it on.
    """

    __tablename__ = "whatsapp_routing_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("whatsapp_products.id"), nullable=False)
    # What the product asks for, e.g. "login_otp".
    intent: Mapped[str] = mapped_column(String(80), nullable=False)
    purpose: Mapped[str] = mapped_column(String(20), nullable=False)
    template_intent: Mapped[str] = mapped_column(String(80), nullable=False)
    # NULL = any locale.
    locale: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    fallback_channel: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    # Campaigns/segments seam — v1 treats a non-empty conditions as no_route.
    conditions: Mapped[Optional[dict]] = mapped_column(JSON, default=dict, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "product_id", "intent", "locale", name="uq_whatsapp_routing_product_intent_locale"
        ),
        CheckConstraint(
            "purpose IN ('authentication','engagement')", name="ck_whatsapp_routing_purpose"
        ),
        CheckConstraint(
            "fallback_channel IS NULL OR fallback_channel IN ('email','sms','none')",
            name="ck_whatsapp_routing_fallback_channel",
        ),
        Index("ix_whatsapp_routing_product_active", "product_id", "is_active"),
    )


class WhatsAppDeliveryEvent(Base, TimestampMixin):
    """One status callback from Meta, deduped.

    ``message_id`` is NULL when the wamid is unknown to us — Meta redelivers
    whole webhook envelopes and we keep the evidence either way.
    """

    __tablename__ = "whatsapp_delivery_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    message_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("whatsapp_messages.id"), nullable=True
    )
    provider_message_id: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    account_id: Mapped[int] = mapped_column(ForeignKey("whatsapp_accounts.id"), nullable=False)

    status: Mapped[str] = mapped_column(String(20), nullable=False)
    # Meta's timestamp, not ours.
    status_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    error_code: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    error_title: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    error_detail: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    pricing: Mapped[Optional[dict]] = mapped_column(JSON, default=dict, nullable=True)
    conversation_ref: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)

    dedupe_key: Mapped[str] = mapped_column(String(160), unique=True, index=True, nullable=False)
    # Redacted webhook fragment.
    raw: Mapped[Optional[dict]] = mapped_column(JSON, default=dict, nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_whatsapp_delivery_events_message_status_at", "message_id", "status_at"),
    )


class WhatsAppAuditLog(Base, TimestampMixin):
    """Who/what did it, and whether it was allowed.

    Deliberately not ``activity_logs``: that table is admin-actor-scoped and
    has no product/account dimension and no ``outcome``. QCP must record
    *machine-initiated denials with no user* — a blocked marketing-on-Verify
    attempt is the single most important row this system will ever write, and
    it has no actor.
    """

    __tablename__ = "whatsapp_audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    actor_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    product_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("whatsapp_products.id"), nullable=True
    )
    account_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("whatsapp_accounts.id"), nullable=True
    )

    action: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    resource_type: Mapped[str] = mapped_column(String(60), nullable=False)
    resource_id: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)

    outcome: Mapped[str] = mapped_column(String(20), default="ok", nullable=False)
    # The RoutingDenied reason code.
    reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    details: Mapped[Optional[dict]] = mapped_column(JSON, default=dict, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "outcome IN ('ok','denied','error')", name="ck_whatsapp_audit_log_outcome"
        ),
        Index("ix_whatsapp_audit_log_action_created", "action", "created_at"),
        Index("ix_whatsapp_audit_log_product_created", "product_id", "created_at"),
        Index("ix_whatsapp_audit_log_outcome_created", "outcome", "created_at"),
    )
