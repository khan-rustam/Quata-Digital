"""CMS marketing-pages API.

- Admin endpoints (require `content:manage`):
    GET    /admin/cms/pages                       List all marketing pages
    GET    /admin/cms/pages/{slug}                Read one (sections included)
    PUT    /admin/cms/pages/{slug}                Replace metadata + sections (bulk save)
    POST   /admin/cms/pages/{slug}/publish        Publish (sets published_at)
    POST   /admin/cms/pages/{slug}/unpublish      Unpublish
    GET    /admin/cms/pages-section-catalogue     Section type catalogue (for the admin "add" picker)

- Public:
    GET    /pages/{slug}                      Returns published sections (or 404)

The legacy `Page` model + its admin endpoints in routes_admin.py /
routes_admin_crud.py are NOT removed — they back the simple inline-content
admin that's been shipping. New content flows through this router.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, log_activity, require_permission
from app.db.session import get_db
from app.models import PageContent, PageContentVersion, User


# Per-page version retention: every save snapshots the previous state.
# Older snapshots are pruned beyond this count, keeping the table small
# without sacrificing the recent-revert window the boss actually uses.
MAX_VERSIONS_PER_PAGE = 10
from app.schemas.page_sections import (
    PAGE_TYPE_ALLOWED_SECTIONS,
    SECTION_TYPES,
    assert_allowed_for_page_type,
    validate_sections,
)


router = APIRouter(tags=["pages"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class PageSummary(BaseModel):
    slug: str
    title: str
    page_type: str
    description: Optional[str]
    is_published: bool
    section_count: int
    updated_at: datetime
    updated_by: Optional[str]


class PageDetail(BaseModel):
    slug: str
    title: str
    page_type: str
    description: Optional[str]
    is_published: bool
    published_at: Optional[datetime]
    sections: list[dict]
    updated_at: datetime
    created_at: datetime
    updated_by: Optional[str]


class PagePut(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    sections: Optional[list[dict]] = None


# ---------------------------------------------------------------------------
# Public read
# ---------------------------------------------------------------------------

@router.get("/cms/pages/{slug:path}")
def public_get_page(slug: str, db: Session = Depends(get_db)):
    """Return a published page's sections, or 404. Used by the marketing
    frontend to render dynamic pages. Slug is path-encoded so we can match
    `ecosystem/quatapay`, `partners/business`, etc."""
    page = db.query(PageContent).filter(PageContent.slug == slug).first()
    if not page or not page.is_published:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Page not found")
    return {
        "slug": page.slug,
        "title": page.title,
        "description": page.description,
        "sections": [s for s in (page.sections or []) if s.get("visible", True)],
        "published_at": page.published_at,
        "updated_at": page.updated_at,
    }


# ---------------------------------------------------------------------------
# Admin
# ---------------------------------------------------------------------------

@router.get("/admin/cms/section-catalogue")
def admin_section_catalogue(
    user: User = Depends(require_permission("content:manage")),
):
    return {
        "types": SECTION_TYPES,
        "allowed_per_page_type": {
            k: sorted(v) for k, v in PAGE_TYPE_ALLOWED_SECTIONS.items()
        },
    }


@router.get("/admin/cms/pages")
def admin_list_pages(
    page_type: Optional[str] = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("content:manage")),
):
    q = db.query(PageContent)
    if page_type:
        q = q.filter(PageContent.page_type == page_type)
    rows = q.order_by(PageContent.page_type, PageContent.title).all()
    return {
        "items": [
            PageSummary(
                slug=r.slug,
                title=r.title,
                page_type=r.page_type,
                description=r.description,
                is_published=r.is_published,
                section_count=len(r.sections or []),
                updated_at=r.updated_at,
                updated_by=r.updated_by.full_name if r.updated_by else None,
            )
            for r in rows
        ],
        "page_types": sorted({r.page_type for r in rows}),
    }


@router.get("/admin/cms/pages/{slug:path}")
def admin_get_page(
    slug: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("content:manage")),
):
    page = db.query(PageContent).filter(PageContent.slug == slug).first()
    if not page:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Page not found")
    return PageDetail(
        slug=page.slug,
        title=page.title,
        page_type=page.page_type,
        description=page.description,
        is_published=page.is_published,
        published_at=page.published_at,
        sections=page.sections or [],
        updated_at=page.updated_at,
        created_at=page.created_at,
        updated_by=page.updated_by.full_name if page.updated_by else None,
    )


def _snapshot_and_prune(db: Session, *, page: PageContent, saved_by_id: int | None) -> None:
    """Create a PageContentVersion row for the page's CURRENT state, then
    delete oldest versions beyond MAX_VERSIONS_PER_PAGE so the table stays
    bounded. Called BEFORE the new payload is applied to the page row."""
    snap = PageContentVersion(
        page_slug=page.slug,
        title=page.title,
        description=page.description,
        sections=list(page.sections or []),
        saved_by_id=saved_by_id,
        created_at=datetime.now(timezone.utc),
    )
    db.add(snap)
    db.flush()
    # Prune. Keep the N most recent for this slug; delete the rest.
    keep_ids = {
        r.id
        for r in db.query(PageContentVersion.id)
        .filter(PageContentVersion.page_slug == page.slug)
        .order_by(PageContentVersion.created_at.desc())
        .limit(MAX_VERSIONS_PER_PAGE)
        .all()
    }
    if keep_ids:
        db.query(PageContentVersion).filter(
            PageContentVersion.page_slug == page.slug,
            PageContentVersion.id.notin_(keep_ids),
        ).delete(synchronize_session=False)


@router.put("/admin/cms/pages/{slug:path}")
def admin_update_page(
    slug: str,
    payload: PagePut,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("content:manage")),
):
    page = db.query(PageContent).filter(PageContent.slug == slug).first()
    if not page:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Page not found")

    # Snapshot the current state before mutating. If the payload is a no-op
    # we still snapshot — this is rare (the admin only PUTs on Save) and
    # the cost is bounded by MAX_VERSIONS_PER_PAGE.
    _snapshot_and_prune(db, page=page, saved_by_id=user.id)

    if payload.title is not None:
        page.title = payload.title
    if payload.description is not None:
        page.description = payload.description
    if payload.sections is not None:
        try:
            validated = validate_sections(payload.sections)
            assert_allowed_for_page_type(page.page_type, validated)
        except ValidationError as exc:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"Section validation failed: {exc.errors()}",
            ) from exc
        except ValueError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
        page.sections = validated
        # Sync media-library used_on. Best-effort — never fails the save.
        try:
            from app.services.media_usage import (
                extract_media_urls_from_sections,
                update_used_on_for_page,
            )

            urls = extract_media_urls_from_sections(validated)
            update_used_on_for_page(db, page_slug=page.slug, section_urls=urls)
        except Exception:  # noqa: BLE001
            pass

    page.updated_by_id = user.id
    log_activity(
        db,
        actor=user,
        action="update_page",
        resource_type="page_content",
        resource_id=page.slug,
        request=request,
        details={
            "fields": [
                k
                for k, v in payload.model_dump(exclude_unset=True).items()
                if v is not None
            ],
            "section_count": len(page.sections or []),
        },
    )
    db.commit()
    db.refresh(page)
    return PageDetail(
        slug=page.slug,
        title=page.title,
        page_type=page.page_type,
        description=page.description,
        is_published=page.is_published,
        published_at=page.published_at,
        sections=page.sections or [],
        updated_at=page.updated_at,
        created_at=page.created_at,
        updated_by=page.updated_by.full_name if page.updated_by else None,
    )


@router.post("/admin/cms/pages/{slug:path}/publish")
def admin_publish_page(
    slug: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("content:manage")),
):
    page = db.query(PageContent).filter(PageContent.slug == slug).first()
    if not page:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Page not found")
    page.is_published = True
    page.published_at = datetime.now(timezone.utc)
    page.updated_by_id = user.id
    log_activity(
        db,
        actor=user,
        action="publish_page",
        resource_type="page_content",
        resource_id=page.slug,
        request=request,
    )
    db.commit()
    return {"slug": page.slug, "is_published": True, "published_at": page.published_at}


@router.post("/admin/cms/pages/{slug:path}/unpublish")
def admin_unpublish_page(
    slug: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("content:manage")),
):
    page = db.query(PageContent).filter(PageContent.slug == slug).first()
    if not page:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Page not found")
    page.is_published = False
    page.updated_by_id = user.id
    log_activity(
        db,
        actor=user,
        action="unpublish_page",
        resource_type="page_content",
        resource_id=page.slug,
        request=request,
    )
    db.commit()
    return {"slug": page.slug, "is_published": False}


# ---------------------------------------------------------------------------
# Version history (last 10 saves per page)
# ---------------------------------------------------------------------------


@router.get("/admin/cms/page-versions/{slug:path}")
def admin_list_versions(
    slug: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("content:manage")),
):
    page = db.query(PageContent).filter(PageContent.slug == slug).first()
    if not page:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Page not found")
    rows = (
        db.query(PageContentVersion)
        .filter(PageContentVersion.page_slug == slug)
        .order_by(PageContentVersion.created_at.desc())
        .limit(MAX_VERSIONS_PER_PAGE)
        .all()
    )
    return [
        {
            "id": r.id,
            "page_slug": r.page_slug,
            "title": r.title,
            "section_count": len(r.sections or []),
            "saved_by": r.saved_by.full_name if r.saved_by else None,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


@router.post("/admin/cms/page-versions/{slug:path}/revert/{version_id}")
def admin_revert_version(
    slug: str,
    version_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("content:manage")),
):
    """Restore a page to a snapshot. Snapshots the CURRENT state first so
    the revert itself is reversible — the boss can revert their revert."""
    page = db.query(PageContent).filter(PageContent.slug == slug).first()
    if not page:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Page not found")
    version = db.get(PageContentVersion, version_id)
    if not version or version.page_slug != slug:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "Version not found for this page",
        )
    # Snapshot the current state first (so the revert is itself reversible).
    _snapshot_and_prune(db, page=page, saved_by_id=user.id)

    # Apply the version.
    page.title = version.title
    page.description = version.description
    page.sections = list(version.sections or [])
    page.updated_by_id = user.id

    # Re-run used_on sync against the reverted sections.
    try:
        from app.services.media_usage import (
            extract_media_urls_from_sections,
            update_used_on_for_page,
        )

        urls = extract_media_urls_from_sections(page.sections)
        update_used_on_for_page(db, page_slug=page.slug, section_urls=urls)
    except Exception:  # noqa: BLE001
        pass

    log_activity(
        db,
        actor=user,
        action="revert_page",
        resource_type="page_content",
        resource_id=page.slug,
        request=request,
        details={"reverted_to_version_id": version.id, "saved_at": version.created_at.isoformat() if version.created_at else None},
    )
    db.commit()
    db.refresh(page)
    return PageDetail(
        slug=page.slug,
        title=page.title,
        page_type=page.page_type,
        description=page.description,
        is_published=page.is_published,
        published_at=page.published_at,
        sections=page.sections or [],
        updated_at=page.updated_at,
        created_at=page.created_at,
        updated_by=page.updated_by.full_name if page.updated_by else None,
    )
