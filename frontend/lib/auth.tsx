"use client";

import * as React from "react";
import { useRouter, usePathname } from "next/navigation";
import { api } from "@/lib/api";

const TOKEN_KEY = "quata_token";

const PUBLIC_ADMIN_PATHS = new Set([
  "/admin/login",
  "/admin/forgot-password",
  "/admin/reset-password",
]);

export type SessionUser = {
  id: number;
  email: string;
  full_name: string;
  role: string;
  department: string | null;
  permissions: string[];
  requires_2fa: boolean;
  has_2fa: boolean;
  must_reset_password: boolean;
};

export type SignInOptions = {
  totp_code?: string;
  recovery_code?: string;
};

export type SignInResult =
  | { kind: "ok" }
  | { kind: "two_factor_required" };

export type AuthState = {
  user: SessionUser | null;
  token: string | null;
  loading: boolean;
  signIn: (email: string, password: string, opts?: SignInOptions) => Promise<SignInResult>;
  signOut: () => void;
  refresh: () => Promise<void>;
  hasPermission: (perm: string) => boolean;
};

const AuthContext = React.createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = React.useState<SessionUser | null>(null);
  const [token, setToken] = React.useState<string | null>(null);
  const [loading, setLoading] = React.useState(true);
  const router = useRouter();
  const pathname = usePathname();

  React.useEffect(() => {
    const t = localStorage.getItem(TOKEN_KEY);
    if (!t) {
      setLoading(false);
      return;
    }
    setToken(t);
    api<SessionUser>("/auth/me", { token: t })
      .then(setUser)
      .catch(() => {
        localStorage.removeItem(TOKEN_KEY);
        setToken(null);
      })
      .finally(() => setLoading(false));
  }, []);

  const signIn = React.useCallback<AuthState["signIn"]>(
    async (email, password, opts = {}) => {
      const res = await api<
        { access_token: string; token_type?: string } | { two_factor_required: true }
      >("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password, ...opts }),
      });

      if ("two_factor_required" in res && res.two_factor_required) {
        return { kind: "two_factor_required" };
      }
      const access = (res as { access_token: string }).access_token;
      localStorage.setItem(TOKEN_KEY, access);
      setToken(access);
      const me = await api<SessionUser>("/auth/me", { token: access });
      setUser(me);
      router.push("/admin/overview");
      return { kind: "ok" };
    },
    [router]
  );

  const signOut = React.useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    setUser(null);
    setToken(null);
    router.push("/admin/login");
  }, [router]);

  const refresh = React.useCallback(async () => {
    if (!token) return;
    const me = await api<SessionUser>("/auth/me", { token });
    setUser(me);
  }, [token]);

  const hasPermission = React.useCallback(
    (perm: string) => {
      if (!user) return false;
      if (user.role === "super_admin") return true;
      return user.permissions.includes(perm);
    },
    [user]
  );

  React.useEffect(() => {
    if (loading) return;
    if (!user && pathname.startsWith("/admin") && !PUBLIC_ADMIN_PATHS.has(pathname)) {
      router.replace("/admin/login");
      return;
    }
    if (!user) return;
    // Outstanding gates take priority over any other admin page.
    if (user.must_reset_password && pathname !== "/admin/setup-password") {
      router.replace("/admin/setup-password");
      return;
    }
    if (
      user.requires_2fa &&
      !user.has_2fa &&
      pathname !== "/admin/setup-2fa" &&
      pathname !== "/admin/setup-password"
    ) {
      router.replace("/admin/setup-2fa");
      return;
    }
  }, [user, loading, pathname, router]);

  return (
    <AuthContext.Provider
      value={{ user, token, loading, signIn, signOut, refresh, hasPermission }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = React.useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
