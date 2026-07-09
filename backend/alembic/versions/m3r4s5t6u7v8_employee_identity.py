"""employee_identity

Revision ID: m3r4s5t6u7v8
Revises: l2q3r4s5t6u7
Create Date: 2026-07-09 15:00:00.000000

HRMS 2B: employee identity — adds ``users.employee_number`` (unique, immutable
QDE-YYYY-NNNNNN) and ``users.verification_code`` (random token backing the
public QR verification URL). Both nullable + additive.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "m3r4s5t6u7v8"
down_revision: Union[str, None] = "l2q3r4s5t6u7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("employee_number", sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column("verification_code", sa.String(length=32), nullable=True))
        batch_op.create_unique_constraint("uq_users_employee_number", ["employee_number"])
        batch_op.create_unique_constraint("uq_users_verification_code", ["verification_code"])
        batch_op.create_index("ix_users_verification_code", ["verification_code"])


def downgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_index("ix_users_verification_code")
        batch_op.drop_constraint("uq_users_verification_code", type_="unique")
        batch_op.drop_constraint("uq_users_employee_number", type_="unique")
        batch_op.drop_column("verification_code")
        batch_op.drop_column("employee_number")
