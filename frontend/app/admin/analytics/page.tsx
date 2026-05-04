"use client";

import * as React from "react";
import {
  Eye,
  FileSignature,
  Briefcase,
  Handshake,
  TrendingUp,
  Users,
} from "lucide-react";
import { PageShell } from "@/components/admin/page-shell";
import { StatCard } from "@/components/admin/stat-card";
import { CardSkeleton, Skeleton } from "@/components/ui/skeleton";
import { BarChart, LineChart } from "@/components/admin/charts";
import { useApi } from "@/lib/use-api";

type Analytics = {
  visits_7d: number;
  unique_visitors_7d: number;
  form_submissions_7d: number;
  partner_requests_7d: number;
  job_applications_7d: number;
  contact_messages_7d: number;
  top_pages: { path: string; views: number }[];
  partner_funnel: { type: string; count: number }[];
};

type TimeSeries = {
  visits: { date: string; value: number }[];
  partner_requests: { date: string; value: number }[];
  job_applications: { date: string; value: number }[];
};

export default function AnalyticsPage() {
  const { data, loading } = useApi<Analytics>("/admin/analytics");
  const [days, setDays] = React.useState(14);
  const ts = useApi<TimeSeries>(`/admin/analytics/timeseries?days=${days}`);

  return (
    <PageShell
      title="Website analytics"
      description="Traffic, form submissions and partner activity for the public-site only. Fintech transaction analytics live in QUATAPAY."
      requirePermission="analytics:view"
    >
      {loading ? (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => <CardSkeleton key={i} />)}
        </div>
      ) : (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard label="Visits (7d)" value={data?.visits_7d ?? 0} icon={Eye} />
            <StatCard label="Unique visitors" value={data?.unique_visitors_7d ?? 0} icon={Users} accent="amber" />
            <StatCard label="Form submissions" value={data?.form_submissions_7d ?? 0} icon={FileSignature} accent="sky" />
            <StatCard label="Partner requests" value={data?.partner_requests_7d ?? 0} icon={Handshake} accent="rose" />
          </div>
          <div className="mt-4 grid grid-cols-2 lg:grid-cols-2 gap-4">
            <StatCard label="Job applications" value={data?.job_applications_7d ?? 0} icon={Briefcase} />
            <StatCard label="Contact messages" value={data?.contact_messages_7d ?? 0} icon={TrendingUp} accent="amber" />
          </div>
        </>
      )}

      <div className="mt-8 rounded-2xl border border-border bg-card p-6 ring-soft">
        <div className="flex items-center justify-between gap-4 mb-6">
          <div>
            <div className="text-sm font-semibold">Page views</div>
            <div className="text-xs text-muted-foreground">Daily volume across the public site</div>
          </div>
          <div className="inline-flex items-center gap-1 rounded-full border border-border bg-surface-soft p-1 text-xs">
            {[7, 14, 30].map((d) => (
              <button
                key={d}
                onClick={() => setDays(d)}
                className={`rounded-full px-3 py-1 ${days === d ? "bg-surface text-foreground shadow-sm" : "text-muted-foreground"}`}
              >
                {d}d
              </button>
            ))}
          </div>
        </div>
        {ts.loading ? (
          <Skeleton className="h-[220px]" />
        ) : (
          <LineChart points={ts.data?.visits ?? []} label="visits" />
        )}
      </div>

      <div className="mt-4 grid lg:grid-cols-2 gap-4">
        <div className="rounded-2xl border border-border bg-card p-6 ring-soft">
          <div className="text-sm font-semibold mb-1">Partner requests by day</div>
          <div className="text-xs text-muted-foreground mb-5">Last {days} days</div>
          {ts.loading ? (
            <Skeleton className="h-[200px]" />
          ) : (
            <BarChart points={ts.data?.partner_requests ?? []} label="requests" />
          )}
        </div>
        <div className="rounded-2xl border border-border bg-card p-6 ring-soft">
          <div className="text-sm font-semibold mb-1">Job applications by day</div>
          <div className="text-xs text-muted-foreground mb-5">Last {days} days</div>
          {ts.loading ? (
            <Skeleton className="h-[200px]" />
          ) : (
            <BarChart points={ts.data?.job_applications ?? []} label="applications" color="var(--accent)" />
          )}
        </div>
      </div>

      <div className="mt-4 grid lg:grid-cols-2 gap-4">
        <div className="rounded-2xl border border-border bg-card p-5 ring-soft">
          <div className="text-sm font-semibold">Top pages</div>
          {loading ? (
            <div className="mt-4 space-y-2">
              {Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-7" />)}
            </div>
          ) : (
            <ul className="mt-4 divide-y divide-border">
              {(data?.top_pages ?? []).map((p) => {
                const max = Math.max(...(data?.top_pages.map((x) => x.views) ?? [1]));
                return (
                  <li key={p.path} className="py-2.5">
                    <div className="flex items-center justify-between text-sm">
                      <code className="text-xs">{p.path || "/"}</code>
                      <span className="font-medium">{p.views.toLocaleString()}</span>
                    </div>
                    <div className="mt-1.5 h-1.5 rounded-full bg-secondary overflow-hidden">
                      <div className="h-full gradient-brand" style={{ width: `${(p.views / max) * 100}%` }} />
                    </div>
                  </li>
                );
              })}
              {!loading && (data?.top_pages?.length ?? 0) === 0 && (
                <li className="py-6 text-center text-sm text-muted-foreground">No traffic yet.</li>
              )}
            </ul>
          )}
        </div>
        <div className="rounded-2xl border border-border bg-card p-5 ring-soft">
          <div className="text-sm font-semibold">Partner gateway funnel</div>
          {loading ? (
            <div className="mt-4 space-y-3">
              {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-8" />)}
            </div>
          ) : (
            <div className="mt-4 space-y-3">
              {(data?.partner_funnel ?? []).map((f) => {
                const max = Math.max(...(data?.partner_funnel.map((x) => x.count) ?? [1]));
                return (
                  <div key={f.type}>
                    <div className="flex items-center justify-between text-xs">
                      <span className="capitalize">{f.type}</span>
                      <span className="font-medium">{f.count}</span>
                    </div>
                    <div className="mt-1 h-2 rounded-full bg-secondary overflow-hidden">
                      <div
                        className="h-full gradient-brand"
                        style={{ width: `${Math.max(8, (f.count / max) * 100)}%` }}
                      />
                    </div>
                  </div>
                );
              })}
              {(data?.partner_funnel?.length ?? 0) === 0 && (
                <div className="text-sm text-muted-foreground">No requests yet.</div>
              )}
            </div>
          )}
        </div>
      </div>
    </PageShell>
  );
}
