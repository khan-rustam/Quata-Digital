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
    """Save an UploadFile under <yyyy>/<mm>/<folder>/<token>-<name>.

    Backend dispatch:
      - `UPLOAD_BACKEND=local` (default) writes to `UPLOAD_DIR/`. The
        FastAPI `StaticFiles` mount serves it under `/uploads/...`.
      - `UPLOAD_BACKEND=s3` writes the original to S3 (or any S3-compatible
        endpoint via `S3_ENDPOINT_URL` — works with R2, MinIO, Backblaze).
        Public URL is `S3_PUBLIC_URL_BASE/...` if set, else the canonical
        bucket URL.

    Returns: { url, filename, size, content_type, path, width, height,
              optimized_url, optimized_size }."""
    ext = Path(file.filename or "").suffix.lower()
    if ext and ext not in ALLOWED_EXTS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"File type not allowed: {ext}")
    if file.content_type and not any(file.content_type.startswith(p) for p in ALLOWED_MIME_PREFIXES):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Mime type not allowed")

    now = datetime.utcnow()
    rel_dir = Path(now.strftime("%Y")) / now.strftime("%m") / folder
    token = secrets.token_urlsafe(8)
    safe = _safe_name(file.filename or "upload")
    filename = f"{token}-{safe}"

    backend = (settings.UPLOAD_BACKEND or "local").lower()
    if backend == "s3":
        return _save_s3(file, ext, rel_dir, filename)
    return _save_local(file, ext, rel_dir, filename)


def _save_local(file: UploadFile, ext: str, rel_dir: Path, filename: str) -> dict:
    abs_dir = Path(settings.UPLOAD_DIR) / rel_dir
    abs_dir.mkdir(parents=True, exist_ok=True)
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


def _save_s3(file: UploadFile, ext: str, rel_dir: Path, filename: str) -> dict:
    """Upload to S3 / R2 / MinIO. Stages to a tmp file first so we can
    enforce the size cap + run image post-processing exactly like local.
    """
    import tempfile

    if not settings.S3_BUCKET:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "UPLOAD_BACKEND=s3 but S3_BUCKET is not set.",
        )
    try:
        import boto3  # type: ignore
        from botocore.exceptions import BotoCoreError, ClientError  # type: ignore
    except ImportError as exc:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "UPLOAD_BACKEND=s3 but boto3 is not installed in this environment.",
        ) from exc

    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    written = 0

    with tempfile.TemporaryDirectory() as tmp_root:
        tmp_dir = Path(tmp_root)
        tmp_path = tmp_dir / filename
        with tmp_path.open("wb") as out:
            while True:
                chunk = file.file.read(64 * 1024)
                if not chunk:
                    break
                written += len(chunk)
                if written > max_bytes:
                    raise HTTPException(
                        status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        "File too large",
                    )
                out.write(chunk)

        # Image post-process locally so we have width/height + WebP shadow,
        # then upload BOTH the original and the optimised file to S3.
        post: dict = {}
        if ext in WEBP_SOURCE_EXTS or ext in {".webp", ".gif"}:
            post = _post_process_image(tmp_path, tmp_dir, filename, rel_dir, ext)

        client_kwargs: dict = {}
        if settings.S3_REGION:
            client_kwargs["region_name"] = settings.S3_REGION
        if settings.S3_ENDPOINT_URL:
            client_kwargs["endpoint_url"] = settings.S3_ENDPOINT_URL
        s3 = boto3.client("s3", **client_kwargs)

        key = f"{rel_dir.as_posix()}/{filename}"
        try:
            s3.upload_file(
                str(tmp_path),
                settings.S3_BUCKET,
                key,
                ExtraArgs={
                    "ContentType": file.content_type or "application/octet-stream",
                    "CacheControl": "public, max-age=31536000, immutable",
                },
            )
        except (BotoCoreError, ClientError) as exc:
            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY,
                f"S3 upload failed: {exc}",
            ) from exc

        # If we generated a WebP, ship it under <key>.webp too.
        webp_local_url: Optional[str] = post.get("optimized_url")
        webp_remote_url: Optional[str] = None
        if webp_local_url:
            webp_name = filename.rsplit(".", 1)[0] + ".webp"
            webp_path = tmp_dir / webp_name
            if webp_path.exists():
                webp_key = f"{rel_dir.as_posix()}/{webp_name}"
                try:
                    s3.upload_file(
                        str(webp_path),
                        settings.S3_BUCKET,
                        webp_key,
                        ExtraArgs={
                            "ContentType": "image/webp",
                            "CacheControl": "public, max-age=31536000, immutable",
                        },
                    )
                    webp_remote_url = _s3_public_url(webp_key)
                except (BotoCoreError, ClientError) as exc:
                    log.warning("WebP S3 upload failed for %s: %s", filename, exc)

    url = _s3_public_url(key)
    info: dict = {
        "url": url,
        "filename": filename,
        "size": written,
        "content_type": file.content_type or "application/octet-stream",
        "path": f"s3://{settings.S3_BUCKET}/{key}",
        "width": post.get("width"),
        "height": post.get("height"),
        "optimized_url": webp_remote_url,
        "optimized_size": post.get("optimized_size") if webp_remote_url else None,
    }
    return info


def _s3_public_url(key: str) -> str:
    """Build the public URL for an S3 key. Prefers the configured CDN /
    custom domain (`S3_PUBLIC_URL_BASE`) when set, falls back to the
    canonical AWS path-style URL."""
    base = (settings.S3_PUBLIC_URL_BASE or "").rstrip("/")
    if base:
        return f"{base}/{key}"
    if settings.S3_ENDPOINT_URL:
        # MinIO / R2 / custom — use the endpoint as the public host. This
        # works for dev; for prod the operator should set S3_PUBLIC_URL_BASE
        # explicitly to the CDN.
        endpoint = settings.S3_ENDPOINT_URL.rstrip("/")
        return f"{endpoint}/{settings.S3_BUCKET}/{key}"
    region = settings.S3_REGION or "us-east-1"
    return f"https://{settings.S3_BUCKET}.s3.{region}.amazonaws.com/{key}"


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
