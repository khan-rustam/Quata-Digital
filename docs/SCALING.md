# Scaling notes

The QUATA backend is built to launch as a single uvicorn worker on a single
VPS. That's fine for the May 2026 launch traffic profile but won't scale
horizontally without a few additions. This doc captures what changes when.

## What works today (single worker, single VPS)

| Subsystem        | Backend                       | Why it's safe at this scale |
|------------------|-------------------------------|------------------------------|
| Rate limiter     | slowapi in-process            | Only one process counts requests |
| WebSocket hub    | In-process pub/sub (`Hub`)    | Every connected client lives in the same process |
| Sessions         | Stateless JWT                 | No server-side session store needed |
| Background jobs  | Synchronous in-request        | Acceptable while volume is low |
| Uploads          | Local disk in `uploads/`      | One writer, no contention |

## When to graduate to multi-worker

Pick a trigger and pre-decide. Common ones:

- **CPU > 70% sustained** for an hour on the VPS → time to add workers.
- **/health p95 > 500 ms** → time to add workers.
- **More than ~50 concurrent WebSocket clients** → time to move the hub.
- **Bot rings burning the rate limiter** → time to share limit state.

## Going to N workers on one box

1. Start uvicorn with `--workers N` (or use gunicorn + uvicorn workers).
2. Set `REDIS_URL` in the env. The rate limiter automatically picks it up
   (see `app/core/rate_limit.py`). Without this step, every worker has its
   own counter and the effective rate-limit is `N × the configured limit`.
3. The WebSocket hub still won't reach clients on other workers — rewrite
   `Hub` to use Redis pub/sub. The current `Hub` lives in
   `app/services/messaging.py`; the contract (broadcast(message)) doesn't
   change, only the implementation. About a 50-line change.

## Going multi-region or multi-box

1. All of the above, plus:
2. Switch from local-disk uploads to S3-compatible object storage.
   `app/services/uploads.py` was deliberately written behind a small
   facade so this is a one-file swap.
3. Move the SQLite/Postgres DB to a managed instance (we recommend
   Postgres on Neon, Supabase, Railway or DO Managed Postgres).
4. Put Cloudflare in front of the apex domain. Cache OG images, static
   assets and `/products` aggressively.

## Testing under load before launch

Run the k6 script in `scripts/load/launch.js` against a staging environment
that has the same shape as production:

```
k6 run -u 50 -d 60s scripts/load/launch.js
```

The script targets the highest-volume public endpoints (`/track`,
`/products`, `/partners`, `/contact`).
