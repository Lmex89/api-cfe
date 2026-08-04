#!/usr/bin/env fish
# =============================================================================
# restore-db.fish — Restore MySQL/MariaDB from a gzip-compressed backup (Fish)
# =============================================================================
#
# WHAT IT DOES
#   1. Reads DB credentials from .env (same file docker-compose loads).
#   2. Locates the running DB container (matches DB_HOST name, falls back to
#      scanning the compose network for mysql/mariadb containers).
#   3. Lists available backups when called with no arguments.
#   4. Prompts for confirmation before overwriting the database.
#   5. Decompresses the chosen .sql.gz and pipes it into `mariadb`/`mysql`
#      inside the container, replacing all existing data in the target database.
#
# USAGE
#   ./restore-db.fish                                     # list available backups
#   ./restore-db.fish backups/cfe_db_20260715.sql.gz      # restore from file
#
# WARNINGS
#   - This is a DESTRUCTIVE operation. All current data in the database will be
#     replaced by the contents of the backup file.
#   - The script asks for interactive confirmation before proceeding.
#   - When running from cron or CI, pipe `yes` into stdin:
#       yes | ./restore-db.fish backups/cfe_db_20260715.sql.gz
#
# DEPENDENCIES
#   docker, gunzip
#
# ENV VARS READ FROM .env
#   DB_HOST   — DB host / container name
#   DB_USER   — DB user with write privileges
#   DB_PSWD   — password for DB_USER
#   DB_NAME   — target database name
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
    if string match -qr '^#.*$' "$line"; or test -z "$line"
        continue
    end
    if string match -qr '^[A-Za-z_][A-Za-z0-9_]*=' "$line"
        set -l key (string split -m1 '=' "$line")[1]
        set -l value (string split -m1 '=' "$line")[2]
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
log_debug "Target container: $CONTAINER"

# ── Pick the client binary available in the container ────────────────────────
set -l CLIENT ""
for cand in mariadb mysql
    if docker exec "$CONTAINER" sh -c "command -v '$cand'" >/dev/null 2>&1
        set CLIENT "$cand"
        break
    end
end
if test -z "$CLIENT"
    log_error "Neither mariadb nor mysql client found in container $CONTAINER"
    exit 1
end
log_debug "Using client binary: $CLIENT"

# ── List mode: no arguments → show available backups ──────────────────────────
set -l BACKUP_DIR "$SCRIPT_DIR/backups"

if test (count $argv) -eq 0
    log_info "Available backups in $BACKUP_DIR:"
    echo ""
    set -l files (find "$BACKUP_DIR" -maxdepth 1 -name "$DB_NAME"'_*.sql.gz' 2>/dev/null | sort)

    if test -z "$files"
        echo "  (no backups found)"
    else
        for f in $files
            set -l SIZE (du -h "$f" | string split -f1 '\t')
            set -l MTIME (stat -c '%y' "$f" 2>/dev/null | cut -d. -f1)
            echo "  "(basename "$f")"  $SIZE  $MTIME"
        end
    end

    echo ""
    echo "Usage: ./"(basename (status filename))" <backup-file>"
    echo "Example: ./"(basename (status filename))" backups/"$DB_NAME"_20260715_020000.sql.gz"
    exit 0
end

# ── Resolve backup file path ─────────────────────────────────────────────────
set -l BACKUP_FILE "$argv[1]"

# If the path is relative (doesn't start with /), make it absolute
# relative to the script directory — not the caller's cwd.
if not string match -qr '^/' "$BACKUP_FILE"
    set BACKUP_FILE "$SCRIPT_DIR/$BACKUP_FILE"
end

if not test -f "$BACKUP_FILE"
    log_error "Backup file not found: $BACKUP_FILE"
    log_error "Run ./restore-db.fish with no arguments to list available backups."
    exit 1
end

set -l FILE_SIZE (du -h "$BACKUP_FILE" | string split -f1 '\t')
log_info "Selected backup: "(basename "$BACKUP_FILE")" ($FILE_SIZE)"

# ── Confirmation prompt ──────────────────────────────────────────────────────
log_warning "This will OVERWRITE all data in '$DB_NAME'."
echo -n "Continue? [y/N] "
set -l confirm (read)
if not string match -qy 'y' "$confirm"
    log_info "Aborted by user."
    exit 0
end

# ── Restore ──────────────────────────────────────────────────────────────────
# gunzip -c  → decompress to stdout (keeps the original .gz file intact)
# docker exec -i  → pass stdin into the container (-i = interactive mode)
# <client> ...  → reads SQL from stdin and executes it
log_info "Restoring database from: "(basename "$BACKUP_FILE")" ..."

gunzip -c "$BACKUP_FILE" | docker exec -i "$CONTAINER" "$CLIENT" \
    -u"$DB_USER" -p"$DB_PSWD" "$DB_NAME"
or begin
    log_error "Restore failed."
    exit 1
end

log_info "Restore completed successfully"
log_info "Database '$DB_NAME' now reflects the state from "(basename "$BACKUP_FILE")
