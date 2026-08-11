"use client";

/**
 * QCP overview — "is it on, is it healthy, what is blocking me".
 *
 * QCP ships dormant on purpose. Three independent gates must all be true
 * before a single message leaves: the `WHATSAPP_ENABLED` environment switch,
 * the `whatsapp.delivery_enabled` site setting, and the per-account /
 * per-product flags (both default off). They are shown separately and
 * unresolved, because "why is nothing sending" has three different answers
 * and collapsing them into one light is what makes someone flip the wrong
 * switch.
 *
 * This screen can now change two of those: an account's credentials, and an
 * account's `is_active`. Neither the environment switch nor the delivery
 * setting is reachable from here, so configuring or even activating a number
 * still cannot start traffic on its own — which is the property that lets
 * this page carry a write surface at all.
 *
 * **Activation is the dangerous one.** It is what lets QCP address Meta from
 * a number the fleet's existing senders are already using. No product has
 * migrated, so a second sender on a live number risks the number's quality
 * rating and its messaging limit. That consequence is spelled out at the
 * point of clicking, the button is blocked while the number is unconfigured,
 * and it takes a typed confirmation.
 */

import * as React from "react";
import {
  AlertTriangle,
  Blocks,
  CheckCircle2,
  Clock,
  KeyRound,
  MinusCircle,
  Phone,
  PlugZap,
  Power,
  RefreshCw,
  Settings2,
  ShieldAlert,
  XCircle,
} from "lucide-react";
import { PageShell } from "@/components/admin/page-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/admin/empty-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useToast } from "@/components/ui/toast";
import { useApi } from "@/lib/use-api";
import { cn } from "@/lib/utils";
import {
  QCP,
  credentialPatch,
  fingerprint,
  useQcpWrite,
  type QcpConnectionTest,
  type QcpRefusal,
} from "./api";
import {
  HEALTH_TONE,
  Loading,
  LoadError,
  Note,
  PurposeBadge,
  PurposeChip,
  QcpTabs,
  RefusalBanner,
  SecretField,
  StatusBadge,
  TypeToConfirm,
  fmt,
  relative,
  type QcpAccount,
  type QcpOverview,
  type QcpProduct,
} from "./shared";

export default function QcpOverviewPage() {
  return (
    <PageShell
      title="QCP — Quata Communications Platform"
      description="One WhatsApp backbone for every QUATA product. Products call QCP; only QCP talks to Meta. Two numbers, kept apart by the database: Quata Verify carries authentication only, QUATA carries everything else."
      requirePermission="settings:manage"
    >
      <QcpTabs />
      <Overview />
    </PageShell>
  );
}

function Overview() {
  const { data, error, loading, refresh } = useApi<QcpOverview>(QCP.overview);
  const [configuring, setConfiguring] = React.useState<QcpAccount | null>(null);
  const [switching, setSwitching] = React.useState<QcpAccount | null>(null);

  if (loading && !data) return <Loading label="Loading QCP status…" />;
  if (error) return <LoadError error={error} onRetry={refresh} />;
  if (!data) return <Loading label="Loading QCP status…" />;

  const { gates } = data;
  const live = gates.env_enabled && gates.delivery_enabled && gates.any_account_active;

  return (
    <div className="grid gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <span
            className={cn(
              "inline-flex h-2.5 w-2.5 rounded-full",
              live ? "bg-emerald-500" : "bg-slate-400"
            )}
          />
          <span className="text-sm font-semibold">
            {live ? "QCP is live" : "QCP is dormant"}
          </span>
          <span className="text-xs text-muted-foreground">
            {live
              ? "At least one number is active and delivery is enabled."
              : "Nothing is being sent. This is the shipped state."}
          </span>
        </div>
        <Button variant="outline" size="sm" onClick={refresh}>
          <RefreshCw className="h-3.5 w-3.5" /> Refresh
        </Button>
      </div>

      {!live && (
        <Note>
          Dormant is correct until a product is explicitly migrated. QuataFood and
          QuataPay keep sending exactly as they do today; QCP takes no traffic from
          them until someone enables that product here and switches its number on.
        </Note>
      )}

      <Gates gates={gates} />

      <Blockers data={data} />

      <section>
        <SectionTitle icon={Phone}>The two numbers</SectionTitle>
        <div className="mt-3 grid gap-3 lg:grid-cols-2">
          {data.accounts.length === 0 ? (
            <div className="lg:col-span-2">
              <EmptyState
                icon={Phone}
                title="No accounts registered"
                description="QCP seeds Quata Verify and QUATA on first boot. Neither is present — the seed has not run against this database."
              />
            </div>
          ) : (
            data.accounts.map((a) => (
              <AccountCard
                key={a.id}
                account={a}
                onConfigure={() => setConfiguring(a)}
                onToggle={() => setSwitching(a)}
                onTested={refresh}
              />
            ))
          )}
        </div>
      </section>

      <section>
        <SectionTitle icon={Blocks}>Registered products</SectionTitle>
        <div className="mt-3">
          {data.products.length === 0 ? (
            <EmptyState
              icon={Blocks}
              title="No products registered"
              description="Nothing may call QCP yet. Register one on the Registry tab — it arrives disabled and with no key, which is the only safe way for it to arrive."
            />
          ) : (
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
              {data.products.map((p) => (
                <ProductChip key={p.id} product={p} />
              ))}
            </div>
          )}
        </div>
      </section>

      <section>
        <SectionTitle icon={Clock}>Traffic</SectionTitle>
        <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Metric
            label="Queue depth"
            value={data.queue.queued}
            tone={data.queue.queued > 0 ? "warn" : "neutral"}
            hint={
              data.queue.oldest_queued_at
                ? `Oldest waiting since ${relative(data.queue.oldest_queued_at)}`
                : "Nothing waiting to send"
            }
          />
          <Metric
            label={`Sent (last ${data.window_hours}h)`}
            value={data.recent.sent}
            tone="neutral"
            hint={`${data.recent.total} messages logged in the window`}
          />
          <Metric
            label="Failed (all time)"
            value={data.queue.failed}
            tone={data.queue.failed > 0 ? "bad" : "neutral"}
            hint={`${data.recent.failed} in the last ${data.window_hours}h`}
          />
          <Metric
            label="Suppressed (all time)"
            value={data.queue.suppressed}
            tone={data.queue.suppressed > 0 ? "warn" : "neutral"}
            hint="Refused by routing before Meta was contacted"
          />
        </div>
        <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Metric
            label="Templates approved"
            value={data.templates.approved}
            tone="neutral"
            hint={`${data.templates.pending_approval} pending, ${data.templates.rejected} rejected`}
          />
          <Metric
            label="Open conversations"
            value={data.conversations.open}
            tone="neutral"
            hint={`${data.conversations.total} thread${
              data.conversations.total === 1 ? "" : "s"
            } in total`}
          />
        </div>
      </section>

      <section>
        <SectionTitle icon={XCircle}>Recent failures &amp; suppressions</SectionTitle>
        <div className="mt-3">
          {data.failures.length === 0 ? (
            <EmptyState
              icon={CheckCircle2}
              title="Nothing has failed"
              description={
                data.queue.total === 0
                  ? "No message has ever been sent through QCP, so there is nothing that could have failed."
                  : "Every message QCP has handled either delivered or is still in flight."
              }
            />
          ) : (
            <div className="overflow-hidden rounded-2xl border border-border bg-card ring-soft divide-y divide-border">
              {data.failures.map((f) => (
                <div key={f.message_uid} className="p-4">
                  <div className="flex flex-wrap items-center gap-2">
                    <StatusBadge
                      value={f.status}
                      tones={{ failed: "danger", suppressed: "default" }}
                    />
                    <span className="text-sm font-medium">{f.intent ?? "—"}</span>
                    {f.product && (
                      <Badge variant="outline" className="text-[11px]">
                        {f.product}
                      </Badge>
                    )}
                    <span className="ml-auto text-xs text-muted-foreground">
                      {fmt(f.created_at)}
                    </span>
                  </div>
                  <div className="mt-1.5 text-xs text-muted-foreground break-words">
                    {f.suppressed_reason
                      ? `Suppressed: ${f.suppressed_reason}`
                      : f.last_error ?? "No error recorded"}
                    {f.error_code && ` (code ${f.error_code})`}
                    {" · "}
                    attempt {f.attempts}/{f.max_attempts}
                    {f.to && ` · to ${f.to}`}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </section>

      <section>
        <SectionTitle icon={AlertTriangle}>Routing denials</SectionTitle>
        <p className="mt-1 text-xs text-muted-foreground max-w-2xl">
          A denial is QCP refusing to send before Meta was contacted — a disabled
          product, a missing route, or an attempt to put the wrong kind of message on
          the Verify number. These rows have no admin actor; they are machine-written.
        </p>
        <div className="mt-3">
          {data.denials.length === 0 ? (
            <EmptyState
              icon={CheckCircle2}
              title="No denials recorded"
              description="Nothing has been refused. With no product enabled, nothing has asked."
            />
          ) : (
            <div className="overflow-hidden rounded-2xl border border-border bg-card ring-soft divide-y divide-border">
              {data.denials.map((d) => (
                <div key={d.id} className="flex flex-wrap items-center gap-2 p-4 text-sm">
                  <Badge variant={d.outcome === "denied" ? "danger" : "warn"}>
                    {d.outcome}
                  </Badge>
                  <code className="text-xs">{d.reason ?? d.action}</code>
                  <span className="text-xs text-muted-foreground">
                    {d.action} · {d.resource_type}
                    {d.product ? ` · ${d.product}` : ""}
                  </span>
                  <span className="ml-auto text-xs text-muted-foreground">
                    {fmt(d.created_at)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </section>

      {/* Keyed so each dialog is a fresh mount per account: its form state is
          derived from the account it opened on, and remounting is how that
          stays true without a state-resetting effect. */}
      {configuring && (
        <ConfigureAccountDialog
          key={configuring.slug}
          account={configuring}
          onClose={() => setConfiguring(null)}
          onSaved={refresh}
        />
      )}
      {switching && (
        <ActivationDialog
          key={switching.slug}
          account={switching}
          anyProductEnabled={gates.any_product_enabled}
          onClose={() => setSwitching(null)}
          onSaved={refresh}
        />
      )}
    </div>
  );
}

/* ------------------------------------------------------------- blockers */

/**
 * "What is blocking me", resolved into things someone can actually do.
 *
 * The gate tiles above say *which* switch is off. This says what to do about
 * it, in the order it has to happen — because the failure mode this console
 * exists to prevent is an operator flipping the switch they can reach (the
 * account) when the one that matters is somewhere else entirely.
 */
function Blockers({ data }: { data: QcpOverview }) {
  const items: { text: string; actionable: boolean }[] = [];
  const { gates } = data;

  const unconfigured = data.accounts.filter((a) => !a.configured);
  if (data.accounts.length === 0) {
    items.push({
      text: "No account rows exist. The QCP seed has not run against this database — nothing on this screen can create the two numbers.",
      actionable: false,
    });
  } else if (unconfigured.length > 0) {
    items.push({
      text: `${unconfigured.map((a) => a.name).join(" and ")} ${
        unconfigured.length === 1 ? "has" : "have"
      } no usable credentials. Use Configure below — you need the phone number id, the WABA id and an access token from Meta.`,
      actionable: true,
    });
  }
  if (!gates.any_account_active) {
    items.push({
      text: "Both numbers are inactive, so QCP will not address Meta at all. Activating one is the single most consequential action in this product — read the dialog.",
      actionable: true,
    });
  }
  if (!gates.any_product_enabled) {
    items.push({
      text: "No product may call QCP. Enable one on the Registry tab and give it an API key; that is the per-product migration gate.",
      actionable: true,
    });
  }
  if (!gates.env_enabled) {
    items.push({
      text: "WHATSAPP_ENABLED is false on the backend. That is an .env change and a restart — no button in this console overrides it.",
      actionable: false,
    });
  }
  if (!gates.delivery_enabled) {
    items.push({
      text: "whatsapp.delivery_enabled is off in site settings. Messages would be recorded and suppressed rather than sent.",
      actionable: false,
    });
  }
  if (!gates.require_signature) {
    items.push({
      text: "Inbound webhook signature verification is not required. Meta's callbacks are unauthenticated until it is.",
      actionable: false,
    });
  }

  if (items.length === 0) {
    return (
      <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-4 text-emerald-900">
        <div className="flex items-start gap-2">
          <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" />
          <div className="text-sm">
            <span className="font-semibold">Nothing is blocking delivery.</span> Every
            gate is open and at least one number and product are on.
          </div>
        </div>
      </div>
    );
  }

  return (
    <section>
      <SectionTitle icon={AlertTriangle}>What is blocking you</SectionTitle>
      <ol className="mt-3 grid gap-2">
        {items.map((b, i) => (
          <li
            key={i}
            className="flex items-start gap-3 rounded-xl border border-border bg-card p-3.5 ring-soft"
          >
            <span className="mt-0.5 inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-secondary text-[11px] font-semibold">
              {i + 1}
            </span>
            <span className="text-xs">
              {b.text}
              {!b.actionable && (
                <Badge variant="outline" className="ml-2 text-[10px]">
                  not fixable here
                </Badge>
              )}
            </span>
          </li>
        ))}
      </ol>
    </section>
  );
}

/* --------------------------------------------------------------- pieces */

function SectionTitle({
  icon: Icon,
  children,
}: {
  icon: React.ComponentType<{ className?: string }>;
  children: React.ReactNode;
}) {
  return (
    <h3 className="flex items-center gap-2 text-sm font-semibold tracking-tight">
      <Icon className="h-4 w-4 text-muted-foreground" />
      {children}
    </h3>
  );
}

function Gates({ gates }: { gates: QcpOverview["gates"] }) {
  const items = [
    {
      label: "Environment switch",
      on: gates.env_enabled,
      detail: gates.env_enabled
        ? "WHATSAPP_ENABLED=true"
        : "WHATSAPP_ENABLED=false — needs a backend .env change and a restart. Nothing in this console overrides it.",
    },
    {
      label: "Delivery setting",
      on: gates.delivery_enabled,
      detail: gates.delivery_enabled
        ? "whatsapp.delivery_enabled is on"
        : "whatsapp.delivery_enabled is off. Messages would be recorded and suppressed, not sent.",
    },
    {
      label: "A number is active",
      on: gates.any_account_active,
      detail: gates.any_account_active
        ? "At least one number is switched on"
        : "Both numbers are inactive. Configure and activate one below.",
    },
    {
      label: "A product is enabled",
      on: gates.any_product_enabled,
      detail: gates.any_product_enabled
        ? "At least one product may call QCP"
        : "No product may call QCP. This is the per-product migration gate.",
    },
  ];

  return (
    <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
      {items.map((g) => (
        <div
          key={g.label}
          className="rounded-2xl border border-border bg-card p-4 ring-soft"
        >
          <div className="flex items-center gap-2">
            {g.on ? (
              <CheckCircle2 className="h-4 w-4 text-emerald-600" />
            ) : (
              <MinusCircle className="h-4 w-4 text-slate-400" />
            )}
            <span className="text-sm font-medium">{g.label}</span>
          </div>
          <p className="mt-1.5 text-xs text-muted-foreground">{g.detail}</p>
        </div>
      ))}
    </div>
  );
}

function AccountCard({
  account,
  onConfigure,
  onToggle,
  onTested,
}: {
  account: QcpAccount;
  onConfigure: () => void;
  onToggle: () => void;
  onTested: () => void;
}) {
  const { write, busy } = useQcpWrite();
  const toast = useToast();
  const [testRefusal, setTestRefusal] = React.useState<QcpRefusal | null>(null);

  /**
   * Ask Meta whether the number is healthy. `sent_message` is pinned false in
   * the backend contract, so this can be offered on an inactive number
   * without any risk of putting a "test" on a real customer's phone.
   */
  async function test() {
    setTestRefusal(null);
    const res = await write<QcpConnectionTest>(
      QCP.accountTestConnection(account.slug),
      { method: "POST" }
    );
    if (!res.ok) {
      setTestRefusal(res.refusal);
      return;
    }
    if (res.data.ok) {
      toast.success(
        `${account.name} answered`,
        `Health ${res.data.health}${
          res.data.verified_name ? ` · verified as ${res.data.verified_name}` : ""
        }${res.data.quality_rating ? ` · quality ${res.data.quality_rating}` : ""}. No message was sent.`
      );
    } else {
      toast.error(
        `${account.name} did not answer`,
        res.data.error ?? "Meta rejected the credentials. No message was sent."
      );
    }
    onTested();
  }

  const creds: { label: string; ok: boolean }[] = [
    { label: "Phone number ID", ok: account.has_phone_number_id },
    { label: "WABA ID", ok: account.has_waba_id },
    { label: "Access token", ok: account.has_access_token },
    { label: "App secret", ok: account.has_app_secret },
    { label: "Webhook verify token", ok: account.has_verify_token },
  ];
  const missing = creds.filter((c) => !c.ok).length;

  return (
    <div className="rounded-2xl border border-border bg-card p-5 ring-soft">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-base font-semibold tracking-tight">{account.name}</span>
            <PurposeChip purpose={account.purpose} />
          </div>
          <div className="mt-1 text-xs text-muted-foreground">
            <code>{account.slug}</code> · {account.display_phone ?? "no number set"} ·{" "}
            {account.api_version}
          </div>
        </div>
        <Badge variant={account.is_active ? "success" : "default"}>
          {account.is_active ? "Active" : "Inactive"}
        </Badge>
      </div>

      <p className="mt-3 text-xs text-muted-foreground">
        {account.purpose === "authentication"
          ? "OTP, login codes, PIN resets, device verification, transaction and security alerts. This number can only ever emit approved templates — free-form and marketing are unrepresentable."
          : "Support, AI, campaigns, order and delivery updates, promotions."}
      </p>

      <div className="mt-4 grid gap-1.5">
        {creds.map((c) => (
          <div key={c.label} className="flex items-center gap-2 text-xs">
            {c.ok ? (
              <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />
            ) : (
              <MinusCircle className="h-3.5 w-3.5 text-slate-400" />
            )}
            <span className={c.ok ? "" : "text-muted-foreground"}>{c.label}</span>
            <span className="ml-auto text-muted-foreground">
              {c.ok ? "set" : "not set"}
            </span>
          </div>
        ))}
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-border pt-3 text-xs">
        <span className="text-muted-foreground">Health</span>
        <StatusBadge value={account.health} tones={HEALTH_TONE} />
        {account.quality_rating && (
          <Badge variant="outline">Quality {account.quality_rating}</Badge>
        )}
        {account.messaging_limit && (
          <Badge variant="outline">{account.messaging_limit}</Badge>
        )}
        <span className="ml-auto text-muted-foreground">
          Checked {relative(account.last_checked_at)}
        </span>
      </div>

      {/*
        A security posture, not a blank field. Rendered above the "credentials
        still missing" line and in a different register, because they are
        different statements: one says the number cannot send yet, the other
        says the two-number separation is currently defeated. A `critical`
        gets the alarm treatment; a `warning` does not, so the alarm keeps
        meaning something.
      */}
      {account.security?.length > 0 && (
        <ul className="mt-3 grid gap-2">
          {account.security.map((w) => (
            <li
              key={w.code}
              className={
                w.severity === "critical"
                  ? "rounded-xl border-2 border-rose-400 bg-rose-50 p-3 text-xs text-rose-900"
                  : "rounded-xl border border-amber-300 bg-amber-50 p-3 text-xs text-amber-900"
              }
            >
              <div className="flex items-start gap-2">
                <ShieldAlert className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                <div className="min-w-0">
                  <div className="font-semibold">
                    {w.severity === "critical" ? "Critical" : "Warning"}
                  </div>
                  <p className="mt-0.5 break-words">{w.message}</p>
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}

      {account.last_error && (
        <p className="mt-2 text-xs text-rose-700 break-words">{account.last_error}</p>
      )}
      {!account.configured && (
        <p className="mt-2 text-xs text-muted-foreground">
          {missing} of {creds.length} credentials still missing — this number cannot
          reach Meta at all, which is why it is safe for it to sit here inactive.
        </p>
      )}

      {testRefusal && (
        <div className="mt-3">
          <RefusalBanner refusal={testRefusal} onDismiss={() => setTestRefusal(null)} />
        </div>
      )}

      <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-border pt-3">
        <Button variant="outline" size="sm" onClick={onConfigure}>
          <Settings2 className="h-3.5 w-3.5" /> Configure credentials
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={test}
          disabled={busy || !account.configured}
          title={
            account.configured
              ? "Asks Meta whether this number is healthy. No message is sent to anyone."
              : "Nothing to test — no credentials are stored."
          }
        >
          <PlugZap className="h-3.5 w-3.5" /> Test connection
        </Button>
        <Button
          size="sm"
          variant={account.is_active ? "outline" : "default"}
          onClick={onToggle}
          disabled={!account.is_active && !account.configured}
          title={
            !account.is_active && !account.configured
              ? "Configure the phone number id, WABA id and access token first — an unconfigured number cannot reach Meta."
              : undefined
          }
        >
          <Power className="h-3.5 w-3.5" />
          {account.is_active ? "Deactivate" : "Activate this number"}
        </Button>
        {!account.is_active && !account.configured && (
          <span className="text-[11px] text-muted-foreground">
            Blocked until credentials are set.
          </span>
        )}
      </div>
    </div>
  );
}

function ProductChip({ product }: { product: QcpProduct }) {
  return (
    <div className="rounded-xl border border-border bg-card p-3.5 ring-soft">
      <div className="flex items-center gap-2">
        <span className="text-sm font-medium truncate">{product.name}</span>
        <Badge
          variant={product.is_enabled ? "success" : "default"}
          className="ml-auto shrink-0"
        >
          {product.is_enabled ? "Enabled" : "Off"}
        </Badge>
      </div>
      <div className="mt-1 text-xs text-muted-foreground">
        <code>{product.slug}</code>
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-1">
        <span className="text-xs text-muted-foreground">May reach</span>
        {(product.allowed_purposes ?? []).map((p) => (
          <PurposeBadge key={p} purpose={p} />
        ))}
      </div>
      <div className="mt-2 text-xs text-muted-foreground">
        {product.has_api_key ? "Key issued" : "No key issued"} · last seen{" "}
        {relative(product.last_seen_at)}
      </div>
    </div>
  );
}

function Metric({
  label,
  value,
  hint,
  tone,
}: {
  label: string;
  value: number;
  hint?: string;
  tone: "warn" | "bad" | "neutral";
}) {
  const toneClass = {
    warn: "text-amber-600",
    bad: "text-rose-600",
    neutral: "text-foreground",
  }[tone];
  return (
    <div className="rounded-2xl border border-border bg-card p-4 ring-soft">
      <div className="text-[11px] uppercase tracking-wider text-muted-foreground">
        {label}
      </div>
      <div className={cn("mt-1 text-2xl font-semibold tracking-tight", toneClass)}>
        {value}
      </div>
      {hint && <div className="mt-1 text-xs text-muted-foreground">{hint}</div>}
    </div>
  );
}

/* --------------------------------------------------------- configure flow */

/**
 * Field for an identifier the API reports only as present/absent.
 *
 * `phone_number_id` and `waba_id` are not secrets, but the read shape returns
 * `has_phone_number_id` rather than the value, so there is nothing to
 * prefill. Same contract as a credential: blank means "leave it alone".
 */
function PresenceField({
  id,
  name,
  label,
  configured,
  placeholder,
}: {
  id: string;
  name: string;
  label: string;
  configured: boolean;
  placeholder: string;
}) {
  return (
    <div className="grid gap-2">
      <div className="flex items-center gap-2">
        <Label htmlFor={id}>{label}</Label>
        <Badge variant={configured ? "success" : "warn"} className="text-[11px]">
          {configured ? "Configured" : "Not configured"}
        </Badge>
      </div>
      <Input
        id={id}
        name={name}
        autoComplete="off"
        spellCheck={false}
        placeholder={configured ? "Leave blank to keep the stored value" : placeholder}
      />
    </div>
  );
}

function ConfigureAccountDialog({
  account,
  onClose,
  onSaved,
}: {
  account: QcpAccount;
  onClose: () => void;
  onSaved: () => void;
}) {
  const { write, busy } = useQcpWrite();
  const toast = useToast();
  const [refusal, setRefusal] = React.useState<QcpRefusal | null>(null);

  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    const str = (k: string) => String(form.get(k) ?? "").trim();

    // Blank credential boxes are omitted entirely — see `credentialPatch`.
    const secrets = credentialPatch({
      phone_number_id: str("phone_number_id"),
      waba_id: str("waba_id"),
      access_token: str("access_token"),
      app_secret: str("app_secret"),
      webhook_verify_token: str("webhook_verify_token"),
    });

    // `AccountCredentialsIn` forbids extra fields, so only the seven it
    // declares may be sent — a stray key is a 422, not a silent no-op.
    const payload: Record<string, unknown> = { ...secrets };
    const display = str("display_phone");
    const version = str("api_version");
    if (display && display !== (account.display_phone ?? "")) {
      payload.display_phone = display;
    }
    if (version && version !== account.api_version) payload.api_version = version;

    if (Object.keys(payload).length === 0) {
      setRefusal({
        title: "Nothing to save",
        detail:
          'Every box was left blank or unchanged, which means "keep what is stored". Fill in the value you want to replace.',
        policy: true,
      });
      return;
    }

    // A short digest of what is being sent, so the operator can match this
    // change against the audit entry later. Never the value itself.
    const changed = Object.keys(secrets);
    const digests = await Promise.all(
      changed.map(async (k) => `${k} → ${await fingerprint(secrets[k])}`)
    );

    const res = await write(QCP.accountCredentials(account.slug), {
      method: "PUT",
      body: payload,
    });
    if (!res.ok) {
      setRefusal(res.refusal);
      return;
    }
    toast.success(
      `${account.name} updated`,
      changed.length
        ? `Replaced ${changed.length} value${changed.length === 1 ? "" : "s"} · ${digests.join(", ")}`
        : "Display details updated."
    );
    onSaved();
    onClose();
  }

  return (
    <Dialog open onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>Configure {account.name}</DialogTitle>
          <DialogDescription>
            Meta credentials for the <strong>{account.purpose}</strong> number. Saving
            these does not switch anything on — the number stays{" "}
            {account.is_active ? "active" : "inactive"} and delivery is unaffected.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={submit} className="grid gap-4 max-h-[70vh] overflow-y-auto pr-1">
          {refusal && (
            <RefusalBanner refusal={refusal} onDismiss={() => setRefusal(null)} />
          )}

          <div className="grid gap-3 sm:grid-cols-2">
            <div className="grid gap-2">
              <Label htmlFor="display_phone">Display phone</Label>
              <Input
                id="display_phone"
                name="display_phone"
                defaultValue={account.display_phone ?? ""}
                placeholder="+237 6XX XXX XXX"
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="api_version">Graph API version</Label>
              <Input
                id="api_version"
                name="api_version"
                defaultValue={account.api_version}
                placeholder="v21.0"
              />
            </div>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <PresenceField
              id="phone_number_id"
              name="phone_number_id"
              label="Phone number ID"
              configured={account.has_phone_number_id}
              placeholder="From Meta → WhatsApp → API setup"
            />
            <PresenceField
              id="waba_id"
              name="waba_id"
              label="WABA ID"
              configured={account.has_waba_id}
              placeholder="WhatsApp Business Account id"
            />
          </div>

          <SecretField
            id="access_token"
            name="access_token"
            label="Access token"
            configured={account.has_access_token}
            hint="The system-user token QCP sends with every Graph call."
          />
          <SecretField
            id="app_secret"
            name="app_secret"
            label="App secret"
            configured={account.has_app_secret}
            hint="Used to verify the X-Hub-Signature-256 on Meta's inbound webhooks."
          />
          <SecretField
            id="webhook_verify_token"
            name="webhook_verify_token"
            label="Webhook verify token"
            configured={account.has_verify_token}
            hint="Echoed back during Meta's webhook subscription handshake."
          />

          <Note>
            This write is audited: your user, the timestamp, which fields changed, and a
            digest of the old and new values. The values themselves are never written to
            the log, echoed back by the API, or shown on this screen.
          </Note>

          <DialogFooter className="pt-2">
            <Button type="button" variant="outline" onClick={onClose} disabled={busy}>
              Cancel
            </Button>
            <Button type="submit" disabled={busy}>
              Save credentials
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

/* -------------------------------------------------------- activation flow */

/**
 * The most dangerous control in QCP.
 *
 * Activating a number is what lets QCP address Meta as that sender. The
 * fleet's existing products still send on these same numbers through their
 * own integrations, so until a product has actually been migrated, activating
 * here adds a *second* sender to a live number — which is what puts its
 * quality rating and messaging limit at risk. That is stated here, at the
 * click, rather than in a runbook nobody has open.
 */
function ActivationDialog({
  account,
  anyProductEnabled,
  onClose,
  onSaved,
}: {
  account: QcpAccount;
  anyProductEnabled: boolean;
  onClose: () => void;
  onSaved: () => void;
}) {
  const { write, busy } = useQcpWrite();
  const toast = useToast();
  const [typed, setTyped] = React.useState("");
  const [reason, setReason] = React.useState("");
  const [refusal, setRefusal] = React.useState<QcpRefusal | null>(null);

  const activating = !account.is_active;
  const phrase = account.slug;
  const confirmed = typed.trim() === phrase;
  // `AccountEnableIn.justification` is min_length=8 and mandatory. Enforced
  // here so the operator is stopped by a disabled button and a visible
  // requirement rather than by a 422 after they have committed to the click.
  const justified = reason.trim().length >= 8;

  async function submit() {
    const res = activating
      ? await write(QCP.accountEnable(account.slug), {
          method: "POST",
          body: { confirm_slug: typed.trim(), justification: reason.trim() },
        })
      : await write(QCP.accountDisable(account.slug), { method: "POST" });
    if (!res.ok) {
      setRefusal(res.refusal);
      return;
    }
    toast.success(
      activating ? `${account.name} is now active` : `${account.name} is now inactive`,
      activating
        ? "QCP can address Meta from this number. Delivery still depends on the environment switch and the delivery setting."
        : "QCP will not address Meta from this number."
    );
    onSaved();
    onClose();
  }

  return (
    <Dialog open onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>
            {activating ? "Activate" : "Deactivate"} {account.name}
            {account.display_phone ? ` (${account.display_phone})` : ""}?
          </DialogTitle>
          <DialogDescription>
            {activating
              ? "This is the switch that lets QCP speak to Meta as this sender."
              : "QCP stops addressing Meta from this number. Queued messages for it will be suppressed rather than sent."}
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-4 max-h-[70vh] overflow-y-auto pr-1">
          {refusal && (
            <RefusalBanner refusal={refusal} onDismiss={() => setRefusal(null)} />
          )}

          {activating ? (
            <>
              <div className="rounded-xl border-2 border-amber-300 bg-amber-50 p-4 text-amber-900">
                <div className="flex items-start gap-2">
                  <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                  <div className="text-xs">
                    <div className="text-sm font-semibold">
                      This number is already in production use by the fleet.
                    </div>
                    <ul className="mt-2 grid list-disc gap-1.5 pl-4">
                      <li>
                        <strong>No product has migrated to QCP yet.</strong> QuataPay,
                        QuataFood, Abaqwa and QuataTrade still send on this number
                        through their own integrations.
                      </li>
                      <li>
                        Activating adds QCP as a <strong>second sender</strong> on a live
                        number. Two senders on one number is what gets a number
                        throttled: Meta drops its quality rating and then its messaging
                        limit, and that applies to the existing products&apos; traffic
                        too — not just QCP&apos;s.
                      </li>
                      <li>
                        {account.purpose === "authentication" ? (
                          <>
                            This is <strong>Quata Verify</strong>. If it gets throttled,
                            login codes stop arriving across the whole fleet.
                          </>
                        ) : (
                          <>
                            This is <strong>QUATA</strong>, which carries support and
                            order updates for every product.
                          </>
                        )}
                      </li>
                      <li>
                        Activation is reversible in this console, but a quality-rating
                        drop at Meta is not — it decays back over days.
                      </li>
                    </ul>
                  </div>
                </div>
              </div>

              <div className="grid gap-2 rounded-xl border border-border bg-surface-soft p-3.5 text-xs">
                <div className="font-medium text-foreground">
                  What activation does and does not do
                </div>
                <div className="flex items-start gap-2">
                  <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-600" />
                  <span>QCP may authenticate to Meta as this number.</span>
                </div>
                <div className="flex items-start gap-2">
                  <MinusCircle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-slate-400" />
                  <span>
                    It does <strong>not</strong> turn on delivery — the environment
                    switch and <code>whatsapp.delivery_enabled</code> are separate and
                    are not reachable from this console.
                  </span>
                </div>
                <div className="flex items-start gap-2">
                  <MinusCircle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-slate-400" />
                  <span>
                    It does <strong>not</strong> enable any product.{" "}
                    {anyProductEnabled
                      ? "At least one product is already enabled, so traffic can begin as soon as the remaining gates open."
                      : "No product is enabled, so nothing can ask QCP to send even after this."}
                  </span>
                </div>
              </div>

              {!account.configured && (
                <RefusalBanner
                  refusal={{
                    title: "Blocked — credentials incomplete",
                    detail:
                      "This number has no usable phone number id, WABA id or access token. Configure it first; activating it would just produce authentication failures against Meta.",
                    policy: true,
                  }}
                />
              )}

              <div className="grid gap-2">
                <Label htmlFor="activation-reason">
                  Why — required, recorded in the audit log
                </Label>
                <Textarea
                  id="activation-reason"
                  rows={2}
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  aria-invalid={reason.length > 0 && !justified}
                  placeholder="e.g. migrating QuataPay OTP to QCP, approved in the 2026-08-11 change window"
                />
                <p className="text-[11px] text-muted-foreground">
                  At least 8 characters. This is the field that makes &ldquo;who
                  turned {account.name} on, and what for&rdquo; answerable months from
                  now.
                </p>
              </div>

              <TypeToConfirm
                phrase={phrase}
                value={typed}
                onChange={setTyped}
                label="This cannot be done by accident."
              />
            </>
          ) : (
            <>
              <Note tone="warn">
                Deactivating is the safe direction: QCP stops addressing Meta from this
                number. Anything already queued for it will be suppressed with a reason
                rather than sent, and will show up under Recent failures. Credentials
                are left in place deliberately, so switching it back on is one click.
              </Note>
            </>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button
            variant={activating ? "destructive" : "default"}
            disabled={
              busy || (activating && (!confirmed || !justified || !account.configured))
            }
            onClick={submit}
          >
            <KeyRound className="h-3.5 w-3.5" />
            {activating ? `Activate ${account.name}` : `Deactivate ${account.name}`}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
