from __future__ import annotations

import os
import re
import secrets
from datetime import datetime
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

from app.core.config import settings

ALLOWED_EXTS = {
    ".pdf", ".doc", ".docx", ".rtf", ".txt", ".md",
    ".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg",
    ".csv", ".xls", ".xlsx",
}
ALLOWED_MIME_PREFIXES = ("image/", "application/", "text/")


def _safe_name(name: str) -> str:
    base = os.path.basename(name)
    base = re.sub(r"[^A-Za-z0-9._-]", "_", base)
    return base[:120]


def save_upload(file: UploadFile, folder: str = "general") -> dict:
    """Save an UploadFile to UPLOAD_DIR/<yyyy>/<mm>/<folder>/<token>-<name>.

    Returns { url, filename, size, content_type, path }."""
    ext = Path(file.filename or "").suffix.lower()
    if ext and ext not in ALLOWED_EXTS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"File type not allowed: {ext}")
    if file.content_type and not any(file.content_type.startswith(p) for p in ALLOWED_MIME_PREFIXES):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Mime type not allowed")

    now = datetime.utcnow()
    rel_dir = Path(now.strftime("%Y")) / now.strftime("%m") / folder
    abs_dir = Path(settings.UPLOAD_DIR) / rel_dir
    abs_dir.mkdir(parents=True, exist_ok=True)

    token = secrets.token_urlsafe(8)
    safe = _safe_name(file.filename or "upload")
    filename = f"{token}-{safe}"
    abs_path = abs_dir / filename

    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    written = 0
    with abs_path.open("wb") as out:
        while True:
            chunk = file.file.read(64 * 1024)
            if not chunk:
                break
            written += len(chunk)
            if written > max_bytes:
                out.close()
                abs_path.unlink(missing_ok=True)
                raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "File too large")
            out.write(chunk)

    url = f"{settings.PUBLIC_BASE_URL}/uploads/{rel_dir.as_posix()}/{filename}"
    return {
        "url": url,
        "filename": filename,
        "size": written,
        "content_type": file.content_type or "application/octet-stream",
        "path": str(abs_path),
    }
