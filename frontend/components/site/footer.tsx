import Link from "next/link";
import { Logo } from "./logo";
import { Mail, MapPin, Phone, ArrowUpRight } from "lucide-react";
import { products } from "@/lib/ecosystem";
import {
  getSiteSettings,
  DEFAULT_PUBLIC_EMAIL,
  DEFAULT_PUBLIC_PHONE,
} from "@/lib/site-settings";

function FacebookIcon(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" {...props}>
      <path d="M22 12.07C22 6.51 17.52 2 12 2S2 6.51 2 12.07c0 5 3.66 9.15 8.44 9.93v-7.02h-2.54v-2.91h2.54V9.85c0-2.51 1.49-3.89 3.77-3.89 1.09 0 2.24.2 2.24.2v2.47h-1.26c-1.24 0-1.63.78-1.63 1.57v1.88h2.78l-.44 2.91h-2.34V22c4.78-.78 8.44-4.93 8.44-9.93Z" />
    </svg>
  );
}

function InstagramIcon(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" {...props}>
      <path d="M12 2.16c3.2 0 3.58 0 4.85.07 1.17.05 1.81.25 2.23.41.56.22.96.48 1.38.9.42.42.68.82.9 1.38.16.42.36 1.06.41 2.23.06 1.27.07 1.65.07 4.85s0 3.58-.07 4.85c-.05 1.17-.25 1.81-.41 2.23-.22.56-.48.96-.9 1.38-.42.42-.82.68-1.38.9-.42.16-1.06.36-2.23.41-1.27.06-1.65.07-4.85.07s-3.58 0-4.85-.07c-1.17-.05-1.81-.25-2.23-.41a3.73 3.73 0 0 1-1.38-.9 3.73 3.73 0 0 1-.9-1.38c-.16-.42-.36-1.06-.41-2.23C2.17 15.58 2.16 15.2 2.16 12s0-3.58.07-4.85c.05-1.17.25-1.81.41-2.23.22-.56.48-.96.9-1.38.42-.42.82-.68 1.38-.9.42-.16 1.06-.36 2.23-.41C8.42 2.17 8.8 2.16 12 2.16ZM12 0C8.74 0 8.33.01 7.05.07 5.78.13 4.9.33 4.14.63a5.9 5.9 0 0 0-2.13 1.38A5.9 5.9 0 0 0 .63 4.14C.33 4.9.13 5.78.07 7.05.01 8.33 0 8.74 0 12s.01 3.67.07 4.95c.06 1.27.26 2.15.56 2.91.31.79.73 1.46 1.38 2.13a5.9 5.9 0 0 0 2.13 1.38c.76.3 1.64.5 2.91.56C8.33 23.99 8.74 24 12 24s3.67-.01 4.95-.07c1.27-.06 2.15-.26 2.91-.56a5.9 5.9 0 0 0 2.13-1.38 5.9 5.9 0 0 0 1.38-2.13c.3-.76.5-1.64.56-2.91.06-1.28.07-1.69.07-4.95s-.01-3.67-.07-4.95c-.06-1.27-.26-2.15-.56-2.91a5.9 5.9 0 0 0-1.38-2.13A5.9 5.9 0 0 0 19.86.63C19.1.33 18.22.13 16.95.07 15.67.01 15.26 0 12 0Zm0 5.84A6.16 6.16 0 1 0 18.16 12 6.16 6.16 0 0 0 12 5.84Zm0 10.16A4 4 0 1 1 16 12a4 4 0 0 1-4 4Zm6.4-11.85a1.44 1.44 0 1 0 1.44 1.44 1.44 1.44 0 0 0-1.44-1.44Z" />
    </svg>
  );
}

function LinkedinIcon(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" {...props}>
      <path d="M20.45 20.45h-3.55v-5.57c0-1.33-.02-3.04-1.85-3.04-1.85 0-2.13 1.45-2.13 2.94v5.67H9.36V9h3.41v1.56h.05c.47-.9 1.64-1.85 3.37-1.85 3.6 0 4.27 2.37 4.27 5.46v6.28ZM5.34 7.43a2.06 2.06 0 1 1 0-4.12 2.06 2.06 0 0 1 0 4.12ZM7.12 20.45H3.56V9h3.56v11.45ZM22.23 0H1.77C.79 0 0 .77 0 1.72v20.56C0 23.23.79 24 1.77 24h20.45C23.2 24 24 23.23 24 22.28V1.72C24 .77 23.2 0 22.23 0Z" />
    </svg>
  );
}

function TwitterIcon(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" {...props}>
      <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24h-6.66l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231 5.45-6.231Zm-1.161 17.52h1.833L7.084 4.126H5.117l11.966 15.644Z" />
    </svg>
  );
}

function YoutubeIcon(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" {...props}>
      <path d="M23.5 6.2a3.02 3.02 0 0 0-2.13-2.14C19.46 3.55 12 3.55 12 3.55s-7.46 0-9.37.51A3.02 3.02 0 0 0 .5 6.2C0 8.13 0 12 0 12s0 3.87.5 5.8a3.02 3.02 0 0 0 2.13 2.14c1.91.51 9.37.51 9.37.51s7.46 0 9.37-.51a3.02 3.02 0 0 0 2.13-2.14C24 15.87 24 12 24 12s0-3.87-.5-5.8ZM9.55 15.57V8.43L15.82 12l-6.27 3.57Z" />
    </svg>
  );
}

const groups = [
  {
    title: "Ecosystem",
    items: products.map((p) => ({ label: p.name, href: `/ecosystem/${p.slug}` })),
  },
  {
    title: "Partner",
    items: [
      { label: "Business partners", href: "/partners/business" },
      { label: "Strategic partners", href: "/partners/strategic" },
      { label: "Investors", href: "/partners/investor" },
      { label: "Service partners", href: "/partners/service" },
    ],
  },
  {
    title: "Company",
    items: [
      { label: "About", href: "/about" },
      { label: "Careers", href: "/careers" },
      { label: "News", href: "/blog" },
      { label: "Contact", href: "/contact" },
    ],
  },
  {
    title: "Legal & trust",
    items: [
      { label: "Privacy policy", href: "/privacy" },
      { label: "Terms of service", href: "/terms" },
      { label: "Security", href: "/security" },
    ],
  },
];

const DEFAULT_ADDRESS_LINES = [
  "Bamenda, North West Region, Cameroon",
];
const DEFAULT_SUPPORT_EMAIL = "support@quatadigital.com";

export async function Footer() {
  const settings = await getSiteSettings();
  // Resolution order: admin-configured value → env override → baked-in
  // default. The default keeps the contact row populated on a fresh
  // deploy where nobody has filled in Site Settings yet.
  const phone =
    settings.contact.phone ??
    process.env.NEXT_PUBLIC_CONTACT_PHONE ??
    DEFAULT_PUBLIC_PHONE;
  const publicEmail = settings.contact.email ?? DEFAULT_PUBLIC_EMAIL;
  const addressLines = settings.contact.address
    ? settings.contact.address.split("\n").map((l) => l.trim()).filter(Boolean)
    : DEFAULT_ADDRESS_LINES;

  // Order matches the rendered icon row below; entry is dropped when null.
  const socialLinks: { href: string; label: string; icon: React.ComponentType<React.SVGProps<SVGSVGElement>> }[] = [
    settings.social.facebook_url
      ? { href: settings.social.facebook_url, label: "Facebook", icon: FacebookIcon }
      : { href: "https://www.facebook.com/share/1HFDnBuFWz/", label: "Facebook", icon: FacebookIcon },
    settings.social.instagram_url
      ? { href: settings.social.instagram_url, label: "Instagram", icon: InstagramIcon }
      : { href: "https://www.instagram.com/quatadigital", label: "Instagram", icon: InstagramIcon },
  ];
  if (settings.social.linkedin_url) {
    socialLinks.push({ href: settings.social.linkedin_url, label: "LinkedIn", icon: LinkedinIcon });
  }
  if (settings.social.twitter_url) {
    socialLinks.push({ href: settings.social.twitter_url, label: "Twitter / X", icon: TwitterIcon });
  }
  if (settings.social.youtube_url) {
    socialLinks.push({ href: settings.social.youtube_url, label: "YouTube", icon: YoutubeIcon });
  }

  return (
    <footer className="mt-24 relative overflow-hidden border-t border-border bg-ink text-white">
      {/* Centered single-line text watermark — fluid font size keeps the
          whole word on one line at every breakpoint. Brand-amber gradient
          at low opacity so it reads as a flourish, not a billboard. */}
      <div
        aria-hidden
        className="pointer-events-none select-none absolute inset-x-0 bottom-0 flex justify-center overflow-hidden"
      >
        <span
          className="whitespace-nowrap font-extrabold leading-none"
          style={{
            fontSize: "clamp(3rem, 14vw, 14rem)",
            background:
              "linear-gradient(180deg, rgba(232,177,74,0.16) 0%, rgba(232,177,74,0.02) 100%)",
            WebkitBackgroundClip: "text",
            backgroundClip: "text",
            color: "transparent",
            letterSpacing: "-0.05em",
            transform: "translateY(18%)",
          }}
        >
          QUATA DIGITAL
        </span>
      </div>
      {/* Soft accent rule across the very top of the footer */}
      <div
        aria-hidden
        className="absolute inset-x-0 top-0 h-px"
        style={{
          background:
            "linear-gradient(90deg, transparent, rgba(232,177,74,0.55), transparent)",
        }}
      />
      <div aria-hidden className="absolute inset-0 dot-grid opacity-[0.05]" />

      <div className="container-page relative pt-20 pb-10">
        {/* Top hero strip — tagline + CTAs */}
        <div className="grid lg:grid-cols-[1.4fr_1fr] gap-10 lg:gap-16 pb-14 border-b border-white/10">
          <div>
            <div className="text-3xl sm:text-4xl md:text-5xl font-semibold tracking-tight max-w-2xl text-balance leading-[1.1]">
              The connected operating system for{" "}
              <span
                className="font-bold"
                style={{
                  background: "linear-gradient(135deg,#34d3a7,#7be0c0)",
                  WebkitBackgroundClip: "text",
                  backgroundClip: "text",
                  color: "transparent",
                }}
              >
                Africa&rsquo;s next decade.
              </span>
            </div>
            <p className="mt-5 max-w-xl text-sm sm:text-base text-white/70">
              Payments, business operations and commerce on one rail —
              built in Bamenda, designed for the continent.
            </p>
          </div>
          <div className="flex flex-col justify-center gap-3 sm:flex-row lg:flex-col lg:items-end">
            <Link
              href="/partners"
              className="group inline-flex items-center justify-center gap-2 rounded-full bg-accent text-accent-foreground px-6 py-3 text-sm font-semibold hover:brightness-95 transition"
            >
              Become a partner
              <ArrowUpRight className="h-4 w-4 transition group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
            </Link>
            <Link
              href="/contact"
              className="group inline-flex items-center justify-center gap-2 rounded-full border border-white/20 px-6 py-3 text-sm font-medium text-white hover:bg-white/10 transition"
            >
              Talk to the team
              <ArrowUpRight className="h-4 w-4 transition group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
            </Link>
          </div>
        </div>

        {/* Main grid: brand + contact + nav columns */}
        <div className="mt-12 grid grid-cols-2 md:grid-cols-6 gap-10 gap-y-12">
          <div className="col-span-2">
            <Logo variant="light" size="xl" />
            <p className="mt-5 max-w-sm text-sm text-white/70 leading-relaxed">
              QUATA Digital Enterprise is building Africa&apos;s connected
              digital ecosystem — payments, business operations and commerce
              on one rail.
            </p>

            <ul className="mt-7 space-y-3 text-xs">
              <li className="flex items-start gap-2.5">
                <MapPin className="h-3.5 w-3.5 text-accent mt-0.5 shrink-0" />
                <span className="text-white/75">
                  {addressLines.map((line, i) => (
                    <span key={i}>
                      {line}
                      {i < addressLines.length - 1 && <br />}
                    </span>
                  ))}
                </span>
              </li>
              <li className="flex items-center gap-2.5">
                <Mail className="h-3.5 w-3.5 text-accent" />
                <a
                  href={`mailto:${publicEmail}`}
                  className="text-white/75 hover:text-white transition"
                >
                  {publicEmail}
                </a>
              </li>
              <li className="flex items-center gap-2.5">
                <Mail className="h-3.5 w-3.5 text-accent" />
                <a
                  href={`mailto:${DEFAULT_SUPPORT_EMAIL}`}
                  className="text-white/75 hover:text-white transition"
                >
                  {DEFAULT_SUPPORT_EMAIL}
                </a>
              </li>
              {phone && (
                <li className="flex items-center gap-2.5">
                  <Phone className="h-3.5 w-3.5 text-accent" />
                  <a
                    href={`tel:${phone.replace(/\s+/g, "")}`}
                    className="text-white/75 hover:text-white transition"
                  >
                    {phone}
                  </a>
                </li>
              )}
              {settings.contact.support_hours && (
                <li className="flex items-center gap-2.5 text-white/55">
                  <span className="ml-5.5">{settings.contact.support_hours}</span>
                </li>
              )}
            </ul>

            <div className="mt-7 flex items-center gap-2.5">
              {socialLinks.map((s) => (
                <a
                  key={s.href + s.label}
                  href={s.href}
                  target="_blank"
                  rel="noreferrer"
                  aria-label={`Follow QUATA Digital on ${s.label}`}
                  className="h-9 w-9 inline-flex items-center justify-center rounded-full border border-white/15 text-white/70 hover:text-white hover:bg-white/10 transition"
                >
                  <s.icon className="h-3.5 w-3.5" />
                </a>
              ))}
            </div>
          </div>

          {groups.map((g) => (
            <div key={g.title}>
              <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-accent">
                {g.title}
              </div>
              <ul className="mt-5 space-y-3 text-sm">
                {g.items.map((item) => (
                  <li key={item.href}>
                    <Link
                      href={item.href}
                      className="text-white/75 hover:text-white transition"
                    >
                      {item.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        {/* Bottom strip: copyright + reg + small nav */}
        <div className="mt-16 flex flex-col-reverse md:flex-row items-start md:items-center justify-between gap-4 border-t border-white/10 pt-6">
          <div className="text-xs text-white/55">
            © {new Date().getFullYear()} QUATA Digital Enterprise. All rights
            reserved.
            <span className="mx-2 text-white/25">·</span>
            Reg.{" "}
            <code className="text-[10px] bg-white/5 border border-white/10 rounded px-1.5 py-0.5 text-white/70">
              RC/BDA/2025A/189
            </code>
            <span className="mx-2 text-white/25">·</span>
            Tax ID{" "}
            <code className="text-[10px] bg-white/5 border border-white/10 rounded px-1.5 py-0.5 text-white/70">
              M052517750267W
            </code>
          </div>
          <div className="flex items-center gap-5 text-xs text-white/55">
            <Link href="/privacy" className="hover:text-white transition">Privacy</Link>
            <Link href="/terms" className="hover:text-white transition">Terms</Link>
            <Link href="/security" className="hover:text-white transition">Security</Link>
          </div>
        </div>
      </div>
    </footer>
  );
}
