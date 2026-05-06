"use client";

import * as React from "react";
import {
  Briefcase,
  Building,
  Cpu,
  FileText,
  Handshake,
  Loader2,
  Package,
  RotateCcw,
  Trash2,
  Users,
} from "lucide-react";

import { PageShell } from "@/components/admin/page-shell";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { useApi, useApiAction } from "@/lib/use-api";
import { useToast } from "@/components/ui/toast";
import { formatDate } from "@/lib/utils";

type TrashItem = {
  id: number;
  deleted_at: string | null;
  name?: string;
  title?: string;
  full_name?: string;
  slug?: string;
  email?: string;
};

type ResourceConfig = {
  slug: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
};

// Mirrors the RESTORABLE allow-list in backend/app/api/routes_security.py.
const RESOURCES: ResourceConfig[] = [
  { slug: "products", label: "Products", icon: Package },
  { slug: "blog", label: "Blog posts", icon: FileText },
  { slug: "pages", label: "CMS pages", icon: FileText },
  { slug: "jobs", label: "Jobs", icon: Briefcase },
  { slug: "applications", label: "Applications", icon: Briefcase },
  { slug: "partners", label: "Partner requests", icon: Handshake },
  { slug: "departments", label: "Departments", icon: Building },
  { slug: "devices", label: "Devices", icon: Cpu },
  { slug: "staff", label: "Staff", icon: Users },
];

export default function TrashPage() {
  return (
    <PageShell
      title="Trash"
      description="Items soft-deleted across the admin. Click Restore to bring them back."
    >
      <Tabs defaultValue={RESOURCES[0].slug}>
        <TabsList>
          {RESOURCES.map((r) => {
            const Icon = r.icon;
            return (
              <TabsTrigger key={r.slug} value={r.slug}>
                <Icon className="h-3.5 w-3.5" /> {r.label}
              </TabsTrigger>
            );
          })}
        </TabsList>
        {RESOURCES.map((r) => (
          <TabsContent key={r.slug} value={r.slug}>
            <TrashList resource={r.slug} label={r.label} />
          </TabsContent>
        ))}
      </Tabs>
    </PageShell>
  );
}

function TrashList({ resource, label }: { resource: string; label: string }) {
  const action = useApiAction();
  const toast = useToast();
  const { data, loading, error, refresh } = useApi<TrashItem[]>(`/admin/trash/${resource}`);
  const [restoring, setRestoring] = React.useState<number | null>(null);

  async function restore(id: number) {
    setRestoring(id);
    try {
      await action(`/admin/trash/${resource}/${id}/restore`, { method: "POST" });
      toast.success("Restored", `Item is back in the live ${label.toLowerCase()} list.`);
      refresh();
    } catch (err) {
      toast.error(
        "Couldn't restore",
        err instanceof Error ? err.message : "Try again.",
      );
    } finally {
      setRestoring(null);
    }
  }

  if (loading) {
    return <div className="text-sm text-muted-foreground">Loading…</div>;
  }
  if (error) {
    return (
      <div className="rounded-2xl border border-rose-200 bg-rose-50 p-6 text-sm text-rose-900">
        Couldn&apos;t load trashed {label.toLowerCase()}. You may not have permission to restore this resource.
      </div>
    );
  }
  if (!data || data.length === 0) {
    return (
      <div className="rounded-2xl border border-dashed border-border bg-surface-soft p-10 text-center">
        <Trash2 className="h-6 w-6 mx-auto mb-3 text-muted-foreground" />
        <div className="text-sm font-medium">Nothing in trash</div>
        <div className="mt-1 text-xs text-muted-foreground">
          Soft-deleted {label.toLowerCase()} would appear here.
        </div>
      </div>
    );
  }
  return (
    <ul className="grid gap-2">
      {data.map((it) => {
        const display =
          it.full_name || it.title || it.name || it.slug || it.email || `#${it.id}`;
        return (
          <li
            key={it.id}
            className="rounded-2xl border border-border bg-card p-4 ring-soft flex flex-wrap items-center gap-3"
          >
            <div className="min-w-0 flex-1">
              <div className="text-sm font-semibold truncate">{display}</div>
              <div className="mt-0.5 text-xs text-muted-foreground">
                ID #{it.id}
                {it.deleted_at ? ` · deleted ${formatDate(it.deleted_at)}` : ""}
              </div>
            </div>
            <Button
              size="sm"
              onClick={() => restore(it.id)}
              disabled={restoring === it.id}
            >
              {restoring === it.id ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <RotateCcw className="h-3.5 w-3.5" />
              )}
              Restore
            </Button>
          </li>
        );
      })}
    </ul>
  );
}
