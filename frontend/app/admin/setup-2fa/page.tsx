"use client";

import * as React from "react";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { Loader2, ShieldCheck, LogOut, Copy, CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Logo } from "@/components/site/logo";
import { useApiAction } from "@/lib/use-api";
import { useAuth } from "@/lib/auth";
import { useToast } from "@/components/ui/toast";

type EnrolResponse = {
  secret: string;
  otpauth_uri: string;
  qr_data_url: string;
};

export default function Setup2faPage() {
  const { user, refresh, signOut, loading } = useAuth();
  const action = useApiAction();
  const router = useRouter();
  const toast = useToast();
  const [step, setStep] = React.useState<"password" | "verify" | "done">("password");
  const [enrol, setEnrol] = React.useState<EnrolResponse | null>(null);
  const [recoveryCodes, setRecoveryCodes] = React.useState<string[] | null>(null);
  const [submitting, setSubmitting] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [copied, setCopied] = React.useState(false);

  // Already satisfied — get out of the way.
  React.useEffect(() => {
    if (loading) return;
    if (!user) return;
    if (!user.requires_2fa || user.has_2fa) {
      router.replace("/admin/overview");
    }
  }, [user, loading, router]);

  async function onPassword(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    const data = new FormData(e.currentTarget);
    try {
      const res = await action<EnrolResponse>("/me/2fa/enrol", {
        method: "POST",
        body: JSON.stringify({ password: String(data.get("password") || "") }),
      });
      setEnrol(res);
      setStep("verify");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't start enrolment.");
    } finally {
      setSubmitting(false);
    }
  }

  async function onVerify(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    const data = new FormData(e.currentTarget);
    try {
      const res = await action<{ enabled: true; recovery_codes: string[] }>(
        "/me/2fa/verify",
        {
          method: "POST",
          body: JSON.stringify({ code: String(data.get("code") || "").trim() }),
        }
      );
      setRecoveryCodes(res.recovery_codes);
      setStep("done");
      toast.success("Two-factor authentication enabled");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Invalid code. Try again.");
    } finally {
      setSubmitting(false);
    }
  }

  async function onContinue() {
    await refresh();
    router.replace("/admin/overview");
  }

  function copyRecovery() {
    if (!recoveryCodes) return;
    navigator.clipboard.writeText(recoveryCodes.join("\n"));
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  return (
    <div className="min-h-svh flex items-center justify-center bg-background p-6">
      <div className="w-full max-w-md">
        <Logo />
        <div className="mt-6 inline-flex h-10 w-10 items-center justify-center rounded-2xl bg-brand-soft text-primary">
          <ShieldCheck className="h-5 w-5" />
        </div>
        <h1 className="mt-4 text-2xl font-semibold tracking-tight">
          Enable two-factor authentication
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Your role requires 2FA before you can use the admin console. This is a one-time setup.
        </p>

        {step === "password" && (
          <form onSubmit={onPassword} className="mt-8 grid gap-4">
            <div className="grid gap-2">
              <Label htmlFor="password">Confirm your password</Label>
              <Input
                id="password"
                name="password"
                type="password"
                autoComplete="current-password"
                required
                autoFocus
              />
            </div>
            {error && (
              <div className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-900">
                {error}
              </div>
            )}
            <Button type="submit" disabled={submitting} size="lg">
              {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
              Continue
            </Button>
          </form>
        )}

        {step === "verify" && enrol && (
          <div className="mt-8 grid gap-4">
            <div className="rounded-2xl border border-border bg-surface-soft p-4">
              <div className="text-sm font-medium">1. Scan in your authenticator</div>
              <div className="text-xs text-muted-foreground mt-1">
                Use Google Authenticator, 1Password, Authy or any TOTP app.
              </div>
              <div className="mt-3 flex justify-center">
                <Image
                  src={enrol.qr_data_url}
                  alt="Scan this QR with your authenticator app"
                  width={180}
                  height={180}
                  unoptimized
                />
              </div>
              <div className="mt-3 text-xs text-muted-foreground text-center">
                Or enter this secret manually:
              </div>
              <div className="mt-1 font-mono text-xs text-center break-all">
                {enrol.secret}
              </div>
            </div>
            <form onSubmit={onVerify} className="grid gap-3">
              <Label htmlFor="code">2. Enter the 6-digit code</Label>
              <Input
                id="code"
                name="code"
                inputMode="numeric"
                autoComplete="one-time-code"
                placeholder="123 456"
                required
                autoFocus
              />
              {error && (
                <div className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-900">
                  {error}
                </div>
              )}
              <Button type="submit" disabled={submitting} size="lg">
                {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                Verify and enable
              </Button>
            </form>
          </div>
        )}

        {step === "done" && recoveryCodes && (
          <div className="mt-8 grid gap-4">
            <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-4 text-emerald-900">
              <div className="flex items-center gap-2 text-sm font-semibold">
                <CheckCircle2 className="h-4 w-4" /> 2FA enabled
              </div>
              <div className="mt-1 text-xs">
                Save these one-time recovery codes somewhere safe. You&apos;ll need
                them if you ever lose access to your authenticator app.
              </div>
            </div>
            <div className="rounded-2xl border border-border bg-surface-soft p-4">
              <div className="grid grid-cols-2 gap-2 font-mono text-xs">
                {recoveryCodes.map((c) => (
                  <div key={c} className="rounded border border-border bg-surface px-2 py-1">
                    {c}
                  </div>
                ))}
              </div>
              <button
                type="button"
                onClick={copyRecovery}
                className="mt-3 inline-flex items-center gap-1 text-xs text-primary hover:underline"
              >
                <Copy className="h-3 w-3" />
                {copied ? "Copied" : "Copy all"}
              </button>
            </div>
            <Button onClick={onContinue} size="lg">
              I&apos;ve saved my recovery codes — continue
            </Button>
          </div>
        )}

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
