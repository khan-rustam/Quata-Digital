"use client";

import * as React from "react";
import Link from "next/link";
import { useSearchParams, useRouter } from "next/navigation";
import {
  Search as SearchIcon,
  Layers,
  BookOpen,
  Briefcase,
  ArrowRight,
  Loader2,
  X,
} from "lucide-react";
import { Section, SectionHeader } from "@/components/site/section";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";

type Results = {
  query: string;
  totals: { products: number; posts: number; jobs: number };
  results: {
    products: { slug: string; name: string; tagline: string; category: string }[];
    posts: { slug: string; title: string; excerpt: string; category: string }[];
    jobs: { id: number; title: string; department: string; location: string; summary: string }[];
  };
};

export default function SearchPage() {
  const params = useSearchParams();
  const router = useRouter();
  const initial = params.get("q") ?? "";
  const [query, setQuery] = React.useState(initial);
  const [data, setData] = React.useState<Results | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [filter, setFilter] = React.useState<"all" | "products" | "posts" | "jobs">("all");

  React.useEffect(() => {
    const q = query.trim();
    if (!q) {
      setData(null);
      return;
    }
    let cancel = false;
    setLoading(true);
    const handle = window.setTimeout(async () => {
      try {
        const r = await api<Results>(`/search?q=${encodeURIComponent(q)}`);
        if (!cancel) setData(r);
      } catch {
        if (!cancel) setData(null);
      } finally {
        if (!cancel) setLoading(false);
      }
    }, 250);
    return () => {
      cancel = true;
      window.clearTimeout(handle);
    };
  }, [query]);

  // Sync URL ?q=
  React.useEffect(() => {
    const next = new URLSearchParams(Array.from(params.entries()));
    if (query) next.set("q", query);
    else next.delete("q");
    const s = next.toString();
    router.replace(`/search${s ? `?${s}` : ""}`, { scroll: false });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query]);

  const totals = data?.totals ?? { products: 0, posts: 0, jobs: 0 };
  const total = totals.products + totals.posts + totals.jobs;

  return (
    <>
      <section className="relative overflow-hidden">
        <div className="absolute inset-0 -z-10 bg-linear-to-b from-brand-soft/40 via-surface to-surface" />
        <div className="absolute inset-0 -z-10 dot-grid mask-fade-b opacity-50" />
        <div className="container-page py-16 md:py-20">
          <div className="inline-flex items-center gap-2 rounded-full border border-border bg-surface/80 px-3 py-1 text-xs text-muted-foreground backdrop-blur">
            <SearchIcon className="h-3.5 w-3.5 text-primary" />
            Search QUATA
          </div>
          <h1 className="mt-6 text-4xl md:text-5xl font-semibold tracking-tight text-balance">
            Find anything across the ecosystem.
          </h1>
          <div className="mt-6 relative max-w-2xl">
            <SearchIcon className="absolute left-4 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              autoFocus
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search products, jobs, blog posts…"
              className="pl-10 pr-12 h-12 text-base"
            />
            {query && (
              <button
                onClick={() => setQuery("")}
                aria-label="Clear search"
                className="absolute right-4 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
              >
                <X className="h-4 w-4" />
              </button>
            )}
          </div>
          {query && (
            <div className="mt-4 flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
              {loading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <span>
                  {total} result{total === 1 ? "" : "s"} for{" "}
                  <span className="font-semibold text-foreground">&ldquo;{query}&rdquo;</span>
                </span>
              )}
            </div>
          )}
        </div>
      </section>

      <Section className="pt-4">
        {/* Filters */}
        {query && total > 0 && (
          <div className="flex flex-wrap items-center gap-2 mb-8">
            {(
              [
                { key: "all", label: `All (${total})` },
                { key: "products", label: `Products (${totals.products})`, icon: Layers },
                { key: "posts", label: `News (${totals.posts})`, icon: BookOpen },
                { key: "jobs", label: `Jobs (${totals.jobs})`, icon: Briefcase },
              ] as const
            ).map((f) => (
              <button
                key={f.key}
                onClick={() => setFilter(f.key as typeof filter)}
                className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs transition ${
                  filter === f.key
                    ? "bg-foreground text-background"
                    : "border border-border bg-card text-muted-foreground hover:text-foreground"
                }`}
              >
                {"icon" in f && f.icon && <f.icon className="h-3 w-3" />}
                {f.label}
              </button>
            ))}
          </div>
        )}

        {/* Empty initial state */}
        {!query && (
          <div className="rounded-2xl border border-border bg-surface-soft p-10 text-center max-w-2xl">
            <SearchIcon className="mx-auto h-6 w-6 text-primary" />
            <h2 className="mt-4 text-lg font-semibold">Start typing.</h2>
            <p className="mt-2 text-sm text-muted-foreground">
              Try searching for &ldquo;quatapay&rdquo;, &ldquo;abaqwa&rdquo;,
              &ldquo;partnerships&rdquo; or any product across the ecosystem.
            </p>
            <div className="mt-5 flex flex-wrap justify-center gap-2">
              {["quatapay", "abaqwa", "merchant", "partnerships"].map((s) => (
                <button
                  key={s}
                  onClick={() => setQuery(s)}
                  className="rounded-full border border-border bg-surface px-3 py-1 text-xs hover:bg-secondary"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* No matches */}
        {query && !loading && total === 0 && (
          <div className="rounded-2xl border border-dashed border-border bg-surface-soft p-10 text-center">
            <h2 className="text-base font-semibold">No matches</h2>
            <p className="mt-2 text-sm text-muted-foreground">
              We couldn&apos;t find anything matching &ldquo;{query}&rdquo;. Try a different
              term or{" "}
              <Link href="/contact" className="text-primary font-medium">
                contact us
              </Link>{" "}
              if you can&apos;t find what you&apos;re looking for.
            </p>
          </div>
        )}

        {/* Results */}
        {data && total > 0 && (
          <div className="grid gap-10">
            {(filter === "all" || filter === "products") && data.results.products.length > 0 && (
              <Group title="Products" icon={Layers}>
                {data.results.products.map((p) => (
                  <ResultCard
                    key={p.slug}
                    href={`/ecosystem/${p.slug}`}
                    title={p.name}
                    body={p.tagline}
                    badge={p.category}
                  />
                ))}
              </Group>
            )}
            {(filter === "all" || filter === "posts") && data.results.posts.length > 0 && (
              <Group title="News & insights" icon={BookOpen}>
                {data.results.posts.map((p) => (
                  <ResultCard
                    key={p.slug}
                    href={`/blog/${p.slug}`}
                    title={p.title}
                    body={p.excerpt}
                    badge={p.category}
                  />
                ))}
              </Group>
            )}
            {(filter === "all" || filter === "jobs") && data.results.jobs.length > 0 && (
              <Group title="Open roles" icon={Briefcase}>
                {data.results.jobs.map((j) => (
                  <ResultCard
                    key={j.id}
                    href={`/careers/${j.id}`}
                    title={j.title}
                    body={j.summary}
                    badge={`${j.department} · ${j.location}`}
                  />
                ))}
              </Group>
            )}
          </div>
        )}
      </Section>
    </>
  );
}

function Group({
  title,
  icon: Icon,
  children,
}: {
  title: string;
  icon: typeof SearchIcon;
  children: React.ReactNode;
}) {
  return (
    <div>
      <div className="flex items-center gap-2 mb-4">
        <Icon className="h-4 w-4 text-primary" />
        <div className="text-sm font-semibold">{title}</div>
      </div>
      <div className="grid gap-3">{children}</div>
    </div>
  );
}

function ResultCard({
  href,
  title,
  body,
  badge,
}: {
  href: string;
  title: string;
  body: string;
  badge?: string;
}) {
  return (
    <Link
      href={href}
      className="group flex items-start justify-between gap-4 rounded-2xl border border-border bg-card p-5 ring-soft transition hover:-translate-y-0.5"
    >
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          {badge && <Badge variant="brand">{badge}</Badge>}
        </div>
        <div className="mt-2 text-base font-semibold tracking-tight">{title}</div>
        <p className="mt-1 text-sm text-muted-foreground line-clamp-2">{body}</p>
      </div>
      <ArrowRight className="h-4 w-4 text-muted-foreground transition group-hover:text-foreground group-hover:translate-x-0.5 shrink-0 mt-1" />
    </Link>
  );
}
