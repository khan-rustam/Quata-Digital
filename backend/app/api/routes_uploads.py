from fastapi import APIRouter, Depends, File, Form, Request, UploadFile

from app.api.deps import get_current_user, log_activity
from app.models import MediaAsset, User
from app.services.uploads import save_upload
from app.db.session import get_db
from sqlalchemy.orm import Session

router = APIRouter(prefix="/uploads", tags=["uploads"])


@router.post("")
def upload_file(
    request: Request,
    file: UploadFile = File(...),
    folder: str = Form("general"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Authenticated upload endpoint. Returns a public URL.

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
def public_upload(
    request: Request,
    file: UploadFile = File(...),
    folder: str = Form("public"),
    db: Session = Depends(get_db),
):
    """Public upload — used by the careers form for resumes. No auth required, but
    rate-limited at the proxy in production. Folder is forced to a public-safe namespace."""
    if folder not in {"resumes", "public"}:
        folder = "public"
    info = save_upload(file, folder=folder)
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
