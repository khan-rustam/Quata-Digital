"use client";

import { AdminTopbar } from "./topbar";
import { useAuth } from "@/lib/auth";
import { Loader2 } from "lucide-react";

export function PageShell({
  title,
  description,
  actions,
  children,
  requirePermission,
  narrow,
}: {
  title: string;
  description?: string;
  actions?: React.ReactNode;
  children: React.ReactNode;
  requirePermission?: string;
  /**
   * Set to true on pages whose body is a narrow form (settings, profile,
   * single-column composers). Wraps the header + content in a centered
   * `max-w-3xl mx-auto` container so the form sits in the middle of the
   * available width on wide screens instead of hugging the sidebar.
   */
  narrow?: boolean;
}) {
  const { user, loading, hasPermission } = useAuth();

  if (loading) {
    return (
      <div className="flex h-svh items-center justify-center">
        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
      </div>
    );
  }
  if (!user) return null;
  if (requirePermission && !hasPermission(requirePermission)) {
    return (
      <div className="p-10">
        <div className="rounded-2xl border border-amber-200 bg-amber-50 p-6 text-amber-900">
          You don&apos;t have permission to view this page.
        </div>
      </div>
    );
  }

  const inner = narrow ? "max-w-3xl mx-auto w-full" : undefined;

  return (
    <div className="flex-1 min-w-0">
      <AdminTopbar title={title} />
      <div className="px-5 lg:px-8 py-6 lg:py-8">
        <div className={inner}>
          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
            <div>
              <h2 className="text-2xl font-semibold tracking-tight">{title}</h2>
              {description && (
                <p className="mt-1 text-sm text-muted-foreground max-w-2xl">
                  {description}
                </p>
              )}
            </div>
            {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
          </div>
          <div className="mt-6">{children}</div>
        </div>
      </div>
    </div>
  );
}
