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
  pip install -r requirements.txt --quiet
  pip install "psycopg[binary]>=3.2.3" --quiet
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

  info "pnpm install (frozen first, regenerate if package.json drifted)"
  # Frozen-lockfile is the right default — guarantees deterministic builds.
  # When package.json changes, the lockfile on the VPS is stale until the
  # boss has updated it. Rather than failing the deploy, regenerate it and
  # carry on; the next deploy will be fast again.
  if ! pnpm install --frozen-lockfile; then
    info "lockfile outdated — running full pnpm install to regenerate"
    pnpm install
  fi
  ok "frontend deps in sync"

  info "pnpm build"
  pnpm build
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

exit $((1 - all_ok))
