#!/usr/bin/env bash
#
# restore_db.sh — Manual MySQL/MariaDB restore for the api-cfe project.
#
# Restores a gzipped dump into the Dockerized database. Stops the backend
# container for the duration of the restore to prevent writes during the
# operation, then restarts it and verifies health.
#
# Usage:
#   ./scripts/restore_db.sh /path/to/backup.sql.gz
#
# Environment variables (read from .env when present):
#   DB_HOST       Docker service name for the database (default: local-mariadb)
#   DB_USER       Database user (default: root)
#   DB_PSWD       Database password
#   DB_NAME       Database name (default: cfe_db)
#
# Returns:
#   0 on success, non-zero on failure.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "${SCRIPT_DIR}")"

load_env() {
  [ -f "${REPO_ROOT}/.env" ] || return 0
  while IFS='=' read -r key value; do
    case "${key}" in
      DB_HOST|DB_USER|DB_PSWD|DB_NAME)
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

log() { printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"; }

fail() {
  log "ERROR: $*"
  exit 1
}

get_db_container() {
  local container=""

  container="$(docker ps -q --filter "name=^/${DB_HOST}$" 2>/dev/null | head -n1)"

  if [ -n "${container}" ]; then
    echo "${container}"
    return 0
  fi

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

BACKUP_FILE="${1:-}"
if [ -z "${BACKUP_FILE}" ]; then
  fail "Usage: $0 /path/to/backup.sql.gz"
fi

if [ ! -f "${BACKUP_FILE}" ]; then
  fail "Backup file not found: ${BACKUP_FILE}"
fi

if ! gzip -t "${BACKUP_FILE}" 2>/dev/null; then
  fail "Backup file is not a valid gzip archive: ${BACKUP_FILE}"
fi

log "About to restore database '${DB_NAME}' from ${BACKUP_FILE}"
read -r -p "This DESTROYS current data. Continue? [y/N] " confirmation
if [[ ! "${confirmation}" =~ ^[Yy]$ ]]; then
  log "Restore aborted by user"
  exit 0
fi

DB_CONTAINER_NAME="$(get_db_container)" || \
  fail "Database container is not running. Expected '${DB_HOST}' or a mysql/mariadb container on network 'db-test-net'"

log "Stopping api container"
docker compose -f "${REPO_ROOT}/docker-compose.yaml" stop api || \
  log "WARNING: could not stop api container; continuing anyway"

log "Dropping and recreating database '${DB_NAME}'"
docker exec "${DB_CONTAINER_NAME}" \
  mysql -u"${DB_USER}" -p"${DB_PSWD}" -v -e \
  "DROP DATABASE IF EXISTS ${DB_NAME}; CREATE DATABASE ${DB_NAME};"

log "Restoring backup into '${DB_NAME}'"
gunzip -c "${BACKUP_FILE}" | docker exec -i "${DB_CONTAINER_NAME}" \
  mysql -u"${DB_USER}" -p"${DB_PSWD}" "${DB_NAME}"

log "Restarting api container"
docker compose -f "${REPO_ROOT}/docker-compose.yaml" start api

log "Waiting for API health check"
for i in $(seq 1 30); do
  if curl -sf http://localhost:8080/docs >/dev/null 2>&1; then
    log "API is healthy"
    break
  fi
  if [ "${i}" -eq 30 ]; then
    fail "API did not become healthy within 30 tries; check 'docker compose ps'"
  fi
  sleep 2
done

log "Restore completed successfully"
