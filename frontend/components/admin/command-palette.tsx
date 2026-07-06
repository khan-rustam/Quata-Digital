"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import {
  Search,
  LayoutDashboard,
  FileText,
  Package,
  Handshake,
  Briefcase,
  Users,
  MessageSquare,
  CalendarDays,
  Clock,
  Activity,
  BarChart3,
  Cpu,
  Building,
  Shield,
  Settings,
  LogOut,
} from "lucide-react";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";

type Item = {
  label: string;
  href?: string;
  action?: () => void;
  keywords?: string[];
  icon: typeof Search;
  group: "Navigate" | "Account" | "Quick action";
  /** Permission required to see this entry (null = always shown). */
  perm?: string | null;
};

export function CommandPalette() {
  const [open, setOpen] = React.useState(false);
  const [query, setQuery] = React.useState("");
  const [highlight, setHighlight] = React.useState(0);
  const router = useRouter();
  const { signOut, hasPermission } = useAuth();

  React.useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((v) => !v);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  React.useEffect(() => {
    if (!open) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect -- reset palette state every time it opens.
    setQuery("");
    setHighlight(0);
  }, [open]);

  const items: Item[] = React.useMemo(() => [
    { label: "Overview", href: "/admin/overview", icon: LayoutDashboard, group: "Navigate", keywords: ["dashboard", "home"] },
    { label: "Analytics", href: "/admin/analytics", icon: BarChart3, group: "Navigate", perm: "analytics:view" },
    { label: "CMS pages", href: "/admin/cms", icon: FileText, group: "Navigate", keywords: ["blog", "posts"], perm: "content:manage" },
    { label: "Products", href: "/admin/products", icon: Package, group: "Navigate", perm: "content:manage" },
    { label: "Partner requests", href: "/admin/partners", icon: Handshake, group: "Navigate", perm: "partners:manage" },
    { label: "Careers & jobs", href: "/admin/careers", icon: Briefcase, group: "Navigate", keywords: ["jobs", "applicants"], perm: "careers:manage" },
    { label: "Employees", href: "/admin/staff", icon: Users, group: "Navigate", keywords: ["staff"], perm: "staff:manage" },
    { label: "Departments", href: "/admin/departments", icon: Building, group: "Navigate", perm: "staff:manage" },
    { label: "Roles & permissions", href: "/admin/roles", icon: Shield, group: "Navigate", keywords: ["rbac", "permissions"], perm: "rbac:manage" },
    { label: "Messages", href: "/admin/messages", icon: MessageSquare, group: "Navigate", keywords: ["chat", "internal"] },
    { label: "Leave", href: "/admin/leave", icon: CalendarDays, group: "Navigate", keywords: ["holiday"] },
    { label: "Attendance", href: "/admin/attendance", icon: Clock, group: "Navigate" },
    { label: "Devices", href: "/admin/devices", icon: Cpu, group: "Navigate", keywords: ["biometric", "webhook"], perm: "devices:manage" },
    { label: "Activity logs", href: "/admin/activity", icon: Activity, group: "Navigate", keywords: ["audit"], perm: "activity:view" },
    { label: "Settings", href: "/admin/settings", icon: Settings, group: "Account" },
    { label: "Sign out", action: signOut, icon: LogOut, group: "Account" },
  ], [signOut]);

  // Only surface entries the current user can actually open.
  const permitted = React.useMemo(
    () => items.filter((it) => !it.perm || hasPermission(it.perm)),
    [items, hasPermission],
  );

  const filtered = React.useMemo(() => {
    const q = query.toLowerCase().trim();
    if (!q) return permitted;
    return permitted.filter((it) =>
      [it.label, ...(it.keywords ?? [])].some((s) => s.toLowerCase().includes(q))
    );
  }, [permitted, query]);

  function activate(it: Item) {
    setOpen(false);
    if (it.href) router.push(it.href);
    else if (it.action) it.action();
  }

  React.useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- reset highlight when the filtered list changes.
    setHighlight(0);
  }, [query]);

  function onKey(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setHighlight((h) => Math.min(filtered.length - 1, h + 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setHighlight((h) => Math.max(0, h - 1));
    } else if (e.key === "Enter") {
      e.preventDefault();
      const it = filtered[highlight];
      if (it) activate(it);
    }
  }

  // Group results
  const grouped = React.useMemo(() => {
    const groups: Record<string, Item[]> = {};
    for (const it of filtered) {
      (groups[it.group] ??= []).push(it);
    }
    return groups;
  }, [filtered]);

  let runningIndex = 0;

  return (
    <DialogPrimitive.Root open={open} onOpenChange={setOpen}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-ink/40 backdrop-blur-sm data-[state=open]:animate-in data-[state=open]:fade-in-0" />
        <DialogPrimitive.Content className="fixed left-1/2 top-[20%] z-50 w-[92vw] max-w-2xl -translate-x-1/2 rounded-2xl border border-border bg-card shadow-2xl ring-soft overflow-hidden data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95">
          <DialogPrimitive.Title className="sr-only">Command palette</DialogPrimitive.Title>
          <div className="flex items-center gap-3 border-b border-border px-4 py-3">
            <Search className="h-4 w-4 text-muted-foreground" />
            <input
              autoFocus
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={onKey}
              placeholder="Type to search — pages, actions…"
              className="flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground"
            />
            <kbd className="hidden md:inline rounded bg-secondary px-1.5 py-0.5 text-[10px] text-muted-foreground border border-border">
              ESC
            </kbd>
          </div>
          <div className="max-h-[60vh] overflow-y-auto">
            {filtered.length === 0 ? (
              <div className="px-4 py-10 text-center text-sm text-muted-foreground">
                No results for &ldquo;{query}&rdquo;.
              </div>
            ) : (
              Object.entries(grouped).map(([group, items]) => (
                <div key={group} className="py-2">
                  <div className="px-4 py-1 text-[10px] uppercase tracking-wider text-muted-foreground">
                    {group}
                  </div>
                  {items.map((it) => {
                    const idx = runningIndex++;
                    const active = idx === highlight;
                    const Icon = it.icon;
                    return (
                      <button
                        key={it.label}
                        onMouseEnter={() => setHighlight(idx)}
                        onClick={() => activate(it)}
                        className={cn(
                          "flex w-full items-center gap-3 px-4 py-2.5 text-sm",
                          active ? "bg-secondary text-foreground" : "hover:bg-surface-soft"
                        )}
                      >
                        <Icon className="h-4 w-4 text-muted-foreground" />
                        <span className="flex-1 text-left">{it.label}</span>
                        {it.href && (
                          <code className="text-[10px] text-muted-foreground">{it.href}</code>
                        )}
                      </button>
                    );
                  })}
                </div>
              ))
            )}
          </div>
          <div className="flex items-center justify-between gap-3 border-t border-border px-4 py-2 text-[11px] text-muted-foreground">
            <div className="flex items-center gap-3">
              <span>↑↓ navigate</span>
              <span>↵ open</span>
            </div>
            <span>⌘K to toggle</span>
          </div>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}
