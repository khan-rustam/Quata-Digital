"use client";

/**
 * Shared pieces for the four QCP console screens.
 *
 * QCP is the single WhatsApp backbone for every QUATA product. Two Meta
 * numbers exist and the separation between them is the whole point:
 * **Quata Verify** carries authentication only, **QUATA** carries everything
 * else. The console's job is to make that separation, and the system's
 * dormancy, legible at a glance.
 *
 * The most important thing here is `LoadState`. QCP ships switched off —
 * nothing configured, no products enabled, no messages ever sent — so
 * "empty" is the *correct* state, not a failure. Every screen distinguishes
 * loading, failed-to-load and correctly-empty, because a screen that looks
 * broken when it is right gets someone to "fix" a working system.
 */

import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  AlertTriangle,
  Blocks,
  Check,
  Copy,
  FileCheck2,
  Gauge,
  Headset,
  Inbox,
  Loader2,
  Lock,
  ShieldCheck,
  Waypoints,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";
import type { QcpRefusal } from "./api";

/* ------------------------------------------------------------------ types */

export type QcpAccount = {
  id: number;
  slug: string;
  name: string;
  purpose: "authentication" | "engagement";
  display_phone: string | null;
  api_version: string;
  is_active: boolean;
  health: "unknown" | "ok" | "degraded" | "unauthorized";
  quality_rating: string | null;
  messaging_limit: string | null;
  last_checked_at: string | null;
  last_error: string | null;
  has_phone_number_id: boolean;
  has_waba_id: boolean;
  has_access_token: boolean;
  has_app_secret: boolean;
  has_verify_token: boolean;
  configured: boolean;
  /**
   * Configuration states that are a security posture, not a blank field.
   *
   * `critical` means the platform is currently *less safe* than it looks, and
   * the card must not render it with the same weight as "display name not
   * set". The one that exists today: while `phone_number_id` is unset the
   * webhook skips cross-number attribution, and both numbers normally share
   * one Meta app — so a correctly signed QUATA envelope is accepted at the
   * Quata Verify webhook.
   */
  security: { code: string; severity: "critical" | "warning"; message: string }[];
};

export type QcpProduct = {
  id: number;
  slug: string;
  name: string;
  description: string | null;
  is_enabled: boolean;
  has_api_key: boolean;
  api_key_prefix: string | null;
  allowed_purposes: string[];
  default_locale: string;
  rate_limit_per_minute: number;
  // No callback-webhook fields. QCP has no outbound callback path, nothing
  // ever wrote whatsapp_products.webhook_url, and the row the console used to
  // render was a permanent "not configured" that read as a feature waiting to
  // be switched on.
  registry_version: string | null;
  last_seen_at: string | null;
  created_at: string | null;
};

export type QcpProductRegistryItem = QcpProduct & {
  routing_rules: number;
  routing_rules_active: number;
  templates: number;
  messages: number;
};

export type QcpOverview = {
  window_hours: number;
  gates: {
    env_enabled: boolean;
    delivery_enabled: boolean;
    any_account_active: boolean;
    any_product_enabled: boolean;
    require_signature: boolean;
  };
  accounts: QcpAccount[];
  products: QcpProduct[];
  queue: {
    queued: number;
    oldest_queued_at: string | null;
    failed: number;
    suppressed: number;
    total: number;
  };
  recent: {
    total: number;
    sent: number;
    queued: number;
    failed: number;
    suppressed: number;
  };
  templates: {
    total: number;
    approved: number;
    pending_approval: number;
    rejected: number;
  };
  conversations: { total: number; open: number };
  failures: {
    message_uid: string;
    status: string;
    intent: string | null;
    product: string | null;
    to: string | null;
    attempts: number;
    max_attempts: number;
    error_code: string | null;
    last_error: string | null;
    suppressed_reason: string | null;
    created_at: string | null;
  }[];
  denials: {
    id: number;
    action: string;
    outcome: string;
    reason: string | null;
    product: string | null;
    resource_type: string;
    resource_id: string | null;
    created_at: string | null;
  }[];
};

export type QcpConversation = {
  id: number;
  phone_e164: string;
  display_name: string | null;
  state: "open" | "snoozed" | "closed";
  product: string | null;
  account: string | null;
  account_name: string | null;
  account_purpose: "authentication" | "engagement" | null;
  assignee_id: number | null;
  unread_count: number;
  locale: string | null;
  last_inbound_at: string | null;
  last_outbound_at: string | null;
  service_window_expires_at: string | null;
  service_window_open: boolean;
  created_at: string | null;
};

export type QcpMessage = {
  id: number;
  message_uid: string;
  direction: "inbound" | "outbound";
  kind: string;
  status: string;
  intent: string | null;
  product: string | null;
  account_purpose: string;
  body: string | null;
  variables: Record<string, unknown>;
  to: string | null;
  from: string | null;
  attempts: number;
  max_attempts: number;
  error_code: string | null;
  last_error: string | null;
  suppressed_reason: string | null;
  created_at: string | null;
  sent_at: string | null;
  delivered_at: string | null;
  read_at: string | null;
  failed_at: string | null;
};

export type QcpTemplate = {
  id: number;
  name: string;
  language: string;
  category: "authentication" | "marketing" | "utility";
  intent: string;
  status: string;
  account: string | null;
  account_name: string | null;
  account_purpose: "authentication" | "engagement";
  account_is_active: boolean;
  product: string | null;
  variables: string[];
  provider_template_id: string | null;
  rejection_reason: string | null;
  last_synced_at: string | null;
  created_at: string | null;
  misbound: boolean;
};

/* ------------------------------------------------------------------- nav */

const TABS = [
  { href: "/admin/qcp", label: "Overview", icon: Gauge },
  { href: "/admin/qcp/conversations", label: "Conversations", icon: Inbox },
  { href: "/admin/qcp/agent", label: "Agent", icon: Headset },
  { href: "/admin/qcp/templates", label: "Templates", icon: FileCheck2 },
  { href: "/admin/qcp/routing", label: "Routing", icon: Waypoints },
  { href: "/admin/qcp/products", label: "Registry", icon: Blocks },
];

export function QcpTabs() {
  const pathname = usePathname();
  return (
    <div className="mb-6 flex flex-wrap items-center gap-1 rounded-full border border-border bg-surface-soft p-1 text-sm w-fit">
      {TABS.map((t) => {
        // Exact match for the overview so it doesn't light up on every child.
        const active =
          t.href === "/admin/qcp"
            ? pathname === t.href
            : pathname === t.href || pathname.startsWith(t.href + "/");
        return (
          <Link
            key={t.href}
            href={t.href}
            className={cn(
              "inline-flex items-center gap-2 whitespace-nowrap rounded-full px-3.5 py-1.5 font-medium transition-colors",
              active
                ? "bg-surface text-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground"
            )}
          >
            <t.icon className="h-3.5 w-3.5" />
            {t.label}
          </Link>
        );
      })}
    </div>
  );
}

/* ------------------------------------------------------- load / error UI */

export function Loading({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 text-sm text-muted-foreground">
      <Loader2 className="h-4 w-4 animate-spin" /> {label}
    </div>
  );
}

/**
 * Failure to reach QCP. Deliberately worded so it cannot be mistaken for
 * "QCP is off" — those are different problems with different fixes.
 */
export function LoadError({ error, onRetry }: { error: Error; onRetry?: () => void }) {
  return (
    <div className="rounded-2xl border border-rose-200 bg-rose-50 p-5 text-rose-900">
      <div className="flex items-start gap-2">
        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
        <div className="min-w-0">
          <div className="text-sm font-semibold">Couldn&apos;t load this screen</div>
          <p className="mt-1 text-xs break-words">
            {error.message}. This is a problem reaching the QCP API — it is not the
            same as QCP being switched off.
          </p>
          {onRetry && (
            <button
              onClick={onRetry}
              className="mt-3 rounded-lg border border-rose-300 px-2.5 py-1 text-xs font-medium hover:bg-rose-100"
            >
              Try again
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

/** Neutral note for a state that is correct but might read as broken. */
export function Note({
  tone = "info",
  children,
}: {
  tone?: "info" | "warn";
  children: React.ReactNode;
}) {
  return (
    <div
      className={cn(
        "flex items-start gap-2 rounded-xl border p-3.5 text-xs",
        tone === "warn"
          ? "border-amber-200 bg-amber-50 text-amber-900"
          : "border-border bg-surface-soft text-muted-foreground"
      )}
    >
      {tone === "warn" ? (
        <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
      ) : (
        <ShieldCheck className="mt-0.5 h-3.5 w-3.5 shrink-0" />
      )}
      <div className="min-w-0">{children}</div>
    </div>
  );
}

/* ---------------------------------------------------------------- badges */

type BadgeTone = "default" | "success" | "warn" | "danger" | "brand" | "outline";

export const MESSAGE_STATUS_TONE: Record<string, BadgeTone> = {
  queued: "warn",
  sending: "warn",
  sent: "brand",
  delivered: "success",
  read: "success",
  failed: "danger",
  suppressed: "default",
};

export const TEMPLATE_STATUS_TONE: Record<string, BadgeTone> = {
  draft: "outline",
  pending_approval: "warn",
  approved: "success",
  rejected: "danger",
  paused: "default",
  disabled: "default",
};

export const HEALTH_TONE: Record<string, BadgeTone> = {
  ok: "success",
  degraded: "warn",
  unauthorized: "danger",
  unknown: "default",
};

export function StatusBadge({
  value,
  tones,
  className,
}: {
  value: string;
  tones: Record<string, BadgeTone>;
  className?: string;
}) {
  return (
    <Badge variant={tones[value] ?? "default"} className={className}>
      {value.replace(/_/g, " ")}
    </Badge>
  );
}

function purposeClass(purpose: string) {
  return purpose === "authentication"
    ? "border-violet-300 bg-violet-50 text-violet-900"
    : "border-sky-300 bg-sky-50 text-sky-900";
}

/**
 * Names the number a purpose resolves to. Use where the account itself is
 * not on screen — a conversation row, a product's allowed purposes — so the
 * reader learns *which* number is involved.
 */
export function PurposeBadge({ purpose }: { purpose: string | null }) {
  if (!purpose) return <span className="text-muted-foreground">—</span>;
  return (
    <Badge variant="outline" className={cn("font-medium", purposeClass(purpose))}>
      {purpose === "authentication" ? "Quata Verify" : "QUATA"}
    </Badge>
  );
}

/**
 * Names the purpose itself, in Meta's vocabulary. Use next to an account's
 * own name, where `PurposeBadge` would just repeat it — the two accounts are
 * literally called "Quata Verify" and "QUATA".
 */
export function PurposeChip({ purpose }: { purpose: string }) {
  return (
    <Badge variant="outline" className={cn("font-medium", purposeClass(purpose))}>
      {purpose}
    </Badge>
  );
}

/* --------------------------------------------------------------- helpers */

/**
 * Parse a timestamp from the QCP API.
 *
 * Every QCP column is `DateTime(timezone=True)` and every writer uses
 * `datetime.now(timezone.utc)`, so these instants are always UTC. Postgres
 * round-trips the offset; SQLite does not, so in dev the API emits a bare
 * `2026-08-11T05:41:13` with no `Z`. `new Date()` reads that as *local*
 * time, which silently shifts every timestamp by the viewer's offset — and
 * on a screen whose job is "is it working", a relative time that is hours
 * wrong is worse than no time at all. Assume UTC when no zone is stated.
 */
function parseUtc(value: string) {
  const hasZone = /(?:Z|[+-]\d{2}:?\d{2})$/.test(value);
  return new Date(hasZone ? value : `${value}Z`);
}

export function fmt(value: string | null | undefined) {
  if (!value) return "—";
  const d = parseUtc(value);
  return Number.isNaN(d.getTime()) ? "—" : d.toLocaleString();
}

export function relative(value: string | null | undefined) {
  if (!value) return "—";
  const d = parseUtc(value).getTime();
  if (Number.isNaN(d)) return "—";
  const mins = Math.round((Date.now() - d) / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.round(hrs / 24)}d ago`;
}

/* ------------------------------------------------------- the one rule */

export const CATEGORIES = ["authentication", "utility", "marketing"] as const;
export type QcpCategory = (typeof CATEGORIES)[number];

export const CATEGORY_STYLE: Record<string, string> = {
  authentication: "border-violet-300 bg-violet-50 text-violet-900",
  marketing: "border-orange-300 bg-orange-50 text-orange-900",
  utility: "border-slate-300 bg-slate-50 text-slate-700",
};

/**
 * Whether a Meta category may sit on a number of this purpose.
 *
 * This is the single most important predicate in the console, and it is
 * defined once so the create form, the edit form and the list all agree.
 * It mirrors `_is_misbound` in `routes_admin_whatsapp.py` and the three
 * CHECK constraints underneath it: **Quata Verify takes `authentication`
 * and nothing else — not even `utility`** — and `authentication` may not
 * sit anywhere but Quata Verify.
 */
export function categoryAllowedOn(category: string, purpose: string): boolean {
  return purpose === "authentication"
    ? category === "authentication"
    : category !== "authentication";
}

/** Why a category/number pairing is refused, in a sentence an operator can act on. */
export function separationReason(category: string, purpose: string): string | null {
  if (categoryAllowedOn(category, purpose)) return null;
  return purpose === "authentication"
    ? `Quata Verify is the authentication number. A ${category} template cannot live there — Meta restricts numbers that mix the two, and the database refuses the row outright. Put it on QUATA.`
    : `An authentication template cannot live on QUATA. Security codes go out on Quata Verify and nowhere else.`;
}

/* --------------------------------------------------------- write-side UI */

/**
 * A refusal rendered where the operator caused it.
 *
 * QCP refuses writes on purpose. A refusal is a sentence with a next action
 * in it, and it is visually distinct from `LoadError` (which means the API
 * could not be reached at all) because those need different responses.
 */
export function RefusalBanner({
  refusal,
  onDismiss,
}: {
  refusal: QcpRefusal;
  onDismiss?: () => void;
}) {
  return (
    <div
      role="alert"
      className={cn(
        "rounded-xl border p-3.5 text-xs",
        refusal.policy
          ? "border-amber-300 bg-amber-50 text-amber-900"
          : "border-rose-300 bg-rose-50 text-rose-900"
      )}
    >
      <div className="flex items-start gap-2">
        <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
        <div className="min-w-0">
          <div className="text-sm font-semibold">{refusal.title}</div>
          <p className="mt-1 break-words">{refusal.detail}</p>
        </div>
        {onDismiss && (
          <button
            type="button"
            onClick={onDismiss}
            className="ml-auto shrink-0 text-[11px] underline"
          >
            Dismiss
          </button>
        )}
      </div>
    </div>
  );
}

/**
 * A write-only credential box.
 *
 * It has no `value` and no `defaultValue` and it never will. QCP stores these
 * Fernet-encrypted and the API returns a boolean, so there is nothing to
 * prefill even if we wanted to — what the operator gets is the *state* of the
 * secret (configured / not configured) and the ability to replace it. Blank
 * means "leave it alone"; see `credentialPatch`.
 */
export function SecretField({
  id,
  name,
  label,
  configured,
  hint,
}: {
  id: string;
  name: string;
  label: string;
  configured: boolean;
  hint?: string;
}) {
  return (
    <div className="grid gap-2">
      <div className="flex items-center gap-2">
        <Label htmlFor={id}>{label}</Label>
        <Badge variant={configured ? "success" : "warn"} className="text-[11px]">
          <Lock className="h-3 w-3" />
          {configured ? "Configured" : "Not configured"}
        </Badge>
      </div>
      <Input
        id={id}
        name={name}
        type="password"
        autoComplete="new-password"
        spellCheck={false}
        placeholder={
          configured ? "Leave blank to keep the stored value" : "Paste the value from Meta"
        }
      />
      <p className="text-[11px] text-muted-foreground">
        {hint ? `${hint} ` : ""}
        Stored encrypted. It is never returned by the API and never rendered here — the
        only thing you can do with a stored credential is replace it.
      </p>
    </div>
  );
}

/**
 * Type-to-confirm.
 *
 * Reserved for the two actions that change what QCP can do to the outside
 * world: activating a number, and rotating a live product key. A dialog you
 * can dismiss with a reflex click is not a gate.
 */
export function TypeToConfirm({
  phrase,
  value,
  onChange,
  label,
}: {
  phrase: string;
  value: string;
  onChange: (v: string) => void;
  label: string;
}) {
  const ok = value.trim() === phrase;
  return (
    <div className="grid gap-2">
      <Label htmlFor="qcp-confirm-phrase">
        {label} Type <code className="font-semibold">{phrase}</code> to continue.
      </Label>
      <Input
        id="qcp-confirm-phrase"
        value={value}
        autoComplete="off"
        onChange={(e) => onChange(e.target.value)}
        placeholder={phrase}
        aria-invalid={value.length > 0 && !ok}
      />
    </div>
  );
}

/** Copy-to-clipboard for a show-once value. */
export function CopyButton({ value, label = "Copy" }: { value: string; label?: string }) {
  const [copied, setCopied] = React.useState(false);
  return (
    <button
      type="button"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(value);
          setCopied(true);
          window.setTimeout(() => setCopied(false), 2000);
        } catch {
          setCopied(false);
        }
      }}
      className="inline-flex items-center gap-1.5 rounded-full border border-border bg-surface px-3 py-1 text-xs font-medium hover:bg-secondary"
    >
      {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
      {copied ? "Copied" : label}
    </button>
  );
}
