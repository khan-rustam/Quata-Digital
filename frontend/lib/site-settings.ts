/**
 * Public site settings — fetched server-side from /api/v1/site-settings.
 *
 * The backend returns a flat dict of dotted keys (e.g. "contact.phone").
 * This module:
 *  - calls the API with a 10s revalidate window (so admin edits propagate
 *    quickly without thundering the backend);
 *  - groups the flat dict into a typed shape;
 *  - falls back to safe empty values when the API is unreachable, so the
 *    public site never crashes on a backend hiccup.
 *
 * Use `getSiteSettings()` from any Server Component. Do not use this from
 * a Client Component — for that, fetch through `useApi("/site-settings")`.
 */

import { apiUrl } from "./api";

export type ContactSettings = {
  phone: string | null;
  email: string | null;
  address: string | null;
  support_hours: string | null;
};

export type SocialSettings = {
  linkedin_url: string | null;
  twitter_url: string | null;
  instagram_url: string | null;
  youtube_url: string | null;
  facebook_url: string | null;
};

export type ToggleSettings = {
  maintenance_mode: boolean;
  maintenance_message: string | null;
};

export type SiteSettings = {
  contact: ContactSettings;
  social: SocialSettings;
  toggles: ToggleSettings;
};

const EMPTY: SiteSettings = {
  contact: { phone: null, email: null, address: null, support_hours: null },
  social: {
    linkedin_url: null,
    twitter_url: null,
    instagram_url: null,
    youtube_url: null,
    facebook_url: null,
  },
  toggles: { maintenance_mode: false, maintenance_message: null },
};

function pick(map: Record<string, string | null>, key: string): string | null {
  const v = map[key];
  if (typeof v !== "string") return null;
  const trimmed = v.trim();
  return trimmed.length > 0 ? trimmed : null;
}

/** Fetch the public site settings. Server-only — uses Next's fetch cache. */
export async function getSiteSettings(): Promise<SiteSettings> {
  try {
    const res = await fetch(`${apiUrl}/site-settings`, {
      // Revalidate once every 10 seconds. Admin edits become visible across
      // the public site within that window without a redeploy.
      next: { revalidate: 10, tags: ["site-settings"] },
    });
    if (!res.ok) return EMPTY;
    const map = (await res.json()) as Record<string, string | null>;
    return {
      contact: {
        phone: pick(map, "contact.phone"),
        email: pick(map, "contact.email"),
        address: pick(map, "contact.address"),
        support_hours: pick(map, "contact.support_hours"),
      },
      social: {
        linkedin_url: pick(map, "social.linkedin_url"),
        twitter_url: pick(map, "social.twitter_url"),
        instagram_url: pick(map, "social.instagram_url"),
        youtube_url: pick(map, "social.youtube_url"),
        facebook_url: pick(map, "social.facebook_url"),
      },
      toggles: {
        // Treat anything other than "true"/"1" as off.
        maintenance_mode:
          (pick(map, "toggles.maintenance_mode") ?? "").toLowerCase() === "true" ||
          pick(map, "toggles.maintenance_mode") === "1",
        maintenance_message: pick(map, "toggles.maintenance_message"),
      },
    };
  } catch {
    return EMPTY;
  }
}

/** Read a single contact value, with optional env fallback for legacy callers. */
export async function getContactValue(
  key: keyof ContactSettings,
  envFallback?: string,
): Promise<string | null> {
  const settings = await getSiteSettings();
  return settings.contact[key] ?? (envFallback?.trim() || null);
}
