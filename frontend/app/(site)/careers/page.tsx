import type { Metadata } from "next";
import Link from "next/link";
import { SectionRenderer } from "@/components/site/sections/section-renderer";
import { getPageContent } from "@/lib/page-content";
import {
  ArrowRight,
  Briefcase,
  MapPin,
  Sparkles,
  Heart,
  Globe2,
  Trophy,
  GraduationCap,
  Activity,
  Wallet,
  Home,
  Mail,
  Search,
  MessageSquare,
  PenTool,
  Rocket,
  Lightbulb,
  Users,
} from "lucide-react";
import { Section, SectionHeader } from "@/components/site/section";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { FeatureGrid } from "@/components/site/sections/feature-grid";
import { StatStrip } from "@/components/site/sections/stat-strip";
import { ProcessSteps } from "@/components/site/sections/process-steps";
import { FaqWithAside } from "@/components/site/sections/faq-with-aside";
import { BigQuote } from "@/components/site/sections/big-quote";
import { BrandImage } from "@/components/site/brand-image";
import { api } from "@/lib/api";

export const metadata: Metadata = {
  title: "Careers",
  description:
    "Join QUATA Digital — building Africa's connected digital ecosystem from Bamenda, Cameroon. We're hiring early teammates ahead of our May 2026 launch.",
};

type Job = {
  id: number;
  slug: string;
  title: string;
  department: string;
  location: string;
  employment_type: string;
  is_published: boolean;
  summary: string;
};

async function getJobs(): Promise<Job[]> {
  try {
    return await api<Job[]>("/jobs?published=true");
  } catch {
    return [];
  }
}

// Real open role per leadership.
const fallbackJobs: Job[] = [
  {
    id: 1,
    slug: "business-development-partnerships-manager",
    title: "Business Development & Partnerships Manager",
    department: "Marketing & Growth",
    location: "Bamenda, Cameroon (hybrid)",
    employment_type: "Full-time",
    is_published: true,
    summary:
      "Drive merchant acquisition, strategic partnerships and ecosystem growth as we approach the launch of QUATAPAY and ABAQWA.",
  },
];

export default async function CareersPage() {
  const cms = await getPageContent("careers");
  if (cms) {
    return <SectionRenderer sections={cms.sections} />;
  }
  const fetched = await getJobs();
  const jobs = fetched.length > 0 ? fetched : fallbackJobs;

  const byDepartment = jobs.reduce<Record<string, Job[]>>((acc, j) => {
    (acc[j.department] ??= []).push(j);
    return acc;
  }, {});

  const totalRoles = jobs.length;
  const totalDepartments = Object.keys(byDepartment).length;

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
                <Briefcase className="h-3.5 w-3.5 text-primary" />
                We&apos;re hiring · {totalRoles} open role{totalRoles === 1 ? "" : "s"}
              </div>
              <h1 className="mt-6 text-3xl sm:text-4xl md:text-6xl font-semibold tracking-tight text-balance">
                Build Africa&apos;s connected{" "}
                <span className="text-gradient-brand">digital ecosystem.</span>
              </h1>
              <p className="mt-5 max-w-xl text-lg text-muted-foreground">
                QUATA Digital is an early-stage company launching its first products
                in May 2026. We&apos;re hiring a small founding team — high
                ownership, fast pace, real impact.
              </p>
              <div className="mt-8 flex flex-wrap gap-3">
                <Button size="lg" asChild>
                  <Link href="#roles">
                    See open roles <ArrowRight className="h-4 w-4" />
                  </Link>
                </Button>
                <Button size="lg" variant="outline" asChild>
                  <Link href="/contact">Talk to us</Link>
                </Button>
              </div>
            </div>
            <BrandImage
              src="/images/careers/hero.jpg"
              alt="QUATA Digital team collaborating in Bamenda"
              width={1200}
              height={1000}
              accent="brand"
              priority
            />
          </div>
        </div>
      </section>

      {/* 2. Stats */}
      <Section className="py-10">
        <StatStrip
          variant="card"
          items={[
            { value: totalRoles.toString(), label: "Open roles", icon: Briefcase, tone: "brand" },
            { value: totalDepartments.toString(), label: "Department hiring", icon: Activity, tone: "amber" },
            { value: "1–3w", label: "Average time to hire", icon: Rocket, tone: "sky" },
            { value: "Bamenda", label: "Headquarters", icon: MapPin, tone: "violet" },
          ]}
        />
      </Section>

      {/* 3. Why work here */}
      <Section>
        <SectionHeader
          eyebrow="Why work here"
          title="Real impact, from day one."
          subtitle="QUATA Digital isn't a feature factory. People here own outcomes end-to-end — from problem to operator metric."
        />
        <div className="mt-12">
          <FeatureGrid
            items={[
              { icon: Trophy, title: "Build at the foundation", body: "Help define how African businesses will operate for the next decade.", tone: "amber" },
              { icon: Sparkles, title: "Compounding leverage", body: "Every product on the rail makes the next one easier to ship.", tone: "brand" },
              { icon: Heart, title: "People over process", body: "Small founding team, low ceremony, high agency.", tone: "rose" },
              { icon: Globe2, title: "Built in Africa", body: "Decisions made on the continent, with operators who live the problems.", tone: "sky" },
              { icon: Lightbulb, title: "Ownership early", body: "Early teammates shape products, culture and the company itself.", tone: "violet" },
              { icon: Wallet, title: "Pay fairly", body: "Competitive base, equity for key roles, transparent levelling.", tone: "emerald" },
            ]}
          />
        </div>
      </Section>

      {/* 4. Big quote */}
      <Section className="py-12">
        <BigQuote
          quote="We're a small team building infrastructure for the next generation of African businesses. If that excites you, we want to hear from you."
          author="Neba Clovis Ngwa"
          role="Founder & CEO, QUATA Digital"
        />
      </Section>

      {/* 5. Open roles */}
      <Section id="roles" className="bg-surface-soft rounded-3xl">
        <SectionHeader
          eyebrow="Open roles"
          title="Find your team."
          subtitle={`${totalRoles} role${totalRoles === 1 ? "" : "s"} across ${totalDepartments} department${totalDepartments === 1 ? "" : "s"}.`}
        />

        <div className="mt-12 grid gap-10">
          {Object.entries(byDepartment).map(([dept, items]) => (
            <div key={dept}>
              <div className="flex items-center gap-3">
                <div className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
                  {dept}
                </div>
                <div className="h-px flex-1 bg-border" />
                <Badge variant="outline">
                  {items.length} role{items.length === 1 ? "" : "s"}
                </Badge>
              </div>
              <div className="mt-4 grid gap-3">
                {items.map((j) => (
                  <Link
                    key={j.id}
                    href={`/careers/${j.id}`}
                    className="group flex flex-col md:flex-row md:items-center md:justify-between gap-3 rounded-2xl border border-border bg-card p-5 ring-soft transition hover:-translate-y-0.5"
                  >
                    <div>
                      <div className="text-base font-semibold tracking-tight">{j.title}</div>
                      <div className="mt-1 text-sm text-muted-foreground">{j.summary}</div>
                      <div className="mt-3 flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
                        <span className="inline-flex items-center gap-1">
                          <MapPin className="h-3.5 w-3.5" /> {j.location}
                        </span>
                        <span className="inline-flex items-center gap-1">
                          <Briefcase className="h-3.5 w-3.5" /> {j.employment_type}
                        </span>
                      </div>
                    </div>
                    <div className="text-sm font-medium text-primary inline-flex items-center gap-1.5">
                      View role
                      <ArrowRight className="h-3.5 w-3.5 transition group-hover:translate-x-0.5" />
                    </div>
                  </Link>
                ))}
              </div>
            </div>
          ))}
        </div>
      </Section>

      {/* 5b. Future roles — what's coming */}
      <Section className="py-12">
        <SectionHeader
          eyebrow="On the roadmap"
          title="Roles we&rsquo;ll open as launch nears."
          subtitle="If your background fits one of these, send us a note now — we line people up months before the role goes live."
        />
        <div className="mt-10 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {[
            { dept: "Engineering", role: "Backend & platform engineers" },
            { dept: "Engineering", role: "Mobile / Flutter engineers" },
            { dept: "Product & Design", role: "Product designers" },
            { dept: "Operations", role: "Merchant operations leads" },
            { dept: "Customer Support", role: "Bilingual support specialists (EN/FR)" },
            { dept: "Field Operations", role: "On-the-ground field reps" },
          ].map((r) => (
            <div
              key={r.role}
              className="rounded-2xl border border-dashed border-border bg-surface-soft p-4"
            >
              <div className="text-[11px] uppercase tracking-wider text-muted-foreground">
                {r.dept}
              </div>
              <div className="mt-2 text-sm font-semibold tracking-tight">
                {r.role}
              </div>
              <Link
                href="/contact"
                className="mt-3 inline-flex items-center gap-1 text-xs text-primary hover:underline"
              >
                Express interest <ArrowRight className="h-3 w-3" />
              </Link>
            </div>
          ))}
        </div>
        <p className="mt-6 text-xs text-muted-foreground">
          Indicative only — final role specs are confirmed before each
          opens for application.
        </p>
      </Section>

      {/* 6. Hiring process — real 5-step */}
      <Section>
        <SectionHeader
          eyebrow="Hiring process"
          title="Five steps. About 1–3 weeks."
          subtitle="We tell you the process up-front and stick to it."
        />
        <div className="mt-12">
          <ProcessSteps
            steps={[
              { icon: Mail, title: "Apply", body: "Submit your application — we read every one.", duration: "Day 0" },
              { icon: Search, title: "Initial screening", body: "Quick HR / founder review of your application.", duration: "Within 1 week" },
              { icon: PenTool, title: "Role-based assessment", body: "A focused exercise relevant to the role you're applying for.", duration: "Week 1–2" },
              { icon: MessageSquare, title: "Team / leadership interview", body: "Conversations with the people you'll work with.", duration: "Week 2" },
              { icon: Rocket, title: "Decision & offer", body: "We move fast — typically within a few days of the final round.", duration: "Within 3 days" },
            ]}
          />
        </div>
      </Section>

      {/* 7. Benefits — honest */}
      <Section className="bg-surface-soft rounded-3xl">
        <SectionHeader eyebrow="Benefits" title="What we offer today." />
        <div className="mt-10">
          <FeatureGrid
            columns={3}
            variant="bordered"
            items={[
              { icon: Wallet, title: "Competitive comp", body: "Cash competitive for level + market. Equity for key roles.", tone: "brand" },
              { icon: Sparkles, title: "High-impact work", body: "Touch every part of the business — and ship things customers use.", tone: "amber" },
              { icon: GraduationCap, title: "Learning & growth", body: "Real space to grow — early teammates lead what comes next.", tone: "violet" },
              { icon: Home, title: "Remote-friendly", body: "Hybrid for Bamenda; remote available for the right roles.", tone: "sky" },
              { icon: Activity, title: "Equipment support", body: "Laptop and tools provided based on role.", tone: "emerald" },
              { icon: Heart, title: "Founders you can talk to", body: "Direct access to leadership. No layers between you and decisions.", tone: "rose" },
            ]}
          />
        </div>
        <p className="mt-6 text-xs text-muted-foreground">
          Health, parental leave and broader benefits will scale as the team grows.
        </p>
      </Section>

      {/* 8. Locations */}
      <Section>
        <SectionHeader
          eyebrow="Where we work"
          title="Bamenda first. Remote-friendly."
        />
        <div className="mt-10 grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          <div className="rounded-2xl border border-border bg-card p-6 ring-soft">
            <div className="flex items-center gap-3">
              <MapPin className="h-4 w-4 text-primary" />
              <div className="text-base font-semibold">
                Bamenda
                <span className="text-muted-foreground font-normal">, Cameroon</span>
              </div>
            </div>
            <div className="mt-4 text-sm text-foreground/80">
              North West Region, Cameroon.
            </div>
            <div className="mt-2 text-xs text-muted-foreground">Founding HQ</div>
          </div>
          <div className="rounded-2xl border border-border bg-card p-6 ring-soft">
            <div className="flex items-center gap-3">
              <Home className="h-4 w-4 text-primary" />
              <div className="text-base font-semibold">Remote / hybrid</div>
            </div>
            <div className="mt-4 text-sm text-foreground/80">
              Remote work supported depending on role. Hybrid collaboration encouraged where possible.
            </div>
          </div>
          <div className="rounded-2xl border border-dashed border-border bg-surface-soft p-6">
            <div className="flex items-center gap-3">
              <Globe2 className="h-4 w-4 text-primary" />
              <div className="text-base font-semibold">Pan-African in time</div>
            </div>
            <div className="mt-4 text-sm text-foreground/80">
              We&apos;ll open additional locations as we expand into new markets.
            </div>
          </div>
        </div>
      </Section>

      {/* 9. D&I */}
      <Section className="py-12">
        <div className="rounded-3xl border border-border bg-surface-soft p-6 sm:p-8 md:p-10">
          <div className="flex items-start gap-4">
            <div className="inline-flex h-10 w-10 items-center justify-center rounded-xl bg-brand-soft text-primary shrink-0">
              <Users className="h-5 w-5" />
            </div>
            <div>
              <div className="text-base font-semibold">Diversity & inclusion</div>
              <p className="mt-2 text-sm text-foreground/80 max-w-3xl">
                QUATA Digital is committed to building a diverse and inclusive
                team. We welcome applicants from all backgrounds and believe
                that diverse perspectives drive innovation and better outcomes.
              </p>
            </div>
          </div>
        </div>
      </Section>

      {/* 10. FAQ */}
      <Section className="bg-surface-soft rounded-3xl">
        <SectionHeader eyebrow="FAQ" title="Common questions about hiring." />
        <div className="mt-10">
          <FaqWithAside
            asideTitle="Talk to recruiting"
            asideBody="Have a question that isn&apos;t covered? Our recruiting lead replies personally — usually within one business day."
            asideStats={[
              { value: "1–3w", label: "Avg. time to hire" },
              { value: totalRoles.toString(), label: "Open roles" },
            ]}
            items={[
              { q: "Do you sponsor relocation?", a: "Case-by-case for senior roles into Bamenda. We'll discuss this during the recruiter call." },
              { q: "Are salary ranges public?", a: "Compensation is competitive and depends on experience, level and impact. Specific ranges are shared during the hiring process." },
              { q: "Do you have an internship or graduate programme?", a: "Planned post-launch. Application windows will be announced publicly." },
              { q: "What if I don't see a role that fits me?", a: "Email info@quatadigital.com — for outstanding people we open roles." },
              { q: "How long does the process take?", a: "1–3 weeks from application to offer." },
              { q: "Is equity available?", a: "Equity may be offered to key full-time roles based on seniority and long-term contribution. Details on a case-by-case basis." },
            ]}
          />
        </div>
      </Section>

      {/* 11. CTA */}
      <Section>
        <div className="rounded-3xl border border-border bg-card p-8 md:p-12 text-center ring-soft">
          <div className="mx-auto inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-brand-soft text-primary">
            <Mail className="h-5 w-5" />
          </div>
          <h3 className="mt-4 text-2xl md:text-3xl font-semibold tracking-tight">
            Don&apos;t see your role?
          </h3>
          <p className="mt-3 text-muted-foreground max-w-xl mx-auto">
            We&apos;re always happy to hear from operators, engineers and
            designers who want to be useful in Africa. Send us a note.
          </p>
          <Button size="lg" asChild className="mt-6">
            <Link href="/contact">
              Get in touch <ArrowRight className="h-4 w-4" />
            </Link>
          </Button>
        </div>
      </Section>
    </>
  );
}
