/**
 * QUATA Notification Service client — drop-in, zero dependencies.
 *
 * Copy this single file into QuataPay / QuataFood / Abaqwa / QuataTrade /
 * QUATA AI. It is the only code those platforms need in order to feed
 * @QuataAlertsBot. No platform ever holds a Telegram token.
 *
 *     import { notify, Events } from "./quata-notify";
 *
 *     notify.publish(Events.ORDER_PLACED, {
 *       restaurant: "Chez Ada",
 *       order_number: "QF-1001",
 *       customer: "John Doe",
 *       amount: 4500,
 *       currency: "XAF",
 *     }, { reference: "QF-1001", dedupeKey: "quatafood:order:QF-1001" });
 *
 * Design notes, because they matter in a payments path:
 *
 *  - Non-blocking. `publish()` enqueues and returns synchronously; a drain
 *    loop does the HTTP. A customer's order never waits on an alert.
 *  - Never throws. Every failure is swallowed and counted.
 *  - Bounded queue. If the service is down, the oldest events are dropped
 *    and counted rather than growing memory until the process dies.
 *  - Idempotent. Pass `dedupeKey` and a retried publish will not
 *    double-alert the administrators.
 *
 * Environment:
 *
 *     QUATA_NOTIFY_URL=https://api.quatadigital.com/api/v1/notify/events
 *     QUATA_PLATFORM=quatafood
 *     QUATA_INGEST_KEY=<the key issued for this platform>
 *     QUATA_NOTIFY_SIGN=true
 *     QUATA_NOTIFY_ENABLED=true
 *
 * Node 18+ (uses global `fetch` and `node:crypto`).
 */

import { createHmac } from "node:crypto";

export interface PublishOptions {
  reference?: string;
  /** info | warning | important | critical — overrides the catalogue default. */
  priority?: "info" | "warning" | "important" | "critical";
  /** Overrides the rendered `Status:` line. */
  status?: string;
  /** Idempotency key. Strongly recommended — prevents duplicate alerts. */
  dedupeKey?: string;
  occurredAt?: Date;
}

export interface NotifierConfig {
  url?: string;
  platform?: string;
  ingestKey?: string;
  sign?: boolean;
  enabled?: boolean;
  timeoutMs?: number;
  maxQueue?: number;
  maxRetries?: number;
}

interface QueuedEvent {
  event: string;
  payload: Record<string, unknown>;
  reference?: string;
  priority?: string;
  status?: string;
  dedupe_key?: string;
  occurred_at: string;
}

function envBool(name: string, fallback: boolean): boolean {
  const raw = process.env[name];
  if (raw === undefined) return fallback;
  return ["1", "true", "yes", "on"].includes(raw.trim().toLowerCase());
}

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

export class QuataNotifier {
  readonly url: string;
  readonly platform: string;
  private readonly ingestKey: string;
  private readonly sign: boolean;
  enabled: boolean;
  private readonly timeoutMs: number;
  private readonly maxQueue: number;
  private readonly maxRetries: number;

  private queue: QueuedEvent[] = [];
  private draining = false;

  /** Expose on a health endpoint so a broken integration is visible. */
  readonly stats = { published: 0, delivered: 0, failed: 0, dropped: 0 };

  constructor(config: NotifierConfig = {}) {
    this.url = config.url ?? process.env.QUATA_NOTIFY_URL ?? "";
    this.platform = (config.platform ?? process.env.QUATA_PLATFORM ?? "").toLowerCase();
    this.ingestKey = config.ingestKey ?? process.env.QUATA_INGEST_KEY ?? "";
    this.sign = config.sign ?? envBool("QUATA_NOTIFY_SIGN", true);
    this.enabled = config.enabled ?? envBool("QUATA_NOTIFY_ENABLED", true);
    this.timeoutMs = config.timeoutMs ?? 5000;
    this.maxQueue = config.maxQueue ?? 1000;
    this.maxRetries = config.maxRetries ?? 3;

    if (this.enabled && !(this.url && this.platform && this.ingestKey)) {
      console.warn(
        "quata-notify: not configured (need QUATA_NOTIFY_URL, QUATA_PLATFORM, " +
          "QUATA_INGEST_KEY); events will be discarded.",
      );
      this.enabled = false;
    }
  }

  /**
   * Queue one event. Returns false if it couldn't be queued.
   * Never throws, never awaits the network.
   */
  publish(
    event: string,
    payload: Record<string, unknown> = {},
    options: PublishOptions = {},
  ): boolean {
    if (!this.enabled) return false;
    try {
      const item: QueuedEvent = {
        event,
        payload,
        occurred_at: (options.occurredAt ?? new Date()).toISOString(),
      };
      if (options.reference) item.reference = String(options.reference);
      if (options.priority) item.priority = options.priority;
      if (options.status) item.status = options.status;
      if (options.dedupeKey) item.dedupe_key = options.dedupeKey;

      if (this.queue.length >= this.maxQueue) {
        // Drop the oldest: during an incident the newest events matter most.
        this.queue.shift();
        this.stats.dropped += 1;
      }
      this.queue.push(item);
      this.stats.published += 1;
      void this.drain();
      return true;
    } catch {
      return false; // alerting must never break the caller
    }
  }

  /** Await the queue draining. Call before a deliberate shutdown. */
  async flush(timeoutMs = 5000): Promise<void> {
    const deadline = Date.now() + timeoutMs;
    while ((this.queue.length > 0 || this.draining) && Date.now() < deadline) {
      await sleep(25);
    }
  }

  private async drain(): Promise<void> {
    if (this.draining) return;
    this.draining = true;
    try {
      while (this.queue.length > 0) {
        const item = this.queue.shift()!;
        const ok = await this.sendWithRetry(item);
        if (ok) this.stats.delivered += 1;
        else this.stats.failed += 1;
      }
    } finally {
      this.draining = false;
    }
  }

  private async sendWithRetry(item: QueuedEvent): Promise<boolean> {
    for (let attempt = 1; attempt <= this.maxRetries; attempt += 1) {
      const { ok, retryable } = await this.sendOnce(item);
      if (ok) return true;
      if (!retryable || attempt === this.maxRetries) return false;
      await sleep(Math.min(2 ** attempt * 1000, 8000));
    }
    return false;
  }

  private async sendOnce(item: QueuedEvent): Promise<{ ok: boolean; retryable: boolean }> {
    const body = JSON.stringify(item);
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      "X-Quata-Platform": this.platform,
      "X-Quata-Key": this.ingestKey,
    };
    if (this.sign) {
      const stamp = Math.floor(Date.now() / 1000).toString();
      headers["X-Quata-Timestamp"] = stamp;
      headers["X-Quata-Signature"] = createHmac("sha256", this.ingestKey)
        .update(`${stamp}.${body}`)
        .digest("hex");
    }

    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      const response = await fetch(this.url, {
        method: "POST",
        headers,
        body,
        signal: controller.signal,
      });
      if (response.ok) return { ok: true, retryable: false };
      // 4xx is our own bug (bad key, bad body) — retrying can't fix it.
      const retryable = response.status >= 500 || response.status === 429;
      if (!retryable) {
        console.warn(`quata-notify: rejected with HTTP ${response.status}`);
      }
      return { ok: false, retryable };
    } catch {
      return { ok: false, retryable: true }; // network, DNS, timeout, abort
    } finally {
      clearTimeout(timer);
    }
  }
}

/** Default instance, configured from the environment. */
export const notify = new QuataNotifier();

/**
 * Event keys. See docs/NOTIFICATIONS.md for the full catalogue. Unknown keys
 * are accepted by the service, so this is a convenience, not a constraint.
 */
export const Events = {
  // Users (every platform)
  USER_REGISTERED: "user.registered",
  USER_ACTIVATED: "user.activated",
  USER_EMAIL_VERIFIED: "user.email_verified",
  USER_PHONE_VERIFIED: "user.phone_verified",
  USER_PASSWORD_RESET_REQUESTED: "user.password_reset_requested",
  USER_PASSWORD_CHANGED: "user.password_changed",
  USER_PROFILE_UPDATED: "user.profile_updated",
  USER_DEACTIVATED: "user.deactivated",
  USER_REACTIVATED: "user.reactivated",
  USER_DELETED: "user.deleted",

  // Security (every platform)
  ADMIN_LOGIN: "security.admin_login",
  ADMIN_LOGOUT: "security.admin_logout",
  ADMIN_LOGIN_FAILED: "security.admin_login_failed",
  SUSPICIOUS_LOGIN: "security.suspicious_login",
  MULTIPLE_FAILED_LOGINS: "security.multiple_failed_logins",
  NEW_DEVICE_LOGIN: "security.new_device_login",
  NEW_LOCATION_LOGIN: "security.new_location_login",
  ACCOUNT_LOCKED: "security.account_locked",
  TWO_FACTOR_ENABLED: "security.two_factor_enabled",
  TWO_FACTOR_DISABLED: "security.two_factor_disabled",

  // QuataPay
  WALLET_CREATED: "wallet.created",
  WALLET_ACTIVATED: "wallet.activated",
  KYC_SUBMITTED: "kyc.submitted",
  KYC_APPROVED: "kyc.approved",
  KYC_REJECTED: "kyc.rejected",
  DEPOSIT_INITIATED: "deposit.initiated",
  DEPOSIT_SUCCESSFUL: "deposit.successful",
  DEPOSIT_FAILED: "deposit.failed",
  WITHDRAWAL_REQUESTED: "withdrawal.requested",
  WITHDRAWAL_APPROVED: "withdrawal.approved",
  WITHDRAWAL_COMPLETED: "withdrawal.completed",
  WITHDRAWAL_FAILED: "withdrawal.failed",
  TRANSFER_WALLET_TO_WALLET: "transfer.wallet_to_wallet",
  TRANSFER_INTERNAL: "transfer.internal",
  PAYMENT_MERCHANT: "payment.merchant",
  PAYMENT_QR: "payment.qr",
  PAYMENT_REQUEST_ACCEPTED: "payment.request_accepted",
  MERCHANT_REGISTERED: "merchant.registered",
  MERCHANT_APPROVED: "merchant.approved",
  MERCHANT_SUSPENDED: "merchant.suspended",
  MERCHANT_SETTLEMENT_COMPLETED: "merchant.settlement_completed",
  REFUND_ISSUED: "transaction.refund_issued",
  CHARGEBACK: "transaction.chargeback",
  DISPUTE_OPENED: "transaction.dispute_opened",
  DISPUTE_RESOLVED: "transaction.dispute_resolved",

  // QuataFood
  RESTAURANT_REGISTERED: "restaurant.registered",
  RESTAURANT_APPROVED: "restaurant.approved",
  RESTAURANT_SUSPENDED: "restaurant.suspended",
  ORDER_PLACED: "order.placed",
  ORDER_ACCEPTED: "order.accepted",
  ORDER_REJECTED: "order.rejected",
  ORDER_PREPARING: "order.preparing",
  ORDER_PREPARED: "order.prepared",
  ORDER_RIDER_ASSIGNED: "order.rider_assigned",
  ORDER_PICKED_UP: "order.picked_up",
  ORDER_DELIVERED: "order.delivered",
  ORDER_CANCELLED: "order.cancelled",
  ORDER_REFUND_PROCESSED: "order.refund_processed",
  RESTAURANT_PAYOUT_COMPLETED: "restaurant.payout_completed",
  PROMOTION_CREATED: "promotion.created",

  // Abaqwa
  DELIVERY_REQUESTED: "delivery.requested",
  RIDE_REQUESTED: "ride.requested",
  PARCEL_REQUESTED: "parcel.requested",
  RIDER_ASSIGNED: "rider.assigned",
  RIDER_ACCEPTED: "rider.accepted",
  PICKUP_COMPLETED: "pickup.completed",
  DELIVERY_COMPLETED: "delivery.completed",
  DELIVERY_CANCELLED: "delivery.cancelled",
  DELIVERY_PAYMENT_COMPLETED: "delivery.payment_completed",

  // QuataTrade
  ACCOUNT_CREATED: "account.created",
  TRADE_CREATED: "trade.created",
  TRADE_ACCEPTED: "trade.accepted",
  TRADE_COMPLETED: "trade.completed",
  TRADE_CANCELLED: "trade.cancelled",
  ESCROW_FUNDED: "escrow.funded",
  ESCROW_RELEASED: "escrow.released",
  ESCROW_DISPUTE_OPENED: "escrow.dispute_opened",
  CRYPTO_DEPOSIT: "crypto.deposit",
  CRYPTO_WITHDRAWAL: "crypto.withdrawal",
  FIAT_DEPOSIT: "fiat.deposit",
  FIAT_WITHDRAWAL: "fiat.withdrawal",
  TRADE_LARGE: "trade.large",
  TRADE_SUSPICIOUS: "trade.suspicious",

  // QUATA AI
  AI_SERVICE_STARTED: "ai.service_started",
  AI_SERVICE_STOPPED: "ai.service_stopped",
  AI_RESTARTED: "ai.restarted",
  AI_UNAVAILABLE: "ai.unavailable",
  AI_API_ERROR: "ai.api_error",
  AI_MODEL_UPDATED: "ai.model_updated",
  AI_USAGE_SPIKE: "ai.usage_spike",
  AI_SYSTEM_OVERLOAD: "ai.system_overload",
  AI_KNOWLEDGE_BASE_UPDATED: "ai.knowledge_base_updated",
  AI_ADMIN_ADDED: "ai.admin_added",
  AI_ADMIN_REMOVED: "ai.admin_removed",

  // Infrastructure — ❌ SYSTEM ALERT
  SERVER_OFFLINE: "infra.server_offline",
  SERVER_RESTARTED: "infra.server_restarted",
  SERVER_RECOVERED: "infra.server_recovered",
  DATABASE_DISCONNECTED: "infra.database_disconnected",
  DATABASE_BACKUP_COMPLETED: "infra.database_backup_completed",
  DATABASE_BACKUP_FAILED: "infra.database_backup_failed",
  STORAGE_LOW: "infra.storage_low",
  HIGH_CPU: "infra.high_cpu",
  HIGH_RAM: "infra.high_ram",
  HIGH_DISK: "infra.high_disk",
  API_UNAVAILABLE: "infra.api_unavailable",
  JOB_FAILURE: "infra.job_failure",
  QUEUE_FAILURE: "infra.queue_failure",
  APPLICATION_ERROR: "infra.application_error",

  // Payment gateways
  MOMO_UNAVAILABLE: "gateway.momo_unavailable",
  MOMO_RESTORED: "gateway.momo_restored",
  PAYMENT_DELAYED: "gateway.payment_delayed",
  CALLBACK_FAILURE: "gateway.callback_failure",
  SETTLEMENT_COMPLETED: "gateway.settlement_completed",
  SETTLEMENT_FAILED: "gateway.settlement_failed",

  // Scheduled report — publish with { metrics: {...} } to override the
  // figures the service would otherwise derive from your event stream.
  DAILY_SUMMARY: "summary.daily",
} as const;

export type QuataEvent = (typeof Events)[keyof typeof Events];
