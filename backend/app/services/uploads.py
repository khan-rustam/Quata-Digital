from __future__ import annotations

import logging
import os
import re
import secrets
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import HTTPException, UploadFile, status

from app.core.config import settings

log = logging.getLogger("quata.uploads")

ALLOWED_EXTS = {
    ".pdf", ".doc", ".docx", ".rtf", ".txt", ".md",
    ".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg",
    ".csv", ".xls", ".xlsx",
}
ALLOWED_MIME_PREFIXES = ("image/", "application/", "text/")

# JPG / PNG get a WebP shadow saved alongside; SVG/GIF/WebP skip optimisation
# (already optimised, animation-sensitive, or vector).
WEBP_SOURCE_EXTS = {".png", ".jpg", ".jpeg"}


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
    info: dict = {
        "url": url,
        "filename": filename,
        "size": written,
        "content_type": file.content_type or "application/octet-stream",
        "path": str(abs_path),
        "width": None,
        "height": None,
        "optimized_url": None,
        "optimized_size": None,
    }

    # Image pipeline — best-effort. Failures don't break the upload.
    if ext in WEBP_SOURCE_EXTS or ext in {".webp", ".gif"}:
        info.update(_post_process_image(abs_path, abs_dir, filename, rel_dir, ext))

    return info


def _post_process_image(
    abs_path: Path,
    abs_dir: Path,
    filename: str,
    rel_dir: Path,
    ext: str,
) -> dict:
    """Extract width/height and (for JPG/PNG) save a WebP shadow next to the
    original. Returns a partial dict that gets merged into the upload result.
    Any error here is logged and swallowed — the upload itself stays
    successful even if Pillow can't open the file.
    """
    out: dict = {}
    try:
        from PIL import Image, UnidentifiedImageError  # noqa: WPS433
    except ImportError:
        log.warning("Pillow not installed; skipping image post-processing.")
        return out

    try:
        with Image.open(abs_path) as img:
            out["width"] = int(img.width)
            out["height"] = int(img.height)

            if ext in WEBP_SOURCE_EXTS:
                webp_name = filename.rsplit(".", 1)[0] + ".webp"
                webp_path = abs_dir / webp_name
                try:
                    # Convert palette images so WebP gets RGB(A) input.
                    rgb_img = img
                    if img.mode in ("P", "PA"):
                        rgb_img = img.convert("RGBA" if "A" in img.mode else "RGB")
                    elif img.mode not in ("RGB", "RGBA", "L"):
                        rgb_img = img.convert("RGB")
                    rgb_img.save(webp_path, format="WEBP", quality=82, method=6)
                    out["optimized_url"] = (
                        f"{settings.PUBLIC_BASE_URL}/uploads/"
                        f"{rel_dir.as_posix()}/{webp_name}"
                    )
                    try:
                        out["optimized_size"] = webp_path.stat().st_size
                    except OSError:
                        out["optimized_size"] = None
                except Exception as exc:  # noqa: BLE001
                    log.info("WebP generation failed for %s: %s", filename, exc)
    except UnidentifiedImageError:
        log.info("Pillow couldn't identify image: %s", filename)
    except Exception as exc:  # noqa: BLE001
        log.info("Image post-processing failed for %s: %s", filename, exc)
    return out
