"use client";

import * as React from "react";
import Link from "next/link";
import { ChevronDown, ChevronRight, Users } from "lucide-react";
import { PageShell } from "@/components/admin/page-shell";
import { Badge } from "@/components/ui/badge";
import { CardSkeleton } from "@/components/ui/skeleton";
import { useApi } from "@/lib/use-api";

type Node = {
  id: number;
  full_name: string;
  job_title: string | null;
  employee_number: string | null;
  department: string | null;
  business_unit: string | null;
  avatar_url: string | null;
  reports: Node[];
};

function initials(name: string): string {
  return name.split(" ").map((p) => p[0]).slice(0, 2).join("").toUpperCase();
}

function OrgNode({ node }: { node: Node }) {
  const [expanded, setExpanded] = React.useState(true);
  const hasReports = node.reports.length > 0;
  return (
    <div>
      <div className="flex items-center gap-2 rounded-xl border border-border bg-card p-3 ring-soft">
        {hasReports ? (
          <button
            type="button"
            onClick={() => setExpanded((e) => !e)}
            className="text-muted-foreground hover:text-foreground"
            aria-label={expanded ? "Collapse" : "Expand"}
          >
            {expanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
          </button>
        ) : (
          <span className="w-4" />
        )}
        <Link href={`/admin/staff/${node.id}`} className="group flex min-w-0 flex-1 items-center gap-3">
          <span className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-brand-soft text-xs font-semibold text-primary">
            {initials(node.full_name)}
          </span>
          <span className="min-w-0">
            <span className="block truncate text-sm font-medium group-hover:text-primary">{node.full_name}</span>
            <span className="block truncate text-xs text-muted-foreground">
              {[node.job_title, node.department, node.business_unit].filter(Boolean).join(" · ") || "—"}
            </span>
          </span>
        </Link>
        {hasReports && (
          <Badge variant="outline" className="shrink-0">
            <Users className="mr-1 h-3 w-3" />{node.reports.length}
          </Badge>
        )}
      </div>
      {hasReports && expanded && (
        <div className="ml-4 mt-2 space-y-2 border-l border-border pl-4">
          {node.reports.map((r) => <OrgNode key={r.id} node={r} />)}
        </div>
      )}
    </div>
  );
}

export default function OrgChartPage() {
  const { data, loading } = useApi<{ total: number; tree: Node[] }>("/admin/org-chart");
  return (
    <PageShell
      title="Org chart"
      description="Reporting hierarchy — built from each employee's manager. Set a reporting manager on the employee profile to shape it."
      requirePermission="staff:manage"
    >
      {loading || !data ? (
        <div className="grid gap-3">{Array.from({ length: 5 }).map((_, i) => <CardSkeleton key={i} />)}</div>
      ) : data.tree.length === 0 ? (
        <div className="rounded-2xl border border-border bg-card p-10 text-center text-sm text-muted-foreground ring-soft">
          No employees yet.
        </div>
      ) : (
        <div className="space-y-3">
          {data.tree.map((n) => <OrgNode key={n.id} node={n} />)}
        </div>
      )}
    </PageShell>
  );
}
