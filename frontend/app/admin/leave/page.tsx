"use client";

import * as React from "react";
import { PageShell } from "@/components/admin/page-shell";
import { DataTable, type Column } from "@/components/admin/data-table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { useApi, useApiAction } from "@/lib/use-api";
import { useToast } from "@/components/ui/toast";
import { TableSkeleton } from "@/components/ui/skeleton";

type LeaveRequest = {
  id: number;
  staff_name: string;
  leave_type: "annual" | "sick" | "parental" | "unpaid" | "other";
  start_date: string;
  end_date: string;
  days: number;
  status: "pending" | "approved" | "rejected";
  reason: string | null;
};

const variant: Record<LeaveRequest["status"], "warn" | "success" | "danger"> = {
  pending: "warn",
  approved: "success",
  rejected: "danger",
};

export default function LeavePage() {
  const { data, loading, refresh } = useApi<LeaveRequest[]>("/admin/leave");
  const action = useApiAction();
  const toast = useToast();
  const [submitting, setSubmitting] = React.useState(false);

  async function setStatus(id: number, status: "approved" | "rejected") {
    try {
      await action(`/admin/leave/${id}`, { method: "PATCH", body: JSON.stringify({ status }) });
      toast.success(`Request ${status}`, "An email notification has been sent.");
      refresh();
    } catch (err) {
      toast.error("Couldn't update", err instanceof Error ? err.message : "Try again.");
    }
  }

  async function applyLeave(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setSubmitting(true);
    const formData = Object.fromEntries(new FormData(e.currentTarget).entries());
    try {
      await action("/leave", { method: "POST", body: JSON.stringify(formData) });
      (e.target as HTMLFormElement).reset();
      toast.success("Request submitted", "Awaiting approval.");
      refresh();
    } catch (err) {
      toast.error("Couldn't submit", err instanceof Error ? err.message : "Try again.");
    } finally {
      setSubmitting(false);
    }
  }

  const columns: Column<LeaveRequest>[] = [
    { key: "name", header: "Employee", cell: (r) => <span className="font-medium">{r.staff_name}</span> },
    { key: "type", header: "Type", cell: (r) => <Badge variant="brand" className="capitalize">{r.leave_type}</Badge> },
    { key: "dates", header: "Dates", cell: (r) => `${r.start_date} → ${r.end_date}` },
    { key: "days", header: "Days", cell: (r) => r.days },
    { key: "status", header: "Status", cell: (r) => (
      <Badge variant={variant[r.status]} className="capitalize">{r.status}</Badge>
    ) },
    { key: "actions", header: "", cell: (r) => r.status === "pending" ? (
      <div className="flex gap-1.5">
        <Button size="sm" onClick={() => setStatus(r.id, "approved")}>Approve</Button>
        <Button size="sm" variant="ghost" className="text-rose-700" onClick={() => setStatus(r.id, "rejected")}>
          Reject
        </Button>
      </div>
    ) : null },
  ];

  return (
    <PageShell
      title="Leave management"
      description="Apply for leave, approve requests and track availability."
    >
      <Tabs defaultValue="requests">
        <TabsList>
          <TabsTrigger value="requests">Requests</TabsTrigger>
          <TabsTrigger value="apply">Apply</TabsTrigger>
          <TabsTrigger value="calendar">Calendar</TabsTrigger>
        </TabsList>
        <TabsContent value="requests">
          {loading ? (
            <TableSkeleton rows={5} cols={6} />
          ) : (
            <DataTable columns={columns} rows={data ?? []} loading={false} />
          )}
        </TabsContent>
        <TabsContent value="apply">
          <form
            onSubmit={applyLeave}
            className="rounded-2xl border border-border bg-card p-6 ring-soft grid gap-4 max-w-xl"
          >
            <div className="grid gap-2">
              <Label htmlFor="leave_type">Leave type</Label>
              <Select id="leave_type" name="leave_type" defaultValue="annual">
                <option value="annual">Annual</option>
                <option value="sick">Sick</option>
                <option value="parental">Parental</option>
                <option value="unpaid">Unpaid</option>
                <option value="other">Other</option>
              </Select>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="grid gap-2">
                <Label htmlFor="start_date">Start</Label>
                <Input id="start_date" name="start_date" type="date" required />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="end_date">End</Label>
                <Input id="end_date" name="end_date" type="date" required />
              </div>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="reason">Reason</Label>
              <Textarea id="reason" name="reason" rows={3} placeholder="Optional — short note for your manager." />
            </div>
            <div>
              <Button type="submit" disabled={submitting}>Submit request</Button>
            </div>
          </form>
        </TabsContent>
        <TabsContent value="calendar">
          <CalendarView leave={data ?? []} onChanged={refresh} />
        </TabsContent>
      </Tabs>
    </PageShell>
  );
}

function toISODate(d: Date) {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function diffDays(a: Date, b: Date): number {
  const ms = b.getTime() - a.getTime();
  return Math.round(ms / 86400000);
}

function CalendarView({ leave, onChanged }: { leave: LeaveRequest[]; onChanged: () => void }) {
  const action = useApiAction();
  const toast = useToast();
  const [cursor, setCursor] = React.useState(() => {
    const t = new Date();
    return new Date(t.getFullYear(), t.getMonth(), 1);
  });
  const [dragging, setDragging] = React.useState<{ id: number; offset: number } | null>(null);

  // Build the month grid (Monday-first)
  const firstOfMonth = new Date(cursor.getFullYear(), cursor.getMonth(), 1);
  const startOffset = (firstOfMonth.getDay() + 6) % 7; // Mon=0 .. Sun=6
  const daysInMonth = new Date(cursor.getFullYear(), cursor.getMonth() + 1, 0).getDate();
  const cells: (Date | null)[] = [];
  for (let i = 0; i < startOffset; i++) cells.push(null);
  for (let d = 1; d <= daysInMonth; d++) cells.push(new Date(cursor.getFullYear(), cursor.getMonth(), d));
  while (cells.length % 7 !== 0) cells.push(null);

  function leaveOn(d: Date) {
    return leave.filter((l) => {
      const start = new Date(l.start_date);
      const end = new Date(l.end_date);
      return d >= startOfDay(start) && d <= startOfDay(end);
    });
  }

  function startOfDay(d: Date) {
    return new Date(d.getFullYear(), d.getMonth(), d.getDate());
  }

  function onDragStart(e: React.DragEvent, l: LeaveRequest, dayIdx: number) {
    const start = new Date(l.start_date);
    const offset = diffDays(startOfDay(start), startOfDay(cells[dayIdx]!));
    setDragging({ id: l.id, offset });
    e.dataTransfer.effectAllowed = "move";
    e.dataTransfer.setData("text/plain", String(l.id));
  }

  function onDragOver(e: React.DragEvent) {
    if (dragging) {
      e.preventDefault();
      e.dataTransfer.dropEffect = "move";
    }
  }

  async function onDrop(e: React.DragEvent, day: Date) {
    e.preventDefault();
    if (!dragging) return;
    const lr = leave.find((l) => l.id === dragging.id);
    if (!lr) return;
    const newStart = new Date(day);
    newStart.setDate(newStart.getDate() - dragging.offset);
    const lengthDays =
      diffDays(startOfDay(new Date(lr.start_date)), startOfDay(new Date(lr.end_date))) + 1;
    const newEnd = new Date(newStart);
    newEnd.setDate(newEnd.getDate() + lengthDays - 1);

    setDragging(null);
    try {
      await action(`/admin/leave/${lr.id}/dates`, {
        method: "PATCH",
        body: JSON.stringify({
          start_date: toISODate(newStart),
          end_date: toISODate(newEnd),
        }),
      });
      toast.success("Rescheduled", `${lr.staff_name} now ${toISODate(newStart)} → ${toISODate(newEnd)}`);
      onChanged();
    } catch (err) {
      toast.error("Couldn't reschedule", err instanceof Error ? err.message : "Try again.");
    }
  }

  return (
    <div className="rounded-2xl border border-border bg-card p-5 ring-soft">
      <div className="flex items-center justify-between mb-4">
        <div className="text-sm font-semibold">
          {cursor.toLocaleString("en-US", { month: "long", year: "numeric" })}
        </div>
        <div className="inline-flex items-center gap-1">
          <Button
            size="sm"
            variant="outline"
            onClick={() =>
              setCursor((c) => new Date(c.getFullYear(), c.getMonth() - 1, 1))
            }
          >
            ←
          </Button>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => {
              const t = new Date();
              setCursor(new Date(t.getFullYear(), t.getMonth(), 1));
            }}
          >
            Today
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={() =>
              setCursor((c) => new Date(c.getFullYear(), c.getMonth() + 1, 1))
            }
          >
            →
          </Button>
        </div>
      </div>
      <div className="grid grid-cols-7 gap-px bg-border rounded-lg overflow-hidden">
        {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((d) => (
          <div key={d} className="bg-surface-soft px-2 py-1.5 text-[10px] uppercase tracking-wider text-muted-foreground">
            {d}
          </div>
        ))}
        {cells.map((d, idx) => {
          if (!d) return <div key={`blank-${idx}`} className="bg-surface min-h-[88px]" />;
          const items = leaveOn(d);
          const today = new Date();
          const isToday =
            d.getFullYear() === today.getFullYear() &&
            d.getMonth() === today.getMonth() &&
            d.getDate() === today.getDate();
          return (
            <div
              key={d.toISOString()}
              onDragOver={onDragOver}
              onDrop={(e) => onDrop(e, d)}
              className={`bg-surface min-h-[88px] p-1.5 ${
                isToday ? "ring-1 ring-primary/40" : ""
              } ${dragging ? "hover:bg-brand-soft/40" : ""}`}
            >
              <div className={`text-xs font-semibold ${isToday ? "text-primary" : ""}`}>
                {d.getDate()}
              </div>
              <div className="mt-1 space-y-0.5">
                {items.slice(0, 3).map((i) => (
                  <div
                    key={i.id}
                    draggable={i.status === "approved" || i.status === "pending"}
                    onDragStart={(e) => onDragStart(e, i, idx)}
                    onDragEnd={() => setDragging(null)}
                    className={`truncate text-[10px] rounded px-1 py-0.5 cursor-grab active:cursor-grabbing ${
                      i.status === "approved"
                        ? "bg-brand-soft text-primary"
                        : i.status === "pending"
                        ? "bg-amber-100 text-amber-900"
                        : "bg-rose-100 text-rose-900"
                    }`}
                    title={`${i.staff_name} · ${i.leave_type} · ${i.status}`}
                  >
                    {i.staff_name}
                  </div>
                ))}
                {items.length > 3 && (
                  <div className="text-[10px] text-muted-foreground">+{items.length - 3}</div>
                )}
              </div>
            </div>
          );
        })}
      </div>
      <p className="mt-3 text-[11px] text-muted-foreground">
        Tip — drag a leave block to a different day to reschedule. Length is preserved.
      </p>
    </div>
  );
}
