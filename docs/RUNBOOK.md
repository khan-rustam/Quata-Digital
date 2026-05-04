# QUATA Digital — Operational runbook

For the on-call engineer or whoever is closest to the keyboard when
something breaks.

Companion docs:
- [`README.md`](../README.md) — first-time deploy.
- [`ADMIN_USER_MANUAL.md`](ADMIN_USER_MANUAL.md) — non-technical admin
  guide.
- [`../BOSS_ACTIONS.md`](../BOSS_ACTIONS.md) — outstanding boss-only
  actions.
- [`../REMAINING_ITEMS.md`](../REMAINING_ITEMS.md) — full remaining
  punch list.

---

## 1. Where things live

| Service | What | Where |
|---|---|---|
| Frontend | Next.js 16 / React 19 | `frontend/` — Vercel (or `Dockerfile`) |
| Backend  | FastAPI / SQLAlchemy 2 | `backend/` — `Dockerfile` |
| Database | Postgres | Managed (Neon / Supabase / RDS — see `DATABASE_URL`) |
| Email    | SMTP2GO  | API keys in backend `.env` |
| Bot protection | hCaptcha | Site key + secret in env |
| Errors   | Sentry   | DSN in backend `.env` |

URLs (set after launch):
- Public site:   `https://quatadigital.com`
- Public API:    `https://api.quatadigital.com/api/v1`
- Admin:         `https://quatadigital.com/admin`
- Healthchecks:  `…/healthz` (backend), `/` (frontend)

---

## 2. Deploy procedure

### 2.1 Frontend (Vercel)

```bash
git push origin main
# Vercel auto-deploys. Watch the build log for any TS / lint failure.
```

If you need to deploy without going through `main`:

```bash
cd frontend
npm ci
npm run lint        # 0 errors expected
npm run build       # 55+ pages prerendered expected
vercel --prod
```

### 2.2 Backend (Docker)

```bash
cd backend
docker build -t quata-backend:$(git rev-parse --short HEAD) .
docker push <registry>/quata-backend:<tag>

# On the host
docker compose pull backend
docker compose up -d backend
docker compose exec backend alembic upgrade head
```

### 2.3 Migrations

Always run `alembic upgrade head` **after** the new container is up but
**before** routing traffic to it. If using a load balancer, drain old
backend instances first.

To create a migration after a model change:

```bash
cd backend
alembic revision --autogenerate -m "add foo column to bar"
# Review the generated file in alembic/versions/ — autogenerate is not psychic.
alembic upgrade head    # apply locally
git add alembic/versions/*.py && git commit
```

---

## 3. Rollback

### 3.1 Frontend
Vercel dashboard → Deployments → previous green deploy → **Promote to
Production**. Live in ~10 seconds.

### 3.2 Backend (no schema change)

```bash
docker compose stop backend
docker pull <registry>/quata-backend:<previous-tag>
docker compose up -d backend
```

### 3.3 Backend (bad migration shipped)

```bash
docker compose exec backend alembic downgrade -1   # rollback one revision
docker compose stop backend
docker pull <registry>/quata-backend:<previous-tag>
docker compose up -d backend
```

If the migration is **not reversible** (data destroyed, columns
dropped), restore from backup — see §6.

---

## 4. Health monitoring

| Signal | What it means | What to do |
|---|---|---|
| Sentry alert burst | Backend exception spike | Check Sentry breadcrumbs → identify endpoint → check DB / SMTP / external service |
| Vercel build red | Frontend won't deploy | Read the build log — usually a fresh lint / TS error |
| `/healthz` 5xx | Backend or DB is down | Check container logs, then DB connectivity |
| Email not arriving | SMTP2GO down or creds rotated | `docker compose logs backend \| grep email` then SMTP2GO dashboard |
| hCaptcha "verification failed" | Site key / secret mismatch | Check both `HCAPTCHA_SITE_KEY` (backend) and `NEXT_PUBLIC_HCAPTCHA_SITE_KEY` (frontend) match the keys in hcaptcha.com |

---

## 5. Common incidents

### 5.1 Backend won't boot — "production_safety_check failed"

The startup guard refuses to boot in production when one of these is
still at its dev default:

- `AUTO_CREATE_TABLES=true` → set `false`, run `alembic upgrade head`
- `SEED_ON_STARTUP=true` → set `false`
- `EMAIL_BACKEND=console` → set `smtp` and provide credentials
- `SECRET_KEY` is the dev fallback → generate a new one

### 5.2 Public form returns 422 with "captcha invalid"

User cleared cookies / hCaptcha site is down. Workflow:

1. Check status.hcaptcha.com.
2. If hCaptcha is down: `EMAIL_BACKEND` won't change anything, but you
   can temporarily set `HCAPTCHA_SECRET_KEY=""` on the backend to
   disable verification (it falls back to allow-all). **Re-enable it as
   soon as hCaptcha recovers.**

### 5.3 Database connection pool exhausted

```bash
docker compose exec backend python -c "from app.db.session import engine; print(engine.pool.status())"
```

If pool is full, restart the backend (`docker compose restart backend`)
to release stale connections. Long-term: tune `pool_size` in
`backend/app/db/session.py`.

### 5.4 Resume upload fails ("disk full")

The default upload backend writes to `backend/uploads/`. If the disk is
full:

1. Move `uploads/` to a larger volume.
2. Update `UPLOAD_DIR` env var.
3. Restart backend.

Long-term fix: switch `services/uploads.py` to S3 (the interface is
intentionally narrow).

### 5.5 "Too many failed login attempts" on a real admin

Rate limiter blocks a user who fat-fingered. Wait 15 min, or:

```bash
docker compose exec backend python -c "
from app.core.cache import cache
cache.clear_pattern('login_attempts:*')
"
```

### 5.6 CSP violation reports flooding browser console

CSP currently ships in **Report-Only** mode (see `next.config.ts`). To
silence noise from a known-safe source: add it to the matching directive
(e.g. `script-src`, `connect-src`) in `next.config.ts` and redeploy.

To **enforce** CSP (after a clean reporting window): change the header
key from `Content-Security-Policy-Report-Only` to
`Content-Security-Policy` in `next.config.ts`.

---

## 6. Backups & restore

> Backup specifics depend on the managed Postgres provider. This section
> documents the **drill** — fill in provider-specific commands once
> chosen (BOSS_ACTIONS.md item #7).

Recommended baseline:

- **Frequency:** daily
- **Retention:** 30 days rolling + monthly snapshots for 1 year
- **Storage:** managed provider's default + an off-provider copy (e.g.
  separate S3 bucket)

### Restore drill (run quarterly)

1. Spin up a throwaway Postgres instance.
2. Restore the most recent backup into it.
3. Point a temporary backend container at it (`DATABASE_URL=…`).
4. Smoke-test: log in as super-admin, list partners, view a job.
5. Tear down — record outcome in `docs/RESTORE_DRILLS.md`.

---

## 7. Secret rotation

If a secret leaks (committed to git, posted in Slack, laptop stolen):

1. **Rotate immediately** in the upstream provider (Sentry, hCaptcha,
   SMTP2GO, DB password).
2. Update env vars on every host.
3. Restart affected services.
4. **For `SECRET_KEY`**: rotating it invalidates all JWTs — every admin
   gets logged out. Communicate before doing so.
5. Audit `git log -p` for accidental check-ins of the old value.
6. Force-push the cleaned history if the leak made it to a public repo
   (last resort).

---

## 8. Out-of-hours escalation

1. On-call engineer triages and fixes if straightforward.
2. If a fix isn't possible in 30 min: push a maintenance page (Vercel
   redirect rule) and roll back.
3. Wake the boss if customer money / data is at risk. Otherwise hold
   until business hours.

Maintenance page redirect (Vercel `vercel.json` snippet):

```json
{ "redirects": [{ "source": "/(.*)", "destination": "/maintenance.html", "permanent": false }] }
```

Place a static `maintenance.html` in `frontend/public/`.
