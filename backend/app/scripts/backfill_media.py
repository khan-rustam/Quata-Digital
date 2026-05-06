"""Backfill width/height + WebP shadows for MediaAsset rows uploaded
before the Pillow integration shipped.

Run on the VPS:

    cd /home/Quata-Digital/backend
    source .venv/bin/activate
    python -m app.scripts.backfill_media

Idempotent: skips rows that already have dimensions filled. Skips rows
whose file doesn't exist on disk (logged but doesn't fail the run).
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from urllib.parse import urlparse

from app.core.config import settings
from app.db.session import SessionLocal
from app.models import MediaAsset


log = logging.getLogger("backfill_media")


def _local_path_for(asset: MediaAsset) -> Path | None:
    """Map an asset's public URL back to a local file path under UPLOAD_DIR.

    The url is shaped `{PUBLIC_BASE_URL}/uploads/<yyyy>/<mm>/<folder>/<file>`
    so we strip the prefix and re-anchor at UPLOAD_DIR.
    """
    parsed = urlparse(asset.url)
    rel = parsed.path
    marker = "/uploads/"
    idx = rel.find(marker)
    if idx == -1:
        return None
    after = rel[idx + len(marker) :]
    return Path(settings.UPLOAD_DIR) / after


def main() -> int:
    try:
        from PIL import Image, UnidentifiedImageError  # noqa: WPS433
    except ImportError:
        print("Pillow is not installed in this environment.", file=sys.stderr)
        return 2

    WEBP_SOURCE_EXTS = {".png", ".jpg", ".jpeg"}
    processed = 0
    skipped_already_done = 0
    skipped_missing = 0
    failed = 0

    with SessionLocal() as db:
        rows = (
            db.query(MediaAsset)
            .filter(MediaAsset.is_deleted == False)  # noqa: E712
            .filter(MediaAsset.content_type.like("image/%"))
            .all()
        )
        for r in rows:
            if r.width is not None and r.height is not None:
                # Already populated. Optimised version may still be missing,
                # but skip wholesale to keep this idempotent + fast.
                if r.optimized_url or not r.filename.lower().endswith(tuple(WEBP_SOURCE_EXTS)):
                    skipped_already_done += 1
                    continue

            local = _local_path_for(r)
            if local is None or not local.exists():
                skipped_missing += 1
                print(f"  ! file missing: {r.url}")
                continue

            try:
                with Image.open(local) as img:
                    r.width = int(img.width)
                    r.height = int(img.height)

                    ext = local.suffix.lower()
                    if ext in WEBP_SOURCE_EXTS and not r.optimized_url:
                        webp_path = local.with_suffix(".webp")
                        rgb_img = img
                        if img.mode in ("P", "PA"):
                            rgb_img = img.convert("RGBA" if "A" in img.mode else "RGB")
                        elif img.mode not in ("RGB", "RGBA", "L"):
                            rgb_img = img.convert("RGB")
                        rgb_img.save(webp_path, format="WEBP", quality=82, method=6)
                        # Reconstruct the public URL alongside the original.
                        r.optimized_url = r.url.rsplit(".", 1)[0] + ".webp"
                        try:
                            r.optimized_size = webp_path.stat().st_size
                        except OSError:
                            r.optimized_size = None
                processed += 1
                if processed % 25 == 0:
                    db.commit()
            except UnidentifiedImageError:
                failed += 1
                print(f"  ! Pillow couldn't identify: {r.url}")
            except Exception as exc:  # noqa: BLE001
                failed += 1
                print(f"  ! error on {r.url}: {exc}")

        db.commit()

    print()
    print(f"Processed: {processed}")
    print(f"Skipped (already done): {skipped_already_done}")
    print(f"Skipped (file missing): {skipped_missing}")
    print(f"Failed: {failed}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
