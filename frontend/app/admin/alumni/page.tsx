"use client";

import * as React from "react";
import Link from "next/link";
import { PageShell } from "@/components/admin/page-shell";
import { DataTable, type Column } from "@/components/admin/data-table";
import { Badge } from "@/components/ui/badge";
import { TableSkeleton } from "@/components/ui/skeleton";
import { SearchInput, useDebouncedValue } from "@/components/admin/search-input";
import { useApi } from "@/lib/use-api";

type Alumnus = {
  id: number;
  full_name: string;
  employee_number: string | null;
  department: string | null;
  job_title: string | null;
  exit_type: string;
  exit_date: string | null;
  rehire_eligible: boolean;
};

const EXIT_LABEL: Record<string, string> = {
  resignation: "Resignation", retirement: "Retirement", contract_end: "Contract end",
  dismissal: "Dismissal", redundancy: "Redundancy", death: "Deceased",
};

function fmt(s: string | null): string {
  if (!s) return "—";
  const d = new Date(`${s}T00:00:00`);
  return isNaN(d.getTime()) ? s : d.toLocaleDateString(undefined, { dateStyle: "medium" });
}

export default function AlumniPage() {
  const { data, loading } = useApi<Alumnus[]>("/admin/alumni");
  const [search, setSearch] = React.useState("");
  const debounced = useDebouncedValue(search);

  const filtered = React.useMemo(() => {
    const q = debounced.trim().toLowerCase();
    return (data ?? []).filter((a) =>
      !q || [a.full_name, a.department ?? "", a.job_title ?? "", a.employee_number ?? ""].join(" ").toLowerCase().includes(q)
    );
  }, [data, debounced]);

  const cols: Column<Alumnus>[] = [
    {
      key: "name",
      header: "Former employee",
      cell: (a) => (
        <Link href={`/admin/staff/${a.id}`} className="group">
          <div className="font-medium group-hover:text-primary transition-colors">{a.full_name}</div>
          <div className="text-xs text-muted-foreground">{a.employee_number ?? "—"}{a.job_title ? ` · ${a.job_title}` : ""}</div>
        </Link>
      ),
    },
    { key: "dept", header: "Department", cell: (a) => a.department ?? "—" },
    {
      key: "exit",
      header: "Exit",
      cell: (a) => <span>{EXIT_LABEL[a.exit_type] ?? a.exit_type}<span className="text-muted-foreground"> · {fmt(a.exit_date)}</span></span>,
    },
    {
      key: "rehire",
      header: "Rehire",
      cell: (a) => <Badge variant={a.rehire_eligible ? "success" : "default"}>{a.rehire_eligible ? "Eligible" : "No"}</Badge>,
    },
  ];

  return (
    <PageShell
      title="Alumni"
      description="Former employees — searchable, with rehire eligibility. History is never deleted."
      requirePermission="staff:manage"
      actions={<SearchInput value={search} onChange={setSearch} placeholder="Search alumni…" />}
    >
      {loading ? (
        <TableSkeleton rows={5} cols={4} />
      ) : (
        <DataTable columns={cols} rows={filtered} loading={false} empty="No alumni yet." />
      )}
    </PageShell>
  );
}
