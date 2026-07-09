"""employee_exits

Revision ID: t0y1z2a3b4c5
Revises: s9x0y1z2a3b4
Create Date: 2026-07-09 20:00:00.000000

HRMS Phase 3: employee exit / offboarding records (one per employee).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "t0y1z2a3b4c5"
down_revision: Union[str, None] = "s9x0y1z2a3b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "employee_exits",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("exit_type", sa.String(length=30), nullable=False),
        sa.Column("exit_date", sa.Date(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("rehire_eligible", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("knowledge_transfer", sa.Text(), nullable=True),
        sa.Column("assets_returned", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("access_revoked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("exit_interview_done", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("final_settlement_done", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", name="uq_employee_exits_user_id"),
    )
    op.create_index("ix_employee_exits_user_id", "employee_exits", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_employee_exits_user_id", table_name="employee_exits")
    op.drop_table("employee_exits")
