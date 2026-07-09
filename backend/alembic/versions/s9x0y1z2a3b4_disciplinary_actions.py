"""disciplinary_actions

Revision ID: s9x0y1z2a3b4
Revises: r8w9x0y1z2a3
Create Date: 2026-07-09 19:30:00.000000

HRMS Phase 3: confidential disciplinary actions.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "s9x0y1z2a3b4"
down_revision: Union[str, None] = "r8w9x0y1z2a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "disciplinary_actions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("issued_by_id", sa.Integer(), nullable=True),
        sa.Column("action_type", sa.String(length=30), nullable=False),
        sa.Column("action_date", sa.Date(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("outcome", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="open"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["issued_by_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_disciplinary_actions_user_id", "disciplinary_actions", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_disciplinary_actions_user_id", table_name="disciplinary_actions")
    op.drop_table("disciplinary_actions")
