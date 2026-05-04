import { notFound } from "next/navigation";
import Link from "next/link";
import { Section } from "@/components/site/section";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { JsonLd, articleJsonLd, breadcrumbJsonLd } from "@/components/site/jsonld";

type Post = {
  id: number;
  slug: string;
  title: string;
  excerpt: string;
  body: string;
  category: string;
  author: string;
  published_at: string;
};

async function getPost(slug: string): Promise<Post | null> {
  try {
    return await api<Post>(`/blog/${slug}`);
  } catch {
    return null;
  }
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
      <div className="prose prose-lg mt-8 max-w-none text-foreground/85 whitespace-pre-line">
        {post.body}
      </div>
    </Section>
  );
}
