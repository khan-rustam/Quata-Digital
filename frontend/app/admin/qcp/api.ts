"use client";

/**
 * The one place the QCP console knows what the backend's write surface looks
 * like.
 *
 * Every path, payload type and refusal code the five screens use lives here
 * and nowhere else, so a route that moves is an edit to `QCP` and
 * `explainQcpRefusal` below rather than a sweep through every screen. The
 * write surface spans two backend modules — `routes_admin_whatsapp.py` for
 * accounts, products and conversations, `routes_admin_templates.py` for
 * templates and routing — which is invisible from here on purpose.
 *
 * Three properties this module is responsible for:
 *
 * 1. **No secret ever travels back.** `stripSecrets` is applied to every write
 *    response before it reaches a screen, so even if a future backend build
 *    accidentally echoes an `access_token`, this console cannot render it. The
 *    one deliberate exception is a freshly minted product key, which is
 *    handled by `mintProductKey` and is show-once by construction.
 * 2. **A refusal is not an error.** QCP refuses writes on purpose — a
 *    marketing template on Quata Verify, an unapproved template in a routing
 *    rule, an account with no credentials. Those come back as 4xx and must
 *    read as a policy decision with a next action, never as a stack trace and
 *    never as "something went wrong".
 * 3. **Nothing here switches QCP on as a side effect.** Activation and
 *    enablement are their own explicit calls, made only from their own
 *    confirmation flows.
 */

import * as React from "react";
import { ApiError } from "@/lib/api";
import { useApiAction } from "@/lib/use-api";

/* ----------------------------------------------------------------- paths */

/**
 * Endpoint map. Grouped by resource, not by which backend module serves it —
 * the split between the two route files is a backend concern.
 */
const enc = encodeURIComponent;

export const QCP = {
  overview: "/admin/qcp/overview",

  // Accounts — routes_admin_whatsapp.py
  accountCredentials: (slug: string) => `/admin/qcp/accounts/${enc(slug)}/credentials`,
  accountEnable: (slug: string) => `/admin/qcp/accounts/${enc(slug)}/enable`,
  accountDisable: (slug: string) => `/admin/qcp/accounts/${enc(slug)}/disable`,
  accountTestConnection: (slug: string) =>
    `/admin/qcp/accounts/${enc(slug)}/test-connection`,

  // Templates — routes_admin_templates.py
  templates: "/admin/qcp/templates",
  template: (id: number) => `/admin/qcp/templates/${id}`,
  templateRetire: (id: number) => `/admin/qcp/templates/${id}/retire`,
  templateAlerts: "/admin/qcp/templates/alerts",
  /** Sync is per number: Meta's template list is a property of one WABA. */
  templateSync: (slug: string) => `/admin/qcp/accounts/${enc(slug)}/templates/sync`,

  // Products — routes_admin_whatsapp.py
  products: "/admin/qcp/products",
  /** PATCH — name / description / rate limit. Never the gates. */
  product: (slug: string) => `/admin/qcp/products/${enc(slug)}`,
  productPurposes: (slug: string) => `/admin/qcp/products/${enc(slug)}/purposes`,
  productGrantAuthentication: (slug: string) =>
    `/admin/qcp/products/${enc(slug)}/purposes/authentication`,
  productApiKey: (slug: string) => `/admin/qcp/products/${enc(slug)}/api-key`,
  productEnable: (slug: string) => `/admin/qcp/products/${enc(slug)}/enable`,
  productDisable: (slug: string) => `/admin/qcp/products/${enc(slug)}/disable`,

  // Routing — routes_admin_templates.py
  routingRules: "/admin/qcp/routing-rules",
  routingRule: (id: number) => `/admin/qcp/routing-rules/${id}`,
  routingRuleActivate: (id: number) => `/admin/qcp/routing-rules/${id}/activate`,
  routingRuleDeactivate: (id: number) => `/admin/qcp/routing-rules/${id}/deactivate`,

  conversationReassign: (id: number) => `/admin/qcp/conversations/${id}/reassign`,
} as const;

/* ----------------------------------------------------------------- types */

/** A routing rule, as `registry.rule_out` reports it. */
export type QcpRoutingRule = {
  id: number;
  product_id: number | null;
  product: string | null;
  intent: string;
  purpose: "authentication" | "engagement";
  template_intent: string;
  locale: string | null;
  priority: number;
  /** The stored switch. NOT what the screen should call "live". */
  is_active: boolean;
  /**
   * The world moved underneath this rule: its product is no longer entitled
   * to the purpose it routes to, so it carries no traffic however the switch
   * reads. Computed server-side by `registry.blocked_state`.
   */
  is_blocked: boolean;
  blocked_reason: string | null;
  blocked_detail: string | null;
  /** `is_active && !is_blocked` — the only honest "live". */
  is_effectively_live: boolean;
  fallback_channel: string | null;
  conditions: Record<string, unknown>;
  created_at: string | null;
  updated_at: string | null;
};

export type QcpRoutingResponse = { items: QcpRoutingRule[] };

/**
 * A guard evaluation from the backend, attached to a create/update/activate
 * response and to `/routing-rules/coverage`.
 *
 * The three severities are `registry.check_rule`'s, not invented here, and the
 * middle one is the interesting one:
 *
 * - `error`      — refused outright; the rule was not written.
 * - `activation` — the rule may exist but may not be switched on. QCP is
 *                  dormant by design, so preparing a rule against a template
 *                  Meta has not approved yet is legitimate; sending with it is
 *                  not.
 * - `warning`    — reported only. "No live number for this purpose" is the
 *                  normal state today.
 */
export type QcpRuleProblem = {
  code: string;
  severity: "error" | "activation" | "warning";
  detail: string;
};

/** `ConnectionTestOut`. `sent_message` is pinned false in the contract. */
export type QcpConnectionTest = {
  ok: boolean;
  health: string;
  quality_rating: string | null;
  messaging_limit: string | null;
  verified_name: string | null;
  error: string | null;
  sent_message: false;
};

/**
 * One sync alert.
 *
 * The same shape whether it arrives in a sync response's `alerts` or from
 * `/templates/alerts` — the backend flattens the stored audit detail so the
 * standing list names the template, the number and the reason exactly as the
 * sync that produced it did. `kind` is the stable code (`code` is tolerated so
 * an older backend still renders).
 */
export type QcpTemplateAlert = {
  kind?: string;
  code?: string;
  detail?: string;
  template?: string;
  account?: string;
  created_at?: string | null;
  [k: string]: unknown;
};

/** `templates.sync_from_meta` — Meta is the authority; this is what it said. */
export type QcpSyncResult = {
  account?: string;
  fetched?: number;
  created?: number;
  updated?: number;
  unchanged?: number;
  alerts?: { code?: string; detail?: string; template?: string; [k: string]: unknown }[];
};

/**
 * `ApiKeyMintedOut` — the one response in QCP that carries a secret, once.
 *
 * `shown_once` is in the backend contract precisely so the console renders a
 * copy-it-now affordance rather than assuming it can re-read the value.
 */
export type QcpMintedKey = {
  api_key: string;
  prefix: string;
  fingerprint: string;
  shown_once: true;
  notice: string;
  product: { slug: string; name: string; has_api_key: boolean };
};

/* ------------------------------------------------- secrets never come back */

/**
 * Field names that must never reach a rendered screen.
 *
 * The backend's read shapes already return booleans (`has_access_token`), so
 * this should never strip anything. It exists because "should never" is not
 * "cannot": one careless `**row.__dict__` on the write path would otherwise
 * put a live Meta token into a React tree, a browser devtools pane and every
 * error reporter in front of it.
 */
export const SECRET_FIELDS = [
  "access_token",
  "app_secret",
  "webhook_verify_token",
  "verify_token",
  "webhook_secret",
  "api_key_hash",
  "access_token_encrypted",
  "app_secret_encrypted",
  "webhook_verify_token_encrypted",
  "webhook_secret_encrypted",
] as const;

/** Recursively drop secret-named keys from an API response. */
export function stripSecrets<T>(value: T): T {
  if (Array.isArray(value)) {
    return value.map((v) => stripSecrets(v)) as unknown as T;
  }
  if (value && typeof value === "object") {
    const out: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(value as Record<string, unknown>)) {
      if ((SECRET_FIELDS as readonly string[]).includes(k)) continue;
      out[k] = stripSecrets(v);
    }
    return out as T;
  }
  return value;
}

/* --------------------------------------------------------------- refusals */

export type QcpRefusal = {
  /** Short headline for a toast or an inline banner. */
  title: string;
  /** What actually happened and what to do about it, in a sentence. */
  detail: string;
  /**
   * True when QCP decided this on purpose (a 4xx). False means QCP broke —
   * a 5xx, a network failure — which is a different conversation entirely
   * and must not be dressed up as a policy decision.
   */
  policy: boolean;
  /** The backend's stable refusal code, when it sent one. */
  code?: string;
  /** Guard evaluations the backend attached to the refusal. */
  problems?: QcpRuleProblem[];
};

/**
 * Headlines for the refusal codes the templates and routing services raise.
 *
 * Only the *headline* is ours. The backend's own sentence is always shown
 * underneath it, because that sentence is written against the row that was
 * actually refused and is more specific than anything this table can say. A
 * code missing from here still produces a readable refusal — it just gets a
 * generic headline.
 */
const REFUSAL_TITLES: Record<string, string> = {
  non_auth_template_on_verify: "Refused — that category cannot live on Quata Verify",
  non_auth_category_on_verify: "Refused — that category cannot live on Quata Verify",
  auth_template_off_verify: "Refused — authentication belongs on Quata Verify",
  auth_traffic_on_engagement_number: "Refused — security codes cannot go out on QUATA",
  invalid_category: "Refused — not a Meta category",
  missing_template_category: "Refused — no category",
  category_is_owned_by_meta: "Refused — Meta owns the category now",
  field_not_editable: "Refused — that field cannot be edited",
  constraint_refused: "Refused by the database",
  template_not_approved: "Refused — template is not approved",
  no_template_for_intent: "Refused — nothing to route to",
  no_account_for_purpose: "Refused — no number for that purpose",
  purpose_not_permitted: "Refused — the product may not reach that number",
  product_disabled: "Refused — the product is disabled",
  duplicate_rule: "Refused — a rule already covers this",
  invalid_purpose: "Refused — not a valid purpose",
  invalid_fallback_channel: "Refused — not a valid fallback channel",
};

/**
 * Turn a backend refusal into something a human can act on.
 *
 * The templates and routing services return `409 {reason, detail, problems?}`
 * — a stable code plus a sentence written against the specific row. That is
 * the good case and it is passed through nearly untouched. Everything else
 * (a 422 from a Pydantic model, a 403, a network failure) is normalised into
 * the same shape so no screen has to branch on how it failed.
 *
 * The one distinction that is never blurred: `policy` is false for a 5xx or a
 * transport failure. A refusal is a decision QCP made; a crash is not, and
 * presenting one as the other teaches an operator to ignore both.
 */
export function explainQcpRefusal(err: unknown): QcpRefusal {
  if (!(err instanceof ApiError)) {
    return {
      title: "Couldn't reach QCP",
      detail:
        err instanceof Error
          ? `${err.message}. Nothing was changed. This is a network or server problem, not a refusal.`
          : "Nothing was changed. This is a network or server problem, not a refusal.",
      policy: false,
    };
  }

  const { message: raw, code, problems } = serverMessage(err);

  if (err.status >= 500) {
    return {
      title: "QCP failed on that write",
      detail:
        `${raw} — this came back as a ${err.status}, which means QCP crashed rather than ` +
        "refused. A refusal is expected to be a clear 4xx with a reason; treat this as a bug.",
      policy: false,
    };
  }

  if (code && REFUSAL_TITLES[code]) {
    return { title: REFUSAL_TITLES[code], detail: `${raw} Nothing was written.`, policy: true, code, problems };
  }

  if (err.status === 403) {
    // Do NOT name a permission here. Reads and most writes take
    // `settings:manage`, but the five fleet-reaching routes — switching a
    // number on or off, minting/revoking a gateway key, granting the
    // authentication purpose — take `whatsapp:operate` instead, and this
    // branch used to tell an Admin to go and get the one they already hold.
    // FastAPI's own detail names the permission it wanted; `raw` is that
    // sentence.
    return {
      title: "Not allowed",
      detail: `${raw} Ask a Super Admin, or someone holding the permission named above.`,
      policy: true,
      code,
    };
  }
  if (err.status === 404) {
    return {
      title: "Not found",
      detail: `${raw} It may have been deleted since this screen loaded — refresh and try again.`,
      policy: true,
      code,
    };
  }
  if (err.status === 422) {
    return {
      title: "Refused — invalid input",
      detail: `${raw} Nothing was written.`,
      policy: true,
      code,
    };
  }
  if (err.status === 409) {
    return {
      title: "Refused",
      detail: `${raw} Nothing was written.`,
      policy: true,
      code,
      problems,
    };
  }

  return { title: "Refused", detail: `${raw} Nothing was written.`, policy: true, code, problems };
}

/**
 * Pull the human part, the stable code and any guard problems out of
 * FastAPI's several detail shapes.
 *
 * A stated refusal is always `HTTPException(409, {reason, <sentence>, ...})`
 * nested one level under FastAPI's own `detail` key — but the two backend
 * modules do not agree on what the sentence is called, and both have to
 * render:
 *
 *   * `routes_admin_templates.py` (`_refused`) sends
 *     `{"reason": code, "detail": sentence, "problems": [...]}`.
 *   * `routes_admin_whatsapp.py` (`_deny`) sends
 *     `{"reason": code, "message": sentence, ...obstacle}` — `message` is
 *     specifically the key it strips before writing the audit row, which is
 *     why it is not called `detail` there.
 *
 * Both keys are read, because that sentence is the entire actionable content
 * of a refusal: it names the fields that are missing, the account that is
 * already live, the product that already owns the thread. Falling back to
 * "QCP refused this: not_configured." throws exactly the instruction away —
 * and every refusal on the account and product write paths (activating a
 * number, minting or revoking a key, granting Quata Verify) comes from the
 * module that uses `message`.
 */
function serverMessage(err: ApiError): {
  message: string;
  code?: string;
  problems?: QcpRuleProblem[];
} {
  const outer = err.detail as unknown;
  const inner =
    outer && typeof outer === "object"
      ? (outer as { detail?: unknown }).detail
      : undefined;

  // The stated-refusal shape: {reason, detail|message, problems?}
  if (inner && typeof inner === "object" && !Array.isArray(inner)) {
    const o = inner as {
      reason?: unknown;
      detail?: unknown;
      message?: unknown;
      problems?: unknown;
    };
    const sentence =
      typeof o.detail === "string"
        ? o.detail
        : typeof o.message === "string"
          ? o.message
          : undefined;
    if (typeof o.reason === "string" || sentence !== undefined) {
      return {
        message: sentence ?? `QCP refused this: ${String(o.reason)}.`,
        code: typeof o.reason === "string" ? o.reason : undefined,
        problems: Array.isArray(o.problems)
          ? (o.problems as QcpRuleProblem[])
          : undefined,
      };
    }
  }

  return { message: plainMessage(err) };
}

function plainMessage(err: ApiError): string {
  const d = err.detail as unknown;
  if (typeof d === "string") return d;
  if (d && typeof d === "object") {
    const detail = (d as { detail?: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      const parts = detail
        .map((item) => {
          if (typeof item === "string") return item;
          const msg = (item as { msg?: unknown })?.msg;
          const loc = (item as { loc?: unknown[] })?.loc;
          const field = Array.isArray(loc) ? loc[loc.length - 1] : undefined;
          return typeof msg === "string"
            ? field
              ? `${String(field)}: ${msg}`
              : msg
            : null;
        })
        .filter(Boolean);
      if (parts.length) return parts.join("; ");
    }
    const reason = (d as { reason?: unknown }).reason;
    if (typeof reason === "string") return reason;
  }
  return err.message;
}

/* ------------------------------------------------------------ write hook */

export type WriteResult<T> =
  | { ok: true; data: T }
  | { ok: false; refusal: QcpRefusal };

/**
 * The write half of `useApi`.
 *
 * Returns a discriminated result instead of throwing, because every QCP write
 * has a refusal path that the *screen* has to render inline (next to the field
 * that caused it) rather than swallow in a catch. `busy` is exposed so a
 * dangerous button can disable itself for the whole round trip.
 */
export function useQcpWrite() {
  const action = useApiAction();
  const [busy, setBusy] = React.useState(false);

  const write = React.useCallback(
    async <T,>(
      path: string,
      init: { method: string; body?: unknown } = { method: "POST" }
    ): Promise<WriteResult<T>> => {
      setBusy(true);
      try {
        const data = await action<T>(path, {
          method: init.method,
          ...(init.body === undefined ? {} : { body: JSON.stringify(init.body) }),
        });
        return { ok: true, data: stripSecrets(data) };
      } catch (err) {
        return { ok: false, refusal: explainQcpRefusal(err) };
      } finally {
        setBusy(false);
      }
    },
    [action]
  );

  /**
   * Minting is the one call whose response legitimately carries a secret, so
   * it deliberately bypasses `stripSecrets`. It is separate from `write` so
   * that bypass is one named function rather than a flag anyone could pass.
   */
  const mintProductKey = React.useCallback(
    async (slug: string): Promise<WriteResult<QcpMintedKey>> => {
      setBusy(true);
      try {
        const data = await action<QcpMintedKey>(QCP.productApiKey(slug), {
          method: "POST",
        });
        return { ok: true, data };
      } catch (err) {
        return { ok: false, refusal: explainQcpRefusal(err) };
      } finally {
        setBusy(false);
      }
    },
    [action]
  );

  return { write, mintProductKey, busy };
}

/* ---------------------------------------------------------------- payload */

/**
 * Build a credential patch.
 *
 * A blank credential box means "leave it alone", never "clear it" — an
 * operator who opens the dialog to fix a typo in the WABA id must not wipe the
 * access token by not retyping it. Clearing is a separate, explicit act.
 */
export function credentialPatch(
  entries: Record<string, string | undefined | null>
): Record<string, string> {
  const out: Record<string, string> = {};
  for (const [k, v] of Object.entries(entries)) {
    const trimmed = (v ?? "").trim();
    if (trimmed) out[k] = trimmed;
  }
  return out;
}

/**
 * A short, non-reversible fingerprint of a value the operator just typed, for
 * the "old → new" line in the audit trail they are about to create. It is
 * never the value and is only ever computed over something already in the
 * browser's memory.
 */
export async function fingerprint(value: string): Promise<string> {
  if (!value) return "—";
  try {
    const bytes = new TextEncoder().encode(value);
    const digest = await crypto.subtle.digest("SHA-256", bytes);
    return Array.from(new Uint8Array(digest))
      .slice(0, 4)
      .map((b) => b.toString(16).padStart(2, "0"))
      .join("");
  } catch {
    return "—";
  }
}
