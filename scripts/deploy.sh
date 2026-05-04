#!/bin/bash
# QUATA Digital — one-shot redeploy from `main`.
#
# Usage (from anywhere on the VPS):
#   bash /home/Quata-Digital/scripts/deploy.sh             # full redeploy
#   bash /home/Quata-Digital/scripts/deploy.sh frontend    # frontend only
#   bash /home/Quata-Digital/scripts/deploy.sh backend     # backend only
#
# What it does:
#   1. git pull  (fast-forward only — refuses if there are local edits to merge)
#   2. backend  → activate venv, pip install, alembic upgrade head, systemctl restart
#   3. frontend → pnpm install --frozen-lockfile, pnpm build, pm2 restart Quata-Digi-F
#   4. smoke test the public HTTPS URLs
#
# Logs to /var/log/quata-redeploy.log so you can `tail -f` from another tab.

set -euo pipefail
SCOPE="${1:-all}"
LOG=/var/log/quata-redeploy.log
PROJECT_DIR="/home/Quata-Digital"

# Tee everything to stdout + the log file.
exec > >(tee -a "$LOG") 2>&1

echo "================================================================"
echo "QUATA Digital redeploy — $(date -u +%Y-%m-%dT%H:%M:%SZ)  scope=$SCOPE"
echo "================================================================"

cd "$PROJECT_DIR"

echo "--- git pull (fast-forward only) ---"
git pull --ff-only origin main

if [[ "$SCOPE" == "all" || "$SCOPE" == "backend" ]]; then
  echo
  echo "================================================================"
  echo "BACKEND"
  echo "================================================================"
  cd "$PROJECT_DIR/backend"
  echo "--- venv: install deps ---"
  # shellcheck disable=SC1091
  source .venv/bin/activate
  pip install --upgrade pip --quiet
  pip install -r requirements.txt --quiet
  pip install "psycopg[binary]>=3.2.3" --quiet
  echo "--- alembic upgrade head ---"
  alembic upgrade head
  deactivate
  echo "--- systemctl restart quata-digital-backend ---"
  systemctl restart quata-digital-backend
  sleep 2
  STATUS=$(systemctl is-active quata-digital-backend)
  echo "backend status: $STATUS"
  if [[ "$STATUS" != "active" ]]; then
    echo "!!! Backend failed to start — last 30 log lines:"
    journalctl -u quata-digital-backend -n 30 --no-pager
    exit 1
  fi
fi

if [[ "$SCOPE" == "all" || "$SCOPE" == "frontend" ]]; then
  echo
  echo "================================================================"
  echo "FRONTEND"
  echo "================================================================"
  cd "$PROJECT_DIR/frontend"
  echo "--- pnpm install --frozen-lockfile ---"
  pnpm install --frozen-lockfile
  echo "--- pnpm build ---"
  pnpm build
  echo "--- pm2 restart Quata-Digi-F ---"
  pm2 restart Quata-Digi-F --update-env
  pm2 save
fi

echo
echo "================================================================"
echo "SMOKE TEST"
echo "================================================================"
for url in \
  "https://quatadigital.com/" \
  "https://www.quatadigital.com/" \
  "https://quatadigital.com/ecosystem" \
  "https://api.quatadigital.com/api/v1/products"; \
do
  printf "%-65s " "$url"
  curl -s -o /dev/null -w "HTTP %{http_code} (%{time_total}s)\n" "$url"
done

echo
echo "--- DONE  $(date -u +%Y-%m-%dT%H:%M:%SZ)  scope=$SCOPE ---"
