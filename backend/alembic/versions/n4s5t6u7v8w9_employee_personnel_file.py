"""employee_personnel_file

Revision ID: n4s5t6u7v8w9
Revises: m3r4s5t6u7v8
Create Date: 2026-07-09 16:00:00.000000

HRMS 2A: complete employee personnel file — personal, employment and
professional fields on ``users``. All additive + nullable.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "n4s5t6u7v8w9"
down_revision: Union[str, None] = "m3r4s5t6u7v8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_COLUMNS = [
    ("gender", sa.String(length=20)),
    ("date_of_birth", sa.Date()),
    ("nationality", sa.String(length=80)),
    ("national_id", sa.String(length=60)),
    ("marital_status", sa.String(length=20)),
    ("blood_group", sa.String(length=8)),
    ("personal_email", sa.String(length=255)),
    ("address", sa.String(length=500)),
    ("emergency_contacts", sa.JSON()),
    ("employment_type", sa.String(length=40)),
    ("grade", sa.String(length=40)),
    ("work_location", sa.String(length=120)),
    ("manager_id", sa.Integer()),
    ("date_hired", sa.Date()),
    ("confirmation_date", sa.Date()),
    ("contract_expiry", sa.Date()),
    ("probation_status", sa.String(length=20)),
    ("education", sa.Text()),
    ("skills", sa.JSON()),
    ("languages", sa.JSON()),
    ("certifications", sa.JSON()),
    ("previous_employment", sa.Text()),
    ("portfolio_url", sa.String(length=500)),
]


def upgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        for name, coltype in _COLUMNS:
            batch_op.add_column(sa.Column(name, coltype, nullable=True))
        batch_op.create_foreign_key(
            "fk_user_manager", "users", ["manager_id"], ["id"], use_alter=True
        )


def downgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_constraint("fk_user_manager", type_="foreignkey")
        for name, _ in reversed(_COLUMNS):
            batch_op.drop_column(name)
