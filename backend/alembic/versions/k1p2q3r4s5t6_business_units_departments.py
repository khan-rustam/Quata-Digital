"""business_units_and_enterprise_departments

Revision ID: k1p2q3r4s5t6
Revises: j0o1p2q3r4s5
Create Date: 2026-07-09 13:00:00.000000

HRMS slice 1F: adds the ``business_units`` table and enterprise fields on
``departments`` (business unit, assistant head, objectives, KPIs, budget,
max headcount, office location). All additive + nullable.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "k1p2q3r4s5t6"
down_revision: Union[str, None] = "j0o1p2q3r4s5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "business_units",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_business_units_slug", "business_units", ["slug"], unique=True)

    with op.batch_alter_table("departments", schema=None) as batch_op:
        batch_op.add_column(sa.Column("business_unit_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("assistant_head_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("objectives", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("kpis", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("budget", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("max_headcount", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("office_location", sa.String(length=200), nullable=True))
        batch_op.create_foreign_key(
            "fk_departments_business_unit_id", "business_units",
            ["business_unit_id"], ["id"], ondelete="SET NULL",
        )
        batch_op.create_foreign_key(
            "fk_dept_assistant_head", "users", ["assistant_head_id"], ["id"], use_alter=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("departments", schema=None) as batch_op:
        batch_op.drop_constraint("fk_dept_assistant_head", type_="foreignkey")
        batch_op.drop_constraint("fk_departments_business_unit_id", type_="foreignkey")
        batch_op.drop_column("office_location")
        batch_op.drop_column("max_headcount")
        batch_op.drop_column("budget")
        batch_op.drop_column("kpis")
        batch_op.drop_column("objectives")
        batch_op.drop_column("assistant_head_id")
        batch_op.drop_column("business_unit_id")
    op.drop_index("ix_business_units_slug", table_name="business_units")
    op.drop_table("business_units")
