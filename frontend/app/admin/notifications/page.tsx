"use client";

import * as React from "react";
import Link from "next/link";
import { FileText, CalendarDays, FileClock, UserCog, Gift, Award, GraduationCap, Bell } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { PageShell } from "@/components/admin/page-shell";
import { CardSkeleton } from "@/components/ui/skeleton";
import { useApi } from "@/lib/use-api";

type Item = { type: string; severity: string; title: string; detail: string; link: string; date: string };
type Notifs = { total: number; by_severity: { serious: number; warn: number; info: number }; items: Item[] };

const ICONS: Record<string, LucideIcon> = {
  application: FileText,
  leave: CalendarDays,
  contract: FileClock,
  probation: UserCog,
  birthday: Gift,
  anniversary: Award,
  training: GraduationCap,
};

const SEV_COLOR: Record<string, string> = {
  serious: "text-rose-600 bg-rose-500/10",
  warn: "text-amber-600 bg-amber-500/10",
  info: "text-primary bg-brand-soft",
};

export default function NotificationsPage() {
  const { data, loading } = useApi<Notifs>("/admin/notifications");

  return (
    <PageShell
      title="Notifications"
      description="Everything needing HR attention — computed live from applicants, approvals, contracts, probation, training, birthdays and anniversaries."
      requirePermission="staff:manage"
    >
      {loading || !data ? (
        <div className="grid gap-3">{Array.from({ length: 5 }).map((_, i) => <CardSkeleton key={i} />)}</div>
      ) : data.items.length === 0 ? (
        <div className="rounded-2xl border border-border bg-card p-10 text-center ring-soft">
          <Bell className="mx-auto h-8 w-8 text-muted-foreground" />
          <div className="mt-3 text-sm text-muted-foreground">All caught up — nothing needs attention.</div>
        </div>
      ) : (
        <div className="space-y-2">
          <div className="mb-3 flex flex-wrap gap-3 text-xs text-muted-foreground">
            <span><span className="font-semibold text-rose-600">{data.by_severity.serious}</span> urgent</span>
            <span><span className="font-semibold text-amber-600">{data.by_severity.warn}</span> due soon</span>
            <span><span className="font-semibold text-primary">{data.by_severity.info}</span> fyi</span>
          </div>
          {data.items.map((it, i) => {
            const Icon = ICONS[it.type] ?? Bell;
            return (
              <Link
                key={`${it.type}-${i}`}
                href={it.link}
                className="flex items-center gap-3 rounded-xl border border-border bg-card p-3 ring-soft transition hover:bg-surface-soft"
              >
                <div className={`inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg ${SEV_COLOR[it.severity] ?? SEV_COLOR.info}`}>
                  <Icon className="h-4 w-4" />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="text-sm font-medium">{it.title}</div>
                  {it.detail && <div className="text-[11px] text-muted-foreground truncate">{it.detail}</div>}
                </div>
              </Link>
            );
          })}
        </div>
      )}
    </PageShell>
  );
}
