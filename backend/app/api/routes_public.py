from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.api.deps import log_activity, get_client_ip
from app.core.config import settings
from app.core.rate_limit import limiter
from app.db.session import get_db
from app.models import (
    Application,
    BlogPost,
    ContactMessage,
    Job,
    NewsletterSubscriber,
    PageView,
    PartnerRequest,
    Product,
    User,
)
from app.schemas.common import (
    BlogPostOut,
    ContactIn,
    JobApplicationIn,
    JobOut,
    PartnerOut,
    PartnerSubmitIn,
    ProductOut,
)
from app.services.captcha import verify_captcha_or_raise
from app.services.email import (
    notify_application_received,
    notify_contact_received,
    notify_partner_received,
)

router = APIRouter(tags=["public"])


VALID_TYPES = {"business", "strategic", "investor", "service"}


@router.get("/products", response_model=List[ProductOut])
def list_products(db: Session = Depends(get_db)):
    return db.query(Product).filter(Product.is_published == True).order_by(Product.id).all()  # noqa: E712


@router.get("/products/{slug}", response_model=ProductOut)
def get_product(slug: str, db: Session = Depends(get_db)):
    p = db.query(Product).filter(Product.slug == slug).first()
    if not p or not p.is_published:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")
    return p


@router.post("/partners/{partner_type}", response_model=PartnerOut, status_code=201)
@limiter.limit(settings.RATE_LIMIT_PUBLIC_FORM)
def submit_partner(
    partner_type: str,
    payload: PartnerSubmitIn,
    request: Request,
    db: Session = Depends(get_db),
):
    if partner_type not in VALID_TYPES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown partner type")
    verify_captcha_or_raise(payload.captcha_token, get_client_ip(request))
    pr = PartnerRequest(partner_type=partner_type, payload=payload.payload, status="new")
    db.add(pr)
    db.flush()
    log_activity(
        db,
        actor=None,
        action="submit",
        resource_type="partner_request",
        resource_id=pr.id,
        request=request,
        details={"partner_type": partner_type},
    )
    db.commit()
    db.refresh(pr)
    try:
        notify_partner_received(partner_type, payload.payload)
    except Exception:  # noqa: BLE001 — best-effort
        pass
    return pr


@router.get("/jobs", response_model=List[JobOut])
def list_jobs(
    db: Session = Depends(get_db),
    department: Optional[str] = None,
):
    # Public endpoint: only ever expose published jobs (the admin surface has
    # its own /admin/jobs listing that includes drafts).
    q = db.query(Job).filter(Job.is_published == True)  # noqa: E712
    if department:
        q = q.filter(Job.department == department)
    jobs = q.order_by(Job.created_at.desc()).all()
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


@router.get("/jobs/{job_id}", response_model=JobOut)
def get_job(job_id: int, db: Session = Depends(get_db)):
    j = db.get(Job, job_id)
    if not j or not j.is_published:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    count = (
        db.query(func.count(Application.id))
        .filter(Application.job_id == job_id)
        .scalar()
        or 0
    )
    d = JobOut.model_validate(j).model_dump()
    d["applications_count"] = count
    return d


@router.post("/jobs/{job_id}/apply", status_code=201)
@limiter.limit(settings.RATE_LIMIT_PUBLIC_FORM)
def apply_to_job(
    job_id: int,
    payload: JobApplicationIn,
    request: Request,
    db: Session = Depends(get_db),
):
    job = db.get(Job, job_id)
    if not job or not job.is_published:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    verify_captcha_or_raise(payload.captcha_token, get_client_ip(request))
    from app.services.uploads import is_internal_upload_url
    if not is_internal_upload_url(payload.resume_url):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Resume must be uploaded through the application form.",
        )
    app_row = Application(
        job_id=job_id,
        full_name=payload.full_name,
        email=payload.email,
        phone=payload.phone,
        resume_url=payload.resume_url,
        cover_letter=payload.cover_letter,
        status="new",
    )
    db.add(app_row)
    db.flush()
    log_activity(
        db,
        actor=None,
        action="apply",
        resource_type="job",
        resource_id=job_id,
        request=request,
        details={"applicant_email": payload.email},
    )
    db.commit()
    try:
        notify_application_received(
            job.title,
            payload.email,
            payload.full_name,
            application_id=app_row.id,
            applicant_phone=payload.phone,
        )
    except Exception:  # noqa: BLE001
        pass
    return {"ok": True, "id": app_row.id}


@router.get("/verify/{code}")
def verify_employee(code: str, db: Session = Depends(get_db)):
    """Public employee verification (QR scan on the ID card, HRMS 2D).

    Returns minimal, non-sensitive info only — no email, phone, or internal id.
    The lookup key is the random ``verification_code``, never the employee
    number, so IDs can't be enumerated.
    """
    u = (
        db.query(User)
        .filter(User.verification_code == code, User.is_deleted == False)  # noqa: E712
        .first()
    )
    if not u or not u.employee_number:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Employee not found")
    active = bool(u.is_active) and u.status == "active"
    bu = u.department.business_unit.name if (u.department and u.department.business_unit) else None
    return {
        "verified": True,
        "full_name": u.full_name,
        "employee_number": u.employee_number,
        "job_title": u.job_title,
        "department": u.department.name if u.department else None,
        "business_unit": bu,
        "avatar_url": u.avatar_url,
        "employment_status": "Active" if active else "Inactive",
    }


@router.get("/blog", response_model=List[BlogPostOut])
def list_posts(
    db: Session = Depends(get_db),
):
    from app.schemas.common import serialize_blog_post
    # Public endpoint: only published posts (admin has /admin/blog for drafts).
    q = db.query(BlogPost).filter(BlogPost.is_published == True)  # noqa: E712
    posts = q.order_by(BlogPost.published_at.desc().nulls_last(), BlogPost.created_at.desc()).all()
    return [serialize_blog_post(p) for p in posts]


@router.get("/blog/{slug}", response_model=BlogPostOut)
def get_post(slug: str, db: Session = Depends(get_db)):
    from app.schemas.common import serialize_blog_post
    p = db.query(BlogPost).filter(BlogPost.slug == slug).first()
    if not p or not p.is_published:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Post not found")
    return serialize_blog_post(p)


@router.post("/contact", status_code=201)
@limiter.limit(settings.RATE_LIMIT_PUBLIC_FORM)
def submit_contact(payload: ContactIn, request: Request, db: Session = Depends(get_db)):
    verify_captcha_or_raise(payload.captcha_token, get_client_ip(request))
    data = payload.model_dump(exclude={"captcha_token"})
    msg = ContactMessage(**data, status="new")
    db.add(msg)
    db.flush()
    log_activity(
        db,
        actor=None,
        action="submit",
        resource_type="contact",
        resource_id=msg.id,
        request=request,
    )
    db.commit()
    try:
        notify_contact_received(payload.model_dump())
    except Exception:  # noqa: BLE001
        pass
    return {"ok": True, "id": msg.id}


@router.get("/search")
def public_search(q: str = Query(default="", min_length=1, max_length=120), db: Session = Depends(get_db)):
    """Search across published products, blog posts and jobs.

    Uses Postgres `to_tsvector @@ plainto_tsquery` for proper relevance
    ranking when the live DB is Postgres. Falls back to lowercase LIKE on
    SQLite (dev / portable mode) so the dev experience matches.
    """
    from sqlalchemy import or_, func, text

    is_postgres = db.bind is not None and db.bind.dialect.name == "postgresql"

    if is_postgres:
        # Per-table relevance with ts_rank. We hard-cap the input via Pydantic
        # bounds (max 120 chars) so building the query string is safe.
        # `plainto_tsquery` parses the user input into a query tsv, treating
        # spaces as AND. `english` is the chosen dictionary; will tighten
        # to a per-locale dictionary if/when we add proper i18n.
        prod_rank = func.ts_rank(
            func.to_tsvector(
                "english",
                func.coalesce(Product.name, "")
                + " "
                + func.coalesce(Product.tagline, "")
                + " "
                + func.coalesce(Product.description, "")
                + " "
                + func.coalesce(Product.category, ""),
            ),
            func.plainto_tsquery("english", q),
        )
        products = (
            db.query(Product)
            .filter(Product.is_published == True)  # noqa: E712
            .filter(prod_rank > 0)
            .order_by(prod_rank.desc())
            .limit(8)
            .all()
        )

        post_rank = func.ts_rank(
            func.to_tsvector(
                "english",
                func.coalesce(BlogPost.title, "")
                + " "
                + func.coalesce(BlogPost.excerpt, "")
                + " "
                + func.coalesce(BlogPost.body, ""),
            ),
            func.plainto_tsquery("english", q),
        )
        posts = (
            db.query(BlogPost)
            .filter(BlogPost.is_published == True)  # noqa: E712
            .filter(post_rank > 0)
            .order_by(post_rank.desc())
            .limit(8)
            .all()
        )

        job_rank = func.ts_rank(
            func.to_tsvector(
                "english",
                func.coalesce(Job.title, "")
                + " "
                + func.coalesce(Job.summary, "")
                + " "
                + func.coalesce(Job.description, "")
                + " "
                + func.coalesce(Job.department, "")
                + " "
                + func.coalesce(Job.location, ""),
            ),
            func.plainto_tsquery("english", q),
        )
        jobs = (
            db.query(Job)
            .filter(Job.is_published == True)  # noqa: E712
            .filter(job_rank > 0)
            .order_by(job_rank.desc())
            .limit(8)
            .all()
        )
    else:
        # SQLite (and any other non-Postgres) — case-insensitive LIKE.
        needle = f"%{q.lower()}%"
        products = (
            db.query(Product)
            .filter(Product.is_published == True)  # noqa: E712
            .filter(or_(
                func.lower(Product.name).like(needle),
                func.lower(Product.tagline).like(needle),
                func.lower(Product.description).like(needle),
                func.lower(Product.category).like(needle),
            ))
            .limit(8)
            .all()
        )
        posts = (
            db.query(BlogPost)
            .filter(BlogPost.is_published == True)  # noqa: E712
            .filter(or_(
                func.lower(BlogPost.title).like(needle),
                func.lower(BlogPost.excerpt).like(needle),
                func.lower(BlogPost.body).like(needle),
            ))
            .limit(8)
            .all()
        )
        jobs = (
            db.query(Job)
            .filter(Job.is_published == True)  # noqa: E712
            .filter(or_(
                func.lower(Job.title).like(needle),
                func.lower(Job.summary).like(needle),
                func.lower(Job.description).like(needle),
                func.lower(Job.department).like(needle),
                func.lower(Job.location).like(needle),
            ))
            .limit(8)
            .all()
        )
    return {
        "query": q,
        "engine": "postgres-fts" if is_postgres else "sqlite-like",
        "results": {
            "products": [
                {"slug": p.slug, "name": p.name, "tagline": p.tagline, "category": p.category}
                for p in products
            ],
            "posts": [
                {"slug": p.slug, "title": p.title, "excerpt": p.excerpt, "category": p.category}
                for p in posts
            ],
            "jobs": [
                {
                    "id": j.id,
                    "title": j.title,
                    "department": j.department,
                    "location": j.location,
                    "summary": j.summary,
                }
                for j in jobs
            ],
        },
        "totals": {
            "products": len(products),
            "posts": len(posts),
            "jobs": len(jobs),
        },
    }


# ----------------------------------------------------------------------------
# Newsletter
# ----------------------------------------------------------------------------

from pydantic import BaseModel, EmailStr, Field  # noqa: E402  (kept local — only used here)


class NewsletterIn(BaseModel):
    email: EmailStr
    source: Optional[str] = None
    locale: Optional[str] = None
    captcha_token: Optional[str] = None


@router.post("/newsletter/subscribe", status_code=201)
@limiter.limit(settings.RATE_LIMIT_PUBLIC_FORM)
def newsletter_subscribe(
    payload: NewsletterIn,
    request: Request,
    db: Session = Depends(get_db),
):
    verify_captcha_or_raise(payload.captcha_token, get_client_ip(request))
    email = payload.email.lower().strip()
    existing = db.query(NewsletterSubscriber).filter(NewsletterSubscriber.email == email).first()
    if existing:
        if not existing.is_active:
            existing.is_active = True
            existing.unsubscribed_at = None
            db.commit()
        return {"ok": True, "id": existing.id, "status": "already_subscribed"}
    sub = NewsletterSubscriber(
        email=email,
        source=(payload.source or "website")[:80],
        locale=(payload.locale or settings.DEFAULT_LOCALE)[:8],
        is_active=True,
    )
    db.add(sub)
    db.flush()
    log_activity(
        db,
        actor=None,
        action="subscribe",
        resource_type="newsletter",
        resource_id=sub.id,
        request=request,
        details={"source": sub.source},
    )
    db.commit()
    return {"ok": True, "id": sub.id, "status": "subscribed"}


@router.post("/newsletter/unsubscribe", status_code=200)
@limiter.limit(settings.RATE_LIMIT_PUBLIC_FORM)
def newsletter_unsubscribe(
    payload: NewsletterIn,
    request: Request,
    db: Session = Depends(get_db),
):
    email = payload.email.lower().strip()
    sub = db.query(NewsletterSubscriber).filter(NewsletterSubscriber.email == email).first()
    if not sub or not sub.is_active:
        # Idempotent — never reveal whether the email was on the list.
        return {"ok": True}
    sub.is_active = False
    sub.unsubscribed_at = datetime.now(timezone.utc)
    log_activity(
        db,
        actor=None,
        action="unsubscribe",
        resource_type="newsletter",
        resource_id=sub.id,
        request=request,
    )
    db.commit()
    return {"ok": True}


@router.get("/newsletter/unsubscribe", status_code=200)
def newsletter_unsubscribe_oneclick(
    email: str,
    token: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """One-click unsubscribe from a broadcast email.

    The token is `HMAC-SHA256(SECRET_KEY, "unsubscribe:" + email).hex()[:24]`.
    Validates the token, marks the subscriber inactive (idempotent), then
    returns a JSON confirmation that the frontend confirmation page reads.
    Always returns ok=true regardless of whether the email was on the list,
    so the URL never leaks list membership.
    """
    from app.services.newsletter_tokens import verify_unsubscribe_token

    email = email.lower().strip()
    if not verify_unsubscribe_token(email, token):
        # Don't 4xx — that would let a scanner enumerate valid emails. Return
        # a generic ok so the public link looks the same to attackers.
        return {"ok": True}

    sub = db.query(NewsletterSubscriber).filter(NewsletterSubscriber.email == email).first()
    if sub and sub.is_active:
        sub.is_active = False
        sub.unsubscribed_at = datetime.now(timezone.utc)
        log_activity(
            db,
            actor=None,
            action="unsubscribe_oneclick",
            resource_type="newsletter",
            resource_id=sub.id,
            request=request,
        )
        db.commit()
    return {"ok": True, "email": email}


class TrackPageviewIn(BaseModel):
    """Payload schema for the anonymous pageview beacon.

    Length caps + typed fields prevent a script from stuffing megabytes of
    junk into the analytics table or smuggling injection payloads through
    a free-form ``dict``.
    """

    path: str = Field(..., max_length=512)
    referrer: Optional[str] = Field(default=None, max_length=512)
    visitor_id: Optional[str] = Field(default=None, max_length=80)
    is_404: bool = False


@router.post("/track", status_code=204)
@limiter.limit("60/minute")
def track_pageview(
    payload: TrackPageviewIn,
    request: Request,
    db: Session = Depends(get_db),
):
    pv = PageView(
        path=payload.path[:255],
        referrer=(payload.referrer or "")[:500] or None,
        user_agent=(request.headers.get("user-agent") or "")[:500] or None,
        visitor_id=(payload.visitor_id or "")[:80] or None,
        ip_address=get_client_ip(request),
        is_404=payload.is_404,
    )
    db.add(pv)
    db.commit()
    return None
