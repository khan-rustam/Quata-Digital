"""assets

Revision ID: r8w9x0y1z2a3
Revises: q7v8w9x0y1z2
Create Date: 2026-07-09 19:00:00.000000

HRMS 2G: company assets assigned to employees.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "r8w9x0y1z2a3"
down_revision: Union[str, None] = "q7v8w9x0y1z2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "assets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("asset_type", sa.String(length=30), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("serial", sa.String(length=120), nullable=True),
        sa.Column("condition", sa.String(length=40), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="assigned"),
        sa.Column("assigned_on", sa.Date(), nullable=True),
        sa.Column("returned_on", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_assets_user_id", "assets", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_assets_user_id", table_name="assets")
    op.drop_table("assets")
