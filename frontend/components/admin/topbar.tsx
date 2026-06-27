"use client";

import Link from "next/link";
import { Search } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { NotificationsDropdown } from "./notifications-dropdown";
import { AdminMobileNav } from "./mobile-nav";

export function AdminTopbar({ title }: { title: string }) {
  const { user } = useAuth();
  return (
    <header className="sticky top-0 z-30 border-b border-border bg-surface/80 backdrop-blur">
      <div className="flex items-center justify-between gap-4 px-5 lg:px-8 h-16">
        <div className="flex items-center gap-3 min-w-0">
          <AdminMobileNav />
          <div className="min-w-0">
            <div className="text-xs text-muted-foreground">QUATA Admin</div>
            <h1 className="text-base font-semibold tracking-tight truncate">{title}</h1>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => {
              const ev = new KeyboardEvent("keydown", { key: "k", metaKey: true });
              window.dispatchEvent(ev);
            }}
            className="hidden md:flex items-center gap-2 rounded-full border border-border bg-surface px-3 py-1.5 text-sm w-72 hover:bg-secondary"
            aria-label="Open command palette"
          >
            <Search className="h-4 w-4 text-muted-foreground" />
            <span className="text-muted-foreground text-sm flex-1 text-left">Search…</span>
            <kbd className="text-[10px] text-muted-foreground border border-border rounded px-1">
              ⌘K
            </kbd>
          </button>
          <NotificationsDropdown />
          <Link
            href="/admin/settings"
            aria-label="Settings"
            className="ml-1 inline-flex h-8 w-8 items-center justify-center rounded-full bg-brand-soft text-primary text-xs font-semibold hover:ring-2 hover:ring-primary/20"
          >
            {user?.full_name
              ?.split(" ")
              .map((p) => p[0])
              .slice(0, 2)
              .join("") ?? "QA"}
          </Link>
        </div>
      </div>
    </header>
  );
}
