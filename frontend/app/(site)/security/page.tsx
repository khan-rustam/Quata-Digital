import type { Metadata } from "next";
import { Section, SectionHeader } from "@/components/site/section";
import {
  ShieldCheck,
  Lock,
  FileWarning,
  Bug,
  KeyRound,
  Activity,
  Mail,
  Globe2,
  Building2,
} from "lucide-react";
import { FeatureGrid } from "@/components/site/sections/feature-grid";
import { FaqWithAside } from "@/components/site/sections/faq-with-aside";
import { SectionRenderer } from "@/components/site/sections/section-renderer";
import { getPageContent } from "@/lib/page-content";

export const metadata: Metadata = {
  title: "Security",
  description:
    "Security posture, compliance and responsible disclosure at QUATA Digital.",
};

export default async function SecurityPage() {
  const cms = await getPageContent("security");
  if (cms) {
    return <SectionRenderer sections={cms.sections} />;
  }
  return (
    <>
      {/* Hero */}
      <section className="relative overflow-hidden -mt-20">
        <div className="absolute inset-0 -z-10 bg-linear-to-b from-brand-soft/40 via-surface to-surface" />
        <div className="absolute inset-0 -z-10 dot-grid mask-fade-b opacity-50" />
        <div className="container-page pt-34 sm:pt-40 pb-14 sm:pb-20">
          <div className="inline-flex items-center gap-2 rounded-full border border-border bg-surface/80 px-3 py-1 text-xs text-muted-foreground backdrop-blur">
            <ShieldCheck className="h-3.5 w-3.5 text-primary" />
            Security &amp; trust
          </div>
          <h1 className="mt-6 text-3xl sm:text-4xl md:text-5xl font-semibold tracking-tight max-w-3xl text-balance">
            How we protect customer and partner data.
          </h1>
          <p className="mt-5 max-w-2xl text-lg text-muted-foreground">
            Security is a primitive at QUATA Digital, not a feature. We&apos;re
            building toward international compliance with a security-first
            engineering approach from day one.
          </p>
        </div>
      </section>

      {/* Controls */}
      <Section>
        <SectionHeader eyebrow="Controls" title="What's in place today." />
        <div className="mt-10">
          <FeatureGrid
            columns={4}
            variant="bordered"
            items={[
              { icon: Lock, title: "TLS everywhere", body: "All traffic encrypted in transit by default.", tone: "emerald" },
              { icon: KeyRound, title: "Encryption at rest", body: "Sensitive fields encrypted at rest with key rotation.", tone: "brand" },
              { icon: ShieldCheck, title: "Fine-grained RBAC", body: "Least-privilege access enforced on every internal endpoint.", tone: "amber" },
              { icon: Activity, title: "Full audit trail", body: "Every staff action attributed and queryable.", tone: "sky" },
            ]}
          />
        </div>
      </Section>

      {/* Compliance roadmap */}
      <Section className="bg-surface-soft rounded-3xl">
        <SectionHeader
          eyebrow="Compliance"
          title="Where we stand and where we&apos;re going."
          subtitle="QUATA Digital operates as a technology and digital infrastructure provider. We are actively working toward regulatory compliance across all operating regions."
        />
        <div className="mt-10 grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          <div className="rounded-2xl border border-emerald-200 bg-emerald-50/40 p-5">
            <div className="flex items-center gap-2 text-emerald-900">
              <Building2 className="h-4 w-4" />
              <div className="text-sm font-semibold">Cameroon — registered</div>
            </div>
            <p className="mt-3 text-sm text-emerald-900/80">
              QUATA Digital Enterprise is registered under{" "}
              <code className="text-[11px] bg-white border border-emerald-200 rounded px-1 py-0.5">
                RC/BDA/2025A/189
              </code>{" "}
              · Tax ID{" "}
              <code className="text-[11px] bg-white border border-emerald-200 rounded px-1 py-0.5">
                M052517750267W
              </code>
              .
            </p>
          </div>
          <div className="rounded-2xl border border-amber-200 bg-amber-50/40 p-5">
            <div className="flex items-center gap-2 text-amber-900">
              <Globe2 className="h-4 w-4" />
              <div className="text-sm font-semibold">Other African markets</div>
            </div>
            <p className="mt-3 text-sm text-amber-900/80">
              Regulatory onboarding (incl. payment service provider licensing
              in Nigeria) will be pursued in line with market entry.
            </p>
          </div>
          <div className="rounded-2xl border border-sky-200 bg-sky-50/40 p-5">
            <div className="flex items-center gap-2 text-sky-900">
              <ShieldCheck className="h-4 w-4" />
              <div className="text-sm font-semibold">Certifications</div>
            </div>
            <ul className="mt-3 space-y-1.5 text-sm text-sky-900/80">
              <li>• PCI-DSS — in progress</li>
              <li>• ISO 27001 — planned</li>
              <li>• SOC 2 — planned</li>
            </ul>
          </div>
        </div>
      </Section>

      {/* Data protection */}
      <Section>
        <SectionHeader
          eyebrow="Data protection"
          title="Designed for global and regional frameworks."
        />
        <div className="mt-10 grid sm:grid-cols-3 gap-4">
          <div className="rounded-2xl border border-border bg-card p-5 ring-soft">
            <div className="text-sm font-semibold">GDPR</div>
            <p className="mt-2 text-xs text-muted-foreground">
              Compliance-oriented design for international users.
            </p>
          </div>
          <div className="rounded-2xl border border-border bg-card p-5 ring-soft">
            <div className="text-sm font-semibold">NDPR</div>
            <p className="mt-2 text-xs text-muted-foreground">
              Planned alignment for Nigerian expansion.
            </p>
          </div>
          <div className="rounded-2xl border border-border bg-card p-5 ring-soft">
            <div className="text-sm font-semibold">POPIA</div>
            <p className="mt-2 text-xs text-muted-foreground">
              Considered for South African market entry.
            </p>
          </div>
        </div>
      </Section>

      {/* Responsible disclosure */}
      <Section className="bg-surface-soft rounded-3xl">
        <SectionHeader
          eyebrow="Responsible disclosure"
          title="Found a vulnerability? Tell us."
          subtitle="We welcome reports from researchers and customers. We will not pursue legal action against people acting in good faith."
        />
        <div className="mt-8 grid lg:grid-cols-2 gap-4">
          <div className="rounded-2xl border border-border bg-card p-6 ring-soft">
            <Bug className="h-5 w-5 text-primary" />
            <div className="mt-4 text-base font-semibold">How to report</div>
            <p className="mt-2 text-sm text-muted-foreground">
              Email{" "}
              <a href="mailto:support@quatadigital.com" className="text-primary font-medium">
                support@quatadigital.com
              </a>{" "}
              with: a description, steps to reproduce, the impact you observed
              and any proof-of-concept artefacts. Please don&apos;t publicly
              disclose until we&apos;ve had a chance to remediate.
            </p>
          </div>
          <div className="rounded-2xl border border-border bg-card p-6 ring-soft">
            <FileWarning className="h-5 w-5 text-primary" />
            <div className="mt-4 text-base font-semibold">Our commitment</div>
            <ul className="mt-2 space-y-2 text-sm text-muted-foreground">
              <li>• Acknowledge reports within a reasonable timeframe</li>
              <li>• Investigate and resolve valid issues</li>
              <li>• No legal action against good-faith researchers</li>
            </ul>
          </div>
        </div>
      </Section>

      {/* FAQ */}
      <Section>
        <SectionHeader eyebrow="FAQ" title="Common security questions." />
        <div className="mt-10">
          <FaqWithAside
            asideTitle="Report a vulnerability"
            asideBody="Found something? Email us with the details. We acknowledge every report within 24 hours and credit researchers in our hall of fame."
            asideEmail="support@quatadigital.com"
            asideIcon="shieldAlert"
            asideStats={[
              { value: "24h", label: "Acknowledgement" },
              { value: "PGP", label: "Available on request" },
            ]}
            items={[
              {
                q: "Do you have a bug bounty?",
                a: "Not publicly today. We acknowledge and credit researchers in our security hall of fame and may offer discretionary rewards for impactful reports.",
              },
              {
                q: "Where is data hosted?",
                a: "Primary storage is on secure cloud infrastructure. Data may be processed in multiple regions depending on service optimisation. We aim to align with local data-protection regulations as we expand.",
              },
              {
                q: "Are you ISO 27001 / SOC 2 certified?",
                a: "We are working toward formal certification. Happy to share our current control documentation under NDA.",
              },
              {
                q: "How do you handle incidents?",
                a: "We have a documented incident-response process with named owners. Affected partners are notified within the timelines required by applicable law.",
              },
              {
                q: "Can I get a security questionnaire filled out?",
                a: "Yes — email support@quatadigital.com and we'll route it to the right team.",
              },
            ]}
          />
        </div>
      </Section>

      {/* CTA */}
      <Section>
        <div className="rounded-3xl border border-border bg-surface-soft p-10 text-center">
          <Mail className="mx-auto h-6 w-6 text-primary" />
          <h3 className="mt-4 text-2xl font-semibold tracking-tight">
            Have a security concern?
          </h3>
          <p className="mt-2 text-sm text-muted-foreground">
            Reach the security team directly.
          </p>
          <a
            href="mailto:support@quatadigital.com"
            className="mt-5 inline-flex items-center gap-2 rounded-full bg-primary text-primary-foreground px-5 py-2.5 text-sm font-medium hover:bg-primary/90"
          >
            <Mail className="h-4 w-4" />
            support@quatadigital.com
          </a>
        </div>
      </Section>
    </>
  );
}
