"use client";

import { Wifi, WifiOff, Loader2 } from "lucide-react";

type Props = { status: "idle" | "connecting" | "open" | "closed" | "error" };

export function LiveIndicator({ status }: Props) {
  if (status === "open") {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 border border-emerald-200 px-2.5 py-1 text-[11px] font-medium text-emerald-900">
        <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500">
          <span className="absolute inset-0 rounded-full bg-emerald-500 opacity-60 animate-ping" />
        </span>
        Live
      </span>
    );
  }
  if (status === "connecting") {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full border border-border bg-surface-soft px-2.5 py-1 text-[11px] font-medium text-muted-foreground">
        <Loader2 className="h-3 w-3 animate-spin" />
        Connecting…
      </span>
    );
  }
  if (status === "error" || status === "closed") {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full border border-amber-200 bg-amber-50 px-2.5 py-1 text-[11px] font-medium text-amber-900">
        <WifiOff className="h-3 w-3" />
        Offline · retrying
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-border bg-surface-soft px-2.5 py-1 text-[11px] font-medium text-muted-foreground">
      <Wifi className="h-3 w-3" />
      Idle
    </span>
  );
}
