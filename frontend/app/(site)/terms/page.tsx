import type { Metadata } from "next";
import { Section } from "@/components/site/section";
import { FileText } from "lucide-react";
import { SectionRenderer } from "@/components/site/sections/section-renderer";
import { getPageContent } from "@/lib/page-content";

export const metadata: Metadata = {
  title: "Terms",
  description: "Terms of service for the QUATA Digital website and products.",
};

const lastUpdated = "Effective on first product launch (May 2026)";

const sections = [
  {
    title: "1. Use of services",
    body: `By using QUATA Digital services, you agree to use them in compliance with applicable laws and regulations.`,
  },
  {
    title: "2. Account responsibility",
    body: `You are responsible for maintaining the confidentiality of your account credentials and for all activity that occurs under your account.`,
  },
  {
    title: "3. Payments & transactions",
    body: `QUATAPAY facilitates digital payments but does not act as a bank. Transaction execution depends on third-party financial networks (Mobile Money operators, card schemes, banks). We do not guarantee that any specific transaction will be successfully executed by those networks.`,
  },
  {
    title: "4. Service availability",
    body: `We aim for high availability but do not guarantee uninterrupted service. Maintenance windows, network failures and force-majeure events may interrupt access from time to time.`,
  },
  {
    title: "5. Acceptable use",
    body: `You agree not to use QUATA services for fraud, money-laundering, terrorist financing, or any illegal activity. We reserve the right to suspend or terminate accounts that violate these terms or applicable law.`,
  },
  {
    title: "6. Intellectual property",
    body: `All content on this site — text, graphics, logos, code — is owned by QUATA Digital Enterprise or its licensors and is protected by intellectual property laws. You may not copy, modify or distribute it without permission.`,
  },
  {
    title: "7. Submissions",
    body: `When you submit a form (partner application, job application, contact form), you represent that the information is accurate and that you have the authority to submit it.`,
  },
  {
    title: "8. Disclaimers",
    body: `The site and services are provided \"as is\" without warranty of any kind. To the maximum extent permitted by law, QUATA Digital disclaims all warranties, express or implied.`,
  },
  {
    title: "9. Limitation of liability",
    body: `To the maximum extent permitted by law, QUATA Digital is not liable for any indirect, incidental, special or consequential damages arising from your use of the site or services.`,
  },
  {
    title: "10. Governing law",
    body: `These terms are governed by the laws of Cameroon. Disputes will be resolved in the competent courts of Bamenda, Northwest Region.`,
  },
  {
    title: "11. Changes",
    body: `We may update these terms periodically with notification through official channels. The latest version is always on this page.`,
  },
  {
    title: "12. Contact",
    body: `Questions: legal@quatadigital.com`,
  },
];

export default async function TermsPage() {
  const cms = await getPageContent("terms");
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
            <FileText className="h-3.5 w-3.5 text-primary" />
            Terms of service
          </div>
          <h1 className="mt-6 text-3xl sm:text-4xl md:text-5xl font-semibold tracking-tight max-w-3xl text-balance">
            The basic rules of the road.
          </h1>
          <p className="mt-3 text-sm text-muted-foreground">{lastUpdated}</p>
        </div>
      </section>
      <Section className="max-w-3xl mx-auto py-12">
        <div className="space-y-10">
          {sections.map((s) => (
            <div key={s.title}>
              <h2 className="text-base font-semibold tracking-tight">{s.title}</h2>
              <p className="mt-3 text-sm text-foreground/80 leading-relaxed">{s.body}</p>
            </div>
          ))}
        </div>
        <div className="mt-12 rounded-2xl border border-border bg-surface-soft p-6 text-sm text-muted-foreground">
          QUATA Digital Enterprise — Bamenda, Northwest Region, Cameroon ·
          Reg. TPPRR:RC.B&apos;DA.2025A.189
        </div>
      </Section>
    </>
  );
}
