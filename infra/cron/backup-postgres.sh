#!/bin/bash
# QUATA Digital — nightly Postgres dump.
#
# Pushes a `pg_dump` to an off-VPS S3-compatible bucket so a complete
# disk failure does not equal complete data loss. Reads its environment
# from /etc/quata-digital.env so it picks up the same DATABASE_URL the
# app uses.
#
# Install once:
#   sudo install -m 0750 infra/cron/backup-postgres.sh /usr/local/sbin/quata-backup
#   sudo crontab -e
#   # then add:
#   10 2 * * *  /usr/local/sbin/quata-backup >> /var/log/quata-backup.log 2>&1
#
# Required env (in /etc/quata-digital.env or the cron env):
#   DATABASE_URL              postgres connection URL
#   BACKUP_S3_BUCKET          target bucket (e.g. quata-backups)
#   BACKUP_S3_PREFIX          optional prefix (default: postgres)
#   BACKUP_S3_ENDPOINT_URL    optional (R2/MinIO/Backblaze)
#   AWS_ACCESS_KEY_ID         + AWS_SECRET_ACCESS_KEY
#   BACKUP_RETENTION_DAYS     default 30
#
# Outcome is reported to @QuataAlertsBot as
# infra.database_backup_completed / infra.database_backup_failed. A backup
# that silently stops running is the classic way to discover you have no
# backups on the day you need one — so the *failure* path is wired to a
# trap and fires on any error, including a partial upload.
#
# Optional env for the alert (skipped entirely when unset):
#   QUATA_BACKEND_DIR         default /home/Quata-Digital/backend
set -euo pipefail

# Load env file if present.
ENV_FILE="/etc/quata-digital.env"
if [[ -r "$ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  set -a; source "$ENV_FILE"; set +a
fi

BACKEND_DIR="${QUATA_BACKEND_DIR:-/home/Quata-Digital/backend}"

# Publish an event through the app's own notification service. Never allowed
# to fail the backup: `|| true` plus a guard on the venv existing, so a box
# without the backend checked out still backs up fine.
notify() {
  local event="$1" payload="$2" priority="${3:-}"
  local python="${BACKEND_DIR}/.venv/bin/python"
  [[ -x "$python" ]] || return 0
  local args=(-m app.scripts.notify_event "$event" --payload "$payload"
              --reference DB-BACKUP --wait --quiet)
  [[ -n "$priority" ]] && args+=(--priority "$priority")
  (cd "$BACKEND_DIR" && "$python" "${args[@]}") || true
}

# Fires on any non-zero exit under `set -e`, including a failed pg_dump or
# a failed upload. Cleared on the success path below.
BACKUP_STAGE="starting"
on_failure() {
  local code=$?
  notify infra.database_backup_failed \
    "$(printf '{"service":"Nightly Postgres backup","detail":"failed during: %s","error":"exit code %s"}' \
       "$BACKUP_STAGE" "$code")" \
    critical
}
trap on_failure ERR

: "${DATABASE_URL:?DATABASE_URL must be set}"
: "${BACKUP_S3_BUCKET:?BACKUP_S3_BUCKET must be set}"
PREFIX="${BACKUP_S3_PREFIX:-postgres}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

DUMP_FILE="$TMP_DIR/quata-${STAMP}.sql.gz"

BACKUP_STAGE="pg_dump"
echo "[backup] $(date -u +%FT%TZ) dumping → ${DUMP_FILE}"
pg_dump --no-owner --clean --if-exists "$DATABASE_URL" | gzip -9 > "$DUMP_FILE"
DUMP_SIZE="$(du -h "$DUMP_FILE" | cut -f1)"
echo "[backup] dump size: ${DUMP_SIZE}"

# Upload.
S3_KEY="${PREFIX}/quata-${STAMP}.sql.gz"
ENDPOINT_FLAG=""
if [[ -n "${BACKUP_S3_ENDPOINT_URL:-}" ]]; then
  ENDPOINT_FLAG="--endpoint-url=${BACKUP_S3_ENDPOINT_URL}"
fi

BACKUP_STAGE="s3 upload"
aws s3 cp ${ENDPOINT_FLAG} "$DUMP_FILE" "s3://${BACKUP_S3_BUCKET}/${S3_KEY}" \
  --only-show-errors
echo "[backup] uploaded → s3://${BACKUP_S3_BUCKET}/${S3_KEY}"

# The dump is safely off-box — report success now. Pruning old objects
# below is housekeeping; if it fails the backup itself was still good, and
# the ERR trap will report that separately.
notify infra.database_backup_completed \
  "$(printf '{"service":"Nightly Postgres backup","size":"%s","detail":"uploaded to s3://%s/%s"}' \
     "$DUMP_SIZE" "$BACKUP_S3_BUCKET" "$S3_KEY")"

# Cull old objects beyond the retention window.
BACKUP_STAGE="retention prune"
echo "[backup] pruning objects older than ${RETENTION_DAYS} days"
THRESHOLD=$(date -u -d "${RETENTION_DAYS} days ago" +%Y-%m-%d)
aws s3api list-objects-v2 ${ENDPOINT_FLAG} \
  --bucket "$BACKUP_S3_BUCKET" \
  --prefix "$PREFIX/" \
  --query "Contents[?LastModified<'${THRESHOLD}'].Key" \
  --output text 2>/dev/null \
  | tr '\t' '\n' \
  | grep -v '^$' \
  | while read -r key; do
      echo "[backup] delete: $key"
      aws s3 rm ${ENDPOINT_FLAG} "s3://${BACKUP_S3_BUCKET}/$key" --only-show-errors || true
    done

echo "[backup] $(date -u +%FT%TZ) OK"
