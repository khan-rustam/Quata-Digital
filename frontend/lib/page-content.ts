/**
 * Server-side fetcher for marketing-page content from the CMS API.
 *
 * Pattern: every public page calls `getPageContent(slug)` server-side. If
 * the API returns sections, the page renders them via `<SectionRenderer />`.
 * If the API returns 404 / null (page exists but unpublished, or backend
 * down), the page falls back to its existing static React copy. This is
 * how the live site stays up even before the boss has filled in any sections.
 */

import { apiUrl } from "./api";

// ---------------------------------------------------------------------------
// Section type catalogue — must stay in sync with
// backend/app/schemas/page_sections.py (`SECTION_TYPES`).
// ---------------------------------------------------------------------------

export type SectionId = string;

type SectionBase<T extends string> = {
  id: SectionId;
  type: T;
  visible?: boolean;
};

export type HeroSection = SectionBase<"hero"> & {
  eyebrow?: string | null;
  title: string;
  subtitle?: string | null;
  primary_cta_label?: string | null;
  primary_cta_href?: string | null;
  secondary_cta_label?: string | null;
  secondary_cta_href?: string | null;
  image_url?: string | null;
  variant?: "default" | "centered" | "split";
};

export type FeatureItem = { title: string; body: string; icon?: string | null };
export type FeatureGridSection = SectionBase<"feature_grid"> & {
  eyebrow?: string | null;
  title?: string | null;
  subtitle?: string | null;
  columns?: number;
  items: FeatureItem[];
};

export type IconBadgeSection = SectionBase<"icon_badge"> & {
  icon?: string | null;
  title: string;
  body?: string | null;
  cta_label?: string | null;
  cta_href?: string | null;
};

export type BigQuoteSection = SectionBase<"big_quote"> & {
  quote: string;
  author?: string | null;
  role?: string | null;
};

export type FaqItem = { question: string; answer: string };
export type FaqSection = SectionBase<"faq"> & {
  title?: string | null;
  subtitle?: string | null;
  items: FaqItem[];
};

export type StatItem = { value: string; label: string; caption?: string | null };
export type StatStripSection = SectionBase<"stat_strip"> & {
  eyebrow?: string | null;
  items: StatItem[];
};

export type TestimonialItem = {
  quote: string;
  author: string;
  role?: string | null;
  company?: string | null;
  headshot_url?: string | null;
};
export type TestimonialsSection = SectionBase<"testimonials"> & {
  eyebrow?: string | null;
  title?: string | null;
  items: TestimonialItem[];
};

export type TimelineItem = { date: string; title: string; body: string };
export type TimelineSection = SectionBase<"timeline"> & {
  title?: string | null;
  items: TimelineItem[];
};

export type ProcessStepItem = { title: string; body: string };
export type ProcessStepsSection = SectionBase<"process_steps"> & {
  eyebrow?: string | null;
  title?: string | null;
  items: ProcessStepItem[];
};

export type LogoItem = { name: string; logo_url: string; href?: string | null };
export type LogoCloudSection = SectionBase<"logo_cloud"> & {
  eyebrow?: string | null;
  title?: string | null;
  items: LogoItem[];
};

export type CtaSection = SectionBase<"cta"> & {
  eyebrow?: string | null;
  title: string;
  subtitle?: string | null;
  primary_cta_label?: string | null;
  primary_cta_href?: string | null;
  secondary_cta_label?: string | null;
  secondary_cta_href?: string | null;
};

export type NewsletterCtaSection = SectionBase<"newsletter_cta"> & {
  eyebrow?: string | null;
  title?: string | null;
  subtitle?: string | null;
};

export type RichTextSection = SectionBase<"rich_text"> & {
  body: string;
  width?: "narrow" | "default" | "wide";
};

export type ImageTextSection = SectionBase<"image_text"> & {
  eyebrow?: string | null;
  title?: string | null;
  body: string;
  image_url?: string | null;
  image_position?: "left" | "right";
};

export type Section =
  | HeroSection
  | FeatureGridSection
  | IconBadgeSection
  | BigQuoteSection
  | FaqSection
  | StatStripSection
  | TestimonialsSection
  | TimelineSection
  | ProcessStepsSection
  | LogoCloudSection
  | CtaSection
  | NewsletterCtaSection
  | RichTextSection
  | ImageTextSection;

export type PageContent = {
  slug: string;
  title: string;
  description: string | null;
  sections: Section[];
  published_at: string | null;
  updated_at: string;
};

// ---------------------------------------------------------------------------
// Server-only fetcher
// ---------------------------------------------------------------------------

/**
 * Fetch a page's content. Returns null when:
 *   - the page exists but isn't published (boss working on a draft)
 *   - the API is unreachable (backend hiccup)
 *   - the slug doesn't exist at all
 *
 * Either way, callers should fall back to their existing static React copy.
 */
export async function getPageContent(slug: string): Promise<PageContent | null> {
  try {
    const res = await fetch(`${apiUrl}/cms/pages/${encodeURI(slug)}`, {
      next: { revalidate: 10, tags: [`page:${slug}`] },
    });
    if (!res.ok) return null;
    const data = (await res.json()) as PageContent;
    if (!Array.isArray(data.sections) || data.sections.length === 0) return null;
    return data;
  } catch {
    return null;
  }
}
