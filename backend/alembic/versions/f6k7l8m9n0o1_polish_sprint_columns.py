"""polish_sprint_columns

Revision ID: f6k7l8m9n0o1
Revises: e5j6k7l8m9n0
Create Date: 2026-05-06 04:00:00.000000

Adds the `is_404` flag on `page_views` so the public 404 page can mark
itself for the admin broken-paths leaderboard.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f6k7l8m9n0o1"
down_revision: Union[str, None] = "e5j6k7l8m9n0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("page_views", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "is_404",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
        batch_op.create_index(
            batch_op.f("ix_page_views_is_404"),
            ["is_404"],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("page_views", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_page_views_is_404"))
        batch_op.drop_column("is_404")
