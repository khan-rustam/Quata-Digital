import type { Metadata } from "next";
import { Section } from "@/components/site/section";
import { ShieldCheck } from "lucide-react";
import { SectionRenderer } from "@/components/site/sections/section-renderer";
import { getPageContent } from "@/lib/page-content";

export const metadata: Metadata = {
  title: "Privacy",
  description:
    "How QUATA Digital collects, processes and protects your personal data.",
};

const lastUpdated = "Effective on first product launch (May 2026)";

const sections = [
  {
    title: "1. Who we are",
    body: `QUATA Digital Enterprise (\"QUATA\", \"we\", \"our\", \"us\") is the controller of the personal data collected through this website and our products. We are registered in Cameroon under RC/BDA/2025A/189 (Tax ID M052517750267W) and operate from Bamenda, North West Region, Cameroon.`,
  },
  {
    title: "2. Why we collect data",
    body: `We collect and process personal data only for the purpose of:\n• Providing payment and business services\n• Improving platform performance\n• Ensuring security and fraud prevention\n• Meeting legal and regulatory requirements`,
  },
  {
    title: "3. What we collect",
    body: `• Contact information (name, phone, email)\n• Business information (for merchants and partners)\n• Transaction data (for payment processing)\n• Technical data (device, IP, usage analytics)`,
  },
  {
    title: "4. How we protect your data",
    body: `We implement industry-standard safeguards including encryption in transit, secure APIs and access controls. Sensitive data is encrypted at rest and access is restricted to authorised personnel.`,
  },
  {
    title: "5. Data sharing",
    body: `We do not sell personal data. Data may be shared only with:\n• Payment processors and financial partners (for transaction execution)\n• Regulatory authorities (where required by law)\n• Service providers under strict confidentiality agreements`,
  },
  {
    title: "6. Your rights",
    body: `Depending on where you live, you may have rights to access, correct, port, delete or restrict the processing of your personal data. To exercise any of these rights, email support@quatadigital.com.`,
  },
  {
    title: "7. Data residency",
    body: `Primary data storage is hosted on secure cloud infrastructure. Data may be processed in multiple regions depending on service optimisation and availability. We aim to align with local data-protection regulations as we expand into new markets.`,
  },
  {
    title: "8. Compliance posture",
    body: `QUATA Digital is aligning operations with key data-protection frameworks: GDPR (compliance-oriented design), NDPR (planned for Nigerian expansion) and POPIA (considered for South African market entry). We design for user consent, data minimisation, secure processing and transparent usage.`,
  },
  {
    title: "9. Changes to this policy",
    body: `We may update this policy from time to time. The latest version is always available on this page, with the \"effective date\" at the top.`,
  },
  {
    title: "10. Contact",
    body: `Questions or requests: support@quatadigital.com`,
  },
];

export default async function PrivacyPage() {
  // CMS-first: once the lawyer-reviewed copy is published in admin, render
  // it. Fall back to this static stub until then.
  const cms = await getPageContent("privacy");
  if (cms) {
    return <SectionRenderer sections={cms.sections} />;
  }
  return (
    <>
      <section className="relative overflow-hidden -mt-20">
        <div className="absolute inset-0 -z-10 bg-linear-to-b from-brand-soft/40 via-surface to-surface" />
        <div className="absolute inset-0 -z-10 dot-grid mask-fade-b opacity-50" />
        <div className="container-page pt-34 sm:pt-40 pb-14 sm:pb-20">
          <div className="inline-flex items-center gap-2 rounded-full border border-border bg-surface/80 px-3 py-1 text-xs text-muted-foreground backdrop-blur">
            <ShieldCheck className="h-3.5 w-3.5 text-primary" />
            Privacy policy
          </div>
          <h1 className="mt-6 text-3xl sm:text-4xl md:text-5xl font-semibold tracking-tight max-w-3xl text-balance">
            How we handle your data.
          </h1>
          <p className="mt-3 text-sm text-muted-foreground">{lastUpdated}</p>
        </div>
      </section>

      <Section className="max-w-3xl mx-auto py-12">
        <div className="space-y-10">
          {sections.map((s) => (
            <div key={s.title}>
              <h2 className="text-base font-semibold tracking-tight">{s.title}</h2>
              <p className="mt-3 text-sm text-foreground/80 leading-relaxed whitespace-pre-line">
                {s.body}
              </p>
            </div>
          ))}
        </div>
        <div className="mt-12 rounded-2xl border border-border bg-surface-soft p-6 text-sm text-muted-foreground">
          QUATA Digital Enterprise — Bamenda, North West Region, Cameroon ·
          Reg. RC/BDA/2025A/189 · Tax ID M052517750267W
        </div>
      </Section>
    </>
  );
}
