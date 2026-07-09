from datetime import date, datetime, timedelta, timezone
from io import StringIO
import csv
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import log_activity, require_permission
from app.db.session import get_db
from app.models import (
    ActivityLog,
    Application,
    AttendanceLog,
    BlogPost,
    BusinessUnit,
    ContactMessage,
    Department,
    EmployeeExit,
    TrainingRecord,
    Device,
    Job,
    LeaveRequest,
    Message,
    MessageRecipient,
    Page,
    PageView,
    PartnerRequest,
    Product,
    Role,
    User,
)
from app.schemas.common import (
    ActivityOut,
    AnalyticsOut,
    ApplicationOut,
    AttendanceOut,
    BlogPostOut,
    DepartmentOut,
    DeviceOut,
    JobOut,
    LeaveOut,
    LeaveStatusIn,
    MessageIn,
    MessageOut,
    OverviewOut,
    PageOut,
    PartnerOut,
    PartnerStatusUpdate,
    ProductOut,
    RoleOut,
    StaffOut,
)

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/overview", response_model=OverviewOut)
def overview(
    db: Session = Depends(get_db),
    # Any admin permission grants overview access. Staff with no perms
    # would otherwise see every partner email + applicant PII.
    user: User = Depends(
        require_permission(
            "partners:manage",
            "careers:manage",
            "staff:manage",
            "analytics:view",
        )
    ),
):
    today = datetime.now(timezone.utc).date()
    totals = {
        "staff": db.query(func.count(User.id)).scalar() or 0,
        "products": db.query(func.count(Product.id)).scalar() or 0,
        "partner_requests": db.query(func.count(PartnerRequest.id)).scalar() or 0,
        "job_applications": db.query(func.count(Application.id)).scalar() or 0,
        "open_jobs": db.query(func.count(Job.id)).filter(Job.is_published == True).scalar() or 0,  # noqa: E712
        "posts": db.query(func.count(BlogPost.id)).filter(BlogPost.is_published == True).scalar() or 0,  # noqa: E712
        "unread_messages": db.query(func.count(MessageRecipient.id))
        .filter(MessageRecipient.user_id == user.id, MessageRecipient.is_read == False)  # noqa: E712
        .scalar()
        or 0,
        "pending_leave": db.query(func.count(LeaveRequest.id))
        .filter(LeaveRequest.status == "pending")
        .scalar()
        or 0,
    }
    recent_partners = (
        db.query(PartnerRequest).order_by(PartnerRequest.created_at.desc()).limit(5).all()
    )
    recent_apps = (
        db.query(Application)
        .options(selectinload(Application.job))
        .order_by(Application.created_at.desc())
        .limit(5)
        .all()
    )

    present = (
        db.query(func.count(AttendanceLog.id))
        .filter(AttendanceLog.status == "present", func.date(AttendanceLog.check_in_at) == today)
        .scalar()
        or 0
    )
    on_leave = (
        db.query(func.count(LeaveRequest.id))
        .filter(
            LeaveRequest.status == "approved",
            LeaveRequest.start_date <= today,
            LeaveRequest.end_date >= today,
        )
        .scalar()
        or 0
    )
    total_staff = totals["staff"] or 0
    absent = max(total_staff - present - on_leave, 0)

    return OverviewOut(
        totals=totals,
        recent_partners=[PartnerOut.model_validate(p) for p in recent_partners],
        recent_applications=[
            {
                "id": a.id,
                "full_name": a.full_name,
                "job_title": a.job.title if a.job else "—",
                "created_at": a.created_at,
            }
            for a in recent_apps
        ],
        attendance_today={"present": present, "absent": absent, "on_leave": on_leave},
    )


_FUNNEL_STAGES = [
    ("new", "New"),
    ("hr_review", "HR review"),
    ("shortlisted", "Shortlisted"),
    ("interview_scheduled", "Interview scheduled"),
    ("interviewed", "Interview completed"),
    ("assessment", "Assessment"),
    ("reference_check", "Reference check"),
    ("offer", "Offer"),
    ("offer_accepted", "Offer accepted"),
    ("hired", "Hired"),
    ("rejected", "Rejected"),
    ("archived", "Archived"),
]


@router.get("/hr-analytics")
def hr_analytics(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("staff:manage", "analytics:view")),
):
    """Executive HR dashboard aggregates, computed over real data only
    (employees, jobs, applicants, departments, business units, leave)."""
    today = datetime.now(timezone.utc).date()
    since_30d = datetime.now(timezone.utc) - timedelta(days=30)

    users_q = db.query(User).filter(User.is_deleted == False)  # noqa: E712
    total_employees = users_q.count()
    active_employees = users_q.filter(User.is_active == True, User.status == "active").count()  # noqa: E712
    invited = users_q.filter(User.status == "invited").count()
    suspended = users_q.filter(User.status == "suspended").count()
    new_hires_30d = users_q.filter(User.created_at >= since_30d).count()

    open_vacancies = (
        db.query(func.count(Job.id))
        .filter(Job.is_published == True, Job.is_deleted == False)  # noqa: E712
        .scalar()
        or 0
    )
    applicants = db.query(func.count(Application.id)).scalar() or 0
    on_leave_today = (
        db.query(func.count(LeaveRequest.id))
        .filter(
            LeaveRequest.status == "approved",
            LeaveRequest.start_date <= today,
            LeaveRequest.end_date >= today,
        )
        .scalar()
        or 0
    )
    pending_leave = (
        db.query(func.count(LeaveRequest.id)).filter(LeaveRequest.status == "pending").scalar() or 0
    )
    business_units_count = (
        db.query(func.count(BusinessUnit.id)).filter(BusinessUnit.is_deleted == False).scalar() or 0  # noqa: E712
    )

    departments = (
        db.query(Department).filter(Department.is_deleted == False).all()  # noqa: E712
    )
    dept_counts = dict(
        db.query(User.department_id, func.count(User.id))
        .filter(User.is_deleted == False)  # noqa: E712
        .group_by(User.department_id)
        .all()
    )
    headcount_by_department = sorted(
        [
            {
                "name": d.name,
                "count": dept_counts.get(d.id, 0),
                "max": d.max_headcount,
                "business_unit": d.business_unit.name if d.business_unit else None,
            }
            for d in departments
        ],
        key=lambda r: r["count"],
        reverse=True,
    )
    bu_map: dict[str, int] = {}
    for d in departments:
        name = d.business_unit.name if d.business_unit else "Unassigned"
        bu_map[name] = bu_map.get(name, 0) + dept_counts.get(d.id, 0)
    headcount_by_business_unit = sorted(
        [{"name": k, "count": v} for k, v in bu_map.items()],
        key=lambda r: r["count"],
        reverse=True,
    )

    stage_counts = dict(
        db.query(Application.status, func.count(Application.id))
        .group_by(Application.status)
        .all()
    )
    recruitment_funnel = [
        {"stage": s, "label": label, "count": stage_counts.get(s, 0)}
        for s, label in _FUNNEL_STAGES
        if stage_counts.get(s, 0) > 0
    ]

    # --- Workforce distributions (from 2A personnel fields) ---
    employees = users_q.all()

    gender_counts: dict[str, int] = {}
    type_counts: dict[str, int] = {}
    age_buckets = {"Under 25": 0, "25–34": 0, "35–44": 0, "45–54": 0, "55+": 0, "Unknown": 0}
    tenure_buckets = {"< 1 year": 0, "1–3 years": 0, "3–5 years": 0, "5+ years": 0, "Unknown": 0}
    for u in employees:
        g = u.gender or "Unspecified"
        gender_counts[g] = gender_counts.get(g, 0) + 1
        t = u.employment_type or "Unspecified"
        type_counts[t] = type_counts.get(t, 0) + 1
        if u.date_of_birth:
            age = today.year - u.date_of_birth.year - (
                (today.month, today.day) < (u.date_of_birth.month, u.date_of_birth.day)
            )
            key = (
                "Under 25" if age < 25 else "25–34" if age < 35 else "35–44"
                if age < 45 else "45–54" if age < 55 else "55+"
            )
            age_buckets[key] += 1
        else:
            age_buckets["Unknown"] += 1
        if u.date_hired:
            yrs = (today - u.date_hired).days / 365.25
            key = "< 1 year" if yrs < 1 else "1–3 years" if yrs < 3 else "3–5 years" if yrs < 5 else "5+ years"
            tenure_buckets[key] += 1
        else:
            tenure_buckets["Unknown"] += 1

    def _sorted_counts(d: dict[str, int]) -> list[dict]:
        return [{"name": k, "count": v} for k, v in sorted(d.items(), key=lambda x: -x[1]) if v > 0]

    return {
        "totals": {
            "employees": total_employees,
            "active_employees": active_employees,
            "invited": invited,
            "suspended": suspended,
            "new_hires_30d": new_hires_30d,
            "open_vacancies": open_vacancies,
            "applicants": applicants,
            "on_leave_today": on_leave_today,
            "pending_leave": pending_leave,
            "business_units": business_units_count,
            "departments": len(departments),
        },
        "headcount_by_department": headcount_by_department,
        "headcount_by_business_unit": headcount_by_business_unit,
        "recruitment_funnel": recruitment_funnel,
        "gender_distribution": _sorted_counts(gender_counts),
        "age_distribution": [{"name": k, "count": v} for k, v in age_buckets.items() if v > 0],
        "tenure_distribution": [{"name": k, "count": v} for k, v in tenure_buckets.items() if v > 0],
        "employment_type_distribution": _sorted_counts(type_counts),
    }


@router.get("/hr-alerts")
def hr_alerts(
    db: Session = Depends(get_db),
    within_days: int = Query(default=60, ge=1, le=365),
    user: User = Depends(require_permission("staff:manage", "analytics:view")),
):
    """Employees needing HR attention: contracts expiring (or expired) within
    ``within_days``, and staff still on probation (flagged overdue once their
    confirmation date has passed). Computed from the 2A personnel fields."""
    today = datetime.now(timezone.utc).date()
    employees = (
        db.query(User)
        .filter(User.is_deleted == False, User.is_active == True)  # noqa: E712
        .all()
    )

    contracts_expiring = []
    for u in employees:
        if u.contract_expiry:
            days_left = (u.contract_expiry - today).days
            if days_left <= within_days:
                contracts_expiring.append(
                    {
                        "id": u.id,
                        "full_name": u.full_name,
                        "employee_number": u.employee_number,
                        "department": u.department.name if u.department else None,
                        "contract_expiry": u.contract_expiry,
                        "days_left": days_left,
                        "expired": days_left < 0,
                    }
                )
    contracts_expiring.sort(key=lambda r: r["days_left"])

    on_probation = []
    for u in employees:
        if u.probation_status == "probation":
            overdue = bool(u.confirmation_date and u.confirmation_date < today)
            on_probation.append(
                {
                    "id": u.id,
                    "full_name": u.full_name,
                    "employee_number": u.employee_number,
                    "department": u.department.name if u.department else None,
                    "confirmation_date": u.confirmation_date,
                    "overdue": overdue,
                }
            )
    on_probation.sort(key=lambda r: (not r["overdue"], r["full_name"]))

    return {
        "within_days": within_days,
        "counts": {
            "contracts_expiring": len(contracts_expiring),
            "contracts_expired": sum(1 for c in contracts_expiring if c["expired"]),
            "on_probation": len(on_probation),
            "probation_overdue": sum(1 for p in on_probation if p["overdue"]),
        },
        "contracts_expiring": contracts_expiring,
        "on_probation": on_probation,
    }


def _days_to_next_birthday(dob, today):
    try:
        bday = dob.replace(year=today.year)
    except ValueError:  # 29 Feb
        return None
    if bday < today:
        try:
            bday = dob.replace(year=today.year + 1)
        except ValueError:
            return None
    return (bday - today).days


@router.get("/notifications")
def notifications(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("staff:manage", "careers:manage", "analytics:view")),
):
    """Actionable HR notifications aggregated live from existing data — new
    applicants, pending approvals, contract/probation/training expiry, birthdays
    and work anniversaries. No new tables; computed on read."""
    today = datetime.now(timezone.utc).date()
    items: list[dict] = []

    for a in (
        db.query(Application)
        .filter(Application.status == "new")
        .order_by(Application.created_at.desc())
        .limit(20)
        .all()
    ):
        items.append({
            "type": "application", "severity": "info",
            "title": f"New applicant: {a.full_name}",
            "detail": a.job.title if a.job else "",
            "link": f"/admin/careers?applicant={a.id}", "date": a.created_at.date(),
        })

    pending_leave = db.query(LeaveRequest).filter(LeaveRequest.status == "pending").count()
    if pending_leave:
        items.append({
            "type": "leave", "severity": "warn",
            "title": f"{pending_leave} leave request{'s' if pending_leave != 1 else ''} awaiting approval",
            "detail": "", "link": "/admin/leave", "date": today,
        })

    employees = db.query(User).filter(User.is_deleted == False, User.is_active == True).all()  # noqa: E712
    for u in employees:
        if u.contract_expiry:
            d = (u.contract_expiry - today).days
            if d <= 60:
                items.append({
                    "type": "contract", "severity": "serious" if d < 0 else "warn",
                    "title": f"Contract {'expired' if d < 0 else 'expiring'}: {u.full_name}",
                    "detail": f"{'was due' if d < 0 else 'due'} {u.contract_expiry.isoformat()}",
                    "link": f"/admin/staff/{u.id}", "date": u.contract_expiry,
                })
        if u.probation_status == "probation" and u.confirmation_date and u.confirmation_date < today:
            items.append({
                "type": "probation", "severity": "warn",
                "title": f"Probation overdue: {u.full_name}",
                "detail": f"confirm by {u.confirmation_date.isoformat()}",
                "link": f"/admin/staff/{u.id}", "date": u.confirmation_date,
            })
        if u.date_of_birth:
            days = _days_to_next_birthday(u.date_of_birth, today)
            if days is not None and days <= 14:
                items.append({
                    "type": "birthday", "severity": "info",
                    "title": f"Birthday {'today' if days == 0 else f'in {days}d'}: {u.full_name}",
                    "detail": "", "link": f"/admin/staff/{u.id}", "date": today,
                })
        if u.date_hired and u.date_hired.month == today.month and u.date_hired.year < today.year:
            yrs = today.year - u.date_hired.year
            items.append({
                "type": "anniversary", "severity": "info",
                "title": f"{yrs}-year work anniversary: {u.full_name}",
                "detail": "", "link": f"/admin/staff/{u.id}", "date": today,
            })

    for t in (
        db.query(TrainingRecord)
        .filter(TrainingRecord.expires_on.isnot(None), TrainingRecord.expires_on <= today + timedelta(days=30))
        .all()
    ):
        d = (t.expires_on - today).days
        items.append({
            "type": "training", "severity": "serious" if d < 0 else "warn",
            "title": f"Training {'expired' if d < 0 else 'expiring'}: {t.title}",
            "detail": t.expires_on.isoformat(), "link": f"/admin/staff/{t.user_id}", "date": t.expires_on,
        })

    order = {"serious": 0, "warn": 1, "info": 2}
    items.sort(key=lambda i: (order.get(i["severity"], 3), str(i["date"])))
    by_sev = {"serious": 0, "warn": 0, "info": 0}
    for i in items:
        by_sev[i["severity"]] = by_sev.get(i["severity"], 0) + 1
    return {"total": len(items), "by_severity": by_sev, "items": items}


# ---------- Partners ----------

@router.get("/partners")
def admin_list_partners(
    db: Session = Depends(get_db),
    partner_type: Optional[str] = None,
    status_filter: Optional[str] = Query(default=None, alias="status"),
    q: Optional[str] = Query(default=None, max_length=120, description="Search payload"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    user: User = Depends(require_permission("partners:manage")),
):
    qry = db.query(PartnerRequest)
    if partner_type:
        qry = qry.filter(PartnerRequest.partner_type == partner_type)
    if status_filter:
        qry = qry.filter(PartnerRequest.status == status_filter)
    if q:
        # SQLite-friendly LIKE on the JSON-encoded payload column (bound param)
        from sqlalchemy import cast, String as SqlString
        qry = qry.filter(cast(PartnerRequest.payload, SqlString).ilike(f"%{q}%"))
    total = qry.count()
    rows = (
        qry.order_by(PartnerRequest.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    # Paginated envelope so the admin UI can compute total pages (a bare list
    # made "Next" impossible past page 1).
    return {
        "items": [PartnerOut.model_validate(r) for r in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.patch("/partners/{partner_id}", response_model=PartnerOut)
def admin_update_partner(
    partner_id: int,
    payload: PartnerStatusUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("partners:manage")),
):
    pr = db.get(PartnerRequest, partner_id)
    if not pr:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    pr.status = payload.status
    log_activity(
        db,
        actor=user,
        action="status_change",
        resource_type="partner_request",
        resource_id=partner_id,
        request=request,
        details={"to": payload.status},
    )
    db.commit()
    db.refresh(pr)
    try:
        from app.services.email import notify_partner_status_changed
        notify_partner_status_changed(
            pr.id,
            pr.partner_type,
            pr.status,
            pr.payload.get("email") if isinstance(pr.payload, dict) else None,
        )
    except Exception:  # noqa: BLE001
        pass
    return pr


@router.get("/partners/export.csv")
def admin_export_partners(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("partners:manage")),
):
    """Stream the partner-requests CSV row-by-row.

    Earlier implementation buffered every row into memory before
    returning — past ~50k rows that's a real OOM/stall vector. We now
    use a server-side cursor (``yield_per``) and a per-row generator so
    memory stays bounded regardless of table size.
    """

    def iter_rows():
        header = StringIO()
        w = csv.writer(header)
        w.writerow(["id", "type", "status", "created_at", "payload"])
        yield header.getvalue()

        query = (
            db.query(PartnerRequest)
            .order_by(PartnerRequest.created_at.desc())
            .execution_options(stream_results=True)
            .yield_per(500)
        )
        for r in query:
            buf = StringIO()
            csv.writer(buf).writerow(
                [r.id, r.partner_type, r.status, r.created_at.isoformat(), r.payload]
            )
            yield buf.getvalue()

    return StreamingResponse(
        iter_rows(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=partner-requests.csv"},
    )


# ---------- Products ----------

@router.get("/products", response_model=List[ProductOut])
def admin_list_products(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("content:manage")),
):
    return db.query(Product).order_by(Product.id).all()


# ---------- Blog & pages ----------

@router.get("/blog", response_model=List[BlogPostOut])
def admin_list_posts(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("content:manage")),
):
    from app.schemas.common import serialize_blog_post
    posts = db.query(BlogPost).order_by(BlogPost.created_at.desc()).all()
    return [serialize_blog_post(p) for p in posts]


@router.get("/pages", response_model=List[PageOut])
def admin_list_pages(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("content:manage")),
):
    return db.query(Page).order_by(Page.title).all()


# ---------- Jobs / Applications ----------

@router.get("/jobs", response_model=List[JobOut])
def admin_list_jobs(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("careers:manage")),
):
    jobs = db.query(Job).order_by(Job.created_at.desc()).all()
    counts = dict(
        db.query(Application.job_id, func.count(Application.id))
        .group_by(Application.job_id)
        .all()
    )
    out = []
    for j in jobs:
        d = JobOut.model_validate(j).model_dump()
        d["applications_count"] = counts.get(j.id, 0)
        out.append(d)
    return out


@router.get("/applications", response_model=List[ApplicationOut])
def admin_list_apps(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("careers:manage")),
):
    rows = (
        db.query(Application)
        .options(selectinload(Application.job))  # avoid an N+1 on job_title
        .order_by(Application.created_at.desc())
        .limit(500)  # bound the public-fed table; use /applications/v2 to filter
        .all()
    )
    return [
        {
            "id": r.id,
            "full_name": r.full_name,
            "email": r.email,
            "job_title": r.job.title if r.job else "—",
            "status": r.status,
            "created_at": r.created_at,
        }
        for r in rows
    ]


# ---------- Staff / Departments / Roles ----------

@router.get("/staff", response_model=List[StaffOut])
def admin_list_staff(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("staff:manage")),
):
    rows = db.query(User).order_by(User.full_name).all()
    return [
        StaffOut(
            id=u.id,
            full_name=u.full_name,
            email=u.email,
            role=u.role.slug if u.role else "staff",
            department=u.department.name if u.department else None,
            job_title=u.job_title,
            status=u.status,
            employee_number=u.employee_number,
            employment_type=u.employment_type,
            work_location=u.work_location,
        )
        for u in rows
    ]


@router.get("/staff/export.csv")
def export_staff_csv(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("staff:manage")),
):
    """Employee directory export (CSV)."""
    rows = db.query(User).filter(User.is_deleted == False).order_by(User.full_name).all()  # noqa: E712
    buf = StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        ["employee_number", "full_name", "email", "role", "department",
         "job_title", "employment_type", "work_location", "status"]
    )
    for u in rows:
        writer.writerow([
            u.employee_number or "",
            u.full_name,
            u.email,
            u.role.slug if u.role else "",
            u.department.name if u.department else "",
            u.job_title or "",
            u.employment_type or "",
            u.work_location or "",
            u.status,
        ])
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=employees.csv"},
    )


@router.get("/alumni")
def list_alumni(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("staff:manage")),
):
    """Former employees — anyone with an exit record — with rehire eligibility."""
    rows = (
        db.query(User, EmployeeExit)
        .join(EmployeeExit, EmployeeExit.user_id == User.id)
        .order_by(EmployeeExit.exit_date.desc().nulls_last(), User.full_name)
        .all()
    )
    return [
        {
            "id": u.id,
            "full_name": u.full_name,
            "employee_number": u.employee_number,
            "department": u.department.name if u.department else None,
            "job_title": u.job_title,
            "exit_type": ex.exit_type,
            "exit_date": ex.exit_date,
            "rehire_eligible": ex.rehire_eligible,
        }
        for (u, ex) in rows
    ]


@router.get("/departments", response_model=List[DepartmentOut])
def admin_list_departments(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("staff:manage")),
):
    deps = (
        db.query(Department)
        .filter(Department.is_deleted == False)  # noqa: E712
        .order_by(Department.name)
        .all()
    )
    counts = dict(
        db.query(User.department_id, func.count(User.id))
        .group_by(User.department_id)
        .all()
    )
    return [
        DepartmentOut(
            id=d.id,
            slug=d.slug,
            name=d.name,
            description=d.description,
            head_name=d.head.full_name if d.head else None,
            head_id=d.head_id,
            assistant_head_id=d.assistant_head_id,
            staff_count=counts.get(d.id, 0),
            business_unit_id=d.business_unit_id,
            business_unit_name=d.business_unit.name if d.business_unit else None,
            objectives=d.objectives,
            kpis=d.kpis,
            budget=d.budget,
            max_headcount=d.max_headcount,
            office_location=d.office_location,
        )
        for d in deps
    ]


@router.get("/roles", response_model=List[RoleOut])
def admin_list_roles(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("rbac:manage")),
):
    roles = db.query(Role).order_by(Role.name).all()
    return [
        RoleOut(
            id=r.id,
            slug=r.slug,
            name=r.name,
            description=r.description,
            permissions=[p.permission for p in r.permissions],
        )
        for r in roles
    ]


# ---------- Messaging ----------

@router.get("/messages", response_model=List[MessageOut])
def admin_list_messages(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("staff:manage")),
):
    # Eager-load sender + recipients_status; otherwise each row in the
    # response triggers two extra queries to render the author + counters.
    msgs = (
        db.query(Message)
        .options(
            selectinload(Message.sender),
            selectinload(Message.recipients_status),
            selectinload(Message.recipient),
        )
        .order_by(Message.created_at.desc())
        .all()
    )
    out = []
    for m in msgs:
        total = len(m.recipients_status)
        read = sum(1 for r in m.recipients_status if r.is_read)
        out.append(
            MessageOut(
                id=m.id,
                subject=m.subject,
                body=m.body,
                audience=m.audience,
                message_type=m.message_type,
                department=m.department_slug,
                recipient=m.recipient.full_name if m.recipient else None,
                read_count=read,
                total_recipients=total,
                created_at=m.created_at,
                author=m.sender.full_name if m.sender else "System",
            )
        )
    return out


@router.post("/messages", response_model=MessageOut, status_code=201)
def admin_create_message(
    payload: MessageIn,
    request: Request,
    db: Session = Depends(get_db),
    # Restricting broadcast to staff:manage stops a phished editor from
    # impersonating leadership across the org.
    user: User = Depends(require_permission("staff:manage")),
):
    # Reject targeted sends with no target rather than silently delivering to
    # nobody (which previously reported success).
    if payload.audience == "department" and not payload.department_slug:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Select a department for a department message.")
    if payload.audience == "individual" and not payload.recipient_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Select a recipient for an individual message.")
    msg = Message(
        subject=payload.subject,
        body=payload.body,
        audience=payload.audience,
        message_type=payload.message_type,
        department_slug=payload.department_slug,
        recipient_id=payload.recipient_id,
        sender_id=user.id,
    )
    db.add(msg)
    db.flush()

    if payload.audience == "all":
        recipients = db.query(User).filter(User.is_active == True).all()  # noqa: E712
    elif payload.audience == "department" and payload.department_slug:
        dept = db.query(Department).filter(Department.slug == payload.department_slug).first()
        recipients = dept.members if dept else []
    elif payload.audience == "individual" and payload.recipient_id:
        target = db.get(User, payload.recipient_id)
        recipients = [target] if target else []
    else:
        recipients = []

    for r in recipients:
        if r.id == user.id:
            continue
        db.add(MessageRecipient(message_id=msg.id, user_id=r.id, is_read=False))

    recipient_ids = [r.id for r in recipients if r.id != user.id]

    log_activity(
        db,
        actor=user,
        action="send_message",
        resource_type="message",
        resource_id=msg.id,
        request=request,
        details={"audience": payload.audience, "type": payload.message_type, "recipients": len(recipient_ids)},
    )
    db.commit()
    db.refresh(msg)

    # Push to active WebSocket subscribers
    try:
        import asyncio
        from app.api.routes_ws import hub
        event = {
            "type": "message",
            "id": msg.id,
            "subject": msg.subject,
            "body": msg.body,
            "message_type": msg.message_type,
            "audience": msg.audience,
            "department_slug": msg.department_slug,
            "author": user.full_name,
            "created_at": msg.created_at.isoformat() if msg.created_at else None,
        }
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(hub.broadcast(set(recipient_ids), event))
        except RuntimeError:
            pass
    except Exception:  # noqa: BLE001
        pass

    return MessageOut(
        id=msg.id,
        subject=msg.subject,
        body=msg.body,
        audience=msg.audience,
        message_type=msg.message_type,
        department=msg.department_slug,
        recipient=msg.recipient.full_name if msg.recipient else None,
        read_count=0,
        total_recipients=len(msg.recipients_status),
        created_at=msg.created_at,
        author=user.full_name,
    )


# ---------- Leave ----------

@router.get("/leave", response_model=List[LeaveOut])
def admin_list_leave(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("staff:manage")),
):
    rows = (
        db.query(LeaveRequest)
        .options(selectinload(LeaveRequest.user))
        .order_by(LeaveRequest.created_at.desc())
        .all()
    )
    return [
        LeaveOut(
            id=l.id,
            staff_name=l.user.full_name if l.user else "—",
            leave_type=l.leave_type,
            start_date=l.start_date,
            end_date=l.end_date,
            days=l.days,
            status=l.status,
            reason=l.reason,
        )
        for l in rows
    ]


@router.patch("/leave/{leave_id}", response_model=LeaveOut)
def admin_decide_leave(
    leave_id: int,
    payload: LeaveStatusIn,
    request: Request,
    db: Session = Depends(get_db),
    # Without this, any logged-in staff member could approve their own leave.
    user: User = Depends(require_permission("staff:manage")),
):
    lr = db.get(LeaveRequest, leave_id)
    if not lr:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Leave not found")
    lr.status = payload.status
    lr.decided_by_id = user.id
    log_activity(
        db,
        actor=user,
        action="decide_leave",
        resource_type="leave_request",
        resource_id=leave_id,
        request=request,
        details={"to": payload.status},
    )
    db.commit()
    db.refresh(lr)
    try:
        from app.services.email import notify_leave_decided
        if lr.user and lr.user.email:
            notify_leave_decided(
                lr.user.email,
                lr.user.full_name,
                lr.status,
                lr.start_date.isoformat(),
                lr.end_date.isoformat(),
            )
    except Exception:  # noqa: BLE001
        pass
    return LeaveOut(
        id=lr.id,
        staff_name=lr.user.full_name if lr.user else "—",
        leave_type=lr.leave_type,
        start_date=lr.start_date,
        end_date=lr.end_date,
        days=lr.days,
        status=lr.status,
        reason=lr.reason,
    )


# ---------- Attendance ----------

@router.get("/attendance", response_model=List[AttendanceOut])
def admin_list_attendance(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("staff:manage")),
    on: Optional[date] = None,
):
    target = on or datetime.now(timezone.utc).date()
    rows = (
        db.query(AttendanceLog)
        .options(
            selectinload(AttendanceLog.user),
            selectinload(AttendanceLog.device),
        )
        .filter(func.date(AttendanceLog.check_in_at) == target)
        .order_by(AttendanceLog.check_in_at.desc())
        .all()
    )
    return [
        AttendanceOut(
            id=a.id,
            staff_name=a.user.full_name if a.user else "—",
            check_in_at=a.check_in_at,
            check_out_at=a.check_out_at,
            source=a.source,
            device_name=a.device.name if a.device else None,
            status=a.status,
        )
        for a in rows
    ]


# ---------- Devices ----------

@router.get("/devices", response_model=List[DeviceOut])
def admin_list_devices(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("devices:manage")),
):
    return db.query(Device).order_by(Device.name).all()


# ---------- Activity ----------

@router.get("/activity", response_model=List[ActivityOut])
def admin_list_activity(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("activity:view")),
):
    rows = (
        db.query(ActivityLog)
        .options(selectinload(ActivityLog.actor))
        .order_by(ActivityLog.created_at.desc())
        .limit(200)
        .all()
    )
    return [
        ActivityOut(
            id=r.id,
            actor_name=r.actor.full_name if r.actor else "Public",
            action=r.action,
            resource_type=r.resource_type,
            resource_id=r.resource_id,
            ip_address=r.ip_address,
            details=r.details or {},
            created_at=r.created_at,
        )
        for r in rows
    ]


# ---------- Analytics ----------

@router.get("/analytics", response_model=AnalyticsOut)
def admin_analytics(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("analytics:view")),
):
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    visits = db.query(func.count(PageView.id)).filter(PageView.created_at >= week_ago).scalar() or 0
    uniques = (
        db.query(func.count(func.distinct(PageView.visitor_id)))
        .filter(PageView.created_at >= week_ago, PageView.visitor_id.isnot(None))
        .scalar()
        or 0
    )
    partners = (
        db.query(func.count(PartnerRequest.id))
        .filter(PartnerRequest.created_at >= week_ago)
        .scalar()
        or 0
    )
    apps_ = (
        db.query(func.count(Application.id))
        .filter(Application.created_at >= week_ago)
        .scalar()
        or 0
    )
    contacts = (
        db.query(func.count(ContactMessage.id))
        .filter(ContactMessage.created_at >= week_ago)
        .scalar()
        or 0
    )
    forms = partners + apps_ + contacts

    top_pages = (
        db.query(PageView.path, func.count(PageView.id).label("c"))
        .filter(PageView.created_at >= week_ago)
        .group_by(PageView.path)
        .order_by(func.count(PageView.id).desc())
        .limit(8)
        .all()
    )

    funnel = (
        db.query(PartnerRequest.partner_type, func.count(PartnerRequest.id))
        .group_by(PartnerRequest.partner_type)
        .all()
    )

    return AnalyticsOut(
        visits_7d=visits,
        unique_visitors_7d=uniques,
        form_submissions_7d=forms,
        partner_requests_7d=partners,
        job_applications_7d=apps_,
        contact_messages_7d=contacts,
        top_pages=[{"path": p[0], "views": p[1]} for p in top_pages],
        partner_funnel=[{"type": f[0], "count": f[1]} for f in funnel],
    )


# ---------- Contact messages ----------

@router.get("/contact")
def admin_list_contact(
    db: Session = Depends(get_db),
    # Contact submissions contain PII (name/email/phone); restrict to staff
    # who already handle partner inquiries.
    user: User = Depends(require_permission("partners:manage")),
):
    rows = db.query(ContactMessage).order_by(ContactMessage.created_at.desc()).limit(200).all()
    return [
        {
            "id": r.id,
            "name": r.name,
            "email": r.email,
            "company": r.company,
            "reason": r.reason,
            "message": r.message,
            "status": r.status,
            "created_at": r.created_at,
        }
        for r in rows
    ]
