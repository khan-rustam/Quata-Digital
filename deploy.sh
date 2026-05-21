#!/bin/bash
# QUATA Digital — one-shot redeploy from `main`.
#
# Usage (from anywhere on the VPS):
#   bash /home/Quata-Digital/deploy.sh             # full redeploy
#   bash /home/Quata-Digital/deploy.sh frontend    # frontend only
#   bash /home/Quata-Digital/deploy.sh backend     # backend only
#
# Logs to /var/log/quata-redeploy.log so you can `tail -f` from another tab.

set -euo pipefail
SCOPE="${1:-all}"
LOG=/var/log/quata-redeploy.log
PROJECT_DIR="/home/Quata-Digital"

# Tee everything to stdout + log file.
exec > >(tee -a "$LOG") 2>&1

# ---------- ANSI colors ----------
if [[ -t 1 ]]; then
  C_RESET='\033[0m'
  C_BOLD='\033[1m'
  C_DIM='\033[2m'
  C_GOLD='\033[38;5;220m'
  C_GREEN='\033[38;5;46m'
  C_CYAN='\033[38;5;51m'
  C_RED='\033[38;5;196m'
  C_BLUE='\033[38;5;39m'
  C_PURPLE='\033[38;5;141m'
else
  C_RESET='' C_BOLD='' C_DIM='' C_GOLD='' C_GREEN='' C_CYAN='' C_RED='' C_BLUE='' C_PURPLE=''
fi

ok()    { echo -e "${C_GREEN}${C_BOLD}✔${C_RESET} $*"; }
fail()  { echo -e "${C_RED}${C_BOLD}✘${C_RESET} $*"; }
info()  { echo -e "${C_CYAN}➜${C_RESET} $*"; }
step()  {
  echo
  echo -e "${C_PURPLE}${C_BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${C_RESET}"
  echo -e "${C_PURPLE}${C_BOLD} ▸ $*${C_RESET}"
  echo -e "${C_PURPLE}${C_BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${C_RESET}"
}

# ---------- Banner ----------
echo
echo -e "${C_GOLD}${C_BOLD}"
cat <<'BANNER'
 ██████╗ ██╗   ██╗ █████╗ ████████╗ █████╗     ██████╗ ██╗ ██████╗ ██╗████████╗ █████╗ ██╗
██╔═══██╗██║   ██║██╔══██╗╚══██╔══╝██╔══██╗    ██╔══██╗██║██╔════╝ ██║╚══██╔══╝██╔══██╗██║
██║   ██║██║   ██║███████║   ██║   ███████║    ██║  ██║██║██║  ███╗██║   ██║   ███████║██║
██║▄▄ ██║██║   ██║██╔══██║   ██║   ██╔══██║    ██║  ██║██║██║   ██║██║   ██║   ██╔══██║██║
╚██████╔╝╚██████╔╝██║  ██║   ██║   ██║  ██║    ██████╔╝██║╚██████╔╝██║   ██║   ██║  ██║███████╗
 ╚══▀▀═╝  ╚═════╝ ╚═╝  ╚═╝   ╚═╝   ╚═╝  ╚═╝    ╚═════╝ ╚═╝ ╚═════╝ ╚═╝   ╚═╝   ╚═╝  ╚═╝╚══════╝
                                       ━ D E P L O Y ━
BANNER
echo -e "${C_RESET}"
echo -e "  ${C_DIM}$(date -u +%Y-%m-%dT%H:%M:%SZ) UTC  ·  scope=${C_RESET}${C_BOLD}${SCOPE}${C_RESET}  ·  ${C_DIM}log=${LOG}${C_RESET}"
echo

cd "$PROJECT_DIR"

# ---------- Pre-deploy snapshot (rollback safety) ----------
PREV_SHA=$(git rev-parse HEAD 2>/dev/null || echo "unknown")
BACKUP_DIR="$PROJECT_DIR/.deploy-backups"
BACKUP_TS="$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$BACKUP_DIR"
DB_SNAPSHOT=""

step "pre-deploy snapshot"
info "previous SHA: ${PREV_SHA:0:12}"

# Try a Postgres dump when DATABASE_URL points at one. Best-effort; if
# the URL isn't set or pg_dump isn't on PATH we record the gap and
# continue (the operator still has the SHA to roll back to).
if [[ -n "${DATABASE_URL:-}" ]] && command -v pg_dump >/dev/null 2>&1; then
  DB_SNAPSHOT="$BACKUP_DIR/db-${BACKUP_TS}.sql.gz"
  if pg_dump "${DATABASE_URL}" 2>/dev/null | gzip > "$DB_SNAPSHOT"; then
    ok "DB snapshot → ${DB_SNAPSHOT}"
  else
    rm -f "$DB_SNAPSHOT"
    DB_SNAPSHOT=""
    info "DB snapshot skipped (pg_dump failed — non-fatal)"
  fi
else
  info "DB snapshot skipped (DATABASE_URL or pg_dump unavailable)"
fi

# Trap any failure from this point on, surface the rollback recipe so
# the operator can reverse the deploy without grepping through logs.
rollback_hint() {
  local rc=$?
  if [[ $rc -ne 0 ]]; then
    echo
    fail "deploy aborted (exit $rc) — rollback recipe:"
    echo -e "  ${C_BOLD}cd $PROJECT_DIR && git reset --hard ${PREV_SHA}${C_RESET}"
    if [[ -n "$DB_SNAPSHOT" ]]; then
      echo -e "  ${C_BOLD}gunzip -c $DB_SNAPSHOT | psql \"\$DATABASE_URL\"${C_RESET}"
    fi
    echo -e "  ${C_BOLD}systemctl restart quata-digital-backend && pm2 restart Quata-Digi-F${C_RESET}"
  fi
}
trap rollback_hint EXIT

# ---------- Git pull ----------
step "git pull (fast-forward only)"
if git pull --ff-only origin main; then
  ok "Repo synced with origin/main"
else
  fail "git pull failed — fix conflicts and retry"
  exit 1
fi

# ---------- Backend ----------
if [[ "$SCOPE" == "all" || "$SCOPE" == "backend" ]]; then
  step "BACKEND  →  uvicorn :8500 (systemd)"
  cd "$PROJECT_DIR/backend"

  info "venv: install / refresh deps"
  # shellcheck disable=SC1091
  source .venv/bin/activate
  pip install --upgrade pip --quiet
  # psycopg[binary] is now in requirements.txt itself — no extra install.
  pip install -r requirements.txt --quiet
  ok "backend deps in sync"

  info "alembic upgrade head"
  alembic upgrade head
  ok "migrations applied"
  deactivate

  info "restart systemd service"
  systemctl restart quata-digital-backend
  sleep 2
  STATUS=$(systemctl is-active quata-digital-backend)
  if [[ "$STATUS" == "active" ]]; then
    ok "quata-digital-backend.service: ${C_GREEN}active${C_RESET}"
  else
    fail "backend status: $STATUS"
    journalctl -u quata-digital-backend -n 30 --no-pager
    exit 1
  fi
fi

# ---------- Frontend ----------
if [[ "$SCOPE" == "all" || "$SCOPE" == "frontend" ]]; then
  step "FRONTEND  →  next.js :3500 (PM2 / Quata-Digi-F)"
  cd "$PROJECT_DIR/frontend"

  info "npm ci (matches CI tooling; package-lock.json is the source of truth)"
  # CI runs `npm ci` against package-lock.json, so deploy must too;
  # otherwise a green CI run can still fail in prod because of lockfile
  # drift between npm and pnpm. If lockfile is stale, fall back to a
  # full `npm install` so the deploy still completes — the next push
  # should refresh the lockfile properly.
  if ! npm ci; then
    info "lockfile outdated — running full npm install to regenerate"
    npm install
  fi
  ok "frontend deps in sync"

  info "npm run build"
  npm run build
  ok "next build complete"

  info "pm2 restart Quata-Digi-F"
  pm2 restart Quata-Digi-F --update-env
  pm2 save
  ok "Quata-Digi-F restarted"

  # Wait for next-server to actually accept connections (avoids 502 on smoke test)
  info "waiting for next-server to come back up"
  for i in {1..20}; do
    if curl -sf -o /dev/null http://127.0.0.1:3500/; then
      ok "next-server responding (took ${i}s)"
      break
    fi
    sleep 1
  done
fi

# ---------- Smoke test ----------
step "SMOKE TEST  →  public HTTPS endpoints"
all_ok=1
for url in \
  "https://quatadigital.com/" \
  "https://www.quatadigital.com/" \
  "https://quatadigital.com/ecosystem" \
  "https://api.quatadigital.com/api/v1/products"; \
do
  CODE=$(curl -s -o /dev/null -w "%{http_code}" "$url")
  TIME=$(curl -s -o /dev/null -w "%{time_total}" "$url")
  if [[ "$CODE" == "200" ]]; then
    printf "  ${C_GREEN}✔ %-3s${C_RESET}  ${C_BLUE}%-65s${C_RESET}  ${C_DIM}%ss${C_RESET}\n" "$CODE" "$url" "$TIME"
  else
    printf "  ${C_RED}✘ %-3s${C_RESET}  ${C_BLUE}%-65s${C_RESET}  ${C_DIM}%ss${C_RESET}\n" "$CODE" "$url" "$TIME"
    all_ok=0
  fi
done

# ---------- Final summary ----------
echo
echo -e "${C_GOLD}${C_BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${C_RESET}"
if [[ $all_ok -eq 1 ]]; then
  echo -e "  ${C_GREEN}${C_BOLD}✔ DEPLOY OK${C_RESET}  ·  scope=${C_BOLD}${SCOPE}${C_RESET}  ·  $(date -u +%Y-%m-%dT%H:%M:%SZ)"
else
  echo -e "  ${C_RED}${C_BOLD}✘ DEPLOY HAD FAILURES${C_RESET}  ·  scope=${C_BOLD}${SCOPE}${C_RESET}  ·  $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo -e "  ${C_DIM}Investigate via:  journalctl -u quata-digital-backend -n 50  /  pm2 logs Quata-Digi-F${C_RESET}"
fi
echo -e "${C_GOLD}${C_BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${C_RESET}"
echo

# Clear the rollback trap on a clean exit so we don't print the recipe
# after a green deploy.
if [[ $all_ok -eq 1 ]]; then
  trap - EXIT
fi
exit $((1 - all_ok))
