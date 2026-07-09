"use client";

import * as React from "react";
import { CalendarDays } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { useApi } from "@/lib/use-api";

type Balance = {
  year: number;
  annual_entitlement: number;
  annual_used: number;
  annual_remaining: number;
  pending: number;
  by_type: { leave_type: string; days: number }[];
};

function Stat({ label, value, accent }: { label: string; value: number; accent?: boolean }) {
  return (
    <div>
      <div className={"text-2xl font-semibold tracking-tight" + (accent ? " text-primary" : "")}>{value}</div>
      <div className="text-[11px] uppercase tracking-wider text-muted-foreground">{label}</div>
    </div>
  );
}

export function EmployeeLeaveBalance({ staffId }: { staffId: number }) {
  const { data } = useApi<Balance>(`/admin/staff/${staffId}/leave-balance`);
  if (!data) return null;

  return (
    <div className="rounded-2xl border border-border bg-card p-6 ring-soft">
      <div className="mb-4 flex items-center gap-2">
        <CalendarDays className="h-4 w-4 text-primary" />
        <h2 className="text-sm font-semibold text-foreground/90">Leave balance</h2>
        <span className="text-xs text-muted-foreground">{data.year}</span>
        {data.pending > 0 && <Badge variant="warn" className="ml-auto">{data.pending} pending</Badge>}
      </div>
      <div className="grid grid-cols-3 gap-4">
        <Stat label="Entitlement" value={data.annual_entitlement} />
        <Stat label="Used" value={data.annual_used} />
        <Stat label="Remaining" value={data.annual_remaining} accent />
      </div>
      {data.by_type.length > 0 && (
        <div className="mt-4 flex flex-wrap gap-2 border-t border-border/60 pt-3">
          {data.by_type.map((t) => (
            <span key={t.leave_type} className="rounded-full border border-border bg-surface-soft px-2.5 py-1 text-xs capitalize text-foreground/85">
              {t.leave_type}: <span className="font-medium">{t.days}d</span>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
