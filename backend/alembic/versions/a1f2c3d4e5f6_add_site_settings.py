"""add_site_settings

Revision ID: a1f2c3d4e5f6
Revises: df03f53e48ce
Create Date: 2026-05-06 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1f2c3d4e5f6"
down_revision: Union[str, None] = "df03f53e48ce"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "site_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=120), nullable=False),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("group", sa.String(length=40), nullable=False),
        sa.Column("label", sa.String(length=160), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("field_type", sa.String(length=20), nullable=False, server_default="text"),
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
    with op.batch_alter_table("site_settings", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_site_settings_key"), ["key"], unique=True)
        batch_op.create_index(batch_op.f("ix_site_settings_group"), ["group"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("site_settings", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_site_settings_group"))
        batch_op.drop_index(batch_op.f("ix_site_settings_key"))
    op.drop_table("site_settings")
