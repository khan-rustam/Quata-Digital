import type { Metadata } from "next";
import Link from "next/link";
import { SectionRenderer } from "@/components/site/sections/section-renderer";
import { getPageContent } from "@/lib/page-content";
import {
  Mail,
  MapPin,
  HeartHandshake,
  Briefcase,
  Coins,
  Headphones,
  Clock,
  MessageCircle,
  ArrowRight,
  Building2,
  Globe2,
  Phone,
} from "lucide-react";
import { Section, SectionHeader } from "@/components/site/section";
import { ContactForm } from "@/components/forms/contact-form";
import { FaqWithAside } from "@/components/site/sections/faq-with-aside";
import { Illustration } from "@/components/site/illustrations/illustration";
import { DEFAULT_PUBLIC_PHONE } from "@/lib/site-settings";

export const metadata: Metadata = {
  title: "Contact",
  description:
    "Get in touch with QUATA Digital — Bamenda, Cameroon. info@quatadigital.com / support@quatadigital.com.",
};

const channels = [
  {
    icon: MessageCircle,
    title: "General",
    desc: "Anything not covered below — we'll route it to the right team.",
    email: "info@quatadigital.com",
    tone: "bg-brand-soft text-primary",
  },
  {
    icon: Headphones,
    title: "Customer support",
    desc: "Help with a product, account or transaction.",
    email: "support@quatadigital.com",
    tone: "bg-sky-100 text-sky-900",
  },
  {
    icon: HeartHandshake,
    title: "Partnerships",
    desc: "Banks, telcos, fleets, platforms — let's talk.",
    email: "pi@quatadigital.com",
    tone: "bg-emerald-100 text-emerald-900",
  },
  {
    icon: Coins,
    title: "Investor relations",
    desc: "Pre-seed / seed investors — submit interest here.",
    email: "pi@quatadigital.com",
    tone: "bg-amber-100 text-amber-900",
  },
  {
    icon: Briefcase,
    title: "Careers",
    desc: "Hiring questions. Applicants apply on the careers page.",
    email: "careers@quatadigital.com",
    tone: "bg-rose-100 text-rose-900",
  },
];

export default async function ContactPage() {
  const cms = await getPageContent("contact");
  if (cms) {
    return <SectionRenderer sections={cms.sections} />;
  }
  return (
    <>
      {/* 1. Hero */}
      <section className="relative overflow-hidden -mt-20">
        <div className="absolute inset-0 -z-10 bg-linear-to-b from-brand-soft/40 via-surface to-surface" />
        <div className="absolute inset-0 -z-10 dot-grid mask-fade-b opacity-50" />
        <div className="container-page pt-34 sm:pt-40 md:pt-44 pb-14 sm:pb-20 md:pb-24">
          <div className="grid lg:grid-cols-2 gap-10 lg:gap-16 items-center">
            <div>
              <div className="inline-flex items-center gap-2 rounded-full border border-border bg-surface/80 px-3 py-1 text-xs text-muted-foreground backdrop-blur">
                <MessageCircle className="h-3.5 w-3.5 text-primary" />
                Get in touch
              </div>
              <h1 className="mt-6 text-3xl sm:text-4xl md:text-6xl font-semibold tracking-tight max-w-2xl text-balance">
                Tell us what you&apos;re{" "}
                <span className="text-gradient-brand">trying to do.</span>
              </h1>
              <p className="mt-5 max-w-2xl text-lg text-muted-foreground">
                We read every message that comes through. Pick the inbox that fits,
                or send a general note and we&apos;ll route you to the right team.
              </p>
            </div>
            <Illustration
              name="contact-hero"
              alt="A QUATA Digital customer-support agent with a headset replying to messages"
              width={1200}
              height={900}
            />
          </div>
        </div>
      </section>

      {/* 2. Multi-purpose contact options */}
      <Section className="py-12">
        <SectionHeader eyebrow="Reach the right team" title="One inbox per question." />
        <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {channels.map((c) => (
            <a
              key={c.title}
              href={`mailto:${c.email}?subject=${encodeURIComponent(c.title)}`}
              className="group rounded-2xl border border-border bg-card p-5 ring-soft transition hover:-translate-y-0.5"
            >
              <div className={`inline-flex h-10 w-10 items-center justify-center rounded-xl ${c.tone}`}>
                <c.icon className="h-5 w-5" />
              </div>
              <div className="mt-4 text-base font-semibold tracking-tight">{c.title}</div>
              <p className="mt-1.5 text-sm text-muted-foreground">{c.desc}</p>
              <div className="mt-4 inline-flex items-center gap-1.5 text-sm font-medium text-primary break-all">
                {c.email}
                <ArrowRight className="h-3.5 w-3.5 transition group-hover:translate-x-0.5 shrink-0" />
              </div>
            </a>
          ))}
        </div>
      </Section>

      {/* 3. General contact form + sidebar */}
      <Section>
        <div className="grid lg:grid-cols-5 gap-10">
          <div className="lg:col-span-2 space-y-4">
            <SectionHeader
              eyebrow="General contact"
              title="Not sure who to email?"
              subtitle="Send us a note and we'll route it internally — no need to find the right inbox."
            />
            <div className="rounded-2xl border border-border bg-surface-soft p-5">
              <div className="flex items-center gap-2">
                <Clock className="h-4 w-4 text-primary" />
                <div className="text-sm font-semibold">Response time</div>
              </div>
              <p className="mt-3 text-sm text-muted-foreground">
                We aim to respond to general enquiries within 1 business day,
                and partnership / investor enquiries within 3 business days.
              </p>
            </div>
            <div className="rounded-2xl border border-border bg-card p-5">
              <div className="flex items-center gap-2">
                <Headphones className="h-4 w-4 text-primary" />
                <div className="text-sm font-semibold">Customer support</div>
              </div>
              <p className="mt-3 text-sm text-muted-foreground">
                For account or transaction help, please email{" "}
                <a href="mailto:support@quatadigital.com" className="text-primary font-medium break-all">
                  support@quatadigital.com
                </a>
                .
              </p>
            </div>
          </div>

          <div className="lg:col-span-3">
            <div className="rounded-2xl border border-border bg-card p-6 md:p-8 ring-soft">
              <ContactForm />
            </div>
          </div>
        </div>
      </Section>

      {/* 4. Office */}
      <Section className="bg-surface-soft rounded-3xl">
        <SectionHeader eyebrow="Headquarters" title="Find us in Bamenda." />
        <div className="mt-10 grid lg:grid-cols-3 gap-4">
          <div className="lg:col-span-2 rounded-2xl border border-border bg-card p-6 sm:p-8 ring-soft">
            <div className="inline-flex h-10 w-10 items-center justify-center rounded-xl bg-brand-soft text-primary">
              <Building2 className="h-5 w-5" />
            </div>
            <div className="mt-5 text-xl font-semibold tracking-tight">
              Bamenda
              <span className="text-muted-foreground font-normal">, Cameroon</span>
            </div>
            <ul className="mt-5 grid sm:grid-cols-2 gap-3 text-sm">
              <li className="flex items-start gap-2 text-muted-foreground">
                <MapPin className="h-3.5 w-3.5 text-primary mt-1 shrink-0" />
                <span>Bamenda, North West Region, Cameroon</span>
              </li>
              <li className="flex items-start gap-2 text-muted-foreground">
                <Mail className="h-3.5 w-3.5 text-primary mt-1 shrink-0" />
                <a href="mailto:info@quatadigital.com" className="hover:text-foreground break-all">
                  info@quatadigital.com
                </a>
              </li>
              {(() => {
                // Env override wins; otherwise fall back to the baked-in
                // default so the contact row always renders. Strip everything
                // except digits + leading `+` from the `tel:` href so visiting
                // links don't break on a number formatted with spaces.
                const phoneDisplay =
                  process.env.NEXT_PUBLIC_CONTACT_PHONE ?? DEFAULT_PUBLIC_PHONE;
                const phoneHref = phoneDisplay.replace(/[^\d+]/g, "");
                return (
                  <li className="flex items-start gap-2 text-muted-foreground">
                    <Phone className="h-3.5 w-3.5 text-primary mt-1 shrink-0" />
                    <a href={`tel:${phoneHref}`} className="hover:text-foreground">
                      {phoneDisplay}
                    </a>
                  </li>
                );
              })()}
              <li className="flex items-start gap-2 text-muted-foreground">
                <Clock className="h-3.5 w-3.5 text-primary mt-1 shrink-0" />
                <span>Mon–Fri, 09:00–18:00 WAT</span>
              </li>
            </ul>
          </div>
          <Illustration
            name="contact-office"
            alt="QUATA Digital headquarters in Bamenda, Cameroon"
            width={800}
            height={600}
            caption="HQ in Bamenda — more offices will follow as we expand across Africa."
          />
        </div>
      </Section>

      {/* 5. Hours */}
      <Section>
        <div className="grid lg:grid-cols-3 gap-4">
          <div className="rounded-2xl border border-border bg-card p-6 ring-soft">
            <Clock className="h-5 w-5 text-primary" />
            <div className="mt-4 text-base font-semibold">Office hours</div>
            <p className="mt-2 text-sm text-muted-foreground">
              Monday – Friday, 09:00 – 18:00 WAT.
            </p>
          </div>
          <div className="rounded-2xl border border-border bg-card p-6 ring-soft">
            <Headphones className="h-5 w-5 text-primary" />
            <div className="mt-4 text-base font-semibold">Support coverage</div>
            <p className="mt-2 text-sm text-muted-foreground">
              Customer support replies during office hours. Critical-incident
              response is on call for partners.
            </p>
          </div>
          <div className="rounded-2xl border border-border bg-card p-6 ring-soft">
            <Globe2 className="h-5 w-5 text-primary" />
            <div className="mt-4 text-base font-semibold">Language</div>
            <p className="mt-2 text-sm text-muted-foreground">
              We operate in English. French support is on the roadmap with
              regional expansion.
            </p>
          </div>
        </div>
      </Section>

      {/* 6. FAQ */}
      <Section className="bg-surface-soft rounded-3xl">
        <SectionHeader eyebrow="FAQ" title="Quick answers." />
        <div className="mt-10">
          <FaqWithAside
            asideTitle="Prefer a real conversation?"
            asideBody="No bots, no auto-routers. The contact form goes to a real human at QUATA Digital who replies personally."
            asideStats={[
              { value: "1 day", label: "Avg. response" },
              { value: "Bamenda", label: "Headquarters" },
            ]}
            items={[
              {
                q: "How fast will I hear back?",
                a: "Same business day for most general enquiries. Partnership and investor enquiries within 3 business days.",
              },
              {
                q: "Can I visit the Bamenda office?",
                a: "Yes — by appointment. Email info@quatadigital.com to arrange.",
              },
              {
                q: "Where do I send a security disclosure?",
                a: "support@quatadigital.com (full details on the /security page).",
              },
              {
                q: "I want to be a vendor or supplier — where do I write?",
                a: "Email info@quatadigital.com with a brief description of what you supply.",
              },
              {
                q: "Do you respond to recruitment outreach?",
                a: "If your tool is genuinely useful for an early-stage African platform, yes — please be specific and brief.",
              },
            ]}
          />
        </div>
      </Section>

      {/* 7. Other ways CTA */}
      <Section>
        <div className="rounded-3xl border border-border bg-ink text-white p-10 md:p-14 grid md:grid-cols-2 gap-8 items-center relative overflow-hidden">
          <div className="absolute inset-0 dot-grid opacity-20" />
          <div className="relative">
            <h3 className="text-2xl md:text-4xl font-semibold tracking-tight">
              Want a faster route?
            </h3>
            <p className="mt-3 text-white/70">
              Apply directly to the path that fits — partner, careers or investor.
            </p>
          </div>
          <div className="relative md:justify-self-end flex flex-wrap gap-3">
            <Link
              href="/partners"
              className="inline-flex items-center gap-2 rounded-full bg-accent text-accent-foreground px-5 py-2.5 text-sm font-medium hover:brightness-95"
            >
              <HeartHandshake className="h-4 w-4" />
              Become a partner
            </Link>
            <Link
              href="/careers"
              className="inline-flex items-center gap-2 rounded-full border border-white/20 px-5 py-2.5 text-sm font-medium hover:bg-white/10"
            >
              <Briefcase className="h-4 w-4" />
              See open roles
            </Link>
            <Link
              href="/partners/investor"
              className="inline-flex items-center gap-2 rounded-full border border-white/20 px-5 py-2.5 text-sm font-medium hover:bg-white/10"
            >
              <Coins className="h-4 w-4" />
              Investor enquiry
            </Link>
          </div>
        </div>
      </Section>
    </>
  );
}
