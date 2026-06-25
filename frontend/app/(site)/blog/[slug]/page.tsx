import type { Metadata } from "next";
import { notFound } from "next/navigation";
import Link from "next/link";
import { Section } from "@/components/site/section";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { renderMarkdownToHtml } from "@/lib/markdown";
import { JsonLd, articleJsonLd, breadcrumbJsonLd } from "@/components/site/jsonld";
import { PostCover } from "@/components/site/illustrations/editorial";

type Post = {
  id: number;
  slug: string;
  title: string;
  excerpt: string;
  body: string;
  category: string;
  author: string;
  published_at: string;
  cover_image_url?: string | null;
};

async function getPost(slug: string): Promise<Post | null> {
  try {
    return await api<Post>(`/blog/${slug}`);
  } catch {
    return null;
  }
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const post = await getPost(slug);
  if (!post) return { title: "Article not found" };
  const description = (post.excerpt || post.body || "").slice(0, 200);
  return {
    title: post.title,
    description,
    alternates: { canonical: `/blog/${post.slug}` },
    openGraph: {
      title: post.title,
      description,
      type: "article",
      url: `/blog/${post.slug}`,
      publishedTime: post.published_at,
      authors: post.author ? [post.author] : undefined,
    },
    twitter: { card: "summary_large_image", title: post.title, description },
  };
}

export default async function BlogPostPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const post = await getPost(slug);
  if (!post) return notFound();

  return (
    <Section className="max-w-3xl mx-auto">
      <JsonLd data={articleJsonLd(post)} />
      <JsonLd
        data={breadcrumbJsonLd([
          { name: "Home", href: "/" },
          { name: "News", href: "/blog" },
          { name: post.title, href: `/blog/${post.slug}` },
        ])}
      />
      <div className="text-sm">
        <Link href="/blog" className="text-muted-foreground hover:text-foreground">
          News
        </Link>
        <span className="mx-2 text-muted-foreground/60">/</span>
        <span>{post.title}</span>
      </div>
      <Badge variant="brand" className="mt-6">{post.category}</Badge>
      <h1 className="mt-4 text-3xl md:text-5xl font-semibold tracking-tight">
        {post.title}
      </h1>
      <div className="mt-3 text-sm text-muted-foreground">
        {post.author} · {formatDate(post.published_at)}
      </div>

      {/* Cover — uploaded image wins; otherwise a topical, on-brand cover
          generated from the article category so every article has a relevant
          visual. */}
      <div className="mt-8 relative aspect-video overflow-hidden rounded-3xl border border-border ring-soft">
        {post.cover_image_url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={post.cover_image_url}
            alt={post.title}
            className="absolute inset-0 h-full w-full object-cover"
          />
        ) : (
          <div className="absolute inset-0">
            <PostCover category={post.category} />
          </div>
        )}
      </div>

      {/* CMS body is markdown — render through the shared sanitiser so
          headings, lists, and inline formatting actually render instead
          of leaking literal asterisks/hashes to the visitor. URLs are
          protocol-allowlisted to keep `javascript:` out. */}
      <div
        className="prose prose-lg mt-8 max-w-none text-foreground/85"
        dangerouslySetInnerHTML={{ __html: renderMarkdownToHtml(post.body || "") }}
      />
    </Section>
  );
}
