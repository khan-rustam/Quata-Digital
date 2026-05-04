"use client";

import * as React from "react";
import Link from "next/link";
import { useSearchParams, useRouter } from "next/navigation";
import { CheckCircle2, KeyRound, Loader2, AlertCircle, ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Logo } from "@/components/site/logo";
import { api } from "@/lib/api";

export default function ResetPasswordClient() {
  const params = useSearchParams();
  const router = useRouter();
  const token = params.get("token") ?? "";
  const [submitting, setSubmitting] = React.useState(false);
  const [done, setDone] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    const form = new FormData(e.currentTarget);
    const next = String(form.get("next") ?? "");
    const confirm = String(form.get("confirm") ?? "");
    if (next.length < 10) {
      setError("Use at least 10 characters.");
      return;
    }
    if (next !== confirm) {
      setError("Passwords don't match.");
      return;
    }
    setSubmitting(true);
    try {
      await api("/auth/reset-password", {
        method: "POST",
        body: JSON.stringify({ token, new_password: next }),
      });
      setDone(true);
      setTimeout(() => router.push("/admin/login"), 2500);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Reset failed.");
    } finally {
      setSubmitting(false);
    }
  }

  if (!token) {
    return (
      <div className="min-h-svh bg-background flex flex-col">
        <header className="container-page py-6"><Logo /></header>
        <main className="flex-1 container-page flex items-center justify-center py-12">
          <div className="max-w-md text-center">
            <div className="mx-auto inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-rose-100 text-rose-700">
              <AlertCircle className="h-5 w-5" />
            </div>
            <h1 className="mt-5 text-2xl font-semibold tracking-tight">Reset link missing</h1>
            <p className="mt-2 text-sm text-muted-foreground">
              The reset link is invalid or has been opened without a token.
            </p>
            <Button asChild className="mt-6">
              <Link href="/admin/forgot-password">Request a new link</Link>
            </Button>
          </div>
        </main>
      </div>
    );
  }

  return (
    <div className="min-h-svh bg-background flex flex-col">
      <header className="container-page py-6"><Logo /></header>
      <main className="flex-1 container-page flex items-center justify-center py-12">
        <div className="w-full max-w-md">
          <div className="inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-brand-soft text-primary">
            <KeyRound className="h-5 w-5" />
          </div>
          <h1 className="mt-5 text-2xl font-semibold tracking-tight">Choose a new password</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            Use at least 10 characters. A passphrase or password manager is best.
          </p>

          {done ? (
            <div className="mt-8 rounded-2xl border border-emerald-200 bg-emerald-50 p-6">
              <CheckCircle2 className="h-5 w-5 text-emerald-700" />
              <div className="mt-3 text-sm font-semibold text-emerald-900">Password updated.</div>
              <p className="mt-1 text-sm text-emerald-900/80">Redirecting you to sign in…</p>
              <Button variant="outline" className="mt-4" asChild>
                <Link href="/admin/login">
                  Sign in <ArrowRight className="h-4 w-4" />
                </Link>
              </Button>
            </div>
          ) : (
            <form onSubmit={onSubmit} className="mt-8 grid gap-4">
              <div className="grid gap-2">
                <Label htmlFor="next">New password</Label>
                <Input id="next" name="next" type="password" required minLength={10} autoFocus />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="confirm">Confirm new password</Label>
                <Input id="confirm" name="confirm" type="password" required minLength={10} />
              </div>
              {error && (
                <div className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-900">
                  {error}
                </div>
              )}
              <Button type="submit" disabled={submitting} size="lg">
                {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                Update password
              </Button>
            </form>
          )}
        </div>
      </main>
    </div>
  );
}
