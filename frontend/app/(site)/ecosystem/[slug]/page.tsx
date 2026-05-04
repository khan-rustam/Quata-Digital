import { notFound } from "next/navigation";
import Image from "next/image";
import Link from "next/link";
import type { Metadata } from "next";
import {
  ArrowRight,
  ArrowUpRight,
  Check,
  Wallet,
  Zap,
  ShieldCheck,
  Code2,
  HeadphonesIcon as Headphones,
  Sparkles,
} from "lucide-react";
import { products, getProduct } from "@/lib/ecosystem";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Section, SectionHeader } from "@/components/site/section";
import { StatStrip } from "@/components/site/sections/stat-strip";
import { FaqWithAside } from "@/components/site/sections/faq-with-aside";
import { ProcessSteps } from "@/components/site/sections/process-steps";
import { FinalCTA } from "@/components/site/cta";
import { JsonLd, productJsonLd, breadcrumbJsonLd } from "@/components/site/jsonld";
import { cn } from "@/lib/utils";

const statusVariant = {
  Live: "live",
  Beta: "beta",
  "Coming Soon": "soon",
  Planned: "outline",
} as const;

export function generateStaticParams() {
  return products.map((p) => ({ slug: p.slug }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const product = getProduct(slug);
  if (!product) return {};
  return {
    title: product.name,
    description: product.shortDescription,
    openGraph: {
      title: `${product.name} — QUATA Digital`,
      description: product.shortDescription,
      images: [{ url: product.logo, width: 256, height: 256, alt: product.name }],
    },
  };
}

export default async function ProductPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const product = getProduct(slug);
  if (!product) return notFound();

  const others = products.filter((p) => p.slug !== slug).slice(0, 3);

  return (
    <>
      <JsonLd data={productJsonLd(product)} />
      <JsonLd
        data={breadcrumbJsonLd([
          { name: "Home", href: "/" },
          { name: "Ecosystem", href: "/ecosystem" },
          { name: product.name, href: `/ecosystem/${product.slug}` },
        ])}
      />

      {/* 1. Hero — clean light surface with a colour halo behind the logo.
            -mt-20 pulls the gradient up behind the floating navbar so the
            page never shows a stripe of white above the hero. */}
      <section className="relative overflow-hidden -mt-20">
        <div className="absolute inset-0 -z-10 bg-linear-to-b from-brand-soft/40 via-surface to-surface" />
        <div className="absolute inset-0 -z-10 dot-grid mask-fade-b opacity-40" />
        {/* Soft brand-tinted halo top-right */}
        <div
          aria-hidden
          className={cn(
            "absolute -top-32 -right-32 -z-10 h-112 w-md rounded-full opacity-20 blur-3xl bg-linear-to-br",
            product.accent
          )}
        />
        {/* Soft amber accent bottom-left */}
        <div
          aria-hidden
          className="absolute -bottom-40 -left-32 -z-10 h-104 w-104 rounded-full opacity-15 blur-3xl"
          style={{
            background: "radial-gradient(closest-side, rgba(232,177,74,0.6), transparent)",
          }}
        />

        <div className="container-page pt-36 md:pt-44 pb-16 md:pb-20">
          {/* Breadcrumb pill */}
          <Link
            href="/ecosystem"
            className="inline-flex items-center gap-1.5 rounded-full border border-border bg-card/80 backdrop-blur px-3 py-1 text-xs text-muted-foreground hover:text-foreground transition"
          >
            <ArrowRight className="h-3 w-3 rotate-180" />
            Back to ecosystem
          </Link>

          <div className="mt-8 grid lg:grid-cols-[1.1fr_0.9fr] gap-12 lg:gap-16 items-center">
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant={statusVariant[product.status]}>{product.status}</Badge>
                <Badge variant="outline">{product.category}</Badge>
                {product.launch && (
                  <span className="inline-flex items-center gap-1.5 rounded-full border border-border bg-card px-2.5 py-1 text-[11px] font-medium text-muted-foreground">
                    <Sparkles className="h-3 w-3 text-primary" />
                    {product.launch}
                  </span>
                )}
              </div>
              <h1 className="mt-6 text-4xl md:text-6xl lg:text-7xl font-semibold tracking-tight text-foreground text-balance leading-[1.05]">
                {product.name}
              </h1>
              <p className="mt-5 max-w-xl text-lg md:text-xl text-foreground/80 leading-relaxed">
                {product.tagline}
              </p>
              <p className="mt-3 max-w-xl text-sm text-muted-foreground leading-relaxed">
                {product.shortDescription}
              </p>

              <div className="mt-8 flex flex-wrap gap-3">
                <Button size="lg" asChild>
                  <Link href="/contact">
                    Talk to the team <ArrowRight className="h-4 w-4" />
                  </Link>
                </Button>
                <Button size="lg" variant="outline" asChild>
                  <Link href="/partners">Become a partner</Link>
                </Button>
              </div>

              {/* Quick highlights preview — 3 chips */}
              {product.highlights.length > 0 && (
                <ul className="mt-8 flex flex-wrap gap-2">
                  {product.highlights.slice(0, 3).map((h) => (
                    <li
                      key={h}
                      className="inline-flex items-center gap-1.5 rounded-full border border-border bg-card px-3 py-1.5 text-xs text-muted-foreground"
                    >
                      <Check className="h-3 w-3 text-primary" />
                      {h}
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <div className="relative mx-auto w-full max-w-md">
              {/* Accent halo behind the card */}
              <div
                aria-hidden
                className={cn(
                  "absolute -inset-8 -z-10 rounded-4xl bg-linear-to-br opacity-25 blur-3xl",
                  product.accent
                )}
              />
              {/* Floating decorative dot ring top-right of card */}
              <div
                aria-hidden
                className="absolute -top-3 -right-3 h-20 w-20 rounded-full border border-border bg-card/60 backdrop-blur ring-soft"
              />
              {/* Logo card — clean white with soft 3D shadow */}
              <div className="relative aspect-square rounded-3xl bg-card border border-border p-10 flex items-center justify-center shadow-[0_30px_80px_-30px_rgba(15,18,22,0.25),0_8px_24px_-12px_rgba(15,18,22,0.12),inset_0_1px_0_rgba(255,255,255,0.8)]">
                <Image
                  src={product.logo}
                  alt={`${product.name} logo`}
                  width={512}
                  height={512}
                  priority
                  className="w-full h-full object-contain"
                />
              </div>
              {/* "Built on QUATA rail" badge floating at bottom */}
              <div className="absolute left-1/2 -bottom-4 -translate-x-1/2">
                <span className="inline-flex items-center gap-1.5 rounded-full border border-border bg-card px-3 py-1.5 text-[11px] font-semibold text-foreground shadow-md">
                  <span className="inline-block h-1.5 w-1.5 rounded-full bg-emerald-500" />
                  Built on the QUATA rail
                </span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* 2. Overview + sticky aside */}
      <Section className="pt-12">
        <div className="grid lg:grid-cols-3 gap-8">
          <div className="lg:col-span-2">
            <h2 className="text-2xl md:text-3xl font-semibold tracking-tight">Overview</h2>
            <p className="mt-4 text-muted-foreground text-lg leading-relaxed">
              {product.description}
            </p>

            <div className="mt-10 grid sm:grid-cols-3 gap-3">
              {product.highlights.map((h) => (
                <div
                  key={h}
                  className="flex items-start gap-2 rounded-xl border border-border bg-surface p-4 text-sm"
                >
                  <Check className="mt-0.5 h-4 w-4 text-primary shrink-0" />
                  <span>{h}</span>
                </div>
              ))}
            </div>
          </div>

          <aside className="lg:sticky lg:top-24 self-start space-y-4">
            <div className="rounded-2xl border border-border bg-surface-soft p-6">
              <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Status
              </div>
              <div className="mt-2 text-base font-medium">{product.status}</div>
              <div className="mt-4 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Category
              </div>
              <div className="mt-2 text-base font-medium">{product.category}</div>
              {product.pricing && (
                <>
                  <div className="mt-4 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                    Pricing
                  </div>
                  <div className="mt-2 text-sm">{product.pricing}</div>
                </>
              )}
              {product.launch && (
                <>
                  <div className="mt-4 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                    Availability
                  </div>
                  <div className="mt-2 text-sm">{product.launch}</div>
                </>
              )}
              <div className="mt-6">
                <Button asChild className="w-full">
                  <Link href="/contact">
                    Get in touch <ArrowRight className="h-4 w-4" />
                  </Link>
                </Button>
              </div>
            </div>

            <div className="rounded-2xl border border-border bg-card p-6">
              <div className="flex items-center gap-2 text-sm font-medium">
                <Wallet className="h-4 w-4 text-primary" />
                Built on the QUATA rail
              </div>
              <p className="mt-2 text-sm text-muted-foreground">
                Every product shares the same wallet, identity and logistics
                layer — so an action in one product always settles cleanly in
                the rest.
              </p>
              <Link
                href="/#how-it-works"
                className="mt-4 inline-flex items-center gap-1.5 text-sm font-medium text-primary"
              >
                See how it works
                <ArrowUpRight className="h-3.5 w-3.5" />
              </Link>
            </div>
          </aside>
        </div>
      </Section>

      {/* 3. Feature deep-dive */}
      <Section className="bg-surface-soft rounded-3xl">
        <SectionHeader
          eyebrow="What you get"
          title={`Inside ${product.name}.`}
          subtitle="The capabilities that ship today, and the design choices behind them."
        />
        <div className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {product.features.length > 0 ? (
            product.features.map((f, i) => (
              <div
                key={f.title}
                className="rounded-2xl border border-border bg-card p-6 ring-soft"
              >
                <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Feature {String(i + 1).padStart(2, "0")}
                </div>
                <div className="mt-3 text-base font-semibold tracking-tight">
                  {f.title}
                </div>
                <p className="mt-2 text-sm text-muted-foreground leading-relaxed">
                  {f.body}
                </p>
              </div>
            ))
          ) : (
            <div className="lg:col-span-3 rounded-2xl border border-dashed border-border p-10 text-center text-muted-foreground text-sm">
              Detailed feature breakdown coming soon.
            </div>
          )}
        </div>
      </Section>

      {/* 4. Use cases */}
      {product.useCases.length > 0 && (
        <Section>
          <SectionHeader
            eyebrow="Use cases"
            title={`Who ships with ${product.name}.`}
            subtitle="A few of the most common ways teams put this product to work."
          />
          <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {product.useCases.map((u, i) => (
              <div
                key={u.title}
                className="rounded-2xl border border-border bg-card p-6 ring-soft"
              >
                <div
                  className={cn(
                    "inline-flex h-8 w-8 items-center justify-center rounded-full text-white text-xs font-semibold bg-linear-to-br",
                    product.accent
                  )}
                >
                  {i + 1}
                </div>
                <div className="mt-4 text-base font-semibold tracking-tight">
                  {u.title}
                </div>
                <p className="mt-2 text-sm text-muted-foreground leading-relaxed">
                  {u.body}
                </p>
              </div>
            ))}
          </div>
        </Section>
      )}

      {/* 5. Stats */}
      {product.metrics.length > 0 && (
        <Section className="py-12 md:py-16">
          <StatStrip
            variant="card"
            items={product.metrics.map((m, i) => ({
              value: m.value,
              label: m.label,
              icon: i === 0 ? Zap : i === 1 ? ShieldCheck : i === 2 ? Code2 : Wallet,
            }))}
          />
        </Section>
      )}

      {/* 6. Ecosystem fit / integrations */}
      {product.integrations.length > 0 && (
        <Section className="bg-surface-soft rounded-3xl">
          <SectionHeader
            eyebrow="Ecosystem fit"
            title={`How ${product.name} connects.`}
            subtitle="Each integration is wired in as a primitive — not glued on with webhooks after the fact."
          />
          <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {product.integrations.map((it) => (
              <Link
                key={it.name}
                href={`/ecosystem/${it.name.toLowerCase().split(" ")[0]}`}
                className="group rounded-2xl border border-border bg-card p-6 ring-soft transition hover:-translate-y-0.5"
              >
                <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Connects with
                </div>
                <div className="mt-2 flex items-center justify-between">
                  <div className="text-base font-semibold tracking-tight">
                    {it.name}
                  </div>
                  <ArrowUpRight className="h-4 w-4 text-muted-foreground transition group-hover:text-primary group-hover:-translate-y-0.5 group-hover:translate-x-0.5" />
                </div>
                <p className="mt-3 text-sm text-muted-foreground leading-relaxed">
                  {it.body}
                </p>
              </Link>
            ))}
          </div>
        </Section>
      )}

      {/* 7. Get started — process */}
      <Section>
        <SectionHeader
          eyebrow="Get started"
          title="From conversation to live in weeks, not quarters."
        />
        <div className="mt-10">
          <ProcessSteps
            steps={[
              {
                icon: Headphones,
                title: "Talk to us",
                body: "A 30-minute scoping call to understand your stack, geography and goals.",
                duration: "Same week",
              },
              {
                icon: Code2,
                title: "Sandbox access",
                body: "Get API keys and a fully working sandbox to test the integration end-to-end.",
                duration: "Day 1",
              },
              {
                icon: ShieldCheck,
                title: "Compliance & due diligence",
                body: "Run KYB, security review and contract in parallel with engineering work.",
                duration: "1–3 weeks",
              },
              {
                icon: Zap,
                title: "Go live",
                body: "Phased rollout with a named QUATA partner success lead.",
                duration: "Production",
              },
            ]}
          />
        </div>
      </Section>

      {/* 8. FAQ */}
      {product.faqs.length > 0 && (
        <Section className="bg-surface-soft rounded-3xl">
          <SectionHeader
            eyebrow="FAQ"
            title={`${product.name} — what people ask first.`}
          />
          <div className="mt-10">
            <FaqWithAside
              items={product.faqs}
              asideTitle={`Talk to the ${product.name} team`}
              asideBody={`Building with ${product.name}? Tell us your scenario — we&apos;ll point you at the right resources or set up a sandbox.`}
              asideEmail="info@quatadigital.com"
              asideStats={[
                { value: product.status, label: "Status" },
                { value: product.launch ?? "TBA", label: "Availability" },
              ]}
            />
          </div>
        </Section>
      )}

      {/* 9. Other products */}
      <Section>
        <div className="flex items-end justify-between gap-4">
          <SectionHeader
            eyebrow="Explore more"
            title="Other products in the ecosystem"
          />
          <Link
            href="/ecosystem"
            className="text-sm font-medium text-primary inline-flex items-center gap-1 shrink-0"
          >
            See all <ArrowRight className="h-3.5 w-3.5" />
          </Link>
        </div>
        <div className="mt-8 grid sm:grid-cols-2 lg:grid-cols-3 gap-5">
          {others.map((p) => (
            <Link
              key={p.slug}
              href={`/ecosystem/${p.slug}`}
              className="group rounded-2xl border border-border bg-card ring-soft transition hover:-translate-y-0.5 hover:border-primary/30 overflow-hidden flex flex-col"
            >
              <div className="flex items-center justify-between px-5 pt-4">
                <span className="text-[11px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">
                  {p.category}
                </span>
                <ArrowRight className="h-3.5 w-3.5 text-muted-foreground transition group-hover:text-primary group-hover:translate-x-0.5" />
              </div>
              <div className="mx-5 mt-3 rounded-xl bg-surface-soft border border-border/60 h-24 flex items-center justify-center px-5">
                <Image
                  src={p.logo}
                  alt={`${p.name} logo`}
                  width={300}
                  height={200}
                  className="max-h-16 w-auto object-contain transition-transform duration-300 group-hover:scale-105"
                />
              </div>
              <div className="px-5 pt-4 pb-5">
                <div className="text-sm text-muted-foreground line-clamp-2">
                  {p.shortDescription}
                </div>
                <div className="mt-3 inline-flex items-center gap-1.5 text-xs font-medium text-primary">
                  Learn more
                  <ArrowRight className="h-3 w-3 transition group-hover:translate-x-0.5" />
                </div>
              </div>
            </Link>
          ))}
        </div>
      </Section>

      {/* 10. CTA */}
      <Section>
        <FinalCTA />
      </Section>
    </>
  );
}
