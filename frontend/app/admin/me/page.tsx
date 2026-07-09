"use client";

import * as React from "react";
import { CalendarDays, Clock, LogIn, LogOut, Plus } from "lucide-react";
import { PageShell } from "@/components/admin/page-shell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { CardSkeleton } from "@/components/ui/skeleton";
import { useApi, useApiAction } from "@/lib/use-api";
import { useToast } from "@/components/ui/toast";

type Balance = {
  year: number;
  annual_entitlement: number;
  annual_used: number;
  annual_remaining: number;
  pending: number;
  by_type: { leave_type: string; days: number }[];
};
type Recent = { date: string | null; check_in: string | null; check_out: string | null; status: string; hours: number | null };
type Attendance = {
  month: string;
  present: number;
  late: number;
  absent: number;
  on_leave: number;
  days_logged: number;
  worked_hours: number;
  avg_check_in: string | null;
  recent: Recent[];
};
type LeaveReq = { id: number; leave_type: string; start_date: string; end_date: string; days: number; status: string; reason: string | null };
type Workspace = {
  profile: { id: number; full_name: string; email: string; job_title: string | null; department: string | null; employee_number: string | null; avatar_url: string | null };
  leave_balance: Balance;
  leave_requests: LeaveReq[];
  attendance: Attendance;
  checked_in: boolean;
  checked_in_at: string | null;
};

const LEAVE_TYPES = ["annual", "sick", "maternity", "paternity", "parental", "emergency", "compassionate", "study", "unpaid", "other"];

const STATUS: Record<string, string> = {
  present: "bg-emerald-500",
  late: "bg-amber-500",
  absent: "bg-rose-500",
  on_leave: "bg-sky-500",
};

function leaveVariant(status: string): "warn" | "success" | "danger" | "default" {
  if (status === "approved") return "success";
  if (status === "pending") return "warn";
  if (status === "rejected") return "danger";
  return "default";
}

function fmtDate(iso: string | null): string {
  return iso ? new Date(`${iso}T00:00:00`).toLocaleDateString([], { month: "short", day: "numeric" }) : "—";
}
function fmtTime(iso: string | null): string {
  return iso ? new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "—";
}

function Stat({ label, value, accent }: { label: string; value: React.ReactNode; accent?: boolean }) {
  return (
    <div>
      <div className={"text-2xl font-semibold tracking-tight" + (accent ? " text-primary" : "")}>{value}</div>
      <div className="text-[11px] uppercase tracking-wider text-muted-foreground">{label}</div>
    </div>
  );
}

export default function MyWorkspacePage() {
  const { data, loading, refresh } = useApi<Workspace>("/me/workspace");
  const action = useApiAction();
  const toast = useToast();
  const [busy, setBusy] = React.useState(false);

  async function toggleAttendance() {
    if (!data) return;
    setBusy(true);
    try {
      await action(`/attendance/${data.checked_in ? "out" : "in"}`, { method: "POST", body: JSON.stringify({ source: "web" }) });
      toast.success(data.checked_in ? "Checked out" : "Checked in");
      refresh();
    } catch (err) {
      toast.error("Couldn't update attendance", err instanceof Error ? err.message : "Try again.");
    } finally {
      setBusy(false);
    }
  }

  async function applyLeave(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const body = Object.fromEntries(new FormData(form).entries());
    setBusy(true);
    try {
      await action("/leave", { method: "POST", body: JSON.stringify(body) });
      toast.success("Leave request submitted", "Awaiting approval.");
      form.reset();
      refresh();
    } catch (err) {
      toast.error("Couldn't submit request", err instanceof Error ? err.message : "Check the dates and try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <PageShell title="My workspace" description="Your attendance, leave balance and requests — all in one place.">
      {loading || !data ? (
        <div className="grid gap-4 sm:grid-cols-2">
          {Array.from({ length: 4 }).map((_, i) => <CardSkeleton key={i} />)}
        </div>
      ) : (
        <div className="space-y-6">
          {/* Profile + check in/out */}
          <div className="flex flex-wrap items-center gap-4 rounded-2xl border border-border bg-card p-6 ring-soft">
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-brand-soft text-lg font-semibold text-primary">
              {data.profile.full_name.slice(0, 1).toUpperCase()}
            </div>
            <div className="min-w-0 flex-1">
              <div className="text-lg font-semibold">{data.profile.full_name}</div>
              <div className="text-sm text-muted-foreground">
                {data.profile.job_title ?? "—"}
                {data.profile.department ? ` · ${data.profile.department}` : ""}
                {data.profile.employee_number ? ` · ${data.profile.employee_number}` : ""}
              </div>
            </div>
            <div className="flex flex-col items-end gap-1">
              <Button onClick={toggleAttendance} disabled={busy} variant={data.checked_in ? "outline" : "default"}>
                {data.checked_in ? <LogOut className="h-4 w-4" /> : <LogIn className="h-4 w-4" />}
                {data.checked_in ? "Check out" : "Check in"}
              </Button>
              {data.checked_in && data.checked_in_at && (
                <span className="text-[11px] text-muted-foreground">Since {fmtTime(data.checked_in_at)}</span>
              )}
            </div>
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            {/* Leave balance */}
            <div className="rounded-2xl border border-border bg-card p-6 ring-soft">
              <div className="mb-4 flex items-center gap-2">
                <CalendarDays className="h-4 w-4 text-primary" />
                <h2 className="text-sm font-semibold text-foreground/90">Leave balance</h2>
                <span className="text-xs text-muted-foreground">{data.leave_balance.year}</span>
                {data.leave_balance.pending > 0 && <Badge variant="warn" className="ml-auto">{data.leave_balance.pending} pending</Badge>}
              </div>
              <div className="grid grid-cols-3 gap-4">
                <Stat label="Entitlement" value={data.leave_balance.annual_entitlement} />
                <Stat label="Used" value={data.leave_balance.annual_used} />
                <Stat label="Remaining" value={data.leave_balance.annual_remaining} accent />
              </div>
              {data.leave_balance.by_type.length > 0 && (
                <div className="mt-4 flex flex-wrap gap-2 border-t border-border/60 pt-3">
                  {data.leave_balance.by_type.map((t) => (
                    <span key={t.leave_type} className="rounded-full border border-border bg-surface-soft px-2.5 py-1 text-xs capitalize text-foreground/85">
                      {t.leave_type}: <span className="font-medium">{t.days}d</span>
                    </span>
                  ))}
                </div>
              )}
            </div>

            {/* Attendance */}
            <div className="rounded-2xl border border-border bg-card p-6 ring-soft">
              <div className="mb-4 flex items-center gap-2">
                <Clock className="h-4 w-4 text-primary" />
                <h2 className="text-sm font-semibold text-foreground/90">Attendance</h2>
                <span className="text-xs text-muted-foreground">{new Date(`${data.attendance.month}-01T00:00:00`).toLocaleDateString([], { month: "long", year: "numeric" })}</span>
                <div className="ml-auto text-xs text-muted-foreground">
                  {data.attendance.worked_hours}h{data.attendance.avg_check_in ? ` · avg ${data.attendance.avg_check_in}` : ""}
                </div>
              </div>
              <div className="grid grid-cols-4 gap-3">
                <Stat label="Present" value={data.attendance.present} />
                <Stat label="Late" value={data.attendance.late} />
                <Stat label="Absent" value={data.attendance.absent} />
                <Stat label="Leave" value={data.attendance.on_leave} />
              </div>
              {data.attendance.recent.length > 0 && (
                <ul className="mt-4 space-y-1.5 border-t border-border/60 pt-3">
                  {data.attendance.recent.slice(0, 5).map((r, i) => (
                    <li key={i} className="flex items-center gap-2 text-sm">
                      <span className={`h-2 w-2 shrink-0 rounded-full ${STATUS[r.status] ?? "bg-muted-foreground"}`} aria-hidden />
                      <span className="w-16 shrink-0 text-muted-foreground">{fmtDate(r.date)}</span>
                      <span className="text-xs text-muted-foreground">
                        {fmtTime(r.check_in)} – {fmtTime(r.check_out)}
                        {r.hours != null ? ` · ${r.hours}h` : ""}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>

          {/* Apply for leave */}
          <div className="rounded-2xl border border-border bg-card p-6 ring-soft">
            <h2 className="mb-4 text-sm font-semibold text-foreground/90">Request leave</h2>
            <form onSubmit={applyLeave} className="grid gap-4 sm:grid-cols-4">
              <div className="grid gap-1.5">
                <Label htmlFor="leave_type">Type</Label>
                <Select id="leave_type" name="leave_type" defaultValue="annual">
                  {LEAVE_TYPES.map((t) => <option key={t} value={t} className="capitalize">{t}</option>)}
                </Select>
              </div>
              <div className="grid gap-1.5">
                <Label htmlFor="start_date">From</Label>
                <Input id="start_date" name="start_date" type="date" required />
              </div>
              <div className="grid gap-1.5">
                <Label htmlFor="end_date">To</Label>
                <Input id="end_date" name="end_date" type="date" required />
              </div>
              <div className="grid gap-1.5">
                <Label htmlFor="reason">Reason</Label>
                <Input id="reason" name="reason" placeholder="Optional" />
              </div>
              <div className="sm:col-span-4">
                <Button type="submit" disabled={busy}>
                  <Plus className="h-4 w-4" /> Submit request
                </Button>
              </div>
            </form>
          </div>

          {/* My requests */}
          <div className="rounded-2xl border border-border bg-card p-6 ring-soft">
            <h2 className="mb-4 text-sm font-semibold text-foreground/90">My leave requests</h2>
            {data.leave_requests.length === 0 ? (
              <div className="text-sm text-muted-foreground">No requests yet.</div>
            ) : (
              <ul className="space-y-2">
                {data.leave_requests.map((lr) => (
                  <li key={lr.id} className="flex items-center gap-3 rounded-xl border border-border bg-surface-soft px-3 py-2">
                    <div className="min-w-0 flex-1">
                      <div className="text-sm font-medium capitalize">{lr.leave_type} · {lr.days}d</div>
                      <div className="text-[11px] text-muted-foreground">
                        {fmtDate(lr.start_date)} – {fmtDate(lr.end_date)}
                        {lr.reason ? ` · ${lr.reason}` : ""}
                      </div>
                    </div>
                    <Badge variant={leaveVariant(lr.status)} className="capitalize">{lr.status}</Badge>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}
    </PageShell>
  );
}
