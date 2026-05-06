import type { Metadata } from "next";
import Link from "next/link";
import { SectionRenderer } from "@/components/site/sections/section-renderer";
import { getPageContent } from "@/lib/page-content";
import {
  ArrowRight,
  Sparkles,
  Wallet,
  Headphones,
  TrendingUp,
  ShieldCheck,
  Globe2,
  HeartHandshake,
  FileText,
  Search,
  CheckCircle2,
  Rocket,
  Building2,
  Briefcase,
  Coins,
  Users,
} from "lucide-react";
import { Section, SectionHeader } from "@/components/site/section";
import { FeatureGrid } from "@/components/site/sections/feature-grid";
import { ProcessSteps } from "@/components/site/sections/process-steps";
import { StatStrip } from "@/components/site/sections/stat-strip";
import { FaqWithAside } from "@/components/site/sections/faq-with-aside";
import { FinalCTA } from "@/components/site/cta";
import { partnerPaths } from "@/lib/partner-types";

export const metadata: Metadata = {
  title: "Partner gateway",
  description:
    "Four ways to plug into the QUATA Digital ecosystem — as a business, strategic, capital or service partner.",
};

const pathIcons = {
  business: Building2,
  strategic: Briefcase,
  investor: Coins,
  service: Users,
} as const;

export default async function PartnersIndexPage() {
  const cms = await getPageContent("partners");
  if (cms) {
    return <SectionRenderer sections={cms.sections} />;
  }
  return (
    <>
      {/* 1. Hero header */}
      <section className="relative overflow-hidden -mt-20">
        <div className="absolute inset-0 -z-10 bg-linear-to-b from-brand-soft/40 via-surface to-surface" />
        <div className="absolute inset-0 -z-10 dot-grid mask-fade-b opacity-50" />
        <div className="container-page pt-34 sm:pt-40 md:pt-48 pb-14 sm:pb-20 md:pb-28">
          <div className="inline-flex items-center gap-2 rounded-full border border-border bg-surface/80 px-3 py-1 text-xs text-muted-foreground backdrop-blur">
            <HeartHandshake className="h-3.5 w-3.5 text-primary" />
            Partner gateway
          </div>
          <h1 className="mt-6 text-3xl sm:text-4xl md:text-6xl font-semibold tracking-tight max-w-3xl text-balance">
            Four ways to{" "}
            <span className="text-gradient-brand">build with QUATA.</span>
          </h1>
          <p className="mt-5 max-w-2xl text-lg text-muted-foreground">
            QUATA is open by design. Choose your path — each one is a real
            on-ramp into the ecosystem with a named team and a clear timeline.
          </p>
          <div className="mt-8 flex flex-wrap items-center gap-2">
            {partnerPaths.map((p) => {
              const Icon = pathIcons[p.slug];
              return (
                <Link
                  key={p.slug}
                  href={`#${p.slug}`}
                  className="inline-flex items-center gap-1.5 rounded-full border border-border bg-card px-3 py-1.5 text-xs hover:bg-secondary"
                >
                  <Icon className="h-3.5 w-3.5 text-primary" />
                  {p.title}
                </Link>
              );
            })}
          </div>
        </div>
      </section>

      {/* 2. Why partner with QUATA */}
      <Section>
        <SectionHeader
          eyebrow="Why partner"
          title="Real leverage, not press releases."
          subtitle="Partnerships at QUATA are designed to move metrics — yours and ours. Here's what we bring to the table."
        />
        <div className="mt-12">
          <FeatureGrid
            items={[
              {
                icon: Wallet,
                title: "Built-in customer base",
                body: "Plug into a wallet that millions are reaching for daily — instant distribution.",
                tone: "brand",
              },
              {
                icon: Globe2,
                title: "Cross-border by default",
                body: "Multi-currency, multi-corridor settlement — sell across markets without rebuilding.",
                tone: "sky",
              },
              {
                icon: ShieldCheck,
                title: "Compliance done with you",
                body: "Shared KYC, transaction monitoring and audit trails reduce your regulatory load.",
                tone: "emerald",
              },
              {
                icon: TrendingUp,
                title: "Co-marketing & growth",
                body: "Joint go-to-market, ecosystem placement and referral mechanics that compound.",
                tone: "amber",
              },
              {
                icon: Headphones,
                title: "Named partner success",
                body: "A dedicated lead from the QUATA team owns the partnership end-to-end.",
                tone: "violet",
              },
              {
                icon: HeartHandshake,
                title: "Roadmap collaboration",
                body: "Strategic partners shape the rail — we build features alongside, not behind.",
                tone: "rose",
              },
            ]}
          />
        </div>
      </Section>

      {/* 3. Stats */}
      <Section className="py-12 md:py-16">
        <StatStrip
          variant="card"
          items={[
            { value: "4", label: "Partner paths", icon: HeartHandshake, tone: "brand" },
            { value: "3–5 days", label: "Avg. application review", icon: Headphones, tone: "amber" },
            { value: "4–8 weeks", label: "Time to integration", icon: Rocket, tone: "sky" },
            { value: "1", label: "Named owner per partner", icon: ShieldCheck, tone: "violet" },
          ]}
        />
      </Section>

      {/* 4. The four paths */}
      <Section className="bg-surface-soft rounded-3xl">
        <SectionHeader
          eyebrow="The paths"
          title="Pick the door that matches what you bring."
        />
        <div className="mt-12 grid gap-6 lg:grid-cols-2">
          {partnerPaths.map((p, i) => {
            const Icon = pathIcons[p.slug];
            return (
              <Link
                key={p.slug}
                id={p.slug}
                href={`/partners/${p.slug}`}
                className="group flex flex-col rounded-2xl border border-border bg-card p-7 ring-soft transition hover:-translate-y-0.5 hover:ring-elevated"
              >
                <div className="flex items-center gap-3">
                  <div className="inline-flex h-10 w-10 items-center justify-center rounded-xl bg-brand-soft text-primary">
                    <Icon className="h-5 w-5" />
                  </div>
                  <div className="text-sm uppercase tracking-wider text-muted-foreground">
                    Path 0{i + 1}
                  </div>
                </div>
                <h3 className="mt-5 text-xl font-semibold tracking-tight">{p.title}</h3>
                <p className="mt-2 text-sm text-muted-foreground">{p.blurb}</p>
                <ul className="mt-5 grid gap-2">
                  {p.perks.slice(0, 3).map((perk) => (
                    <li
                      key={perk}
                      className="text-sm text-foreground/80 flex items-start gap-2"
                    >
                      <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 text-primary shrink-0" />
                      {perk}
                    </li>
                  ))}
                </ul>
                <div className="mt-6 inline-flex items-center gap-1.5 text-sm font-medium text-primary">
                  {p.cta}{" "}
                  <ArrowRight className="h-3.5 w-3.5 transition group-hover:translate-x-0.5" />
                </div>
              </Link>
            );
          })}
        </div>
      </Section>

      {/* 5. Process steps */}
      <Section>
        <SectionHeader
          eyebrow="The process"
          title="From application to live partnership."
          subtitle="Same playbook for every path — only the depth and stakeholders change."
        />
        <div className="mt-12">
          <ProcessSteps
            steps={[
              {
                icon: FileText,
                title: "Submit application",
                body: "Tell us who you are and what you'd like to do. Takes about 5 minutes.",
                duration: "Day 0",
              },
              {
                icon: Search,
                title: "Review & scoping",
                body: "A QUATA lead reviews, asks clarifying questions and proposes the shape of the deal.",
                duration: "Within 3–7 days",
              },
              {
                icon: ShieldCheck,
                title: "Compliance & contract",
                body: "KYB, security review and legal in parallel — typically 2–4 weeks.",
                duration: "Weeks 2–4",
              },
              {
                icon: Rocket,
                title: "Integrate & launch",
                body: "Account setup, integration support and phased rollout. Strategic integrations 4–8 weeks.",
                duration: "Weeks 4–8",
              },
            ]}
          />
        </div>
      </Section>

      {/* 6. Be an early partner — replaces fake testimonials */}
      <Section>
        <div className="rounded-3xl border border-border bg-surface-soft p-8 sm:p-10 md:p-12 grid lg:grid-cols-3 gap-6 items-center">
          <div className="lg:col-span-2">
            <div className="inline-flex items-center gap-2 rounded-full border border-border bg-surface px-3 py-1 text-xs">
              <Sparkles className="h-3.5 w-3.5 text-primary" />
              Early-partner advantage
            </div>
            <h3 className="mt-4 text-2xl md:text-3xl font-semibold tracking-tight text-balance">
              Be among the first names on the rail.
            </h3>
            <p className="mt-3 text-sm md:text-base text-muted-foreground max-w-2xl">
              QUATA Digital is launching its first products in May 2026. Early
              partners get priority onboarding, competitive pricing and a
              direct line to the founding team. Customer logos and case
              studies will be added here as partners come on board — there is
              still room to be one of them.
            </p>
          </div>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-1">
            {[
              { label: "Priority onboarding", icon: Rocket },
              { label: "Competitive pricing", icon: TrendingUp },
              { label: "Direct line to leadership", icon: Headphones },
              { label: "Case-study spotlight", icon: Sparkles },
            ].map((b) => (
              <div
                key={b.label}
                className="flex items-center gap-3 rounded-xl border border-border bg-card p-3"
              >
                <span className="inline-flex h-8 w-8 items-center justify-center rounded-lg bg-brand-soft text-primary">
                  <b.icon className="h-4 w-4" />
                </span>
                <span className="text-sm font-medium">{b.label}</span>
              </div>
            ))}
          </div>
        </div>
      </Section>

      {/* 7. FAQ */}
      <Section className="bg-surface-soft rounded-3xl">
        <SectionHeader
          eyebrow="Common questions"
          title="What partners ask before applying."
        />
        <div className="mt-10">
          <FaqWithAside
            asideTitle="Talk to partnerships"
            asideBody="Skip the form and write directly. We respond to every partnership enquiry within 3 business days."
            asideEmail="partnerships@quatadigital.com"
            asideStats={[
              { value: "3 days", label: "Avg. response" },
              { value: "4 paths", label: "Ways to plug in" },
            ]}
            items={[
              {
                q: "Is there a cost to partner with QUATA?",
                a: "Onboarding itself is free. Commercial terms depend on the partnership type — usually a per-transaction model for business partners, custom commercial terms for strategic partners.",
              },
              {
                q: "How long does the application take to review?",
                a: "We aim to respond within 3 business days for every submission. Strategic partnerships sometimes take longer because they involve multiple stakeholders.",
              },
              {
                q: "What documents do I need to submit?",
                a: "Just the application form. We'll request KYB documentation (incorporation, beneficial-owner ID, regulatory licences if applicable) when we move into the compliance phase.",
              },
              {
                q: "Can I switch partner type later?",
                a: "Yes — many service partners become business partners over time, and many business partners go on to integrate strategically. We restructure the relationship accordingly.",
              },
              {
                q: "Do you partner outside Africa?",
                a: "Our focus is Africa-wide. We're open to global partners that bring relevant capability into African markets.",
              },
              {
                q: "Where do I track the status of my application?",
                a: "After submission you'll receive an email confirmation; for ongoing visibility your QUATA partnership lead becomes your single point of contact.",
              },
            ]}
          />
        </div>
      </Section>

      {/* 8. Trust */}
      <Section>
        <SectionHeader
          eyebrow="Trust"
          title="Built to be safe to integrate with."
        />
        <div className="mt-10">
          <FeatureGrid
            columns={4}
            variant="bordered"
            items={[
              { icon: ShieldCheck, title: "Compliance-led", body: "Shared KYC, transaction monitoring and audit trails out of the box.", tone: "emerald" },
              { icon: Sparkles, title: "Production-grade APIs", body: "Versioned, documented, with a public changelog.", tone: "amber" },
              { icon: Globe2, title: "Multi-region data", body: "Data residency options for partners with regulatory requirements.", tone: "sky" },
              { icon: Headphones, title: "Tier-1 support", body: "Named partner success owner + 24/7 incident response.", tone: "brand" },
            ]}
          />
        </div>
      </Section>

      {/* 9. Final CTA */}
      <Section>
        <FinalCTA />
      </Section>
    </>
  );
}
