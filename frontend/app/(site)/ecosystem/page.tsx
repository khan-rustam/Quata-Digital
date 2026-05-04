import type { Metadata } from "next";
import Link from "next/link";
import {
  Wallet,
  Layers3,
  ShoppingCart,
  Building2,
  Heart,
  ShieldCheck,
  KeyRound,
  Activity,
  Sparkles,
  Network,
} from "lucide-react";
import { Section, SectionHeader } from "@/components/site/section";
import { EcosystemGrid } from "@/components/site/ecosystem-grid";
import { FeatureGrid } from "@/components/site/sections/feature-grid";
import { StatStrip } from "@/components/site/sections/stat-strip";
import { CoverageMap } from "@/components/site/sections/coverage-map";
import { FAQ } from "@/components/site/sections/faq";
import { ComparisonTable } from "@/components/site/sections/comparison";
import { FinalCTA } from "@/components/site/cta";
import { products } from "@/lib/ecosystem";

export const metadata: Metadata = {
  title: "Ecosystem",
  description:
    "Explore the QUATA Digital ecosystem — payments, business operations and commerce, all on one rail.",
};

const categories = [
  { name: "Payments", icon: Wallet, slugs: ["quatapay"] },
  { name: "Business operations", icon: Layers3, slugs: ["abaqwa"] },
  { name: "Commerce", icon: ShoppingCart, slugs: ["quatafood", "88basket", "o3mall"] },
  { name: "Real Estate", icon: Building2, slugs: ["88brickz"] },
  { name: "Health", icon: Heart, slugs: ["qmediq"] },
];

export default function EcosystemIndexPage() {
  return (
    <>
      {/* 1. Hero header */}
      <section className="relative overflow-hidden">
        <div className="absolute inset-0 -z-10 bg-linear-to-b from-brand-soft/40 via-surface to-surface" />
        <div className="absolute inset-0 -z-10 dot-grid mask-fade-b opacity-50" />
        <div className="container-page py-14 sm:py-20 md:py-28">
          <div className="inline-flex items-center gap-2 rounded-full border border-border bg-surface/80 px-3 py-1 text-xs text-muted-foreground backdrop-blur">
            <Sparkles className="h-3.5 w-3.5 text-primary" />
            The ecosystem
          </div>
          <h1 className="mt-6 text-3xl sm:text-4xl md:text-6xl font-semibold tracking-tight max-w-3xl text-balance">
            One ecosystem. <span className="text-gradient-brand">Many doorways.</span>
          </h1>
          <p className="mt-5 max-w-2xl text-lg text-muted-foreground">
            Each product is built with the others in mind. Pick the one closest to
            your need — or build with all of them.
          </p>
        </div>
      </section>

      {/* 2. Categories pill bar */}
      <Section className="py-10">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs uppercase tracking-wider text-muted-foreground mr-2">Browse by</span>
          {categories.map((c) => (
            <span
              key={c.name}
              className="inline-flex items-center gap-1.5 rounded-full border border-border bg-card px-3 py-1.5 text-xs"
            >
              <c.icon className="h-3.5 w-3.5 text-primary" />
              {c.name}
              <span className="text-muted-foreground">· {c.slugs.length}</span>
            </span>
          ))}
        </div>
      </Section>

      {/* 3. Product grid */}
      <Section className="pt-0">
        <EcosystemGrid />
      </Section>

      {/* 4. Stats strip */}
      <Section className="py-12 md:py-16">
        <StatStrip
          variant="card"
          items={[
            { value: products.filter((p) => p.status === "Beta").length.toString(), label: "In beta (May 2026)", icon: Sparkles },
            { value: products.filter((p) => p.status === "Coming Soon").length.toString(), label: "Coming soon", icon: Activity },
            { value: products.filter((p) => p.status === "Planned").length.toString(), label: "Planned", icon: KeyRound },
            { value: "1", label: "Shared wallet", icon: Wallet },
          ]}
        />
      </Section>

      {/* 5. How the ecosystem connects */}
      <Section className="bg-surface-soft rounded-3xl">
        <SectionHeader
          eyebrow="How it connects"
          title="Three layers, one rail."
          subtitle="The architecture is intentional — every product sits on a shared base of identity, settlement and logistics."
        />
        <div className="mt-10 grid lg:grid-cols-3 gap-5">
          <LayerCard
            level="Layer 01"
            title="Payments base"
            desc="QUATAPAY moves money — wallets, settlement, issuing, acceptance."
            icon={Wallet}
            tint="from-emerald-700 to-emerald-500"
          />
          <LayerCard
            level="Layer 02"
            title="Business operations"
            desc="ABAQWA helps businesses manage operations, sales and analytics from one system."
            icon={Layers3}
            tint="from-amber-500 to-amber-300"
          />
          <LayerCard
            level="Layer 03"
            title="Commerce surfaces"
            desc="QUATAFOOD, 88BASKET, O3MALL, 88BRICKZ, QMEDIQ deliver experiences."
            icon={ShoppingCart}
            tint="from-sky-600 to-cyan-400"
          />
        </div>
      </Section>

      {/* 6. Why one rail (comparison) */}
      <Section>
        <SectionHeader
          eyebrow="Why one rail"
          title="Connected ecosystem vs standalone tools."
          subtitle="The shape of the system changes the economics. Here&rsquo;s what shifts when payments, business operations and commerce share a foundation."
        />
        <div className="mt-10">
          <ComparisonTable
            rows={[
              { label: "Customer identity", standalone: "One per app", quata: "Shared across products" },
              { label: "Wallet balance", standalone: "Each product separate", quata: "One balance everywhere" },
              { label: "Compliance & KYC", standalone: "Repeated per vendor", quata: "Reused across the rail" },
              { label: "Settlement window", standalone: "Varies by network", quata: "Targeting same-day on supported corridors" },
              { label: "Cross-product loyalty", standalone: false, quata: true },
              { label: "Vendor contracts", standalone: "Several per stack", quata: "One" },
              { label: "Time to launch a new product on the rail", standalone: "Months", quata: "Weeks" },
            ]}
          />
          <p className="mt-4 text-xs text-muted-foreground max-w-3xl">
            Comparison reflects how the QUATA ecosystem is designed.
            Settlement windows, loyalty mechanics and onboarding timelines
            depend on the partner network and product mix at launch.
          </p>
        </div>
      </Section>

      {/* 7. Trust & security */}
      <Section>
        <SectionHeader
          eyebrow="Trust & security"
          title="Designed to be safe by default."
          subtitle="Every product on the ecosystem inherits the same security baseline, audit trail and operational controls."
        />
        <div className="mt-10">
          <FeatureGrid
            columns={4}
            variant="bordered"
            items={[
              { icon: ShieldCheck, title: "Encrypted in transit and at rest", body: "TLS everywhere, envelope encryption for sensitive fields.", tone: "emerald" },
              { icon: KeyRound, title: "Fine-grained RBAC", body: "Per-permission scopes for every staff and partner role.", tone: "brand" },
              { icon: Activity, title: "Full audit trail", body: "Every admin action attributed and queryable.", tone: "amber" },
              { icon: Network, title: "Compliance ready", body: "PCI-DSS scope minimised, regional data residency available.", tone: "sky" },
            ]}
          />
        </div>
      </Section>

      {/* 8. Coverage */}
      <Section>
        <SectionHeader
          eyebrow="Where we operate"
          title="Live, expanding and on the roadmap."
          subtitle="QUATA serves customers across the continent, with rolling expansion through 2026 and 2027."
        />
        <div className="mt-10">
          <CoverageMap />
        </div>
      </Section>

      {/* 9. FAQ */}
      <Section>
        <SectionHeader
          eyebrow="FAQ"
          title="Things builders ask first."
        />
        <div className="mt-10 max-w-3xl">
          <FAQ
            items={[
              {
                q: "Do I have to use every product to use one?",
                a: "No. Every product can be adopted independently. The benefits compound when you use more than one — but that's a choice, not a requirement.",
              },
              {
                q: "Can I integrate at the rail level instead of using the products?",
                a: "Yes — strategic partners (banks, telcos, large platforms) typically integrate at the API and wallet layer. Talk to us via the Partner gateway.",
              },
              {
                q: "What's the difference between QUATAPAY and the other products?",
                a: "QUATAPAY is the payments rail beneath everything. Every other product settles on it. You can use QUATAPAY without any of the other products, but the other products always sit on QUATAPAY.",
              },
              {
                q: "How do you handle multi-currency settlement?",
                a: "QUATAPAY supports multi-currency wallets with intraday settlement on supported corridors and FX at transparent rates.",
              },
              {
                q: "Is there a public API?",
                a: "Yes. APIs are documented under each product. Strategic partners get extended access at the platform layer.",
              },
            ]}
          />
        </div>
      </Section>

      {/* 10. Final CTA */}
      <Section>
        <FinalCTA />
      </Section>
    </>
  );
}

function LayerCard({
  level,
  title,
  desc,
  icon: Icon,
  tint,
}: {
  level: string;
  title: string;
  desc: string;
  icon: typeof Wallet;
  tint: string;
}) {
  return (
    <div className="relative overflow-hidden rounded-2xl border border-border bg-card p-6 ring-soft">
      <div className={`absolute -right-10 -top-10 h-32 w-32 rounded-full opacity-20 blur-2xl bg-linear-to-br ${tint}`} />
      <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">{level}</div>
      <div className="mt-3 flex items-center gap-3">
        <span className={`inline-flex h-10 w-10 items-center justify-center rounded-xl text-white bg-linear-to-br ${tint}`}>
          <Icon className="h-5 w-5" />
        </span>
        <div className="text-lg font-semibold tracking-tight">{title}</div>
      </div>
      <p className="mt-4 text-sm text-muted-foreground">{desc}</p>
    </div>
  );
}
