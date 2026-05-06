"""Pydantic schemas for every section type the marketing CMS supports.

Each section dict on `PageContent.sections` is validated against the
discriminated union `SectionUnion` below before saving — so the admin can't
write garbage that breaks the public renderer.

Adding a new section type means three steps:
  1. Define a `*Section` model below.
  2. Add it to `SECTION_MODELS` and the `SectionUnion` annotation.
  3. Build the matching admin form + frontend renderer.
"""
from __future__ import annotations

from typing import Annotated, Literal, Optional, Union
from uuid import uuid4

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Base — every section carries a stable id (used as React key on reorder).
# ---------------------------------------------------------------------------

class _SectionBase(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex[:12])
    visible: bool = True


# ---------------------------------------------------------------------------
# Item-level shapes (reused across sections).
# ---------------------------------------------------------------------------

class FeatureItem(BaseModel):
    title: str
    body: str
    icon: Optional[str] = None  # lucide icon name; renderer falls back to a default


class FaqItem(BaseModel):
    question: str
    answer: str


class StatItem(BaseModel):
    value: str
    label: str
    caption: Optional[str] = None


class TestimonialItem(BaseModel):
    quote: str
    author: str
    role: Optional[str] = None
    company: Optional[str] = None
    headshot_url: Optional[str] = None


class TimelineItem(BaseModel):
    date: str
    title: str
    body: str


class ProcessStepItem(BaseModel):
    title: str
    body: str


class LogoItem(BaseModel):
    name: str
    logo_url: str
    href: Optional[str] = None


# ---------------------------------------------------------------------------
# Section types (13). Order = canonical order shown in the admin "add
# section" picker.
# ---------------------------------------------------------------------------

class HeroSection(_SectionBase):
    type: Literal["hero"] = "hero"
    eyebrow: Optional[str] = None
    title: str
    subtitle: Optional[str] = None
    primary_cta_label: Optional[str] = None
    primary_cta_href: Optional[str] = None
    secondary_cta_label: Optional[str] = None
    secondary_cta_href: Optional[str] = None
    image_url: Optional[str] = None
    variant: Literal["default", "centered", "split"] = "default"


class FeatureGridSection(_SectionBase):
    type: Literal["feature_grid"] = "feature_grid"
    eyebrow: Optional[str] = None
    title: Optional[str] = None
    subtitle: Optional[str] = None
    columns: int = Field(default=3, ge=1, le=4)
    items: list[FeatureItem] = Field(default_factory=list)


class IconBadgeSection(_SectionBase):
    type: Literal["icon_badge"] = "icon_badge"
    icon: Optional[str] = None
    title: str
    body: Optional[str] = None
    cta_label: Optional[str] = None
    cta_href: Optional[str] = None


class BigQuoteSection(_SectionBase):
    type: Literal["big_quote"] = "big_quote"
    quote: str
    author: Optional[str] = None
    role: Optional[str] = None


class FaqSection(_SectionBase):
    type: Literal["faq"] = "faq"
    title: Optional[str] = None
    subtitle: Optional[str] = None
    items: list[FaqItem] = Field(default_factory=list)


class StatStripSection(_SectionBase):
    type: Literal["stat_strip"] = "stat_strip"
    eyebrow: Optional[str] = None
    items: list[StatItem] = Field(default_factory=list)


class TestimonialsSection(_SectionBase):
    type: Literal["testimonials"] = "testimonials"
    eyebrow: Optional[str] = None
    title: Optional[str] = None
    items: list[TestimonialItem] = Field(default_factory=list)


class TimelineSection(_SectionBase):
    type: Literal["timeline"] = "timeline"
    title: Optional[str] = None
    items: list[TimelineItem] = Field(default_factory=list)


class ProcessStepsSection(_SectionBase):
    type: Literal["process_steps"] = "process_steps"
    eyebrow: Optional[str] = None
    title: Optional[str] = None
    items: list[ProcessStepItem] = Field(default_factory=list)


class LogoCloudSection(_SectionBase):
    type: Literal["logo_cloud"] = "logo_cloud"
    eyebrow: Optional[str] = None
    title: Optional[str] = None
    items: list[LogoItem] = Field(default_factory=list)


class CtaSection(_SectionBase):
    type: Literal["cta"] = "cta"
    eyebrow: Optional[str] = None
    title: str
    subtitle: Optional[str] = None
    primary_cta_label: Optional[str] = None
    primary_cta_href: Optional[str] = None
    secondary_cta_label: Optional[str] = None
    secondary_cta_href: Optional[str] = None


class NewsletterCtaSection(_SectionBase):
    type: Literal["newsletter_cta"] = "newsletter_cta"
    eyebrow: Optional[str] = None
    title: Optional[str] = None
    subtitle: Optional[str] = None


class RichTextSection(_SectionBase):
    type: Literal["rich_text"] = "rich_text"
    body: str  # markdown
    width: Literal["narrow", "default", "wide"] = "default"


class ImageTextSection(_SectionBase):
    type: Literal["image_text"] = "image_text"
    eyebrow: Optional[str] = None
    title: Optional[str] = None
    body: str  # markdown
    image_url: Optional[str] = None
    image_position: Literal["left", "right"] = "right"


# ---------------------------------------------------------------------------
# Discriminated union — Pydantic uses the `type` field to pick the right model.
# ---------------------------------------------------------------------------

SECTION_MODELS = [
    HeroSection,
    FeatureGridSection,
    IconBadgeSection,
    BigQuoteSection,
    FaqSection,
    StatStripSection,
    TestimonialsSection,
    TimelineSection,
    ProcessStepsSection,
    LogoCloudSection,
    CtaSection,
    NewsletterCtaSection,
    RichTextSection,
    ImageTextSection,
]

# Catalogue surfaced to the admin so it can render a "Add section" picker.
SECTION_TYPES = [
    {"type": "hero", "label": "Hero", "description": "Page title, subtitle, two CTAs and an optional image."},
    {"type": "feature_grid", "label": "Feature grid", "description": "Title + a grid of feature cards (1–4 columns)."},
    {"type": "icon_badge", "label": "Icon badge", "description": "Single icon-led marketing block."},
    {"type": "big_quote", "label": "Big quote", "description": "Pull-quote styled large for emphasis."},
    {"type": "faq", "label": "FAQ", "description": "Title + question/answer pairs."},
    {"type": "stat_strip", "label": "Stat strip", "description": "A row of headline numbers."},
    {"type": "testimonials", "label": "Testimonials", "description": "Customer quotes with optional headshot."},
    {"type": "timeline", "label": "Timeline", "description": "Dated milestones."},
    {"type": "process_steps", "label": "Process steps", "description": "Numbered, ordered steps."},
    {"type": "logo_cloud", "label": "Logo cloud", "description": "Press / partner logo wall."},
    {"type": "cta", "label": "Call-to-action", "description": "Standalone CTA block (no form)."},
    {"type": "newsletter_cta", "label": "Newsletter signup", "description": "Inline email-capture for the newsletter."},
    {"type": "rich_text", "label": "Rich text", "description": "Markdown body for free-form copy."},
    {"type": "image_text", "label": "Image + text", "description": "Two-column image-and-prose row."},
]


SectionUnion = Annotated[
    Union[
        HeroSection,
        FeatureGridSection,
        IconBadgeSection,
        BigQuoteSection,
        FaqSection,
        StatStripSection,
        TestimonialsSection,
        TimelineSection,
        ProcessStepsSection,
        LogoCloudSection,
        CtaSection,
        NewsletterCtaSection,
        RichTextSection,
        ImageTextSection,
    ],
    Field(discriminator="type"),
]


def validate_sections(raw: list) -> list[dict]:
    """Round-trip a list of raw section dicts through the discriminated
    union to enforce per-type validation. Returns the canonical dump that
    should be persisted on `PageContent.sections`. Raises Pydantic
    ValidationError on bad input.
    """
    from pydantic import TypeAdapter

    adapter = TypeAdapter(list[SectionUnion])
    parsed = adapter.validate_python(raw or [])
    return [m.model_dump(mode="json") for m in parsed]


# ---------------------------------------------------------------------------
# Per-page-type allow-list. `general` accepts every type; `product` and
# `partner_type` follow a brand-consistent shape so individual product/partner
# pages don't drift.
# ---------------------------------------------------------------------------

PAGE_TYPE_ALLOWED_SECTIONS: dict[str, set[str]] = {
    "general": {s["type"] for s in SECTION_TYPES},
    "product": {
        "hero",
        "feature_grid",
        "icon_badge",
        "stat_strip",
        "image_text",
        "process_steps",
        "testimonials",
        "faq",
        "cta",
        "rich_text",
    },
    "partner_type": {
        "hero",
        "feature_grid",
        "icon_badge",
        "process_steps",
        "stat_strip",
        "faq",
        "cta",
        "rich_text",
    },
}


def assert_allowed_for_page_type(page_type: str, sections: list[dict]) -> None:
    allowed = PAGE_TYPE_ALLOWED_SECTIONS.get(page_type, PAGE_TYPE_ALLOWED_SECTIONS["general"])
    bad = [s for s in sections if s.get("type") not in allowed]
    if bad:
        raise ValueError(
            f"Section type(s) {sorted({s.get('type') for s in bad})} are not allowed on a "
            f"{page_type} page (allowed: {sorted(allowed)})."
        )
