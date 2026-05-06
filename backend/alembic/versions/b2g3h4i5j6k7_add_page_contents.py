"""add_page_contents

Revision ID: b2g3h4i5j6k7
Revises: a1f2c3d4e5f6
Create Date: 2026-05-06 00:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b2g3h4i5j6k7"
down_revision: Union[str, None] = "a1f2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "page_contents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("page_type", sa.String(length=40), nullable=False, server_default="general"),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("sections", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("is_published", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
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
    with op.batch_alter_table("page_contents", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_page_contents_slug"), ["slug"], unique=True)
        batch_op.create_index(batch_op.f("ix_page_contents_page_type"), ["page_type"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("page_contents", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_page_contents_page_type"))
        batch_op.drop_index(batch_op.f("ix_page_contents_slug"))
    op.drop_table("page_contents")
