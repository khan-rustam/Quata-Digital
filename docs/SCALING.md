# Scaling notes

The QUATA backend is built to launch as **a single uvicorn worker on a single
VPS**. That fits the May 2026 launch traffic profile but won't scale
horizontally without a few additions. This doc captures what changes when.

---

## What works today (single worker, single VPS)

| Subsystem | Implementation | Why it's safe at this scale |
|---|---|---|
| Rate limiter | slowapi in-process | Only one process is counting requests. Backed by `REDIS_URL` automatically when set ([core/rate_limit.py](../backend/app/core/rate_limit.py)). |
| WebSocket hub | In-process pub/sub (`Hub` in [routes_ws.py](../backend/app/api/routes_ws.py)) | Every connected client lives in the same process so a `broadcast()` reaches all of them. |
| Sessions | Stateless JWT | No server-side session store needed. |
| Background jobs | Synchronous in-request (with best-effort `try/except`) | Acceptable while volume is low — partner-submission emails, application emails, leave decisions all dispatch in-band. |
| Uploads | Local disk in `uploads/` | One writer, no contention. |
| Soft-delete filter | SQLAlchemy `do_orm_execute` event ([db/session.py](../backend/app/db/session.py)) | No external dependencies. |

---

## When to graduate to multi-worker

Pick a trigger and pre-decide. Common ones:

- **CPU > 70% sustained** for an hour on the VPS → time to add workers.
- **`/health` p95 > 500 ms** → time to add workers.
- **More than ~50 concurrent WebSocket clients** → time to move the hub.
- **Traffic spike that exhausts the rate limiter unfairly** (because each worker has its own counter) → time to share limit state via Redis.

---

## Going to N workers on one box

1. Start uvicorn with `--workers N` (or use gunicorn + uvicorn workers in the systemd unit).
2. Set `REDIS_URL` in the env. The slowapi limiter automatically picks it up — without this, the effective rate limit becomes `N × the configured limit`.
3. The WebSocket hub still won't reach clients on other workers. Two options:
   - **Stay single-worker for the WS process** — run a dedicated 1-worker uvicorn for `/ws/*` behind the proxy and N workers for everything else.
   - **Rewrite `Hub` to use Redis pub/sub or Postgres LISTEN/NOTIFY.** The contract (`broadcast(user_ids, event)`) doesn't change; only the implementation. ~50-line change.
4. Move sync email dispatch off the request path — drop the email helpers into a Redis queue (RQ / Arq) and run a worker. The current `try/except` swallow is fine for an in-process best-effort, but on retry it's better to have a queue.

---

## Going multi-region or multi-box

1. All of the above, plus:
2. **Switch from local-disk uploads to S3-compatible object storage.** [`backend/app/services/uploads.py`](../backend/app/services/uploads.py) is intentionally a small facade — replace the local-disk write with an S3 PUT, switch `PUBLIC_BASE_URL` to the bucket's CDN URL.
3. **Move the database to a managed Postgres instance.** Neon, Supabase, Railway, DO Managed Postgres, RDS — any will do. Set `DATABASE_URL` and `psycopg[binary]` (already installed by [deploy.sh](../deploy.sh)) handles the rest.
4. **Put Cloudflare in front of the apex domain.** Cache OG images, static assets and `/products` aggressively. The frontend security headers play nice with the CF Free plan.
5. **Pin a single source of truth for sessions / lockout.** The `users.failed_login_attempts` and `users.locked_until` columns already serialize on the database — multi-box is fine for auth.

---

## Testing under load before launch

A k6 script targeting the highest-volume public endpoints lives at [scripts/load/launch.js](../scripts/load/launch.js). Run it against a staging environment that has the same shape as production:

```bash
k6 run -u 50 -d 60s scripts/load/launch.js
```

The script targets `/track`, `/products`, `/partners`, `/contact`. Point the
base URL via env var per the script's header.

---

## Indexes worth knowing about

The baseline migration creates indexes you'd expect:

- `users.email` (unique), `users.biometric_id`
- `partner_requests.partner_type`
- `jobs.department`, `jobs.slug`
- `blog_posts.slug`, `products.slug`
- `page_views.path`, `page_views.visitor_id`
- `activity_logs.actor` is **not** indexed — if `/admin/activity/v2?actor_id=` becomes a hot path under load, add one.

The retention prune endpoint ([routes_admin_extra.py:629](../backend/app/api/routes_admin_extra.py)) keeps `activity_logs` and `page_views` from growing unbounded. Cron it nightly.
