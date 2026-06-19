#!/usr/bin/env bash
# ============================================================================
# Скрипт оновлення VPS MySQL з cloud (farforre.mysql.tools).
# Безпечно: спочатку робить локальний бекап старої БД, потім дамп з cloud,
# потім імпорт. Якщо щось зламається — є файл для rollback.
#
# Використання на VPS (у /var/www/farforrent):
#   sudo bash deploy/refresh_db_from_cloud.sh
# ============================================================================
set -euo pipefail

# --- Конфіг (читаємо з .env або задаємо вручну) ---
ENV_FILE="/var/www/farforrent/backend/.env"
if [ -f "$ENV_FILE" ]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

CLOUD_HOST="${RH_DB_HOST:-farforre.mysql.tools}"
CLOUD_PORT="${RH_DB_PORT:-3306}"
CLOUD_USER="${RH_DB_USERNAME:?RH_DB_USERNAME required}"
CLOUD_PASS="${RH_DB_PASSWORD:?RH_DB_PASSWORD required}"
CLOUD_DB="${RH_DB_DATABASE:-farforre_rentalhub}"

# VPS local DB (можна тримати таку ж саму назву)
LOCAL_HOST="${LOCAL_DB_HOST:-127.0.0.1}"
LOCAL_PORT="${LOCAL_DB_PORT:-3306}"
LOCAL_USER="${LOCAL_DB_USER:-root}"
LOCAL_PASS="${LOCAL_DB_PASS:-}"
LOCAL_DB="${LOCAL_DB_NAME:-farforre_rentalhub}"

BACKUP_DIR="/var/www/farforrent/db_backups"
TS=$(date +%Y%m%d_%H%M%S)
mkdir -p "$BACKUP_DIR"

echo "📦 Step 1/4: Backup поточної VPS-БД у $BACKUP_DIR/before_refresh_${TS}.sql.gz"
mysqldump -h "$LOCAL_HOST" -P "$LOCAL_PORT" -u "$LOCAL_USER" \
  ${LOCAL_PASS:+-p"$LOCAL_PASS"} \
  --routines --triggers --events \
  --single-transaction --quick "$LOCAL_DB" \
  | gzip > "$BACKUP_DIR/before_refresh_${TS}.sql.gz"
echo "   ✓ Розмір бекапу: $(du -h "$BACKUP_DIR/before_refresh_${TS}.sql.gz" | cut -f1)"

echo ""
echo "🌐 Step 2/4: Дамп з cloud ($CLOUD_HOST/$CLOUD_DB)…"
mysqldump -h "$CLOUD_HOST" -P "$CLOUD_PORT" -u "$CLOUD_USER" \
  -p"$CLOUD_PASS" \
  --routines --triggers --events \
  --single-transaction --quick \
  --skip-lock-tables \
  --column-statistics=0 \
  "$CLOUD_DB" > "$BACKUP_DIR/cloud_dump_${TS}.sql"
echo "   ✓ Розмір дампу: $(du -h "$BACKUP_DIR/cloud_dump_${TS}.sql" | cut -f1)"

echo ""
echo "♻️  Step 3/4: Перезапис локальної БД (DROP + CREATE + import)…"
mysql -h "$LOCAL_HOST" -P "$LOCAL_PORT" -u "$LOCAL_USER" \
  ${LOCAL_PASS:+-p"$LOCAL_PASS"} \
  -e "DROP DATABASE IF EXISTS \`$LOCAL_DB\`; CREATE DATABASE \`$LOCAL_DB\` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

mysql -h "$LOCAL_HOST" -P "$LOCAL_PORT" -u "$LOCAL_USER" \
  ${LOCAL_PASS:+-p"$LOCAL_PASS"} \
  "$LOCAL_DB" < "$BACKUP_DIR/cloud_dump_${TS}.sql"
echo "   ✓ Імпорт завершено"

echo ""
echo "🔄 Step 4/4: Перезапуск backend"
if systemctl is-active --quiet rentalhub-backend; then
  systemctl restart rentalhub-backend
  echo "   ✓ rentalhub-backend перезапущено"
else
  echo "   ⚠️  rentalhub-backend не активний — пропускаю"
fi

echo ""
echo "✅ Готово!"
echo ""
echo "📊 Швидка перевірка:"
mysql -h "$LOCAL_HOST" -P "$LOCAL_PORT" -u "$LOCAL_USER" \
  ${LOCAL_PASS:+-p"$LOCAL_PASS"} "$LOCAL_DB" \
  -e "SELECT 
      (SELECT COUNT(*) FROM orders) AS orders_count,
      (SELECT COUNT(*) FROM products) AS products_count,
      (SELECT COUNT(*) FROM fin_payments) AS fin_payments_count,
      (SELECT COUNT(*) FROM fin_transactions) AS fin_transactions_count;"

echo ""
echo "💾 Бекап старої БД (rollback): $BACKUP_DIR/before_refresh_${TS}.sql.gz"
echo "   Відновити: gunzip -c <file> | mysql -u $LOCAL_USER $LOCAL_DB"
