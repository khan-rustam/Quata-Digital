/**
 * seo-engine.ts — QUATA SEO Engine client (tenant: quatadigital)
 *
 * Zero external dependencies. All functions are fail-open: any network
 * error, timeout, or unexpected response returns null so the calling page
 * falls back to its local metadata. The engine must never take the site down.
 *
 * Environment variables (set in .env.local; see .env.example):
 *   SEO_ENGINE_URL   — base URL of the engine API   (server-only)
 *   SEO_TENANT_SLUG  — override the tenant slug      (server-only)
 *   SEO_API_KEY      — API key issued by the engine  (server-only)
 */

import type { Metadata } from "next";

const ENGINE_URL =
  process.env.SEO_ENGINE_URL ?? "https://api.seo.quatadigital.com";

const TENANT = process.env.SEO_TENANT_SLUG ?? "quatadigital";

const API_KEY = process.env.SEO_API_KEY ?? "";

/** Flat response shape served by GET /api/v1/public/{tenant}/meta */
export interface SeoMetaResponse {
  path: string;
  title?: string | null;
  meta_description?: string | null;
  canonical?: string | null;
  og_title?: string | null;
  og_description?: string | null;
  og_image?: string | null;
  twitter_title?: string | null;
  twitter_description?: string | null;
  twitter_image?: string | null;
  robots?: string | null;
  json_ld?: unknown[];
}

export interface SeoSitemapEntry {
  url: string;
  lastModified?: string | null;
  changeFrequency?: string | null;
  priority?: number | null;
}

/**
 * Fetch rendered SEO metadata for a single path from the engine.
 * Returns the parsed response or null on any error. 2s timeout so a slow
 * engine never blocks SSR. Cached by Next.js for 5 minutes.
 */
export async function fetchSeoMeta(
  path: string
): Promise<SeoMetaResponse | null> {
  try {
    const url = `${ENGINE_URL}/api/v1/public/${TENANT}/meta?path=${encodeURIComponent(path)}`;
    const res = await fetch(url, {
      headers: { "X-API-Key": API_KEY },
      signal: AbortSignal.timeout(2000),
      next: { revalidate: 300 },
    });
    if (!res.ok) return null;
    return (await res.json()) as SeoMetaResponse;
  } catch {
    return null;
  }
}

/**
 * Fetch the full sitemap entry list from the engine.
 * Returns an array of entries or null on any error. Cached for 1 hour.
 */
export async function fetchSeoSitemap(): Promise<SeoSitemapEntry[] | null> {
  try {
    const url = `${ENGINE_URL}/api/v1/public/${TENANT}/sitemap.json`;
    const res = await fetch(url, {
      signal: AbortSignal.timeout(5000),
      next: { revalidate: 3600 },
    });
    if (!res.ok) return null;
    const data = await res.json();
    if (!Array.isArray(data) || data.length === 0) return null;
    return data as SeoSitemapEntry[];
  } catch {
    return null;
  }
}

/**
 * Fetch the JSON-LD blocks for a path (for embedding in a <script
 * type="application/ld+json"> tag). Returns null when unavailable.
 */
export async function getJsonLd(path: string): Promise<unknown[] | null> {
  const meta = await fetchSeoMeta(path);
  if (!meta?.json_ld || meta.json_ld.length === 0) return null;
  return meta.json_ld;
}

/**
 * Build a Next.js Metadata object by merging engine-supplied meta over the
 * caller-supplied fallback. Returns the fallback unchanged when the engine
 * is unavailable.
 *
 * Usage in a page/layout:
 *   export async function generateMetadata({ params }): Promise<Metadata> {
 *     return buildMetadata(`/some/${params.slug}`, { title: "Fallback" });
 *   }
 */
export async function buildMetadata(
  path: string,
  fallback: Metadata = {}
): Promise<Metadata> {
  const meta = await fetchSeoMeta(path);
  if (!meta) return fallback;

  const result: Metadata = { ...fallback };

  if (meta.title) result.title = meta.title;
  if (meta.meta_description) result.description = meta.meta_description;

  if (meta.canonical) {
    result.alternates = { ...result.alternates, canonical: meta.canonical };
  }

  if (meta.og_title || meta.og_description || meta.og_image) {
    result.openGraph = {
      ...(result.openGraph ?? {}),
      ...(meta.og_title ? { title: meta.og_title } : {}),
      ...(meta.og_description ? { description: meta.og_description } : {}),
      ...(meta.og_image ? { images: [meta.og_image] } : {}),
    };
  }

  if (meta.twitter_title || meta.twitter_description || meta.twitter_image) {
    result.twitter = {
      ...(result.twitter ?? {}),
      card: "summary_large_image",
      ...(meta.twitter_title ? { title: meta.twitter_title } : {}),
      ...(meta.twitter_description
        ? { description: meta.twitter_description }
        : {}),
      ...(meta.twitter_image ? { images: [meta.twitter_image] } : {}),
    };
  }

  if (meta.robots) result.robots = meta.robots;

  return result;
}
