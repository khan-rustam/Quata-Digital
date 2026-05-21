import { ImageResponse } from "next/og";
import { api } from "@/lib/api";

export const alt = "QUATA Digital — news & insights";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

/**
 * Per-post Open Graph card.
 *
 * Without this, every blog post share rendered the homepage OG image,
 * which gives social previews no per-article context. We now render
 * the post's category + title + author into a branded card.
 *
 * Errors silently fall back to a brand-only card so a failing API
 * never breaks the share preview.
 */
export default async function BlogOgImage({
  params,
}: {
  params: { slug: string };
}) {
  let title = "QUATA Digital — News & Insights";
  let category = "QUATA Digital";
  let author = "QUATA Team";
  try {
    const post = await api<{
      title: string;
      category: string;
      author: string;
    }>(`/blog/${params.slug}`);
    title = post.title || title;
    category = post.category || category;
    author = post.author || author;
  } catch {
    /* keep defaults */
  }

  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          background:
            "linear-gradient(135deg, #0E5B4A 0%, #1c8a6e 55%, #34d3a7 100%)",
          color: "white",
          padding: "80px",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          fontFamily: "system-ui, sans-serif",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <div
            style={{
              width: 56,
              height: 56,
              borderRadius: 14,
              background: "rgba(255,255,255,0.15)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 28,
              fontWeight: 700,
            }}
          >
            Q
          </div>
          <div style={{ fontSize: 26, fontWeight: 600 }}>QUATA Digital</div>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div
            style={{
              fontSize: 22,
              fontWeight: 600,
              letterSpacing: 2,
              textTransform: "uppercase",
              opacity: 0.85,
            }}
          >
            {category}
          </div>
          <div
            style={{
              fontSize: 64,
              fontWeight: 600,
              letterSpacing: -1.5,
              lineHeight: 1.1,
              maxWidth: 1000,
            }}
          >
            {title}
          </div>
        </div>

        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            color: "rgba(255,255,255,0.75)",
            fontSize: 22,
          }}
        >
          <div>by {author}</div>
          <div>quatadigital.com/blog</div>
        </div>
      </div>
    ),
    { ...size }
  );
}
