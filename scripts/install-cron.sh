#!/usr/bin/env bash
#
# install-cron.sh — Idempotent crontab entry installer for api-cfe backups.
#
# Usage:
#   ./scripts/install-cron.sh          # install the cron entry
#   ./scripts/install-cron.sh --remove # remove the cron entry
#
# The cron entry runs the backup script daily at 02:00 and logs to
# backups/cron.log.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "${SCRIPT_DIR}")"
BACKUP_DIR="${REPO_ROOT}/backups"

# Marker for identifying our cron entry
MARKER="# api-cfe daily DB backup"
CRON_LINE="0 2 * * * ${SCRIPT_DIR}/backup_db.sh >> ${BACKUP_DIR}/cron.log 2>&1"
CRON_ENTRY="${MARKER}
${CRON_LINE}"

log() { printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"; }

# Ensure backups directory exists
mkdir -p "${BACKUP_DIR}"

if [ "${1:-}" = "--remove" ]; then
  log "Removing cron entry for api-cfe backup"
  
  # Get current crontab (or empty if none)
  CURRENT_CRON="$(crontab -l 2>/dev/null || true)"
  
  if [ -z "${CURRENT_CRON}" ]; then
    log "No crontab entries found"
    exit 0
  fi
  
  # Remove our marker and the following line
  NEW_CRON="$(echo "${CURRENT_CRON}" | grep -v -A1 "^${MARKER}$" || true)"
  
  if [ "${NEW_CRON}" = "${CURRENT_CRON}" ]; then
    log "Cron entry not found — nothing to remove"
    exit 0
  fi
  
  echo "${NEW_CRON}" | crontab -
  log "Cron entry removed successfully"
  exit 0
fi

log "Installing cron entry for api-cfe backup"

# Get current crontab (or empty if none)
CURRENT_CRON="$(crontab -l 2>/dev/null || true)"

# Check if our entry already exists
if echo "${CURRENT_CRON}" | grep -qF "${MARKER}"; then
  log "Cron entry already exists — skipping"
  exit 0
fi

# Append our entry
if [ -z "${CURRENT_CRON}" ]; then
  NEW_CRON="${CRON_ENTRY}"
else
  NEW_CRON="${CURRENT_CRON}

${CRON_ENTRY}"
fi

echo "${NEW_CRON}" | crontab -
log "Cron entry installed successfully"
log ""
log "Current crontab:"
crontab -l
