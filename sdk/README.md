# QUATA Notification SDK

Drop-in clients so QuataPay, QuataFood, Abaqwa, QuataTrade and QUATA AI can
feed **@QuataAlertsBot** without holding a Telegram token or duplicating the
delivery logic.

| File | Runtime | Dependencies |
| --- | --- | --- |
| [`python/quata_notify.py`](python/quata_notify.py) | Python 3.8+ | none (stdlib only) |
| [`typescript/quata-notify.ts`](typescript/quata-notify.ts) | Node 18+ | none |

Both are **single files** — copy them into your project. No package to
publish, no version to keep in sync, no supply-chain surface.

The full protocol, event catalogue and security model are in
[`../docs/NOTIFICATIONS.md`](../docs/NOTIFICATIONS.md).

---

## Setup

Ask the QUATA Digital admin for your platform's ingest key (generated with
`python -c "import secrets; print(secrets.token_urlsafe(32))"` and installed
in the API's `NOTIFY_INGEST_KEYS`). Then set:

```bash
QUATA_NOTIFY_URL=https://api.quatadigital.com/api/v1/notify/events
QUATA_PLATFORM=quatapay          # quatapay | quatafood | abaqwa | quatatrade | quata_ai
QUATA_INGEST_KEY=<your key>
QUATA_NOTIFY_SIGN=true           # leave on unless the server has signing disabled
QUATA_NOTIFY_ENABLED=true        # local kill-switch
```

Treat `QUATA_INGEST_KEY` like any other secret: environment only, never in
source control, rotate if leaked. It grants the ability to publish alerts as
your platform — nothing else. It cannot read data, and it cannot publish as a
different platform.

---

## Python

```python
from quata_notify import notify, Events

# In your deposit handler, after the transaction commits:
notify.publish(
    Events.DEPOSIT_SUCCESSFUL,
    {
        "full_name": user.full_name,
        "email": user.email,
        "phone": user.phone,
        "country": user.country,
        "amount": txn.amount,
        "currency": "XAF",
        "fee": txn.fee,
        "payment_method": "MTN MoMo",
        "transaction_id": txn.reference,
        "sender": txn.sender_name,
        "receiver": txn.receiver_name,
    },
    reference=txn.reference,
    dedupe_key=f"quatapay:deposit:{txn.id}",
)
```

`publish()` returns immediately — a background daemon thread does the HTTP.
It never raises and never blocks your request.

Before a deliberate shutdown, drain in-flight alerts:

```python
notify.flush(timeout=5)
```

Expose the counters on your health endpoint so a silently-broken integration
is visible:

```python
{"notifications": notify.stats}
# {'published': 1402, 'delivered': 1400, 'failed': 2, 'dropped': 0}
```

Smoke-test the wiring:

```bash
QUATA_NOTIFY_URL=... QUATA_PLATFORM=... QUATA_INGEST_KEY=... \
  python quata_notify.py
```

## TypeScript / Node

```ts
import { notify, Events } from "./quata-notify";

notify.publish(
  Events.ORDER_PLACED,
  {
    restaurant: order.restaurantName,
    order_number: order.number,
    customer: order.customerName,
    rider: order.riderName,
    amount: order.total,
    currency: "XAF",
    delivery_address: order.address,
  },
  { reference: order.number, dedupeKey: `quatafood:order:${order.id}` },
);
```

Same contract: synchronous return, never throws. `await notify.flush()`
before shutdown, and surface `notify.stats` on your health endpoint.

---

## Rules that keep this working

**Always pass a `dedupe_key`.** It's the difference between an at-least-once
pipeline that's safe to retry and one that pages your administrators twice at
3am. Use something stable and unique per business event —
`quatapay:deposit:<txn id>`, not a timestamp.

**Publish after your transaction commits.** Alerting on a transaction that
later rolls back means Telegram says something happened that didn't.

**Never put credentials in the payload.** The service strips anything that
looks like a password, OTP, PIN, token, API key or secret before storing it —
but that's a backstop, not permission. Don't send them.

**Send amounts as plain numbers.** `25000`, not `"25,000 XAF"`. The service
formats and thousands-separates them, and compares them against the
large-transaction threshold — a pre-formatted string defeats both.

**Use the catalogue key that matches the event.** A key that isn't in the
catalogue still gets delivered (categorised by namespace, at INFO), so ship
first and ask for a curated label later — but don't reuse an unrelated key to
avoid the conversation, because priorities and categories are what
administrators filter on.

---

## Daily business summary

The service derives your platform's daily figures from the events you
publish. To report authoritative numbers instead — anything the event stream
can't see, like balances or MAUs — publish once a day:

```python
notify.publish(Events.DAILY_SUMMARY, {
    "metrics": {
        "new_users": 128,
        "deposits": 940,
        "withdrawals": 210,
        "transaction_volume": 48_200_000,
        "merchant_registrations": 6,
        "kyc_approved": 71,
    },
})
```

Whatever is in `metrics` is reported verbatim in place of the derived counts.

---

## Troubleshooting

| Symptom | Cause |
| --- | --- |
| `not configured … events will be discarded` | One of `QUATA_NOTIFY_URL` / `QUATA_PLATFORM` / `QUATA_INGEST_KEY` is unset. |
| `rejected with HTTP 401` | Wrong key, wrong platform slug, or (with signing on) clock skew over 5 minutes. Check NTP. |
| `rejected with HTTP 503` | The server has no `NOTIFY_INGEST_KEYS` configured at all. |
| `stats.failed` climbing | The service is unreachable. Events already accepted by it are retried server-side; these never got that far. |
| `stats.dropped` above zero | The local queue filled while the service was down. Raise `max_queue`, or accept the loss. |
| Published fine, nothing in Telegram | Server-side. Ask the admin to check **Alert centre → Logs** — the row will show `suppressed` with a reason, or a delivery error. |
