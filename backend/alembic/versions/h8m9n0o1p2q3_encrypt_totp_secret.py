"""encrypt_totp_secret

Revision ID: h8m9n0o1p2q3
Revises: g7l8m9n0o1p2
Create Date: 2026-07-06 00:00:00.000000

Widen ``users.totp_secret`` from 64 to 255 chars. TOTP secrets are now stored
Fernet-encrypted at rest (see ``services/security_extras.encrypt_totp_secret``);
the ciphertext is longer than the raw base32 secret. Existing plaintext rows
keep working — decryption falls back to treating the value as raw base32.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "h8m9n0o1p2q3"
down_revision: Union[str, None] = "g7l8m9n0o1p2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.alter_column(
            "totp_secret",
            existing_type=sa.String(length=64),
            type_=sa.String(length=255),
            existing_nullable=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.alter_column(
            "totp_secret",
            existing_type=sa.String(length=255),
            type_=sa.String(length=64),
            existing_nullable=True,
        )
