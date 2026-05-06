"""media_dims_and_versioning

Revision ID: e5j6k7l8m9n0
Revises: d4i5j6k7l8m9
Create Date: 2026-05-06 03:00:00.000000

Adds image-pipeline columns to `media_assets` (width/height/optimized_url/
optimized_size) and creates the `page_content_versions` snapshot table that
backs the page editor's revert-to-version flow.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e5j6k7l8m9n0"
down_revision: Union[str, None] = "d4i5j6k7l8m9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- media_assets: image pipeline metadata ---
    with op.batch_alter_table("media_assets", schema=None) as batch_op:
        batch_op.add_column(sa.Column("width", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("height", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("optimized_url", sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column("optimized_size", sa.Integer(), nullable=True))

    # --- page_content_versions: snapshots for revert ---
    op.create_table(
        "page_content_versions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("page_slug", sa.String(length=120), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("sections", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("saved_by_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["saved_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("page_content_versions", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_page_content_versions_page_slug"),
            ["page_slug"],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("page_content_versions", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_page_content_versions_page_slug"))
    op.drop_table("page_content_versions")
    with op.batch_alter_table("media_assets", schema=None) as batch_op:
        batch_op.drop_column("optimized_size")
        batch_op.drop_column("optimized_url")
        batch_op.drop_column("height")
        batch_op.drop_column("width")
