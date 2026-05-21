# infra/ — reproducible production scaffolding

Everything in this folder is what makes the VPS look the way it does
today. Source of truth — if the box dies, you rebuild from here.

## Contents

| Path | Purpose | Install path on VPS |
|---|---|---|
| [caddy/Caddyfile](caddy/Caddyfile) | Reverse proxy, TLS termination, www→apex redirect, WS upgrade | `/etc/caddy/Caddyfile` |
| [systemd/quata-digital-backend.service](systemd/quata-digital-backend.service) | uvicorn unit, 2 workers, MemoryMax, hardening flags | `/etc/systemd/system/` |
| [pm2/ecosystem.config.js](pm2/ecosystem.config.js) | next-server cluster, max-old-space-size cap | `/home/Quata-Digital/frontend/ecosystem.config.js` (or load from infra/ directly) |
| [cron/backup-postgres.sh](cron/backup-postgres.sh) | Nightly `pg_dump` → off-VPS S3 with retention prune | `/usr/local/sbin/quata-backup` |
| [cron/retention-prune.cron](cron/retention-prune.cron) | Template for daily activity-log retention prune | crontab |

## First-time install (single-VPS, fresh box)

```bash
# 1. Caddy
sudo cp infra/caddy/Caddyfile /etc/caddy/Caddyfile
sudo systemctl reload caddy

# 2. Backend service
sudo cp infra/systemd/quata-digital-backend.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now quata-digital-backend

# 3. Frontend (PM2)
pm2 start infra/pm2/ecosystem.config.js
pm2 save
pm2 startup     # one-time

# 4. Nightly backup
sudo install -m 0750 infra/cron/backup-postgres.sh /usr/local/sbin/quata-backup
sudo crontab -e
# add:
#   10 2 * * *  /usr/local/sbin/quata-backup >> /var/log/quata-backup.log 2>&1
```

## Secret file (`/etc/quata-digital.env`)

Never committed. Read by both the systemd unit and the backup script.
Minimum keys:

```ini
ENVIRONMENT=production
SECRET_KEY=<64+ char random>
DATABASE_URL=postgresql+psycopg://user:pass@host:5432/quata
FRONTEND_URL=https://quatadigital.com
PUBLIC_BASE_URL=https://api.quatadigital.com
BACKEND_CORS_ORIGINS=["https://quatadigital.com","https://www.quatadigital.com"]

EMAIL_BACKEND=smtp
SMTP_HOST=mail.smtp2go.com
SMTP_PORT=587
SMTP_USER=<smtp2go user>
SMTP_PASSWORD=<smtp2go password>
EMAIL_FROM=QUATA Digital <noreply@quatadigital.com>
EMAIL_NOTIFY_TO=info@quatadigital.com

# Optional but recommended
REDIS_URL=redis://default:<pw>@127.0.0.1:6379/0
SENTRY_DSN=<from sentry.io>
HCAPTCHA_SITE_KEY=<from hcaptcha>
HCAPTCHA_SECRET_KEY=<from hcaptcha>

UPLOAD_BACKEND=s3
S3_BUCKET=quata-uploads
S3_REGION=auto
S3_ENDPOINT_URL=https://<account>.r2.cloudflarestorage.com
S3_PUBLIC_URL_BASE=https://cdn.quatadigital.com
AWS_ACCESS_KEY_ID=<key>
AWS_SECRET_ACCESS_KEY=<secret>

# Backup destination
BACKUP_S3_BUCKET=quata-backups
BACKUP_S3_ENDPOINT_URL=https://<account>.r2.cloudflarestorage.com
BACKUP_RETENTION_DAYS=30
```
