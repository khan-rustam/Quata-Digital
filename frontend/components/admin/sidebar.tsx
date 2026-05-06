"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
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
  Layers,
  Image as ImageIcon,
  Settings,
  SlidersHorizontal,
  Mail,
  LogOut,
} from "lucide-react";
import { Logo } from "@/components/site/logo";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";

const groups = [
  {
    title: "Overview",
    items: [
      { href: "/admin/overview", label: "Dashboard", icon: LayoutDashboard, perm: null },
      { href: "/admin/analytics", label: "Analytics", icon: BarChart3, perm: "analytics:view" },
    ],
  },
  {
    title: "Content",
    items: [
      { href: "/admin/cms/pages", label: "Marketing pages", icon: Layers, perm: "content:manage" },
      { href: "/admin/cms", label: "Blog & posts", icon: FileText, perm: "content:manage" },
      { href: "/admin/products", label: "Products", icon: Package, perm: "content:manage" },
      { href: "/admin/media", label: "Media library", icon: ImageIcon, perm: "content:manage" },
      { href: "/admin/newsletter", label: "Newsletter", icon: Mail, perm: "newsletter:manage" },
    ],
  },
  {
    title: "Pipeline",
    items: [
      { href: "/admin/partners", label: "Partner requests", icon: Handshake, perm: "partners:manage" },
      { href: "/admin/careers", label: "Careers & jobs", icon: Briefcase, perm: "careers:manage" },
    ],
  },
  {
    title: "Staff",
    items: [
      { href: "/admin/staff", label: "Employees", icon: Users, perm: "staff:manage" },
      { href: "/admin/departments", label: "Departments", icon: Building, perm: "staff:manage" },
      { href: "/admin/roles", label: "Roles & permissions", icon: Shield, perm: "rbac:manage" },
      { href: "/admin/messages", label: "Messages", icon: MessageSquare, perm: null },
      { href: "/admin/leave", label: "Leave", icon: CalendarDays, perm: null },
      { href: "/admin/attendance", label: "Attendance", icon: Clock, perm: null },
      { href: "/admin/devices", label: "Biometric devices", icon: Cpu, perm: "devices:manage" },
    ],
  },
  {
    title: "System",
    items: [
      { href: "/admin/activity", label: "Activity logs", icon: Activity, perm: "activity:view" },
      { href: "/admin/site-settings", label: "Site settings", icon: SlidersHorizontal, perm: "settings:manage" },
      { href: "/admin/settings", label: "My settings", icon: Settings, perm: null },
    ],
  },
];

export function AdminSidebar() {
  const pathname = usePathname();
  const { user, signOut, hasPermission } = useAuth();

  return (
    <aside className="hidden lg:flex w-64 shrink-0 flex-col border-r border-border bg-surface-soft sticky top-0 h-svh">
      {/* Fixed header */}
      <div className="shrink-0 px-5 py-5 border-b border-border">
        <Logo />
        <div className="mt-1 text-[11px] uppercase tracking-wider text-muted-foreground">
          Admin console
        </div>
      </div>
      {/* Scrollable nav (only this scrolls, header + footer stay put) */}
      <nav className="flex-1 min-h-0 overflow-y-auto overscroll-contain px-3 py-4 space-y-6">
        {groups.map((g) => (
          <div key={g.title}>
            <div className="px-2 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
              {g.title}
            </div>
            <div className="mt-2 grid gap-0.5">
              {g.items
                .filter((i) => !i.perm || hasPermission(i.perm))
                .map((item) => {
                  const active =
                    pathname === item.href || pathname.startsWith(item.href + "/");
                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      className={cn(
                        "flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm transition-colors",
                        active
                          ? "bg-surface text-foreground ring-soft"
                          : "text-muted-foreground hover:text-foreground hover:bg-surface/60"
                      )}
                    >
                      <item.icon className="h-4 w-4" />
                      {item.label}
                    </Link>
                  );
                })}
            </div>
          </div>
        ))}
      </nav>
      {/* Fixed footer */}
      <div className="shrink-0 px-3 py-3 border-t border-border bg-surface-soft">
        <div className="rounded-xl border border-border bg-surface p-3">
          <div className="text-sm font-medium truncate">{user?.full_name}</div>
          <div className="text-xs text-muted-foreground truncate">
            {user?.email}
          </div>
          <div className="mt-2 inline-flex items-center gap-1.5 rounded-full bg-brand-soft px-2 py-0.5 text-[11px] font-medium text-primary">
            {user?.role}
          </div>
          <button
            onClick={signOut}
            className="mt-3 flex w-full items-center justify-center gap-1.5 rounded-lg border border-border px-2 py-1.5 text-xs hover:bg-secondary"
          >
            <LogOut className="h-3.5 w-3.5" /> Sign out
          </button>
        </div>
      </div>
    </aside>
  );
}
