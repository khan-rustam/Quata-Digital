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

# ---------- self-protection: survive `git pull` rewriting this file ----------
# bash reads a script lazily, by byte offset, so when the pull below updates
# deploy.sh the running shell keeps reading the NEW file at its OLD offset —
# a mix of both versions. The practical failure is that any step the update
# ADDS never runs while the deploy still reports success (observed
# 2026-08-03: the commit adding the standalone asset sync deployed without
# ever syncing). Stage 1 re-execs from a throwaway copy the pull cannot
# touch; stage 2 (just after the pull) hands over to the new version.
#
# QD_SELF must be resolved ONCE: after `exec bash <copy>`, BASH_SOURCE points
# at the copy, so recomputing would make QD_SELF equal QD_SELF_COPY and
# silently disable both the stage-2 check and the cleanup trap.
if [[ -z "${QD_SELF:-}" ]]; then
  QD_SELF="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)/$(basename "${BASH_SOURCE[0]}")"
fi
export QD_SELF

if [[ "${QD_REEXEC:-}" != "1" ]]; then
  _qd_copy="$(mktemp -t quatadigital-deploy.XXXXXX)"
  cp "$QD_SELF" "$_qd_copy"
  export QD_REEXEC=1 QD_SELF_COPY="$_qd_copy"
  exec bash "$_qd_copy" "$@"
fi
if [[ -n "${QD_SELF_COPY:-}" && "$QD_SELF_COPY" != "$QD_SELF" ]]; then
  trap 'rm -f "$QD_SELF_COPY"' EXIT
fi

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
# Something worth noticing that is NOT fatal — the deploy continues.
warn()  { echo -e "${C_GOLD}${C_BOLD}!${C_RESET} $*"; }
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
    echo -e "  ${C_BOLD}systemctl restart quata-digital-backend && pm2 restart QuataDigital-F${C_RESET}"
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

# Stage 2 of the self-protection at the top. If that pull changed deploy.sh,
# the copy we are running is stale and every step below is the OLD logic.
# Hand over to the pulled version exactly once (QD_REEXEC_PULLED guards the
# loop); the re-run's `git pull` is a no-op.
if [[ "${QD_REEXEC_PULLED:-}" != "1" ]] \
   && ! cmp -s "$QD_SELF" "${QD_SELF_COPY:-/dev/null}"; then
  info "deploy.sh changed in this pull — restarting with the new version"
  _qd_new="$(mktemp -t quatadigital-deploy.XXXXXX)"
  cp "$QD_SELF" "$_qd_new"
  # exec replaces the process so the EXIT trap never fires — drop the old
  # copy by hand first.
  if [[ -n "${QD_SELF_COPY:-}" && "$QD_SELF_COPY" != "$QD_SELF" ]]; then
    rm -f "$QD_SELF_COPY"
  fi
  export QD_REEXEC_PULLED=1 QD_SELF_COPY="$_qd_new"
  exec bash "$_qd_new" "$@"
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

  # Notification worker — retry sweeps, infrastructure monitoring and the
  # daily business summary for @QuataAlertsBot. It shares the backend's
  # venv and code, so it must restart on the same deploy or it keeps
  # running the old build.
  #
  # Treated as non-fatal: alerts are delivered in-process by the API the
  # moment an event is published, so a worker that won't start degrades
  # reliability but must never abort a deploy that is otherwise healthy.
  if systemctl list-unit-files quata-notification-worker.service &>/dev/null &&
     systemctl is-enabled quata-notification-worker &>/dev/null; then
    info "restart notification worker"
    systemctl restart quata-notification-worker || true
    sleep 2
    WORKER_STATUS=$(systemctl is-active quata-notification-worker || true)
    if [[ "$WORKER_STATUS" == "active" ]]; then
      ok "quata-notification-worker.service: ${C_GREEN}active${C_RESET}"
    else
      warn "notification worker status: $WORKER_STATUS (alerts still send in-process;"
      warn "  retries, monitoring and the daily summary are paused until it's up)"
      journalctl -u quata-notification-worker -n 20 --no-pager || true
    fi
  else
    warn "quata-notification-worker not installed — see infra/systemd/ and docs/NOTIFICATIONS.md"
  fi
fi

# ---------- Frontend ----------
if [[ "$SCOPE" == "all" || "$SCOPE" == "frontend" ]]; then
  step "FRONTEND  →  next.js :3500 (PM2 / QuataDigital-F)"
  cd "$PROJECT_DIR/frontend"

  # The VPS uses pnpm (CI uses `npm ci` against the tracked
  # package-lock.json for lint/typecheck/build smoke). pnpm-lock.yaml
  # is NOT tracked — it's regenerated from package.json on each deploy
  # if missing or stale. Detect a left-over npm `node_modules` layout
  # (no .pnpm/ directory) and nuke it before installing so pnpm starts
  # from a clean slate — fixes the EUSAGE/`Cannot read properties of
  # null` failure mode after a previous deploy aborted mid-install.
  if [[ -d node_modules && ! -d node_modules/.pnpm ]]; then
    info "node_modules looks non-pnpm — removing for a clean install"
    rm -rf node_modules
  fi

  info "pnpm install (frozen first, regenerate if package.json drifted)"
  if ! pnpm install --frozen-lockfile 2>/dev/null; then
    info "lockfile missing or outdated — regenerating with full pnpm install"
    pnpm install
  fi
  ok "frontend deps in sync"

  info "pnpm build"
  pnpm build
  ok "next build complete"

  # next.config sets `output: "standalone"`. Next emits the self-contained
  # server but does NOT copy the client assets into that tree — that is the
  # caller's job. Without this the standalone server boots and 404s every
  # CSS/JS chunk and everything under public/.
  if [ -f .next/standalone/server.js ]; then
    info "syncing standalone assets (.next/static + public/)"
    rm -rf .next/standalone/.next/static .next/standalone/public
    if ! cp -r .next/static .next/standalone/.next/static; then
      fail "failed to copy .next/static into the standalone tree"
      exit 1
    fi
    if [ -d public ] && ! cp -r public .next/standalone/public; then
      fail "failed to copy public/ into the standalone tree"
      exit 1
    fi
    ok "standalone assets synced"
  fi

  info "pm2 restart QuataDigital-F"
  pm2 restart QuataDigital-F --update-env
  pm2 save
  ok "QuataDigital-F restarted"

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
  echo -e "  ${C_DIM}Investigate via:  journalctl -u quata-digital-backend -n 50  /  pm2 logs QuataDigital-F${C_RESET}"
fi
echo -e "${C_GOLD}${C_BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${C_RESET}"
echo

# Clear the rollback trap on a clean exit so we don't print the recipe
# after a green deploy.
if [[ $all_ok -eq 1 ]]; then
  trap - EXIT
fi
exit $((1 - all_ok))
