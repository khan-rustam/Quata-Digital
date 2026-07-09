"""Per-employee HR metric computations, shared by the admin staff endpoints
and the employee self-service portal so both return identical shapes."""
from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import AttendanceLog, LeaveRequest, User


def leave_balance(db: Session, u: User) -> dict:
    """Annual leave balance + this-year usage by type, from approved requests."""
    year = datetime.now(timezone.utc).year
    approved = (
        db.query(LeaveRequest)
        .filter(LeaveRequest.user_id == u.id, LeaveRequest.status == "approved")
        .all()
    )
    by_type: dict[str, int] = {}
    for lr in approved:
        if lr.start_date and lr.start_date.year == year:
            by_type[lr.leave_type] = by_type.get(lr.leave_type, 0) + (lr.days or 0)
    entitlement = u.annual_leave_entitlement or 0
    annual_used = by_type.get("annual", 0)
    pending = (
        db.query(func.count(LeaveRequest.id))
        .filter(LeaveRequest.user_id == u.id, LeaveRequest.status == "pending")
        .scalar()
        or 0
    )
    return {
        "year": year,
        "annual_entitlement": entitlement,
        "annual_used": annual_used,
        "annual_remaining": entitlement - annual_used,
        "pending": pending,
        "by_type": [{"leave_type": k, "days": v} for k, v in sorted(by_type.items(), key=lambda x: -x[1])],
    }


def attendance_summary(db: Session, u: User) -> dict:
    """This-month attendance rollup: status counts, days logged, hours worked,
    average check-in time, and the most recent entries."""
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    logs = (
        db.query(AttendanceLog)
        .filter(AttendanceLog.user_id == u.id)
        .order_by(AttendanceLog.check_in_at.desc().nulls_last(), AttendanceLog.created_at.desc())
        .limit(100)
        .all()
    )
    counts = {"present": 0, "late": 0, "absent": 0, "on_leave": 0}
    worked_seconds = 0
    days_logged = 0
    checkin_minutes: list[int] = []
    recent = []
    for a in logs:
        eff = a.check_in_at or a.created_at
        # SQLite returns naive datetimes; treat any naive value as UTC so it
        # compares against the tz-aware month boundary.
        if eff is not None and eff.tzinfo is None:
            eff = eff.replace(tzinfo=timezone.utc)
        if eff and eff >= month_start:
            counts[a.status] = counts.get(a.status, 0) + 1
            if a.check_in_at:
                days_logged += 1
                checkin_minutes.append(a.check_in_at.hour * 60 + a.check_in_at.minute)
                if a.check_out_at:
                    worked_seconds += max(0, (a.check_out_at - a.check_in_at).total_seconds())
        if len(recent) < 8:
            hours = None
            if a.check_in_at and a.check_out_at:
                hours = round(max(0, (a.check_out_at - a.check_in_at).total_seconds()) / 3600, 1)
            recent.append(
                {
                    "date": (eff.date().isoformat() if eff else None),
                    "check_in": a.check_in_at,
                    "check_out": a.check_out_at,
                    "status": a.status,
                    "hours": hours,
                }
            )
    avg_check_in = None
    if checkin_minutes:
        avg = round(sum(checkin_minutes) / len(checkin_minutes))
        avg_check_in = f"{avg // 60:02d}:{avg % 60:02d}"
    return {
        "month": now.strftime("%Y-%m"),
        "present": counts.get("present", 0),
        "late": counts.get("late", 0),
        "absent": counts.get("absent", 0),
        "on_leave": counts.get("on_leave", 0),
        "days_logged": days_logged,
        "worked_hours": round(worked_seconds / 3600, 1),
        "avg_check_in": avg_check_in,
        "recent": recent,
    }
