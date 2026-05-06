# QUATA Digital — Ecosystem Platform

Production codebase for **QUATA Digital Enterprise** (Bamenda, Cameroon · founded
May 2025) — an integrated platform serving the public-facing marketing site,
seven product pages and a full internal cockpit on a single API.

Backend version: **0.3.0** · Frontend: **Next.js 16 / React 19**.

---

## What's in this repo

```
QuataDigital/
├─ frontend/                     Next.js 16 + Tailwind v4 + Radix UI primitives
├─ backend/                      FastAPI + SQLAlchemy 2 + Alembic + JWT/2FA
├─ docs/
│  ├─ PRODUCTION_AUDIT.md        Source-of-truth launch audit (numbered C/H/M items)
│  ├─ RUNBOOK.md                 On-call / deploy / rollback / incidents
│  ├─ ADMIN_USER_MANUAL.md       Non-technical admin guide
│  ├─ SCALING.md                 When to graduate from single-VPS
│  └─ BUSINESS_QUESTIONS.md      Open content questions (what's still placeholder)
├─ BOSS_ACTIONS.md               Boss-only outstanding items
├─ REMAINING_ITEMS.md            Single-page launch readiness dashboard
├─ deploy.sh                     One-shot VPS redeploy (systemd + PM2)
├─ docker-compose.yml            Local dev stack (Postgres + backend + frontend)
└─ scripts/
   ├─ fetch_images.py            Placeholder image puller (picsum)
   └─ load/launch.js             k6 load test for highest-volume public endpoints
```

The original brief referenced Prisma — Prisma is JavaScript-only, so the Python
backend uses **SQLAlchemy 2 + Alembic**, the canonical FastAPI equivalent.

---

## Architecture at a glance

| Layer | Tech | Notes |
|---|---|---|
| Frontend | Next.js 16.2.4 / React 19.2.4 / Tailwind v4 | App Router; 15 public routes + 23 admin routes, 55 prerendered. |
| UI primitives | Radix UI + CVA + `tw-animate-css` | shadcn-style, all components vendored locally in `components/ui/`. |
| Animation | `framer-motion` 12 | Hero / grid / reveal entry only. |
| Backend | FastAPI ≥ 0.118 + SQLAlchemy ≥ 2.0 + Pydantic v2 | 11 route modules, 20 ORM models. |
| Auth | JWT bearer + bcrypt + TOTP (pyotp) + recovery codes | Account lockout, password-reset tokens, mandatory 2FA for super_admin. |
| DB | SQLite (dev) / Postgres (prod) | Soft-delete is global via SQLAlchemy `do_orm_execute` event. |
| Migrations | Alembic | Single baseline `df03f53e48ce_initial_baseline.py` (20 tables). |
| Real-time | WebSocket `/ws/messages` | Per-process `Hub`; switch to Redis pub/sub for multi-worker (see SCALING). |
| Rate limiting | slowapi | Redis storage when `REDIS_URL` set, else in-process. |
| Email | pluggable (`console` / `smtp` / `disabled`) | SMTP2GO recommended for prod. |
| Bot protection | hCaptcha (server-side verify) | No-op when keys absent. |
| Observability | python-json-logger + Sentry SDK | JSON logs by default in prod; Sentry off until DSN supplied. |
| Uploads | Local disk under `UPLOAD_DIR/yyyy/mm/folder` | Pluggable; swap to S3 by replacing `services/uploads.py`. |

---

## Quick start (no Docker)

### Backend

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1                  # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
Copy-Item .env.example .env                 # then edit DATABASE_URL etc. for prod
uvicorn app.main:app --reload --port 8000
```

First boot:
- Creates `backend/quata.db` (SQLite — gitignored).
- Seeds 7 roles, 11 departments, 7 products, 1 open job, 3 launch posts, 3 CMS pages and the founder super-admin.
- Boots the API on `http://localhost:8000` (`/docs` for Swagger).

Default super-admin (also pre-filled on the login screen):

```
admin@quatadigital.com  /  ChangeMe!2026
```

The seeded admin has `must_reset_password=true`, so the first login forces a password change.

### Frontend

```powershell
cd frontend
Copy-Item .env.local.example .env.local     # adjust if API isn't on :8000
npm install
npm run dev
```

- Public site → `http://localhost:3000`
- Admin cockpit → `http://localhost:3000/admin/login`

### Docker (local stack)

```bash
docker compose up --build
```

Frontend `:3000`, backend `:8000`, Postgres `:5432` (user/pw `quata`/`quata`).

---

## Authentication & RBAC

### Auth
- **JWT bearer**, default 7-day expiry (`ACCESS_TOKEN_EXPIRE_MINUTES`).
- Login: `POST /api/v1/auth/login` → `{ access_token }` *or* `{ two_factor_required: true }` if TOTP is enrolled.
- Account lockout: 5 failed attempts → 15 minute lock (`MAX_LOGIN_ATTEMPTS`, `LOCKOUT_MINUTES`).
- Password reset: `POST /auth/forgot-password` → email a single-use token (default 30 min TTL).
- Frontend stores the token in `localStorage` (`quata_token`) and exposes a React `AuthProvider` ([frontend/lib/auth.tsx](frontend/lib/auth.tsx)).

### 2FA
- Per-user TOTP enrolment under `POST /me/2fa/enrol` → returns secret + SVG QR data URL.
- Verify with `POST /me/2fa/verify` → returns 8 one-time recovery codes (stored hashed).
- `super_admin` is forced to enrol (`REQUIRE_2FA_FOR_ROLES`).

### Roles seeded
| Slug | Permissions |
|---|---|
| `super_admin` | wildcard `*` |
| `admin` | `content:manage`, `partners:manage`, `careers:manage`, `staff:manage`, `rbac:manage`, `devices:manage`, `activity:view`, `analytics:view`, `newsletter:manage` |
| `manager` | `partners:manage`, `careers:manage`, `staff:manage`, `analytics:view` |
| `team_lead` | `careers:manage`, `partners:manage` |
| `staff` / `intern` / `contractor` | self-service only |

### Permission keys
`content:manage` · `partners:manage` · `careers:manage` · `staff:manage` ·
`rbac:manage` · `devices:manage` · `activity:view` · `analytics:view` ·
`newsletter:manage`

Backend enforcement: `Depends(require_permission("perm:key"))` in [backend/app/api/deps.py](backend/app/api/deps.py).
Frontend: `<PageShell requirePermission=…>` hides nav and renders a friendly 403.

---

## API surface

```
# --- Auth ---
POST   /api/v1/auth/login                        Public — sign in (TOTP-aware)
GET    /api/v1/auth/me                           Me + permissions + 2FA status
POST   /api/v1/auth/forgot-password              Public — request reset link (rate-limited)
POST   /api/v1/auth/reset-password               Public — consume reset token

# --- Self-service (any signed-in user) ---
PATCH  /api/v1/me                                Update profile fields
POST   /api/v1/me/password                       Change own password
GET    /api/v1/me/notifications                  Notification prefs (JSON)
PUT    /api/v1/me/notifications
POST   /api/v1/me/2fa/enrol                      Begin TOTP enrolment
POST   /api/v1/me/2fa/verify                     Complete enrolment, return recovery codes
POST   /api/v1/me/2fa/disable
POST   /api/v1/leave                             Submit leave request
POST   /api/v1/attendance/in
POST   /api/v1/attendance/out

# --- Public site ---
GET    /api/v1/products                          Published products
GET    /api/v1/products/{slug}
GET    /api/v1/jobs?published=true&department=
GET    /api/v1/jobs/{id}
POST   /api/v1/jobs/{id}/apply                   hCaptcha + email notification
GET    /api/v1/blog?published=true
GET    /api/v1/blog/{slug}
POST   /api/v1/contact                           hCaptcha + email notification
POST   /api/v1/partners/{type}                   business|strategic|investor|service
POST   /api/v1/newsletter/subscribe              hCaptcha
POST   /api/v1/newsletter/unsubscribe            Idempotent — never reveals membership
POST   /api/v1/track                             Anonymous page-view ping
GET    /api/v1/search?q=…                        Across products, posts, jobs

# --- Uploads ---
POST   /api/v1/uploads                           Auth — generic uploads (CMS covers, etc.)
POST   /api/v1/uploads/public                    Public — folder forced to /resumes
GET    /uploads/{yyyy}/{mm}/{folder}/{file}      Static file serving (FastAPI StaticFiles)

# --- Biometric device webhook ---
POST   /api/v1/devices/{id}/sync                 X-Device-Token (+ optional HMAC)
GET    /api/v1/devices/{id}/health

# --- Admin: read ---
GET    /api/v1/admin/overview                    Tiles + recent activity + attendance summary
GET    /api/v1/admin/partners?partner_type=&status=&q=&page=&page_size=
GET    /api/v1/admin/partners/{id}
GET    /api/v1/admin/partners/export.csv
GET    /api/v1/admin/products | /blog | /pages | /jobs
GET    /api/v1/admin/applications | /applications/v2 (filtered)
GET    /api/v1/admin/applications/{id}
GET    /api/v1/admin/staff | /staff/{id}         Staff list / detailed staff record
GET    /api/v1/admin/departments | /roles | /permissions
GET    /api/v1/admin/messages
GET    /api/v1/admin/leave
GET    /api/v1/admin/attendance?on=YYYY-MM-DD
GET    /api/v1/admin/devices
GET    /api/v1/admin/activity | /activity/v2 (filtered)
GET    /api/v1/admin/activity/distinct-actions | /distinct-resources
GET    /api/v1/admin/analytics
GET    /api/v1/admin/analytics/timeseries?days=14
GET    /api/v1/admin/contact
GET    /api/v1/admin/newsletter | /newsletter/export.csv

# --- Admin: write ---
POST/PUT/DELETE on:    products, blog, pages, jobs, departments, devices
POST                    /api/v1/admin/staff (invite)
PUT/DELETE              /api/v1/admin/staff/{id}
PATCH                   /api/v1/admin/applications/{id}    Status update
POST                    /api/v1/admin/devices/{id}/rotate  Rotate device API token
POST                    /api/v1/admin/messages             Send to all/dept/individual
PATCH                   /api/v1/admin/partners/{id}        Status change → email
PUT                     /api/v1/admin/partners/{id}/notes
PATCH                   /api/v1/admin/leave/{id}           Approve/reject → email
PATCH                   /api/v1/admin/leave/{id}/dates     Reschedule
POST/PUT/DELETE         /api/v1/admin/roles
DELETE                  /api/v1/admin/newsletter/{id}

# --- Admin: trash & retention ---
GET    /api/v1/admin/trash/{resource}            products|blog|pages|jobs|applications|partners|departments|devices|staff
POST   /api/v1/admin/trash/{resource}/{id}/restore
GET    /api/v1/admin/retention/preview           How many activity / pageview rows would be pruned
POST   /api/v1/admin/retention/prune             Hard-delete past the retention windows

# --- WebSocket ---
WS     /ws/messages?token=<jwt>                  Real-time admin messaging push
```

Full interactive schema at `http://localhost:8000/docs` (OpenAPI lives at `/api/v1/openapi.json`).

---

## Database

20 SQLAlchemy models cover the brief end-to-end:

| Group | Models |
|---|---|
| **Identity / RBAC** | `User`, `Role`, `RolePermission`, `Department`, `PasswordResetToken` |
| **Marketing site** | `Product`, `BlogPost`, `Page`, `Job`, `Application`, `PartnerRequest`, `ContactMessage`, `NewsletterSubscriber` |
| **Internal ops** | `Message`, `MessageRecipient`, `LeaveRequest`, `AttendanceLog`, `Device` |
| **Telemetry** | `ActivityLog`, `PageView` |

All except the lookup tables include a `SoftDeleteMixin` (`is_deleted`, `deleted_at`) and a global SQLAlchemy filter that auto-excludes deleted rows — `execution_options(include_deleted=True)` opts back in for the trash/restore views.

### Migrations

- **Dev** (`AUTO_CREATE_TABLES=true`): `Base.metadata.create_all` runs at boot. Zero-config.
- **Prod** (`AUTO_CREATE_TABLES=false`, enforced by the production-safety guard): use Alembic.

```powershell
cd backend
alembic upgrade head                                  # apply migrations
alembic revision --autogenerate -m "add foo column"   # after model changes — review the file
alembic downgrade -1                                  # rollback one revision
```

The single baseline `alembic/versions/df03f53e48ce_initial_baseline.py` builds all 20 tables on a fresh DB. `render-as-batch` is enabled for SQLite compatibility.

---

## Production safety guard

`Settings.assert_production_safe()` runs at process startup before lifespan. If
`ENVIRONMENT=production`, the app refuses to boot when **any** of these are still
at their dev defaults:

- `SECRET_KEY` is the placeholder
- `AUTO_CREATE_TABLES=true`
- `EMAIL_BACKEND=console`
- `SEED_ON_STARTUP=true` without explicit `ALLOW_PRODUCTION_SEED=true`
- `DEFAULT_ADMIN_PASSWORD` is the placeholder while seeding is enabled

The error lists every problem at once so you fix them in one go.

---

## Production deploy (current — single VPS)

The live deploy is a single VPS with:
- Backend: systemd unit `quata-digital-backend` running uvicorn on `127.0.0.1:8500`
- Frontend: PM2 process `Quata-Digi-F` running `next start` on `127.0.0.1:3500`
- Reverse proxy: Caddy/Nginx (TLS termination + routing)
- Domain: `quatadigital.com` (apex), `www.quatadigital.com` (currently mirrors)
- API host: `api.quatadigital.com`

One-shot redeploy:

```bash
# from anywhere on the VPS
bash /home/Quata-Digital/deploy.sh             # full
bash /home/Quata-Digital/deploy.sh backend     # backend only
bash /home/Quata-Digital/deploy.sh frontend    # frontend only
```

The script: pulls `main`, refreshes deps, runs `alembic upgrade head`, restarts
systemd + PM2, waits for the next-server to accept connections, then smoke-tests
`https://quatadigital.com/`, `/ecosystem`, and `/api/v1/products`. Logs to
`/var/log/quata-redeploy.log`.

### Required env vars

**Backend** ([backend/.env.example](backend/.env.example) is the template):

| Var | Required | Notes |
|---|---|---|
| `ENVIRONMENT=production` | ✅ | Triggers the safety guard. |
| `DATABASE_URL` | ✅ | `postgresql+psycopg://user:pw@host:5432/db` (psycopg 3). |
| `SECRET_KEY` | ✅ | `python -c "import secrets; print(secrets.token_urlsafe(64))"`. |
| `AUTO_CREATE_TABLES=false` | ✅ | Forces Alembic. |
| `SEED_ON_STARTUP=false` | ✅ | After first boot. |
| `EMAIL_BACKEND=smtp` | ✅ | + `SMTP_HOST/PORT/USER/PASSWORD/USE_TLS`, `EMAIL_FROM`, `EMAIL_NOTIFY_TO`. |
| `BACKEND_CORS_ORIGINS` | ✅ | JSON array of allowed origins. Localhost is auto-stripped in prod. |
| `PUBLIC_BASE_URL`, `FRONTEND_URL` | ✅ | Used in upload URLs / reset emails. |
| `HCAPTCHA_SITE_KEY` / `HCAPTCHA_SECRET_KEY` | recommended | Empty disables enforcement. |
| `SENTRY_DSN` / `SENTRY_ENV` | recommended | No-op when DSN unset. |
| `REDIS_URL` | optional | Shares rate-limit state across workers (see SCALING). |
| `DEVICE_REQUIRE_SIGNATURE` | optional | Forces HMAC on biometric webhook. |
| `ACTIVITY_LOG_RETENTION_DAYS` (90) / `PAGE_VIEW_RETENTION_DAYS` (180) | optional | Used by `/admin/retention/prune`. |

**Frontend** (`.env.production`):

| Var | Required | Notes |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | ✅ | e.g. `https://api.quatadigital.com/api/v1`. |
| `NEXT_PUBLIC_SITE_URL` | ✅ | e.g. `https://quatadigital.com`. |
| `NEXT_PUBLIC_HCAPTCHA_SITE_KEY` | recommended | Same site key as backend. |
| `NEXT_PUBLIC_CONTACT_PHONE` | optional | Hidden in footer/contact when unset. |

---

## Frontend design system

White-first; Africa-greens primary; warm-amber accent. Tokens in [frontend/app/globals.css](frontend/app/globals.css):

- `--brand: #0E5B4A` (deep emerald)
- `--accent: #E8B14A` (warm amber)
- `--ink: #0F1216`
- `--surface-soft: #FAFAF7`

Plus dark-mode palette and gradient/utility helpers (`gradient-brand`, `text-gradient-brand`, `dot-grid`, `ring-soft`, `ring-elevated`).

The dark/light toggle was deliberately removed — the app is light-only. Tokens
remain so CSS values match design specs.

---

## Security baseline

- Headers in [next.config.ts](frontend/next.config.ts): HSTS (`max-age=63072000; includeSubDomains`, no `preload` yet), `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy: camera=(), microphone=(), geolocation=(), payment=(), usb=()`, `X-DNS-Prefetch-Control: on`.
- **CSP shipped Report-Only** — flip the header name in `next.config.ts` to enforce after a clean reporting window.
- Rate limits per slowapi: `RATE_LIMIT_LOGIN=10/minute`, `RATE_LIMIT_PUBLIC_FORM=20/minute`, `RATE_LIMIT_PASSWORD_RESET=5/hour`. Public endpoints are decorated; auth/admin routes share the same key function (`get_remote_address`).
- All file uploads are extension- and MIME-checked, size-capped (default 25 MB, `MAX_UPLOAD_SIZE_MB`), tokenised filenames, and stored under date-partitioned folders.
- The biometric webhook validates the device's `api_token` and (when `DEVICE_REQUIRE_SIGNATURE=true`) an HMAC-SHA256 signature with a 5-minute timestamp skew window.
- Activity logging captures actor, action, resource, IP, user-agent and a JSON detail blob on every state-changing route.

---

## Where things are

| Concern | Location |
|---|---|
| Public website routes | [frontend/app/(site)/](frontend/app/(site)/) — 15 routes |
| Admin cockpit routes | [frontend/app/admin/](frontend/app/admin/) — 23 routes |
| API auth | [backend/app/api/routes_auth.py](backend/app/api/routes_auth.py) |
| API public site | [backend/app/api/routes_public.py](backend/app/api/routes_public.py) |
| API self-service | [backend/app/api/routes_self.py](backend/app/api/routes_self.py) |
| API admin (read) | [backend/app/api/routes_admin.py](backend/app/api/routes_admin.py) |
| API admin (CRUD) | [backend/app/api/routes_admin_crud.py](backend/app/api/routes_admin_crud.py) |
| API admin (extras / trash / retention) | [backend/app/api/routes_admin_extra.py](backend/app/api/routes_admin_extra.py) · [routes_security.py](backend/app/api/routes_security.py) |
| Devices | [backend/app/api/routes_devices.py](backend/app/api/routes_devices.py) |
| Uploads | [backend/app/api/routes_uploads.py](backend/app/api/routes_uploads.py) |
| WebSocket hub | [backend/app/api/routes_ws.py](backend/app/api/routes_ws.py) |
| Production-safety guard | [backend/app/core/config.py](backend/app/core/config.py) — `assert_production_safe()` |
| Email backend | [backend/app/services/email.py](backend/app/services/email.py) |
| hCaptcha | [backend/app/services/captcha.py](backend/app/services/captcha.py) |
| Upload service | [backend/app/services/uploads.py](backend/app/services/uploads.py) |
| TOTP / lockout / HMAC | [backend/app/services/security_extras.py](backend/app/services/security_extras.py) |
| Seed script | [backend/app/seeds/seed.py](backend/app/seeds/seed.py) |
| Alembic baseline | [backend/alembic/versions/df03f53e48ce_initial_baseline.py](backend/alembic/versions/df03f53e48ce_initial_baseline.py) |

---

## Pre-launch readiness

A single-page status dashboard lives in [REMAINING_ITEMS.md](REMAINING_ITEMS.md).
Boss-only blockers are tracked in [BOSS_ACTIONS.md](BOSS_ACTIONS.md).
The numbered audit (`C##`/`H##`/`M##` references in BOSS_ACTIONS) is in
[docs/PRODUCTION_AUDIT.md](docs/PRODUCTION_AUDIT.md).

---

## License

Proprietary — © QUATA Digital Enterprise.
