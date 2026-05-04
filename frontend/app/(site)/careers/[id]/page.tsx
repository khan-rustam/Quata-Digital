import { notFound } from "next/navigation";
import Link from "next/link";
import {
  ArrowRight,
  MapPin,
  Briefcase,
  Building2,
  Clock,
  CheckCircle2,
  Users,
  Wallet,
  HeartPulse,
  Home,
  Plane,
  GraduationCap,
  Sparkles,
  Mail,
  MessageSquare,
  PenTool,
  Search,
  Rocket,
} from "lucide-react";
import { Section, SectionHeader } from "@/components/site/section";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { JobApplicationForm } from "@/components/forms/job-application-form";
import { ProcessSteps } from "@/components/site/sections/process-steps";
import { FeatureGrid } from "@/components/site/sections/feature-grid";
import { BigQuote } from "@/components/site/sections/big-quote";
import { FAQ } from "@/components/site/sections/faq";
import { JsonLd, jobJsonLd, breadcrumbJsonLd } from "@/components/site/jsonld";
import { api } from "@/lib/api";

type Job = {
  id: number;
  slug: string;
  title: string;
  department: string;
  location: string;
  employment_type: string;
  summary: string;
  description: string;
  responsibilities: string[];
  requirements: string[];
};

async function getJob(id: string): Promise<Job | null> {
  try {
    return await api<Job>(`/jobs/${id}`);
  } catch {
    return null;
  }
}

async function getRelatedJobs(department: string, excludeId: number): Promise<Job[]> {
  try {
    const jobs = await api<Job[]>(`/jobs?published=true&department=${encodeURIComponent(department)}`);
    return jobs.filter((j) => j.id !== excludeId).slice(0, 3);
  } catch {
    return [];
  }
}

export default async function JobPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const job = await getJob(id);
  if (!job) return notFound();
  const related = await getRelatedJobs(job.department, job.id);

  return (
    <>
      <JsonLd data={jobJsonLd(job)} />
      <JsonLd
        data={breadcrumbJsonLd([
          { name: "Home", href: "/" },
          { name: "Careers", href: "/careers" },
          { name: job.title, href: `/careers/${job.id}` },
        ])}
      />
      {/* 1. Breadcrumb + hero header */}
      <Section className="pt-12 pb-6">
        <div className="text-sm">
          <Link href="/careers" className="text-muted-foreground hover:text-foreground">
            Careers
          </Link>
          <span className="mx-2 text-muted-foreground/60">/</span>
          <span className="text-muted-foreground">{job.department}</span>
          <span className="mx-2 text-muted-foreground/60">/</span>
          <span>{job.title}</span>
        </div>

        <div className="mt-8 grid lg:grid-cols-5 gap-10">
          <div className="lg:col-span-3">
            <Badge variant="brand">{job.department}</Badge>
            <h1 className="mt-4 text-3xl md:text-5xl font-semibold tracking-tight">
              {job.title}
            </h1>
            <div className="mt-5 flex flex-wrap items-center gap-4 text-sm text-muted-foreground">
              <span className="inline-flex items-center gap-1.5">
                <MapPin className="h-4 w-4" />
                {job.location}
              </span>
              <span className="inline-flex items-center gap-1.5">
                <Briefcase className="h-4 w-4" />
                {job.employment_type}
              </span>
              <span className="inline-flex items-center gap-1.5">
                <Building2 className="h-4 w-4" />
                {job.department}
              </span>
            </div>
            <p className="mt-6 text-lg text-muted-foreground">{job.summary}</p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Button size="lg" asChild>
                <Link href="#apply">
                  Apply now <ArrowRight className="h-4 w-4" />
                </Link>
              </Button>
              <Button size="lg" variant="outline" asChild>
                <Link href="/careers">All open roles</Link>
              </Button>
            </div>
          </div>

          <div className="lg:col-span-2">
            <div className="rounded-2xl border border-border bg-surface-soft p-6">
              <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                At a glance
              </div>
              <ul className="mt-4 grid gap-3 text-sm">
                <li className="flex justify-between border-b border-border pb-3">
                  <span className="text-muted-foreground">Department</span>
                  <span className="font-medium">{job.department}</span>
                </li>
                <li className="flex justify-between border-b border-border pb-3">
                  <span className="text-muted-foreground">Location</span>
                  <span className="font-medium">{job.location}</span>
                </li>
                <li className="flex justify-between border-b border-border pb-3">
                  <span className="text-muted-foreground">Type</span>
                  <span className="font-medium">{job.employment_type}</span>
                </li>
                <li className="flex justify-between">
                  <span className="text-muted-foreground">Process</span>
                  <span className="font-medium">~3 weeks</span>
                </li>
              </ul>
            </div>
          </div>
        </div>
      </Section>

      {/* 2. Description + responsibilities + requirements */}
      <Section className="py-12">
        <div className="grid lg:grid-cols-3 gap-10">
          <div className="lg:col-span-2 space-y-10">
            <div>
              <h2 className="text-xl font-semibold tracking-tight">About the role</h2>
              <div className="mt-4 prose prose-sm max-w-none text-foreground/85 whitespace-pre-line">
                {job.description}
              </div>
            </div>

            {job.responsibilities?.length > 0 && (
              <div>
                <h3 className="text-base font-semibold">What you&apos;ll do</h3>
                <ul className="mt-4 grid gap-3">
                  {job.responsibilities.map((r) => (
                    <li
                      key={r}
                      className="flex items-start gap-3 rounded-xl border border-border bg-card p-4 text-sm"
                    >
                      <CheckCircle2 className="mt-0.5 h-4 w-4 text-primary shrink-0" />
                      <span>{r}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {job.requirements?.length > 0 && (
              <div>
                <h3 className="text-base font-semibold">What we&apos;re looking for</h3>
                <ul className="mt-4 grid gap-3">
                  {job.requirements.map((r) => (
                    <li
                      key={r}
                      className="flex items-start gap-3 rounded-xl border border-border bg-card p-4 text-sm"
                    >
                      <Sparkles className="mt-0.5 h-4 w-4 text-primary shrink-0" />
                      <span>{r}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          <aside className="space-y-4">
            <div className="lg:sticky lg:top-24 space-y-4">
              <div className="rounded-2xl border border-border bg-card p-6 ring-soft">
                <div className="flex items-center gap-2">
                  <Users className="h-4 w-4 text-primary" />
                  <div className="text-sm font-semibold">The {job.department} team</div>
                </div>
                <p className="mt-3 text-sm text-muted-foreground">
                  You&apos;ll work alongside a focused group of operators and
                  engineers who own outcomes end-to-end. Small squads, low
                  ceremony, high agency.
                </p>
                <div className="mt-4 flex -space-x-2">
                  {["KM", "AA", "SH", "JK"].map((i) => (
                    <span
                      key={i}
                      className="inline-flex h-8 w-8 items-center justify-center rounded-full bg-brand-soft text-primary text-xs font-semibold ring-2 ring-card"
                    >
                      {i}
                    </span>
                  ))}
                </div>
              </div>

              <div className="rounded-2xl border border-border bg-surface-soft p-6">
                <div className="flex items-center gap-2">
                  <Clock className="h-4 w-4 text-primary" />
                  <div className="text-sm font-semibold">Timing</div>
                </div>
                <p className="mt-3 text-sm text-muted-foreground">
                  Expect ~3 weeks from application to offer. We tell you the
                  process upfront and stick to it.
                </p>
              </div>
            </div>
          </aside>
        </div>
      </Section>

      {/* 3. Quote from a teammate */}
      <Section className="py-8">
        <BigQuote
          quote={`The best thing about working in ${job.department} at QUATA is the loop between shipping and seeing the outcome. There's no waiting for someone else to validate the work — you go talk to the user.`}
          author="A current teammate"
          role={`${job.department}`}
        />
      </Section>

      {/* 4. Hiring process */}
      <Section>
        <SectionHeader
          eyebrow="Hiring process"
          title="What to expect from here."
        />
        <div className="mt-12">
          <ProcessSteps
            steps={[
              { icon: Mail, title: "Apply", body: "Submit the form on this page.", duration: "Day 0" },
              { icon: Search, title: "Recruiter screen", body: "30-min call with recruiting.", duration: "Within 1 week" },
              { icon: MessageSquare, title: "Hiring manager", body: "Conversation about your work.", duration: "Week 2" },
              { icon: PenTool, title: "Practical exercise", body: "Time-boxed take-home or live.", duration: "Week 2-3" },
              { icon: MessageSquare, title: "Team interviews", body: "2–3 chats with the squad.", duration: "Week 3" },
              { icon: Rocket, title: "Offer", body: "Decision within 48h of final round.", duration: "Within 3 days" },
            ]}
          />
        </div>
      </Section>

      {/* 5. Benefits */}
      <Section className="bg-surface-soft rounded-3xl">
        <SectionHeader
          eyebrow="Compensation & benefits"
          title="What QUATA offers."
        />
        <div className="mt-10">
          <FeatureGrid
            columns={4}
            variant="bordered"
            items={[
              { icon: Wallet, title: "Competitive comp + equity", body: "Cash and meaningful equity, transparent bands.", tone: "brand" },
              { icon: HeartPulse, title: "Health cover", body: "For you and dependents.", tone: "rose" },
              { icon: Home, title: "Remote-friendly", body: "Hubs in 3 cities, work from anywhere in-region.", tone: "sky" },
              { icon: Plane, title: "Annual offsite", body: "Whole-team gathering once a year.", tone: "amber" },
              { icon: GraduationCap, title: "$1,500 learning", body: "Books, courses, conferences — yearly.", tone: "violet" },
              { icon: HeartPulse, title: "Parental leave", body: "16 weeks paid for primary caregiver.", tone: "emerald" },
            ]}
          />
        </div>
      </Section>

      {/* 6. Apply form */}
      <Section id="apply">
        <SectionHeader
          eyebrow="Apply"
          title={`Ready to join us as ${job.title}?`}
          subtitle="Takes about 5 minutes. We aim to respond within a week."
        />
        <div className="mt-10 max-w-2xl">
          <div className="rounded-2xl border border-border bg-card p-6 md:p-8 ring-soft">
            <JobApplicationForm jobId={job.id} />
          </div>
        </div>
      </Section>

      {/* 7. Other roles in the same department */}
      {related.length > 0 && (
        <Section>
          <div className="flex items-end justify-between gap-4">
            <SectionHeader
              eyebrow="Same team"
              title={`Other ${job.department} roles`}
            />
            <Link
              href="/careers"
              className="text-sm font-medium text-primary inline-flex items-center gap-1 shrink-0"
            >
              See all <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </div>
          <div className="mt-8 grid gap-3">
            {related.map((r) => (
              <Link
                key={r.id}
                href={`/careers/${r.id}`}
                className="group flex flex-col md:flex-row md:items-center md:justify-between gap-3 rounded-2xl border border-border bg-card p-5 ring-soft transition hover:-translate-y-0.5"
              >
                <div>
                  <div className="text-base font-semibold tracking-tight">{r.title}</div>
                  <div className="mt-1 text-sm text-muted-foreground">{r.summary}</div>
                  <div className="mt-3 flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
                    <span className="inline-flex items-center gap-1">
                      <MapPin className="h-3.5 w-3.5" /> {r.location}
                    </span>
                    <span className="inline-flex items-center gap-1">
                      <Briefcase className="h-3.5 w-3.5" /> {r.employment_type}
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
        </Section>
      )}

      {/* 8. FAQ */}
      <Section>
        <SectionHeader eyebrow="FAQ" title="Common questions about this role." />
        <div className="mt-10 max-w-3xl">
          <FAQ
            items={[
              { q: "Is this role open to candidates outside the listed location?", a: "Often yes — confirm with the recruiter on the screening call." },
              { q: "Can I apply if I don't tick every requirement?", a: "Yes. Requirements are guidelines; please apply if you can do the work." },
              { q: "Do you sponsor visas?", a: "For senior roles into our hub cities, yes." },
              { q: "Is salary disclosed up-front?", a: "We share the band on the recruiter call." },
              { q: "How will I hear back?", a: "Email — usually within a week." },
            ]}
          />
        </div>
      </Section>
    </>
  );
}
