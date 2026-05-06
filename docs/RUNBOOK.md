# QUATA Digital — Operational runbook

For the on-call engineer or whoever is closest to the keyboard when something
breaks.

Companion docs:
- [`../README.md`](../README.md) — first-time deploy + env-var matrix.
- [`ADMIN_USER_MANUAL.md`](ADMIN_USER_MANUAL.md) — non-technical admin guide.
- [`PRODUCTION_AUDIT.md`](PRODUCTION_AUDIT.md) — numbered launch audit.
- [`../BOSS_ACTIONS.md`](../BOSS_ACTIONS.md) — boss-only outstanding items.
- [`../REMAINING_ITEMS.md`](../REMAINING_ITEMS.md) — single-page readiness dashboard.

---

## 1. Where things live

### Production VPS

| Service | Process | Port (loopback) | Manager |
|---|---|---|---|
| Backend (FastAPI / uvicorn) | `quata-digital-backend` | `127.0.0.1:8500` | systemd |
| Frontend (Next.js `next start`) | `Quata-Digi-F` | `127.0.0.1:3500` | PM2 |
| Reverse proxy | Caddy or Nginx | `:443` | system-managed |

| URL | Routes to |
|---|---|
| `https://quatadigital.com` | frontend `:3500` |
| `https://www.quatadigital.com` | frontend `:3500` |
| `https://api.quatadigital.com` | backend `:8500` |

| Concern | Where |
|---|---|
| Repo on host | `/home/Quata-Digital` |
| Deploy log | `/var/log/quata-redeploy.log` |
| Database | managed Postgres (URL in `/home/Quata-Digital/backend/.env`) |
| Uploads (resumes, CMS covers) | `/home/Quata-Digital/backend/uploads/yyyy/mm/folder/` |
| Email | SMTP2GO (or whatever provider is wired in `.env`) |
| Bot protection | hCaptcha — site key + secret in `.env` |
| Errors | Sentry — DSN in `.env` |

### Health endpoints

- Backend: `GET https://api.quatadigital.com/health` — returns 200 with a `database: ok` check, or 503 if the DB read fails.
- Frontend: `GET https://quatadigital.com/` — 200 means next-server is alive; verify the `Strict-Transport-Security` header is present.

> Note: the historical `/healthz` path doesn't exist — the FastAPI route is `/health` (see [backend/app/main.py:121](../backend/app/main.py)).

---

## 2. Deploy procedure

### 2.1 Standard redeploy from `main`

```bash
# from anywhere on the VPS
bash /home/Quata-Digital/deploy.sh             # full
bash /home/Quata-Digital/deploy.sh backend     # backend only
bash /home/Quata-Digital/deploy.sh frontend    # frontend only
```

The script ([deploy.sh](../deploy.sh)) does:

1. `git pull --ff-only origin main` (refuses on conflict)
2. **Backend** — refresh `pip install -r requirements.txt`, install `psycopg[binary]`, `alembic upgrade head`, `systemctl restart quata-digital-backend`, wait 2s, assert `is-active`.
3. **Frontend** — `pnpm install --frozen-lockfile`, `pnpm build`, `pm2 restart Quata-Digi-F --update-env`, `pm2 save`, poll `127.0.0.1:3500/` for up to 20s.
4. **Smoke test** — `curl` `https://quatadigital.com/`, `https://www.quatadigital.com/`, `https://quatadigital.com/ecosystem`, `https://api.quatadigital.com/api/v1/products`. Exits non-zero if any returns ≠ 200.

If a step fails, the script prints the failing region and dumps the last 30
lines of `journalctl -u quata-digital-backend` for the operator. Don't ignore
red lines.

### 2.2 Manual one-off

```bash
# backend without redeploy script
cd /home/Quata-Digital/backend
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
sudo systemctl restart quata-digital-backend
sudo systemctl status quata-digital-backend
```

```bash
# frontend without redeploy script
cd /home/Quata-Digital/frontend
pnpm install --frozen-lockfile
pnpm build
pm2 restart Quata-Digi-F --update-env
pm2 logs Quata-Digi-F
```

### 2.3 Migrations

Always `alembic upgrade head` **after** new code is on the host but **before**
restarting the backend service so the new code never runs against an old
schema.

To create a new migration after a model change:

```bash
cd /home/Quata-Digital/backend
source .venv/bin/activate
alembic revision --autogenerate -m "add foo column to bar"
# Review the generated file — autogenerate is not psychic.
alembic upgrade head
git add alembic/versions/*.py && git commit
```

---

## 3. Rollback

### 3.1 Backend (no schema change)

```bash
cd /home/Quata-Digital
git log --oneline -10            # find the previous green SHA
git reset --hard <previous-sha>  # ⚠ destructive — only do this when sure
sudo systemctl restart quata-digital-backend
```

Better — check out a tagged release if you tag deploys, or `git revert` the
broken commit and let `deploy.sh` redeploy.

### 3.2 Backend (bad migration shipped)

```bash
cd /home/Quata-Digital/backend
source .venv/bin/activate
alembic downgrade -1
sudo systemctl restart quata-digital-backend
```

If the migration is **not reversible** (data dropped, columns removed),
restore from backup — see §6.

### 3.3 Frontend

```bash
cd /home/Quata-Digital
git reset --hard <previous-sha>  # ⚠ same caveat
cd frontend
pnpm install --frozen-lockfile
pnpm build
pm2 restart Quata-Digi-F --update-env
```

---

## 4. Health monitoring

| Signal | What it means | First check |
|---|---|---|
| Sentry alert burst | Backend exception spike | breadcrumbs → identify endpoint → DB / SMTP / external |
| Smoke test red in `deploy.sh` | One of `/`, `/ecosystem`, `/api/v1/products` returned non-200 | `pm2 logs Quata-Digi-F` and `journalctl -u quata-digital-backend -n 50` |
| `/health` returns 503 | DB unreachable | check `DATABASE_URL`, run `psql` from VPS, check provider's status page |
| Email not arriving | SMTP credentials rotated or provider down | provider dashboard, then `journalctl -u quata-digital-backend \| grep -i smtp` |
| hCaptcha "verification failed" everywhere | Site key / secret mismatch | confirm both `HCAPTCHA_SITE_KEY` (backend) and `NEXT_PUBLIC_HCAPTCHA_SITE_KEY` (frontend) match what's at hcaptcha.com |
| WebSocket disconnects | Reverse proxy doesn't upgrade `/ws` | confirm Caddy/Nginx has `Upgrade`/`Connection` headers passed for `/ws/messages` |

---

## 5. Common incidents

### 5.1 Backend won't boot — `ProductionConfigError`

The startup guard in [`core/config.py`](../backend/app/core/config.py) refuses
boot in production while any of these are at dev defaults. The error message
lists every offender at once:

- `SECRET_KEY` is the placeholder → generate one (`python -c "import secrets; print(secrets.token_urlsafe(64))"`)
- `AUTO_CREATE_TABLES=true` → set `false` and run `alembic upgrade head`
- `EMAIL_BACKEND=console` → set `smtp` (or `disabled` to opt out explicitly)
- `SEED_ON_STARTUP=true` without explicit `ALLOW_PRODUCTION_SEED=true`
- Default admin password unchanged while seeding is on

### 5.2 Public form returns 4xx with "Captcha verification failed"

Most likely the user took too long on the form (token expires) or hCaptcha is
down.

1. Check status.hcaptcha.com.
2. If hCaptcha is genuinely down: temporarily set `HCAPTCHA_SECRET_KEY=""` on the backend (`captcha_enabled()` becomes False, helper turns into a no-op), restart, and **revert as soon as hCaptcha recovers**. The site key on the frontend stays — clients will still render the widget but server won't enforce.

### 5.3 "Account locked" on a real admin

Five failed logins lock the account for 15 minutes (`MAX_LOGIN_ATTEMPTS`,
`LOCKOUT_MINUTES`). Either wait, or:

```bash
psql "$DATABASE_URL" -c "UPDATE users SET failed_login_attempts=0, locked_until=NULL WHERE email='admin@quatadigital.com';"
```

### 5.4 Resume upload fails with 413

Default cap is 25 MB (`MAX_UPLOAD_SIZE_MB`). If genuinely too small for the
real-world resume size, raise the env var and restart. If the disk is full, see §5.5.

### 5.5 Disk full on upload

```bash
df -h /home
du -sh /home/Quata-Digital/backend/uploads/* | sort -h
```

Long-term: switch [`backend/app/services/uploads.py`](../backend/app/services/uploads.py) to S3 — the interface is intentionally narrow (~50-line change). Short-term: move
`uploads/` to a larger volume, update `UPLOAD_DIR`, restart.

### 5.6 CSP violation reports flooding the browser console

CSP currently ships in **Report-Only** mode in [`next.config.ts`](../frontend/next.config.ts).
Add the offending source to the matching directive (`script-src`, `connect-src`, …) and redeploy.

To **enforce** CSP (after ~30 days of clean reports): change the header key
from `Content-Security-Policy-Report-Only` to `Content-Security-Policy`.

### 5.7 WebSocket clients can't connect

- Verify the reverse proxy upgrades `/ws/messages` requests (Caddy: `reverse_proxy /ws/* localhost:8500`; Nginx: `proxy_set_header Upgrade $http_upgrade; proxy_set_header Connection "upgrade";`).
- Check the JWT — connections without a valid `?token=` are closed with code 4401.
- The hub is in-process; if you've moved to multiple uvicorn workers without Redis pub/sub, only the worker handling the WS connection gets broadcasts. See [SCALING.md](SCALING.md).

### 5.8 Database connection issues

Default SQLAlchemy engine has no explicit pool sizing — relies on driver
defaults. If you see "too many connections" errors:

```bash
psql "$DATABASE_URL" -c "SELECT count(*), state FROM pg_stat_activity GROUP BY state;"
```

Either bump the provider's connection limit or add explicit pool args in [`backend/app/db/session.py`](../backend/app/db/session.py) (`pool_size`, `max_overflow`, `pool_recycle`).

---

## 6. Backups & restore

> Backup specifics depend on the managed Postgres provider. This section
> documents the **drill** — the provider-specific commands go in once the
> backup decision lands ([BOSS_ACTIONS.md](../BOSS_ACTIONS.md) #7).

Recommended baseline:
- **Frequency:** daily
- **Retention:** 30 days rolling + monthly snapshots for 1 year
- **Storage:** managed provider's default + an off-provider copy (separate S3 bucket)

### Restore drill (run quarterly)

1. Spin up a throwaway Postgres instance.
2. Restore the most recent backup into it.
3. Point a temporary backend container at it (`DATABASE_URL=…`).
4. Smoke-test: log in as super-admin, list partners, view a job.
5. Tear down — record outcome in `docs/RESTORE_DRILLS.md` (create on first drill).

---

## 7. Secret rotation

If a secret leaks (committed to git, posted in Slack, laptop stolen):

1. **Rotate immediately** in the upstream provider (Sentry, hCaptcha, SMTP, Postgres).
2. Update env vars on the VPS (`/home/Quata-Digital/backend/.env`, `/home/Quata-Digital/frontend/.env.production`).
3. Run `bash /home/Quata-Digital/deploy.sh` to restart with new values.
4. **For `SECRET_KEY`:** rotating it invalidates all JWTs — every signed-in admin gets logged out. Communicate before rotating.
5. Audit `git log -p --all -- backend/.env*` to confirm the leaked value never made it into git.
6. If it did, scrub history (`git filter-repo` or BFG) and force-push **after backing the repo up**.

---

## 8. Retention

The activity log and page-view table grow unbounded. Defaults: `ACTIVITY_LOG_RETENTION_DAYS=90`, `PAGE_VIEW_RETENTION_DAYS=180`. Prune endpoints:

```
GET  /api/v1/admin/retention/preview     # dry-run row counts
POST /api/v1/admin/retention/prune       # hard delete past retention
```

Recommended: cron the prune endpoint nightly. Example crontab on the VPS:

```cron
0 3 * * * curl -fsS -X POST -H "Authorization: Bearer $QUATA_RETENTION_TOKEN" https://api.quatadigital.com/api/v1/admin/retention/prune > /var/log/quata-retention.log 2>&1
```

The token must belong to a user with `activity:view` permission.

---

## 9. Out-of-hours escalation

1. On-call engineer triages and fixes if straightforward.
2. If a fix isn't possible in 30 min: push a maintenance page (Caddy/Nginx static-route override) and roll back code.
3. Wake the boss only if customer money / data is at risk. Otherwise hold until business hours.

Caddy maintenance snippet:

```caddy
quatadigital.com {
    handle_path /maintenance {
        respond "QUATA is briefly offline for maintenance. Back shortly." 503
    }
    rewrite * /maintenance
}
```

(Replace with whatever's in production — adjust to taste.)
