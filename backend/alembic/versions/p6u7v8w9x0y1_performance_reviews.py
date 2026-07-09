"""performance_reviews

Revision ID: p6u7v8w9x0y1
Revises: o5t6u7v8w9x0
Create Date: 2026-07-09 18:00:00.000000

HRMS 2G: employee performance reviews.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "p6u7v8w9x0y1"
down_revision: Union[str, None] = "o5t6u7v8w9x0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "performance_reviews",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("reviewer_id", sa.Integer(), nullable=True),
        sa.Column("period", sa.String(length=40), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=True),
        sa.Column("strengths", sa.Text(), nullable=True),
        sa.Column("improvements", sa.Text(), nullable=True),
        sa.Column("goals", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="submitted"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewer_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_performance_reviews_user_id", "performance_reviews", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_performance_reviews_user_id", table_name="performance_reviews")
    op.drop_table("performance_reviews")
