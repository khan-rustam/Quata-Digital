"""Regression test for the CMS seed payloads.

If someone renames a section field, drops a section type, or tightens the
per-page-type allow-list, the canned payloads in `page_content_seeds.py`
will silently break the next fresh boot. This test catches that instantly.

What it asserts:
  1. Every section in `DEFAULTS` validates through the discriminated union
     (`validate_sections` in `app.schemas.page_sections`).
  2. Every page's payload is allowed for its declared `page_type`.
  3. Every default page slug listed in `seed_default_pages.DEFAULT_PAGES`
     either has a corresponding payload in `DEFAULTS`, or is intentionally
     left empty (general/legal pages where boss fills sections in admin).

Lives separate from the fastapi TestClient fixtures so it's quick + can
run as part of CI without spinning up the app.
"""
from __future__ import annotations

import pytest

from app.schemas.page_sections import (
    PAGE_TYPE_ALLOWED_SECTIONS,
    assert_allowed_for_page_type,
    validate_sections,
)
from app.services.page_content import DEFAULT_PAGES
from app.services.page_content_seeds import DEFAULTS


# Map slug -> page_type. The seed creates these rows; payloads must obey
# the matching allow-list.
SLUG_TO_PAGE_TYPE = {slug: page_type for slug, _title, page_type, _desc in DEFAULT_PAGES}


@pytest.mark.parametrize("slug", list(DEFAULTS.keys()))
def test_seeded_payload_validates(slug: str):
    """Every default section payload round-trips through Pydantic."""
    sections = DEFAULTS[slug]
    validated = validate_sections(sections)
    assert len(validated) == len(sections), (
        f"validate_sections lost rows for '{slug}': "
        f"input {len(sections)} → output {len(validated)}"
    )


@pytest.mark.parametrize("slug", list(DEFAULTS.keys()))
def test_seeded_payload_allowed_for_page_type(slug: str):
    """Every payload only uses sections allowed for that page's `page_type`."""
    page_type = SLUG_TO_PAGE_TYPE.get(slug)
    assert page_type is not None, (
        f"Slug '{slug}' has a payload in DEFAULTS but isn't in DEFAULT_PAGES — "
        f"fix the catalogues so they agree."
    )
    validated = validate_sections(DEFAULTS[slug])
    # Raises ValueError if a disallowed section type is present.
    assert_allowed_for_page_type(page_type, validated)


def test_every_seeded_page_slug_is_known():
    """DEFAULTS keys should never go stale relative to DEFAULT_PAGES."""
    unknown = sorted(set(DEFAULTS.keys()) - set(SLUG_TO_PAGE_TYPE.keys()))
    assert not unknown, f"DEFAULTS contains unknown slugs: {unknown}"


def test_allow_lists_use_only_real_section_types():
    """The per-page-type allow-lists shouldn't reference nonexistent types."""
    from app.schemas.page_sections import SECTION_TYPES

    real = {s["type"] for s in SECTION_TYPES}
    for page_type, allowed in PAGE_TYPE_ALLOWED_SECTIONS.items():
        bad = sorted(allowed - real)
        assert not bad, (
            f"Page type '{page_type}' allow-list references types that "
            f"don't exist in SECTION_TYPES: {bad}"
        )
