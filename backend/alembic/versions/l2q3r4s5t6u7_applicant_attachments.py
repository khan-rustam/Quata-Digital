"""applicant_attachments

Revision ID: l2q3r4s5t6u7
Revises: k1p2q3r4s5t6
Create Date: 2026-07-09 14:00:00.000000

HRMS 1B: private document attachments on applicants (offer letters,
assessments, reference checks). Served only via the authenticated admin
endpoint, like resumes.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "l2q3r4s5t6u7"
down_revision: Union[str, None] = "k1p2q3r4s5t6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "application_attachments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("application_id", sa.Integer(), nullable=False),
        sa.Column("uploaded_by_id", sa.Integer(), nullable=True),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("url", sa.String(length=500), nullable=False),
        sa.Column("content_type", sa.String(length=120), nullable=True),
        sa.Column("size", sa.Integer(), nullable=True),
        sa.Column("label", sa.String(length=200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["uploaded_by_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_application_attachments_application_id", "application_attachments", ["application_id"])


def downgrade() -> None:
    op.drop_index("ix_application_attachments_application_id", table_name="application_attachments")
    op.drop_table("application_attachments")
