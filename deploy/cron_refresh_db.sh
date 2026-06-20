#!/usr/bin/env bash
# ============================================================================
# Cron-friendly: оновити VPS local DB з cloud (faforre.mysql.tools).
# Захист: робить бекап старого VPS перед перезаписом + write-lock-файл.
# 
# Запуск з cron (раз на 6 годин):
#   0 */6 * * * /var/www/farforrent/deploy/cron_refresh_db.sh >> /var/log/rentalhub-db-sync.log 2>&1
# 
# Або щодоби о 04:00:
#   0 4 * * *  /var/www/farforrent/deploy/cron_refresh_db.sh >> /var/log/rentalhub-db-sync.log 2>&1
# 
# Запуск вручну:
#   sudo bash deploy/cron_refresh_db.sh
# ============================================================================
set -euo pipefail

LOCK="/var/run/rentalhub-db-sync.lock"
ENV_FILE="/var/www/farforrent/backend/.env"
BACKUP_DIR="/var/www/farforrent/db_backups"
TS=$(date +%Y%m%d_%H%M%S)
LOG_PREFIX="[$(date '+%Y-%m-%d %H:%M:%S')]"

# --- Lock (запобігає паралельному запуску) ---
exec 9>"$LOCK"
if ! flock -n 9; then
    echo "$LOG_PREFIX ⏭️  Already running, exiting"
    exit 0
fi

# --- Load env ---
if [ ! -f "$ENV_FILE" ]; then
    echo "$LOG_PREFIX ❌ .env not found at $ENV_FILE"
    exit 1
fi
set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

CLOUD_HOST="${RH_DB_HOST:-farforre.mysql.tools}"
CLOUD_PORT="${RH_DB_PORT:-3306}"
CLOUD_USER="${RH_DB_USERNAME:?RH_DB_USERNAME required}"
CLOUD_PASS="${RH_DB_PASSWORD:?RH_DB_PASSWORD required}"
CLOUD_DB="${RH_DB_DATABASE:-farforre_rentalhub}"

LOCAL_HOST="${LOCAL_DB_HOST:-127.0.0.1}"
LOCAL_PORT="${LOCAL_DB_PORT:-3306}"
LOCAL_USER="${LOCAL_DB_USER:-root}"
LOCAL_PASS="${LOCAL_DB_PASS:-}"
LOCAL_DB="${LOCAL_DB_NAME:-farforre_rentalhub}"

mkdir -p "$BACKUP_DIR"

echo "$LOG_PREFIX ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "$LOG_PREFIX 🔄 Starting DB sync: $CLOUD_HOST/$CLOUD_DB → $LOCAL_HOST/$LOCAL_DB"

# --- Step 1: Backup current local DB (тільки останні 14 днів) ---
mysqldump -h "$LOCAL_HOST" -P "$LOCAL_PORT" -u "$LOCAL_USER" \
  ${LOCAL_PASS:+-p"$LOCAL_PASS"} \
  --routines --triggers --events \
  --single-transaction --quick "$LOCAL_DB" 2>/dev/null \
  | gzip > "$BACKUP_DIR/cron_backup_${TS}.sql.gz"
SIZE=$(du -h "$BACKUP_DIR/cron_backup_${TS}.sql.gz" | cut -f1)
echo "$LOG_PREFIX 📦 Backup: $SIZE"

# Видалити бекапи старше 14 днів
find "$BACKUP_DIR" -name "cron_backup_*.sql.gz" -mtime +14 -delete 2>/dev/null || true

# --- Step 2: Dump cloud ---
TMP_DUMP="$BACKUP_DIR/cloud_dump_${TS}.sql"
mysqldump -h "$CLOUD_HOST" -P "$CLOUD_PORT" -u "$CLOUD_USER" -p"$CLOUD_PASS" \
  --routines --triggers --events \
  --single-transaction --quick \
  --skip-lock-tables \
  --column-statistics=0 \
  "$CLOUD_DB" > "$TMP_DUMP" 2>/dev/null
DUMP_SIZE=$(du -h "$TMP_DUMP" | cut -f1)
DUMP_LINES=$(wc -l < "$TMP_DUMP")
echo "$LOG_PREFIX ☁️  Dump fetched: $DUMP_SIZE ($DUMP_LINES lines)"

# --- Sanity check: dump повинен мати щонайменше 100 рядків ---
if [ "$DUMP_LINES" -lt 100 ]; then
    echo "$LOG_PREFIX ❌ Dump suspiciously small — ABORTING import"
    rm -f "$TMP_DUMP"
    exit 1
fi

# --- Step 3: Replace local DB ---
mysql -h "$LOCAL_HOST" -P "$LOCAL_PORT" -u "$LOCAL_USER" \
  ${LOCAL_PASS:+-p"$LOCAL_PASS"} \
  -e "DROP DATABASE IF EXISTS \`$LOCAL_DB\`; CREATE DATABASE \`$LOCAL_DB\` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;" 2>/dev/null

mysql -h "$LOCAL_HOST" -P "$LOCAL_PORT" -u "$LOCAL_USER" \
  ${LOCAL_PASS:+-p"$LOCAL_PASS"} \
  "$LOCAL_DB" < "$TMP_DUMP" 2>/dev/null

rm -f "$TMP_DUMP"

# --- Step 4: Quick stats ---
STATS=$(mysql -h "$LOCAL_HOST" -P "$LOCAL_PORT" -u "$LOCAL_USER" \
  ${LOCAL_PASS:+-p"$LOCAL_PASS"} -N -s "$LOCAL_DB" -e "
    SELECT CONCAT(
        'orders=', (SELECT COUNT(*) FROM orders),
        ' products=', (SELECT COUNT(*) FROM products),
        ' fin_payments=', (SELECT COUNT(*) FROM fin_payments)
    );" 2>/dev/null)

echo "$LOG_PREFIX ✅ Sync complete: $STATS"
echo "$LOG_PREFIX 💾 Latest cloud snapshot available locally for tests/dev"
echo ""
