"""Best-effort tracking of which marketing pages reference which media
assets. Updated on every page save so the admin can:
  - show "used on /home, /about" next to every library asset
  - warn (or refuse) before deleting a referenced asset

Asset URLs are matched against `MediaAsset.url` exactly. If the boss
hand-types an external URL into a section, it's not in the library and
won't appear in "used_on" — that's by design.
"""
from __future__ import annotations

from typing import Iterable

from sqlalchemy.orm import Session

from app.models import MediaAsset


# Section fields that may contain a media-library URL. Walked recursively
# through sections + their item lists.
_SCALAR_URL_FIELDS = {
    "image_url",
    "logo_url",
    "headshot_url",
    "cover_image_url",
    "icon_url",
}


def extract_media_urls_from_sections(sections: list[dict] | None) -> set[str]:
    """Return the set of media URLs referenced anywhere in the section list."""
    if not sections:
        return set()
    out: set[str] = set()

    def walk(node):
        if isinstance(node, dict):
            for key, val in node.items():
                if key in _SCALAR_URL_FIELDS and isinstance(val, str) and val.strip():
                    out.add(val.strip())
                elif isinstance(val, (dict, list)):
                    walk(val)
        elif isinstance(node, list):
            for child in node:
                walk(child)

    walk(sections)
    return out


def update_used_on_for_page(
    db: Session,
    *,
    page_slug: str,
    section_urls: Iterable[str],
) -> None:
    """Sync `MediaAsset.used_on` so:
      - assets referenced on this page have `page_slug` in their list
      - assets that USED to reference this page but no longer do are removed.
    Only operates on assets in the library (matching by URL); external URLs
    are silently ignored. Soft-deleted assets are also skipped.
    """
    section_urls_set = {u for u in section_urls if u}

    # 1) Drop this slug from every asset NOT in the new set.
    rows = (
        db.query(MediaAsset)
        .execution_options(include_deleted=True)
        .filter(MediaAsset.is_deleted == False)  # noqa: E712
        .all()
    )
    for r in rows:
        used = list(r.used_on or [])
        is_referenced = r.url in section_urls_set
        has_slug = page_slug in used
        if is_referenced and not has_slug:
            used.append(page_slug)
            r.used_on = sorted(set(used))
        elif (not is_referenced) and has_slug:
            r.used_on = [s for s in used if s != page_slug]
