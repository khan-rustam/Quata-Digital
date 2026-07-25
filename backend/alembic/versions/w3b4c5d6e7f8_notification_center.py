"""notification_center

Tables backing the QUATA Notification Service (@QuataAlertsBot): the event
outbox/audit log, the authorised Telegram recipients, and the runtime
toggle catalogue.

Revision ID: w3b4c5d6e7f8
Revises: v2a3b4c5d6e7
Create Date: 2026-07-25 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "w3b4c5d6e7f8"
down_revision: Union[str, None] = "v2a3b4c5d6e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notification_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("event_id", sa.String(length=40), nullable=False),
        sa.Column("platform", sa.String(length=40), nullable=False),
        sa.Column("event_key", sa.String(length=100), nullable=False),
        sa.Column("category", sa.String(length=40), nullable=False),
        sa.Column("priority", sa.String(length=20), nullable=False, server_default="info"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("dedupe_key", sa.String(length=200), nullable=True),
        sa.Column("reference", sa.String(length=160), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("last_error", sa.String(length=500), nullable=True),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivery", sa.JSON(), nullable=True),
        sa.Column("suppressed_reason", sa.String(length=200), nullable=True),
        sa.Column("source_ip", sa.String(length=45), nullable=True),
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
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("notification_events", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_notification_events_event_id"), ["event_id"], unique=True)
        batch_op.create_index(batch_op.f("ix_notification_events_dedupe_key"), ["dedupe_key"], unique=True)
        batch_op.create_index(batch_op.f("ix_notification_events_platform"), ["platform"], unique=False)
        batch_op.create_index(batch_op.f("ix_notification_events_event_key"), ["event_key"], unique=False)
        batch_op.create_index(batch_op.f("ix_notification_events_category"), ["category"], unique=False)
        batch_op.create_index(batch_op.f("ix_notification_events_priority"), ["priority"], unique=False)
        batch_op.create_index(batch_op.f("ix_notification_events_status"), ["status"], unique=False)
        batch_op.create_index(batch_op.f("ix_notification_events_reference"), ["reference"], unique=False)
        batch_op.create_index(
            batch_op.f("ix_notification_events_next_attempt_at"), ["next_attempt_at"], unique=False
        )
        # The retry sweeper's hot query is
        # `WHERE status = 'pending' AND next_attempt_at <= now()`.
        batch_op.create_index(
            "ix_notification_events_status_next_attempt",
            ["status", "next_attempt_at"],
            unique=False,
        )
        # The digest counts events per platform over a rolling window.
        batch_op.create_index(
            "ix_notification_events_platform_created",
            ["platform", "created_at"],
            unique=False,
        )

    op.create_table(
        "notification_recipients",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("chat_id", sa.String(length=40), nullable=False),
        sa.Column("label", sa.String(length=120), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_group", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("min_priority", sa.String(length=20), nullable=False, server_default="info"),
        sa.Column("platforms", sa.JSON(), nullable=True),
        sa.Column("categories", sa.JSON(), nullable=True),
        sa.Column("last_ok_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(length=500), nullable=True),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
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
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("notification_recipients", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_notification_recipients_chat_id"), ["chat_id"], unique=True)
        batch_op.create_index(
            batch_op.f("ix_notification_recipients_is_active"), ["is_active"], unique=False
        )

    op.create_table(
        "notification_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=120), nullable=False),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("group", sa.String(length=40), nullable=False),
        sa.Column("label", sa.String(length=160), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("field_type", sa.String(length=20), nullable=False, server_default="toggle"),
        sa.Column("is_secret", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_by_id", sa.Integer(), nullable=True),
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
        sa.ForeignKeyConstraint(["updated_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("notification_settings", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_notification_settings_key"), ["key"], unique=True)
        batch_op.create_index(batch_op.f("ix_notification_settings_group"), ["group"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("notification_settings", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_notification_settings_group"))
        batch_op.drop_index(batch_op.f("ix_notification_settings_key"))
    op.drop_table("notification_settings")

    with op.batch_alter_table("notification_recipients", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_notification_recipients_is_active"))
        batch_op.drop_index(batch_op.f("ix_notification_recipients_chat_id"))
    op.drop_table("notification_recipients")

    with op.batch_alter_table("notification_events", schema=None) as batch_op:
        batch_op.drop_index("ix_notification_events_platform_created")
        batch_op.drop_index("ix_notification_events_status_next_attempt")
        batch_op.drop_index(batch_op.f("ix_notification_events_next_attempt_at"))
        batch_op.drop_index(batch_op.f("ix_notification_events_reference"))
        batch_op.drop_index(batch_op.f("ix_notification_events_status"))
        batch_op.drop_index(batch_op.f("ix_notification_events_priority"))
        batch_op.drop_index(batch_op.f("ix_notification_events_category"))
        batch_op.drop_index(batch_op.f("ix_notification_events_event_key"))
        batch_op.drop_index(batch_op.f("ix_notification_events_platform"))
        batch_op.drop_index(batch_op.f("ix_notification_events_dedupe_key"))
        batch_op.drop_index(batch_op.f("ix_notification_events_event_id"))
    op.drop_table("notification_events")
