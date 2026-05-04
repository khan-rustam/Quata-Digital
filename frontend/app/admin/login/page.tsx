"use client";

import * as React from "react";
import Link from "next/link";
import { Loader2, ShieldCheck, ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Logo } from "@/components/site/logo";
import { useAuth } from "@/lib/auth";

export default function AdminLoginPage() {
  const { signIn } = useAuth();
  const [submitting, setSubmitting] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [step, setStep] = React.useState<"credentials" | "totp">("credentials");
  const [creds, setCreds] = React.useState<{ email: string; password: string }>({
    email: "",
    password: "",
  });
  const [useRecovery, setUseRecovery] = React.useState(false);

  async function onCredentials(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    const data = new FormData(e.currentTarget);
    const email = String(data.get("email"));
    const password = String(data.get("password"));
    try {
      const res = await signIn(email, password);
      if (res.kind === "two_factor_required") {
        setCreds({ email, password });
        setStep("totp");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign-in failed");
    } finally {
      setSubmitting(false);
    }
  }

  async function onTotp(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    const data = new FormData(e.currentTarget);
    const code = String(data.get("code") || "").trim();
    try {
      await signIn(
        creds.email,
        creds.password,
        useRecovery ? { recovery_code: code } : { totp_code: code }
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign-in failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-svh grid lg:grid-cols-2 bg-background">
      <div className="hidden lg:flex flex-col justify-between p-10 bg-ink text-white relative overflow-hidden">
        <div className="absolute inset-0 dot-grid opacity-20" />
        <div
          className="absolute -top-32 -left-32 h-96 w-96 rounded-full opacity-30 blur-3xl"
          style={{
            background:
              "radial-gradient(closest-side, rgba(52,211,167,0.7), transparent)",
          }}
        />
        <Logo variant="light" />
        <div className="relative z-10">
          <div className="text-3xl md:text-4xl font-semibold tracking-tight max-w-md">
            The connected operating system for Africa&apos;s next decade.
          </div>
          <p className="mt-4 text-white/70 max-w-md">
            One ecosystem. Seven products. One internal cockpit.
          </p>
        </div>
        <div className="text-xs text-white/50">
          © {new Date().getFullYear()} QUATA Digital
        </div>
      </div>

      <div className="flex items-center justify-center p-6 md:p-10">
        <div className="w-full max-w-md">
          <Logo />

          {step === "credentials" ? (
            <>
              <h1 className="mt-6 text-2xl font-semibold tracking-tight">
                Sign in to QUATA Admin
              </h1>
              <p className="mt-1 text-sm text-muted-foreground">
                Use your work email and password.
              </p>

              <form onSubmit={onCredentials} className="mt-8 grid gap-4">
                <div className="grid gap-2">
                  <Label htmlFor="email">Work email</Label>
                  <Input id="email" name="email" type="email" placeholder="you@quata.digital" required autoFocus />
                </div>
                <div className="grid gap-2">
                  <div className="flex items-center justify-between">
                    <Label htmlFor="password">Password</Label>
                    <Link
                      href="/admin/forgot-password"
                      className="text-xs text-primary hover:underline"
                    >
                      Forgot password?
                    </Link>
                  </div>
                  <Input id="password" name="password" type="password" required placeholder="••••••••" />
                </div>
                {error && (
                  <div className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-900">
                    {error}
                  </div>
                )}
                <Button type="submit" disabled={submitting} size="lg">
                  {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                  Sign in
                </Button>
              </form>

              {process.env.NODE_ENV === "development" && (
                <div className="mt-6 rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900">
                  <div className="font-semibold">Dev seed credentials</div>
                  <div className="mt-1">
                    <span className="font-mono">admin@quatadigital.com</span> /{" "}
                    <span className="font-mono">ChangeMe!2026</span>
                  </div>
                </div>
              )}
            </>
          ) : (
            <>
              <div className="mt-6 inline-flex h-10 w-10 items-center justify-center rounded-2xl bg-brand-soft text-primary">
                <ShieldCheck className="h-5 w-5" />
              </div>
              <h1 className="mt-4 text-2xl font-semibold tracking-tight">
                Two-factor authentication
              </h1>
              <p className="mt-1 text-sm text-muted-foreground">
                {useRecovery
                  ? "Enter one of your one-time recovery codes."
                  : "Enter the 6-digit code from your authenticator app."}
              </p>

              <form onSubmit={onTotp} className="mt-8 grid gap-4">
                <div className="grid gap-2">
                  <Label htmlFor="code">{useRecovery ? "Recovery code" : "6-digit code"}</Label>
                  <Input
                    id="code"
                    name="code"
                    autoFocus
                    autoComplete="one-time-code"
                    inputMode={useRecovery ? "text" : "numeric"}
                    placeholder={useRecovery ? "ABCDE-12345" : "123 456"}
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
                  Verify and sign in
                </Button>
                <button
                  type="button"
                  onClick={() => setUseRecovery((v) => !v)}
                  className="text-xs text-muted-foreground hover:text-foreground text-left"
                >
                  {useRecovery ? "Use authenticator code instead" : "I lost my device — use a recovery code"}
                </button>
                <button
                  type="button"
                  onClick={() => { setStep("credentials"); setError(null); }}
                  className="text-xs text-muted-foreground hover:text-foreground inline-flex items-center gap-1"
                >
                  <ArrowLeft className="h-3 w-3" /> Back
                </button>
              </form>
            </>
          )}

          <div className="mt-8 text-sm">
            <Link href="/" className="text-muted-foreground hover:text-foreground">
              ← Back to site
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
