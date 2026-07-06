from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import log_activity, require_permission
from app.core.config import settings
from app.core.rate_limit import limiter
from app.db.session import get_db
from app.models import MediaAsset, User
from app.services.uploads import save_upload

router = APIRouter(prefix="/uploads", tags=["uploads"])


@router.post("")
def upload_file(
    request: Request,
    file: UploadFile = File(...),
    folder: str = Form("general"),
    user: User = Depends(require_permission("content:manage")),
    db: Session = Depends(get_db),
):
    """Authenticated upload endpoint (content managers only). Returns a URL.

    Every successful upload also creates a `MediaAsset` row so the file is
    discoverable from the admin media library and can be reused across
    CMS pages without re-uploading.
    """
    original_name = file.filename or "upload"
    info = save_upload(file, folder=folder)
    # Index into the media library. Best-effort — if the table doesn't exist
    # yet (fresh DB pre-migration) the upload still returns successfully.
    try:
        asset = MediaAsset(
            url=info["url"],
            filename=info["filename"],
            original_filename=original_name,
            content_type=info["content_type"],
            size=info["size"],
            folder=folder or "general",
            width=info.get("width"),
            height=info.get("height"),
            optimized_url=info.get("optimized_url"),
            optimized_size=info.get("optimized_size"),
            uploaded_by_id=user.id,
            tags=[],
            used_on=[],
        )
        db.add(asset)
        db.flush()
    except Exception:  # noqa: BLE001
        db.rollback()
    log_activity(
        db,
        actor=user,
        action="upload",
        resource_type="file",
        resource_id=info["filename"],
        request=request,
        details={"size": info["size"], "content_type": info["content_type"], "folder": folder},
    )
    db.commit()
    return info


@router.post("/public", include_in_schema=False)
@limiter.limit(settings.RATE_LIMIT_PUBLIC_FORM)
def public_upload(
    request: Request,
    file: UploadFile = File(...),
    folder: str = Form("public"),
    db: Session = Depends(get_db),
):
    """Anonymous upload used by the careers form for resumes.

    Hardening:
    * slowapi rate-limit per-IP (matches the rest of the public surface);
    * forces ``public=True`` so the upload service refuses SVG and anything
      outside the public-safe allow-list, and size-caps the stream.

    NOTE: this endpoint is deliberately NOT gated on hCaptcha. The upload
    fires the instant the applicant picks a file — before the form-level
    captcha is solved — so a captcha check here made every job application
    impossible once keys were configured. The bot gate lives on the actual
    submission (`POST /jobs/{id}/apply`), which still verifies the token.
    """
    if folder not in {"resumes", "public"}:
        folder = "public"
    info = save_upload(file, folder=folder, public=True)
    log_activity(
        db,
        actor=None,
        action="upload",
        resource_type="file",
        resource_id=info["filename"],
        request=request,
        details={"size": info["size"], "content_type": info["content_type"], "folder": folder},
    )
    db.commit()
    return info
