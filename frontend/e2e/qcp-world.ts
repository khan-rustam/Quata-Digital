/**
 * A fake QCP backend, driven from the browser.
 *
 * The QCP console's write screens have never been exercised by anything but a
 * human. The first human to exercise them would be doing it against Quata
 * Verify — the number that carries every login code in the fleet, and whose
 * restriction locks QuataFood users out of accounts that have no email
 * fallback. So the tests drive the real screens, in a real browser, against
 * this: an in-memory QCP that mirrors the two backend route modules closely
 * enough that a screen which passes here would behave the same against the
 * real one.
 *
 * The mirroring that matters is the *refusal* shapes, because they are not
 * the same in both modules and the console has to render both:
 *
 *   * `routes_admin_whatsapp.py` refuses with `409 {detail: {reason, message,
 *     …}}` — the human sentence is under `message`.
 *   * `routes_admin_templates.py` refuses with `409 {detail: {reason, detail,
 *     problems?}}` — the human sentence is under `detail`.
 *
 * Both are reproduced verbatim here (`denyAccounts` / `denyTemplates`) so a
 * console that only understands one of them fails a test rather than shipping.
 *
 * Nothing in this file is a real credential. `FAKE_*` values are literal
 * strings invented for the test and exist so a test can assert that a value
 * the operator typed is never rendered back — which requires knowing what to
 * search the DOM for.
 */

import type { Page } from "@playwright/test";

/* ------------------------------------------------------------- test values */

/** Synthetic. Not a token, not derived from one — a needle to search the DOM for. */
export const FAKE = {
  phoneNumberId: "111222333444555",
  wabaId: "999888777666555",
  accessToken: "FAKE-ACCESS-TOKEN-do-not-render-me-aaaaaaaaaaaa",
  appSecret: "FAKE-APP-SECRET-do-not-render-me-bbbbbbbbbbbb",
  verifyToken: "FAKE-VERIFY-TOKEN-do-not-render-me-cccccccccccc",
} as const;

/** Every needle, for the "nothing leaked anywhere" sweep. */
export const FAKE_VALUES = Object.values(FAKE);

const TOKEN = "e2e-session-token";

/* ------------------------------------------------------------------- state */

const CRED_FIELDS = [
  "phone_number_id",
  "waba_id",
  "access_token",
  "app_secret",
  "webhook_verify_token",
] as const;
type CredField = (typeof CRED_FIELDS)[number];

/** What makes an account able to address Meta at all — mirrors `_account_out`. */
const CONFIG_FIELDS: CredField[] = ["phone_number_id", "waba_id", "access_token"];

export type Purpose = "authentication" | "engagement";

export type AccountRow = {
  id: number;
  slug: string;
  name: string;
  purpose: Purpose;
  display_phone: string | null;
  api_version: string;
  is_active: boolean;
  health: "unknown" | "ok" | "degraded" | "unauthorized";
  quality_rating: string | null;
  messaging_limit: string | null;
  last_checked_at: string | null;
  last_error: string | null;
  /** Stored plaintext. The read shape must never expose any of it. */
  secrets: Partial<Record<CredField, string>>;
};

export type ProductRow = {
  id: number;
  slug: string;
  name: string;
  description: string | null;
  is_enabled: boolean;
  api_key_hash: string;
  api_key_prefix: string;
  allowed_purposes: string[];
  default_locale: string;
  rate_limit_per_minute: number;
  registry_version: string | null;
  last_seen_at: string | null;
  created_at: string | null;
};

export type TemplateRow = {
  id: number;
  name: string;
  language: string;
  category: "authentication" | "marketing" | "utility";
  intent: string;
  status: string;
  account: string;
  product: string | null;
  variables: string[];
  provider_template_id: string | null;
  rejection_reason: string | null;
  last_synced_at: string | null;
  created_at: string | null;
};

export type RecordedRequest = {
  method: string;
  path: string;
  body: Record<string, unknown> | null;
};

export type World = {
  accounts: AccountRow[];
  products: ProductRow[];
  templates: TemplateRow[];
  rules: unknown[];
  conversations: unknown[];
  alerts: unknown[];
  gates: {
    env_enabled: boolean;
    delivery_enabled: boolean;
    require_signature: boolean;
  };
  /** Every QCP request the browser made, in order. */
  requests: RecordedRequest[];
  /** Paths this fake does not know about, so a test can notice a real gap. */
  unhandled: string[];
  /** Plaintext keys this fake handed out, so a test can hunt for them. */
  mintedKeys: string[];
  /** `"POST /admin/qcp/accounts/quata-verify/enable"` → forced response. */
  forced: Map<string, { status: number; body: unknown }>;
  account(slug: string): AccountRow | undefined;
  product(slug: string): ProductRow | undefined;
};

/* ------------------------------------------------------------------- seeds */

function account(
  id: number,
  slug: string,
  name: string,
  purpose: Purpose,
  extra: Partial<AccountRow> = {}
): AccountRow {
  return {
    id,
    slug,
    name,
    purpose,
    display_phone: null,
    api_version: "v21.0",
    is_active: false,
    health: "unknown",
    quality_rating: null,
    messaging_limit: null,
    last_checked_at: null,
    last_error: null,
    secrets: {},
    ...extra,
  };
}

export function product(
  id: number,
  slug: string,
  name: string,
  extra: Partial<ProductRow> = {}
): ProductRow {
  return {
    id,
    slug,
    name,
    description: null,
    is_enabled: false,
    api_key_hash: "",
    api_key_prefix: "",
    allowed_purposes: ["engagement"],
    default_locale: "en",
    rate_limit_per_minute: 600,
    registry_version: null,
    last_seen_at: null,
    created_at: "2026-08-01T09:00:00Z",
    ...extra,
  };
}

/**
 * The state QCP actually ships in: both numbers seeded, nothing configured,
 * nothing enabled, nothing ever sent. This is what the first real operator
 * meets, so it is the default.
 */
export function freshWorld(overrides: Partial<World> = {}): World {
  const w: World = {
    accounts: [
      account(1, "quata-verify", "Quata Verify", "authentication"),
      account(2, "quata", "QUATA", "engagement"),
    ],
    products: [],
    templates: [],
    rules: [],
    conversations: [],
    alerts: [],
    gates: { env_enabled: false, delivery_enabled: false, require_signature: true },
    requests: [],
    unhandled: [],
    mintedKeys: [],
    forced: new Map(),
    account(slug) {
      return this.accounts.find((a) => a.slug === slug);
    },
    product(slug) {
      return this.products.find((p) => p.slug === slug);
    },
    ...overrides,
  };
  return w;
}

/** Nothing at all — not even the seed. The "seed has not run" screen. */
export function barrenWorld(): World {
  return freshWorld({ accounts: [] });
}

/* ------------------------------------------------------------- read shapes */

function accountSecurity(a: AccountRow) {
  if (a.secrets.phone_number_id) return [];
  return [
    {
      code: "phone_number_id_unset",
      severity: "critical" as const,
      message:
        "With no phone number id the webhook cannot attribute an inbound envelope to this number, so a correctly signed QUATA envelope is accepted here.",
    },
  ];
}

export function accountOut(a: AccountRow) {
  const has = (f: CredField) => Boolean(a.secrets[f]);
  return {
    id: a.id,
    slug: a.slug,
    name: a.name,
    purpose: a.purpose,
    display_phone: a.display_phone,
    api_version: a.api_version,
    is_active: a.is_active,
    health: a.health,
    quality_rating: a.quality_rating,
    messaging_limit: a.messaging_limit,
    last_checked_at: a.last_checked_at,
    last_error: a.last_error,
    has_phone_number_id: has("phone_number_id"),
    has_waba_id: has("waba_id"),
    has_access_token: has("access_token"),
    has_app_secret: has("app_secret"),
    has_verify_token: has("webhook_verify_token"),
    configured: CONFIG_FIELDS.every(has),
    security: accountSecurity(a),
  };
}

function productOut(p: ProductRow) {
  return {
    id: p.id,
    slug: p.slug,
    name: p.name,
    description: p.description,
    is_enabled: p.is_enabled,
    has_api_key: Boolean(p.api_key_hash),
    api_key_prefix: p.api_key_prefix || null,
    allowed_purposes: p.allowed_purposes,
    default_locale: p.default_locale,
    rate_limit_per_minute: p.rate_limit_per_minute,
    registry_version: p.registry_version,
    last_seen_at: p.last_seen_at,
    created_at: p.created_at,
  };
}

function templateOut(w: World, t: TemplateRow) {
  const acct = w.account(t.account);
  const purpose = acct?.purpose ?? "engagement";
  return {
    id: t.id,
    name: t.name,
    language: t.language,
    category: t.category,
    intent: t.intent,
    status: t.status,
    account: t.account,
    account_name: acct?.name ?? null,
    account_purpose: purpose,
    account_is_active: acct?.is_active ?? false,
    product: t.product,
    variables: t.variables,
    provider_template_id: t.provider_template_id,
    rejection_reason: t.rejection_reason,
    last_synced_at: t.last_synced_at,
    created_at: t.created_at,
    misbound:
      (t.category === "authentication") !== (purpose === "authentication"),
  };
}

function overviewOut(w: World) {
  const accounts = w.accounts.map(accountOut);
  return {
    window_hours: 24,
    gates: {
      env_enabled: w.gates.env_enabled,
      delivery_enabled: w.gates.delivery_enabled,
      any_account_active: w.accounts.some((a) => a.is_active),
      any_product_enabled: w.products.some((p) => p.is_enabled),
      require_signature: w.gates.require_signature,
    },
    accounts,
    products: w.products.map(productOut),
    queue: { queued: 0, oldest_queued_at: null, failed: 0, suppressed: 0, total: 0 },
    recent: { total: 0, sent: 0, queued: 0, failed: 0, suppressed: 0 },
    templates: {
      total: w.templates.length,
      approved: w.templates.filter((t) => t.status === "approved").length,
      pending_approval: 0,
      rejected: 0,
    },
    conversations: { total: w.conversations.length, open: 0 },
    failures: [],
    denials: [],
  };
}

/* --------------------------------------------------------------- refusals */

type Reply = { status: number; body: unknown };

/** `routes_admin_whatsapp.py` — the sentence lives under `message`. */
function denyAccounts(
  reason: string,
  message: string,
  extra: Record<string, unknown> = {}
): Reply {
  return { status: 409, body: { detail: { reason, message, ...extra } } };
}

/** `routes_admin_templates.py` — the sentence lives under `detail`. */
function denyTemplates(
  reason: string,
  detail: string,
  problems?: unknown[]
): Reply {
  return {
    status: 409,
    body: { detail: { reason, detail, ...(problems ? { problems } : {}) } },
  };
}

/** FastAPI's own 422, as a Pydantic min_length failure produces it. */
function unprocessable(field: string, msg: string): Reply {
  return {
    status: 422,
    body: { detail: [{ loc: ["body", field], msg, type: "value_error" }] },
  };
}

/* ---------------------------------------------------------------- routing */

const OK = (body: unknown): Reply => ({ status: 200, body });

function handle(
  w: World,
  method: string,
  path: string,
  params: URLSearchParams,
  body: Record<string, unknown> | null
): Reply {
  const forced = w.forced.get(`${method} ${path}`);
  if (forced) return forced;

  const str = (k: string) => String(body?.[k] ?? "").trim();

  /* ---- session ---- */
  if (path === "/auth/me") {
    return OK({
      id: 1,
      email: "ops@quatadigital.com",
      full_name: "QCP Operator",
      role: "super_admin",
      department: null,
      phone: null,
      job_title: null,
      avatar_url: null,
      permissions: ["settings:manage", "activity:view"],
      requires_2fa: false,
      has_2fa: true,
      must_reset_password: false,
    });
  }
  if (path === "/admin/activity") return OK([]);

  /* ---- reads ---- */
  if (path === "/admin/qcp/overview") return OK(overviewOut(w));

  if (path === "/admin/qcp/products" && method === "GET") {
    return OK({
      items: w.products.map((p) => ({
        ...productOut(p),
        routing_rules: 0,
        routing_rules_active: 0,
        templates: w.templates.filter((t) => t.product === p.slug).length,
        messages: 0,
      })),
      platform_templates: w.templates.filter((t) => !t.product).length,
    });
  }

  if (path === "/admin/qcp/templates/alerts") return OK({ items: w.alerts });

  if (path === "/admin/qcp/templates" && method === "GET") {
    const category = params.get("category");
    const status = params.get("status");
    const items = w.templates
      .filter((t) => !category || t.category === category)
      .filter((t) => !status || t.status === status)
      .map((t) => templateOut(w, t));
    return OK({
      items,
      accounts: [...w.accounts]
        .sort((a, b) => a.purpose.localeCompare(b.purpose))
        .map((a) => ({
          slug: a.slug,
          name: a.name,
          purpose: a.purpose,
          is_active: a.is_active,
          display_phone: a.display_phone,
        })),
      misbound_count: items.filter((i) => i.misbound).length,
    });
  }

  if (path === "/admin/qcp/routing-rules" && method === "GET") {
    return OK({ items: w.rules });
  }

  if (path === "/admin/qcp/conversations" && method === "GET") {
    return OK({
      total: w.conversations.length,
      page: 1,
      page_size: 25,
      items: w.conversations,
    });
  }

  /* ---- account writes ---- */
  const acctMatch = /^\/admin\/qcp\/accounts\/([^/]+)\/(.+)$/.exec(path);
  if (acctMatch) {
    const a = w.account(decodeURIComponent(acctMatch[1]));
    if (!a) return { status: 404, body: { detail: "Account not found" } };
    const action = acctMatch[2];

    if (action === "credentials" && method === "PUT") {
      // `AccountCredentialsIn` forbids extra fields.
      const allowed = new Set<string>([...CRED_FIELDS, "display_phone", "api_version"]);
      const extra = Object.keys(body ?? {}).filter((k) => !allowed.has(k));
      if (extra.length) {
        return unprocessable(extra[0], "Extra inputs are not permitted");
      }
      if (!body || Object.keys(body).length === 0) {
        return unprocessable("body", "At least one field must be supplied");
      }
      for (const f of CRED_FIELDS) {
        // Absent means "keep". Only a present, non-empty value replaces.
        if (typeof body[f] === "string" && String(body[f]).trim()) {
          a.secrets[f] = String(body[f]).trim();
        }
      }
      if (typeof body.display_phone === "string") a.display_phone = body.display_phone;
      if (typeof body.api_version === "string") a.api_version = body.api_version;
      return OK(accountOut(a));
    }

    if (action === "enable" && method === "POST") {
      if (str("justification").length < 8) {
        return unprocessable("justification", "String should have at least 8 characters");
      }
      if (str("confirm_slug") !== a.slug) {
        return denyAccounts(
          "confirmation_mismatch",
          `Type '${a.slug}' to confirm you are switching on this number.`
        );
      }
      const blocking = CONFIG_FIELDS.filter((f) => !a.secrets[f]);
      if (blocking.length) {
        return denyAccounts(
          "not_configured",
          `This number is not fully configured. Set ${blocking.join(", ")} before switching it on.`,
          { blocking }
        );
      }
      const conflict = w.accounts.find(
        (o) => o.purpose === a.purpose && o.is_active && o.id !== a.id
      );
      if (conflict) {
        return denyAccounts(
          "another_account_active_for_purpose",
          `${conflict.name} is already the live ${a.purpose} number. Deactivate it before switching this one on.`,
          { conflict: conflict.slug, purpose: a.purpose }
        );
      }
      a.is_active = true;
      return OK(accountOut(a));
    }

    if (action === "disable" && method === "POST") {
      a.is_active = false;
      return OK(accountOut(a));
    }

    if (action === "test-connection" && method === "POST") {
      const missing = CONFIG_FIELDS.filter((f) => !a.secrets[f]);
      if (missing.length) {
        return denyAccounts(
          "not_configured",
          `There is nothing to test with yet. Set ${missing.join(", ")} first.`,
          { blocking: missing }
        );
      }
      return OK({
        ok: true,
        health: "ok",
        quality_rating: "GREEN",
        messaging_limit: "TIER_1K",
        verified_name: a.name,
        error: null,
        sent_message: false,
      });
    }

    if (action === "templates/sync" && method === "POST") {
      return OK({
        account: a.slug,
        fetched: 0,
        created: 0,
        updated: 0,
        unchanged: 0,
        alerts: [],
      });
    }
  }

  /* ---- product writes ---- */
  const prodMatch = /^\/admin\/qcp\/products\/([^/]+)\/(.+)$/.exec(path);
  if (prodMatch) {
    const p = w.product(decodeURIComponent(prodMatch[1]));
    if (!p) return { status: 404, body: { detail: "Product not found" } };
    const action = prodMatch[2];

    if (action === "api-key" && method === "POST") {
      const plaintext = `qcp_${p.slug}_${"k".repeat(8)}${w.mintedKeys.length}_PLAINTEXT_ONLY_ONCE`;
      w.mintedKeys.push(plaintext);
      p.api_key_hash = `sha256:${plaintext.length}`;
      p.api_key_prefix = plaintext.slice(0, 12);
      return OK({
        product: productOut(p),
        api_key: plaintext,
        prefix: p.api_key_prefix,
        fingerprint: "abc123def456",
        shown_once: true,
        notice:
          "This key is shown once and is not stored. Copy it now; if it is lost, rotate the key rather than trying to recover it.",
      });
    }

    if (action === "api-key" && method === "DELETE") {
      p.api_key_hash = "";
      p.api_key_prefix = "";
      return OK(productOut(p));
    }

    if (action === "enable" && method === "POST") {
      if (!p.api_key_hash) {
        return denyAccounts(
          "no_api_key",
          "This product has no API key, so it cannot authenticate at the gateway. Mint one before enabling it."
        );
      }
      p.is_enabled = true;
      return OK(productOut(p));
    }

    if (action === "disable" && method === "POST") {
      p.is_enabled = false;
      return OK(productOut(p));
    }

    if (action === "purposes" && method === "PUT") {
      const wanted = (body?.purposes as string[]) ?? [];
      if (!p.allowed_purposes.includes("authentication") && wanted.includes("authentication")) {
        return denyAccounts(
          "authentication_grant_requires_dedicated_action",
          "Reaching Quata Verify is granted by its own route with a justification, not by this list."
        );
      }
      p.allowed_purposes = wanted;
      return OK(productOut(p));
    }

    if (action === "purposes/authentication" && method === "POST") {
      if (str("justification").length < 8) {
        return unprocessable("justification", "String should have at least 8 characters");
      }
      if (!p.allowed_purposes.includes("authentication")) {
        p.allowed_purposes = [...p.allowed_purposes, "authentication"];
      }
      return OK(productOut(p));
    }
  }

  if (path === "/admin/qcp/products" && method === "POST") {
    if (w.product(str("slug"))) {
      return denyAccounts("slug_taken", `A product with the slug '${str("slug")}' already exists.`);
    }
    w.products.push(
      product(w.products.length + 10, str("slug"), str("name"), {
        description: str("description") || null,
        default_locale: str("default_locale") || "en",
        rate_limit_per_minute: Number(body?.rate_limit_per_minute ?? 600),
      })
    );
    return { status: 201, body: productOut(w.products[w.products.length - 1]) };
  }

  /* ---- template writes ---- */
  if (path === "/admin/qcp/templates" && method === "POST") {
    const acct = w.account(str("account"));
    if (!acct) {
      return { status: 404, body: { detail: `Unknown account '${str("account")}'` } };
    }
    const category = str("category");
    if (category === "authentication" && acct.purpose !== "authentication") {
      return denyTemplates(
        "auth_template_off_verify",
        `An authentication template may only live on the authentication number. '${acct.name}' carries engagement traffic.`
      );
    }
    if (category !== "authentication" && acct.purpose === "authentication") {
      return denyTemplates(
        "non_auth_category_on_verify",
        `Quata Verify carries the authentication category and nothing else, not even utility. Put this ${category} template on QUATA.`
      );
    }
    const bodyText = str("body");
    const vars = [...bodyText.matchAll(/\{\{(\d+)\}\}/g)].map((m) => m[1]);
    const row: TemplateRow = {
      id: w.templates.length + 100,
      name: str("name"),
      language: str("language") || "en",
      category: category as TemplateRow["category"],
      intent: str("intent"),
      status: "draft",
      account: acct.slug,
      product: str("product") || null,
      variables: vars,
      provider_template_id: null,
      rejection_reason: null,
      last_synced_at: null,
      created_at: "2026-08-11T10:00:00Z",
    };
    w.templates.push(row);
    return { status: 201, body: templateOut(w, row) };
  }

  w.unhandled.push(`${method} ${path}`);
  return OK({ items: [], total: 0, page: 1, page_size: 25 });
}

/* --------------------------------------------------------------- install */

const CORS = {
  "access-control-allow-origin": "*",
  "access-control-allow-headers": "*",
  "access-control-allow-methods": "GET,POST,PUT,PATCH,DELETE,OPTIONS",
};

/**
 * Point the browser at `world` and sign it in.
 *
 * The console's auth is entirely client-side — a bearer token in
 * `localStorage` and a `/auth/me` round trip — so seeding the token in an init
 * script is the whole of "log in", and it happens before any app code runs.
 */
export async function useWorld(page: Page, world: World): Promise<World> {
  await page.addInitScript((token) => {
    window.localStorage.setItem("quata_token", token);
  }, TOKEN);

  await page.route("**/api/v1/**", async (route) => {
    const req = route.request();
    const url = new URL(req.url());
    const path = url.pathname.replace(/^\/api\/v1/, "");
    const method = req.method();

    let body: Record<string, unknown> | null = null;
    try {
      body = (req.postDataJSON() as Record<string, unknown>) ?? null;
    } catch {
      body = null;
    }
    if (path.startsWith("/admin/qcp")) {
      world.requests.push({ method, path, body });
    }

    const reply = handle(world, method, path, url.searchParams, body);
    await route.fulfill({
      status: reply.status,
      contentType: "application/json",
      headers: CORS,
      body: JSON.stringify(reply.body),
    });
  });

  return world;
}

/** Every QCP request for one path, newest last. */
export function requestsTo(w: World, method: string, path: string): RecordedRequest[] {
  return w.requests.filter((r) => r.method === method && r.path === path);
}
