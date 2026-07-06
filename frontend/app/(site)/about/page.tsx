import type { Metadata } from "next";
import Link from "next/link";
import { SectionRenderer } from "@/components/site/sections/section-renderer";
import { getPageContent } from "@/lib/page-content";
import {
  Compass,
  Globe2,
  ShieldCheck,
  Sparkles,
  Heart,
  Target,
  Users,
  Network,
  Building2,
  Rocket,
  Trophy,
  Briefcase,
  HeartHandshake,
  Gauge,
  MapPin,
} from "lucide-react";
import { Section, SectionHeader } from "@/components/site/section";
import { Button } from "@/components/ui/button";
import { Timeline } from "@/components/site/sections/timeline";
import { FeatureGrid } from "@/components/site/sections/feature-grid";
import { StatStrip } from "@/components/site/sections/stat-strip";
import { BigQuote } from "@/components/site/sections/big-quote";
import { Illustration } from "@/components/site/illustrations/illustration";

export const metadata: Metadata = {
  title: "About",
  description:
    "QUATA Digital is building Africa's connected digital ecosystem — payments, business operations and commerce on one rail. Founded May 2025 in Bamenda, Cameroon.",
};

export default async function AboutPage() {
  const cms = await getPageContent("about");
  if (cms) {
    return <SectionRenderer sections={cms.sections} />;
  }
  return (
    <>
      {/* 1. Hero — 2-col with image right */}
      <section className="relative overflow-hidden -mt-20">
        <div className="absolute inset-0 -z-10 bg-linear-to-b from-brand-soft/40 via-surface to-surface" />
        <div className="absolute inset-0 -z-10 dot-grid mask-fade-b opacity-50" />
        <div className="container-page pt-34 sm:pt-40 md:pt-44 pb-14 sm:pb-20 md:pb-24">
          <div className="grid lg:grid-cols-2 gap-10 lg:gap-16 items-center">
            <div>
              <div className="inline-flex items-center gap-2 rounded-full border border-border bg-surface/80 px-3 py-1 text-xs text-muted-foreground backdrop-blur">
                <Sparkles className="h-3.5 w-3.5 text-primary" />
                About QUATA Digital
              </div>
              <h1 className="mt-6 text-3xl sm:text-4xl md:text-6xl font-semibold tracking-tight text-balance">
                Building Africa&apos;s{" "}
                <span className="text-gradient-brand">connected digital ecosystem.</span>
              </h1>
              <p className="mt-5 max-w-xl text-lg text-muted-foreground">
                Founded in May 2025 in Bamenda, Cameroon. QUATA Digital exists to
                make it easier for anyone, anywhere in Africa, to start, run and
                scale a business without friction.
              </p>
            </div>
            <Illustration
              name="about-hero"
              alt="QUATA Digital's team collaborating in their Bamenda office — laptops, a whiteboard and a product dashboard"
              width={1200}
              height={1000}
            />
          </div>
        </div>
      </section>

      {/* 2. Mission + Vision */}
      <Section className="pt-8">
        <div className="grid lg:grid-cols-2 gap-6">
          <div className="rounded-3xl border border-border bg-card p-8 ring-soft">
            <div className="inline-flex h-10 w-10 items-center justify-center rounded-xl bg-brand-soft text-primary">
              <Target className="h-5 w-5" />
            </div>
            <div className="mt-5 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Mission
            </div>
            <p className="mt-3 text-xl sm:text-2xl font-medium tracking-tight text-balance">
              To build powerful digital infrastructure that enables businesses
              and individuals across Africa to seamlessly transact, operate and
              grow in a connected economy.
            </p>
          </div>
          <div className="rounded-3xl border border-border bg-card p-8 ring-soft">
            <div className="inline-flex h-10 w-10 items-center justify-center rounded-xl bg-brand-soft text-primary">
              <Compass className="h-5 w-5" />
            </div>
            <div className="mt-5 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Vision
            </div>
            <p className="mt-3 text-xl sm:text-2xl font-medium tracking-tight text-balance">
              To become Africa&apos;s leading digital ecosystem, powering the
              future of commerce, finance and business operations at scale.
            </p>
          </div>
        </div>
      </Section>

      {/* 3. Why we exist */}
      <Section>
        <SectionHeader
          eyebrow="Why we exist"
          title="The gap we were built to close."
        />
        <div className="mt-10 grid lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-5 text-base sm:text-lg text-foreground/85 leading-relaxed">
            <p>
              Across Africa, millions of businesses and individuals operate in a
              fragmented digital environment — payments are unreliable, business
              tools are disconnected, and scaling across markets remains
              unnecessarily complex. While global solutions exist, they are
              often not designed for the realities of African markets, leaving a
              critical gap between potential and execution.
            </p>
            <p className="text-foreground font-medium">
              QUATA Digital exists to close that gap.
            </p>
            <p>
              We&apos;re building an integrated ecosystem of digital products
              designed specifically for Africa — combining payments, business
              infrastructure and operational tools into a seamless experience.
              Instead of forcing businesses to rely on multiple disconnected
              platforms, QUATA brings everything into a unified system that is
              scalable, secure and built for real-world conditions.
            </p>
            <p>
              The timing has never been more critical. Africa is experiencing
              rapid digital adoption, with a new generation of entrepreneurs and
              businesses emerging every day. QUATA Digital positions itself at
              the centre of this transformation — building not just tools, but
              the foundation for how modern African businesses will operate.
            </p>
          </div>
          <aside className="rounded-3xl border border-border bg-surface-soft p-6 self-start">
            <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              At a glance
            </div>
            <ul className="mt-4 grid gap-3 text-sm">
              <li className="flex items-start gap-3">
                <Building2 className="h-4 w-4 text-primary mt-0.5 shrink-0" />
                <span>
                  <span className="font-medium">Founded May 2025</span> in
                  Bamenda, Cameroon
                </span>
              </li>
              <li className="flex items-start gap-3">
                <MapPin className="h-4 w-4 text-primary mt-0.5 shrink-0" />
                <span>HQ: Bamenda, North West Region, Cameroon</span>
              </li>
              <li className="flex items-start gap-3">
                <Sparkles className="h-4 w-4 text-primary mt-0.5 shrink-0" />
                <span>
                  Seven products in the ecosystem; QUATAPAY and ABAQWA launch
                  May 2026
                </span>
              </li>
              <li className="flex items-start gap-3">
                <ShieldCheck className="h-4 w-4 text-primary mt-0.5 shrink-0" />
                <span>
                  Reg.{" "}
                  <code className="text-[11px] bg-card border border-border rounded px-1 py-0.5">
                    RC/BDA/2025A/189
                  </code>{" "}
                  · Tax ID{" "}
                  <code className="text-[11px] bg-card border border-border rounded px-1 py-0.5">
                    M052517750267W
                  </code>
                </span>
              </li>
            </ul>
          </aside>
        </div>
      </Section>

      {/* 4. Stats — honest */}
      <Section className="py-12">
        <StatStrip
          variant="card"
          items={[
            { value: "7", label: "Products in the ecosystem", icon: Sparkles, tone: "brand" },
            { value: "May 2025", label: "Founded", icon: Building2, tone: "amber" },
            { value: "Bamenda", label: "Headquarters", icon: MapPin, tone: "sky" },
            { value: "May 2026", label: "First products live", icon: Rocket, tone: "violet" },
          ]}
        />
      </Section>

      {/* 5. Our story / Timeline */}
      <Section>
        <SectionHeader
          eyebrow="Our story"
          title="From a single product to an ecosystem."
          subtitle="Key moments in the QUATA Digital journey so far."
        />
        <div className="mt-12 max-w-3xl">
          <Timeline
            entries={[
              {
                date: "May 2025",
                title: "QUATA Digital founded",
                body: "QUATA Digital Enterprise founded in Bamenda, Cameroon by Clovis Neba, with one objective: build next-generation digital infrastructure tailored for African markets.",
                icon: Building2,
              },
              {
                date: "Q3 2025",
                title: "Initial concept and architecture",
                body: "Concept and architecture design for QUATAPAY and ABAQWA — the payments and business infrastructure platforms.",
                icon: Network,
              },
              {
                date: "Q4 2025",
                title: "Core platform development",
                body: "Engineering and product teams begin building the core platform.",
                icon: Sparkles,
              },
              {
                date: "Q1 2026",
                title: "Internal testing & refinement",
                body: "End-to-end internal testing, hardening and operational rehearsal ahead of launch.",
                icon: Gauge,
              },
              {
                date: "May 2026",
                title: "QUATAPAY + ABAQWA launch",
                body: "Public launch in Cameroon. Merchants get one rail for payments and the operational tools to run on top.",
                icon: Rocket,
              },
              {
                date: "Future",
                title: "Pan-African expansion",
                body: "Expansion into multiple African markets, with QUATAFOOD, 88BRICKZ, 88BASKET, O3MALL and QMEDIQ joining the ecosystem.",
                icon: Globe2,
              },
            ]}
          />
        </div>
      </Section>

      {/* 6. Founder */}
      <Section className="bg-surface-soft rounded-3xl">
        <SectionHeader eyebrow="Founder" title="The team behind the rail." />
        <div className="mt-10 grid lg:grid-cols-[320px_1fr] gap-8 lg:gap-12 items-start max-w-4xl">
          <Illustration
            name="about-founder"
            alt="Clovis Neba, Founder &amp; CEO of QUATA Digital"
            width={900}
            height={1100}
            rounded="rounded-3xl"
          />
          <div>
            <div className="text-xl font-semibold tracking-tight">Clovis Neba</div>
            <div className="text-sm text-muted-foreground">Founder &amp; CEO</div>
            <p className="mt-4 text-base text-foreground/85 max-w-xl">
              Founded QUATA Digital in May 2025 in Bamenda with a simple
              conviction: African businesses deserve infrastructure designed for
              their reality, not adapted from elsewhere. He leads product,
              partnerships and the company&apos;s broader vision.
            </p>
            <p className="mt-4 text-sm text-muted-foreground max-w-xl">
              The leadership roster will be expanded as the team grows beyond
              its founding cohort.
            </p>
          </div>
        </div>
      </Section>

      {/* 7. Big quote */}
      <Section className="py-12">
        <BigQuote
          quote="Africa is experiencing rapid digital adoption, but the infrastructure to support that growth at scale is still evolving. We're here to build that foundation — for the businesses that will define the next decade."
          author="Clovis Neba"
          role="Founder & CEO, QUATA Digital"
        />
      </Section>

      {/* 8. Values */}
      <Section>
        <SectionHeader eyebrow="Principles" title="What we hold ourselves to." />
        <div className="mt-10">
          <FeatureGrid
            items={[
              { icon: Compass, title: "Useful at scale", body: "We build for daily life — not edge cases. If millions can't use it, we don't ship it.", tone: "brand" },
              { icon: Globe2, title: "Built in Africa, for Africa", body: "Decisions made on the continent, with operators who live the problems we solve.", tone: "sky" },
              { icon: ShieldCheck, title: "Trust by default", body: "Money, identity and care don't get half-measures. We default to safety and ownership.", tone: "emerald" },
              { icon: Sparkles, title: "Connected, not bundled", body: "Each product earns its place — together they unlock more than the sum.", tone: "amber" },
              { icon: Heart, title: "People first", body: "Customers, teammates, partners. The rest is downstream of how we treat people.", tone: "rose" },
              { icon: Trophy, title: "Outcomes over output", body: "We don't celebrate launches. We celebrate things people actually use.", tone: "violet" },
            ]}
          />
        </div>
      </Section>

      {/* 9. Office locations — single HQ + future */}
      <Section>
        <SectionHeader
          eyebrow="Where we work"
          title="One headquarters. A continental ambition."
        />
        <div className="mt-10 grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          <div className="rounded-2xl border border-border bg-card p-6 ring-soft">
            <div className="inline-flex h-10 w-10 items-center justify-center rounded-xl bg-brand-soft text-primary">
              <MapPin className="h-5 w-5" />
            </div>
            <div className="mt-5 text-base font-semibold tracking-tight">
              Bamenda
              <span className="text-muted-foreground font-normal">, Cameroon</span>
            </div>
            <p className="mt-2 text-sm text-muted-foreground">
              North West Region, Cameroon.
            </p>
            <div className="mt-4 text-xs text-muted-foreground">
              Founding team — small and focused.
            </div>
          </div>
          <div className="rounded-2xl border border-dashed border-border bg-surface-soft p-6">
            <div className="inline-flex h-10 w-10 items-center justify-center rounded-xl bg-secondary text-muted-foreground">
              <Globe2 className="h-5 w-5" />
            </div>
            <div className="mt-5 text-base font-semibold tracking-tight">
              Pan-African expansion
            </div>
            <p className="mt-2 text-sm text-muted-foreground">
              Additional offices will follow as we expand into new African
              markets.
            </p>
          </div>
          <div className="rounded-2xl border border-dashed border-border bg-surface-soft p-6">
            <div className="inline-flex h-10 w-10 items-center justify-center rounded-xl bg-secondary text-muted-foreground">
              <Users className="h-5 w-5" />
            </div>
            <div className="mt-5 text-base font-semibold tracking-tight">
              Remote-friendly roles
            </div>
            <p className="mt-2 text-sm text-muted-foreground">
              Most engineering, design and content roles are open to
              remote-first teammates.
            </p>
          </div>
        </div>
      </Section>

      {/* 10. CTA */}
      <Section>
        <div className="rounded-3xl border border-border bg-ink text-white p-10 md:p-14 grid md:grid-cols-2 gap-8 items-center relative overflow-hidden">
          <div className="absolute inset-0 dot-grid opacity-20" />
          <div className="relative">
            <h3 className="text-3xl md:text-4xl font-semibold tracking-tight">
              Want to be part of this?
            </h3>
            <p className="mt-3 text-white/70 max-w-xl">
              We&apos;re hiring early teammates and partners across the continent.
            </p>
          </div>
          <div className="relative md:justify-self-end flex gap-3 flex-wrap">
            <Button variant="accent" size="lg" asChild>
              <Link href="/careers">
                <Briefcase className="h-4 w-4" />
                Open roles
              </Link>
            </Button>
            <Button
              variant="outline"
              size="lg"
              asChild
              className="bg-white/0 text-white border-white/20 hover:bg-white/10 hover:text-white"
            >
              <Link href="/partners">
                <HeartHandshake className="h-4 w-4" />
                Partner with us
              </Link>
            </Button>
          </div>
        </div>
      </Section>
    </>
  );
}
