"use client";

import * as React from "react";
import Link from "next/link";
import {
  ArrowRight,
  CheckCircle2,
  CircleDot,
  FileText,
  Layers,
  Search,
} from "lucide-react";

import { PageShell } from "@/components/admin/page-shell";
import { Input } from "@/components/ui/input";
import { useApi } from "@/lib/use-api";
import { formatDate } from "@/lib/utils";

type PageSummary = {
  slug: string;
  title: string;
  page_type: string;
  description: string | null;
  is_published: boolean;
  section_count: number;
  updated_at: string;
  updated_by: string | null;
};

type ListResponse = {
  items: PageSummary[];
  page_types: string[];
};

const TYPE_META: Record<string, { label: string; color: string }> = {
  general: { label: "General", color: "bg-secondary text-foreground" },
  product: { label: "Product page", color: "bg-brand-soft text-primary" },
  partner_type: { label: "Partner type", color: "bg-amber-100 text-amber-900" },
};

export default function MarketingPagesIndex() {
  return (
    <PageShell
      title="Marketing pages"
      description="Every public page on quatadigital.com. Click a page to edit its sections — hero, feature grids, FAQ, testimonials and more. Pages stay as drafts until you publish."
      requirePermission="content:manage"
    >
      <PagesIndex />
    </PageShell>
  );
}

function PagesIndex() {
  const { data, loading, error } = useApi<ListResponse>("/admin/cms/pages");
  const [query, setQuery] = React.useState("");
  const [typeFilter, setTypeFilter] = React.useState<string | null>(null);

  const filtered = React.useMemo(() => {
    if (!data) return [];
    const q = query.trim().toLowerCase();
    return data.items.filter((p) => {
      if (typeFilter && p.page_type !== typeFilter) return false;
      if (!q) return true;
      return (
        p.slug.toLowerCase().includes(q) ||
        p.title.toLowerCase().includes(q) ||
        (p.description ?? "").toLowerCase().includes(q)
      );
    });
  }, [data, query, typeFilter]);

  if (loading) {
    return <div className="text-sm text-muted-foreground">Loading…</div>;
  }
  if (error || !data) {
    return (
      <div className="rounded-2xl border border-rose-200 bg-rose-50 p-6 text-rose-900">
        Couldn&apos;t load pages. Try refreshing.
      </div>
    );
  }

  const grouped = groupByType(filtered);

  return (
    <div className="grid gap-6">
      <div className="grid gap-3 sm:grid-cols-[1fr_auto] items-center">
        <div className="relative">
          <Search className="absolute inset-y-0 left-3 h-4 w-4 my-auto text-muted-foreground" />
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search pages by title or slug…"
            className="pl-9"
          />
        </div>
        <div className="flex flex-wrap gap-2">
          <FilterPill
            active={typeFilter === null}
            onClick={() => setTypeFilter(null)}
            count={data.items.length}
          >
            All
          </FilterPill>
          {data.page_types.map((t) => (
            <FilterPill
              key={t}
              active={typeFilter === t}
              onClick={() => setTypeFilter(t)}
              count={data.items.filter((p) => p.page_type === t).length}
            >
              {TYPE_META[t]?.label ?? t}
            </FilterPill>
          ))}
        </div>
      </div>

      {filtered.length === 0 ? (
        <div className="rounded-2xl border border-border bg-card p-10 text-center text-muted-foreground">
          <FileText className="h-6 w-6 mx-auto mb-3" />
          No pages match your filter.
        </div>
      ) : (
        Object.entries(grouped).map(([type, pages]) => (
          <section key={type} className="grid gap-3">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">
                {TYPE_META[type]?.label ?? type} ({pages.length})
              </h3>
            </div>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {pages.map((p) => (
                <PageCard key={p.slug} page={p} />
              ))}
            </div>
          </section>
        ))
      )}
    </div>
  );
}

function FilterPill({
  active,
  onClick,
  count,
  children,
}: {
  active: boolean;
  onClick: () => void;
  count: number;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-medium transition ${
        active
          ? "border-primary bg-brand-soft text-primary"
          : "border-border bg-surface text-muted-foreground hover:text-foreground"
      }`}
    >
      {children}
      <span className="inline-flex h-4 min-w-4 items-center justify-center rounded-full bg-white/40 px-1 text-[10px]">
        {count}
      </span>
    </button>
  );
}

function PageCard({ page }: { page: PageSummary }) {
  const meta = TYPE_META[page.page_type];
  const editHref = `/admin/cms/pages/${encodeURIComponent(page.slug)}`;
  return (
    <Link
      href={editHref}
      className="group rounded-2xl border border-border bg-card p-5 ring-soft hover:ring-elevated transition flex flex-col gap-3"
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="text-xs text-muted-foreground font-mono truncate">
            /{page.slug}
          </div>
          <h4 className="mt-1 text-base font-semibold truncate">{page.title}</h4>
        </div>
        {meta && (
          <span className={`shrink-0 inline-flex rounded-full px-2 py-0.5 text-[10px] font-medium ${meta.color}`}>
            {meta.label}
          </span>
        )}
      </div>
      {page.description && (
        <div className="text-xs text-muted-foreground line-clamp-2">
          {page.description}
        </div>
      )}
      <div className="mt-auto flex items-center gap-3 pt-2 text-xs">
        <span className="inline-flex items-center gap-1 text-muted-foreground">
          <Layers className="h-3 w-3" />
          {page.section_count} {page.section_count === 1 ? "section" : "sections"}
        </span>
        <span className="text-muted-foreground/60">·</span>
        {page.is_published ? (
          <span className="inline-flex items-center gap-1 text-emerald-700">
            <CheckCircle2 className="h-3 w-3" />
            Published
          </span>
        ) : (
          <span className="inline-flex items-center gap-1 text-amber-700">
            <CircleDot className="h-3 w-3" />
            Draft
          </span>
        )}
        <span className="ml-auto inline-flex items-center gap-1 text-primary font-medium opacity-0 group-hover:opacity-100 transition">
          Edit <ArrowRight className="h-3 w-3" />
        </span>
      </div>
      <div className="text-[10px] text-muted-foreground/70">
        Updated {formatDate(page.updated_at)}
        {page.updated_by ? ` · ${page.updated_by}` : ""}
      </div>
    </Link>
  );
}

function groupByType(pages: PageSummary[]): Record<string, PageSummary[]> {
  // Stable canonical order: general → product → partner_type → others.
  const ORDER = ["general", "product", "partner_type"];
  const out: Record<string, PageSummary[]> = {};
  for (const t of ORDER) {
    const list = pages.filter((p) => p.page_type === t);
    if (list.length > 0) out[t] = list;
  }
  for (const p of pages) {
    if (!ORDER.includes(p.page_type)) {
      (out[p.page_type] ||= []).push(p);
    }
  }
  return out;
}
