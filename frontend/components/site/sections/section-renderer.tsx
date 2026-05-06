/**
 * Renders an ordered list of CMS sections (from `lib/page-content.ts`).
 * Switches on `section.type` and dispatches to the matching renderer.
 *
 * Adding a new section type:
 *   1. Add the schema in backend/app/schemas/page_sections.py.
 *   2. Add the TS type to lib/page-content.ts.
 *   3. Add a renderer + admin form below + in components/admin/cms-sections/.
 */

import Link from "next/link";
import Image from "next/image";
import {
  ArrowRight,
  ArrowUpRight,
  CheckCircle2,
  Quote,
  Sparkles,
  Star,
} from "lucide-react";

import type { Section } from "@/lib/page-content";
import { renderMarkdownToHtml } from "@/lib/markdown";
import { Button } from "@/components/ui/button";
import { NewsletterSignup } from "@/components/site/sections/newsletter";

// ---------------------------------------------------------------------------
// Public — render an ordered list of sections.
// ---------------------------------------------------------------------------

export function SectionRenderer({ sections }: { sections: Section[] }) {
  return (
    <>
      {sections
        .filter((s) => s.visible !== false)
        .map((s) => (
          <SectionSwitch key={s.id} section={s} />
        ))}
    </>
  );
}

function SectionSwitch({ section }: { section: Section }) {
  switch (section.type) {
    case "hero":
      return <HeroSection s={section} />;
    case "feature_grid":
      return <FeatureGridSection s={section} />;
    case "icon_badge":
      return <IconBadgeSection s={section} />;
    case "big_quote":
      return <BigQuoteSection s={section} />;
    case "faq":
      return <FaqSection s={section} />;
    case "stat_strip":
      return <StatStripSection s={section} />;
    case "testimonials":
      return <TestimonialsSection s={section} />;
    case "timeline":
      return <TimelineSection s={section} />;
    case "process_steps":
      return <ProcessStepsSection s={section} />;
    case "logo_cloud":
      return <LogoCloudSection s={section} />;
    case "cta":
      return <CtaSection s={section} />;
    case "newsletter_cta":
      return <NewsletterCtaSection s={section} />;
    case "rich_text":
      return <RichTextSection s={section} />;
    case "image_text":
      return <ImageTextSection s={section} />;
    default:
      return null;
  }
}

// ---------------------------------------------------------------------------
// Type-specific renderers
// ---------------------------------------------------------------------------

function SectionWrap({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section className={`container-page py-16 md:py-20 ${className}`}>
      {children}
    </section>
  );
}

function HeroSection({ s }: { s: Extract<Section, { type: "hero" }> }) {
  const centered = s.variant === "centered";
  const split = s.variant === "split";

  if (split && s.image_url) {
    return (
      <SectionWrap className="!pt-10 md:!pt-14">
        <div className="grid lg:grid-cols-[1.2fr_1fr] gap-10 items-center">
          <div>
            {s.eyebrow && (
              <div className="text-xs uppercase tracking-wider text-primary font-semibold">
                {s.eyebrow}
              </div>
            )}
            <h1 className="mt-3 text-4xl md:text-5xl lg:text-6xl font-semibold tracking-tight text-balance leading-[1.05]">
              {s.title}
            </h1>
            {s.subtitle && (
              <p className="mt-5 text-lg text-muted-foreground max-w-xl">{s.subtitle}</p>
            )}
            <HeroCtas s={s} />
          </div>
          <div className="relative aspect-[4/3] rounded-2xl overflow-hidden ring-elevated bg-secondary">
            <Image src={s.image_url} alt={s.title} fill className="object-cover" />
          </div>
        </div>
      </SectionWrap>
    );
  }

  return (
    <SectionWrap className={centered ? "!pt-10 md:!pt-14 text-center" : "!pt-10 md:!pt-14"}>
      <div className={centered ? "max-w-3xl mx-auto" : "max-w-3xl"}>
        {s.eyebrow && (
          <div className="text-xs uppercase tracking-wider text-primary font-semibold">
            {s.eyebrow}
          </div>
        )}
        <h1 className="mt-3 text-4xl md:text-5xl lg:text-6xl font-semibold tracking-tight text-balance leading-[1.05]">
          {s.title}
        </h1>
        {s.subtitle && (
          <p className={`mt-5 text-lg text-muted-foreground ${centered ? "" : "max-w-2xl"}`}>
            {s.subtitle}
          </p>
        )}
        <HeroCtas s={s} centered={centered} />
      </div>
      {s.image_url && !split && (
        <div className="mt-10 relative aspect-[16/9] rounded-2xl overflow-hidden ring-elevated bg-secondary max-w-5xl mx-auto">
          <Image src={s.image_url} alt={s.title} fill className="object-cover" />
        </div>
      )}
    </SectionWrap>
  );
}

function HeroCtas({
  s,
  centered = false,
}: {
  s: Extract<Section, { type: "hero" }>;
  centered?: boolean;
}) {
  const has =
    (s.primary_cta_label && s.primary_cta_href) ||
    (s.secondary_cta_label && s.secondary_cta_href);
  if (!has) return null;
  return (
    <div className={`mt-7 flex flex-wrap gap-2 ${centered ? "justify-center" : ""}`}>
      {s.primary_cta_label && s.primary_cta_href && (
        <Button asChild size="lg">
          <Link href={s.primary_cta_href}>
            {s.primary_cta_label}
            <ArrowRight className="h-4 w-4" />
          </Link>
        </Button>
      )}
      {s.secondary_cta_label && s.secondary_cta_href && (
        <Button asChild variant="outline" size="lg">
          <Link href={s.secondary_cta_href}>{s.secondary_cta_label}</Link>
        </Button>
      )}
    </div>
  );
}

function FeatureGridSection({ s }: { s: Extract<Section, { type: "feature_grid" }> }) {
  const cols = Math.min(Math.max(s.columns ?? 3, 1), 4);
  const gridCols =
    cols === 1 ? "grid-cols-1" : cols === 2 ? "sm:grid-cols-2" : cols === 4 ? "sm:grid-cols-2 lg:grid-cols-4" : "sm:grid-cols-2 lg:grid-cols-3";
  return (
    <SectionWrap>
      {(s.eyebrow || s.title || s.subtitle) && (
        <header className="max-w-2xl">
          {s.eyebrow && (
            <div className="text-xs uppercase tracking-wider text-primary font-semibold">
              {s.eyebrow}
            </div>
          )}
          {s.title && (
            <h2 className="mt-3 text-3xl md:text-4xl font-semibold tracking-tight">
              {s.title}
            </h2>
          )}
          {s.subtitle && <p className="mt-3 text-muted-foreground">{s.subtitle}</p>}
        </header>
      )}
      <ul className={`mt-10 grid gap-5 ${gridCols}`}>
        {s.items.map((it, i) => (
          <li
            key={i}
            className="rounded-2xl border border-border bg-card p-6 ring-soft hover:ring-elevated transition"
          >
            <div className="inline-flex h-9 w-9 items-center justify-center rounded-xl bg-brand-soft text-primary">
              <Sparkles className="h-4 w-4" />
            </div>
            <h3 className="mt-4 text-base font-semibold">{it.title}</h3>
            <p className="mt-2 text-sm text-muted-foreground leading-relaxed">{it.body}</p>
          </li>
        ))}
      </ul>
    </SectionWrap>
  );
}

function IconBadgeSection({ s }: { s: Extract<Section, { type: "icon_badge" }> }) {
  return (
    <SectionWrap>
      <div className="rounded-3xl border border-border bg-card p-8 md:p-10 ring-soft flex flex-col md:flex-row items-start md:items-center gap-6">
        <div className="inline-flex h-14 w-14 items-center justify-center rounded-2xl bg-brand-soft text-primary shrink-0">
          <Sparkles className="h-6 w-6" />
        </div>
        <div className="flex-1">
          <h3 className="text-xl md:text-2xl font-semibold">{s.title}</h3>
          {s.body && <p className="mt-2 text-muted-foreground">{s.body}</p>}
        </div>
        {s.cta_label && s.cta_href && (
          <Button asChild>
            <Link href={s.cta_href}>
              {s.cta_label} <ArrowUpRight className="h-4 w-4" />
            </Link>
          </Button>
        )}
      </div>
    </SectionWrap>
  );
}

function BigQuoteSection({ s }: { s: Extract<Section, { type: "big_quote" }> }) {
  return (
    <SectionWrap>
      <div className="max-w-3xl mx-auto text-center">
        <Quote className="h-8 w-8 text-primary mx-auto" aria-hidden />
        <blockquote className="mt-5 text-2xl md:text-3xl font-medium tracking-tight text-balance leading-snug">
          “{s.quote}”
        </blockquote>
        {(s.author || s.role) && (
          <figcaption className="mt-5 text-sm text-muted-foreground">
            {s.author}
            {s.role && <span className="text-muted-foreground/70"> — {s.role}</span>}
          </figcaption>
        )}
      </div>
    </SectionWrap>
  );
}

function FaqSection({ s }: { s: Extract<Section, { type: "faq" }> }) {
  return (
    <SectionWrap>
      {(s.title || s.subtitle) && (
        <header className="max-w-2xl">
          {s.title && (
            <h2 className="text-3xl md:text-4xl font-semibold tracking-tight">{s.title}</h2>
          )}
          {s.subtitle && <p className="mt-3 text-muted-foreground">{s.subtitle}</p>}
        </header>
      )}
      <ul className="mt-8 grid gap-3 max-w-3xl">
        {s.items.map((it, i) => (
          <li
            key={i}
            className="rounded-2xl border border-border bg-card p-5 ring-soft"
          >
            <details className="group">
              <summary className="flex items-start justify-between gap-4 cursor-pointer list-none">
                <span className="text-sm font-semibold">{it.question}</span>
                <span className="text-muted-foreground shrink-0 transition group-open:rotate-45">
                  +
                </span>
              </summary>
              <div className="mt-3 text-sm text-muted-foreground leading-relaxed">
                {it.answer}
              </div>
            </details>
          </li>
        ))}
      </ul>
    </SectionWrap>
  );
}

function StatStripSection({ s }: { s: Extract<Section, { type: "stat_strip" }> }) {
  return (
    <SectionWrap>
      {s.eyebrow && (
        <div className="text-xs uppercase tracking-wider text-primary font-semibold">
          {s.eyebrow}
        </div>
      )}
      <ul className={`mt-4 grid gap-6 ${gridForCount(s.items.length)}`}>
        {s.items.map((it, i) => (
          <li key={i}>
            <div className="text-3xl md:text-4xl font-semibold tracking-tight">
              {it.value}
            </div>
            <div className="mt-1 text-sm font-medium">{it.label}</div>
            {it.caption && (
              <div className="mt-1 text-xs text-muted-foreground">{it.caption}</div>
            )}
          </li>
        ))}
      </ul>
    </SectionWrap>
  );
}

function gridForCount(n: number): string {
  if (n <= 2) return "sm:grid-cols-2";
  if (n === 3) return "sm:grid-cols-3";
  if (n === 4) return "sm:grid-cols-2 lg:grid-cols-4";
  return "sm:grid-cols-2 lg:grid-cols-3";
}

function TestimonialsSection({ s }: { s: Extract<Section, { type: "testimonials" }> }) {
  return (
    <SectionWrap>
      {(s.eyebrow || s.title) && (
        <header className="max-w-2xl">
          {s.eyebrow && (
            <div className="text-xs uppercase tracking-wider text-primary font-semibold">
              {s.eyebrow}
            </div>
          )}
          {s.title && (
            <h2 className="mt-3 text-3xl md:text-4xl font-semibold tracking-tight">
              {s.title}
            </h2>
          )}
        </header>
      )}
      <ul className="mt-8 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
        {s.items.map((it, i) => (
          <li
            key={i}
            className="rounded-2xl border border-border bg-card p-6 ring-soft"
          >
            <div className="flex gap-1 text-accent">
              {[0, 1, 2, 3, 4].map((k) => (
                <Star key={k} className="h-3.5 w-3.5 fill-current" />
              ))}
            </div>
            <p className="mt-4 text-sm leading-relaxed">“{it.quote}”</p>
            <div className="mt-5 flex items-center gap-3">
              {it.headshot_url && (
                <Image
                  src={it.headshot_url}
                  alt={it.author}
                  width={36}
                  height={36}
                  className="rounded-full object-cover"
                />
              )}
              <div>
                <div className="text-sm font-medium">{it.author}</div>
                {(it.role || it.company) && (
                  <div className="text-xs text-muted-foreground">
                    {[it.role, it.company].filter(Boolean).join(" · ")}
                  </div>
                )}
              </div>
            </div>
          </li>
        ))}
      </ul>
    </SectionWrap>
  );
}

function TimelineSection({ s }: { s: Extract<Section, { type: "timeline" }> }) {
  return (
    <SectionWrap>
      {s.title && (
        <h2 className="text-3xl md:text-4xl font-semibold tracking-tight max-w-2xl">
          {s.title}
        </h2>
      )}
      <ol className="mt-10 grid gap-6 max-w-3xl">
        {s.items.map((it, i) => (
          <li
            key={i}
            className="relative pl-8 before:content-[''] before:absolute before:left-2 before:top-2 before:h-full before:w-px before:bg-border last:before:hidden"
          >
            <span className="absolute left-0 top-1 inline-flex h-4 w-4 items-center justify-center rounded-full bg-primary text-white">
              <CheckCircle2 className="h-3 w-3" />
            </span>
            <div className="text-xs text-muted-foreground uppercase tracking-wider">
              {it.date}
            </div>
            <h3 className="mt-1 text-base font-semibold">{it.title}</h3>
            <p className="mt-1 text-sm text-muted-foreground leading-relaxed">{it.body}</p>
          </li>
        ))}
      </ol>
    </SectionWrap>
  );
}

function ProcessStepsSection({ s }: { s: Extract<Section, { type: "process_steps" }> }) {
  return (
    <SectionWrap>
      {(s.eyebrow || s.title) && (
        <header className="max-w-2xl">
          {s.eyebrow && (
            <div className="text-xs uppercase tracking-wider text-primary font-semibold">
              {s.eyebrow}
            </div>
          )}
          {s.title && (
            <h2 className="mt-3 text-3xl md:text-4xl font-semibold tracking-tight">
              {s.title}
            </h2>
          )}
        </header>
      )}
      <ol className="mt-10 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
        {s.items.map((it, i) => (
          <li
            key={i}
            className="rounded-2xl border border-border bg-card p-6 ring-soft"
          >
            <div className="text-xs uppercase tracking-wider text-primary font-semibold">
              Step {String(i + 1).padStart(2, "0")}
            </div>
            <h3 className="mt-3 text-base font-semibold">{it.title}</h3>
            <p className="mt-2 text-sm text-muted-foreground leading-relaxed">{it.body}</p>
          </li>
        ))}
      </ol>
    </SectionWrap>
  );
}

function LogoCloudSection({ s }: { s: Extract<Section, { type: "logo_cloud" }> }) {
  return (
    <SectionWrap>
      {(s.eyebrow || s.title) && (
        <header className="max-w-2xl">
          {s.eyebrow && (
            <div className="text-xs uppercase tracking-wider text-primary font-semibold">
              {s.eyebrow}
            </div>
          )}
          {s.title && (
            <h2 className="mt-3 text-3xl md:text-4xl font-semibold tracking-tight">
              {s.title}
            </h2>
          )}
        </header>
      )}
      <ul className="mt-10 grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-6 items-center">
        {s.items.map((it, i) => (
          <li key={i} className="flex items-center justify-center">
            {it.href ? (
              <a href={it.href} target="_blank" rel="noreferrer" className="opacity-60 hover:opacity-100 transition">
                <Image src={it.logo_url} alt={it.name} width={120} height={40} className="h-10 w-auto" />
              </a>
            ) : (
              <Image src={it.logo_url} alt={it.name} width={120} height={40} className="h-10 w-auto opacity-60" />
            )}
          </li>
        ))}
      </ul>
    </SectionWrap>
  );
}

function CtaSection({ s }: { s: Extract<Section, { type: "cta" }> }) {
  return (
    <SectionWrap>
      <div className="rounded-3xl border border-border bg-ink text-white p-10 md:p-14 ring-elevated relative overflow-hidden">
        <div aria-hidden className="absolute inset-0 dot-grid opacity-[0.06]" />
        <div className="relative">
          {s.eyebrow && (
            <div className="text-xs uppercase tracking-wider text-accent font-semibold">
              {s.eyebrow}
            </div>
          )}
          <h2 className="mt-3 text-3xl md:text-4xl font-semibold tracking-tight max-w-2xl text-balance">
            {s.title}
          </h2>
          {s.subtitle && (
            <p className="mt-4 text-white/70 max-w-2xl">{s.subtitle}</p>
          )}
          <div className="mt-7 flex flex-wrap gap-2">
            {s.primary_cta_label && s.primary_cta_href && (
              <Button asChild size="lg">
                <Link href={s.primary_cta_href}>
                  {s.primary_cta_label} <ArrowUpRight className="h-4 w-4" />
                </Link>
              </Button>
            )}
            {s.secondary_cta_label && s.secondary_cta_href && (
              <Button
                asChild
                size="lg"
                variant="outline"
                className="bg-transparent border-white/30 text-white hover:bg-white/10 hover:text-white"
              >
                <Link href={s.secondary_cta_href}>{s.secondary_cta_label}</Link>
              </Button>
            )}
          </div>
        </div>
      </div>
    </SectionWrap>
  );
}

function NewsletterCtaSection({ s }: { s: Extract<Section, { type: "newsletter_cta" }> }) {
  return (
    <SectionWrap>
      <div className="rounded-3xl border border-border bg-card p-8 md:p-10 ring-soft">
        {s.eyebrow && (
          <div className="text-xs uppercase tracking-wider text-primary font-semibold">
            {s.eyebrow}
          </div>
        )}
        {s.title && (
          <h2 className="mt-3 text-2xl md:text-3xl font-semibold tracking-tight">{s.title}</h2>
        )}
        {s.subtitle && (
          <p className="mt-2 text-muted-foreground max-w-2xl">{s.subtitle}</p>
        )}
        <div className="mt-6">
          <NewsletterSignup />
        </div>
      </div>
    </SectionWrap>
  );
}

function RichTextSection({ s }: { s: Extract<Section, { type: "rich_text" }> }) {
  const widthClass =
    s.width === "narrow" ? "max-w-2xl" : s.width === "wide" ? "max-w-5xl" : "max-w-3xl";
  // Server-rendered markdown via the shared `lib/markdown.ts` helper. Same
  // formatter the admin preview uses, so what the boss sees in the editor
  // matches the published page.
  const html = renderMarkdownToHtml(s.body);
  return (
    <SectionWrap>
      <article
        className={`${widthClass} text-foreground/90 text-[15px] md:text-base`}
        dangerouslySetInnerHTML={{ __html: html }}
      />
    </SectionWrap>
  );
}

function ImageTextSection({ s }: { s: Extract<Section, { type: "image_text" }> }) {
  const right = (s.image_position ?? "right") === "right";
  return (
    <SectionWrap>
      <div className="grid lg:grid-cols-2 gap-10 items-center">
        <div className={right ? "lg:order-1" : "lg:order-2"}>
          {s.eyebrow && (
            <div className="text-xs uppercase tracking-wider text-primary font-semibold">
              {s.eyebrow}
            </div>
          )}
          {s.title && (
            <h2 className="mt-3 text-3xl md:text-4xl font-semibold tracking-tight">
              {s.title}
            </h2>
          )}
          <div
            className="mt-4 text-muted-foreground leading-relaxed"
            dangerouslySetInnerHTML={{ __html: renderMarkdownToHtml(s.body) }}
          />
        </div>
        {s.image_url && (
          <div className={`relative aspect-[4/3] rounded-2xl overflow-hidden ring-elevated bg-secondary ${right ? "lg:order-2" : "lg:order-1"}`}>
            <Image src={s.image_url} alt={s.title ?? ""} fill className="object-cover" />
          </div>
        )}
      </div>
    </SectionWrap>
  );
}
