"""application_ai_analysis

Revision ID: o5t6u7v8w9x0
Revises: n4s5t6u7v8w9
Create Date: 2026-07-09 17:00:00.000000

HRMS 1E: AI talent-intelligence results on ``applications`` — ai_score,
ai_analysis (JSON), ai_analyzed_at. Additive + nullable.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "o5t6u7v8w9x0"
down_revision: Union[str, None] = "n4s5t6u7v8w9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("applications", schema=None) as batch_op:
        batch_op.add_column(sa.Column("ai_score", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("ai_analysis", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("ai_analyzed_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("applications", schema=None) as batch_op:
        batch_op.drop_column("ai_analyzed_at")
        batch_op.drop_column("ai_analysis")
        batch_op.drop_column("ai_score")
