"use client";

import * as React from "react";
import { Download, Trash2, Mail, MailX } from "lucide-react";
import { PageShell } from "@/components/admin/page-shell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { StatCard } from "@/components/admin/stat-card";
import { useApi, useApiAction } from "@/lib/use-api";
import { useToast } from "@/components/ui/toast";
import { useAuth } from "@/lib/auth";
import { apiUrl } from "@/lib/api";

type Subscriber = {
  id: number;
  email: string;
  source: string | null;
  locale: string | null;
  is_active: boolean;
  confirmed_at: string | null;
  unsubscribed_at: string | null;
  created_at: string;
};

type ListResponse = {
  total: number;
  active: number;
  items: Subscriber[];
};

export default function NewsletterPage() {
  const [filter, setFilter] = React.useState<"all" | "active" | "unsubscribed">("active");
  const [search, setSearch] = React.useState("");
  const params = new URLSearchParams();
  if (filter === "active") params.set("is_active", "true");
  if (filter === "unsubscribed") params.set("is_active", "false");
  if (search.trim()) params.set("q", search.trim());
  const qs = params.toString();
  const { data, loading, refresh } = useApi<ListResponse>(
    `/admin/newsletter${qs ? `?${qs}` : ""}`
  );
  const action = useApiAction();
  const toast = useToast();
  const { token } = useAuth();

  async function onDelete(id: number) {
    if (!confirm("Permanently delete this subscriber?")) return;
    try {
      await action(`/admin/newsletter/${id}`, { method: "DELETE" });
      toast.success("Subscriber deleted");
      refresh();
    } catch (err) {
      toast.error("Couldn't delete", err instanceof Error ? err.message : "Try again.");
    }
  }

  async function onExport() {
    try {
      const res = await fetch(
        `${apiUrl}/admin/newsletter/export.csv?is_active=true`,
        { headers: token ? { Authorization: `Bearer ${token}` } : undefined }
      );
      if (!res.ok) throw new Error(`Export failed (${res.status})`);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "newsletter-subscribers.csv";
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      toast.error("Export failed", err instanceof Error ? err.message : "Try again.");
    }
  }

  return (
    <PageShell
      title="Newsletter"
      description="Subscribers captured from the marketing site footer and product pages."
      requirePermission="newsletter:manage"
      actions={
        <Button onClick={onExport} variant="outline" size="sm">
          <Download className="h-4 w-4" /> Export active CSV
        </Button>
      }
    >
      <div className="grid gap-6">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <StatCard label="Total subscribers" value={data?.total ?? 0} icon={Mail} />
          <StatCard label="Active" value={data?.active ?? 0} icon={Mail} />
          <StatCard
            label="Unsubscribed"
            value={(data?.total ?? 0) - (data?.active ?? 0)}
            icon={MailX}
          />
        </div>

        <div className="rounded-2xl border border-border bg-card ring-soft">
          <div className="flex flex-wrap items-center gap-2 p-4 border-b border-border">
            <div className="flex items-center gap-1 text-xs">
              {(["active", "all", "unsubscribed"] as const).map((k) => (
                <button
                  key={k}
                  onClick={() => setFilter(k)}
                  className={`rounded-full px-3 py-1.5 capitalize transition ${
                    filter === k
                      ? "bg-foreground text-background"
                      : "border border-border text-muted-foreground hover:text-foreground"
                  }`}
                >
                  {k}
                </button>
              ))}
            </div>
            <div className="flex-1 min-w-[180px]">
              <Input
                placeholder="Search by email…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-surface-soft text-xs uppercase tracking-wider text-muted-foreground">
                <tr>
                  <th className="text-left px-4 py-3 font-semibold">Email</th>
                  <th className="text-left px-4 py-3 font-semibold">Source</th>
                  <th className="text-left px-4 py-3 font-semibold">Locale</th>
                  <th className="text-left px-4 py-3 font-semibold">Status</th>
                  <th className="text-left px-4 py-3 font-semibold">Subscribed</th>
                  <th className="px-4 py-3"></th>
                </tr>
              </thead>
              <tbody>
                {loading && (
                  <tr>
                    <td colSpan={6} className="px-4 py-8 text-center text-muted-foreground">
                      Loading…
                    </td>
                  </tr>
                )}
                {!loading && (data?.items.length ?? 0) === 0 && (
                  <tr>
                    <td colSpan={6} className="px-4 py-10 text-center text-muted-foreground">
                      No subscribers match the current filter.
                    </td>
                  </tr>
                )}
                {(data?.items ?? []).map((s) => (
                  <tr key={s.id} className="border-t border-border">
                    <td className="px-4 py-3 font-medium">{s.email}</td>
                    <td className="px-4 py-3 text-muted-foreground">{s.source ?? "—"}</td>
                    <td className="px-4 py-3 text-muted-foreground uppercase">
                      {s.locale ?? "—"}
                    </td>
                    <td className="px-4 py-3">
                      <Badge variant={s.is_active ? "brand" : "outline"}>
                        {s.is_active ? "Active" : "Unsubscribed"}
                      </Badge>
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {new Date(s.created_at).toLocaleDateString()}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button
                        onClick={() => onDelete(s.id)}
                        className="text-muted-foreground hover:text-rose-600 transition"
                        aria-label="Delete subscriber"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </PageShell>
  );
}
