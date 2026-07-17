import { api } from "@/lib/api";
import { OG_CONTENT_TYPE, OG_SIZE, renderOg } from "@/lib/og-template";

export const alt = "QUATA Digital — news & insights";
export const size = OG_SIZE;
export const contentType = OG_CONTENT_TYPE;

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

  return renderOg({
    background: "blog",
    eyebrow: category,
    title,
    pathname: "/blog",
    footerLeft: `by ${author}`,
    footerRight: "quatadigital.com/blog",
  });
}
