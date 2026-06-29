"use client";

import * as React from "react";
import { createPortal } from "react-dom";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Menu, X, LogOut } from "lucide-react";
import { Logo } from "@/components/site/logo";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";
import { adminNavGroups } from "./sidebar";

/**
 * Mobile admin navigation — the desktop <AdminSidebar> is `hidden lg:flex`,
 * so on phones/tablets there was no way to reach any admin page. This renders
 * a hamburger (in the topbar) that opens an off-canvas drawer with the full,
 * permission-filtered nav. Closes on backdrop click, link tap, Escape and on
 * route change.
 *
 * The overlay is rendered through a portal to <body>. The topbar header it
 * lives in uses `backdrop-blur`, and an ancestor with `backdrop-filter`
 * becomes the containing block for `position: fixed` descendants — without
 * the portal the `fixed inset-0` overlay collapses to the 64px-tall header
 * box instead of covering the viewport.
 */
export function AdminMobileNav() {
  const [open, setOpen] = React.useState(false);
  const pathname = usePathname();
  const { user, signOut, hasPermission } = useAuth();

  // Close whenever the route changes (e.g. after tapping a link).
  React.useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- collapse the drawer on navigation.
    setOpen(false);
  }, [pathname]);

  // Lock body scroll + close on Escape while the drawer is open.
  React.useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("keydown", onKey);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prevOverflow;
    };
  }, [open]);

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label="Open navigation menu"
        aria-expanded={open}
        className="lg:hidden inline-flex h-9 w-9 items-center justify-center rounded-lg border border-border bg-surface text-foreground hover:bg-secondary"
      >
        <Menu className="h-5 w-5" />
      </button>

      {open &&
        createPortal(
          <div className="lg:hidden fixed inset-0 z-50">
          {/* Backdrop */}
          <button
            type="button"
            aria-label="Close navigation menu"
            onClick={() => setOpen(false)}
            className="absolute inset-0 bg-ink/40 backdrop-blur-sm"
          />

          {/* Drawer */}
          <div className="absolute inset-y-0 left-0 flex w-72 max-w-[85%] flex-col border-r border-border bg-surface-soft shadow-xl">
            <div className="shrink-0 flex items-center justify-between gap-2 px-5 py-4 border-b border-border">
              <div>
                <Logo />
                <div className="mt-1 text-[11px] uppercase tracking-wider text-muted-foreground">
                  Admin console
                </div>
              </div>
              <button
                type="button"
                onClick={() => setOpen(false)}
                aria-label="Close navigation menu"
                className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-border hover:bg-secondary"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <nav className="flex-1 min-h-0 overflow-y-auto overscroll-contain px-3 py-4 space-y-6">
              {adminNavGroups.map((g) => (
                <div key={g.title}>
                  <div className="px-2 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                    {g.title}
                  </div>
                  <div className="mt-2 grid gap-0.5">
                    {g.items
                      .filter((i) => !i.perm || hasPermission(i.perm))
                      .map((item) => {
                        const active =
                          pathname === item.href ||
                          pathname.startsWith(item.href + "/");
                        return (
                          <Link
                            key={item.href}
                            href={item.href}
                            onClick={() => setOpen(false)}
                            className={cn(
                              "flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm transition-colors",
                              active
                                ? "bg-surface text-foreground ring-soft"
                                : "text-muted-foreground hover:text-foreground hover:bg-surface/60",
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

            <div className="shrink-0 px-3 py-3 border-t border-border bg-surface-soft">
              <div className="rounded-xl border border-border bg-surface p-3">
                <div className="text-sm font-medium truncate">{user?.full_name}</div>
                <div className="text-xs text-muted-foreground truncate">{user?.email}</div>
                {user?.role && (
                  <div className="mt-2 inline-flex items-center gap-1.5 rounded-full bg-brand-soft px-2 py-0.5 text-[11px] font-medium text-primary">
                    {user.role}
                  </div>
                )}
                <button
                  onClick={signOut}
                  className="mt-3 flex w-full items-center justify-center gap-1.5 rounded-lg border border-border px-2 py-1.5 text-xs hover:bg-secondary"
                >
                  <LogOut className="h-3.5 w-3.5" /> Sign out
                </button>
              </div>
            </div>
          </div>
        </div>,
          document.body,
        )}
    </>
  );
}
