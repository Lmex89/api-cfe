#!/usr/bin/env fish
# =============================================================================
# backup-db.fish — MySQL/MariaDB backup via Docker container dump (Fish version)
# =============================================================================
#
# WHAT IT DOES
#   1. Reads DB credentials from .env (same file docker-compose loads).
#   2. Locates the running DB container (matches DB_HOST name, falls back to
#      scanning the compose network for mysql/mariadb containers).
#   3. Runs `mariadb-dump` (or `mysqldump`) inside the container and pipes the
#      output through gzip.
#   4. Saves the compressed dump to ./backups/<db>_<YYYYMMDD_HHMMSS>.sql.gz
#   5. Deletes backups older than RETENTION_DAYS (default 30).
#
# USAGE
#   ./backup-db.fish
#
# CRON EXAMPLE  (daily at 02:00, logs to backups/cron.log)
#   0 2 * * * /full/path/backup-db.fish >> /full/path/backups/cron.log 2>&1
#
# DEPENDENCIES
#   docker, gzip, find
#
# ENV VARS READ FROM .env
#   DB_HOST   — DB host / container name
#   DB_USER   — DB user with dump privileges
#   DB_PSWD   — password for DB_USER
#   DB_NAME   — database name to dump
# =============================================================================

# ── Exit on error ─────────────────────────────────────────────────────────────
# Fish exits on error by default when used in scripts
status is-interactive; and exit 1

# ── Logging helpers ───────────────────────────────────────────────────────────
function _ts
    date +"%Y-%m-%d %H:%M:%S"
end

function log_debug
    echo "[$(_ts)] [DEBUG]   $argv" >&2
end

function log_info
    echo "[$(_ts)] [INFO]    $argv"
end

function log_warning
    echo "[$(_ts)] [WARNING] $argv" >&2
end

function log_error
    echo "[$(_ts)] [ERROR]   $argv" >&2
end

# ── Resolve project root ─────────────────────────────────────────────────────
set -l SCRIPT_DIR (realpath (status dirname))
log_debug "Script directory: $SCRIPT_DIR"

# ── Load environment ─────────────────────────────────────────────────────────
set -l ENV_FILE "$SCRIPT_DIR/.env"

if not test -f "$ENV_FILE"
    log_error "Environment file not found: $ENV_FILE"
    exit 1
end

# Parse .env manually (Fish doesn't source bash-style env files)
for line in (cat "$ENV_FILE")
    # Skip comments and empty lines
    if string match -qr '^#.*$' "$line"; or test -z "$line"
        continue
    end
    # Extract key=value pairs
    if string match -qr '^[A-Za-z_][A-Za-z0-9_]*=' "$line"
        set -l key (string split -m1 '=' "$line")[1]
        set -l value (string split -m1 '=' "$line")[2]
        # Remove surrounding quotes if present
        set value (string trim -c '"' -c "'" "$value")
        set -gx $key "$value"
    end
end

if test -z "$DB_HOST"; or test -z "$DB_USER"; or test -z "$DB_PSWD"; or test -z "$DB_NAME"
    log_error "Missing required DB_* variables in $ENV_FILE"
    exit 1
end
log_debug "Loaded env from $ENV_FILE (database=$DB_NAME, host=$DB_HOST, user=$DB_USER)"

# ── Locate the DB container ──────────────────────────────────────────────────
set -l CONTAINER ""

# 1) Try by container name matching DB_HOST (anchored regex on /<name>)
set -l NAME_FILTER "^/$DB_HOST\$"
set CONTAINER (docker ps -q --filter "name=$NAME_FILTER" 2>/dev/null | head -n1)

# 2) Fallback: scan the compose network for mysql/mariadb containers
if test -z "$CONTAINER"
    set -l NETWORK (docker compose -f "$SCRIPT_DIR/docker-compose.yaml" config --networks 2>/dev/null \
        | string match -r '^  [A-Za-z0-9_-]+:' \
        | string trim -c ' :' \
        | head -n1)
    if test -z "$NETWORK"
        set NETWORK db-test-net
    end
    log_debug "Searching for DB container on network '$NETWORK'"
    for c in (docker ps -q --filter "network=$NETWORK" 2>/dev/null)
        set -l img (docker inspect --format '{{.Image}}' "$c" 2>/dev/null)
        if string match -qr 'mysql|maria' "$img"
            set CONTAINER "$c"
            break
        end
    end
end

if test -z "$CONTAINER"
    log_error "The DB container could not be found."
    log_error "Expected a container named '$DB_HOST' or a mysql/mariadb container on the compose network."
    exit 1
end
log_info "Target container: $CONTAINER"

# ── Pick the dump binary available in the container ──────────────────────────
set -l DUMPER ""
for cand in mariadb-dump mysqldump
    if docker exec "$CONTAINER" sh -c "command -v '$cand'" >/dev/null 2>&1
        set DUMPER "$cand"
        break
    end
end
if test -z "$DUMPER"
    log_error "Neither mariadb-dump nor mysqldump found in container $CONTAINER"
    exit 1
end
log_debug "Using dump binary: $DUMPER"

# ── Build output path ────────────────────────────────────────────────────────
set -l BACKUP_DIR "$SCRIPT_DIR/backups"
set -l TIMESTAMP (date +"%Y%m%d_%H%M%S")
set -l FILENAME "$DB_NAME"_"$TIMESTAMP.sql.gz"
set -l OUTPUT_PATH "$BACKUP_DIR/$FILENAME"
set -l RETENTION_DAYS 30

mkdir -p "$BACKUP_DIR"
log_info "Starting backup → $OUTPUT_PATH"

# ── Dump & compress ─────────────────────────────────────────────────────────
docker exec "$CONTAINER" "$DUMPER" \
    -u"$DB_USER" -p"$DB_PSWD" \
    --single-transaction --routines --triggers --events \
    "$DB_NAME" | gzip > "$OUTPUT_PATH"

# ── Validate dump ────────────────────────────────────────────────────────────
if not test -s "$OUTPUT_PATH"
    log_error "Backup produced an empty file — removing it."
    rm -f "$OUTPUT_PATH"
    exit 1
end

set -l FILE_SIZE (du -h "$OUTPUT_PATH" | string split -f1 '\t')
log_info "Backup created successfully: $FILENAME ($FILE_SIZE)"

# ── Retention cleanup ────────────────────────────────────────────────────────
set -l DELETED_COUNT 0
for old_file in (find "$BACKUP_DIR" -name "$DB_NAME"'_*.sql.gz' -mtime +"$RETENTION_DAYS")
    log_debug "Removing expired backup: "(basename "$old_file")
    set DELETED_COUNT (math "$DELETED_COUNT + 1")
    rm -f "$old_file"
end

if test "$DELETED_COUNT" -gt 0
    log_info "Cleaned $DELETED_COUNT backup(s) older than $RETENTION_DAYS days"
else
    log_debug "No expired backups to clean"
end

log_info "Backup job finished"
