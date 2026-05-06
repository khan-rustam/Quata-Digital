"use client";

import * as React from "react";

import { apiUrl } from "@/lib/api";
import { useConsent } from "@/components/site/cookie-banner";

const VISITOR_KEY = "quata_visitor_id";

function getVisitorId(): string {
  try {
    if (typeof window === "undefined") return "";
    let v = window.localStorage.getItem(VISITOR_KEY);
    if (!v) {
      v =
        typeof crypto !== "undefined" && "randomUUID" in crypto
          ? crypto.randomUUID()
          : `v_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 10)}`;
      window.localStorage.setItem(VISITOR_KEY, v);
    }
    return v;
  } catch {
    return "anonymous";
  }
}

/**
 * Sends a single `/track?is_404=true` ping when the public 404 page
 * mounts — but only when the visitor has accepted analytics in the
 * cookie banner (same gate the regular `<PageViewTracker />` uses).
 *
 * Powers the admin "broken inbound paths" leaderboard.
 */
export function NotFoundTracker() {
  const consent = useConsent();
  React.useEffect(() => {
    if (consent !== "all") return;
    if (typeof navigator !== "undefined" && navigator.doNotTrack === "1") return;
    const path = window.location.pathname + window.location.search;
    const referrer = document.referrer || null;
    fetch(`${apiUrl}/track`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        path,
        referrer,
        visitor_id: getVisitorId(),
        is_404: true,
      }),
      keepalive: true,
    }).catch(() => {
      // Best-effort — never bubble an error to the user.
    });
  }, [consent]);
  return null;
}
