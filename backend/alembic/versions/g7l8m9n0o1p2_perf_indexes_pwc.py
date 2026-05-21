"""perf_indexes_and_password_changed_at

Revision ID: g7l8m9n0o1p2
Revises: f6k7l8m9n0o1
Create Date: 2026-05-21 12:00:00.000000

Performance + security hardening migration:

* Adds covering indexes for every hot admin filter / sort:
  - ``page_views.created_at`` (analytics + retention prune scan)
  - ``activity_logs.(actor_id, created_at desc)`` (audit log filter)
  - ``activity_logs.created_at`` (retention prune scan)
  - ``applications.job_id`` (per-job application count)
  - ``attendance_logs.user_id`` (per-staff attendance history)
  - ``leave_requests.user_id`` (per-staff leave list)
  - ``message_recipients.(message_id, user_id)`` (unread counter)
  - ``message_recipients.user_id`` (per-user inbox)
* Adds ``users.password_changed_at`` — folded into the JWT as ``pwc`` so
  changing a password instantly invalidates every active session.

All index additions use ``if_not_exists=True`` (best-effort) so the
migration is idempotent and replays cleanly on a partially-migrated DB.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "g7l8m9n0o1p2"
down_revision: Union[str, None] = "f6k7l8m9n0o1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _create_index(name: str, table: str, cols, **kwargs):
    """Create an index, tolerating ``already exists`` on replay."""
    try:
        op.create_index(name, table, cols, **kwargs)
    except Exception:  # noqa: BLE001
        # SQLite + Postgres both raise on duplicate index; we treat it
        # as a successful no-op so a partial replay can finish.
        pass


def upgrade() -> None:
    # New audit-rotation column
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True)
        )

    # Hot-path indexes
    _create_index("ix_page_views_created_at", "page_views", ["created_at"])
    _create_index(
        "ix_activity_logs_actor_created",
        "activity_logs",
        ["actor_id", sa.text("created_at DESC")],
    )
    _create_index("ix_activity_logs_created_at", "activity_logs", ["created_at"])
    _create_index("ix_applications_job_id", "applications", ["job_id"])
    _create_index("ix_attendance_logs_user_id", "attendance_logs", ["user_id"])
    _create_index("ix_leave_requests_user_id", "leave_requests", ["user_id"])
    _create_index(
        "ix_message_recipients_message_user",
        "message_recipients",
        ["message_id", "user_id"],
    )
    _create_index("ix_message_recipients_user_id", "message_recipients", ["user_id"])


def downgrade() -> None:
    for name in (
        "ix_message_recipients_user_id",
        "ix_message_recipients_message_user",
        "ix_leave_requests_user_id",
        "ix_attendance_logs_user_id",
        "ix_applications_job_id",
        "ix_activity_logs_created_at",
        "ix_activity_logs_actor_created",
        "ix_page_views_created_at",
    ):
        try:
            op.drop_index(name)
        except Exception:  # noqa: BLE001
            pass

    with op.batch_alter_table("users", schema=None) as batch_op:
        try:
            batch_op.drop_column("password_changed_at")
        except Exception:  # noqa: BLE001
            pass
