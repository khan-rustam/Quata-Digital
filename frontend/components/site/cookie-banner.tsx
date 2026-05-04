"use client";

import * as React from "react";
import Link from "next/link";
import { Cookie, X } from "lucide-react";
import { Button } from "@/components/ui/button";

const STORAGE_KEY = "quata_cookie_consent";

export type ConsentValue = "all" | "essential";

export function getConsent(): ConsentValue | null {
  if (typeof window === "undefined") return null;
  const v = window.localStorage.getItem(STORAGE_KEY);
  if (v === "all" || v === "essential") return v;
  return null;
}

/**
 * Audit (2026-05-03):
 *   - No third-party cookies are set by this site today.
 *   - Geist fonts are self-hosted by Next.js, so no Google cookie is set.
 *   - hCaptcha (when configured) only loads on form submit pages and sets
 *     its own cookies — disclose that here.
 *   - The only first-party storage we set is localStorage (token,
 *     visitor_id, this consent flag) — not technically cookies but worth
 *     disclosing for clarity.
 */
export function CookieBanner() {
  const [open, setOpen] = React.useState(false);

  React.useEffect(() => {
    if (typeof window === "undefined") return;
    if (!localStorage.getItem(STORAGE_KEY)) setOpen(true);
  }, []);

  function set(value: ConsentValue) {
    localStorage.setItem(STORAGE_KEY, value);
    // Notify same-tab listeners (the page-view tracker reads this).
    window.dispatchEvent(new CustomEvent("quata-consent-change", { detail: value }));
    setOpen(false);
  }

  if (!open) return null;

  return (
    <div className="fixed bottom-4 left-4 right-4 sm:left-auto sm:max-w-md z-50">
      <div className="rounded-2xl border border-border bg-card p-5 ring-elevated">
        <div className="flex items-start gap-3">
          <div className="inline-flex h-9 w-9 items-center justify-center rounded-xl bg-brand-soft text-primary shrink-0">
            <Cookie className="h-4 w-4" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-sm font-semibold">A note on storage</div>
            <p className="mt-1 text-xs text-muted-foreground">
              We store a few items in your browser to keep the site working
              (sign-in, language) and — only if you opt in — to count
              anonymous page views so we can improve the site. We use no
              third-party advertising cookies. See our{" "}
              <Link href="/privacy" className="text-primary font-medium">
                privacy policy
              </Link>
              .
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              <Button size="sm" onClick={() => set("all")}>
                Accept analytics
              </Button>
              <Button size="sm" variant="outline" onClick={() => set("essential")}>
                Essential only
              </Button>
            </div>
          </div>
          <button
            aria-label="Dismiss"
            onClick={() => set("essential")}
            className="text-muted-foreground hover:text-foreground"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
