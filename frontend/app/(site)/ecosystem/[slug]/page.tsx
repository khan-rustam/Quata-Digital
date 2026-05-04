import { notFound } from "next/navigation";
import Link from "next/link";
import type { Metadata } from "next";
import {
  ArrowRight,
  ArrowUpRight,
  Check,
  Wallet,
  Zap,
  ShieldCheck,
  Globe2,
  Code2,
  HeadphonesIcon as Headphones,
  Users,
  Layers,
  Building2,
  TrendingUp,
} from "lucide-react";
import { products, getProduct } from "@/lib/ecosystem";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Section, SectionHeader } from "@/components/site/section";
import { FeatureGrid } from "@/components/site/sections/feature-grid";
import { StatStrip } from "@/components/site/sections/stat-strip";
import { FAQ } from "@/components/site/sections/faq";
import { ProcessSteps } from "@/components/site/sections/process-steps";
import { FinalCTA } from "@/components/site/cta";
import { JsonLd, productJsonLd, breadcrumbJsonLd } from "@/components/site/jsonld";
import { BrandImage } from "@/components/site/brand-image";
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
    description: product.tagline,
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
      {/* 1. Hero — 2-col with product mockup on the right */}
      <section className="relative overflow-hidden">
        <div
          className={cn(
            "absolute inset-x-0 top-0 -z-10 h-140 bg-linear-to-br opacity-90",
            product.accent
          )}
        />
        <div className="absolute inset-0 -z-10 mask-fade-b dot-grid opacity-20" />
        <div className="container-page pt-16 md:pt-24 pb-14 text-white">
          <div className="flex items-center gap-2 text-sm">
            <Link href="/ecosystem" className="text-white/70 hover:text-white">
              Ecosystem
            </Link>
            <span className="text-white/50">/</span>
            <span>{product.name}</span>
          </div>
          <div className="mt-8 grid lg:grid-cols-2 gap-10 lg:gap-16 items-center">
            <div>
              <div className="flex flex-wrap items-center gap-3">
                <Badge variant={statusVariant[product.status]}>{product.status}</Badge>
                <Badge variant="outline" className="border-white/30 text-white">
                  {product.category}
                </Badge>
              </div>
              <h1 className="mt-5 text-4xl md:text-6xl font-semibold tracking-tight">
                {product.name}
              </h1>
              <p className="mt-4 max-w-xl text-lg text-white/85">{product.tagline}</p>
              <div className="mt-8 flex flex-wrap gap-3">
                <Button size="lg" variant="accent" asChild>
                  <Link href="/contact">
                    Talk to the team <ArrowRight className="h-4 w-4" />
                  </Link>
                </Button>
                <Button
                  size="lg"
                  variant="outline"
                  asChild
                  className="bg-white/0 text-white border-white/30 hover:bg-white/10 hover:text-white"
                >
                  <Link href="/partners">Become a partner</Link>
                </Button>
              </div>
            </div>
            <BrandImage
              src={`/images/ecosystem/${product.slug}/hero.jpg`}
              alt={`${product.name} product preview`}
              width={1200}
              height={900}
              accent="ink"
              priority
            />
          </div>
        </div>
      </section>

      {/* 2. Overview + sticky aside */}
      <Section className="pt-12">
        <div className="grid lg:grid-cols-3 gap-8">
          <div className="lg:col-span-2">
            <h2 className="text-2xl md:text-3xl font-semibold tracking-tight">Overview</h2>
            <p className="mt-4 text-muted-foreground text-lg">{product.description}</p>

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
                Every product shares the same wallet, identity and logistics layer
                — so an action in one product always settles cleanly in the rest.
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
        <div className="mt-12 grid gap-4 lg:grid-cols-3">
          {product.features.length > 0 ? (
            product.features.map((f, i) => (
              <div key={f.title} className="rounded-2xl border border-border bg-card p-6 ring-soft">
                <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Feature 0{i + 1}
                </div>
                <div className="mt-3 text-base font-semibold tracking-tight">{f.title}</div>
                <p className="mt-2 text-sm text-muted-foreground">{f.body}</p>
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
      <Section>
        <SectionHeader
          eyebrow="Use cases"
          title={`Who ships with ${product.name}.`}
          subtitle="A few of the most common ways teams put this product to work."
        />
        <div className="mt-12">
          <FeatureGrid
            columns={3}
            variant="bordered"
            items={[
              {
                icon: Building2,
                title: "Established businesses",
                body: `Switch from fragmented vendors to a single rail — without rebuilding the back office.`,
                tone: "brand",
              },
              {
                icon: Users,
                title: "Growth-stage startups",
                body: `Ship faster with one API, one dashboard and one settlement window across products.`,
                tone: "amber",
              },
              {
                icon: TrendingUp,
                title: "Platforms & marketplaces",
                body: `Embed ${product.name} into your stack and pass the leverage to your customers.`,
                tone: "sky",
              },
            ]}
          />
        </div>
      </Section>

      {/* 5. Stats */}
      <Section className="py-12 md:py-16">
        <StatStrip
          variant="card"
          items={[
            { value: "<1s", label: "Wallet transfer", icon: Zap },
            { value: "99.95%", label: "Operational uptime SLA", icon: ShieldCheck },
            { value: "20+", label: "Markets in scope", icon: Globe2 },
            { value: "1 API", label: "End-to-end coverage", icon: Code2 },
          ]}
        />
      </Section>

      {/* 6. Get started — process */}
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

      {/* 7. FAQ */}
      <Section className="bg-surface-soft rounded-3xl">
        <SectionHeader eyebrow="FAQ" title={`${product.name} — what people ask first.`} />
        <div className="mt-10 max-w-3xl">
          <FAQ
            items={[
              {
                q: "Is there a public sandbox?",
                a: "Yes. Once you're approved as a partner, you get isolated sandbox keys and can simulate full transaction flows.",
              },
              {
                q: "How is pricing structured?",
                a: "Pricing depends on volume, geography and product mix. We publish indicative ranges in the partner pack — talk to us for a quote that matches your scenario.",
              },
              {
                q: `Can I use ${product.name} without the rest of QUATA?`,
                a: `Yes. Each product is independently usable. The benefits compound when you adopt more than one, but adoption is your call.`,
              },
              {
                q: "What's the typical integration time?",
                a: "Most teams are live within 2–6 weeks depending on product and geography.",
              },
              {
                q: "Where is data hosted?",
                a: "Production data is hosted in-region for compliance. Specific regions are confirmed during onboarding.",
              },
            ]}
          />
        </div>
      </Section>

      {/* 8. Other products */}
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
              className="group rounded-2xl border border-border bg-card p-5 ring-soft transition hover:-translate-y-0.5"
            >
              <div className={cn("h-2 w-12 rounded-full bg-linear-to-r", p.accent)} />
              <div className="mt-4 text-base font-semibold tracking-tight">{p.name}</div>
              <div className="mt-1 text-sm text-muted-foreground">{p.tagline}</div>
              <div className="mt-4 inline-flex items-center gap-1.5 text-xs font-medium text-primary">
                Learn more
                <ArrowRight className="h-3 w-3 transition group-hover:translate-x-0.5" />
              </div>
            </Link>
          ))}
        </div>
      </Section>

      {/* 9. CTA */}
      <Section>
        <FinalCTA />
      </Section>
    </>
  );
}
