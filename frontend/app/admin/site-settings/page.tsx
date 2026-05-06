"use client";

import * as React from "react";
import {
  Loader2,
  Plug,
  Phone,
  Share2,
  ToggleLeft,
  Save,
  RotateCcw,
  Lock,
  Eye,
  EyeOff,
  AlertTriangle,
  Mail,
  CheckCircle2,
  XCircle,
} from "lucide-react";

import { PageShell } from "@/components/admin/page-shell";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useApi, useApiAction } from "@/lib/use-api";
import { useToast } from "@/components/ui/toast";

type SettingItem = {
  key: string;
  value: string | null;
  group: string;
  label: string;
  description: string | null;
  field_type: string;
  is_secret: boolean;
  sort_order: number;
  has_value: boolean;
};

type ListResponse = {
  items: SettingItem[];
  groups: string[];
};

const GROUP_META: Record<string, { label: string; description: string; icon: React.ComponentType<{ className?: string }> }> = {
  integrations: {
    label: "Integrations",
    description:
      "External service credentials. Pasted here instead of env vars so they can rotate without a redeploy.",
    icon: Plug,
  },
  contact: {
    label: "Contact info",
    description:
      "Public contact details. Read by the marketing footer + contact page. Blank rows are hidden on the site.",
    icon: Phone,
  },
  social: {
    label: "Social",
    description:
      "Public social links. Each one becomes a footer icon when set, hidden when blank.",
    icon: Share2,
  },
  toggles: {
    label: "Toggles",
    description:
      "Site-wide switches. Maintenance mode shows a banner on the public site without affecting the admin.",
    icon: ToggleLeft,
  },
};

const TAB_ORDER = ["integrations", "contact", "social", "toggles"];

export default function SiteSettingsPage() {
  return (
    <PageShell
      title="Site settings"
      description="Runtime configuration for the public site and integrations. Changes apply within ~10 seconds; Sentry DSN changes need a backend restart to take effect."
      requirePermission="settings:manage"
    >
      <SiteSettingsTabs />
    </PageShell>
  );
}

function SiteSettingsTabs() {
  const { data, loading, refresh } = useApi<ListResponse>("/admin/site-settings");
  const tabs = React.useMemo(() => {
    if (!data) return TAB_ORDER;
    const known = new Set(data.groups);
    // Keep canonical order, append any new groups the backend introduces.
    const extras = data.groups.filter((g) => !TAB_ORDER.includes(g));
    return [...TAB_ORDER.filter((g) => known.has(g)), ...extras];
  }, [data]);

  if (loading) {
    return <div className="text-sm text-muted-foreground">Loading…</div>;
  }
  if (!data) {
    return (
      <div className="rounded-2xl border border-rose-200 bg-rose-50 p-6 text-rose-900">
        Couldn&apos;t load settings. Try refreshing the page.
      </div>
    );
  }

  const itemsByGroup: Record<string, SettingItem[]> = {};
  for (const item of data.items) {
    (itemsByGroup[item.group] ||= []).push(item);
  }
  for (const group of Object.keys(itemsByGroup)) {
    itemsByGroup[group].sort(
      (a, b) => a.sort_order - b.sort_order || a.label.localeCompare(b.label),
    );
  }

  const initial = tabs[0] ?? "integrations";

  return (
    <Tabs defaultValue={initial}>
      <TabsList>
        {tabs.map((g) => {
          const meta = GROUP_META[g] ?? { label: g, description: "", icon: ToggleLeft };
          const Icon = meta.icon;
          return (
            <TabsTrigger key={g} value={g}>
              <Icon className="h-3.5 w-3.5" /> {meta.label}
            </TabsTrigger>
          );
        })}
      </TabsList>
      {tabs.map((g) => (
        <TabsContent key={g} value={g}>
          <SettingsGroupForm
            group={g}
            items={itemsByGroup[g] ?? []}
            onSaved={refresh}
          />
        </TabsContent>
      ))}
    </Tabs>
  );
}

function SettingsGroupForm({
  group,
  items,
  onSaved,
}: {
  group: string;
  items: SettingItem[];
  onSaved: () => void;
}) {
  const action = useApiAction();
  const toast = useToast();

  // Local working copy. `null` means "no value" (cleared).
  // For secret fields, undefined means "preserve current server value".
  const [drafts, setDrafts] = React.useState<Record<string, string | null | undefined>>({});
  const [submitting, setSubmitting] = React.useState(false);

  const meta = GROUP_META[group];

  function update(key: string, value: string | null | undefined) {
    setDrafts((d) => ({ ...d, [key]: value }));
  }

  function reset() {
    setDrafts({});
  }

  const dirty = React.useMemo(() => {
    return items.filter((it) => {
      const draft = drafts[it.key];
      if (draft === undefined) return false;
      // Compare to server value; for secrets, server returns null with has_value=true,
      // so any user-typed value (including a clearing empty string) is "dirty".
      const serverValue = it.value ?? "";
      const draftValue = draft ?? "";
      return draftValue !== serverValue;
    });
  }, [drafts, items]);

  async function save() {
    if (dirty.length === 0) return;
    setSubmitting(true);
    try {
      await action("/admin/site-settings/bulk", {
        method: "POST",
        body: JSON.stringify({
          items: dirty.map((it) => ({
            key: it.key,
            // empty string clears the value on the backend
            value: drafts[it.key] === null ? null : drafts[it.key] ?? null,
          })),
        }),
      });
      toast.success(
        "Saved",
        `${dirty.length} setting${dirty.length === 1 ? "" : "s"} updated.`,
      );
      setDrafts({});
      onSaved();
    } catch (err) {
      toast.error("Couldn't save", err instanceof Error ? err.message : "Try again.");
    } finally {
      setSubmitting(false);
    }
  }

  if (items.length === 0) {
    return (
      <div className="rounded-2xl border border-border bg-card p-6 text-sm text-muted-foreground">
        No settings in this group.
      </div>
    );
  }

  return (
    <div className="grid gap-5 max-w-3xl">
      {meta && (
        <div className="rounded-2xl border border-border bg-surface-soft p-5 ring-soft">
          <div className="flex items-start gap-3">
            <div className="inline-flex h-9 w-9 items-center justify-center rounded-xl bg-brand-soft text-primary shrink-0">
              <meta.icon className="h-4 w-4" />
            </div>
            <div>
              <div className="text-sm font-semibold">{meta.label}</div>
              <div className="mt-0.5 text-xs text-muted-foreground">
                {meta.description}
              </div>
            </div>
          </div>
        </div>
      )}

      <div className="rounded-2xl border border-border bg-card p-6 ring-soft grid gap-5">
        {items.map((it) => (
          <SettingField
            key={it.key}
            item={it}
            draft={drafts[it.key]}
            onChange={(v) => update(it.key, v)}
          />
        ))}
      </div>

      {group === "integrations" && (
        <>
          <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-xs text-amber-900 flex items-start gap-2">
            <AlertTriangle className="h-3.5 w-3.5 mt-0.5 shrink-0" />
            <div>
              <strong className="font-semibold">Sentry DSN changes require a backend restart</strong>
              {" "}to take effect — the SDK only initialises once at boot. hCaptcha keys take effect within ~15 seconds.
            </div>
          </div>
          <HCaptchaTestPanel />
          <SentryTestPanel />
          <SmtpTestPanel />
        </>
      )}

      <div className="flex flex-wrap items-center gap-2">
        <Button onClick={save} disabled={submitting || dirty.length === 0}>
          {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
          Save changes
          {dirty.length > 0 && (
            <span className="ml-1 inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-white/15 px-1.5 text-[11px]">
              {dirty.length}
            </span>
          )}
        </Button>
        <Button variant="outline" onClick={reset} disabled={submitting || dirty.length === 0}>
          <RotateCcw className="h-3.5 w-3.5" /> Discard
        </Button>
      </div>
    </div>
  );
}

function SettingField({
  item,
  draft,
  onChange,
}: {
  item: SettingItem;
  draft: string | null | undefined;
  onChange: (value: string | null | undefined) => void;
}) {
  // For secrets with a value already set, we lock the input behind a "Replace"
  // button so admins don't accidentally overwrite a working credential by
  // typing into an empty box.
  const [replacingSecret, setReplacingSecret] = React.useState(false);
  const [revealSecret, setRevealSecret] = React.useState(false);

  const isSecret = item.is_secret;
  const isToggle = item.field_type === "toggle";

  // Effective rendered value.
  // - For secrets we never echo the server value (server returned null when masked).
  // - For non-secret fields, server value seeds the input.
  const effective: string =
    draft === null
      ? ""
      : draft !== undefined
        ? draft
        : item.value ?? "";

  if (isToggle) {
    const isOn = (effective || "").toLowerCase() === "true" || effective === "1";
    return (
      <div className="flex items-start justify-between gap-4">
        <div>
          <Label className="text-sm font-medium">{item.label}</Label>
          {item.description && (
            <div className="mt-1 text-xs text-muted-foreground">{item.description}</div>
          )}
        </div>
        <label className="inline-flex items-center cursor-pointer mt-1">
          <input
            type="checkbox"
            className="sr-only peer"
            checked={isOn}
            onChange={(e) => onChange(e.target.checked ? "true" : "false")}
          />
          <span className="relative inline-block h-5 w-9 rounded-full bg-secondary transition peer-checked:bg-primary">
            <span className="absolute top-0.5 left-0.5 h-4 w-4 rounded-full bg-white shadow-sm transition peer-checked:translate-x-4" />
          </span>
        </label>
      </div>
    );
  }

  const showSecretLock = isSecret && item.has_value && !replacingSecret;

  return (
    <div className="grid gap-2">
      <div className="flex items-center gap-2">
        <Label htmlFor={item.key} className="text-sm font-medium">
          {item.label}
        </Label>
        {isSecret && (
          <span className="inline-flex items-center gap-1 rounded-full bg-secondary px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground">
            <Lock className="h-2.5 w-2.5" /> secret
          </span>
        )}
      </div>
      {item.description && (
        <div className="text-xs text-muted-foreground">{item.description}</div>
      )}

      {showSecretLock ? (
        <div className="flex items-center gap-2 rounded-lg border border-border bg-surface px-3.5 py-2.5 text-sm">
          <span className="font-mono text-muted-foreground">••••••••••••</span>
          <span className="text-xs text-muted-foreground">(set)</span>
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="ml-auto"
            onClick={() => {
              setReplacingSecret(true);
              onChange("");
            }}
          >
            Replace
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => onChange(null)}
          >
            Clear
          </Button>
        </div>
      ) : item.field_type === "textarea" ? (
        <Textarea
          id={item.key}
          value={effective}
          placeholder={placeholderFor(item)}
          onChange={(e) => onChange(e.target.value || null)}
          rows={3}
        />
      ) : (
        <div className="relative">
          <Input
            id={item.key}
            value={effective}
            type={
              isSecret && !revealSecret
                ? "password"
                : htmlInputType(item.field_type)
            }
            inputMode={inputModeFor(item.field_type)}
            placeholder={placeholderFor(item)}
            onChange={(e) => onChange(e.target.value || null)}
            autoComplete={isSecret ? "new-password" : undefined}
          />
          {isSecret && (
            <button
              type="button"
              aria-label={revealSecret ? "Hide value" : "Reveal value"}
              onClick={() => setRevealSecret((v) => !v)}
              className="absolute inset-y-0 right-2 inline-flex items-center text-muted-foreground hover:text-foreground"
            >
              {revealSecret ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
            </button>
          )}
        </div>
      )}
    </div>
  );
}

function htmlInputType(field: string): string {
  switch (field) {
    case "email":
      return "email";
    case "url":
      return "url";
    case "phone":
      return "tel";
    case "number":
      return "number";
    default:
      return "text";
  }
}

function inputModeFor(field: string): React.HTMLAttributes<HTMLInputElement>["inputMode"] {
  switch (field) {
    case "email":
      return "email";
    case "url":
      return "url";
    case "phone":
      return "tel";
    case "number":
      return "numeric";
    default:
      return undefined;
  }
}

function ConnectionTestPanel({
  title,
  description,
  endpoint,
  iconLabel,
}: {
  title: string;
  description: string;
  endpoint: string;
  iconLabel: React.ReactNode;
}) {
  const action = useApiAction();
  const [submitting, setSubmitting] = React.useState(false);
  const [result, setResult] = React.useState<{
    ok: boolean;
    message?: string;
    configured?: boolean;
  } | null>(null);

  async function run() {
    setSubmitting(true);
    setResult(null);
    try {
      const r = await action<{ ok: boolean; message?: string; configured?: boolean }>(
        endpoint,
        { method: "POST", body: JSON.stringify({}) },
      );
      setResult(r);
    } catch (err) {
      setResult({ ok: false, message: err instanceof Error ? err.message : "Network error." });
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="rounded-xl border border-border bg-card p-4 ring-soft grid gap-3">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-2">
          <div className="inline-flex h-8 w-8 items-center justify-center rounded-lg bg-brand-soft text-primary shrink-0">
            {iconLabel}
          </div>
          <div>
            <div className="text-sm font-semibold">{title}</div>
            <div className="text-xs text-muted-foreground">{description}</div>
          </div>
        </div>
        <Button onClick={run} disabled={submitting} size="sm">
          {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
          Test
        </Button>
      </div>
      {result && (
        <div
          className={`rounded-lg border p-3 text-xs flex items-start gap-2 ${
            result.ok
              ? "border-emerald-200 bg-emerald-50 text-emerald-900"
              : "border-rose-200 bg-rose-50 text-rose-900"
          }`}
        >
          {result.ok ? (
            <CheckCircle2 className="h-3.5 w-3.5 mt-0.5 shrink-0" />
          ) : (
            <XCircle className="h-3.5 w-3.5 mt-0.5 shrink-0" />
          )}
          <span>{result.message ?? (result.ok ? "OK" : "Failed.")}</span>
        </div>
      )}
    </div>
  );
}

function HCaptchaTestPanel() {
  return (
    <ConnectionTestPanel
      title="Test hCaptcha keys"
      description="Verify the configured site + secret keys are accepted by hCaptcha."
      endpoint="/admin/site-settings/test-hcaptcha"
      iconLabel={<Plug className="h-3.5 w-3.5" />}
    />
  );
}

function SentryTestPanel() {
  return (
    <ConnectionTestPanel
      title="Test Sentry DSN"
      description="Send a one-off test event to Sentry without restarting the live SDK."
      endpoint="/admin/site-settings/test-sentry"
      iconLabel={<Plug className="h-3.5 w-3.5" />}
    />
  );
}

function SmtpTestPanel() {
  const action = useApiAction();
  const [target, setTarget] = React.useState("");
  const [submitting, setSubmitting] = React.useState(false);
  const [result, setResult] = React.useState<{ ok: boolean; error?: string } | null>(null);

  async function send() {
    setSubmitting(true);
    setResult(null);
    try {
      const r = await action<{ ok: boolean; error?: string; to?: string }>(
        "/admin/site-settings/test-email",
        {
          method: "POST",
          body: JSON.stringify({ to: target.trim() }),
        },
      );
      setResult({ ok: !!r.ok, error: r.error });
    } catch (err) {
      setResult({
        ok: false,
        error: err instanceof Error ? err.message : "Network error.",
      });
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="rounded-xl border border-border bg-card p-4 ring-soft grid gap-3">
      <div className="flex items-start gap-2">
        <div className="inline-flex h-8 w-8 items-center justify-center rounded-lg bg-brand-soft text-primary shrink-0">
          <Mail className="h-3.5 w-3.5" />
        </div>
        <div>
          <div className="text-sm font-semibold">Send a test email</div>
          <div className="text-xs text-muted-foreground">
            Verify that the SMTP backend is reachable and your sender domain is
            verified. The test uses the active configuration in the backend
            (env-vars first, then anything you may have wired through admin).
          </div>
        </div>
      </div>
      <div className="grid gap-2 sm:grid-cols-[1fr_auto] items-end">
        <Input
          type="email"
          placeholder="you@quatadigital.com"
          value={target}
          onChange={(e) => setTarget(e.target.value)}
        />
        <Button
          onClick={send}
          disabled={submitting || target.trim().length < 4 || !target.includes("@")}
        >
          {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Mail className="h-4 w-4" />}
          Send test
        </Button>
      </div>
      {result && (
        <div
          className={`rounded-lg border p-3 text-xs flex items-start gap-2 ${
            result.ok
              ? "border-emerald-200 bg-emerald-50 text-emerald-900"
              : "border-rose-200 bg-rose-50 text-rose-900"
          }`}
        >
          {result.ok ? (
            <>
              <CheckCircle2 className="h-3.5 w-3.5 mt-0.5 shrink-0" />
              <span>
                Sent to <strong>{target}</strong>. If it didn&apos;t land, check spam, then
                confirm SPF / DKIM / DMARC are green at the SMTP provider.
              </span>
            </>
          ) : (
            <>
              <XCircle className="h-3.5 w-3.5 mt-0.5 shrink-0" />
              <span>
                Send failed. <span className="font-mono">{result.error}</span>
              </span>
            </>
          )}
        </div>
      )}
    </div>
  );
}

function placeholderFor(item: SettingItem): string {
  switch (item.key) {
    case "contact.phone":
      return "+237 6 00 00 00 00";
    case "contact.email":
      return "info@quatadigital.com";
    case "contact.address":
      return "QUATA Building, P.C Ntamulung Street\nBamenda — Northwest Region, Cameroon";
    case "contact.support_hours":
      return "Mon–Fri 09:00–18:00 WAT";
    case "social.linkedin_url":
      return "https://linkedin.com/company/quatadigital";
    case "social.twitter_url":
      return "https://twitter.com/quatadigital";
    case "social.instagram_url":
      return "https://instagram.com/quatadigital";
    case "social.youtube_url":
      return "https://youtube.com/@quatadigital";
    case "social.facebook_url":
      return "https://facebook.com/quatadigital";
    case "integrations.hcaptcha_site_key":
      return "10000000-ffff-ffff-ffff-000000000001";
    case "integrations.hcaptcha_secret_key":
      return "Paste secret from hcaptcha.com";
    case "integrations.sentry_dsn":
      return "https://<key>@<id>.ingest.sentry.io/<project>";
    case "integrations.sentry_env":
      return "production";
    default:
      return item.field_type === "url" ? "https://…" : "";
  }
}
