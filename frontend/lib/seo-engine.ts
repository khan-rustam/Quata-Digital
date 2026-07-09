/**
 * seo-engine.ts — QUATA SEO Engine client (tenant: quatadigital)
 *
 * Zero external dependencies. All functions are fail-open: any network
 * error, timeout, or unexpected response returns null so the calling page
 * falls back to its local metadata. The engine must never take the site down.
 *
 * Environment variables (server-only — NEVER prefix with NEXT_PUBLIC_):
 *   SEO_ENGINE_URL   — base URL of the engine API   (default below)
 *   SEO_TENANT_SLUG  — override the tenant slug      (default: quatadigital)
 *   SEO_API_KEY      — read-only key from the engine admin UI (Tenants → API key)
 */

import type { Metadata } from "next";

// Production engine is mounted at the host ROOT — no `/api/v1` prefix — and the
// host is the single-level `apiseo.` subdomain (hosting can't serve a
// multi-level `api.seo.` subdomain — it never resolved). Endpoints:
//   GET /public/{tenant}/meta?path=       (X-API-Key)
//   GET /public/{tenant}/sitemap.json     (public)
// Override per deployment with SEO_ENGINE_URL.
const ENGINE_URL =
  process.env.SEO_ENGINE_URL ?? "https://apiseo.quatadigital.com";

const TENANT = process.env.SEO_TENANT_SLUG ?? "quatadigital";

const API_KEY = process.env.SEO_API_KEY ?? "";

/** Flat response shape served by GET /public/{tenant}/meta */
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
 * Internal engine fetch. Returns parsed JSON, or null on any error/non-2xx.
 *
 * Hardened against a Node/undici crash that surfaces as
 *   `TypeError: controller[kState].transformAlgorithm is not a function`
 * emitted *asynchronously* from undici's gzip/br decompression stream when an
 * aborted (timed-out) or non-OK *compressed* response is torn down — so it
 * escapes the try/catch around `await`. Two belt-and-suspenders mitigations:
 *   1. `Accept-Encoding: identity` — the engine returns uncompressed bytes, so
 *      undici never builds a decompression stream to crash on.
 *   2. Drain the body on the non-OK path so an unconsumed stream can't throw on GC.
 * Fail-open: every error path returns null and the caller uses its fallback.
 */
async function engineFetch<T>(
  url: string,
  opts: { timeoutMs: number; revalidate: number; headers?: Record<string, string> }
): Promise<T | null> {
  try {
    const res = await fetch(url, {
      headers: { "Accept-Encoding": "identity", ...(opts.headers ?? {}) },
      signal: AbortSignal.timeout(opts.timeoutMs),
      next: { revalidate: opts.revalidate },
    });
    if (!res.ok) {
      try {
        await res.body?.cancel();
      } catch {
        /* ignore — best-effort drain */
      }
      return null;
    }
    return (await res.json()) as T;
  } catch {
    return null;
  }
}

/**
 * Fetch rendered SEO metadata for a single path from the engine.
 * Returns the parsed response or null on any error. 2s timeout so a slow
 * engine never blocks SSR. Cached by Next.js for 5 minutes.
 */
export async function fetchSeoMeta(
  path: string
): Promise<SeoMetaResponse | null> {
  const url = `${ENGINE_URL}/public/${TENANT}/meta?path=${encodeURIComponent(path)}`;
  return engineFetch<SeoMetaResponse>(url, {
    timeoutMs: 2000,
    revalidate: 300,
    headers: { "X-API-Key": API_KEY },
  });
}

/**
 * Fetch the full sitemap entry list from the engine.
 * Returns an array of entries or null on any error. Cached for 1 hour.
 */
export async function fetchSeoSitemap(): Promise<SeoSitemapEntry[] | null> {
  const url = `${ENGINE_URL}/public/${TENANT}/sitemap.json`;
  const data = await engineFetch<unknown>(url, { timeoutMs: 5000, revalidate: 3600 });
  if (!Array.isArray(data) || data.length === 0) return null;
  return data as SeoSitemapEntry[];
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
