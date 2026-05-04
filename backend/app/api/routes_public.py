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
    if not p:
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
    published: Optional[bool] = Query(default=True),
    department: Optional[str] = None,
):
    q = db.query(Job)
    if published is True:
        q = q.filter(Job.is_published == True)  # noqa: E712
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
    if not j:
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
    if not job:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    verify_captcha_or_raise(payload.captcha_token, get_client_ip(request))
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
        notify_application_received(job.title, payload.email, payload.full_name)
    except Exception:  # noqa: BLE001
        pass
    return {"ok": True, "id": app_row.id}


@router.get("/blog", response_model=List[BlogPostOut])
def list_posts(
    db: Session = Depends(get_db),
    published: Optional[bool] = Query(default=True),
):
    from app.schemas.common import serialize_blog_post
    q = db.query(BlogPost)
    if published is True:
        q = q.filter(BlogPost.is_published == True)  # noqa: E712
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
    """Search across published products, blog posts and jobs."""
    from sqlalchemy import or_, func
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

from pydantic import BaseModel, EmailStr  # noqa: E402  (kept local — only used here)


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


@router.post("/track", status_code=204)
def track_pageview(
    payload: dict,
    request: Request,
    db: Session = Depends(get_db),
):
    pv = PageView(
        path=str(payload.get("path", ""))[:255],
        referrer=str(payload.get("referrer", ""))[:500] or None,
        user_agent=request.headers.get("user-agent"),
        visitor_id=str(payload.get("visitor_id", ""))[:80] or None,
        ip_address=get_client_ip(request),
    )
    db.add(pv)
    db.commit()
    return None
