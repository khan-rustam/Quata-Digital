"use client";

import * as React from "react";
import { Clock } from "lucide-react";
import { useApi } from "@/lib/use-api";

type Recent = {
  date: string | null;
  check_in: string | null;
  check_out: string | null;
  status: string;
  hours: number | null;
};
type Summary = {
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

// Reserved status palette — each pairs a hue with a label, never colour alone.
const STATUS: Record<string, { label: string; dot: string; text: string }> = {
  present: { label: "Present", dot: "bg-emerald-500", text: "text-emerald-700" },
  late: { label: "Late", dot: "bg-amber-500", text: "text-amber-700" },
  absent: { label: "Absent", dot: "bg-rose-500", text: "text-rose-700" },
  on_leave: { label: "On leave", dot: "bg-sky-500", text: "text-sky-700" },
};

function fmtTime(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function Tile({ label, value, dot }: { label: string; value: number; dot?: string }) {
  return (
    <div className="rounded-xl border border-border bg-surface-soft px-3 py-2">
      <div className="flex items-center gap-1.5">
        {dot && <span className={`h-2 w-2 rounded-full ${dot}`} aria-hidden />}
        <span className="text-[11px] uppercase tracking-wider text-muted-foreground">{label}</span>
      </div>
      <div className="mt-0.5 text-xl font-semibold tracking-tight">{value}</div>
    </div>
  );
}

export function EmployeeAttendance({ staffId }: { staffId: number }) {
  const { data } = useApi<Summary>(`/admin/staff/${staffId}/attendance-summary`);
  if (!data) return null;

  const monthLabel = new Date(`${data.month}-01T00:00:00`).toLocaleDateString([], { month: "long", year: "numeric" });

  return (
    <div className="rounded-2xl border border-border bg-card p-6 ring-soft">
      <div className="mb-4 flex items-center gap-2">
        <Clock className="h-4 w-4 text-primary" />
        <h2 className="text-sm font-semibold text-foreground/90">Attendance</h2>
        <span className="text-xs text-muted-foreground">{monthLabel}</span>
        <div className="ml-auto text-xs text-muted-foreground">
          {data.worked_hours}h logged
          {data.avg_check_in ? ` · avg in ${data.avg_check_in}` : ""}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Tile label="Present" value={data.present} dot={STATUS.present.dot} />
        <Tile label="Late" value={data.late} dot={STATUS.late.dot} />
        <Tile label="Absent" value={data.absent} dot={STATUS.absent.dot} />
        <Tile label="On leave" value={data.on_leave} dot={STATUS.on_leave.dot} />
      </div>

      {data.recent.length > 0 && (
        <div className="mt-4 border-t border-border/60 pt-3">
          <div className="mb-2 text-[11px] uppercase tracking-wider text-muted-foreground">Recent</div>
          <ul className="space-y-1.5">
            {data.recent.map((r, i) => {
              const st = STATUS[r.status] ?? { label: r.status, dot: "bg-muted-foreground", text: "text-foreground/80" };
              return (
                <li key={i} className="flex items-center gap-2 text-sm">
                  <span className={`h-2 w-2 shrink-0 rounded-full ${st.dot}`} aria-hidden />
                  <span className="w-24 shrink-0 text-muted-foreground">
                    {r.date ? new Date(`${r.date}T00:00:00`).toLocaleDateString([], { month: "short", day: "numeric" }) : "—"}
                  </span>
                  <span className={`w-16 shrink-0 text-xs font-medium ${st.text}`}>{st.label}</span>
                  <span className="text-xs text-muted-foreground">
                    {fmtTime(r.check_in)} – {fmtTime(r.check_out)}
                    {r.hours != null ? ` · ${r.hours}h` : ""}
                  </span>
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </div>
  );
}
