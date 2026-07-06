"use client";

import {
  Briefcase,
  Handshake,
  MessageSquare,
  Package,
  Users,
  FileText,
} from "lucide-react";
import { PageShell } from "@/components/admin/page-shell";
import { StatCard } from "@/components/admin/stat-card";
import { CardSkeleton, Skeleton } from "@/components/ui/skeleton";
import { useApi } from "@/lib/use-api";
import { useAuth } from "@/lib/auth";

type Overview = {
  totals: {
    staff: number;
    products: number;
    partner_requests: number;
    job_applications: number;
    open_jobs: number;
    posts: number;
    unread_messages: number;
    pending_leave: number;
  };
  recent_partners: { id: number; partner_type: string; payload: Record<string, string>; created_at: string }[];
  recent_applications: { id: number; full_name: string; job_title: string; created_at: string }[];
  attendance_today: { present: number; absent: number; on_leave: number };
};

export default function OverviewPage() {
  const { user } = useAuth();
  const { data, loading } = useApi<Overview>("/admin/overview");

  return (
    <PageShell
      title="Welcome back"
      description={
        user ? `${user.full_name.split(" ")[0]}, here's what's moving across the ecosystem today.` : ""
      }
    >
      {loading ? (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {Array.from({ length: 8 }).map((_, i) => <CardSkeleton key={i} />)}
        </div>
      ) : !data ? (
        <div className="rounded-2xl border border-border bg-card p-10 text-center ring-soft">
          <div className="text-base font-semibold">Dashboard unavailable</div>
          <p className="mx-auto mt-1 max-w-md text-sm text-muted-foreground">
            We couldn&apos;t load your overview. Your account may not have access to
            these metrics — pick a section you manage from the sidebar.
          </p>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard label="Staff" value={data.totals.staff} icon={Users} />
            <StatCard label="Products" value={data.totals.products} icon={Package} accent="amber" />
            <StatCard label="Partner requests" value={data.totals.partner_requests} icon={Handshake} accent="sky" />
            <StatCard label="Job applications" value={data.totals.job_applications} icon={Briefcase} accent="rose" />
          </div>
          <div className="mt-4 grid grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard label="Open jobs" value={data.totals.open_jobs} icon={Briefcase} />
            <StatCard label="Published posts" value={data.totals.posts} icon={FileText} accent="amber" />
            <StatCard label="Unread messages" value={data.totals.unread_messages} icon={MessageSquare} accent="sky" />
            <StatCard label="Pending leave" value={data.totals.pending_leave} icon={Users} accent="rose" />
          </div>
        </>
      )}

      <div className="mt-8 grid lg:grid-cols-3 gap-4">
        <div className="rounded-2xl border border-border bg-card p-5 ring-soft lg:col-span-2">
          <div className="text-sm font-semibold">Recent partner requests</div>
          {loading ? (
            <div className="mt-4 space-y-3">
              {Array.from({ length: 4 }).map((_, i) => (
                <Skeleton key={i} className="h-10 w-full" />
              ))}
            </div>
          ) : (
            <ul className="mt-4 divide-y divide-border">
              {(data?.recent_partners ?? []).map((p) => (
                <li key={p.id} className="py-3 flex items-center justify-between gap-4">
                  <div>
                    <div className="text-sm font-medium">
                      {p.payload.company_name ?? p.payload.full_name ?? p.payload.name ?? "—"}
                    </div>
                    <div className="text-xs text-muted-foreground capitalize">{p.partner_type}</div>
                  </div>
                  <div className="text-xs text-muted-foreground">
                    {new Date(p.created_at).toLocaleString()}
                  </div>
                </li>
              ))}
              {(data?.recent_partners?.length ?? 0) === 0 && (
                <li className="py-6 text-center text-sm text-muted-foreground">
                  No partner requests yet.
                </li>
              )}
            </ul>
          )}
        </div>
        <div className="rounded-2xl border border-border bg-card p-5 ring-soft">
          <div className="text-sm font-semibold">Attendance today</div>
          {loading ? (
            <div className="mt-4 grid grid-cols-3 gap-2">
              <Skeleton className="h-20" />
              <Skeleton className="h-20" />
              <Skeleton className="h-20" />
            </div>
          ) : (
            <div className="mt-4 grid grid-cols-3 gap-2 text-center">
              <div className="rounded-xl bg-emerald-50 border border-emerald-200 p-3">
                <div className="text-2xl font-semibold text-emerald-900">{data?.attendance_today.present ?? 0}</div>
                <div className="text-xs text-emerald-900/70">Present</div>
              </div>
              <div className="rounded-xl bg-amber-50 border border-amber-200 p-3">
                <div className="text-2xl font-semibold text-amber-900">{data?.attendance_today.on_leave ?? 0}</div>
                <div className="text-xs text-amber-900/70">On leave</div>
              </div>
              <div className="rounded-xl bg-rose-50 border border-rose-200 p-3">
                <div className="text-2xl font-semibold text-rose-900">{data?.attendance_today.absent ?? 0}</div>
                <div className="text-xs text-rose-900/70">Absent</div>
              </div>
            </div>
          )}
        </div>
      </div>
    </PageShell>
  );
}
