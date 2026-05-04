import * as React from "react";
import { cn } from "@/lib/utils";
import type { LucideIcon } from "lucide-react";

export function StatCard({
  label,
  value,
  delta,
  icon: Icon,
  accent = "primary",
}: {
  label: string;
  value: React.ReactNode;
  delta?: string;
  icon?: LucideIcon;
  accent?: "primary" | "amber" | "rose" | "sky";
}) {
  const accents = {
    primary: "bg-brand-soft text-primary",
    amber: "bg-amber-100 text-amber-900",
    rose: "bg-rose-100 text-rose-900",
    sky: "bg-sky-100 text-sky-900",
  };
  return (
    <div className="rounded-2xl border border-border bg-card p-5 ring-soft">
      <div className="flex items-start justify-between gap-2">
        <div className="text-sm text-muted-foreground">{label}</div>
        {Icon && (
          <div className={cn("inline-flex h-8 w-8 items-center justify-center rounded-lg", accents[accent])}>
            <Icon className="h-4 w-4" />
          </div>
        )}
      </div>
      <div className="mt-2 text-3xl font-semibold tracking-tight">{value}</div>
      {delta && (
        <div className="mt-1 text-xs text-muted-foreground">{delta}</div>
      )}
    </div>
  );
}
