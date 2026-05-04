"use client";

import * as React from "react";
import { Activity, Filter } from "lucide-react";
import { PageShell } from "@/components/admin/page-shell";
import { Skeleton } from "@/components/ui/skeleton";
import { SearchInput, useDebouncedValue } from "@/components/admin/search-input";
import { Select } from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/admin/empty-state";
import { useApi } from "@/lib/use-api";

type Event = {
  id: number;
  actor_name: string;
  action: string;
  resource_type: string;
  resource_id: string | null;
  ip_address: string | null;
  details: Record<string, unknown>;
  created_at: string;
};

type Bucket = { action?: string; resource_type?: string; count: number };

export default function ActivityPage() {
  const [search, setSearch] = React.useState("");
  const debounced = useDebouncedValue(search);
  const [actionFilter, setActionFilter] = React.useState("");
  const [resourceFilter, setResourceFilter] = React.useState("");
  const [since, setSince] = React.useState("");
  const [until, setUntil] = React.useState("");

  const params = new URLSearchParams();
  if (actionFilter) params.set("action", actionFilter);
  if (resourceFilter) params.set("resource_type", resourceFilter);
  if (since) params.set("since", since);
  if (until) params.set("until", until);

  const path = `/admin/activity/v2${params.toString() ? `?${params.toString()}` : ""}`;
  const { data, loading } = useApi<Event[]>(path);
  const actions = useApi<Bucket[]>("/admin/activity/distinct-actions");
  const resources = useApi<Bucket[]>("/admin/activity/distinct-resources");

  const filtered = React.useMemo(() => {
    if (!debounced.trim()) return data ?? [];
    const q = debounced.toLowerCase();
    return (data ?? []).filter((e) =>
      [e.actor_name, e.action, e.resource_type, e.resource_id ?? "", e.ip_address ?? ""]
        .join(" ")
        .toLowerCase()
        .includes(q)
    );
  }, [data, debounced]);

  const activeFilters = [actionFilter, resourceFilter, since, until, debounced].filter(Boolean).length;

  function clearAll() {
    setSearch("");
    setActionFilter("");
    setResourceFilter("");
    setSince("");
    setUntil("");
  }

  return (
    <PageShell
      title="Activity logs"
      description="Login history, admin operations and content updates — every action attributed."
      requirePermission="activity:view"
      actions={
        <SearchInput value={search} onChange={setSearch} placeholder="Search actor, action, resource…" />
      }
    >
      <div className="rounded-2xl border border-border bg-surface-soft p-4 mb-4">
        <div className="flex items-center justify-between gap-3 mb-3">
          <div className="flex items-center gap-2 text-sm font-medium">
            <Filter className="h-4 w-4 text-primary" />
            Filters
            {activeFilters > 0 && (
              <span className="rounded-full bg-brand-soft text-primary text-xs px-2 py-0.5">
                {activeFilters} active
              </span>
            )}
          </div>
          {activeFilters > 0 && (
            <Button size="sm" variant="ghost" onClick={clearAll}>
              Clear all
            </Button>
          )}
        </div>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Select value={actionFilter} onChange={(e) => setActionFilter(e.target.value)}>
            <option value="">All actions</option>
            {(actions.data ?? []).map((a) => (
              <option key={a.action} value={a.action}>
                {a.action} ({a.count})
              </option>
            ))}
          </Select>
          <Select value={resourceFilter} onChange={(e) => setResourceFilter(e.target.value)}>
            <option value="">All resources</option>
            {(resources.data ?? []).map((r) => (
              <option key={r.resource_type} value={r.resource_type}>
                {r.resource_type} ({r.count})
              </option>
            ))}
          </Select>
          <Input type="date" value={since} onChange={(e) => setSince(e.target.value)} placeholder="Since" />
          <Input type="date" value={until} onChange={(e) => setUntil(e.target.value)} placeholder="Until" />
        </div>
      </div>

      {loading ? (
        <div className="rounded-2xl border border-border bg-card overflow-hidden ring-soft p-1">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="p-4 flex items-center justify-between gap-4 border-b border-border last:border-0">
              <Skeleton className="h-4 w-2/3" />
              <Skeleton className="h-3 w-32" />
            </div>
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <EmptyState
          icon={Activity}
          title={activeFilters > 0 ? "No matching activity" : "No activity yet"}
          description={activeFilters > 0 ? "Try clearing some filters." : "Actions across the admin will appear here."}
          action={activeFilters > 0 ? <Button variant="outline" onClick={clearAll}>Clear filters</Button> : undefined}
        />
      ) : (
        <div className="rounded-2xl border border-border bg-card overflow-hidden ring-soft">
          <ul className="divide-y divide-border">
            {filtered.map((e) => (
              <li key={e.id} className="flex items-start justify-between gap-4 p-4 hover:bg-surface-soft">
                <div>
                  <div className="text-sm">
                    <span className="font-semibold">{e.actor_name}</span>{" "}
                    <span className="text-muted-foreground">{e.action}</span>{" "}
                    <code className="text-xs bg-secondary rounded px-1 py-0.5">
                      {e.resource_type}
                      {e.resource_id ? `#${e.resource_id}` : ""}
                    </code>
                  </div>
                  {Object.keys(e.details ?? {}).length > 0 && (
                    <div className="mt-1 text-xs text-muted-foreground font-mono">
                      {Object.entries(e.details).map(([k, v]) => `${k}=${String(v)}`).join(" · ")}
                    </div>
                  )}
                  {e.ip_address && (
                    <div className="mt-0.5 text-xs text-muted-foreground">from {e.ip_address}</div>
                  )}
                </div>
                <div className="text-xs text-muted-foreground whitespace-nowrap">
                  {new Date(e.created_at).toLocaleString()}
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}
    </PageShell>
  );
}
