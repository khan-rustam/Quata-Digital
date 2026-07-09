"""applicant_collaboration

Revision ID: j0o1p2q3r4s5
Revises: i9n0o1p2q3r4
Create Date: 2026-07-09 12:00:00.000000

HRMS slice 1A: applicant collaboration. Adds ``applications.assigned_hr_id``
(the HR officer who owns the applicant) and an ``application_notes`` table for
internal HR notes/comments. Additive + nullable — existing rows unaffected.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "j0o1p2q3r4s5"
down_revision: Union[str, None] = "i9n0o1p2q3r4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("applications", schema=None) as batch_op:
        batch_op.add_column(sa.Column("assigned_hr_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_applications_assigned_hr_id_users",
            "users",
            ["assigned_hr_id"],
            ["id"],
            ondelete="SET NULL",
        )

    op.create_table(
        "application_notes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("application_id", sa.Integer(), nullable=False),
        sa.Column("author_id", sa.Integer(), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_application_notes_application_id", "application_notes", ["application_id"])


def downgrade() -> None:
    op.drop_index("ix_application_notes_application_id", table_name="application_notes")
    op.drop_table("application_notes")
    with op.batch_alter_table("applications", schema=None) as batch_op:
        batch_op.drop_constraint("fk_applications_assigned_hr_id_users", type_="foreignkey")
        batch_op.drop_column("assigned_hr_id")
