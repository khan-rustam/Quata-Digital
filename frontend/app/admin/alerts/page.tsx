"use client";

/**
 * Alert centre — the control surface for the QUATA Notification Service.
 *
 * Every QUATA platform (QuataPay, QuataFood, Abaqwa, QuataTrade, QUATA AI and
 * this website) publishes events into one service, which is the only thing
 * that talks to @QuataAlertsBot. This page is where a Super Administrator
 * turns that firehose on and off, decides who receives it, proves it works,
 * and audits everything it has ever sent.
 */

import * as React from "react";
import {
  AlertTriangle,
  Bell,
  CheckCircle2,
  ChevronRight,
  Layers,
  Loader2,
  Plug,
  Plus,
  RefreshCw,
  RotateCcw,
  Save,
  Send,
  Server,
  ShieldCheck,
  Trash2,
  Users,
  XCircle,
} from "lucide-react";

import { PageShell } from "@/components/admin/page-shell";
import { EmptyState } from "@/components/admin/empty-state";
import { SlideOver, SlideOverContent } from "@/components/admin/slide-over";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useToast } from "@/components/ui/toast";
import { useApi, useApiAction } from "@/lib/use-api";

type SettingItem = {
  key: string;
  value: string | null;
  group: string;
  label: string;
  description: string | null;
  field_type: string;
  sort_order: number;
};

type Meta = { slug: string; name: string; description: string };

type Stats = {
  window_hours: number;
  total: number;
  sent: number;
  pending: number;
  failed: number;
  suppressed: number;
};

type SettingsResponse = {
  items: SettingItem[];
  groups: string[];
  bot: { ok: boolean; configured: boolean; username?: string; error?: string };
  env_kill_switch: boolean;
  delivery_enabled: boolean;
  platforms: Meta[];
  categories: Meta[];
  priorities: { slug: string; label: string }[];
  configured_platform_keys: string[];
  stats: Stats;
};

type Recipient = {
  id: number;
  chat_id: string;
  label: string;
  is_active: boolean;
  is_group: boolean;
  min_priority: string;
  platforms: string[];
  categories: string[];
  last_ok_at: string | null;
  last_error: string | null;
};

type LogItem = {
  event_id: string;
  platform: string;
  platform_name: string;
  event_key: string;
  category: string;
  category_name: string;
  priority: string;
  priority_label: string;
  status: string;
  title: string;
  reference: string | null;
  attempts: number;
  max_attempts: number;
  last_error: string | null;
  suppressed_reason: string | null;
  sent_at: string | null;
  created_at: string;
  recipients: number;
};

type LogsResponse = {
  total: number;
  page: number;
  page_size: number;
  items: LogItem[];
  stats: Stats;
};

type LogDetail = LogItem & {
  payload: Record<string, unknown> | null;
  message: string | null;
  delivery: { chat_id: string; label?: string; ok: boolean; error?: string | null }[];
  next_attempt_at: string | null;
  source_ip: string | null;
};

const STATUS_VARIANT: Record<string, "success" | "warn" | "danger" | "default"> = {
  sent: "success",
  pending: "warn",
  sending: "warn",
  failed: "danger",
  suppressed: "default",
};

const PRIORITY_DOT: Record<string, string> = {
  info: "bg-emerald-500",
  warning: "bg-amber-500",
  important: "bg-orange-500",
  critical: "bg-rose-500",
};

function isOn(value: string | null | undefined) {
  const v = (value ?? "").toLowerCase();
  return v === "true" || v === "1" || v === "yes" || v === "on";
}

export default function AlertCentrePage() {
  return (
    <PageShell
      title="Alert centre"
      description="@QuataAlertsBot is the single alert channel for the whole QUATA ecosystem. Every platform publishes here; this page controls what gets delivered, to whom, and keeps the audit trail."
      requirePermission="settings:manage"
    >
      <AlertCentre />
    </PageShell>
  );
}

function AlertCentre() {
  const { data, loading, refresh } = useApi<SettingsResponse>("/admin/alerts/settings");

  if (loading || !data) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" /> Loading alert configuration…
      </div>
    );
  }

  return (
    <div className="grid gap-6">
      <StatusStrip data={data} onRefresh={refresh} />
      <Tabs defaultValue="delivery">
        <TabsList>
          <TabsTrigger value="delivery">
            <Send className="h-3.5 w-3.5" /> Delivery
          </TabsTrigger>
          <TabsTrigger value="scope">
            <Layers className="h-3.5 w-3.5" /> Platforms &amp; events
          </TabsTrigger>
          <TabsTrigger value="recipients">
            <Users className="h-3.5 w-3.5" /> Recipients
          </TabsTrigger>
          <TabsTrigger value="logs">
            <Bell className="h-3.5 w-3.5" /> Logs
          </TabsTrigger>
        </TabsList>

        <TabsContent value="delivery">
          <DeliveryTab data={data} onSaved={refresh} />
        </TabsContent>
        <TabsContent value="scope">
          <ScopeTab data={data} onSaved={refresh} />
        </TabsContent>
        <TabsContent value="recipients">
          <RecipientsTab data={data} />
        </TabsContent>
        <TabsContent value="logs">
          <LogsTab data={data} />
        </TabsContent>
      </Tabs>
    </div>
  );
}

/* ---------------------------------------------------------------- status */

function StatusStrip({ data, onRefresh }: { data: SettingsResponse; onRefresh: () => void }) {
  const { bot, stats, delivery_enabled, env_kill_switch } = data;

  return (
    <div className="grid gap-3">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Bot connection"
          value={bot.ok ? `@${bot.username ?? "QuataAlertsBot"}` : bot.configured ? "Error" : "Not configured"}
          tone={bot.ok ? "good" : "bad"}
          hint={bot.ok ? "Token verified with Telegram" : bot.error ?? "Add the bot token in Site settings → Integrations"}
        />
        <StatCard
          label={`Delivered (${stats.window_hours}h)`}
          value={String(stats.sent)}
          tone="good"
          hint={`${stats.total} events published`}
        />
        <StatCard
          label="Queued"
          value={String(stats.pending)}
          tone={stats.pending > 0 ? "warn" : "neutral"}
          hint="Waiting for delivery or retry"
        />
        <StatCard
          label="Failed"
          value={String(stats.failed)}
          tone={stats.failed > 0 ? "bad" : "neutral"}
          hint={`${stats.suppressed} suppressed by settings`}
        />
      </div>

      {env_kill_switch && (
        <Banner tone="warn">
          <strong className="font-semibold">NOTIFY_ENABLED=false in the environment.</strong> Events are
          recorded and audited, but nothing is sent to Telegram regardless of the toggles below. Change it in
          the backend <code className="font-mono">.env</code> and restart to re-enable delivery.
        </Banner>
      )}
      {!delivery_enabled && !env_kill_switch && (
        <Banner tone="warn">
          Telegram delivery is switched off. Events are still recorded — turn it back on under Delivery.
        </Banner>
      )}
      {!bot.configured && (
        <Banner tone="warn">
          No bot token yet. Paste the token for the existing <strong className="font-semibold">@QuataAlertsBot</strong>{" "}
          under <a className="underline" href="/admin/site-settings">Site settings → Integrations</a>. Do not
          create a new bot.
        </Banner>
      )}

      <div>
        <Button variant="outline" size="sm" onClick={onRefresh}>
          <RefreshCw className="h-3.5 w-3.5" /> Refresh
        </Button>
      </div>
    </div>
  );
}

function StatCard({
  label,
  value,
  hint,
  tone,
}: {
  label: string;
  value: string;
  hint?: string;
  tone: "good" | "warn" | "bad" | "neutral";
}) {
  const toneClass = {
    good: "text-emerald-600",
    warn: "text-amber-600",
    bad: "text-rose-600",
    neutral: "text-foreground",
  }[tone];
  return (
    <div className="rounded-2xl border border-border bg-card p-4 ring-soft">
      <div className="text-[11px] uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className={`mt-1 text-xl font-semibold truncate ${toneClass}`}>{value}</div>
      {hint && <div className="mt-1 text-xs text-muted-foreground line-clamp-2">{hint}</div>}
    </div>
  );
}

function Banner({ tone, children }: { tone: "warn" | "info"; children: React.ReactNode }) {
  const cls =
    tone === "warn"
      ? "border-amber-200 bg-amber-50 text-amber-900"
      : "border-border bg-surface-soft text-muted-foreground";
  return (
    <div className={`flex items-start gap-2 rounded-xl border p-3.5 text-xs ${cls}`}>
      <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
      <div>{children}</div>
    </div>
  );
}

/* -------------------------------------------------------------- settings */

function useSettingsDraft(items: SettingItem[], onSaved: () => void) {
  const action = useApiAction();
  const toast = useToast();
  const [drafts, setDrafts] = React.useState<Record<string, string>>({});
  const [saving, setSaving] = React.useState(false);

  const dirty = React.useMemo(
    () => items.filter((it) => drafts[it.key] !== undefined && drafts[it.key] !== (it.value ?? "")),
    [drafts, items],
  );

  async function save() {
    if (!dirty.length) return;
    setSaving(true);
    try {
      await action("/admin/alerts/settings/bulk", {
        method: "POST",
        body: JSON.stringify({ items: dirty.map((it) => ({ key: it.key, value: drafts[it.key] })) }),
      });
      toast.success("Saved", `${dirty.length} setting${dirty.length === 1 ? "" : "s"} updated.`);
      setDrafts({});
      onSaved();
    } catch (err) {
      toast.error("Couldn't save", err instanceof Error ? err.message : "Try again.");
    } finally {
      setSaving(false);
    }
  }

  return {
    drafts,
    dirty,
    saving,
    save,
    reset: () => setDrafts({}),
    set: (key: string, value: string) => setDrafts((d) => ({ ...d, [key]: value })),
    valueOf: (it: SettingItem) => drafts[it.key] ?? it.value ?? "",
  };
}

function SaveBar({
  dirty,
  saving,
  onSave,
  onReset,
}: {
  dirty: number;
  saving: boolean;
  onSave: () => void;
  onReset: () => void;
}) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <Button onClick={onSave} disabled={saving || dirty === 0}>
        {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
        Save changes
        {dirty > 0 && (
          <span className="ml-1 inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-white/15 px-1.5 text-[11px]">
            {dirty}
          </span>
        )}
      </Button>
      <Button variant="outline" onClick={onReset} disabled={saving || dirty === 0}>
        <RotateCcw className="h-3.5 w-3.5" /> Discard
      </Button>
    </div>
  );
}

function Toggle({
  label,
  description,
  checked,
  onChange,
  badge,
}: {
  label: string;
  description?: string | null;
  checked: boolean;
  onChange: (next: boolean) => void;
  badge?: React.ReactNode;
}) {
  return (
    <div className="flex items-start justify-between gap-4">
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <Label className="text-sm font-medium">{label}</Label>
          {badge}
        </div>
        {description && <div className="mt-1 text-xs text-muted-foreground">{description}</div>}
      </div>
      <label className="mt-1 inline-flex cursor-pointer items-center">
        <input
          type="checkbox"
          className="peer sr-only"
          checked={checked}
          onChange={(e) => onChange(e.target.checked)}
        />
        <span className="relative inline-block h-5 w-9 rounded-full bg-secondary transition peer-checked:bg-primary">
          <span className="absolute left-0.5 top-0.5 h-4 w-4 rounded-full bg-white shadow-sm transition peer-checked:translate-x-4" />
        </span>
      </label>
    </div>
  );
}

/* -------------------------------------------------------------- delivery */

function DeliveryTab({ data, onSaved }: { data: SettingsResponse; onSaved: () => void }) {
  const items = data.items.filter((i) => i.group === "delivery" || i.group === "thresholds");
  const draft = useSettingsDraft(items, onSaved);

  return (
    <div className="grid max-w-3xl gap-5">
      <div className="grid gap-5 rounded-2xl border border-border bg-card p-6 ring-soft">
        {items.map((it) =>
          it.field_type === "toggle" ? (
            <Toggle
              key={it.key}
              label={it.label}
              description={it.description}
              checked={isOn(draft.valueOf(it))}
              onChange={(next) => draft.set(it.key, next ? "true" : "false")}
            />
          ) : (
            <div key={it.key} className="grid gap-2">
              <Label htmlFor={it.key} className="text-sm font-medium">
                {it.label}
              </Label>
              {it.description && <div className="text-xs text-muted-foreground">{it.description}</div>}
              {it.key === "delivery.min_priority" ? (
                <Select
                  id={it.key}
                  value={draft.valueOf(it)}
                  onChange={(e) => draft.set(it.key, e.target.value)}
                >
                  {data.priorities.map((p) => (
                    <option key={p.slug} value={p.slug}>
                      {p.label}
                    </option>
                  ))}
                </Select>
              ) : (
                <Input
                  id={it.key}
                  type={it.field_type === "number" ? "number" : "text"}
                  inputMode={it.field_type === "number" ? "numeric" : undefined}
                  value={draft.valueOf(it)}
                  onChange={(e) => draft.set(it.key, e.target.value)}
                />
              )}
            </div>
          ),
        )}
      </div>

      <SaveBar dirty={draft.dirty.length} saving={draft.saving} onSave={draft.save} onReset={draft.reset} />
      <TestPanel />
      <DigestPanel />
      <IngestPanel keys={data.configured_platform_keys} platforms={data.platforms} />
    </div>
  );
}

function TestPanel() {
  const action = useApiAction();
  const toast = useToast();
  const [busy, setBusy] = React.useState<"connection" | "test" | "retry" | null>(null);
  const [result, setResult] = React.useState<{ ok: boolean; text: string } | null>(null);

  async function testConnection() {
    setBusy("connection");
    setResult(null);
    try {
      const r = await action<{
        ok: boolean;
        configured: boolean;
        username?: string;
        bot_id?: number;
        error?: string;
      }>("/admin/alerts/bot");
      setResult({
        ok: r.ok,
        text: r.ok
          ? `Connected to @${r.username} (bot id ${r.bot_id}). The token is valid.`
          : r.configured
            ? (r.error ?? "Telegram rejected the token.")
            : "No bot token set. Add it in Site settings → Integrations.",
      });
    } catch (err) {
      setResult({ ok: false, text: err instanceof Error ? err.message : "Request failed." });
    } finally {
      setBusy(null);
    }
  }

  async function sendTest() {
    setBusy("test");
    setResult(null);
    try {
      const r = await action<{ ok: boolean; delivered?: number; error?: string }>("/admin/alerts/test", {
        method: "POST",
      });
      setResult({
        ok: r.ok,
        text: r.ok
          ? `Delivered to ${r.delivered ?? 0} chat${r.delivered === 1 ? "" : "s"}. Check Telegram.`
          : r.error ?? "Delivery failed.",
      });
    } catch (err) {
      setResult({ ok: false, text: err instanceof Error ? err.message : "Request failed." });
    } finally {
      setBusy(null);
    }
  }

  async function retryFailed() {
    setBusy("retry");
    try {
      const r = await action<{ retried: number; delivered: number }>("/admin/alerts/retry-failed", {
        method: "POST",
      });
      toast.success("Retry complete", `${r.delivered} of ${r.retried} failed notifications delivered.`);
    } catch (err) {
      toast.error("Retry failed", err instanceof Error ? err.message : "Try again.");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="rounded-2xl border border-border bg-surface-soft p-5 ring-soft">
      <div className="flex items-start gap-3">
        <div className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-brand-soft text-primary">
          <ShieldCheck className="h-4 w-4" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="text-sm font-semibold">Prove it works</div>
          <div className="mt-0.5 text-xs text-muted-foreground">
            <strong className="font-semibold">Test connection</strong> asks Telegram to identify the bot —
            it checks the token only. <strong className="font-semibold">Send test notification</strong> puts a
            real alert through the whole pipeline: token, recipient filters, formatting and delivery.
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            <Button size="sm" variant="outline" onClick={testConnection} disabled={busy !== null}>
              {busy === "connection" ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Plug className="h-3.5 w-3.5" />
              )}
              Test connection
            </Button>
            <Button size="sm" onClick={sendTest} disabled={busy !== null}>
              {busy === "test" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Send className="h-3.5 w-3.5" />}
              Send test notification
            </Button>
            <Button size="sm" variant="outline" onClick={retryFailed} disabled={busy !== null}>
              {busy === "retry" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
              Retry failed
            </Button>
          </div>
          {result && (
            <div
              className={`mt-3 flex items-start gap-2 rounded-lg p-3 text-xs ${
                result.ok ? "bg-emerald-50 text-emerald-900" : "bg-rose-50 text-rose-900"
              }`}
            >
              {result.ok ? (
                <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              ) : (
                <XCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              )}
              <span>{result.text}</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function DigestPanel() {
  const action = useApiAction();
  const toast = useToast();
  const [preview, setPreview] = React.useState<string | null>(null);
  const [busy, setBusy] = React.useState<"preview" | "send" | null>(null);

  async function loadPreview() {
    setBusy("preview");
    try {
      const r = await action<{ message: string }>("/admin/alerts/digest/preview");
      // The backend renders Telegram HTML; strip the tags for the web preview.
      setPreview(r.message.replace(/<[^>]+>/g, ""));
    } catch (err) {
      toast.error("Couldn't build the summary", err instanceof Error ? err.message : "Try again.");
    } finally {
      setBusy(null);
    }
  }

  async function sendNow() {
    setBusy("send");
    try {
      const r = await action<{ ok: boolean; delivered?: number; error?: string }>(
        "/admin/alerts/digest/send",
        { method: "POST" },
      );
      if (r.ok) toast.success("Summary sent", `Delivered to ${r.delivered ?? 0} chat(s).`);
      else toast.error("Not sent", r.error ?? "Delivery failed.");
    } catch (err) {
      toast.error("Not sent", err instanceof Error ? err.message : "Try again.");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="rounded-2xl border border-border bg-card p-5 ring-soft">
      <div className="text-sm font-semibold">Daily business summary</div>
      <div className="mt-0.5 text-xs text-muted-foreground">
        Sent automatically at the configured hour. Figures come from what each platform published in the last
        24 hours; a platform can override them by publishing its own <code className="font-mono">summary.daily</code>{" "}
        metrics.
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        <Button size="sm" variant="outline" onClick={loadPreview} disabled={busy !== null}>
          {busy === "preview" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <ChevronRight className="h-3.5 w-3.5" />}
          Preview
        </Button>
        <Button size="sm" variant="outline" onClick={sendNow} disabled={busy !== null}>
          {busy === "send" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Send className="h-3.5 w-3.5" />}
          Send now
        </Button>
      </div>
      {preview && (
        <pre className="mt-3 max-h-80 overflow-auto whitespace-pre-wrap rounded-lg bg-surface-soft p-3 text-xs leading-relaxed">
          {preview}
        </pre>
      )}
    </div>
  );
}

function IngestPanel({ keys, platforms }: { keys: string[]; platforms: Meta[] }) {
  return (
    <div className="rounded-2xl border border-border bg-card p-5 ring-soft">
      <div className="flex items-center gap-2">
        <Server className="h-4 w-4 text-muted-foreground" />
        <div className="text-sm font-semibold">Connected platforms</div>
      </div>
      <div className="mt-0.5 text-xs text-muted-foreground">
        A platform can publish events once it has an ingest key in{" "}
        <code className="font-mono">NOTIFY_INGEST_KEYS</code>. Adding a new platform needs a key, not a code
        change.
      </div>
      <div className="mt-3 grid gap-2">
        {platforms
          .filter((p) => p.slug !== "quata_digital")
          .map((p) => {
            const connected = keys.includes(p.slug);
            return (
              <div
                key={p.slug}
                className="flex items-center justify-between gap-3 rounded-xl border border-border bg-surface-soft px-3 py-2"
              >
                <div className="min-w-0">
                  <div className="text-sm font-medium">{p.name}</div>
                  <div className="truncate text-xs text-muted-foreground">{p.description}</div>
                </div>
                <Badge variant={connected ? "success" : "soon"}>{connected ? "Key set" : "No key"}</Badge>
              </div>
            );
          })}
        <div className="flex items-center justify-between gap-3 rounded-xl border border-border bg-surface-soft px-3 py-2">
          <div className="min-w-0">
            <div className="text-sm font-medium">Quata Digital Enterprise</div>
            <div className="truncate text-xs text-muted-foreground">
              This website and admin console — publishes in-process.
            </div>
          </div>
          <Badge variant="success">Built in</Badge>
        </div>
      </div>
    </div>
  );
}

/* ----------------------------------------------------------------- scope */

function ScopeTab({ data, onSaved }: { data: SettingsResponse; onSaved: () => void }) {
  const items = data.items.filter((i) => i.group === "platforms" || i.group === "categories");
  const draft = useSettingsDraft(items, onSaved);
  const platformItems = items.filter((i) => i.group === "platforms");
  const categoryItems = items.filter((i) => i.group === "categories");

  return (
    <div className="grid max-w-3xl gap-5">
      <div className="rounded-2xl border border-border bg-card p-6 ring-soft">
        <div className="text-sm font-semibold">Platforms</div>
        <div className="mt-0.5 text-xs text-muted-foreground">
          Silence a whole product without touching its code. Its events are still recorded and auditable.
        </div>
        <div className="mt-5 grid gap-5">
          {platformItems.map((it) => (
            <Toggle
              key={it.key}
              label={it.label}
              description={it.description}
              checked={isOn(draft.valueOf(it))}
              onChange={(next) => draft.set(it.key, next ? "true" : "false")}
            />
          ))}
        </div>
      </div>

      <div className="rounded-2xl border border-border bg-card p-6 ring-soft">
        <div className="text-sm font-semibold">Event categories</div>
        <div className="mt-0.5 text-xs text-muted-foreground">
          Applies across every platform. Security and infrastructure alerts are the ones you least want off.
        </div>
        <div className="mt-5 grid gap-5">
          {categoryItems.map((it) => (
            <Toggle
              key={it.key}
              label={it.label}
              description={it.description}
              checked={isOn(draft.valueOf(it))}
              onChange={(next) => draft.set(it.key, next ? "true" : "false")}
              badge={
                it.key === "category.security" || it.key === "category.infrastructure" ? (
                  <Badge variant="warn">critical</Badge>
                ) : undefined
              }
            />
          ))}
        </div>
      </div>

      <SaveBar dirty={draft.dirty.length} saving={draft.saving} onSave={draft.save} onReset={draft.reset} />
    </div>
  );
}

/* ------------------------------------------------------------ recipients */

function RecipientsTab({ data }: { data: SettingsResponse }) {
  const { data: list, loading, refresh } = useApi<{ items: Recipient[] }>("/admin/alerts/recipients");
  const action = useApiAction();
  const toast = useToast();
  const [adding, setAdding] = React.useState(false);
  const [pendingDelete, setPendingDelete] = React.useState<Recipient | null>(null);

  async function toggleActive(r: Recipient) {
    try {
      await action(`/admin/alerts/recipients/${r.id}`, {
        method: "PUT",
        body: JSON.stringify({ is_active: !r.is_active }),
      });
      refresh();
    } catch (err) {
      toast.error("Couldn't update", err instanceof Error ? err.message : "Try again.");
    }
  }

  async function remove() {
    if (!pendingDelete) return;
    try {
      await action(`/admin/alerts/recipients/${pendingDelete.id}`, { method: "DELETE" });
      toast.success("Removed", `${pendingDelete.label} will no longer receive alerts.`);
      setPendingDelete(null);
      refresh();
    } catch (err) {
      toast.error("Couldn't remove", err instanceof Error ? err.message : "Try again.");
    }
  }

  return (
    <div className="grid max-w-3xl gap-5">
      <Banner tone="info">
        Only the chats listed here ever receive an alert. To find a Telegram chat id, message{" "}
        <strong className="font-semibold">@QuataAlertsBot</strong> from that account (or add it to the group)
        and read the id from <code className="font-mono">getUpdates</code>. Group ids start with{" "}
        <code className="font-mono">-100</code>.
      </Banner>

      <div className="flex items-center justify-between gap-3">
        <div className="text-sm text-muted-foreground">
          {loading ? "Loading…" : `${list?.items.length ?? 0} recipient(s)`}
        </div>
        <Button size="sm" onClick={() => setAdding(true)}>
          <Plus className="h-3.5 w-3.5" /> Add recipient
        </Button>
      </div>

      {!loading && (list?.items.length ?? 0) === 0 && (
        <EmptyState
          title="No recipients yet"
          description="Nothing will be delivered until at least one Telegram chat is authorised here."
        />
      )}

      <div className="grid gap-2">
        {(list?.items ?? []).map((r) => (
          <div key={r.id} className="rounded-2xl border border-border bg-card p-4 ring-soft">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-sm font-medium">{r.label}</span>
                  <Badge variant={r.is_active ? "success" : "soon"}>{r.is_active ? "active" : "paused"}</Badge>
                  {r.is_group && <Badge variant="outline">group</Badge>}
                  <Badge variant="outline">≥ {r.min_priority}</Badge>
                </div>
                <div className="mt-1 font-mono text-xs text-muted-foreground">{r.chat_id}</div>
                <div className="mt-1 text-xs text-muted-foreground">
                  {r.platforms.length ? `Platforms: ${r.platforms.join(", ")}` : "All platforms"}
                  {" · "}
                  {r.categories.length ? `Categories: ${r.categories.join(", ")}` : "All categories"}
                </div>
                {r.last_error && (
                  <div className="mt-1 text-xs text-rose-600">Last error: {r.last_error}</div>
                )}
              </div>
              <div className="flex gap-2">
                <Button size="sm" variant="outline" onClick={() => toggleActive(r)}>
                  {r.is_active ? "Pause" : "Resume"}
                </Button>
                <Button size="sm" variant="outline" onClick={() => setPendingDelete(r)}>
                  <Trash2 className="h-3.5 w-3.5" />
                </Button>
              </div>
            </div>
          </div>
        ))}
      </div>

      <AddRecipient
        open={adding}
        onOpenChange={setAdding}
        data={data}
        onCreated={() => {
          setAdding(false);
          refresh();
        }}
      />

      <ConfirmDialog
        open={pendingDelete !== null}
        onOpenChange={(v) => !v && setPendingDelete(null)}
        title="Remove this recipient?"
        description={`${pendingDelete?.label ?? ""} will stop receiving QUATA alerts immediately.`}
        confirmLabel="Remove"
        destructive
        onConfirm={remove}
      />
    </div>
  );
}

function AddRecipient({
  open,
  onOpenChange,
  data,
  onCreated,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  data: SettingsResponse;
  onCreated: () => void;
}) {
  const action = useApiAction();
  const toast = useToast();
  const [chatId, setChatId] = React.useState("");
  const [label, setLabel] = React.useState("");
  const [minPriority, setMinPriority] = React.useState("info");
  const [platforms, setPlatforms] = React.useState<string[]>([]);
  const [categories, setCategories] = React.useState<string[]>([]);
  const [saving, setSaving] = React.useState(false);

  function toggleIn(list: string[], setList: (v: string[]) => void, slug: string) {
    setList(list.includes(slug) ? list.filter((s) => s !== slug) : [...list, slug]);
  }

  async function submit() {
    setSaving(true);
    try {
      await action("/admin/alerts/recipients", {
        method: "POST",
        body: JSON.stringify({
          chat_id: chatId.trim(),
          label: label.trim(),
          min_priority: minPriority,
          platforms,
          categories,
        }),
      });
      toast.success("Recipient added", `${label} will now receive QUATA alerts.`);
      setChatId("");
      setLabel("");
      setPlatforms([]);
      setCategories([]);
      setMinPriority("info");
      onCreated();
    } catch (err) {
      toast.error("Couldn't add", err instanceof Error ? err.message : "Check the chat id and try again.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <SlideOver open={open} onOpenChange={onOpenChange}>
      <SlideOverContent
        title="Add Telegram recipient"
        description="Authorise a Telegram chat to receive QUATA alerts."
      >
        <div className="grid gap-5">
          <div className="grid gap-2">
            <Label htmlFor="chat-id">Telegram chat id</Label>
            <Input
              id="chat-id"
              value={chatId}
              placeholder="123456789 or -1001234567890"
              onChange={(e) => setChatId(e.target.value)}
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="label">Label</Label>
            <Input
              id="label"
              value={label}
              placeholder="e.g. Clovis (CEO) or Ops group"
              onChange={(e) => setLabel(e.target.value)}
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="min-priority">Minimum priority</Label>
            <Select id="min-priority" value={minPriority} onChange={(e) => setMinPriority(e.target.value)}>
              {data.priorities.map((p) => (
                <option key={p.slug} value={p.slug}>
                  {p.label}
                </option>
              ))}
            </Select>
            <div className="text-xs text-muted-foreground">
              Everything at or above this level reaches this chat.
            </div>
          </div>

          <FilterPicker
            title="Platforms"
            hint="None selected = every platform."
            options={data.platforms}
            selected={platforms}
            onToggle={(slug) => toggleIn(platforms, setPlatforms, slug)}
          />
          <FilterPicker
            title="Categories"
            hint="None selected = every category."
            options={data.categories}
            selected={categories}
            onToggle={(slug) => toggleIn(categories, setCategories, slug)}
          />

          <div className="flex gap-2">
            <Button onClick={submit} disabled={saving || !chatId.trim() || !label.trim()}>
              {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
              Add recipient
            </Button>
            <Button variant="outline" onClick={() => onOpenChange(false)} disabled={saving}>
              Cancel
            </Button>
          </div>
        </div>
      </SlideOverContent>
    </SlideOver>
  );
}

function FilterPicker({
  title,
  hint,
  options,
  selected,
  onToggle,
}: {
  title: string;
  hint: string;
  options: Meta[];
  selected: string[];
  onToggle: (slug: string) => void;
}) {
  return (
    <div className="grid gap-2">
      <Label>{title}</Label>
      <div className="text-xs text-muted-foreground">{hint}</div>
      <div className="flex flex-wrap gap-1.5">
        {options.map((o) => {
          const on = selected.includes(o.slug);
          return (
            <button
              key={o.slug}
              type="button"
              onClick={() => onToggle(o.slug)}
              className={`rounded-full border px-2.5 py-1 text-xs transition ${
                on
                  ? "border-transparent bg-primary text-primary-foreground"
                  : "border-border text-muted-foreground hover:bg-surface-soft"
              }`}
            >
              {o.name}
            </button>
          );
        })}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ logs */

function LogsTab({ data }: { data: SettingsResponse }) {
  const [platform, setPlatform] = React.useState("");
  const [statusFilter, setStatusFilter] = React.useState("");
  const [category, setCategory] = React.useState("");
  const [priority, setPriority] = React.useState("");
  const [search, setSearch] = React.useState("");
  const [page, setPage] = React.useState(1);
  const [openId, setOpenId] = React.useState<string | null>(null);

  // Debounce the free-text box so typing a reference doesn't fire a request
  // per keystroke against a table that only grows.
  const [debouncedSearch, setDebouncedSearch] = React.useState("");
  React.useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(search.trim());
      setPage(1);
    }, 300);
    return () => clearTimeout(timer);
  }, [search]);

  const query = new URLSearchParams({ page: String(page), page_size: "25" });
  if (platform) query.set("platform", platform);
  if (statusFilter) query.set("status", statusFilter);
  if (category) query.set("category", category);
  if (priority) query.set("priority", priority);
  if (debouncedSearch) query.set("q", debouncedSearch);

  const { data: logs, loading, refresh } = useApi<LogsResponse>(`/admin/alerts/logs?${query.toString()}`);
  const pages = logs ? Math.max(1, Math.ceil(logs.total / logs.page_size)) : 1;

  const filtered = Boolean(platform || statusFilter || category || priority || debouncedSearch);
  function clearFilters() {
    setPlatform("");
    setStatusFilter("");
    setCategory("");
    setPriority("");
    setSearch("");
    setPage(1);
  }

  function onFilterChange(setter: (v: string) => void) {
    return (e: React.ChangeEvent<HTMLSelectElement>) => {
      setter(e.target.value);
      setPage(1);
    };
  }

  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-center gap-2">
        <Input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search title, event key or reference…"
          className="w-full sm:w-64"
        />
        <Select value={platform} onChange={onFilterChange(setPlatform)} className="w-auto">
          <option value="">All platforms</option>
          {data.platforms.map((p) => (
            <option key={p.slug} value={p.slug}>
              {p.name}
            </option>
          ))}
        </Select>
        <Select value={category} onChange={onFilterChange(setCategory)} className="w-auto">
          <option value="">All categories</option>
          {data.categories.map((c) => (
            <option key={c.slug} value={c.slug}>
              {c.name}
            </option>
          ))}
        </Select>
        <Select value={priority} onChange={onFilterChange(setPriority)} className="w-auto">
          <option value="">Any priority</option>
          {data.priorities.map((p) => (
            <option key={p.slug} value={p.slug}>
              {p.label}
            </option>
          ))}
        </Select>
        <Select value={statusFilter} onChange={onFilterChange(setStatusFilter)} className="w-auto">
          <option value="">Any status</option>
          <option value="sent">Sent</option>
          <option value="pending">Queued</option>
          <option value="failed">Failed</option>
          <option value="suppressed">Suppressed</option>
        </Select>
        <Button size="sm" variant="outline" onClick={refresh}>
          <RefreshCw className="h-3.5 w-3.5" /> Refresh
        </Button>
        {filtered && (
          <Button size="sm" variant="outline" onClick={clearFilters}>
            Clear
          </Button>
        )}
        <div className="ml-auto text-xs text-muted-foreground">
          {logs ? `${logs.total} notification(s)` : ""}
        </div>
      </div>

      {loading && <div className="text-sm text-muted-foreground">Loading…</div>}

      {!loading && logs && logs.items.length === 0 && (
        <EmptyState
          title={filtered ? "No matches" : "Nothing here yet"}
          description={
            filtered
              ? "No notifications match these filters. Try clearing them."
              : "Published events will appear as soon as they arrive."
          }
        />
      )}

      <div className="grid gap-1.5">
        {(logs?.items ?? []).map((item) => (
          <button
            key={item.event_id}
            type="button"
            onClick={() => setOpenId(item.event_id)}
            className="flex items-center gap-3 rounded-xl border border-border bg-card p-3 text-left ring-soft transition hover:bg-surface-soft"
          >
            <span
              className={`h-2 w-2 shrink-0 rounded-full ${PRIORITY_DOT[item.priority] ?? "bg-slate-400"}`}
              aria-hidden
            />
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <span className="truncate text-sm font-medium">{item.title}</span>
                <Badge variant={STATUS_VARIANT[item.status] ?? "default"}>{item.status}</Badge>
              </div>
              <div className="mt-0.5 truncate text-xs text-muted-foreground">
                {item.platform_name} · {item.event_key}
                {item.reference ? ` · ${item.reference}` : ""}
              </div>
            </div>
            <div className="shrink-0 text-right text-xs text-muted-foreground">
              <div>{new Date(item.created_at).toLocaleString()}</div>
              {item.status === "failed" && <div className="text-rose-600">{item.attempts} attempt(s)</div>}
            </div>
            <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" />
          </button>
        ))}
      </div>

      {pages > 1 && (
        <div className="flex items-center justify-center gap-2">
          <Button size="sm" variant="outline" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
            Previous
          </Button>
          <span className="text-xs text-muted-foreground">
            Page {page} of {pages}
          </span>
          <Button size="sm" variant="outline" disabled={page >= pages} onClick={() => setPage((p) => p + 1)}>
            Next
          </Button>
        </div>
      )}

      <LogDetailPanel eventId={openId} onClose={() => setOpenId(null)} onRetried={refresh} />
    </div>
  );
}

function LogDetailPanel({
  eventId,
  onClose,
  onRetried,
}: {
  eventId: string | null;
  onClose: () => void;
  onRetried: () => void;
}) {
  const { data: detail, loading, refresh } = useApi<LogDetail>(
    eventId ? `/admin/alerts/logs/${eventId}` : null,
  );
  const action = useApiAction();
  const toast = useToast();
  const [retrying, setRetrying] = React.useState(false);

  async function retry() {
    if (!eventId) return;
    setRetrying(true);
    try {
      const r = await action<{ ok: boolean; error?: string }>(`/admin/alerts/logs/${eventId}/retry`, {
        method: "POST",
      });
      if (r.ok) toast.success("Retried", "The notification was delivered.");
      else toast.error("Still failing", r.error ?? "Telegram rejected the message.");
      refresh();
      onRetried();
    } catch (err) {
      toast.error("Retry failed", err instanceof Error ? err.message : "Try again.");
    } finally {
      setRetrying(false);
    }
  }

  return (
    <SlideOver open={eventId !== null} onOpenChange={(v) => !v && onClose()}>
      <SlideOverContent
        title={detail?.title ?? "Notification"}
        description={detail ? `${detail.platform_name} · ${detail.event_key}` : undefined}
        size="lg"
      >
        {loading || !detail ? (
          <div className="text-sm text-muted-foreground">Loading…</div>
        ) : (
          <div className="grid gap-5">
            <div className="flex flex-wrap gap-2">
              <Badge variant={STATUS_VARIANT[detail.status] ?? "default"}>{detail.status}</Badge>
              <Badge variant="outline">{detail.priority_label}</Badge>
              <Badge variant="outline">{detail.category_name}</Badge>
              {detail.reference && <Badge variant="outline">{detail.reference}</Badge>}
            </div>

            {detail.suppressed_reason && (
              <Banner tone="warn">Suppressed: {detail.suppressed_reason}</Banner>
            )}
            {detail.last_error && (
              <div className="rounded-xl bg-rose-50 p-3 text-xs text-rose-900">
                <strong className="font-semibold">Last error:</strong> {detail.last_error}
                <div className="mt-1">
                  Attempt {detail.attempts} of {detail.max_attempts}
                  {detail.next_attempt_at
                    ? ` · next retry ${new Date(detail.next_attempt_at).toLocaleString()}`
                    : ""}
                </div>
              </div>
            )}

            <div>
              <div className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Message sent
              </div>
              <pre className="max-h-72 overflow-auto whitespace-pre-wrap rounded-lg bg-surface-soft p-3 text-xs leading-relaxed">
                {(detail.message ?? "").replace(/<[^>]+>/g, "")}
              </pre>
            </div>

            <div>
              <div className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Delivery
              </div>
              {detail.delivery.length === 0 ? (
                <div className="text-xs text-muted-foreground">Not attempted yet.</div>
              ) : (
                <div className="grid gap-1.5">
                  {detail.delivery.map((d, i) => (
                    <div
                      key={`${d.chat_id}-${i}`}
                      className="flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-xs"
                    >
                      {d.ok ? (
                        <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />
                      ) : (
                        <XCircle className="h-3.5 w-3.5 text-rose-600" />
                      )}
                      <span className="font-medium">{d.label ?? d.chat_id}</span>
                      <span className="font-mono text-muted-foreground">{d.chat_id}</span>
                      {d.error && <span className="ml-auto truncate text-rose-600">{d.error}</span>}
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div>
              <div className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Payload (redacted at ingest)
              </div>
              <pre className="max-h-56 overflow-auto rounded-lg bg-surface-soft p-3 text-xs">
                {JSON.stringify(detail.payload ?? {}, null, 2)}
              </pre>
            </div>

            {detail.status !== "sent" && (
              <div>
                <Button onClick={retry} disabled={retrying}>
                  {retrying ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
                  Retry delivery
                </Button>
              </div>
            )}
          </div>
        )}
      </SlideOverContent>
    </SlideOver>
  );
}
