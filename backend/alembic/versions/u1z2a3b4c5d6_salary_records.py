"""salary_records

Revision ID: u1z2a3b4c5d6
Revises: t0y1z2a3b4c5
Create Date: 2026-07-09 20:30:00.000000

HRMS payroll prep: employee compensation structure / salary history.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "u1z2a3b4c5d6"
down_revision: Union[str, None] = "t0y1z2a3b4c5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "salary_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=True),
        sa.Column("currency", sa.String(length=8), nullable=False, server_default="XAF"),
        sa.Column("basic_salary", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("allowances", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("bonus", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("overtime", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tax", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("pension", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("insurance", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("loan_deduction", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("advance_deduction", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("payment_method", sa.String(length=40), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_salary_records_user_id", "salary_records", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_salary_records_user_id", table_name="salary_records")
    op.drop_table("salary_records")
