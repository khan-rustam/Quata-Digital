"""qcp_whatsapp_platform

The eight tables backing QCP — the Quata Communications Platform hosted at
whatsapp.quatadigital.com. Two Meta numbers ("Quata Verify" for
authentication only, "QUATA" for everything else), a plugin registry of the
products entitled to call QCP, templates, conversations, the message
outbox/log, routing rules, Meta delivery callbacks and an audit trail.

The account-purpose separation is enforced in the schema, not by convention:
``whatsapp_templates`` carries a denormalised ``account_purpose`` with a
composite FK to ``whatsapp_accounts(id, purpose)`` and three CHECKs, and
``whatsapp_messages`` carries composite FKs to both. There is no row shape
that pairs the Verify number with anything but an authentication template.

Composite FKs are enforced by Postgres. SQLite (dev) does not enable
``PRAGMA foreign_keys`` in this repo, so there the CHECK constraints and
``services/whatsapp/routing.resolve_route()`` carry the invariant.

Revision ID: x4c5d6e7f8g9
Revises: w3b4c5d6e7f8
Create Date: 2026-08-11 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "x4c5d6e7f8g9"
down_revision: Union[str, None] = "w3b4c5d6e7f8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _timestamps() -> list:
    return [
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
    ]


def upgrade() -> None:
    # ---------------------------------------------------------------- accounts
    op.create_table(
        "whatsapp_accounts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("slug", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("purpose", sa.String(length=20), nullable=False),
        sa.Column("phone_number_id", sa.String(length=40), nullable=False),
        sa.Column("waba_id", sa.String(length=40), nullable=False),
        sa.Column("display_phone", sa.String(length=32), nullable=False),
        sa.Column("access_token_encrypted", sa.Text(), nullable=True),
        sa.Column("app_secret_encrypted", sa.Text(), nullable=True),
        sa.Column("webhook_verify_token_encrypted", sa.Text(), nullable=True),
        sa.Column("api_version", sa.String(length=12), nullable=False, server_default="v21.0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("health", sa.String(length=20), nullable=False, server_default="unknown"),
        sa.Column("quality_rating", sa.String(length=20), nullable=True),
        sa.Column("messaging_limit", sa.String(length=20), nullable=True),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(length=500), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
        # Anchor for the composite FKs on templates + messages.
        sa.UniqueConstraint("id", "purpose", name="uq_whatsapp_accounts_id_purpose"),
        sa.CheckConstraint(
            "purpose IN ('authentication','engagement')",
            name="ck_whatsapp_accounts_purpose",
        ),
        sa.CheckConstraint(
            "health IN ('unknown','ok','degraded','unauthorized')",
            name="ck_whatsapp_accounts_health",
        ),
    )
    with op.batch_alter_table("whatsapp_accounts", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_whatsapp_accounts_slug"), ["slug"], unique=True)
        batch_op.create_index(batch_op.f("ix_whatsapp_accounts_purpose"), ["purpose"], unique=False)
        batch_op.create_index(
            batch_op.f("ix_whatsapp_accounts_is_active"), ["is_active"], unique=False
        )
        # Partial unique: at most ONE active number per purpose, while a
        # retired number may still sit alongside its replacement.
        batch_op.create_index(
            "uq_whatsapp_accounts_active_purpose",
            ["purpose"],
            unique=True,
            sqlite_where=sa.text("is_active = 1"),
            postgresql_where=sa.text("is_active"),
        )

    # ---------------------------------------------------------------- products
    op.create_table(
        "whatsapp_products",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("slug", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("api_key_hash", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("api_key_prefix", sa.String(length=12), nullable=False, server_default=""),
        sa.Column("allowed_purposes", sa.JSON(), nullable=True),
        sa.Column("default_locale", sa.String(length=10), nullable=False, server_default="en"),
        sa.Column(
            "rate_limit_per_minute", sa.Integer(), nullable=False, server_default="600"
        ),
        sa.Column("webhook_url", sa.String(length=500), nullable=True),
        sa.Column("webhook_secret_encrypted", sa.Text(), nullable=True),
        sa.Column("registry_version", sa.String(length=20), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("whatsapp_products", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_whatsapp_products_slug"), ["slug"], unique=True)
        batch_op.create_index(
            batch_op.f("ix_whatsapp_products_is_enabled"), ["is_enabled"], unique=False
        )

    # --------------------------------------------------------------- templates
    op.create_table(
        "whatsapp_templates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        # Denormalised on purpose — this column is what carries the invariant.
        sa.Column("account_purpose", sa.String(length=20), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("language", sa.String(length=10), nullable=False, server_default="en"),
        sa.Column("category", sa.String(length=20), nullable=False),
        sa.Column("intent", sa.String(length=80), nullable=False),
        sa.Column(
            "status", sa.String(length=20), nullable=False, server_default="pending_approval"
        ),
        sa.Column("provider_template_id", sa.String(length=60), nullable=True),
        sa.Column("body_hash", sa.String(length=64), nullable=True),
        sa.Column("variables", sa.JSON(), nullable=True),
        sa.Column("example_payload", sa.JSON(), nullable=True),
        sa.Column("rejection_reason", sa.String(length=500), nullable=True),
        sa.Column("flow_id", sa.String(length=40), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["account_id", "account_purpose"],
            ["whatsapp_accounts.id", "whatsapp_accounts.purpose"],
            name="fk_whatsapp_templates_account_purpose",
        ),
        sa.ForeignKeyConstraint(["product_id"], ["whatsapp_products.id"]),
        # Anchor for whatsapp_messages' composite FK.
        sa.UniqueConstraint("id", "account_purpose", name="uq_whatsapp_templates_id_purpose"),
        sa.UniqueConstraint(
            "account_id", "name", "language", name="uq_whatsapp_templates_account_name_lang"
        ),
        sa.CheckConstraint(
            "category <> 'authentication' OR account_purpose = 'authentication'",
            name="ck_whatsapp_templates_auth_only_on_verify",
        ),
        sa.CheckConstraint(
            "category <> 'marketing' OR account_purpose = 'engagement'",
            name="ck_whatsapp_templates_marketing_never_on_verify",
        ),
        # The Verify number accepts the authentication category and nothing
        # else. ``category`` is operator-typed and never synced back from
        # Meta, so a template filed as 'utility' would keep leaving the
        # verification number even after Meta re-classified it as MARKETING.
        # Ordered after the marketing CHECK so a marketing-on-Verify row
        # still fails with the constraint that names its actual sin.
        sa.CheckConstraint(
            "account_purpose <> 'authentication' OR category = 'authentication'",
            name="ck_whatsapp_templates_verify_is_auth_only",
        ),
        sa.CheckConstraint(
            "category IN ('authentication','marketing','utility')",
            name="ck_whatsapp_templates_category",
        ),
        sa.CheckConstraint(
            "status IN ('draft','pending_approval','approved','rejected','paused','disabled')",
            name="ck_whatsapp_templates_status",
        ),
    )
    with op.batch_alter_table("whatsapp_templates", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_whatsapp_templates_intent"), ["intent"], unique=False)
        batch_op.create_index(batch_op.f("ix_whatsapp_templates_status"), ["status"], unique=False)
        batch_op.create_index(
            "ix_whatsapp_templates_account_status", ["account_id", "status"], unique=False
        )
        batch_op.create_index(
            "ix_whatsapp_templates_product_intent", ["product_id", "intent"], unique=False
        )

    # ----------------------------------------------------------- conversations
    op.create_table(
        "whatsapp_conversations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=True),
        sa.Column("wa_contact_id", sa.String(length=40), nullable=False),
        sa.Column("phone_e164", sa.String(length=24), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=True),
        sa.Column("state", sa.String(length=20), nullable=False, server_default="open"),
        sa.Column("assignee_id", sa.Integer(), nullable=True),
        sa.Column("assigned_agent", sa.String(length=40), nullable=True),
        sa.Column("last_inbound_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_outbound_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("service_window_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("unread_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("locale", sa.String(length=10), nullable=True),
        sa.Column("meta", sa.JSON(), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["account_id"], ["whatsapp_accounts.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["whatsapp_products.id"]),
        sa.ForeignKeyConstraint(["assignee_id"], ["users.id"]),
        sa.UniqueConstraint(
            "account_id", "wa_contact_id", name="uq_whatsapp_conversations_account_contact"
        ),
        sa.CheckConstraint(
            "state IN ('open','snoozed','closed')", name="ck_whatsapp_conversations_state"
        ),
    )
    with op.batch_alter_table("whatsapp_conversations", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_whatsapp_conversations_phone_e164"), ["phone_e164"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_whatsapp_conversations_last_inbound_at"),
            ["last_inbound_at"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_whatsapp_conversations_service_window_expires_at"),
            ["service_window_expires_at"],
            unique=False,
        )
        batch_op.create_index(
            "ix_whatsapp_conversations_account_state_inbound",
            ["account_id", "state", "last_inbound_at"],
            unique=False,
        )

    # ---------------------------------------------------------------- messages
    op.create_table(
        "whatsapp_messages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("message_uid", sa.String(length=40), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("account_purpose", sa.String(length=20), nullable=False),
        sa.Column("conversation_id", sa.Integer(), nullable=True),
        sa.Column("product_id", sa.Integer(), nullable=True),
        sa.Column("template_id", sa.Integer(), nullable=True),
        sa.Column("direction", sa.String(length=10), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("intent", sa.String(length=80), nullable=True),
        sa.Column("to_phone_e164", sa.String(length=24), nullable=True),
        sa.Column("from_phone_e164", sa.String(length=24), nullable=True),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("variables", sa.JSON(), nullable=True),
        sa.Column("media", sa.JSON(), nullable=True),
        sa.Column("provider_message_id", sa.String(length=80), nullable=True),
        sa.Column("idempotency_key", sa.String(length=200), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="queued"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(length=500), nullable=True),
        sa.Column("error_code", sa.String(length=40), nullable=True),
        sa.Column("suppressed_reason", sa.String(length=200), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("pricing_category", sa.String(length=20), nullable=True),
        sa.Column("campaign_id", sa.String(length=40), nullable=True),
        sa.Column("source_ip", sa.String(length=45), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["account_id", "account_purpose"],
            ["whatsapp_accounts.id", "whatsapp_accounts.purpose"],
            name="fk_whatsapp_messages_account_purpose",
        ),
        # ← THE INVARIANT. A marketing template can never carry
        # account_purpose='authentication' (see the templates CHECKs), so no
        # INSERT can pair the Verify number with a marketing template.
        sa.ForeignKeyConstraint(
            ["template_id", "account_purpose"],
            ["whatsapp_templates.id", "whatsapp_templates.account_purpose"],
            name="fk_whatsapp_messages_template_purpose",
        ),
        sa.ForeignKeyConstraint(["conversation_id"], ["whatsapp_conversations.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["whatsapp_products.id"]),
        sa.CheckConstraint(
            "direction = 'inbound' OR kind <> 'template' OR template_id IS NOT NULL",
            name="ck_whatsapp_messages_template_required",
        ),
        sa.CheckConstraint(
            "account_purpose <> 'authentication' OR direction = 'inbound' OR kind = 'template'",
            name="ck_whatsapp_messages_no_freeform_on_verify",
        ),
        sa.CheckConstraint(
            "direction IN ('inbound','outbound')", name="ck_whatsapp_messages_direction"
        ),
        sa.CheckConstraint(
            "kind IN ('template','text','interactive','media','reaction','system')",
            name="ck_whatsapp_messages_kind",
        ),
        sa.CheckConstraint(
            "status IN ('queued','sending','sent','delivered','read','failed','suppressed')",
            name="ck_whatsapp_messages_status",
        ),
    )
    with op.batch_alter_table("whatsapp_messages", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_whatsapp_messages_message_uid"), ["message_uid"], unique=True
        )
        batch_op.create_index(
            batch_op.f("ix_whatsapp_messages_provider_message_id"),
            ["provider_message_id"],
            unique=True,
        )
        batch_op.create_index(
            batch_op.f("ix_whatsapp_messages_idempotency_key"), ["idempotency_key"], unique=True
        )
        batch_op.create_index(batch_op.f("ix_whatsapp_messages_intent"), ["intent"], unique=False)
        batch_op.create_index(
            batch_op.f("ix_whatsapp_messages_to_phone_e164"), ["to_phone_e164"], unique=False
        )
        batch_op.create_index(batch_op.f("ix_whatsapp_messages_status"), ["status"], unique=False)
        batch_op.create_index(
            batch_op.f("ix_whatsapp_messages_next_attempt_at"), ["next_attempt_at"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_whatsapp_messages_campaign_id"), ["campaign_id"], unique=False
        )
        # The sweeper's hot query is
        # `WHERE status = 'queued' AND next_attempt_at <= now()`.
        batch_op.create_index(
            "ix_whatsapp_messages_status_next_attempt",
            ["status", "next_attempt_at"],
            unique=False,
        )
        batch_op.create_index(
            "ix_whatsapp_messages_conversation_created",
            ["conversation_id", "created_at"],
            unique=False,
        )
        batch_op.create_index(
            "ix_whatsapp_messages_product_created", ["product_id", "created_at"], unique=False
        )
        batch_op.create_index(
            "ix_whatsapp_messages_account_created", ["account_id", "created_at"], unique=False
        )

    # ----------------------------------------------------------- routing rules
    op.create_table(
        "whatsapp_routing_rules",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("intent", sa.String(length=80), nullable=False),
        sa.Column("purpose", sa.String(length=20), nullable=False),
        sa.Column("template_intent", sa.String(length=80), nullable=False),
        sa.Column("locale", sa.String(length=10), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("fallback_channel", sa.String(length=20), nullable=True),
        sa.Column("conditions", sa.JSON(), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["product_id"], ["whatsapp_products.id"]),
        sa.UniqueConstraint(
            "product_id", "intent", "locale", name="uq_whatsapp_routing_product_intent_locale"
        ),
        sa.CheckConstraint(
            "purpose IN ('authentication','engagement')", name="ck_whatsapp_routing_purpose"
        ),
        sa.CheckConstraint(
            "fallback_channel IS NULL OR fallback_channel IN ('email','sms','none')",
            name="ck_whatsapp_routing_fallback_channel",
        ),
    )
    with op.batch_alter_table("whatsapp_routing_rules", schema=None) as batch_op:
        batch_op.create_index(
            "ix_whatsapp_routing_product_active", ["product_id", "is_active"], unique=False
        )

    # --------------------------------------------------------- delivery events
    op.create_table(
        "whatsapp_delivery_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("message_id", sa.Integer(), nullable=True),
        sa.Column("provider_message_id", sa.String(length=80), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("status_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("error_code", sa.String(length=40), nullable=True),
        sa.Column("error_title", sa.String(length=200), nullable=True),
        sa.Column("error_detail", sa.String(length=500), nullable=True),
        sa.Column("pricing", sa.JSON(), nullable=True),
        sa.Column("conversation_ref", sa.String(length=80), nullable=True),
        sa.Column("dedupe_key", sa.String(length=160), nullable=False),
        sa.Column("raw", sa.JSON(), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["message_id"], ["whatsapp_messages.id"]),
        sa.ForeignKeyConstraint(["account_id"], ["whatsapp_accounts.id"]),
    )
    with op.batch_alter_table("whatsapp_delivery_events", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_whatsapp_delivery_events_dedupe_key"), ["dedupe_key"], unique=True
        )
        batch_op.create_index(
            batch_op.f("ix_whatsapp_delivery_events_provider_message_id"),
            ["provider_message_id"],
            unique=False,
        )
        batch_op.create_index(
            "ix_whatsapp_delivery_events_message_status_at",
            ["message_id", "status_at"],
            unique=False,
        )

    # --------------------------------------------------------------- audit log
    op.create_table(
        "whatsapp_audit_log",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column("product_id", sa.Integer(), nullable=True),
        sa.Column("account_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("resource_type", sa.String(length=60), nullable=False),
        sa.Column("resource_id", sa.String(length=80), nullable=True),
        sa.Column("outcome", sa.String(length=20), nullable=False, server_default="ok"),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["whatsapp_products.id"]),
        sa.ForeignKeyConstraint(["account_id"], ["whatsapp_accounts.id"]),
        sa.CheckConstraint(
            "outcome IN ('ok','denied','error')", name="ck_whatsapp_audit_log_outcome"
        ),
    )
    with op.batch_alter_table("whatsapp_audit_log", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_whatsapp_audit_log_action"), ["action"], unique=False)
        batch_op.create_index(
            "ix_whatsapp_audit_log_action_created", ["action", "created_at"], unique=False
        )
        batch_op.create_index(
            "ix_whatsapp_audit_log_product_created", ["product_id", "created_at"], unique=False
        )
        batch_op.create_index(
            "ix_whatsapp_audit_log_outcome_created", ["outcome", "created_at"], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table("whatsapp_audit_log", schema=None) as batch_op:
        batch_op.drop_index("ix_whatsapp_audit_log_outcome_created")
        batch_op.drop_index("ix_whatsapp_audit_log_product_created")
        batch_op.drop_index("ix_whatsapp_audit_log_action_created")
        batch_op.drop_index(batch_op.f("ix_whatsapp_audit_log_action"))
    op.drop_table("whatsapp_audit_log")

    with op.batch_alter_table("whatsapp_delivery_events", schema=None) as batch_op:
        batch_op.drop_index("ix_whatsapp_delivery_events_message_status_at")
        batch_op.drop_index(batch_op.f("ix_whatsapp_delivery_events_provider_message_id"))
        batch_op.drop_index(batch_op.f("ix_whatsapp_delivery_events_dedupe_key"))
    op.drop_table("whatsapp_delivery_events")

    with op.batch_alter_table("whatsapp_routing_rules", schema=None) as batch_op:
        batch_op.drop_index("ix_whatsapp_routing_product_active")
    op.drop_table("whatsapp_routing_rules")

    with op.batch_alter_table("whatsapp_messages", schema=None) as batch_op:
        batch_op.drop_index("ix_whatsapp_messages_account_created")
        batch_op.drop_index("ix_whatsapp_messages_product_created")
        batch_op.drop_index("ix_whatsapp_messages_conversation_created")
        batch_op.drop_index("ix_whatsapp_messages_status_next_attempt")
        batch_op.drop_index(batch_op.f("ix_whatsapp_messages_campaign_id"))
        batch_op.drop_index(batch_op.f("ix_whatsapp_messages_next_attempt_at"))
        batch_op.drop_index(batch_op.f("ix_whatsapp_messages_status"))
        batch_op.drop_index(batch_op.f("ix_whatsapp_messages_to_phone_e164"))
        batch_op.drop_index(batch_op.f("ix_whatsapp_messages_intent"))
        batch_op.drop_index(batch_op.f("ix_whatsapp_messages_idempotency_key"))
        batch_op.drop_index(batch_op.f("ix_whatsapp_messages_provider_message_id"))
        batch_op.drop_index(batch_op.f("ix_whatsapp_messages_message_uid"))
    op.drop_table("whatsapp_messages")

    with op.batch_alter_table("whatsapp_conversations", schema=None) as batch_op:
        batch_op.drop_index("ix_whatsapp_conversations_account_state_inbound")
        batch_op.drop_index(batch_op.f("ix_whatsapp_conversations_service_window_expires_at"))
        batch_op.drop_index(batch_op.f("ix_whatsapp_conversations_last_inbound_at"))
        batch_op.drop_index(batch_op.f("ix_whatsapp_conversations_phone_e164"))
    op.drop_table("whatsapp_conversations")

    with op.batch_alter_table("whatsapp_templates", schema=None) as batch_op:
        batch_op.drop_index("ix_whatsapp_templates_product_intent")
        batch_op.drop_index("ix_whatsapp_templates_account_status")
        batch_op.drop_index(batch_op.f("ix_whatsapp_templates_status"))
        batch_op.drop_index(batch_op.f("ix_whatsapp_templates_intent"))
    op.drop_table("whatsapp_templates")

    with op.batch_alter_table("whatsapp_products", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_whatsapp_products_is_enabled"))
        batch_op.drop_index(batch_op.f("ix_whatsapp_products_slug"))
    op.drop_table("whatsapp_products")

    with op.batch_alter_table("whatsapp_accounts", schema=None) as batch_op:
        batch_op.drop_index("uq_whatsapp_accounts_active_purpose")
        batch_op.drop_index(batch_op.f("ix_whatsapp_accounts_is_active"))
        batch_op.drop_index(batch_op.f("ix_whatsapp_accounts_purpose"))
        batch_op.drop_index(batch_op.f("ix_whatsapp_accounts_slug"))
    op.drop_table("whatsapp_accounts")
