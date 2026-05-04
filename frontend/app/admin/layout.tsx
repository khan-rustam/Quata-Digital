"use client";

import { usePathname } from "next/navigation";
import { AuthProvider } from "@/lib/auth";
import { AdminSidebar } from "@/components/admin/sidebar";
import { ToastProvider } from "@/components/ui/toast";
import { CommandPalette } from "@/components/admin/command-palette";

export default function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const isPublic =
    pathname === "/admin/login" ||
    pathname === "/admin/forgot-password" ||
    pathname === "/admin/reset-password";
  // Forced-gate pages render full-screen so users can't navigate around them.
  const isGate =
    pathname === "/admin/setup-password" || pathname === "/admin/setup-2fa";

  return (
    <AuthProvider>
      <ToastProvider>
        {isPublic || isGate ? (
          children
        ) : (
          <div className="flex min-h-svh">
            <AdminSidebar />
            {children}
            <CommandPalette />
          </div>
        )}
      </ToastProvider>
    </AuthProvider>
  );
}
