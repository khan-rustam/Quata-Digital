# QUATA Notification Service — @QuataAlertsBot

The single real-time alert channel for the whole QUATA Digital Enterprise
ecosystem.

```
QuataPay · QuataFood · Abaqwa · QuataTrade · QUATA AI · Quata Digital
                              │
                              ▼
                 QUATA Notification Service
                              │
                              ▼
                   Existing @QuataAlertsBot
                              │
                              ▼
             Authorized Telegram administrators
```

**Rules that make this work, and must not be broken:**

1. There is exactly **one** Telegram bot — the existing **@QuataAlertsBot**. No
   platform creates its own.
2. Only the notification service talks to the Telegram API. Every other
   system publishes *events* and never sees a bot token.
3. Adding a platform is a configuration change (one ingest key), not a change
   to the notification architecture.

The service lives in this repository at
[`backend/app/services/notifications/`](../backend/app/services/notifications/),
with its HTTP surface in
[`backend/app/api/routes_notifications.py`](../backend/app/api/routes_notifications.py).

---

## 1. Operator setup

### 1.1 Bot token

Get the token for the **existing** @QuataAlertsBot from @BotFather
(`/mybots → @QuataAlertsBot → API Token`). Then either:

- **Preferred** — paste it in the admin at **Site settings → Integrations →
  Telegram bot token**. Takes effect within ~15 seconds, no redeploy.
- Or set `TELEGRAM_BOT_TOKEN` in `backend/.env` and restart.

The admin value wins when both are set.

### 1.2 Recipients

Nothing is delivered until at least one Telegram chat is authorised.

1. Message @QuataAlertsBot from the admin's Telegram account (or add the bot to
   the ops group and post once).
2. Run the discovery helper, which reads `getUpdates` and prints the ids:

   ```bash
   cd backend && source .venv/bin/activate
   python -m app.scripts.telegram_chats
   #   123456789            Clovis Neba @clovis  [private]
   #   -1001234567890       QUATA Ops            [group]
   ```

   `--send-hello` posts a confirmation to each chat; `--add-all` registers
   them as active recipients directly.
3. Otherwise add them by hand under **Admin → Alert centre → Recipients**.

> `getUpdates` only covers the last ~24 hours and returns nothing while a
> webhook is set. An empty list usually means "message the bot, then retry".

Per recipient you can set a **minimum priority** and restrict to specific
**platforms** or **categories** — so the CEO's chat can carry only 🔴 CRITICAL
while the ops group gets everything.

### 1.3 Ingest keys for the other platforms

Generate one key per platform:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Put them in `backend/.env`:

```bash
NOTIFY_INGEST_KEYS=["quatapay:KEY1","quatafood:KEY2","abaqwa:KEY3","quatatrade:KEY4","quata_ai:KEY5"]
NOTIFY_REQUIRE_SIGNATURE=true   # recommended in production
```

Restart the API. **Admin → Alert centre → Delivery → Connected platforms**
shows which platforms now have a key.

### 1.4 Background worker

Alerts are delivered in-process the moment they're published, so the worker
isn't required for alerts to arrive. It *is* required for retry-after-outage,
scheduled reports and infrastructure monitoring.

```bash
sudo cp infra/systemd/quata-notification-worker.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now quata-notification-worker
journalctl -u quata-notification-worker -f
```

The unit is checked in at
[`infra/systemd/quata-notification-worker.service`](../infra/systemd/quata-notification-worker.service)
and reads the same `/etc/quata-digital.env` as the API, so the two always
agree on the database, bot token and thresholds. `deploy.sh` restarts it
alongside the backend — non-fatally, since a worker that won't start must
never abort an otherwise-healthy deploy.

Each cycle it sweeps queued events, reclaims anything a killed process left
half-sent, probes `NOTIFY_HEALTHCHECK_URL`, samples CPU/RAM/disk/database/
queue health, sends the daily summary at the configured hour, and prunes the
log past `NOTIFICATION_LOG_RETENTION_DAYS`.

`python -m app.scripts.notification_worker --once` runs a single cycle, if you
prefer cron. `docker compose up` starts one automatically for local dev.

### 1.5 Database

```bash
cd backend && alembic upgrade head    # adds the three notification_* tables
```

### 1.6 Alerting from shell scripts

Cron jobs, backup scripts and deploy hooks publish through the app's own
service — no bot token, no ingest key:

```bash
cd /home/Quata-Digital/backend
.venv/bin/python -m app.scripts.notify_event infra.database_backup_completed \
    --payload '{"size": "412 MB", "detail": "pg_dump nightly"}' \
    --reference DB-BACKUP --wait --quiet
```

Exit code is `1` only for a caller error (bad JSON, unrecordable event). A
suppressed or undeliverable alert exits `0` — a backup that succeeded still
succeeded, and alerting must never turn a good run into a failed one.

[`infra/cron/backup-postgres.sh`](../infra/cron/backup-postgres.sh) already
uses this: success is reported once the dump is safely off-box, and an `ERR`
trap reports `infra.database_backup_failed` at 🔴 CRITICAL with the stage that
failed. A backup that silently stops running is how you discover you have no
backups on the day you need one.

---

## 2. Publishing events from another platform

### 2.1 Endpoint

```
POST https://<api-host>/api/v1/notify/events
```

| Header | Required | Value |
| --- | --- | --- |
| `X-Quata-Platform` | yes | `quatapay` · `quatafood` · `abaqwa` · `quatatrade` · `quata_ai` |
| `X-Quata-Key` | yes | that platform's ingest key |
| `X-Quata-Timestamp` | when signing | unix seconds |
| `X-Quata-Signature` | when signing | `HMAC-SHA256(key, "<timestamp>.<raw body>")`, hex |

Returns `202 Accepted` immediately — the caller never waits for Telegram.

> A platform may only publish **as itself**. A `platform` field in the body is
> ignored; the header credential decides. QuataFood's key cannot forge a
> QuataPay financial alert.

### 2.2 Body

Single event:

```json
{
  "event": "deposit.successful",
  "payload": {
    "full_name": "John Doe",
    "email": "john@example.com",
    "phone": "+237600000000",
    "country": "Cameroon",
    "amount": 25000,
    "currency": "XAF",
    "fee": 125,
    "payment_method": "MTN MoMo",
    "transaction_id": "TXN-000245",
    "sender": "John Doe",
    "receiver": "QuataPay Wallet"
  },
  "reference": "TXN-000245",
  "dedupe_key": "quatapay:deposit:TXN-000245"
}
```

Or a batch of up to 50: `{"events": [ … ]}`.

| Field | Notes |
| --- | --- |
| `event` | Catalogue key. Unknown keys are accepted and categorised by namespace. |
| `payload` | Free-form. Rendered in the message; credentials are stripped (§4). |
| `reference` | Business reference shown as `Reference:` — order no, txn id, user id. |
| `priority` | Override: `info` · `warning` · `important` · `critical`. |
| `status` | Override the `Status:` line. |
| `dedupe_key` | **Strongly recommended.** Idempotency key — a repeat publish with the same key is recorded as a duplicate instead of alerting twice. |
| `occurred_at` | ISO-8601. Defaults to receipt time. |

### 2.3 Use the SDK

Don't hand-roll the client — [`sdk/`](../sdk/) ships a single-file,
zero-dependency implementation for Python and TypeScript that already handles
signing, the background queue, bounded buffering and retry:

```python
from quata_notify import notify, Events

notify.publish(
    Events.DEPOSIT_SUCCESSFUL,
    {"full_name": "John Doe", "amount": 25000, "currency": "XAF"},
    reference="TXN-000245",
    dedupe_key="quatapay:deposit:245",
)
```

See [`sdk/README.md`](../sdk/README.md). The raw protocol below is documented
for any platform on a runtime the SDK doesn't cover.

### 2.4 Reference client (raw protocol)

```python
import hashlib, hmac, json, time, urllib.request

QUATA_NOTIFY_URL = "https://api.quatadigital.com/api/v1/notify/events"
PLATFORM = "quatapay"
INGEST_KEY = "..."           # from the environment, never hard-coded


def publish(event: str, payload: dict, reference: str | None = None,
            dedupe_key: str | None = None) -> None:
    """Publish one event to the QUATA Notification Service.

    Fire-and-forget: alerting must never fail a user's transaction, so every
    error is swallowed. Run it off the request path (Celery / a thread) —
    the endpoint is fast, but not free.
    """
    body = json.dumps({
        "event": event,
        "payload": payload,
        "reference": reference,
        "dedupe_key": dedupe_key,
    }).encode()

    stamp = str(int(time.time()))
    signature = hmac.new(
        INGEST_KEY.encode(), f"{stamp}.".encode() + body, hashlib.sha256
    ).hexdigest()

    request = urllib.request.Request(QUATA_NOTIFY_URL, data=body, headers={
        "Content-Type": "application/json",
        "X-Quata-Platform": PLATFORM,
        "X-Quata-Key": INGEST_KEY,
        "X-Quata-Timestamp": stamp,
        "X-Quata-Signature": signature,
    })
    try:
        urllib.request.urlopen(request, timeout=5).read()
    except Exception:
        pass  # never let alerting break the caller
```

Node/TypeScript equivalent:

```ts
import { createHmac } from "node:crypto";

export async function publish(event: string, payload: Record<string, unknown>,
                              reference?: string, dedupeKey?: string) {
  const body = JSON.stringify({ event, payload, reference, dedupe_key: dedupeKey });
  const stamp = Math.floor(Date.now() / 1000).toString();
  const signature = createHmac("sha256", process.env.QUATA_INGEST_KEY!)
    .update(`${stamp}.${body}`)
    .digest("hex");

  try {
    await fetch(process.env.QUATA_NOTIFY_URL!, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Quata-Platform": process.env.QUATA_PLATFORM!,
        "X-Quata-Key": process.env.QUATA_INGEST_KEY!,
        "X-Quata-Timestamp": stamp,
        "X-Quata-Signature": signature,
      },
      body,
    });
  } catch {
    // alerting must never break the caller
  }
}
```

### 2.5 From inside this repository

Quata Digital's own events go through the same `emit()`, no HTTP hop:

```python
from app.services import notifications

notifications.emit(
    "website.investor_inquiry",
    payload={"full_name": "…", "email": "…"},
    reference="MSG-000012",
)
```

`emit()` never raises and never blocks on the network.

### 2.6 Health check

`GET /api/v1/notify/health` — unauthenticated, for integration smoke tests.

---

## 3. Event catalogue

Full list: [`catalog.py`](../backend/app/services/notifications/catalog.py).
Keys are **not** platform-prefixed — shared lifecycle events are defined once
and any platform may publish them.

### User management — every platform
`user.registered` · `user.activated` · `user.email_verified` ·
`user.phone_verified` · `user.password_reset_requested` ·
`user.password_changed` · `user.profile_updated` · `user.deactivated` ·
`user.reactivated` · `user.deleted`

Payload fields rendered in order: `full_name`, `username`, `email`, `phone`,
`country`, `user_id`, `registration_date`, `ip_address`, `device_type`.

### Authentication & security — 🚨 SECURITY ALERT
`security.admin_login` · `security.admin_logout` ·
`security.admin_login_failed` · `security.suspicious_login` ·
`security.multiple_failed_logins` · `security.new_device_login` ·
`security.new_location_login` · `security.account_locked` ·
`security.two_factor_enabled` · `security.two_factor_disabled`

### QuataPay
Wallets — `wallet.created` · `wallet.activated`
KYC — `kyc.submitted` · `kyc.approved` · `kyc.rejected`
Deposits — `deposit.initiated` · `deposit.successful` · `deposit.failed`
Withdrawals — `withdrawal.requested` · `withdrawal.approved` ·
`withdrawal.completed` · `withdrawal.failed`
Transfers — `transfer.wallet_to_wallet` · `transfer.internal` ·
`payment.merchant` · `payment.qr` · `payment.request_accepted`
Merchants — `merchant.registered` · `merchant.approved` ·
`merchant.suspended` · `merchant.settlement_completed`
Disputes — `transaction.refund_issued` · `transaction.chargeback` ·
`transaction.dispute_opened` · `transaction.dispute_resolved`

### QuataFood
`restaurant.registered` · `restaurant.approved` · `restaurant.suspended` ·
`order.placed` · `order.accepted` · `order.rejected` · `order.preparing` · `order.prepared` ·
`order.rider_assigned` · `order.picked_up` · `order.delivered` ·
`order.cancelled` · `order.refund_processed` ·
`restaurant.payout_completed` · `promotion.created`

Fields: `restaurant`, `order_number`, `customer`, `rider`, `amount`,
`delivery_address`.

### Abaqwa
`delivery.requested` · `ride.requested` · `parcel.requested` ·
`rider.assigned` · `rider.accepted` · `pickup.completed` ·
`delivery.completed` · `delivery.cancelled` · `delivery.payment_completed`

Fields: `service_type`, `customer`, `rider`, `amount`, `pickup_location`,
`destination`.

### QuataTrade
`account.created` · `kyc.submitted` · `kyc.approved` · `trade.created` ·
`trade.accepted` · `trade.completed` · `trade.cancelled` · `escrow.funded` ·
`escrow.released` · `escrow.dispute_opened` · `crypto.deposit` ·
`crypto.withdrawal` · `fiat.deposit` · `fiat.withdrawal` · `trade.large` ·
`trade.suspicious`

Fields: `trade_id`, `currency`, `amount`, `buyer`, `seller`, `status`.

### QUATA AI
`ai.service_started` · `ai.service_stopped` · `ai.restarted` ·
`ai.unavailable` · `ai.api_error` · `ai.model_updated` · `ai.usage_spike` ·
`ai.system_overload` · `ai.knowledge_base_updated` · `ai.admin_added` ·
`ai.admin_removed`

### Quata Digital Enterprise website
`website.contact_submitted` · `website.partnership_request` ·
`website.investor_inquiry` · `website.business_inquiry` ·
`website.career_application` · `website.support_request` ·
`website.newsletter_subscribed`

### Already wired in this repository

Quata Digital Enterprise publishes these with no further work. Listed so
nobody re-implements them, and so you know what to expect in Telegram:

| Trigger | Event |
| --- | --- |
| Contact form — *Investor relations* | `website.investor_inquiry` |
| Contact form — *Partnerships* | `website.partnership_request` |
| Contact form — *Customer support* | `website.support_request` |
| Contact form — *Press / media* | `website.business_inquiry` |
| Contact form — anything else | `website.contact_submitted` |
| Partner form (`investor` / `business` / `strategic` / `service`) | investor / business / partnership event |
| Job application submitted | `website.career_application` |
| Newsletter signup | `website.newsletter_subscribed` |
| Admin signs in | `security.admin_login` (+ `new_device_login` / `new_location_login` when the device or country is unfamiliar) |
| Admin signs out | `security.admin_logout` |
| Wrong password on a real account | `security.admin_login_failed` |
| Attempts reach `MAX_LOGIN_ATTEMPTS` | `security.multiple_failed_logins` + `security.account_locked` |
| Login against an unknown / closed / locked / disabled account | `security.suspicious_login` |
| 2FA enrolled or removed | `security.two_factor_enabled` / `..._disabled` |
| Password reset requested / completed | `user.password_reset_requested` / `user.password_changed` |
| Staff invited | `user.registered` |
| Staff suspended / restored / reactivated | `user.deactivated` / `user.reactivated` |
| Profile edited | `user.profile_updated` |
| CV analysis fails upstream | `ai.api_error` |
| AI key or package missing | `ai.unavailable` |
| AI request rate crosses the threshold | `ai.usage_spike` |
| Broadcast email send fails | `infra.job_failure` |
| Unhandled exception in any request | `infra.application_error` |
| API process starts / stops cleanly | `infra.server_restarted` / `infra.server_offline` |
| Worker samples an unhealthy host | `infra.high_cpu` / `high_ram` / `high_disk` / `storage_low` / `database_disconnected` / `queue_failure`, with `infra.server_recovered` on the way back |

**New-device and different-country detection** compares against the account's
previous `login` activity rows.

* *Device* — class derived from the User-Agent (Desktop / Mobile / Tablet).
* *Country* — read from a CDN or reverse-proxy header (`CF-IPCountry`,
  `X-Vercel-IP-Country`, `X-Country-Code`, `X-Geo-Country`) and stored on the
  login activity row so the *next* sign-in has something to compare against.
  Cloudflare's `XX` (unknown) and `T1` (Tor) sentinels are ignored.
* *Fallback* — with no proxy header there is no country signal, so the check
  degrades to comparing the IPv4 /24. That answers the weaker "has this
  account signed in from around here before?" rather than a true country
  change.

To get real country alerts, put the API behind a CDN that sets one of those
headers. There is no GeoIP database in this deployment and none is required.

### Infrastructure — ❌ SYSTEM ALERT
`infra.server_offline` · `infra.server_restarted` · `infra.server_recovered` ·
`infra.database_disconnected` · `infra.database_backup_completed` ·
`infra.database_backup_failed` · `infra.storage_low` · `infra.high_cpu` ·
`infra.high_ram` · `infra.high_disk` · `infra.api_unavailable` ·
`infra.job_failure` · `infra.queue_failure` · `infra.application_error`

For this application these fire automatically — the worker samples the host,
and any unhandled exception in a request becomes an
`infra.application_error`. Other platforms publish their own.

The nightly backup already reports its own outcome — see §1.6. From Python:

```python
from app.services.notifications import monitor
monitor.report_backup(ok=True, detail="pg_dump 412 MB", size="412 MB")
```

### Payment gateways
`gateway.momo_unavailable` · `gateway.momo_restored` ·
`gateway.payment_delayed` · `gateway.callback_failure` ·
`gateway.settlement_completed` · `gateway.settlement_failed`

```python
monitor.report_gateway("gateway.momo_unavailable", error="504 from collection API")
```

### Unknown keys

A key that isn't in the catalogue is still accepted, categorised by its
namespace (`loyalty.points_awarded` → uncategorised, `deposit.reversed` →
transaction) and delivered at INFO. Ship the event first, add the curated
label and priority later.

---

## 4. Security

**Never transmitted.** Any payload field whose name looks like a credential is
replaced with `[redacted]` *before the event is stored* — so secrets never
reach the audit table, let alone Telegram. Covered: passwords, password
hashes, OTPs, TOTP/MFA codes, PINs, CVV/CVC, API keys, access and refresh
tokens, authorization headers, client secrets, private keys, seed phrases,
mnemonics, session ids and signatures. Matching is on a normalised key, so
`api_key`, `apiKey`, `API-KEY` and `x_api_key` are all caught.

The marker is kept in the stored payload so a misbehaving integration is
auditable, but redacted fields are omitted from the outgoing message
entirely — printing `Password: [redacted]` into a Telegram group only
advertises that a password was in flight.

**Masked.** Account-like identifiers keep a recognisable head and tail:
`account_number`, `card_number`, `iban`, `swift`, `wallet_address`,
`national_id`, `passport_number`, `tax_id` →
`1234567890123456` becomes `12••••••••••3456`. Values too short to mask
meaningfully are replaced wholesale.

**Sent as provided.** `email` and `phone` are rendered in full — the
specification lists both as required content for user notifications. Mask
them at the publisher if your jurisdiction requires it.

**Access control.**
- Delivery goes only to active rows in `notification_recipients` — there is no
  "reply to whoever messages the bot" path.
- Ingest keys are compared in constant time; an unknown platform and a wrong
  key are indistinguishable to the caller.
- With `NOTIFY_REQUIRE_SIGNATURE=true`, requests must carry a valid HMAC over
  `<timestamp>.<body>`; stale timestamps are refused, which blocks replay.
- The admin surface requires the `settings:manage` permission. Adding or
  removing a recipient is an authorisation change and is written to the
  activity log with the chat id.

**Audit.** Every event — delivered, queued, failed or suppressed — is a row in
`notification_events` with its rendered message, per-recipient delivery
outcome, attempt count and failure reason. Browsable at **Alert centre →
Logs**; retained for `NOTIFICATION_LOG_RETENTION_DAYS` (default 180).

**Injection.** Messages use Telegram HTML mode and every payload value is
escaped, so a payload cannot inject markup or break the message envelope.

---

## 5. Reliability

| Requirement | How it's met |
| --- | --- |
| Notifications are asynchronous | `emit()` writes the row and hands off to RQ (when `REDIS_URL` is set) or an in-process thread pool. |
| User actions never wait for Telegram | `emit()` performs no network I/O on the caller's thread and never raises. |
| Queue while Telegram is unavailable | Failed sends stay `pending` with a `next_attempt_at`; the worker sweeps them. |
| Automatic retry | Exponential backoff — 1m, 2m, 4m, 8m … capped at 1h, up to `NOTIFY_MAX_ATTEMPTS` (default 5). Permanent rejections (bad chat id, bot blocked) are not retried. |
| Delivery status recorded | Per-recipient `{chat_id, ok, message_id, error}` on every event. |
| No duplicates | Unique `dedupe_key`. Supply your own, or the service fingerprints (platform, event, reference, payload) in a 5-minute window. A partially-delivered event skips the chats that already succeeded on retry. |

Two more safety nets: events wedged in `sending` by a killed worker are
reclaimed after 15 minutes, and concurrent workers claim rows with a guarded
`UPDATE` so an event is never sent twice.

---

## 6. Message format

```
🔔 QUATA ALERT

Platform:
QuataPay

Priority:
🟢 INFO

Event:
New User Registration

Status:
SUCCESS

Name:
John Doe

Email:
john@example.com

Phone:
+2376XXXXXXXX

Country:
Cameroon

Reference:
USR-000245

Date:
25 Jul 2026

Time:
14:30
```

Priority sits directly under Platform so severity is readable before the
event name — on a phone lock screen that's often all you get. The emoji
signal lives there and only there; `Status` is a plain word, so the two
channels don't compete.

Banners: `🔔 QUATA ALERT` · `🚨 SECURITY ALERT` ·
`💰 LARGE TRANSACTION ALERT` · `❌ SYSTEM ALERT` · `📊 QUATA DAILY SUMMARY`.

Priorities: 🟢 INFO · 🟡 WARNING · 🟠 IMPORTANT · 🔴 CRITICAL. Assigned
automatically from the event catalogue; a publisher may override.

**Timestamps are WAT (UTC+1, no DST)** — QUATA's operating timezone. The
rendered value carries no suffix, per the specified format. If QUATA ever
operates across zones, `DISPLAY_TZ` in
[`formatter.py`](../backend/app/services/notifications/formatter.py) is the
single place to revisit.

The exact envelope is pinned character-for-character by
`test_message_follows_the_standard_layout`, so a change to it is a
deliberate act rather than an accident.

### Large transactions

Any event in a monetary category whose `amount` reaches the configured
threshold (**Alert centre → Delivery → Large transaction threshold**, default
1,000,000 XAF) is re-flagged as `💰 LARGE TRANSACTION ALERT` at 🔴 CRITICAL,
carrying the full transaction detail. It re-flags the originating event rather
than emitting a second one, so administrators get one message, not two.

---

## 7. Daily business summary

Sent automatically at **Alert centre → Delivery → Daily summary hour (UTC)**
(default 21:00 UTC / 22:00 WAT). Preview or send on demand from the same page.

Because each platform owns its own database, the report is built from the
events published in the last 24 hours:

| Platform | Reported |
| --- | --- |
| QuataPay | New users · Deposits · Withdrawals · Transaction volume · **Revenue (sum of fees)** · Merchant registrations · KYC submitted/approved/rejected · **Pending KYC** |
| QuataFood | New restaurants · Orders · Completed deliveries · Cancelled orders |
| Abaqwa | Delivery requests · Completed deliveries · Active riders |
| QuataTrade | New users · Trades completed · Escrow transactions |
| QUATA AI | Total requests · Active users · API errors · System health |
| Quata Digital | Contact enquiries · Partner requests · Career applications · Newsletter signups · New staff accounts |

**Revenue** is the sum of the `fee` field across successful money events, so
a platform that omits `fee` reports zero — send it. **Pending KYC** is
submissions minus decisions inside the window, floored at zero (an approval
for an earlier window's submission would otherwise produce a negative).
Quata Digital's section is computed directly from this application's tables.

**Authoritative override.** A platform that wants exact figures publishes them
and they're reported verbatim:

```json
{
  "event": "summary.daily",
  "payload": {
    "metrics": {
      "new_users": 128,
      "deposits": 940,
      "withdrawals": 210,
      "transaction_volume": 48200000,
      "merchant_registrations": 6,
      "kyc_approved": 71
    }
  }
}
```

Use it for anything the event stream can't see — balances, MAUs, uptime.

---

## 8. Configuration reference

| Variable | Default | Purpose |
| --- | --- | --- |
| `TELEGRAM_BOT_TOKEN` | `""` | @QuataAlertsBot token. Site settings override this. Empty = record but never send. |
| `TELEGRAM_API_BASE` | `https://api.telegram.org` | Override for a proxy. |
| `TELEGRAM_DEFAULT_CHAT_IDS` | `""` | Comma-separated chat ids where alerts go (typically the ops group). Seeded on first boot only. |
| `TELEGRAM_ADMIN_USER_IDS` | `""` | Comma-separated private chat ids for individual administrators. Same allow-list; separate variable so people and groups can be provisioned independently. |
| `NOTIFY_ENABLED` | `true` | Env kill-switch. `false` overrides the admin toggle. |
| `NOTIFY_TIMEOUT_SECONDS` | `10` | Telegram HTTP timeout. |
| `NOTIFY_MAX_ATTEMPTS` | `5` | Retries before an event is marked failed. |
| `NOTIFY_DEDUPE_WINDOW_SECONDS` | `300` | Window for automatic fingerprint dedupe. |
| `NOTIFY_LARGE_TX_THRESHOLD` | `1000000` | Fallback threshold; the admin value wins. |
| `NOTIFY_INGEST_KEYS` | `[]` | `["platform:key", …]`. A platform with no key cannot publish. |
| `NOTIFY_REQUIRE_SIGNATURE` | `false` | Require the HMAC header. Recommended in production. |
| `NOTIFY_SIGNATURE_SKEW_SECONDS` | `300` | Replay window for signed requests. |
| `NOTIFICATION_LOG_RETENTION_DAYS` | `180` | Audit-log retention. |
| `NOTIFY_HEALTHCHECK_URL` | `""` | Absolute URL the worker probes to detect an API outage. Must point at the **API** host. Empty = watchdog off. |

Runtime settings (**Alert centre**, no restart needed): master delivery
toggle, global minimum priority, per-platform toggles, per-category toggles,
large-transaction threshold, daily-summary on/off and hour, the CPU / RAM /
disk alert thresholds, and the AI usage-spike rate.

---

## 9. Troubleshooting

| Symptom | Check |
| --- | --- |
| Nothing arrives in Telegram | Alert centre header — is the bot connection green, and is there at least one active recipient? Then **Send test notification**. |
| "Telegram bot token is not configured" | Set it in Site settings → Integrations, or `TELEGRAM_BOT_TOKEN`. |
| Events show as `suppressed` | Open the log entry — the reason is recorded (platform off, category off, priority below the floor, or no recipient matched). |
| Events stay `pending` | Telegram is unreachable or the worker isn't running. Check `systemctl status quata-notification-worker`. |
| A platform gets `401` | Its slug must match `NOTIFY_INGEST_KEYS` exactly and be sent in `X-Quata-Platform`. With signing on, check clock skew. |
| Duplicate alerts | The publisher isn't sending a stable `dedupe_key`, and its retries fall outside the 5-minute fingerprint window. |
| Alerts are too noisy | Raise the global minimum priority, turn off a category, or give individual recipients a higher `min_priority`. |
