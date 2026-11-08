#!/usr/bin/env bash
#
# backup_db.sh — Manual MySQL/MariaDB backup for the api-cfe project.
#
# Creates a gzipped dump of the Dockerized database, stores it in the
# configured backup directory, prunes old local backups (retention policy),
# and optionally uploads the dump to Backblaze B2.
#
# Usage:
#   ./scripts/backup_db.sh [backup_dir] [retention_days]
#
# Environment variables (read from .env when present):
#   DB_HOST             Docker service name for the database (default: local-mariadb)
#   DB_USER             Database user (default: root)
#   DB_PSWD             Database password
#   DB_NAME             Database name (default: cfe_db)
#   BACK_BLAZE_KEY_ID   Backblaze B2 application key ID (for rclone)
#   BACK_BLAZE_SECRET   Backblaze B2 application key (for rclone)
#   BACK_BLAZE_BUCKET   Backblaze B2 bucket name (default: lmex-backups-db)
#   BACK_BLAZE_DIR      Folder/prefix inside the bucket (default: api-cfe-db)
#
# Returns:
#   0 on success, non-zero on failure.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "${SCRIPT_DIR}")"

# Load environment variables from .env
load_env() {
  [ -f "${REPO_ROOT}/.env" ] || return 0
  while IFS='=' read -r key value; do
    case "${key}" in
      DB_HOST|DB_USER|DB_PSWD|DB_NAME| \
      BACK_BLAZE_KEY_ID|BACK_BLAZE_SECRET|BACK_BLAZE_BUCKET|BACK_BLAZE_DIR)
        if [ -n "${value}" ]; then
          export "${key}=${value}"
        fi
        ;;
    esac
  done < <(grep -E '^[A-Za-z_][A-Za-z0-9_]*=' "${REPO_ROOT}/.env" || true)
}

load_env

DB_HOST="${DB_HOST:-local-mariadb}"
DB_USER="${DB_USER:-root}"
DB_PSWD="${DB_PSWD:-}"
DB_NAME="${DB_NAME:-cfe_db}"
BACKUP_DIR="${1:-${REPO_ROOT}/backups}"
RETENTION_DAYS="${2:-30}"

log() { printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"; }

fail() {
  log "ERROR: $*"
  exit 1
}

# Resolve the running database container
get_db_container() {
  local container=""
  
  # Try by container name matching DB_HOST
  container="$(docker ps -q --filter "name=^/${DB_HOST}$" 2>/dev/null | head -n1)"
  
  if [ -n "${container}" ]; then
    echo "${container}"
    return 0
  fi
  
  # Fallback: scan the compose network for mysql/mariadb containers
  local network="db-test-net"
  for c in $(docker ps -q --filter "network=${network}" 2>/dev/null); do
    local img
    img="$(docker inspect --format '{{.Config.Image}}' "${c}" 2>/dev/null)"
    if echo "${img}" | grep -qE 'mysql|maria'; then
      echo "${c}"
      return 0
    fi
  done
  
  return 1
}

DB_CONTAINER_NAME="$(get_db_container)" || \
  fail "Database container is not running. Expected '${DB_HOST}' or a mysql/mariadb container on network '${network}'"

# Pick the dump binary available in the container
DUMPER=""
for cand in mariadb-dump mysqldump; do
  if docker exec "${DB_CONTAINER_NAME}" sh -c "command -v '${cand}'" >/dev/null 2>&1; then
    DUMPER="${cand}"
    break
  fi
done

[ -z "${DUMPER}" ] && fail "Neither mariadb-dump nor mysqldump found in container ${DB_CONTAINER_NAME}"

# Ensure the backup directory exists
mkdir -p "${BACKUP_DIR}"

# Timestamped backup file name
TIMESTAMP="$(date '+%Y%m%d_%H%M%S')"
BACKUP_FILE="${BACKUP_DIR}/${DB_NAME}_${TIMESTAMP}.sql.gz"

log "Starting backup of database '${DB_NAME}' from container '${DB_CONTAINER_NAME}'"

# Create the dump
docker exec "${DB_CONTAINER_NAME}" "${DUMPER}" \
  -u"${DB_USER}" -p"${DB_PSWD}" \
  --single-transaction --routines --triggers --events \
  "${DB_NAME}" | gzip > "${BACKUP_FILE}"

# Validate the backup: non-zero size and gzip integrity
if [ ! -s "${BACKUP_FILE}" ]; then
  rm -f "${BACKUP_FILE}"
  fail "Backup file is empty; dump failed"
fi

if ! gzip -t "${BACKUP_FILE}" 2>/dev/null; then
  rm -f "${BACKUP_FILE}"
  fail "Backup file failed gzip integrity check"
fi

BACKUP_SIZE="$(du -h "${BACKUP_FILE}" | cut -f1)"
log "Backup created: $(basename "${BACKUP_FILE}") (${BACKUP_SIZE})"

# Local retention: delete backups older than RETENTION_DAYS
log "Applying local retention policy (delete older than ${RETENTION_DAYS} days)"
DELETED_COUNT=0
while IFS= read -r old_file; do
  log "Removing old backup: $(basename "${old_file}")"
  DELETED_COUNT=$((DELETED_COUNT + 1))
done < <(find "${BACKUP_DIR}" -maxdepth 1 -name "${DB_NAME}_*.sql.gz" \
  -type f -mtime +"${RETENTION_DAYS}" -print -delete)

if [ "${DELETED_COUNT}" -gt 0 ]; then
  log "Cleaned ${DELETED_COUNT} backup(s) older than ${RETENTION_DAYS} days"
else
  log "No expired backups to clean"
fi

# Optional remote upload to Backblaze B2 via rclone
upload_to_backblaze() {
  local cloud_bucket="${BACK_BLAZE_BUCKET:-lmex-backups-db}"
  local cloud_dir="${BACK_BLAZE_DIR:-api-cfe-db}"
  local cloud_path="${cloud_bucket}/${cloud_dir}"

  if ! command -v rclone >/dev/null 2>&1; then
    log "WARNING: rclone not found — skipping Backblaze B2 upload (install: https://rclone.org/install/)"
    return 0
  fi

  if [ -z "${BACK_BLAZE_KEY_ID:-}" ] || [ -z "${BACK_BLAZE_SECRET:-}" ]; then
    log "WARNING: BACK_BLAZE_KEY_ID / BACK_BLAZE_SECRET not set — skipping Backblaze B2 upload"
    return 0
  fi

  log "Uploading backup to Backblaze B2 → b2:${cloud_path}/$(basename "${BACKUP_FILE}")"
  if rclone copy "${BACKUP_FILE}" ":b2:${cloud_path}/" \
      --b2-account "${BACK_BLAZE_KEY_ID}" \
      --b2-key "${BACK_BLAZE_SECRET}"; then
    log "Cloud upload succeeded: $(basename "${BACKUP_FILE}")"
  else
    log "ERROR: Cloud upload failed — local backup kept at ${BACKUP_FILE}"
  fi

  log "Pruning B2 backups older than ${RETENTION_DAYS} days"
  rclone delete ":b2:${cloud_path}/" \
      --b2-account "${BACK_BLAZE_KEY_ID}" \
      --b2-key "${BACK_BLAZE_SECRET}" \
      --include "*.sql.gz" --min-age "${RETENTION_DAYS}d" \
    || log "WARNING: Cloud retention cleanup failed — cloud backups kept"
}

upload_to_backblaze

log "Backup completed successfully"
