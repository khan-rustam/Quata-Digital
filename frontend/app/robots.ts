import type { MetadataRoute } from "next";

const SITE = process.env.NEXT_PUBLIC_SITE_URL ?? "https://quatadigital.com";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      { userAgent: "*", allow: "/", disallow: ["/admin/", "/api/"] },
    ],
    sitemap: `${SITE}/sitemap.xml`,
    // `host:` is a non-standard directive (Yandex-only) and was being
    // ignored by Google + Bing. Dropped to keep the file lean.
  };
}
