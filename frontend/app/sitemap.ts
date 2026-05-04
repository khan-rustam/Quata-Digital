import type { MetadataRoute } from "next";
import { products } from "@/lib/ecosystem";
import { partnerPaths } from "@/lib/partner-types";

const SITE = process.env.NEXT_PUBLIC_SITE_URL ?? "https://quatadigital.com";

export default function sitemap(): MetadataRoute.Sitemap {
  const now = new Date();
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
    lastModified: now,
    changeFrequency: "weekly",
    priority: path === "" ? 1.0 : 0.7,
  }));

  for (const p of products) {
    entries.push({
      url: `${SITE}/ecosystem/${p.slug}`,
      lastModified: now,
      changeFrequency: "weekly",
      priority: 0.8,
    });
  }

  for (const p of partnerPaths) {
    entries.push({
      url: `${SITE}/partners/${p.slug}`,
      lastModified: now,
      changeFrequency: "monthly",
      priority: 0.6,
    });
  }

  return entries;
}
