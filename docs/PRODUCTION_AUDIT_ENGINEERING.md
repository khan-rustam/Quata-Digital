# QUATA Digital — Engineering production audit (2026-05-21)

Companion to [PRODUCTION_AUDIT.md](PRODUCTION_AUDIT.md), which tracks
**boss-blocked** content/credential items only. This document tracks
**engineering** findings from the deep-dive code review run on 2026-05-21
(four parallel audits across security, backend correctness/perf, frontend
Next.js 16, and deploy/ops/infra).

A large share of the punch list has been resolved in the accompanying
commit; the remainder is captured here under **What's still open** so it
doesn't slip through the cracks.

Last reviewed: **2026-05-21**

---

## What shipped in this sprint

### Backend — security

| ID | Finding | Fix |
|---|---|---|
| S1 | No CSP / HSTS / X-Frame-Options on API responses | `backend/app/core/security_headers.py` middleware, wired in `main.py`. CSP starts in Report-Only; flip `CSP_ENFORCE=true` after 30 days. |
| S2 | Swagger / Redoc / OpenAPI enumerable in production | Hard-gated on `settings.is_production` in `main.py`. |
| S3 | `must_reset_password` was UI-only | New strict `get_current_user` rejects the bearer until `must_reset_password=False`. Lenient variant exposed for `/auth/me`, `/me/password`, 2FA enrolment. |
| S4 | `REQUIRE_2FA_FOR_ROLES` was UI-only | Same strict dependency rejects super_admins without enrolled TOTP. |
| S5 | 12 admin endpoints used `Depends(get_current_user)` instead of `require_permission` — including **PATCH /admin/leave/{id}** (anyone could approve own leave) | All converted to `require_permission(...)`. |
| S6 | `/admin/retention/prune` (destructive) was gated on `activity:view` | Moved to `rbac:manage`. |
| S7 | `X-Forwarded-For` blindly trusted | `get_client_ip()` now requires the immediate peer to be in `TRUSTED_PROXIES` (RFC1918 + loopback by default). |
| S8 | `/api/v1/track` was unauth + unrated + untyped `dict` | `TrackPageviewIn` Pydantic schema + `@limiter.limit("60/minute")`. |
| S9 | `/uploads/public` — anonymous, no captcha, accepted `.svg` | Captcha verify + rate limit + `public=True` flag drops SVG / sets stricter allow-list. |
| S10 | WebSocket: no Origin check, no message-size cap | `_origin_allowed()` matches `settings.cors_origins`; 4 KB frame cap. |
| S11 | Newsletter broadcast body unsanitised | `_sanitize_broadcast_body()` strips control chars; 100 KB cap via Pydantic. |
| S12 | `python-jose` (CVE-2024-33663/33664) | Migrated to `PyJWT >= 2.9`. |
| S13 | No JWT rotation on password change | `password_changed_at` column + `pwc` JWT claim; lenient dep rejects superseded tokens. |
| S14 | CORS wildcard methods/headers with credentials | Explicit method + header list. |

### Backend — correctness / performance

| ID | Finding | Fix |
|---|---|---|
| C1 | No Postgres driver in `requirements.txt` | `psycopg[binary] >= 3.2.3` now bundled. |
| C2 | Docker image didn't ship `alembic/` | New multi-stage Dockerfile copies `alembic/`, `alembic.ini`, runs as non-root, exposes a `HEALTHCHECK`, runs uvicorn with `--workers 2 --proxy-headers --forwarded-allow-ips=* --timeout-graceful-shutdown 20`. |
| C3 | Single uvicorn worker without `--proxy-headers` | Fixed (see C2). |
| C4 | Missing hot-path indexes | `g7l8m9n0o1p2_perf_indexes_pwc.py` adds indexes on `page_views.created_at`, `activity_logs.(actor_id, created_at)`, `activity_logs.created_at`, `applications.job_id`, `attendance_logs.user_id`, `leave_requests.user_id`, `message_recipients.(message_id, user_id)`, `message_recipients.user_id`. |
| C5 | N+1 in admin list endpoints | `selectinload` added to `/admin/messages`, `/admin/overview` recent_apps, `/admin/leave`, `/admin/attendance`, `/admin/activity`. |
| C6 | `/admin/analytics/timeseries` issued `3 × days` queries | Collapsed to 3 grouped queries (one per series). |
| C7 | CSV exports buffered entire result set | `admin_export_partners` + `export_newsletter_csv` now stream via `StreamingResponse` + `yield_per(500)`. |
| C8 | Pillow no decompression-bomb guard | `Image.MAX_IMAGE_PIXELS = 50_000_000`; explicit 12k px per-axis cap. |
| C9 | `datetime.utcnow()` (deprecated) | Replaced with `datetime.now(timezone.utc)` in models + uploads. |
| C10 | `print()` in `services/email.py:51` | Removed; `log.info` already covers it. |
| C11 | `/health` mixed liveness + readiness, leaked DSN text | Split into `/health/live` (no DB) + `/health/ready` (DB, generic message). |
| C12 | `public_site_settings` did a full table scan per request | Added 15 s TTL `_PUBLIC_CACHE`, invalidated by `invalidate_cache`. |

### Deploy / ops / infra

| ID | Finding | Fix |
|---|---|---|
| D1 | No `.dockerignore` anywhere | `backend/.dockerignore`, `frontend/.dockerignore`. |
| D2 | No root `.gitignore` | Added — catches `.env`, `*.db`, OS junk at repo root. |
| D3 | `docker-compose.yml` ships dev defaults, ports bound to `0.0.0.0` | Ports now bound to `127.0.0.1` only; header warns and the production-safety guard catches misuse. |
| D4 | Frontend Dockerfile shipped full `node_modules` | Switched to `output: 'standalone'` + non-root runtime image. ~250 MB vs ~1 GB. |
| D5 | `deploy.sh` no rollback on failure | Captures pre-deploy SHA + best-effort `pg_dump` snapshot, prints rollback recipe on any non-zero exit via trap. |
| D6 | CI used `npm ci`, deploy used `pnpm` | Aligned `deploy.sh` on `npm ci` (matches the actual `package-lock.json`). |
| D7 | Reverse proxy / systemd unit / PM2 ecosystem not in repo | `infra/caddy/Caddyfile`, `infra/systemd/quata-digital-backend.service`, `infra/pm2/ecosystem.config.js`. |
| D8 | No DB backup recipe | `infra/cron/backup-postgres.sh` ships nightly `pg_dump` → S3 with retention prune. |
| D9 | Retention prune cron not committed | Template at `infra/cron/retention-prune.cron`. |

### Frontend

| ID | Finding | Fix |
|---|---|---|
| F1 | `/blog/[slug]` + `/careers/[id]` inherited the homepage title | `generateMetadata()` returns per-record title / description / OG / canonical. |
| F2 | CMS markdown rendered as `whitespace-pre-line` | Both detail pages now use `renderMarkdownToHtml()`. |
| F3 | Fake blog fallback rows used `new Date()` (hydration drift) | Removed; explicit "couldn't load latest stories" state replaces it. |
| F4 | CMS markdown allowed any URL scheme | `safeUrl()` allow-lists `https`, `mailto`, `tel`, root-relative, anchors, `data:image/*`. |
| F5 | Async `<Footer>` blocked first paint on slow settings API | Wrapped in `Suspense` with a chrome skeleton. |
| F6 | No `error.tsx` in `(site)` or `admin` segments | Both added; admin variant keeps the sidebar visible. |
| F7 | No `next/image` `remotePatterns`; missing `sizes` on `<Image fill>` | `next.config.ts` allowlists `quatadigital.com`, `*.quatadigital.com`, S3/R2/B2 hosts; `sizes` added on Hero + image_text variants. |
| F8 | No central 401 handling | `setUnauthorizedHandler()` wired in `auth.tsx`; auto-logout + redirect on any 401. |
| F9 | `force-dynamic` on `/search` shell | Removed; the actual query lives in a Suspense-bounded client component. |
| F10 | `host:` in `robots.ts` | Dropped (non-standard). |
| F11 | No `revalidate` on sitemap | Set to 1 hour. |
| F12 | No global `:focus-visible` style; no `prefers-reduced-motion` | Both added to `globals.css`. |
| F13 | Navbar: no `aria-current`, no Escape close, no body-scroll lock | All three fixed. |
| F14 | `jobJsonLd.datePosted = new Date()` (kept moving forward) | Uses `job.published_at` / `job.created_at`. |
| F15 | `formatDate` was en-US, no invalid-date guard | Pinned to `en-GB`, NaN guard returns "". |
| F16 | Dev-seed credentials banner gated on `NODE_ENV` | Now requires explicit `NEXT_PUBLIC_SHOW_DEV_SEED=1`. |
| F17 | OG inheritance only — no per-post or per-job cards | `app/(site)/blog/[slug]/opengraph-image.tsx` + `app/(site)/careers/[id]/opengraph-image.tsx` render per-record cards. |
| F18 | Newsletter delete used `window.confirm` | Switched to the themed `ConfirmDialog`. |
| F19 | `lib/datetime.ts` introduced for hydration-safe admin timestamps | New helper available; admin-page call sites can adopt it incrementally. |

---

## What's still open

These are real findings from the audit that we deliberately did **not**
ship in this commit. Most either require external accounts/credentials,
or are larger refactors that benefit from a focused follow-up sprint.

| Severity | Item | Why deferred |
|---|---|---|
| Critical (Boss) | Domain canonicalisation on Hostinger | Tracked under [C-02](PRODUCTION_AUDIT.md#c-02). |
| Critical (Boss) | hCaptcha keys | [H-02](PRODUCTION_AUDIT.md#h-02). |
| High (Boss) | Sentry DSN | [H-03](PRODUCTION_AUDIT.md#h-03). |
| High (Ops) | SPF / DKIM / DMARC records for `quatadigital.com` | Boss task at Hostinger DNS. |
| High (Ops) | Uptime monitor + alerting on `/health/ready` | Pick provider (UptimeRobot / Better Stack). |
| High (Ops) | Log aggregation beyond `journalctl` | Pick provider (Loki / Grafana Cloud / Better Stack). |
| High (Ops) | TLS cert renewal alerting | Add an external SSL monitor; Caddy renews automatically but a silent failure must page someone. |
| High (Backend) | Auth bearer in `localStorage` | Moving to `httpOnly` cookie is a sizeable refactor across every fetch site. Recommended in a dedicated PR. |
| High (Backend) | Newsletter broadcast still synchronous when `REDIS_URL` unset | Provision Redis + RQ worker, then `UPLOAD_BACKEND=s3` while you're at it. |
| Medium | CSP nonce — frontend still allows `'unsafe-inline'` | Coupled to the cookie-auth refactor; tackle together. |
| Medium | Pagination on remaining admin lists (messages, analytics, careers, media, staff/[id]) | Touches multiple UI screens; one focused PR. |
| Medium | Migrate admin pages to `lib/datetime.ts` | Mechanical — find/replace `toLocaleString()` call sites. |
| Medium | Adopt OG images for `/ecosystem`, `/ecosystem/[slug]`, `/partners/[type]`, `/privacy`, `/terms`, `/search` | Optional — root `app/opengraph-image.tsx` already covers them. |
| Medium | Cloudflare in front of the apex | Decision pending; flagged in [PRODUCTION_AUDIT.md](PRODUCTION_AUDIT.md). |
| Low | Bcrypt 72-byte silent truncation in `core/security.py:11` | Add an explicit `len > 72` rejection. |
| Low | Device webhook signing default `False` | Flip to `True` after biometric devices are configured in admin. |
| Low | 17 bare `except Exception` blocks across 11 backend files | Log → Sentry. |

---

## How this doc relates to the others

* [`docs/PRODUCTION_AUDIT.md`](PRODUCTION_AUDIT.md) — boss-blocked
  content / credential items only.
* [`docs/PRODUCTION_AUDIT_ENGINEERING.md`](PRODUCTION_AUDIT_ENGINEERING.md) — *this file*, engineering scope.
* [`REMAINING_ITEMS.md`](../REMAINING_ITEMS.md) — single-page status board.
* [`docs/RUNBOOK.md`](RUNBOOK.md) — on-call / deploy / rollback.
* [`infra/README.md`](../infra/README.md) — production scaffolding install
  guide.
