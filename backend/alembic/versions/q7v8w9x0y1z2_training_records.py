"""training_records

Revision ID: q7v8w9x0y1z2
Revises: p6u7v8w9x0y1
Create Date: 2026-07-09 18:30:00.000000

HRMS 2G: employee training records.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "q7v8w9x0y1z2"
down_revision: Union[str, None] = "p6u7v8w9x0y1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "training_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("provider", sa.String(length=160), nullable=True),
        sa.Column("training_type", sa.String(length=20), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="completed"),
        sa.Column("completed_on", sa.Date(), nullable=True),
        sa.Column("expires_on", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_training_records_user_id", "training_records", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_training_records_user_id", table_name="training_records")
    op.drop_table("training_records")
