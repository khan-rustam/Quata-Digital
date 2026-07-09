"""annual_leave_entitlement

Revision ID: v2a3b4c5d6e7
Revises: u1z2a3b4c5d6
Create Date: 2026-07-09 21:00:00.000000

HRMS leave upgrade: per-employee annual paid-leave entitlement (days/year).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "v2a3b4c5d6e7"
down_revision: Union[str, None] = "u1z2a3b4c5d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("annual_leave_entitlement", sa.Integer(), nullable=False, server_default="18")
        )


def downgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("annual_leave_entitlement")
