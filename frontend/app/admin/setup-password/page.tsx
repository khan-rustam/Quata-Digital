"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { Loader2, KeyRound, LogOut } from "lucide-react";
import { Button } from "@/components/ui/button";
import { PasswordInput } from "@/components/ui/password-input";
import { Label } from "@/components/ui/label";
import { Logo } from "@/components/site/logo";
import { useApiAction } from "@/lib/use-api";
import { useAuth } from "@/lib/auth";
import { useToast } from "@/components/ui/toast";

export default function SetupPasswordPage() {
  const { user, refresh, signOut, loading } = useAuth();
  const action = useApiAction();
  const router = useRouter();
  const toast = useToast();
  const [submitting, setSubmitting] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  // If the gate has already been cleared, get out of the way.
  React.useEffect(() => {
    if (!loading && user && !user.must_reset_password) {
      router.replace("/admin/overview");
    }
  }, [user, loading, router]);

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    const data = new FormData(e.currentTarget);
    const current = String(data.get("current_password") || "");
    const next = String(data.get("new_password") || "");
    const confirm = String(data.get("confirm_password") || "");
    if (next.length < 10) {
      setError("New password must be at least 10 characters.");
      return;
    }
    if (next !== confirm) {
      setError("Passwords don't match.");
      return;
    }
    setSubmitting(true);
    try {
      await action("/me/password", {
        method: "POST",
        body: JSON.stringify({ current_password: current, new_password: next }),
      });
      await refresh();
      toast.success("Password updated");
      router.replace("/admin/overview");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't update password.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-svh flex items-center justify-center bg-background p-6">
      <div className="w-full max-w-md">
        <Logo />
        <div className="mt-6 inline-flex h-10 w-10 items-center justify-center rounded-2xl bg-brand-soft text-primary">
          <KeyRound className="h-5 w-5" />
        </div>
        <h1 className="mt-4 text-2xl font-semibold tracking-tight">
          Set a new password
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          You&apos;re using a temporary password. Choose a new one before continuing.
        </p>

        <form onSubmit={onSubmit} className="mt-8 grid gap-4">
          <div className="grid gap-2">
            <Label htmlFor="current_password">Current password</Label>
            <PasswordInput
              id="current_password"
              name="current_password"
              autoComplete="current-password"
              required
              autoFocus
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="new_password">New password</Label>
            <PasswordInput
              id="new_password"
              name="new_password"
              autoComplete="new-password"
              minLength={10}
              required
            />
            <div className="text-xs text-muted-foreground">
              At least 10 characters. Use a passphrase you don&apos;t reuse anywhere else.
            </div>
          </div>
          <div className="grid gap-2">
            <Label htmlFor="confirm_password">Confirm new password</Label>
            <PasswordInput
              id="confirm_password"
              name="confirm_password"
              autoComplete="new-password"
              minLength={10}
              required
            />
          </div>
          {error && (
            <div className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-900">
              {error}
            </div>
          )}
          <Button type="submit" disabled={submitting} size="lg">
            {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
            Update password and continue
          </Button>
        </form>

        <button
          type="button"
          onClick={signOut}
          className="mt-6 inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground"
        >
          <LogOut className="h-3 w-3" /> Sign out instead
        </button>
      </div>
    </div>
  );
}
