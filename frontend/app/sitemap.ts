import type { MetadataRoute } from "next";
import { products } from "@/lib/ecosystem";
import { partnerPaths } from "@/lib/partner-types";
import { apiUrl } from "@/lib/api";
import { fetchSeoSitemap } from "@/lib/seo-engine";

const SITE = process.env.NEXT_PUBLIC_SITE_URL ?? "https://quatadigital.com";

export const revalidate = 3600;

type PublishedPage = {
  slug: string;
  updated_at: string;
};

async function fetchPublishedPages(): Promise<Map<string, Date>> {
  try {
    const res = await fetch(`${apiUrl}/cms/pages-index`, {
      next: { revalidate: 60 },
    });
    if (!res.ok) return new Map();
    const items = (await res.json()) as PublishedPage[];
    const m = new Map<string, Date>();
    for (const p of items) {
      m.set(`/${p.slug}`, new Date(p.updated_at));
    }
    return m;
  } catch {
    return new Map();
  }
}

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const engineEntries = await fetchSeoSitemap();
  if (engineEntries && engineEntries.length > 0) {
    return engineEntries.map((e) => ({
      url: e.url,
      lastModified: e.lastModified ? new Date(e.lastModified) : new Date(),
      changeFrequency: (e.changeFrequency as MetadataRoute.Sitemap[number]["changeFrequency"]) ?? "weekly",
      priority: e.priority ?? 0.5,
    }));
  }

  const now = new Date();
  const lastMod = await fetchPublishedPages();
  const lm = (path: string) => lastMod.get(path) ?? now;

  const staticRoutes = [
    "",
    "/ecosystem",
    "/partners",
    "/careers",
    "/blog",
    "/about",
    "/contact",
    "/security",
    "/privacy",
    "/terms",
    "/search",
  ];

  const entries: MetadataRoute.Sitemap = staticRoutes.map((path) => ({
    url: `${SITE}${path}`,
    lastModified: path === "" ? lm("/home") : lm(path),
    changeFrequency: "weekly",
    priority: path === "" ? 1.0 : 0.7,
  }));

  for (const p of products) {
    entries.push({
      url: `${SITE}/ecosystem/${p.slug}`,
      lastModified: lm(`/ecosystem/${p.slug}`),
      changeFrequency: "weekly",
      priority: 0.8,
    });
  }

  for (const p of partnerPaths) {
    entries.push({
      url: `${SITE}/partners/${p.slug}`,
      lastModified: lm(`/partners/${p.slug}`),
      changeFrequency: "monthly",
      priority: 0.6,
    });
  }

  return entries;
}
