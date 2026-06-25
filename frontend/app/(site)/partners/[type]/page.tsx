import { notFound } from "next/navigation";
import type { Metadata } from "next";
import Link from "next/link";
import {
  ArrowRight,
  CheckCircle2,
  ShieldCheck,
  Headphones,
  FileText,
  Search,
  Rocket,
  Mail,
  ClipboardCheck,
} from "lucide-react";
import { Section, SectionHeader } from "@/components/site/section";
import { SectionRenderer } from "@/components/site/sections/section-renderer";
import { getPageContent } from "@/lib/page-content";
import { partnerPaths, getPartnerPath } from "@/lib/partner-types";
import { PartnerForm } from "@/components/forms/partner-form";
import { ProcessSteps } from "@/components/site/sections/process-steps";
import { FAQ } from "@/components/site/sections/faq";
import { Illustration, type IllustrationName } from "@/components/site/illustrations/illustration";

const eligibilityByType: Record<string, string[]> = {
  business: [
    "Registered legal entity in an active QUATA market",
    "Online or offline presence with paying customers",
    "Ability to accept digital payments",
    "Clean compliance and AML record",
  ],
  strategic: [
    "Bank, telco, logistics network or platform with regional reach",
    "Existing technical team able to integrate at the API layer",
    "Strategic intent for a 12+ month partnership",
    "Internal sponsor at director level or above",
  ],
  investor: [
    "Active institutional investor or family office",
    "Africa or frontier-market investment thesis",
    "Comfort with private, NDA-gated diligence",
    "Stage fit (currently raising private capital — not public)",
  ],
  service: [
    "Valid ID and right to work in your country",
    "Vehicle or equipment that matches your service",
    "Smartphone with reliable internet",
    "Willingness to complete onboarding training",
  ],
};

const faqByType: Record<string, { q: string; a: string }[]> = {
  business: [
    { q: "Who can become a business partner?", a: "Any business or merchant looking to accept payments or digitise operations." },
    { q: "Is registration required?", a: "Not strictly — informal businesses can also apply." },
    { q: "How long does onboarding take?", a: "Typically within 1–2 weeks." },
    { q: "Are there setup fees?", a: "Pricing depends on the selected plan and services." },
    { q: "Can small businesses apply?", a: "Yes — QUATA is designed for businesses of all sizes." },
  ],
  strategic: [
    { q: "What qualifies as a strategic partner?", a: "Organisations that can integrate, distribute or enhance QUATA services." },
    { q: "Do you support API integrations?", a: "Yes — integration capabilities are part of our ecosystem roadmap." },
    { q: "Is revenue sharing available?", a: "Yes — depending on the partnership structure." },
    { q: "How long does integration take?", a: "Typically 4–8 weeks depending on scope." },
    { q: "Can startups apply as strategic partners?", a: "Yes — if there is strong alignment and value." },
  ],
  investor: [
    { q: "What stage is QUATA Digital currently at?", a: "Pre-seed / Seed stage." },
    { q: "Is QUATA currently raising funds?", a: "Yes — details are shared upon request." },
    { q: "Is the pitch deck public?", a: "Available upon request (NDA optional)." },
    { q: "What sectors does QUATA operate in?", a: "Fintech, commerce, infrastructure and digital services." },
    { q: "How often are updates shared?", a: "Quarterly investor updates." },
  ],
  service: [
    { q: "Who qualifies as a service partner?", a: "Developers, agencies, logistics providers and other service professionals." },
    { q: "Are there guaranteed projects?", a: "Opportunities are based on demand and performance." },
    { q: "Can freelancers apply?", a: "Yes — if they meet quality standards." },
    { q: "How are partners selected?", a: "Based on experience, capability and alignment." },
    { q: "Is there a contract?", a: "Yes — for formal engagements." },
  ],
};

// Boss-confirmed disqualification criteria per partner type. Surfaced
// upfront so applicants self-select.
const disqualifiersByType: Record<string, string[]> = {
  business: [
    "False or misleading information",
    "Illegal or non-compliant business activity",
    "Incomplete application",
  ],
  strategic: [
    "Misalignment with the QUATA ecosystem",
    "Lack of operational or technical capacity",
    "Non-compliant or high-risk business",
  ],
  investor: [
    "Misalignment with the company vision",
    "Lack of verifiable investment background",
    "Non-serious or speculative inquiries",
  ],
  service: [
    "Poor or unverifiable track record",
    "Lack of professionalism or capacity",
    "Misalignment with service requirements",
  ],
};

// Boss-confirmed onboarding timelines per type.
const timelineByType: Record<string, { label: string; value: string }[]> = {
  business: [
    { label: "Application review", value: "2–5 business days" },
    { label: "Account setup", value: "3–7 days" },
    { label: "Full onboarding", value: "Up to 2 weeks" },
  ],
  strategic: [
    { label: "Initial response", value: "3–7 business days" },
    { label: "Evaluation & discussion", value: "2–4 weeks" },
    { label: "Integration", value: "4–8 weeks" },
  ],
  investor: [
    { label: "Initial response", value: "3–5 business days" },
    { label: "Introductory discussions", value: "1–2 weeks" },
    { label: "Due diligence", value: "2–6 weeks" },
  ],
  service: [
    { label: "Application review", value: "3–5 business days" },
    { label: "Evaluation", value: "1–2 weeks" },
    { label: "Engagement", value: "Project-dependent" },
  ],
};

// Long-form supporting quotes for the FAQ side-panel — keeps the right
// half of the FAQ row from being empty.
const faqQuoteByType: Record<string, { quote: string; voice: string }> = {
  business: {
    quote:
      "We don't ask merchants to learn a new way of working — QUATAPAY plugs into how you already sell.",
    voice: "QUATA Digital",
  },
  strategic: {
    quote:
      "Every strategic partner is paired with an exec sponsor. You're talking to the people who can actually decide.",
    voice: "QUATA Digital",
  },
  investor: {
    quote:
      "We share a public summary openly and the detailed deck under NDA — fast, in writing, no theatre.",
    voice: "QUATA Digital",
  },
  service: {
    quote:
      "Most service partners go live within a week. The bar is your ID, your vehicle, and finishing onboarding.",
    voice: "QUATA Digital",
  },
};

export function generateStaticParams() {
  return partnerPaths.map((p) => ({ type: p.slug }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ type: string }>;
}): Promise<Metadata> {
  const { type } = await params;
  const path = getPartnerPath(type);
  if (!path) return {};
  return { title: path.title, description: path.blurb };
}

export default async function PartnerTypePage({
  params,
}: {
  params: Promise<{ type: string }>;
}) {
  const { type } = await params;
  const path = getPartnerPath(type);
  if (!path) return notFound();

  const cms = await getPageContent(`partners/${type}`);
  if (cms) {
    return <SectionRenderer sections={cms.sections} />;
  }

  const Icon = path.icon;
  const eligibility = eligibilityByType[path.slug] ?? [];
  const faqs = faqByType[path.slug] ?? [];
  const faqQuote = faqQuoteByType[path.slug];
  const disqualifiers = disqualifiersByType[path.slug] ?? [];
  const timeline = timelineByType[path.slug] ?? [];

  return (
    <>
      {/* 1. Hero — 2-col with image on the right */}
      <section className="relative overflow-hidden -mt-20">
        <div className="absolute inset-0 -z-10 bg-linear-to-b from-brand-soft/50 via-surface to-surface" />
        <div className="absolute inset-0 -z-10 dot-grid mask-fade-b opacity-50" />
        <div className="container-page pt-36 md:pt-40 pb-16 md:pb-20">
          <div className="text-sm">
            <Link href="/partners" className="text-muted-foreground hover:text-foreground">
              Partners
            </Link>
            <span className="mx-2 text-muted-foreground/60">/</span>
            <span className="text-foreground">{path.title}</span>
          </div>
          <div className="mt-8 grid lg:grid-cols-2 gap-10 lg:gap-16 items-center">
            <div>
              <div className="inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-brand-soft text-primary">
                <Icon className="h-6 w-6" />
              </div>
              <h1 className="mt-5 text-3xl sm:text-4xl md:text-5xl font-semibold tracking-tight max-w-xl text-balance">
                {path.title}
              </h1>
              <p className="mt-4 text-lg text-muted-foreground max-w-xl">
                {path.description}
              </p>
            </div>
            <Illustration
              name={`partner-${path.slug}-hero` as IllustrationName}
              alt={`${path.title} working with QUATA Digital`}
              width={1200}
              height={900}
            />
          </div>
        </div>
      </section>

      {/* 2. Benefits grid */}
      <Section className="py-12">
        <SectionHeader
          eyebrow="Benefits"
          title="What you get when you join."
        />
        <div className="mt-10 grid sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {path.perks.map((perk) => (
            <div
              key={perk}
              className="flex items-start gap-3 rounded-2xl border border-border bg-card p-5 ring-soft"
            >
              <span className="inline-flex h-7 w-7 items-center justify-center rounded-full bg-brand-soft text-primary shrink-0">
                <CheckCircle2 className="h-3.5 w-3.5" />
              </span>
              <span className="text-sm">{perk}</span>
            </div>
          ))}
        </div>
      </Section>

      {/* 3. Form + sidebar — visual block at the bottom of the left col so
          the column matches the form's height instead of trailing off. */}
      <Section className="py-8">
        <div className="grid lg:grid-cols-5 gap-10 lg:gap-16">
          <div className="lg:col-span-2 space-y-4">
            <div className="rounded-2xl border border-border bg-card p-6 ring-soft">
              <div className="text-sm font-semibold flex items-center gap-2">
                <Mail className="h-4 w-4 text-primary" />
                What happens next
              </div>
              <ol className="mt-4 space-y-3 text-sm text-muted-foreground">
                <li className="flex gap-3">
                  <span className="inline-flex h-5 w-5 items-center justify-center rounded-full bg-brand-soft text-primary text-[11px] font-bold shrink-0">
                    1
                  </span>
                  Confirmation email immediately on submit.
                </li>
                <li className="flex gap-3">
                  <span className="inline-flex h-5 w-5 items-center justify-center rounded-full bg-brand-soft text-primary text-[11px] font-bold shrink-0">
                    2
                  </span>
                  Partnership lead reviews within 3 business days.
                </li>
                <li className="flex gap-3">
                  <span className="inline-flex h-5 w-5 items-center justify-center rounded-full bg-brand-soft text-primary text-[11px] font-bold shrink-0">
                    3
                  </span>
                  Scoping call to align on goals and timeline.
                </li>
                <li className="flex gap-3">
                  <span className="inline-flex h-5 w-5 items-center justify-center rounded-full bg-brand-soft text-primary text-[11px] font-bold shrink-0">
                    4
                  </span>
                  Compliance, contract, integration, launch.
                </li>
              </ol>
            </div>

            <div className="rounded-2xl border border-border bg-surface-soft p-6">
              <div className="text-sm font-semibold flex items-center gap-2">
                <ShieldCheck className="h-4 w-4 text-primary" />
                Privacy
              </div>
              <p className="mt-3 text-sm text-muted-foreground">
                Your application is treated as confidential. We only share details
                with internal QUATA team members evaluating the partnership.
              </p>
            </div>

            <div className="rounded-2xl border border-border bg-card p-6">
              <div className="text-sm font-semibold flex items-center gap-2">
                <Headphones className="h-4 w-4 text-primary" />
                Talk to a person
              </div>
              <p className="mt-3 text-sm text-muted-foreground">
                Prefer a conversation first? Email{" "}
                <a href="mailto:pi@quatadigital.com" className="text-primary font-medium">
                  pi@quatadigital.com
                </a>{" "}
                or visit our{" "}
                <Link href="/contact" className="text-primary font-medium">
                  contact page
                </Link>
                .
              </p>
            </div>

            <Illustration
              name={`partner-${path.slug}-sidebar` as IllustrationName}
              alt={`What working with QUATA looks like for a ${path.title.toLowerCase()}`}
              width={800}
              height={600}
            />
          </div>

          <div className="lg:col-span-3">
            <div className="rounded-2xl border border-border bg-card p-6 md:p-8 ring-soft">
              <h2 className="text-xl font-semibold tracking-tight">{path.cta}</h2>
              <p className="mt-2 text-sm text-muted-foreground">
                Takes about 5 minutes. We respond within 3 business days.
              </p>
              <div className="mt-6">
                <PartnerForm
                  type={path.slug}
                  fields={path.formFields}
                  cta={path.cta}
                />
              </div>
            </div>
          </div>
        </div>
      </Section>

      {/* 4. Eligibility + timeline + disqualifiers */}
      <Section className="bg-surface-soft rounded-3xl">
        <SectionHeader
          eyebrow="Eligibility"
          title="Who this path is for."
          subtitle="To save you time, here's what we look for in successful applications, the timeline you can expect, and what would disqualify an application."
        />
        <div className="mt-10 grid lg:grid-cols-3 gap-5">
          <div className="lg:col-span-1 space-y-3">
            <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Qualifies
            </div>
            {eligibility.map((item) => (
              <div
                key={item}
                className="flex items-start gap-3 rounded-2xl border border-border bg-card p-4"
              >
                <ClipboardCheck className="h-4 w-4 text-primary mt-0.5 shrink-0" />
                <span className="text-sm">{item}</span>
              </div>
            ))}
          </div>
          <div className="lg:col-span-1 space-y-3">
            <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Onboarding timeline
            </div>
            <div className="rounded-2xl border border-border bg-card p-5 ring-soft">
              <ol className="space-y-4">
                {timeline.map((step, i) => (
                  <li key={step.label} className="flex items-start gap-3">
                    <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-brand-soft text-primary text-[11px] font-bold shrink-0">
                      {i + 1}
                    </span>
                    <div>
                      <div className="text-sm font-medium">{step.label}</div>
                      <div className="text-xs text-muted-foreground">
                        {step.value}
                      </div>
                    </div>
                  </li>
                ))}
              </ol>
            </div>
          </div>
          <div className="lg:col-span-1 space-y-3">
            <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Won&rsquo;t qualify
            </div>
            <div className="rounded-2xl border border-rose-200 bg-rose-50/60 p-5">
              <ul className="space-y-3">
                {disqualifiers.map((d) => (
                  <li key={d} className="flex items-start gap-2 text-sm text-rose-900">
                    <span className="text-rose-700 mt-0.5">×</span>
                    <span>{d}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      </Section>

      {/* 5. The process */}
      <Section>
        <SectionHeader
          eyebrow="The process"
          title="Simple, transparent, no surprises."
        />
        <div className="mt-12">
          <ProcessSteps
            steps={[
              { icon: FileText, title: "Submit", body: "Fill the application above. Around 5 minutes.", duration: "Day 0" },
              { icon: Search, title: "Review", body: "Partnership lead reviews and reaches out.", duration: "Within 3 days" },
              { icon: ShieldCheck, title: "Compliance", body: "KYB, security and contract in parallel.", duration: "1–3 weeks" },
              { icon: Rocket, title: "Launch", body: "Integration support then go live.", duration: "2–6 weeks" },
            ]}
          />
        </div>
      </Section>

      {/* 6. FAQ — 2-col on lg+, FAQ left, supporting quote panel right */}
      <Section>
        <SectionHeader
          eyebrow="FAQ"
          title={`${path.title} — common questions.`}
        />
        <div className="mt-10 grid lg:grid-cols-5 gap-10 lg:gap-16 items-start">
          <div className="lg:col-span-3">
            <FAQ
              items={
                faqs.length > 0
                  ? faqs
                  : [{ q: "How long does it take to hear back?", a: "Within 3 business days." }]
              }
            />
          </div>
          <div className="lg:col-span-2 space-y-5 lg:sticky lg:top-24">
            <Illustration
              name={`partner-${path.slug}-faq` as IllustrationName}
              alt={`${path.title} talking with the QUATA partnerships team`}
              width={900}
              height={1100}
              rounded="rounded-3xl"
            />
            {faqQuote && (
              <figure className="rounded-3xl border border-border bg-card p-6 ring-soft">
                <blockquote className="text-base font-medium tracking-tight text-balance">
                  &ldquo;{faqQuote.quote}&rdquo;
                </blockquote>
                <figcaption className="mt-3 text-xs text-muted-foreground">
                  — {faqQuote.voice}
                </figcaption>
              </figure>
            )}
          </div>
        </div>
      </Section>

      {/* 7. Other paths */}
      <Section className="bg-surface-soft rounded-3xl">
        <SectionHeader
          eyebrow="Not the right fit?"
          title="Try another partner path."
        />
        <div className="mt-10 grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {partnerPaths
            .filter((p) => p.slug !== path.slug)
            .map((p) => {
              const PathIcon = p.icon;
              return (
                <Link
                  key={p.slug}
                  href={`/partners/${p.slug}`}
                  className="group flex items-start gap-3 rounded-2xl border border-border bg-card p-5 ring-soft transition hover:-translate-y-0.5"
                >
                  <div className="inline-flex h-9 w-9 items-center justify-center rounded-lg bg-brand-soft text-primary shrink-0">
                    <PathIcon className="h-4 w-4" />
                  </div>
                  <div className="min-w-0">
                    <div className="text-sm font-semibold">{p.title}</div>
                    <div className="mt-1 text-xs text-muted-foreground line-clamp-2">{p.blurb}</div>
                    <div className="mt-2 inline-flex items-center gap-1 text-xs font-medium text-primary">
                      Open path
                      <ArrowRight className="h-3 w-3 transition group-hover:translate-x-0.5" />
                    </div>
                  </div>
                </Link>
              );
            })}
        </div>
      </Section>
    </>
  );
}
