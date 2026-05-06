"""Admin media library API.

Surface for the boss to browse, search, edit metadata on, and delete every
file uploaded through the authenticated `/uploads` endpoint. Public uploads
(`/uploads/public` — used by the careers form for resumes) are NOT indexed
here, so resumes don't leak into the media browser.

Endpoints (all require `content:manage`):
    GET    /admin/media                 List with filter + search + pagination
    GET    /admin/media/{id}            Get one
    PATCH  /admin/media/{id}            Update alt_text + tags
    DELETE /admin/media/{id}            Soft-delete the row (file on disk
                                        is left alone — easy to recover)
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.deps import log_activity, require_permission
from app.db.session import get_db
from app.models import MediaAsset, User


router = APIRouter(prefix="/admin/media", tags=["media"])


class MediaOut(BaseModel):
    id: int
    url: str
    filename: str
    original_filename: Optional[str]
    content_type: str
    size: int
    folder: str
    width: Optional[int] = None
    height: Optional[int] = None
    optimized_url: Optional[str] = None
    optimized_size: Optional[int] = None
    alt_text: Optional[str]
    tags: List[str]
    used_on: List[str]
    uploaded_by: Optional[str]
    created_at: str

    @classmethod
    def from_row(cls, r: MediaAsset) -> "MediaOut":
        return cls(
            id=r.id,
            url=r.url,
            filename=r.filename,
            original_filename=r.original_filename,
            content_type=r.content_type,
            size=r.size,
            folder=r.folder,
            width=r.width,
            height=r.height,
            optimized_url=r.optimized_url,
            optimized_size=r.optimized_size,
            alt_text=r.alt_text,
            tags=list(r.tags or []),
            used_on=list(r.used_on or []),
            uploaded_by=r.uploaded_by.full_name if r.uploaded_by else None,
            created_at=r.created_at.isoformat() if r.created_at else "",
        )


class MediaPatch(BaseModel):
    alt_text: Optional[str] = None
    tags: Optional[List[str]] = None


@router.get("")
def list_media(
    db: Session = Depends(get_db),
    q: Optional[str] = Query(default=None, description="Search filename / alt / tags"),
    folder: Optional[str] = None,
    content_type_prefix: Optional[str] = Query(
        default=None,
        description="e.g. 'image/' to filter to images, 'application/' for documents",
    ),
    limit: int = Query(default=60, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(require_permission("content:manage")),
):
    qry = db.query(MediaAsset).filter(MediaAsset.is_deleted == False)  # noqa: E712
    if folder:
        qry = qry.filter(MediaAsset.folder == folder)
    if content_type_prefix:
        qry = qry.filter(MediaAsset.content_type.like(f"{content_type_prefix}%"))
    if q:
        like = f"%{q.lower()}%"
        from sqlalchemy import func, cast, String as SqlString
        qry = qry.filter(
            or_(
                func.lower(MediaAsset.filename).like(like),
                func.lower(MediaAsset.original_filename).like(like),
                func.lower(MediaAsset.alt_text).like(like),
                # tags is JSON; cast to string so simple LIKE works on SQLite
                func.lower(cast(MediaAsset.tags, SqlString)).like(like),
            )
        )
    total = qry.count()
    rows = (
        qry.order_by(MediaAsset.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    folders = sorted(
        {
            r[0]
            for r in db.query(MediaAsset.folder)
            .filter(MediaAsset.is_deleted == False)  # noqa: E712
            .distinct()
            .all()
        }
    )
    return {
        "items": [MediaOut.from_row(r).model_dump() for r in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
        "folders": folders,
    }


@router.get("/{asset_id}")
def get_media(
    asset_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("content:manage")),
):
    r = db.get(MediaAsset, asset_id)
    if not r or r.is_deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Asset not found")
    return MediaOut.from_row(r).model_dump()


@router.patch("/{asset_id}")
def patch_media(
    asset_id: int,
    payload: MediaPatch,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("content:manage")),
):
    r = db.get(MediaAsset, asset_id)
    if not r or r.is_deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Asset not found")
    if payload.alt_text is not None:
        r.alt_text = payload.alt_text[:255]
    if payload.tags is not None:
        # Normalise tags: lower, trim, dedupe, drop empties.
        cleaned = []
        seen = set()
        for t in payload.tags:
            tt = t.strip().lower()
            if tt and tt not in seen and len(tt) <= 40:
                cleaned.append(tt)
                seen.add(tt)
        r.tags = cleaned
    log_activity(
        db,
        actor=user,
        action="update",
        resource_type="media_asset",
        resource_id=r.id,
        request=request,
        details={"fields": list(payload.model_dump(exclude_unset=True).keys())},
    )
    db.commit()
    db.refresh(r)
    return MediaOut.from_row(r).model_dump()


@router.delete("/{asset_id}", status_code=204)
def delete_media(
    asset_id: int,
    request: Request,
    force: bool = Query(default=False, description="Delete even when referenced by pages"),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("content:manage")),
):
    """Soft-delete the media-library entry. The file on disk is preserved
    so any pages still referencing the URL keep rendering.

    If the asset is currently referenced by one or more marketing pages
    (`used_on` is non-empty) and `force=false`, returns 409 with the list
    of slugs so the admin UI can show a confirmation."""
    from datetime import datetime, timezone

    r = db.get(MediaAsset, asset_id)
    if not r or r.is_deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Asset not found")
    if (r.used_on or []) and not force:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "asset_in_use",
                "used_on": list(r.used_on or []),
                "message": (
                    f"This asset is referenced by {len(r.used_on or [])} page(s). "
                    "Re-issue the delete with ?force=true to remove anyway — pages "
                    "currently using it will continue to render until you replace "
                    "the image (the file on disk is preserved)."
                ),
            },
        )
    r.is_deleted = True
    r.deleted_at = datetime.now(timezone.utc)
    log_activity(
        db,
        actor=user,
        action="delete",
        resource_type="media_asset",
        resource_id=r.id,
        request=request,
        details={"url": r.url, "forced": force, "was_used_on": list(r.used_on or [])},
    )
    db.commit()
