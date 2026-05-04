# QUATA Digital — Ecosystem Platform

A production-ready foundation for **QUATA Digital Enterprise** — Africa's connected operating system.

This monorepo contains:

- **Public website** (Next.js 16 App Router + Tailwind v4 + shadcn-style UI) marketing the seven-product ecosystem.
- **Internal admin dashboard** (CMS, partner pipeline, careers, full staff management, messaging, leave, attendance, devices, activity, analytics).
- **FastAPI backend** with SQLAlchemy 2, JWT auth, fine-grained RBAC, and seed data.
- **Docker** setup with Postgres for one-command deploys.

> Note on stack: the original brief specified Prisma; Prisma is JavaScript-only.
> This stack uses **SQLAlchemy + Alembic-ready models** which is the canonical
> Python equivalent for FastAPI.

---

## Repo layout

```
QuataDigital/
├─ frontend/                         # Next.js 16 + Tailwind v4 + shadcn primitives
│  ├─ app/
│  │  ├─ (site)/                     # Public website (route group)
│  │  │  ├─ page.tsx                 # Home
│  │  │  ├─ ecosystem/[slug]/        # Dynamic product pages
│  │  │  ├─ partners/[type]/         # 4 partner paths with forms
│  │  │  ├─ careers/[id]/            # Job listings + applications
│  │  │  ├─ blog/[slug]/             # CMS-driven posts
│  │  │  ├─ contact, about/
│  │  ├─ admin/                      # Internal cockpit (auth-gated)
│  │  │  ├─ login/
│  │  │  ├─ overview, cms, products, partners, careers,
│  │  │  ├─ staff, departments, roles,
│  │  │  ├─ messages, leave, attendance, devices,
│  │  │  ├─ activity, analytics
│  │  ├─ globals.css                 # Tailwind v4 theme tokens
│  ├─ components/
│  │  ├─ ui/                         # shadcn-style primitives
│  │  ├─ site/                       # Marketing surface (nav, hero…)
│  │  ├─ admin/                      # Dashboard surface (sidebar, tables…)
│  │  └─ forms/                      # Reusable form components
│  └─ lib/                           # api client, auth, ecosystem data
│
├─ backend/                          # FastAPI service
│  ├─ app/
│  │  ├─ main.py                     # FastAPI app + lifespan + seed
│  │  ├─ core/                       # config, security (JWT, hashing)
│  │  ├─ db/                         # SQLAlchemy session
│  │  ├─ models/                     # 14 ORM models
│  │  ├─ schemas/                    # Pydantic v2 DTOs
│  │  ├─ api/
│  │  │  ├─ deps.py                  # auth, RBAC, activity logger
│  │  │  ├─ routes_auth.py           # /auth/login, /auth/me
│  │  │  ├─ routes_public.py         # public site endpoints
│  │  │  ├─ routes_self.py           # leave / attendance self-service
│  │  │  └─ routes_admin.py          # admin endpoints
│  │  └─ seeds/seed.py               # idempotent seed (roles, products…)
│  ├─ requirements.txt
│  ├─ Dockerfile
│  └─ .env.example
│
├─ docker-compose.yml                # Postgres + backend + frontend
└─ README.md
```

---

## Quick start (local dev, no Docker)

### 1. Backend (FastAPI)

```bash
cd backend
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS / Linux:
# source .venv/bin/activate

pip install -r requirements.txt
copy .env.example .env          # PowerShell: Copy-Item .env.example .env
uvicorn app.main:app --reload --port 8000
```

The first boot:
- Creates the SQLite DB at `backend/quata.db`.
- Seeds roles, departments, products, sample staff, jobs, blog posts, partner requests and a biometric device.
- Boots the API on http://localhost:8000 (Swagger UI at `/docs`).

Default super admin (also shown on the login screen):

```
admin@quata.digital  /  ChangeMe!2026
```

### 2. Frontend (Next.js)

In a second terminal:

```bash
cd frontend
copy .env.local.example .env.local      # adjust if your API isn't on :8000
npm install                             # already done if you cloned with deps
npm run dev
```

Open http://localhost:3000 — public site.
Open http://localhost:3000/admin/login — admin cockpit.

---

## Quick start with Docker

```bash
# from repo root
docker compose up --build
```

- Frontend → http://localhost:3000
- Backend  → http://localhost:8000 (Swagger at `/docs`)
- Postgres → localhost:5432 (user/pw `quata`/`quata`)

---

## Authentication & RBAC

- **JWT bearer tokens**, 7-day expiry by default (`ACCESS_TOKEN_EXPIRE_MINUTES`).
- Login: `POST /api/v1/auth/login` returns `{ access_token }`.
- Authenticated requests pass `Authorization: Bearer <token>`.
- The frontend stores the token in `localStorage` (`quata_token`) and provides a React `AuthProvider` (`frontend/lib/auth.ts`).

### Roles seeded
- `super_admin` — wildcard access (`*`)
- `admin` — content, partners, careers, staff, RBAC, devices, activity, analytics
- `manager` — partners, careers, staff, analytics
- `team_lead` — partners, careers
- `staff`, `intern`, `contractor` — base access (self-service only)

### Permission keys used
- `content:manage` — CMS, products
- `partners:manage` — Partner request triage
- `careers:manage` — Jobs, applicants
- `staff:manage` — Employee management
- `rbac:manage` — Roles & permissions
- `devices:manage` — Biometric devices
- `activity:view` — Activity logs
- `analytics:view` — Website analytics

Backend enforces with `Depends(require_permission("perm:key"))`. Frontend hides nav items and shows a friendly 403 via `<PageShell requirePermission=…>`.

---

## API surface (selected)

```
# --- Auth ---
POST   /api/v1/auth/login                              Public — sign in
GET    /api/v1/auth/me                                 Me + permissions

# --- Public site ---
GET    /api/v1/products
GET    /api/v1/products/{slug}
GET    /api/v1/jobs?published=true&department=
GET    /api/v1/jobs/{id}
POST   /api/v1/jobs/{id}/apply                         Triggers email notification
GET    /api/v1/blog?published=true
GET    /api/v1/blog/{slug}
POST   /api/v1/contact                                 Triggers email notification
POST   /api/v1/partners/{type}                         business|strategic|investor|service
POST   /api/v1/track                                   Page view tracking

# --- Uploads ---
POST   /api/v1/uploads                                 Auth — generic uploads (CMS covers, etc.)
POST   /api/v1/uploads/public                          Public — restricted to /resumes folder
GET    /uploads/{yyyy}/{mm}/{folder}/{file}            Static file serving

# --- Self-service ---
POST   /api/v1/leave
POST   /api/v1/attendance/in
POST   /api/v1/attendance/out

# --- Biometric device webhook ---
POST   /api/v1/devices/{id}/sync                       Auth via X-Device-Token header
GET    /api/v1/devices/{id}/health

# --- Admin: read ---
GET    /api/v1/admin/overview
GET    /api/v1/admin/partners?partner_type=&status=&q=&page=&page_size=
PATCH  /api/v1/admin/partners/{id}                     Triggers email notification
GET    /api/v1/admin/partners/export.csv
GET    /api/v1/admin/products
GET    /api/v1/admin/blog
GET    /api/v1/admin/pages
GET    /api/v1/admin/jobs
GET    /api/v1/admin/applications
GET    /api/v1/admin/staff
GET    /api/v1/admin/departments
GET    /api/v1/admin/roles
GET    /api/v1/admin/messages
GET    /api/v1/admin/leave
GET    /api/v1/admin/attendance?on=YYYY-MM-DD
GET    /api/v1/admin/devices
GET    /api/v1/admin/activity
GET    /api/v1/admin/analytics
GET    /api/v1/admin/contact

# --- Admin: write (CRUD) ---
POST   /api/v1/admin/products                          PUT /:id, DELETE /:id
POST   /api/v1/admin/blog                              PUT /:id, DELETE /:id
POST   /api/v1/admin/pages                             PUT /:id, DELETE /:id
POST   /api/v1/admin/jobs                              PUT /:id, DELETE /:id
PATCH  /api/v1/admin/applications/{id}                 Update applicant status
POST   /api/v1/admin/staff                             PUT /:id, DELETE /:id (soft-suspends)
POST   /api/v1/admin/departments                       PUT /:id, DELETE /:id
POST   /api/v1/admin/devices                           PUT /:id, DELETE /:id
POST   /api/v1/admin/devices/{id}/rotate               Rotate API token
POST   /api/v1/admin/messages                          Send to all/department/individual
PATCH  /api/v1/admin/leave/{id}                        Triggers email notification
```

Full schema is browsable at `http://localhost:8000/docs`.

---

## Frontend design system

White-first, Africa-greens primary, warm-amber accent. Defined as design tokens in [`frontend/app/globals.css`](frontend/app/globals.css):

- `--brand: #0E5B4A` (deep emerald) — primary
- `--accent: #E8B14A` (warm amber)
- `--ink: #0F1216`
- `--surface-soft: #FAFAF7`
- Plus dark-mode palette and gradient/utility helpers (`gradient-brand`, `text-gradient-brand`, `dot-grid`, `ring-soft`, `ring-elevated`).

Primitives in `components/ui/` are shadcn-flavoured (Radix + CVA + Tailwind), lightweight, no external CLI.

Animation: `framer-motion` for hero/grid entry. `tw-animate-css` is loaded for shadcn primitives that ship with `data-state` animations.

---

## Database

14 SQLAlchemy models cover the brief end-to-end:

| Model | Purpose |
|------|---------|
| `User`, `Role`, `RolePermission`, `Department` | Staff + RBAC |
| `Product` | Ecosystem product cards |
| `BlogPost`, `Page` | CMS |
| `Job`, `Application` | Careers |
| `PartnerRequest` | 4 partner paths |
| `Message`, `MessageRecipient` | Internal comms (incl. read state) |
| `LeaveRequest` | Leave management |
| `AttendanceLog`, `Device` | Attendance + biometric devices |
| `ContactMessage` | Public contact form |
| `ActivityLog` | Audit trail |
| `PageView` | Website analytics |

Migrations:

- **Dev** (`AUTO_CREATE_TABLES=true`): SQLAlchemy `Base.metadata.create_all` runs at boot. Zero-config.
- **Prod** (`AUTO_CREATE_TABLES=false`): use Alembic — `alembic.ini` and `alembic/env.py` are wired up with `target_metadata = Base.metadata`. Workflow:

```bash
cd backend
alembic revision --autogenerate -m "init"   # generates alembic/versions/*.py
alembic upgrade head                         # applies pending migrations
alembic downgrade -1                         # rollback one step
```

---

## Production deploy

> Companion docs: see [`docs/RUNBOOK.md`](docs/RUNBOOK.md) for incident
> response and [`docs/ADMIN_USER_MANUAL.md`](docs/ADMIN_USER_MANUAL.md)
> for non-technical admins.

### Required environment variables

**Backend** (`backend/.env`):

| Variable | Required | Notes |
|---|---|---|
| `DATABASE_URL` | ✅ | Managed Postgres URL (e.g. `postgresql+psycopg://user:pw@host:5432/db`). |
| `SECRET_KEY` | ✅ | Generate with `python -c "import secrets; print(secrets.token_urlsafe(64))"`. |
| `AUTO_CREATE_TABLES` | ✅ | Must be `false` in prod — forces Alembic-managed migrations. |
| `SEED_ON_STARTUP` | ✅ | `false` after first deploy. |
| `BACKEND_CORS_ORIGINS` | ✅ | JSON array of allowed origins, e.g. `["https://quatadigital.com"]`. |
| `EMAIL_BACKEND` | ✅ | `smtp` in prod (production guard refuses `console`). |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASSWORD` / `SMTP_USE_TLS` | ✅ if SMTP | SMTP2GO recommended. |
| `EMAIL_FROM` / `EMAIL_NOTIFY_TO` | ✅ if SMTP | `noreply@…` / `info@…`. |
| `HCAPTCHA_SITE_KEY` / `HCAPTCHA_SECRET_KEY` | recommended | Public form bot protection. |
| `SENTRY_DSN` / `SENTRY_ENV` | recommended | Error visibility. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | optional | Default 7 days. |

**Frontend** (`frontend/.env.production`):

| Variable | Required | Notes |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | ✅ | Public origin of the backend, e.g. `https://api.quatadigital.com/api/v1`. |
| `NEXT_PUBLIC_SITE_URL` | ✅ | Canonical site origin, e.g. `https://quatadigital.com`. |
| `NEXT_PUBLIC_HCAPTCHA_SITE_KEY` | recommended | Same site key as backend. |
| `NEXT_PUBLIC_CONTACT_PHONE` | optional | Phone displayed in footer + contact page. Row hidden when unset. |

### First-time deploy (any host)

```bash
# 1. Build the frontend
cd frontend
npm ci
npm run lint    # must be clean
npm run build   # produces .next/

# 2. Apply backend migrations (against the production DATABASE_URL)
cd ../backend
pip install -r requirements.txt
AUTO_CREATE_TABLES=false alembic upgrade head

# 3. Boot the backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4

# 4. Boot the frontend
cd ../frontend
npm run start -- --port 3000
```

### Vercel (frontend) + Render/Fly/Railway (backend)

1. **Backend**: deploy `backend/` (uses `Dockerfile`). Set every env var
   above. The startup `production_safety_check()` will refuse to boot if
   `EMAIL_BACKEND=console`, `AUTO_CREATE_TABLES=true`, or
   `SEED_ON_STARTUP=true` are still set in production.
2. **Frontend**: import `frontend/` to Vercel. Set the env vars above.
   Build command `npm run build`, output `.next`. Vercel handles HSTS,
   HTTP/3 and edge caching automatically.
3. Sign in with the seeded super-admin, **rotate the password
   immediately**, then create real staff under `/admin/staff`.

### Single-host (Docker Compose)

The root `docker-compose.yml` is a complete stack. Put it behind
Caddy/Nginx with TLS termination — sufficient for early deployments.

```bash
docker compose pull
docker compose up -d
docker compose exec backend alembic upgrade head
```

### Healthchecks

- Backend: `GET /healthz` returns `{ "status": "ok" }`.
- Frontend: `GET /` returns 200; check the `Strict-Transport-Security`
  header is present.

### Rollback

```bash
# Frontend (Vercel) — promote the previous deployment from the dashboard.

# Backend
docker compose stop backend
docker compose run --rm backend alembic downgrade -1   # if a bad migration shipped
docker compose up -d backend
```

If the migration is reversible, prefer `alembic downgrade -1`. If not,
restore from the most recent backup (see `docs/RUNBOOK.md`).

---

## Pre-launch checklist

- [ ] Real `SECRET_KEY` set on backend.
- [ ] `DATABASE_URL` points to managed Postgres.
- [ ] `AUTO_CREATE_TABLES=false`, `SEED_ON_STARTUP=false`.
- [ ] Super-admin password rotated; default deleted.
- [ ] `BACKEND_CORS_ORIGINS` locked to real frontend domain(s).
- [ ] API behind TLS (Caddy / Nginx / Cloudflare).
- [ ] `NEXT_PUBLIC_API_URL` and `NEXT_PUBLIC_SITE_URL` set on frontend.
- [ ] CDN / edge cache enabled for `/`, `/ecosystem`, `/blog`.
- [ ] S3 (or compatible) wired for uploads (`services/uploads.py`).
- [ ] Sentry DSN configured (or explicit decision logged).
- [ ] hCaptcha keys configured.
- [ ] SMTP2GO verified (SPF / DKIM / DMARC green).
- [ ] First DB backup taken; restore drill rehearsed.

---

## What's shipped (v0.2)

This release closes the v0.1 roadmap end-to-end:

- ✅ **Full admin CRUD** — products, blog posts, CMS pages, jobs, applications, staff, departments, devices. Every page has create/edit/delete dialogs, confirm flows, search and skeleton loaders.
- ✅ **File uploads** — local disk in dev (`/uploads/yyyy/mm/folder/file`), pluggable for S3/MinIO. Used by resume submissions and CMS cover images. Authenticated and public-restricted endpoints.
- ✅ **Email notifications** — pluggable backend (`console` / `smtp` / `disabled`). Hooks fire on partner submission, partner status change, job application, leave decision and contact form. Console output for dev, real SMTP for prod.
- ✅ **Biometric device webhook** — `POST /api/v1/devices/{id}/sync` accepts batched `check_in`/`check_out` events with `X-Device-Token` header auth. Devices have rotatable tokens.
- ✅ **Alembic migrations** — `alembic.ini`, `alembic/env.py` wired with `target_metadata = Base.metadata`, render-as-batch enabled for SQLite. Toggle `AUTO_CREATE_TABLES=false` in prod and run `alembic upgrade head`.
- ✅ **i18n EN/FR** — light dictionary (`lib/i18n.tsx`) with locale switcher in nav, persisted in localStorage. Ready to extend with more keys or swap to `next-intl`.
- ✅ **UI polish** — Toast/Toaster, Skeleton loaders, ConfirmDialog, FormDialog with file uploads, server-side pagination + search on partner requests.

## Roadmap (still open)

- Real-time messaging (WebSocket / Postgres LISTEN/NOTIFY) for the internal comms module.
- S3/MinIO swap for the upload backend (the `services/uploads.py` interface is intentionally narrow so this is a 50-line change).
- Office365/Google OIDC for staff sign-in.
- CI pipeline (lint + typecheck + alembic check).

---

## License

Proprietary — © QUATA Digital Enterprise.
