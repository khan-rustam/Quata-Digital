"use client";

import * as React from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  ArrowLeft,
  Mail,
  Phone,
  Building,
  Briefcase,
  Activity,
  CalendarDays,
  Clock,
  Shield,
  Loader2,
} from "lucide-react";
import { PageShell } from "@/components/admin/page-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useApi } from "@/lib/use-api";

type Detail = {
  profile: {
    id: number;
    full_name: string;
    email: string;
    phone: string | null;
    avatar_url: string | null;
    job_title: string | null;
    biometric_id: string | null;
    role: string | null;
    department: string | null;
    status: "active" | "invited" | "suspended";
    created_at: string;
  };
  leave: {
    id: number;
    leave_type: string;
    start_date: string;
    end_date: string;
    days: number;
    status: string;
  }[];
  attendance: {
    id: number;
    check_in_at: string | null;
    check_out_at: string | null;
    source: string;
    status: string;
  }[];
  activity: {
    id: number;
    action: string;
    resource_type: string;
    resource_id: string | null;
    created_at: string;
  }[];
};

const statusVariant = {
  active: "success" as const,
  invited: "warn" as const,
  suspended: "danger" as const,
};

export default function StaffDetailPage() {
  const params = useParams<{ id: string }>();
  const id = Array.isArray(params.id) ? params.id[0] : params.id;
  const { data, loading } = useApi<Detail>(id ? `/admin/staff/${id}` : null);

  if (loading || !data) {
    return (
      <PageShell title="Employee" requirePermission="staff:manage">
        <div className="flex items-center justify-center py-20">
          <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
        </div>
      </PageShell>
    );
  }

  const { profile, leave, attendance, activity } = data;

  return (
    <PageShell
      title={profile.full_name}
      description={profile.job_title ?? "Employee"}
      requirePermission="staff:manage"
      actions={
        <Button variant="outline" asChild>
          <Link href="/admin/staff">
            <ArrowLeft className="h-4 w-4" /> Back to employees
          </Link>
        </Button>
      }
    >
      <div className="grid lg:grid-cols-3 gap-4">
        {/* Profile card */}
        <div className="rounded-2xl border border-border bg-card p-6 ring-soft">
          <div className="flex items-center gap-4">
            <div className="h-14 w-14 rounded-full bg-brand-soft text-primary inline-flex items-center justify-center text-base font-semibold">
              {profile.full_name.split(" ").map((p) => p[0]).slice(0, 2).join("")}
            </div>
            <div className="min-w-0">
              <div className="text-base font-semibold">{profile.full_name}</div>
              <div className="text-xs text-muted-foreground truncate">{profile.email}</div>
              <Badge variant={statusVariant[profile.status]} className="mt-2 capitalize">
                {profile.status}
              </Badge>
            </div>
          </div>
          <ul className="mt-6 grid gap-3 text-sm">
            <li className="flex items-center gap-2 text-muted-foreground">
              <Mail className="h-3.5 w-3.5 text-primary" />
              <a href={`mailto:${profile.email}`} className="hover:text-foreground truncate">{profile.email}</a>
            </li>
            {profile.phone && (
              <li className="flex items-center gap-2 text-muted-foreground">
                <Phone className="h-3.5 w-3.5 text-primary" />
                <a href={`tel:${profile.phone}`} className="hover:text-foreground">{profile.phone}</a>
              </li>
            )}
            <li className="flex items-center gap-2 text-muted-foreground">
              <Briefcase className="h-3.5 w-3.5 text-primary" />
              {profile.job_title ?? "—"}
            </li>
            <li className="flex items-center gap-2 text-muted-foreground">
              <Building className="h-3.5 w-3.5 text-primary" />
              {profile.department ?? "—"}
            </li>
            <li className="flex items-center gap-2 text-muted-foreground">
              <Shield className="h-3.5 w-3.5 text-primary" />
              <span className="capitalize">{profile.role?.replace("_", " ") ?? "—"}</span>
            </li>
            {profile.biometric_id && (
              <li className="flex items-center gap-2 text-muted-foreground">
                <code className="text-[10px]">bio: {profile.biometric_id}</code>
              </li>
            )}
          </ul>
          <div className="mt-6 text-xs text-muted-foreground border-t border-border pt-3">
            Joined {new Date(profile.created_at).toLocaleDateString()}
          </div>
        </div>

        {/* Leave history */}
        <div className="rounded-2xl border border-border bg-card p-6 ring-soft">
          <div className="flex items-center gap-2 mb-4">
            <CalendarDays className="h-4 w-4 text-primary" />
            <div className="text-sm font-semibold">Leave history</div>
          </div>
          {leave.length === 0 ? (
            <div className="text-sm text-muted-foreground">No leave requests yet.</div>
          ) : (
            <ul className="divide-y divide-border">
              {leave.map((l) => (
                <li key={l.id} className="py-2.5 text-sm flex items-start justify-between gap-3">
                  <div>
                    <div className="capitalize">{l.leave_type}</div>
                    <div className="text-xs text-muted-foreground">
                      {l.start_date} → {l.end_date} · {l.days}d
                    </div>
                  </div>
                  <Badge
                    variant={
                      l.status === "approved" ? "success" : l.status === "rejected" ? "danger" : "warn"
                    }
                    className="capitalize"
                  >
                    {l.status}
                  </Badge>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* Attendance */}
        <div className="rounded-2xl border border-border bg-card p-6 ring-soft">
          <div className="flex items-center gap-2 mb-4">
            <Clock className="h-4 w-4 text-primary" />
            <div className="text-sm font-semibold">Recent attendance</div>
          </div>
          {attendance.length === 0 ? (
            <div className="text-sm text-muted-foreground">No attendance logged.</div>
          ) : (
            <ul className="divide-y divide-border">
              {attendance.slice(0, 6).map((a) => (
                <li key={a.id} className="py-2.5 text-sm">
                  <div className="flex items-center justify-between">
                    <div>
                      {a.check_in_at ? new Date(a.check_in_at).toLocaleString() : "—"}
                    </div>
                    <Badge
                      variant={
                        a.status === "present" ? "success" : a.status === "late" ? "warn" : "danger"
                      }
                      className="capitalize"
                    >
                      {a.status.replace("_", " ")}
                    </Badge>
                  </div>
                  <div className="text-xs text-muted-foreground">
                    {a.check_out_at ? `out ${new Date(a.check_out_at).toLocaleTimeString()}` : "still in"} · via {a.source}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      {/* Activity */}
      <div className="mt-4 rounded-2xl border border-border bg-card p-6 ring-soft">
        <div className="flex items-center gap-2 mb-4">
          <Activity className="h-4 w-4 text-primary" />
          <div className="text-sm font-semibold">Recent activity</div>
        </div>
        {activity.length === 0 ? (
          <div className="text-sm text-muted-foreground">No activity yet.</div>
        ) : (
          <ul className="divide-y divide-border">
            {activity.map((ev) => (
              <li key={ev.id} className="py-2.5 text-sm flex items-center justify-between gap-3">
                <div>
                  <span className="text-muted-foreground">{ev.action}</span>{" "}
                  <code className="text-xs bg-secondary rounded px-1 py-0.5">
                    {ev.resource_type}
                    {ev.resource_id ? `#${ev.resource_id}` : ""}
                  </code>
                </div>
                <span className="text-xs text-muted-foreground">
                  {new Date(ev.created_at).toLocaleString()}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </PageShell>
  );
}
