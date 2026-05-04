"use client";

import * as React from "react";
import * as Popover from "@radix-ui/react-popover";
import Link from "next/link";
import { Bell, Check } from "lucide-react";
import { useApi } from "@/lib/use-api";
import { cn } from "@/lib/utils";

type Event = {
  id: number;
  actor_name: string;
  action: string;
  resource_type: string;
  resource_id: string | null;
  created_at: string;
};

const READ_KEY = "quata_notifications_seen_id";

export function NotificationsDropdown() {
  const { data, loading } = useApi<Event[]>("/admin/activity");
  const [seenId, setSeenId] = React.useState<number>(0);

  React.useEffect(() => {
    const v = Number(localStorage.getItem(READ_KEY) ?? "0");
    setSeenId(Number.isFinite(v) ? v : 0);
  }, []);

  const events = (data ?? []).slice(0, 12);
  const unread = events.filter((e) => e.id > seenId).length;

  function markAllRead() {
    if (events[0]) {
      const newest = events[0].id;
      localStorage.setItem(READ_KEY, String(newest));
      setSeenId(newest);
    }
  }

  return (
    <Popover.Root>
      <Popover.Trigger asChild>
        <button
          className="relative inline-flex h-9 w-9 items-center justify-center rounded-full border border-border hover:bg-secondary"
          aria-label="Notifications"
        >
          <Bell className="h-4 w-4" />
          {unread > 0 && (
            <span className="absolute -right-1 -top-1 inline-flex min-h-[18px] min-w-[18px] items-center justify-center rounded-full bg-primary px-1 text-[10px] font-bold text-primary-foreground">
              {unread > 9 ? "9+" : unread}
            </span>
          )}
        </button>
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content
          align="end"
          sideOffset={6}
          className="w-[360px] rounded-2xl border border-border bg-card shadow-xl ring-soft z-50"
        >
          <div className="flex items-center justify-between border-b border-border p-3">
            <div className="text-sm font-semibold">Notifications</div>
            <button
              onClick={markAllRead}
              className="inline-flex items-center gap-1 text-xs text-primary hover:underline"
            >
              <Check className="h-3 w-3" /> Mark all read
            </button>
          </div>
          <div className="max-h-[420px] overflow-y-auto">
            {loading ? (
              <div className="p-6 text-center text-xs text-muted-foreground">Loading…</div>
            ) : events.length === 0 ? (
              <div className="p-6 text-center text-xs text-muted-foreground">No activity yet.</div>
            ) : (
              <ul className="divide-y divide-border">
                {events.map((e) => {
                  const isUnread = e.id > seenId;
                  return (
                    <li key={e.id} className="p-3 flex items-start gap-3 hover:bg-surface-soft">
                      <span
                        className={cn(
                          "mt-1.5 inline-block h-2 w-2 rounded-full shrink-0",
                          isUnread ? "bg-primary" : "bg-muted"
                        )}
                      />
                      <div className="flex-1 min-w-0">
                        <div className="text-sm">
                          <span className="font-semibold">{e.actor_name}</span>{" "}
                          <span className="text-muted-foreground">{e.action}</span>{" "}
                          <code className="text-[11px] bg-secondary rounded px-1">
                            {e.resource_type}{e.resource_id ? `#${e.resource_id}` : ""}
                          </code>
                        </div>
                        <div className="mt-0.5 text-[11px] text-muted-foreground">
                          {new Date(e.created_at).toLocaleString()}
                        </div>
                      </div>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
          <div className="border-t border-border p-2">
            <Link
              href="/admin/activity"
              className="block w-full rounded-lg px-3 py-2 text-center text-xs font-medium text-primary hover:bg-secondary"
            >
              See all activity →
            </Link>
          </div>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}
