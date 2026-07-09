"""Employee identity: employee-number + verification-code generation (HRMS 2B).

Employee numbers are unique, immutable once set, and never reused. Format
``QDE-YYYY-NNNNNN`` with a global running 6-digit sequence.
"""
from __future__ import annotations

import secrets
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import User


def _next_sequence(db: Session) -> int:
    """Highest existing employee-number sequence + 1 (global running counter)."""
    rows = db.query(User.employee_number).filter(User.employee_number.isnot(None)).all()
    max_seq = 0
    for (num,) in rows:
        try:
            max_seq = max(max_seq, int(str(num).rsplit("-", 1)[-1]))
        except (ValueError, TypeError):
            continue
    return max_seq + 1


def generate_employee_number(db: Session) -> str:
    year = datetime.now(timezone.utc).year
    return f"QDE-{year}-{_next_sequence(db):06d}"


def generate_verification_code() -> str:
    # ~22 url-safe chars, well under the 32-char column.
    return secrets.token_urlsafe(16)


def ensure_employee_identity(db: Session, user: User) -> bool:
    """Assign an employee number + verification code if the user lacks them.

    Returns True if anything was assigned. Flushes so a subsequent call in the
    same transaction (e.g. a seed backfill loop) sees the new number and keeps
    the sequence monotonic. Never overwrites an existing employee number.
    """
    changed = False
    if not user.employee_number:
        user.employee_number = generate_employee_number(db)
        changed = True
    if not user.verification_code:
        user.verification_code = generate_verification_code()
        changed = True
    if changed:
        db.flush()
    return changed
