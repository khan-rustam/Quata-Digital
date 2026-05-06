"use client";

import * as React from "react";
import { Loader2, KeyRound, User as UserIcon, Bell, ShieldCheck, ShieldOff, ShieldAlert, Copy } from "lucide-react";
import { PageShell } from "@/components/admin/page-shell";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { PasswordInput } from "@/components/ui/password-input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/lib/auth";
import { useApi, useApiAction } from "@/lib/use-api";
import { useToast } from "@/components/ui/toast";

export default function SettingsPage() {
  const { refresh } = useAuth();
  return (
    <PageShell
      title="Settings"
      description="Update your profile, change your password, manage 2FA and notification preferences."
      narrow
    >
      <Tabs defaultValue="profile">
        <TabsList>
          <TabsTrigger value="profile">
            <UserIcon className="h-3.5 w-3.5" /> Profile
          </TabsTrigger>
          <TabsTrigger value="password">
            <KeyRound className="h-3.5 w-3.5" /> Password
          </TabsTrigger>
          <TabsTrigger value="2fa">
            <ShieldCheck className="h-3.5 w-3.5" /> Two-factor
          </TabsTrigger>
          <TabsTrigger value="notifications">
            <Bell className="h-3.5 w-3.5" /> Notifications
          </TabsTrigger>
        </TabsList>
        <TabsContent value="profile"><ProfileForm onSaved={refresh} /></TabsContent>
        <TabsContent value="password"><PasswordForm /></TabsContent>
        <TabsContent value="2fa"><TwoFactorPanel /></TabsContent>
        <TabsContent value="notifications"><NotificationsForm /></TabsContent>
      </Tabs>
    </PageShell>
  );
}

function ProfileForm({ onSaved }: { onSaved: () => void }) {
  const { user } = useAuth();
  const action = useApiAction();
  const toast = useToast();
  const [submitting, setSubmitting] = React.useState(false);

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setSubmitting(true);
    const data = Object.fromEntries(new FormData(e.currentTarget).entries());
    try {
      await action("/me", { method: "PATCH", body: JSON.stringify(data) });
      toast.success("Profile updated");
      onSaved();
    } catch (err) {
      toast.error("Couldn't save", err instanceof Error ? err.message : "Try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="rounded-2xl border border-border bg-card p-6 ring-soft grid gap-4 max-w-xl">
      <div className="grid gap-2">
        <Label htmlFor="full_name">Full name</Label>
        <Input id="full_name" name="full_name" defaultValue={user?.full_name} required placeholder="Jane Doe" autoComplete="name" />
      </div>
      <div className="grid gap-2">
        <Label htmlFor="email">Email</Label>
        <Input id="email" name="email" type="email" defaultValue={user?.email} disabled />
        <div className="text-xs text-muted-foreground">Email is used for sign-in and is managed by your admin.</div>
      </div>
      <div className="grid gap-2">
        <Label htmlFor="job_title">Job title</Label>
        <Input id="job_title" name="job_title" placeholder="What do you do at QUATA?" />
      </div>
      <div className="grid gap-2">
        <Label htmlFor="phone">Phone</Label>
        <Input id="phone" name="phone" type="tel" placeholder="+237 6 7000 0000" autoComplete="tel" />
      </div>
      <div>
        <Button type="submit" disabled={submitting}>
          {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
          Save changes
        </Button>
      </div>
    </form>
  );
}

function PasswordForm() {
  const action = useApiAction();
  const toast = useToast();
  const [submitting, setSubmitting] = React.useState(false);

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    const current = String(form.get("current") || "");
    const next = String(form.get("next") || "");
    const confirm = String(form.get("confirm") || "");
    if (next.length < 10) {
      toast.error("Too short", "Use at least 10 characters.");
      return;
    }
    if (next !== confirm) {
      toast.error("Doesn't match", "New password and confirmation don't match.");
      return;
    }
    setSubmitting(true);
    try {
      await action("/me/password", {
        method: "POST",
        body: JSON.stringify({ current_password: current, new_password: next }),
      });
      toast.success("Password updated", "Use your new password next time you sign in.");
      (e.target as HTMLFormElement).reset();
    } catch (err) {
      toast.error("Couldn't change", err instanceof Error ? err.message : "Try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="rounded-2xl border border-border bg-card p-6 ring-soft grid gap-4 max-w-xl">
      <div className="grid gap-2">
        <Label htmlFor="current">Current password</Label>
        <PasswordInput id="current" name="current" required autoComplete="current-password" />
      </div>
      <div className="grid gap-2">
        <Label htmlFor="next">New password</Label>
        <PasswordInput id="next" name="next" required minLength={10} autoComplete="new-password" />
        <div className="text-xs text-muted-foreground">At least 10 characters. A passphrase or password manager is best.</div>
      </div>
      <div className="grid gap-2">
        <Label htmlFor="confirm">Confirm new password</Label>
        <PasswordInput id="confirm" name="confirm" required minLength={10} autoComplete="new-password" />
      </div>
      <div>
        <Button type="submit" disabled={submitting}>
          {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
          Change password
        </Button>
      </div>
    </form>
  );
}

function TwoFactorPanel() {
  const { refresh } = useAuth();
  const action = useApiAction();
  const toast = useToast();
  const [enrol, setEnrol] = React.useState<{ qr_data_url: string; secret: string } | null>(null);
  const [recovery, setRecovery] = React.useState<string[] | null>(null);
  const [submitting, setSubmitting] = React.useState(false);

  async function startEnrol(password: string) {
    setSubmitting(true);
    try {
      const r = await action<{ secret: string; otpauth_uri: string; qr_data_url: string }>(
        "/me/2fa/enrol",
        { method: "POST", body: JSON.stringify({ password }) }
      );
      setEnrol({ qr_data_url: r.qr_data_url, secret: r.secret });
    } catch (err) {
      toast.error("Couldn't start", err instanceof Error ? err.message : "Try again.");
    } finally {
      setSubmitting(false);
    }
  }

  async function verify(code: string) {
    setSubmitting(true);
    try {
      const r = await action<{ enabled: true; recovery_codes: string[] }>("/me/2fa/verify", {
        method: "POST",
        body: JSON.stringify({ code }),
      });
      setEnrol(null);
      setRecovery(r.recovery_codes);
      toast.success("2FA enabled", "Save your recovery codes in a safe place.");
      refresh();
    } catch (err) {
      toast.error("Invalid code", err instanceof Error ? err.message : "Try again.");
    } finally {
      setSubmitting(false);
    }
  }

  async function disable(password: string) {
    setSubmitting(true);
    try {
      await action("/me/2fa/disable", { method: "POST", body: JSON.stringify({ password }) });
      toast.success("2FA disabled");
      setEnrol(null);
      setRecovery(null);
      refresh();
    } catch (err) {
      toast.error("Couldn't disable", err instanceof Error ? err.message : "Try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="grid gap-4 max-w-2xl">
      <div className="rounded-2xl border border-border bg-card p-6 ring-soft">
        <div className="flex items-center gap-3">
          <div className="inline-flex h-10 w-10 items-center justify-center rounded-xl bg-brand-soft text-primary">
            <ShieldCheck className="h-5 w-5" />
          </div>
          <div>
            <div className="text-base font-semibold">Authenticator app (TOTP)</div>
            <div className="text-xs text-muted-foreground">
              Use an app like 1Password, Authy or Google Authenticator.
            </div>
          </div>
        </div>

        {!enrol && !recovery && (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              const pw = String(new FormData(e.currentTarget).get("password") || "");
              startEnrol(pw);
            }}
            className="mt-5 grid gap-3 sm:grid-cols-[1fr_auto] items-end"
          >
            <div className="grid gap-2">
              <Label htmlFor="enrolPassword">Confirm password to begin enrolment</Label>
              <PasswordInput id="enrolPassword" name="password" required autoComplete="current-password" />
            </div>
            <Button type="submit" disabled={submitting}>
              {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
              Begin enrolment
            </Button>
          </form>
        )}

        {enrol && (
          <div className="mt-5 grid gap-4 sm:grid-cols-[180px_1fr]">
            {/* eslint-disable-next-line @next/next/no-img-element -- inline data: URL from server, not an optimisable asset. */}
            <img
              src={enrol.qr_data_url}
              alt="2FA QR code"
              className="rounded-xl border border-border bg-white p-2 w-[180px] h-[180px]"
            />
            <div>
              <div className="text-sm">Scan the QR code with your authenticator app.</div>
              <div className="mt-2 text-xs text-muted-foreground">Or enter this secret manually:</div>
              <div className="mt-1 inline-flex items-center gap-2 rounded-lg border border-border bg-surface px-3 py-2 text-xs font-mono">
                {enrol.secret}
                <button
                  type="button"
                  className="text-muted-foreground hover:text-foreground"
                  onClick={() => navigator.clipboard.writeText(enrol.secret).then(() => toast.success("Copied"))}
                >
                  <Copy className="h-3.5 w-3.5" />
                </button>
              </div>
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  const code = String(new FormData(e.currentTarget).get("code") || "");
                  verify(code);
                }}
                className="mt-4 grid gap-2 sm:grid-cols-[1fr_auto] items-end"
              >
                <div className="grid gap-1.5">
                  <Label htmlFor="verifyCode" className="text-xs">6-digit code</Label>
                  <Input id="verifyCode" name="code" inputMode="numeric" autoComplete="one-time-code" required placeholder="123 456" />
                </div>
                <Button type="submit" disabled={submitting}>
                  {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                  Verify
                </Button>
              </form>
            </div>
          </div>
        )}

        {recovery && (
          <div className="mt-5 rounded-xl border border-amber-200 bg-amber-50 p-4">
            <div className="flex items-center gap-2 text-sm font-semibold text-amber-900">
              <ShieldAlert className="h-4 w-4" />
              Save these recovery codes
            </div>
            <p className="mt-1 text-xs text-amber-900/80">
              Each code works once if you lose your authenticator. Store them in a password manager — they won&apos;t be shown again.
            </p>
            <div className="mt-3 grid grid-cols-2 sm:grid-cols-4 gap-2">
              {recovery.map((c) => (
                <code key={c} className="rounded-md bg-white border border-amber-200 px-2 py-1 text-xs font-mono">
                  {c}
                </code>
              ))}
            </div>
            <Button
              variant="outline"
              size="sm"
              className="mt-3"
              onClick={() => navigator.clipboard.writeText(recovery.join("\n")).then(() => toast.success("Codes copied"))}
            >
              <Copy className="h-3.5 w-3.5" /> Copy all
            </Button>
          </div>
        )}
      </div>

      <div className="rounded-2xl border border-border bg-card p-6 ring-soft">
        <div className="flex items-center gap-3">
          <div className="inline-flex h-10 w-10 items-center justify-center rounded-xl bg-rose-100 text-rose-700">
            <ShieldOff className="h-5 w-5" />
          </div>
          <div>
            <div className="text-base font-semibold">Disable two-factor</div>
            <div className="text-xs text-muted-foreground">Confirm your password to remove 2FA from your account.</div>
          </div>
        </div>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            const pw = String(new FormData(e.currentTarget).get("password") || "");
            disable(pw);
          }}
          className="mt-4 grid gap-3 sm:grid-cols-[1fr_auto] items-end"
        >
          <div className="grid gap-2">
            <Label htmlFor="disablePassword">Password</Label>
            <PasswordInput id="disablePassword" name="password" required autoComplete="current-password" />
          </div>
          <Button type="submit" variant="destructive" disabled={submitting}>
            Disable
          </Button>
        </form>
      </div>
    </div>
  );
}

function NotificationsForm() {
  const action = useApiAction();
  const toast = useToast();
  const { data, loading, refresh } = useApi<Record<string, boolean>>("/me/notifications");
  const [prefs, setPrefs] = React.useState<Record<string, boolean>>({});
  const [submitting, setSubmitting] = React.useState(false);

  React.useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- hydrating editable form state from fetched data once it arrives.
    if (data) setPrefs(data);
  }, [data]);

  async function save() {
    setSubmitting(true);
    try {
      await action("/me/notifications", { method: "PUT", body: JSON.stringify(prefs) });
      toast.success("Preferences saved");
      refresh();
    } catch (err) {
      toast.error("Couldn't save", err instanceof Error ? err.message : "Try again.");
    } finally {
      setSubmitting(false);
    }
  }

  const items: { key: string; label: string; desc: string }[] = [
    { key: "partner_requests", label: "Partner requests", desc: "New partner submissions." },
    { key: "job_applications", label: "Job applications", desc: "New applicants for any job." },
    { key: "leave_decisions", label: "Leave decisions", desc: "Approvals and rejections affecting you." },
    { key: "contact_messages", label: "Contact messages", desc: "Public contact form submissions." },
    { key: "weekly_digest", label: "Weekly digest", desc: "A Monday-morning summary of activity." },
    { key: "system_alerts", label: "System alerts", desc: "Critical incidents and security alerts." },
  ];

  if (loading) {
    return <div className="text-sm text-muted-foreground">Loading…</div>;
  }

  return (
    <div className="rounded-2xl border border-border bg-card p-6 ring-soft grid gap-4 max-w-xl">
      <ul className="grid gap-2">
        {items.map((it) => (
          <li
            key={it.key}
            className="flex items-center justify-between gap-4 rounded-xl border border-border bg-surface px-4 py-3"
          >
            <div>
              <div className="text-sm font-medium">{it.label}</div>
              <div className="text-xs text-muted-foreground">{it.desc}</div>
            </div>
            <label className="inline-flex items-center cursor-pointer">
              <input
                type="checkbox"
                className="sr-only peer"
                checked={!!prefs[it.key]}
                onChange={(e) => setPrefs({ ...prefs, [it.key]: e.target.checked })}
              />
              <span className="relative inline-block h-5 w-9 rounded-full bg-secondary transition peer-checked:bg-primary">
                <span className="absolute top-0.5 left-0.5 h-4 w-4 rounded-full bg-white shadow-sm transition peer-checked:translate-x-4" />
              </span>
            </label>
          </li>
        ))}
      </ul>
      <div>
        <Button onClick={save} disabled={submitting}>
          {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
          Save preferences
        </Button>
      </div>
    </div>
  );
}
