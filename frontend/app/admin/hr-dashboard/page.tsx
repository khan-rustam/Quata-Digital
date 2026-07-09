"use client";

import * as React from "react";
import Link from "next/link";
import { Users, UserCheck, Briefcase, FileText, CalendarOff, Clock, Building2, TrendingUp, FileClock, UserCog } from "lucide-react";
import { PageShell } from "@/components/admin/page-shell";
import { StatCard } from "@/components/admin/stat-card";
import { Badge } from "@/components/ui/badge";
import { CardSkeleton } from "@/components/ui/skeleton";
import { useApi } from "@/lib/use-api";

type Totals = {
  employees: number;
  active_employees: number;
  invited: number;
  suspended: number;
  new_hires_30d: number;
  open_vacancies: number;
  applicants: number;
  on_leave_today: number;
  pending_leave: number;
  business_units: number;
  departments: number;
};
type Bar = { name: string; count: number; max?: number | null; business_unit?: string | null };
type FunnelRow = { stage: string; label: string; count: number };
type HrAnalytics = {
  totals: Totals;
  headcount_by_department: Bar[];
  headcount_by_business_unit: Bar[];
  recruitment_funnel: FunnelRow[];
};

type ContractRow = { id: number; full_name: string; employee_number: string | null; department: string | null; contract_expiry: string; days_left: number; expired: boolean };
type ProbationRow = { id: number; full_name: string; employee_number: string | null; department: string | null; confirmation_date: string | null; overdue: boolean };
type HrAlerts = {
  counts: { contracts_expiring: number; contracts_expired: number; on_probation: number; probation_overdue: number };
  contracts_expiring: ContractRow[];
  on_probation: ProbationRow[];
};

/**
 * Magnitude bars — single hue (brand), rounded data-end anchored to the
 * baseline, direct count label in ink (never the mark colour), recessive
 * track. Single series, so no legend needed.
 */
function BarList({
  rows,
  emptyLabel,
}: {
  rows: { label: string; value: number; sub?: string | null }[];
  emptyLabel: string;
}) {
  const max = Math.max(1, ...rows.map((r) => r.value));
  if (rows.length === 0) {
    return <div className="text-sm text-muted-foreground py-6 text-center">{emptyLabel}</div>;
  }
  return (
    <div className="space-y-2.5">
      {rows.map((r) => (
        <div key={r.label} className="flex items-center gap-3">
          <div className="w-40 shrink-0 truncate text-sm" title={r.label}>{r.label}</div>
          <div className="h-5 flex-1 overflow-hidden rounded-md bg-surface-soft">
            <div
              className="h-full rounded-md bg-primary"
              style={{ width: `${(r.value / max) * 100}%`, minWidth: r.value > 0 ? "0.5rem" : 0 }}
            />
          </div>
          <div className="w-16 text-right text-sm font-medium tabular-nums">
            {r.value}
            {r.sub ? <span className="text-muted-foreground"> / {r.sub}</span> : null}
          </div>
        </div>
      ))}
    </div>
  );
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-2xl border border-border bg-card p-5 ring-soft">
      <h2 className="text-sm font-semibold text-foreground/90 mb-4">{title}</h2>
      {children}
    </div>
  );
}

export default function HrDashboardPage() {
  const { data, loading } = useApi<HrAnalytics>("/admin/hr-analytics");
  const alerts = useApi<HrAlerts>("/admin/hr-alerts");

  return (
    <PageShell
      title="HR dashboard"
      description="Workforce and recruitment at a glance — computed live from employees, jobs, applicants, departments and leave."
      requirePermission="staff:manage"
    >
      {loading || !data ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 8 }).map((_, i) => <CardSkeleton key={i} />)}
        </div>
      ) : (
        <div className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard label="Total employees" value={data.totals.employees} icon={Users} />
            <StatCard label="Active" value={data.totals.active_employees} icon={UserCheck} accent="primary" />
            <StatCard label="Open vacancies" value={data.totals.open_vacancies} icon={Briefcase} accent="sky" />
            <StatCard label="Applicants" value={data.totals.applicants} icon={FileText} accent="amber" />
            <StatCard label="New hires (30d)" value={data.totals.new_hires_30d} icon={TrendingUp} accent="primary" />
            <StatCard label="On leave today" value={data.totals.on_leave_today} icon={CalendarOff} accent="rose" />
            <StatCard label="Pending approvals" value={data.totals.pending_leave} icon={Clock} accent="amber" />
            <StatCard label="Business units" value={data.totals.business_units} delta={`${data.totals.departments} departments`} icon={Building2} accent="sky" />
          </div>

          {alerts.data && (alerts.data.counts.contracts_expiring > 0 || alerts.data.counts.on_probation > 0) && (
            <div className="grid gap-6 lg:grid-cols-2">
              <Panel title="Contracts expiring soon">
                <div className="space-y-2">
                  {alerts.data.contracts_expiring.length === 0 ? (
                    <div className="text-sm text-muted-foreground">None in the window.</div>
                  ) : (
                    alerts.data.contracts_expiring.map((c) => (
                      <Link key={c.id} href={`/admin/staff/${c.id}`} className="flex items-center gap-3 rounded-xl border border-border bg-surface-soft px-3 py-2 hover:bg-card transition">
                        <FileClock className={`h-4 w-4 shrink-0 ${c.expired ? "text-rose-600" : "text-amber-600"}`} />
                        <div className="min-w-0 flex-1">
                          <div className="text-sm font-medium truncate">{c.full_name}</div>
                          <div className="text-[11px] text-muted-foreground truncate">{c.department ?? "—"} · {new Date(`${c.contract_expiry}T00:00:00`).toLocaleDateString()}</div>
                        </div>
                        <Badge variant={c.expired ? "danger" : "warn"}>
                          {c.expired ? "Expired" : `${c.days_left}d left`}
                        </Badge>
                      </Link>
                    ))
                  )}
                </div>
              </Panel>
              <Panel title="On probation">
                <div className="space-y-2">
                  {alerts.data.on_probation.length === 0 ? (
                    <div className="text-sm text-muted-foreground">No one on probation.</div>
                  ) : (
                    alerts.data.on_probation.map((pr) => (
                      <Link key={pr.id} href={`/admin/staff/${pr.id}`} className="flex items-center gap-3 rounded-xl border border-border bg-surface-soft px-3 py-2 hover:bg-card transition">
                        <UserCog className={`h-4 w-4 shrink-0 ${pr.overdue ? "text-rose-600" : "text-primary"}`} />
                        <div className="min-w-0 flex-1">
                          <div className="text-sm font-medium truncate">{pr.full_name}</div>
                          <div className="text-[11px] text-muted-foreground truncate">
                            {pr.department ?? "—"}
                            {pr.confirmation_date ? ` · confirm by ${new Date(`${pr.confirmation_date}T00:00:00`).toLocaleDateString()}` : ""}
                          </div>
                        </div>
                        {pr.overdue ? <Badge variant="danger">Overdue</Badge> : <Badge variant="warn">Probation</Badge>}
                      </Link>
                    ))
                  )}
                </div>
              </Panel>
            </div>
          )}

          <div className="grid gap-6 lg:grid-cols-2">
            <Panel title="Headcount by department">
              <BarList
                rows={data.headcount_by_department.map((d) => ({
                  label: d.name,
                  value: d.count,
                  sub: d.max ? String(d.max) : null,
                }))}
                emptyLabel="No departments yet."
              />
            </Panel>
            <Panel title="Recruitment funnel">
              <BarList
                rows={data.recruitment_funnel.map((f) => ({ label: f.label, value: f.count }))}
                emptyLabel="No applicants yet."
              />
            </Panel>
          </div>

          <Panel title="Headcount by business unit">
            <BarList
              rows={data.headcount_by_business_unit.map((b) => ({ label: b.name, value: b.count }))}
              emptyLabel="No business units yet."
            />
          </Panel>
        </div>
      )}
    </PageShell>
  );
}
