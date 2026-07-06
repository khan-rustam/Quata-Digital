"""application_scheduling

Revision ID: i9n0o1p2q3r4
Revises: h8m9n0o1p2q3
Create Date: 2026-07-06 12:00:00.000000

Adds hiring-workflow scheduling to ``applications``: ``interview_at`` +
``interview_location`` (set when a candidate is shortlisted) and
``start_date`` (set when hired). These drive the automated shortlist/hire
emails and are shown on the admin careers dashboard. All nullable — existing
rows are unaffected.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "i9n0o1p2q3r4"
down_revision: Union[str, None] = "h8m9n0o1p2q3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("applications", schema=None) as batch_op:
        batch_op.add_column(sa.Column("interview_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("interview_location", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("start_date", sa.Date(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("applications", schema=None) as batch_op:
        batch_op.drop_column("start_date")
        batch_op.drop_column("interview_location")
        batch_op.drop_column("interview_at")
