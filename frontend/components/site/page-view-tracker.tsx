"use client";

import * as React from "react";
import { usePathname, useSearchParams } from "next/navigation";
import { apiUrl } from "@/lib/api";
import { getConsent } from "@/components/site/cookie-banner";

const VISITOR_KEY = "quata_visitor_id";

function getVisitorId(): string {
  try {
    let id = window.localStorage.getItem(VISITOR_KEY);
    if (!id) {
      id =
        typeof crypto !== "undefined" && "randomUUID" in crypto
          ? crypto.randomUUID()
          : `v_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 10)}`;
      window.localStorage.setItem(VISITOR_KEY, id);
    }
    return id;
  } catch {
    return "anonymous";
  }
}

export function PageViewTracker() {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  // Re-render when consent changes so a user accepting analytics mid-session
  // starts being tracked from the next navigation.
  const [consent, setConsent] = React.useState<string | null>(null);
  React.useEffect(() => {
    setConsent(getConsent());
    function onChange(e: Event) {
      setConsent((e as CustomEvent<string>).detail);
    }
    window.addEventListener("quata-consent-change", onChange);
    return () => window.removeEventListener("quata-consent-change", onChange);
  }, []);

  React.useEffect(() => {
    if (!pathname) return;
    if (pathname.startsWith("/admin")) return;
    // Honour Do Not Track
    if (typeof navigator !== "undefined" && navigator.doNotTrack === "1") return;
    // Honour the user's consent choice. Without explicit "accept analytics"
    // we don't fire the tracker.
    if (consent !== "all") return;

    const visitor_id = getVisitorId();
    const qs = searchParams?.toString();
    const path = qs ? `${pathname}?${qs}` : pathname;
    const referrer = typeof document !== "undefined" ? document.referrer : "";

    const body = JSON.stringify({ path, referrer, visitor_id });

    try {
      if (
        typeof navigator !== "undefined" &&
        typeof navigator.sendBeacon === "function"
      ) {
        navigator.sendBeacon(
          `${apiUrl}/track`,
          new Blob([body], { type: "application/json" })
        );
        return;
      }
    } catch {
      // fall through to fetch
    }

    fetch(`${apiUrl}/track`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body,
      keepalive: true,
    }).catch(() => {
      // best-effort — never break the page on a tracking failure
    });
  }, [pathname, searchParams, consent]);

  return null;
}
