/**
 * Server-side helper for OG image generators. Fetches a CMS page's hero
 * data so OG cards reflect what the boss publishes — no need to commit
 * marketing copy in two places.
 *
 * Returns null on any failure (network, page unpublished, no hero
 * section). Callers should fall back to their static title.
 */

import { apiUrl } from "./api";

export type HeroFallback = {
  title: string;
  subtitle?: string | null;
};

export type ResolvedOgHero = {
  title: string;
  subtitle: string | null;
};

export async function getHeroForOg(
  slug: string,
  fallback: HeroFallback,
): Promise<ResolvedOgHero> {
  try {
    const res = await fetch(`${apiUrl}/cms/pages/${encodeURI(slug)}`, {
      next: { revalidate: 60 },
    });
    if (res.ok) {
      const data = (await res.json()) as {
        sections?: Array<Record<string, unknown>>;
      };
      const hero = (data.sections ?? []).find((s) => s.type === "hero") as
        | { title?: string; subtitle?: string | null }
        | undefined;
      if (hero?.title) {
        return {
          title: hero.title,
          subtitle: hero.subtitle ?? null,
        };
      }
    }
  } catch {
    // fall through
  }
  return {
    title: fallback.title,
    subtitle: fallback.subtitle ?? null,
  };
}
