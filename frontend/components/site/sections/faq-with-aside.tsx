"use client";

import * as React from "react";
import Link from "next/link";
import { LifeBuoy, MessageCircle, Mail, ShieldAlert, Sparkles, Users } from "lucide-react";
import { FAQ, type FaqItem } from "./faq";

const ASIDE_ICONS = {
  lifebuoy: LifeBuoy,
  shieldAlert: ShieldAlert,
  sparkles: Sparkles,
  users: Users,
} as const;

export type AsideIconName = keyof typeof ASIDE_ICONS;

/**
 * FaqWithAside — FAQ on the left, decorated support panel on the right
 * (or vice-versa). Use this anywhere a one-column FAQ leaves the page
 * looking empty.
 *
 * The aside is intentionally small: a card with an icon, a few stat
 * lines, and a "talk to a human" CTA. It exists to balance the layout,
 * not to compete with the FAQ.
 */
export function FaqWithAside({
  items,
  asidePosition = "right",
  asideTitle = "Still have questions?",
  asideBody = "We read every message. A real human replies — usually within one business day.",
  asideEmail = "info@quatadigital.com",
  asideCta = { label: "Contact the team", href: "/contact" },
  asideIcon = "lifebuoy",
  asideStats,
}: {
  items: FaqItem[];
  asidePosition?: "left" | "right";
  asideTitle?: string;
  asideBody?: string;
  asideEmail?: string;
  asideCta?: { label: string; href: string };
  asideIcon?: AsideIconName;
  asideStats?: { label: string; value: string }[];
}) {
  const AsideIcon = ASIDE_ICONS[asideIcon];
  const aside = (
    <aside className="lg:sticky lg:top-28 self-start space-y-4">
      <div className="relative overflow-hidden rounded-2xl border border-border bg-card p-6 ring-soft">
        {/* Brand-tinted halo */}
        <div
          aria-hidden
          className="absolute -top-20 -right-20 h-44 w-44 rounded-full opacity-20 blur-2xl"
          style={{
            background: "radial-gradient(closest-side, rgba(14,91,74,0.6), transparent)",
          }}
        />
        <div className="relative flex items-center gap-3">
          <span className="inline-flex h-11 w-11 items-center justify-center rounded-xl bg-brand-soft text-primary ring-1 ring-primary/15">
            <AsideIcon className="h-5 w-5" />
          </span>
          <div>
            <div className="text-base font-semibold tracking-tight">{asideTitle}</div>
            <div className="text-xs text-muted-foreground">Real humans, fast replies</div>
          </div>
        </div>
        <p className="mt-4 text-sm text-muted-foreground leading-relaxed">{asideBody}</p>

        {asideStats && asideStats.length > 0 && (
          <ul className="mt-5 grid grid-cols-2 gap-3">
            {asideStats.map((s) => (
              <li
                key={s.label}
                className="rounded-xl border border-border bg-surface-soft p-3"
              >
                <div className="text-base font-semibold tracking-tight">{s.value}</div>
                <div className="text-[11px] text-muted-foreground mt-0.5">{s.label}</div>
              </li>
            ))}
          </ul>
        )}

        <div className="mt-5 flex flex-col gap-2">
          <Link
            href={asideCta.href}
            className="inline-flex items-center justify-center gap-2 rounded-full bg-primary text-primary-foreground px-4 py-2.5 text-sm font-semibold hover:brightness-95 transition"
          >
            <MessageCircle className="h-4 w-4" />
            {asideCta.label}
          </Link>
          <a
            href={`mailto:${asideEmail}`}
            className="inline-flex items-center justify-center gap-2 rounded-full border border-border bg-surface px-4 py-2.5 text-sm font-medium text-foreground hover:bg-secondary transition"
          >
            <Mail className="h-4 w-4 text-primary" />
            {asideEmail}
          </a>
        </div>
      </div>

      <div className="rounded-2xl border border-dashed border-border p-5 text-xs text-muted-foreground">
        <span className="font-semibold text-foreground">Tip:</span> can&apos;t
        find your answer? Search the site (top-right) or browse our{" "}
        <Link href="/blog" className="text-primary font-medium">
          news &amp; insights
        </Link>
        .
      </div>
    </aside>
  );

  return (
    <div className="grid lg:grid-cols-[1.4fr_0.9fr] gap-8 lg:gap-12 items-start">
      {asidePosition === "left" && aside}
      <div>
        <FAQ items={items} />
      </div>
      {asidePosition === "right" && aside}
    </div>
  );
}
