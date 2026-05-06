"""Default catalogue of marketing pages, seeded at boot.

Like `site_settings`, the page list is upserted on every boot so a freshly
migrated production DB has every page available in the admin even with
`SEED_ON_STARTUP=false`. Existing rows are NEVER overwritten — only the
metadata (title / description / page_type) is refreshed so the admin shows
the latest copy.

Section content is left empty by default; the boss fills sections one page
at a time. Until a page is published with sections, the public renderer
falls back to the existing static React copy on the frontend.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import PageContent


# slug -> (title, page_type, description)
DEFAULT_PAGES: list[tuple[str, str, str, str]] = [
    # General pages (free-form)
    ("home", "Home", "general", "Marketing home page."),
    ("about", "About", "general", "Company story, mission, values, founder."),
    ("ecosystem", "Ecosystem", "general", "Ecosystem overview — how the seven products fit together."),
    ("partners", "Partners", "general", "Partner gateway — overview of the four paths."),
    ("careers", "Careers", "general", "Open roles + life at QUATA."),
    ("contact", "Contact", "general", "Contact form + office details."),
    ("privacy", "Privacy policy", "general", "Privacy policy."),
    ("terms", "Terms of service", "general", "Terms of service."),
    ("security", "Security", "general", "Security disclosure + posture."),
    # Per-product pages (strict shape)
    ("ecosystem/quatapay", "QUATAPAY", "product", "QUATAPAY product page."),
    ("ecosystem/abaqwa", "ABAQWA", "product", "ABAQWA product page."),
    ("ecosystem/quatafood", "QUATAFOOD", "product", "QUATAFOOD product page."),
    ("ecosystem/88basket", "88BASKET", "product", "88BASKET product page."),
    ("ecosystem/88brickz", "88BRICKZ", "product", "88BRICKZ product page."),
    ("ecosystem/o3mall", "O3MALL", "product", "O3MALL product page."),
    ("ecosystem/qmediq", "QMEDIQ", "product", "QMEDIQ product page."),
    # Per-partner-type pages (strict shape)
    ("partners/business", "Business partners", "partner_type", "Business partner application path."),
    ("partners/strategic", "Strategic partners", "partner_type", "Strategic partner application path."),
    ("partners/investor", "Investors", "partner_type", "Investor partner application path."),
    ("partners/service", "Service partners", "partner_type", "Service partner application path."),
]


def seed_default_pages(db: Session) -> int:
    """Upsert every entry in `DEFAULT_PAGES`. Existing rows keep their
    sections + published status; only metadata is refreshed."""
    inserted = 0
    for slug, title, page_type, description in DEFAULT_PAGES:
        row = db.query(PageContent).filter(PageContent.slug == slug).first()
        if row is None:
            db.add(
                PageContent(
                    slug=slug,
                    title=title,
                    page_type=page_type,
                    description=description,
                    sections=[],
                    is_published=False,
                )
            )
            inserted += 1
        else:
            # Refresh metadata; keep sections + publish state intact.
            row.title = title
            row.page_type = page_type
            row.description = description
    db.commit()
    return inserted
