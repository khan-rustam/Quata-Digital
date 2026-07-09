import type { Metadata } from "next";
import { buildMetadata } from "@/lib/seo-engine";
import {
  Layers,
  Network,
  ShieldCheck,
  Globe2,
  Sparkles,
  Wallet,
  Zap,
  Users,
  TrendingUp,
  Building2,
  HeartHandshake,
  Rocket,
} from "lucide-react";
import { Hero } from "@/components/site/hero";
import { Section, SectionHeader } from "@/components/site/section";
import { EcosystemGrid } from "@/components/site/ecosystem-grid";
import { HowItWorks } from "@/components/site/how-it-works";
import { PartnerPreview } from "@/components/site/partner-preview";
import { FinalCTA } from "@/components/site/cta";
import { StatStrip } from "@/components/site/sections/stat-strip";
import { FeatureGrid } from "@/components/site/sections/feature-grid";
import { BigQuote } from "@/components/site/sections/big-quote";
import { CoverageMap } from "@/components/site/sections/coverage-map";
import { SectionRenderer } from "@/components/site/sections/section-renderer";
import { getPageContent } from "@/lib/page-content";

export function generateMetadata(): Promise<Metadata> {
  // Empty fallback: with the engine down/empty this is a no-op and the root
  // layout's metadata stands; once the tenant has page data the engine drives it.
  return buildMetadata("/", {});
}

export default async function HomePage() {
  // CMS-first: if the boss has published sections for the home page, render
  // those. Otherwise fall back to the curated static layout below — the live
  // site keeps working exactly as it does today until they publish in admin.
  const cms = await getPageContent("home");
  if (cms) {
    return <SectionRenderer sections={cms.sections} />;
  }
  return (
    <>
      {/* 1. Hero */}
      <Hero />

      {/* 2. Why QUATA — value pillars */}
      <Section>
        <SectionHeader
          eyebrow="Why QUATA"
          title="Built differently — on purpose."
          subtitle="Most platforms ship one product and stop. QUATA is engineered as one rail so every additional product makes the rest cheaper, faster and more useful."
        />
        <div className="mt-12">
          <FeatureGrid
            items={[
              {
                icon: Layers,
                title: "One rail, many products",
                body: "Payments, business operations and commerce surfaces share the same identity, wallet and infrastructure.",
                tone: "brand",
              },
              {
                icon: Network,
                title: "Network compounding",
                body: "Each new product on the rail strengthens the rest. The 7th product is cheaper to build than the 1st.",
                tone: "amber",
              },
              {
                icon: ShieldCheck,
                title: "Trust by default",
                body: "Compliance, fraud monitoring and audit trails are core primitives — not bolt-ons.",
                tone: "emerald",
              },
              {
                icon: Globe2,
                title: "Built for African scale",
                body: "Designed for the multi-currency, multi-rail, low-bandwidth realities of doing business across the continent.",
                tone: "sky",
              },
              {
                icon: Zap,
                title: "Operator-grade performance",
                body: "Reliable wallet transfers, predictable settlement and a uniform API surface across products.",
                tone: "violet",
              },
              {
                icon: HeartHandshake,
                title: "Open to partners",
                body: "Banks, telcos, fleets and merchants integrate at the rail — not above it.",
                tone: "rose",
              },
            ]}
          />
        </div>
      </Section>

      {/* 3. Ecosystem grid */}
      <Section id="ecosystem">
        <SectionHeader
          eyebrow="The ecosystem"
          title="Seven products. One operating system."
          subtitle="Each product solves a real problem in payments, business operations or commerce — and they're stronger together because they share a wallet, an identity and an infrastructure layer."
        />
        <div className="mt-12">
          <EcosystemGrid />
        </div>
      </Section>

      {/* 4. Stat strip — honest numbers */}
      <Section className="py-12 md:py-16">
        <StatStrip
          variant="card"
          items={[
            { value: "7", label: "Products in the ecosystem", icon: Sparkles, tone: "brand" },
            { value: "1", label: "Unified wallet", icon: Wallet, tone: "amber" },
            { value: "May 2026", label: "First products live", icon: Rocket, tone: "sky" },
            { value: "Cameroon", label: "Founding market", icon: Globe2, tone: "violet" },
          ]}
        />
      </Section>

      {/* 5. How it works */}
      <Section id="how-it-works" className="bg-surface-soft rounded-3xl">
        <SectionHeader
          eyebrow="How the ecosystem works"
          title="Three layers. One rail."
          subtitle="Payments at the base, business operations in the middle, commerce surfaces on top — each layer makes the next one cheaper, faster and more useful."
        />
        <div className="mt-12">
          <HowItWorks />
        </div>
      </Section>

      {/* 6. Coverage */}
      <Section>
        <SectionHeader
          eyebrow="Coverage"
          title="Live where we are. Building toward the rest."
          subtitle="QUATAPAY and ABAQWA launch in Cameroon in May 2026. Additional African markets follow in phased rollouts."
        />
        <div className="mt-10">
          <CoverageMap />
        </div>
      </Section>

      {/* 7. Founding thesis quote */}
      <Section className="py-16 md:py-20">
        <BigQuote
          quote="Africa doesn't need another standalone app. It needs infrastructure that connects daily life — and lets the next ten thousand builders plug in."
          author="Clovis Neba"
          role="Founder & CEO, QUATA Digital"
        />
      </Section>

      {/* 8. Partner gateway preview */}
      <Section id="partners">
        <SectionHeader
          eyebrow="Partner gateway"
          title="Four ways to plug in."
          subtitle="QUATA is open by design. Pick the path that matches what you bring to the ecosystem."
        />
        <div className="mt-12">
          <PartnerPreview />
        </div>
      </Section>

      {/* 9. Built for grid */}
      <Section className="bg-surface-soft rounded-3xl">
        <SectionHeader
          eyebrow="Built for"
          title="Operators across daily life."
          subtitle="QUATA shows up wherever value moves — between people, businesses and the public services around them."
        />
        <div className="mt-10">
          <FeatureGrid
            variant="bordered"
            columns={4}
            items={[
              { icon: Building2, title: "Merchants & SMBs", body: "Accept payments, manage orders, settle reliably.", tone: "brand" },
              { icon: Users, title: "Banks & telcos", body: "Integrate at the rail — co-issue, co-acquire, route on shared infrastructure.", tone: "sky" },
              { icon: TrendingUp, title: "Fintech builders", body: "Build on the QUATAPAY APIs and ship in weeks.", tone: "amber" },
              { icon: Rocket, title: "Public sector", body: "Disbursements, identity and citizen services on a trusted rail.", tone: "violet" },
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
