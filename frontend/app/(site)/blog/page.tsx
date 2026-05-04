import type { Metadata } from "next";
import Link from "next/link";
import {
  ArrowRight,
  BookOpen,
  Calendar,
  Hash,
  TrendingUp,
  Sparkles,
  Layers,
  Building2,
  Lightbulb,
} from "lucide-react";
import { Section, SectionHeader } from "@/components/site/section";
import { Badge } from "@/components/ui/badge";
import { FeaturedPost } from "@/components/site/sections/featured-post";
import { NewsletterSignup } from "@/components/site/sections/newsletter";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/utils";

export const metadata: Metadata = {
  title: "News & insights",
  description: "Updates, deep-dives and announcements from the QUATA Digital team.",
};

type Post = {
  id: number;
  slug: string;
  title: string;
  excerpt: string;
  category: string;
  cover_image_url: string | null;
  published_at: string;
};

async function getPosts(): Promise<Post[]> {
  try {
    return await api<Post[]>("/blog?published=true");
  } catch {
    return [];
  }
}

const fallback: Post[] = [
  {
    id: 1,
    slug: "introducing-quatapay-2",
    title: "Introducing QUATAPAY 2.0",
    excerpt:
      "A faster ledger, cheaper cross-border settlement, and a new acceptance API for merchants.",
    category: "Product",
    cover_image_url: null,
    published_at: new Date().toISOString(),
  },
  {
    id: 2,
    slug: "abaqwa-east-africa-launch",
    title: "ABAQWA expands to East Africa",
    excerpt:
      "Riders, drivers and customers across Kenya, Uganda and Tanzania can now move on the QUATA wallet.",
    category: "Company",
    cover_image_url: null,
    published_at: new Date(Date.now() - 86400000 * 5).toISOString(),
  },
  {
    id: 3,
    slug: "the-case-for-one-rail",
    title: "The case for one rail",
    excerpt:
      "Why Africa benefits more from connected platforms than from another standalone app.",
    category: "Insight",
    cover_image_url: null,
    published_at: new Date(Date.now() - 86400000 * 14).toISOString(),
  },
];

const categoryIcons: Record<string, typeof BookOpen> = {
  Product: Layers,
  Company: Building2,
  Insight: Lightbulb,
  Engineering: Sparkles,
};

export default async function BlogPage() {
  const fetched = await getPosts();
  const posts = fetched.length > 0 ? fetched : fallback;

  const featured = posts[0];
  const rest = posts.slice(1);

  // Category counts
  const counts = posts.reduce<Record<string, number>>((acc, p) => {
    acc[p.category] = (acc[p.category] ?? 0) + 1;
    return acc;
  }, {});
  const categories = Object.entries(counts).map(([name, count]) => ({ name, count }));

  return (
    <>
      {/* 1. Hero header */}
      <section className="relative overflow-hidden">
        <div className="absolute inset-0 -z-10 bg-linear-to-b from-brand-soft/40 via-surface to-surface" />
        <div className="absolute inset-0 -z-10 dot-grid mask-fade-b opacity-50" />
        <div className="container-page py-14 sm:py-20 md:py-24">
          <div className="inline-flex items-center gap-2 rounded-full border border-border bg-surface/80 px-3 py-1 text-xs text-muted-foreground backdrop-blur">
            <BookOpen className="h-3.5 w-3.5 text-primary" />
            News & insights
          </div>
          <h1 className="mt-6 text-3xl sm:text-4xl md:text-6xl font-semibold tracking-tight max-w-3xl text-balance">
            What we&apos;re shipping,{" "}
            <span className="text-gradient-brand">learning</span> and announcing.
          </h1>
          <p className="mt-5 max-w-2xl text-lg text-muted-foreground">
            Product updates, market dispatches and the occasional opinion from
            inside the QUATA team.
          </p>
        </div>
      </section>

      {/* 2. Featured post */}
      {featured && (
        <Section className="pt-0">
          <FeaturedPost post={featured} />
        </Section>
      )}

      {/* 3. Category filter pills */}
      <Section className="py-8">
        <div className="flex flex-wrap items-center gap-2">
          <span className="inline-flex items-center gap-1.5 rounded-full bg-foreground text-background px-3 py-1.5 text-xs">
            <Hash className="h-3 w-3" />
            All
            <span className="text-background/70">· {posts.length}</span>
          </span>
          {categories.map((c) => {
            const Icon = categoryIcons[c.name] ?? BookOpen;
            return (
              <span
                key={c.name}
                className="inline-flex items-center gap-1.5 rounded-full border border-border bg-card px-3 py-1.5 text-xs"
              >
                <Icon className="h-3 w-3 text-primary" />
                {c.name}
                <span className="text-muted-foreground">· {c.count}</span>
              </span>
            );
          })}
        </div>
      </Section>

      {/* 4. Latest posts grid */}
      <Section className="pt-0">
        <SectionHeader eyebrow="Latest" title="Recent stories." />
        <div className="mt-10 grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {rest.map((p) => {
            const Icon = categoryIcons[p.category] ?? BookOpen;
            return (
              <Link
                key={p.id}
                href={`/blog/${p.slug}`}
                className="group flex flex-col rounded-2xl border border-border bg-card overflow-hidden ring-soft transition hover:-translate-y-0.5"
              >
                <div className="h-40 w-full gradient-brand relative">
                  <div className="absolute inset-0 dot-grid opacity-30" />
                  <div className="absolute left-4 top-4">
                    <span className="inline-flex items-center gap-1.5 rounded-full bg-white/95 px-2.5 py-1 text-[11px] font-medium text-ink">
                      <Icon className="h-3 w-3 text-primary" />
                      {p.category}
                    </span>
                  </div>
                </div>
                <div className="flex flex-1 flex-col gap-2 p-5">
                  <div className="text-xs text-muted-foreground inline-flex items-center gap-1.5">
                    <Calendar className="h-3 w-3" />
                    {formatDate(p.published_at)}
                  </div>
                  <h3 className="text-base font-semibold tracking-tight">{p.title}</h3>
                  <p className="text-sm text-muted-foreground line-clamp-3">{p.excerpt}</p>
                  <div className="mt-3 inline-flex items-center gap-1.5 text-sm font-medium text-primary">
                    Read article
                    <ArrowRight className="h-3.5 w-3.5 transition group-hover:translate-x-0.5" />
                  </div>
                </div>
              </Link>
            );
          })}
        </div>
      </Section>

      {/* 5. By topic */}
      <Section className="bg-surface-soft rounded-3xl">
        <SectionHeader
          eyebrow="By topic"
          title="What we write about most."
        />
        <div className="mt-10 grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {[
            { icon: Layers, name: "Product", desc: "Features, releases, technical decisions.", tone: "bg-brand-soft text-primary" },
            { icon: Building2, name: "Company", desc: "Hires, milestones, market launches.", tone: "bg-amber-100 text-amber-900" },
            { icon: Lightbulb, name: "Insight", desc: "How we think about Africa, payments, and rails.", tone: "bg-sky-100 text-sky-900" },
            { icon: TrendingUp, name: "Operator notes", desc: "Real lessons from running daily ops.", tone: "bg-rose-100 text-rose-900" },
          ].map((t) => (
            <div
              key={t.name}
              className="rounded-2xl border border-border bg-card p-5 ring-soft"
            >
              <div className={`inline-flex h-10 w-10 items-center justify-center rounded-xl ${t.tone}`}>
                <t.icon className="h-5 w-5" />
              </div>
              <div className="mt-4 text-base font-semibold tracking-tight">{t.name}</div>
              <p className="mt-1.5 text-sm text-muted-foreground">{t.desc}</p>
            </div>
          ))}
        </div>
      </Section>

      {/* 6. Most read */}
      <Section>
        <SectionHeader
          eyebrow="Most read"
          title="The stories people return to."
        />
        <div className="mt-8 grid gap-3">
          {posts.slice(0, 5).map((p, i) => (
            <Link
              key={p.id}
              href={`/blog/${p.slug}`}
              className="group flex items-center justify-between gap-4 rounded-2xl border border-border bg-card p-5 ring-soft transition hover:-translate-y-0.5"
            >
              <div className="flex items-center gap-4 min-w-0">
                <span className="text-2xl font-semibold text-muted-foreground/40 tabular-nums shrink-0">
                  {String(i + 1).padStart(2, "0")}
                </span>
                <div className="min-w-0">
                  <div className="text-sm font-semibold truncate">{p.title}</div>
                  <div className="mt-1 inline-flex items-center gap-2 text-xs text-muted-foreground">
                    <Badge variant="brand">{p.category}</Badge>
                    <span>{formatDate(p.published_at)}</span>
                  </div>
                </div>
              </div>
              <ArrowRight className="h-4 w-4 text-muted-foreground transition group-hover:text-foreground group-hover:translate-x-0.5 shrink-0" />
            </Link>
          ))}
        </div>
      </Section>

      {/* 7. Newsletter */}
      <Section>
        <NewsletterSignup
          title="The QUATA Dispatch."
          subtitle="Once a month, the most important things we shipped, learned and noticed across the continent."
        />
      </Section>
    </>
  );
}
