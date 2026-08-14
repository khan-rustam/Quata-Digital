"use client";

/**
 * What the campaigns screen knows about the backend.
 *
 * Kept next to the screen rather than in `../api.ts` for the same reason that
 * file gives for existing at all: one place per surface, so a route that moves
 * is one edit. The refusal handling, the secret stripping and the write hook
 * are all reused from `../api` — a campaign refusal is exactly the shape the
 * templates and routing screens already render (`409 {reason, detail}`), so
 * `explainQcpRefusal` needs no new branch for it.
 */

const enc = encodeURIComponent;

export const CAMPAIGNS = {
  list: "/admin/qcp/campaigns",
  create: "/admin/qcp/campaigns",
  one: (uid: string) => `/admin/qcp/campaigns/${enc(uid)}`,
  audience: (uid: string) => `/admin/qcp/campaigns/${enc(uid)}/audience`,
  schedule: (uid: string) => `/admin/qcp/campaigns/${enc(uid)}/schedule`,
  start: (uid: string) => `/admin/qcp/campaigns/${enc(uid)}/start`,
  pause: (uid: string) => `/admin/qcp/campaigns/${enc(uid)}/pause`,
  stop: (uid: string) => `/admin/qcp/campaigns/${enc(uid)}/stop`,
  audiencePreview: "/admin/qcp/campaigns/audience-preview",
  optOuts: "/admin/qcp/campaigns/opt-outs",
  optOutScan: "/admin/qcp/campaigns/opt-outs/scan",
  runDue: "/admin/qcp/campaigns/run-due",
} as const;

/** Every state a campaign can be in, in the order it moves through them. */
export const CAMPAIGN_STATUSES = [
  "draft",
  "scheduled",
  "running",
  "paused",
  "stopped",
  "completed",
] as const;

export type CampaignStatus = (typeof CAMPAIGN_STATUSES)[number];

/**
 * What a send actually did.
 *
 * `sent`, `delivered` and `read` are cumulative, not disjoint — Meta's status
 * ladder is monotonic and the backend reports it that way, so a read message
 * is counted in all three. Rendering them as slices of a pie would say a
 * campaign reached a third of the people it reached.
 */
export type CampaignResults = {
  audience: number;
  pending: number;
  queued: number;
  sent: number;
  delivered: number;
  read: number;
  failed: number;
  suppressed: number;
  opted_out: number;
  cancelled: number;
};

export type Campaign = {
  campaign_uid: string;
  name: string;
  status: CampaignStatus;
  product: string | null;
  product_name: string | null;
  product_enabled: boolean;
  intent: string;
  locale: string | null;
  account: string | null;
  account_name: string | null;
  /** Always "engagement". Rendered anyway — it is the fact QCP exists to keep. */
  account_purpose: string;
  template: string | null;
  template_category: string | null;
  template_status: string | null;
  variables: string[];
  audience_source: string;
  audience_label: string | null;
  audience_filters: Record<string, unknown>;
  audience_size: number;
  messages_per_minute: number;
  scheduled_at: string | null;
  started_at: string | null;
  finished_at: string | null;
  stopped_at: string | null;
  stop_reason: string | null;
  last_error: string | null;
  created_at: string | null;
  results: CampaignResults;
};

export type CampaignRecipient = {
  phone_e164: string;
  status: string;
  conversation_id: number | null;
  message_uid: string | null;
  last_error: string | null;
  attempted_at: string | null;
};

export type CampaignDetail = Campaign & { recipients: CampaignRecipient[] };

/**
 * Why a campaign can or cannot send right now.
 *
 * Carried on the list response rather than fetched separately, because "no
 * campaigns" and "no campaign could send even if it existed" are different
 * states and an empty screen has to say which one it is looking at.
 */
export type CampaignPlatform = {
  delivery_enabled: boolean;
  engagement_account: string | null;
  engagement_account_name: string | null;
  any_product_enabled: boolean;
  products: {
    slug: string;
    name: string;
    is_enabled: boolean;
    allowed_purposes: string[];
    default_locale: string;
  }[];
  audience_sources: { value: string; label: string }[];
  opt_outs: number;
  max_messages_per_minute: number;
  max_audience: number;
};

export type CampaignListResponse = {
  items: Campaign[];
  platform: CampaignPlatform;
};

export type AudiencePreview = {
  source: string;
  label: string;
  filters: Record<string, unknown>;
  matched: number;
  opted_out: number;
  eligible: number;
  capped: boolean;
  limit: number;
  sample: string[];
};

export type OptOut = {
  phone_e164: string;
  source: string;
  evidence: string | null;
  note: string | null;
  created_at: string | null;
};

export type OptOutListResponse = { items: OptOut[]; total: number };

export const CAMPAIGN_STATUS_TONE: Record<
  string,
  "default" | "success" | "warn" | "danger" | "brand" | "outline"
> = {
  draft: "outline",
  scheduled: "warn",
  running: "brand",
  paused: "warn",
  stopped: "danger",
  completed: "success",
};

export const RECIPIENT_STATUS_TONE: Record<
  string,
  "default" | "success" | "warn" | "danger" | "brand" | "outline"
> = {
  pending: "outline",
  queued: "brand",
  suppressed: "default",
  failed: "danger",
  opted_out: "warn",
  cancelled: "default",
};
