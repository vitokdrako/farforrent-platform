#!/bin/bash
# ============================================================================
# ОДНОРАЗОВИЙ МІГРАЦІЙНИЙ СКРИПТ: cloud MySQL → local MySQL на VPS
#
# Що робить:
#   1. Встановлює MySQL 8.0 (якщо ще нема)
#   2. Тюнить my.cnf під ваш VPS (innodb_buffer_pool = 50% RAM)
#   3. Створює БД farforre_rentalhub + farforre_db, юзера farforre_vps
#   4. Дампить обидві cloud БД → імпорт у локальні
#   5. Оновлює backend/.env — RH_DB_HOST/OC_DB_HOST → 127.0.0.1
#   6. Перезапускає rentalhub-backend
#   7. Ставить cron на нічні бекапи (30 днів rotation)
#
# ЗАПУСК:
#   sudo bash /var/www/farforrent/deploy/setup_local_db.sh
#
# ROLLBACK (якщо щось піде не так):
#   sudo cp /var/www/farforrent/backend/.env.bak.<timestamp> /var/www/farforrent/backend/.env
#   sudo systemctl restart rentalhub-backend
# ============================================================================
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="$REPO_ROOT/backend/.env"
BACKUP_DIR="/var/backups/mysql"
LOCAL_USER="farforre_vps"
LOCAL_PASS="EDt869Up6y"
LOCAL_HOST="127.0.0.1"
LOCAL_PORT="3306"

# ---------- Cloud creds з .env ----------
if [ ! -f "$ENV_FILE" ]; then
  echo "❌ $ENV_FILE не знайдено — cloud паролі невідомі."
  exit 1
fi
set -a; source "$ENV_FILE"; set +a

CLOUD_HOST="${RH_DB_HOST:-farforre.mysql.tools}"
CLOUD_PORT="${RH_DB_PORT:-3306}"
CLOUD_RH_USER="${RH_DB_USERNAME:-farforre_rentalhub}"
CLOUD_RH_PASS="${RH_DB_PASSWORD:?RH_DB_PASSWORD required in .env}"
CLOUD_RH_DB="${RH_DB_DATABASE:-farforre_rentalhub}"

CLOUD_OC_USER="${OC_DB_USERNAME:-farforre_db}"
CLOUD_OC_PASS="${OC_DB_PASSWORD:?OC_DB_PASSWORD required in .env}"
CLOUD_OC_DB="${OC_DB_DATABASE:-farforre_db}"

# ==========================================================================
# [1/7] Встановлення MySQL
# ==========================================================================
echo "═══ [1/7] MySQL install ═══"
if ! command -v mysql >/dev/null 2>&1; then
  echo "📦 apt install mysql-server…"
  apt update -y
  DEBIAN_FRONTEND=noninteractive apt install -y mysql-server
  systemctl enable mysql
  systemctl start mysql
  echo "✅ MySQL 8 встановлено"
else
  echo "✅ MySQL уже стоїть: $(mysql --version)"
  systemctl is-active --quiet mysql || systemctl start mysql
fi

# ==========================================================================
# [2/7] Tuning
# ==========================================================================
echo ""
echo "═══ [2/7] my.cnf tuning ═══"
TUNE_FILE="/etc/mysql/mysql.conf.d/farforrent-tune.cnf"
if [ ! -f "$TUNE_FILE" ]; then
  TOTAL_MEM_KB=$(grep MemTotal /proc/meminfo | awk '{print $2}')
  BUFFER_POOL_MB=$((TOTAL_MEM_KB / 1024 / 2))   # 50% RAM
  [ "$BUFFER_POOL_MB" -lt 256 ] && BUFFER_POOL_MB=256
  cat > "$TUNE_FILE" <<EOF
[mysqld]
# автогенеровано deploy/setup_local_db.sh
innodb_buffer_pool_size       = ${BUFFER_POOL_MB}M
innodb_log_file_size          = 256M
innodb_flush_log_at_trx_commit = 2
innodb_flush_method           = O_DIRECT
max_connections               = 200
character-set-server          = utf8mb4
collation-server              = utf8mb4_unicode_ci
skip-name-resolve
EOF
  systemctl restart mysql
  echo "✅ innodb_buffer_pool_size = ${BUFFER_POOL_MB}M"
else
  echo "ℹ️  Уже налаштовано у $TUNE_FILE"
fi

# ==========================================================================
# [3/7] Створення БД і юзера (через root socket auth)
# ==========================================================================
echo ""
echo "═══ [3/7] БД + юзер ═══"
mysql <<SQL
CREATE DATABASE IF NOT EXISTS \`$CLOUD_RH_DB\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE IF NOT EXISTS \`$CLOUD_OC_DB\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS '$LOCAL_USER'@'localhost' IDENTIFIED BY '$LOCAL_PASS';
CREATE USER IF NOT EXISTS '$LOCAL_USER'@'127.0.0.1' IDENTIFIED BY '$LOCAL_PASS';
GRANT ALL PRIVILEGES ON \`$CLOUD_RH_DB\`.* TO '$LOCAL_USER'@'localhost';
GRANT ALL PRIVILEGES ON \`$CLOUD_RH_DB\`.* TO '$LOCAL_USER'@'127.0.0.1';
GRANT ALL PRIVILEGES ON \`$CLOUD_OC_DB\`.* TO '$LOCAL_USER'@'localhost';
GRANT ALL PRIVILEGES ON \`$CLOUD_OC_DB\`.* TO '$LOCAL_USER'@'127.0.0.1';
FLUSH PRIVILEGES;
SQL
echo "✅ Створено: БД '$CLOUD_RH_DB', '$CLOUD_OC_DB'; юзер '$LOCAL_USER'"

# ==========================================================================
# [4/7] Дамп з cloud → імпорт у local
# ==========================================================================
echo ""
echo "═══ [4/7] Мігрую дані з cloud ═══"
mkdir -p "$BACKUP_DIR"
TS=$(date +%Y%m%d_%H%M%S)
DUMP_RH="$BACKUP_DIR/cloud_rh_$TS.sql"
DUMP_OC="$BACKUP_DIR/cloud_oc_$TS.sql"

echo "🌐 mysqldump RH ($CLOUD_HOST/$CLOUD_RH_DB)…"
mysqldump -h "$CLOUD_HOST" -P "$CLOUD_PORT" -u "$CLOUD_RH_USER" -p"$CLOUD_RH_PASS" \
  --single-transaction --quick --skip-lock-tables --column-statistics=0 \
  --routines --triggers --events \
  "$CLOUD_RH_DB" > "$DUMP_RH"
echo "   ✓ $(du -h "$DUMP_RH" | cut -f1)"

echo "🌐 mysqldump OC ($CLOUD_HOST/$CLOUD_OC_DB) — може бути великий…"
mysqldump -h "$CLOUD_HOST" -P "$CLOUD_PORT" -u "$CLOUD_OC_USER" -p"$CLOUD_OC_PASS" \
  --single-transaction --quick --skip-lock-tables --column-statistics=0 \
  --routines --triggers --events \
  "$CLOUD_OC_DB" > "$DUMP_OC"
echo "   ✓ $(du -h "$DUMP_OC" | cut -f1)"

echo "♻️  Import у локальні БД…"
mysql "$CLOUD_RH_DB" < "$DUMP_RH"
mysql "$CLOUD_OC_DB" < "$DUMP_OC"
echo "✅ Дані перенесено"

# ==========================================================================
# [5/7] Переключення backend/.env на локальну БД
# ==========================================================================
echo ""
echo "═══ [5/7] backend/.env → 127.0.0.1 ═══"
cp "$ENV_FILE" "$ENV_FILE.bak.$TS"
sed -i \
  -e "s|^RH_DB_HOST=.*|RH_DB_HOST=$LOCAL_HOST|" \
  -e "s|^RH_DB_PORT=.*|RH_DB_PORT=$LOCAL_PORT|" \
  -e "s|^RH_DB_USERNAME=.*|RH_DB_USERNAME=$LOCAL_USER|" \
  -e "s|^RH_DB_PASSWORD=.*|RH_DB_PASSWORD=$LOCAL_PASS|" \
  -e "s|^OC_DB_HOST=.*|OC_DB_HOST=$LOCAL_HOST|" \
  -e "s|^OC_DB_PORT=.*|OC_DB_PORT=$LOCAL_PORT|" \
  -e "s|^OC_DB_USERNAME=.*|OC_DB_USERNAME=$LOCAL_USER|" \
  -e "s|^OC_DB_PASSWORD=.*|OC_DB_PASSWORD=$LOCAL_PASS|" \
  "$ENV_FILE"
echo "✅ .env оновлено. Бекап: $ENV_FILE.bak.$TS"

# ==========================================================================
# [6/7] Restart backend + smoke-test
# ==========================================================================
echo ""
echo "═══ [6/7] Restart backend ═══"
if systemctl is-active --quiet rentalhub-backend; then
  systemctl restart rentalhub-backend
  sleep 3
  echo "🔄 rentalhub-backend перезапущено"
else
  echo "⚠️  rentalhub-backend не активний — перевір вручну"
fi

echo ""
echo "🔎 Smoke-test API:"
API_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8001/api/event/health || echo "000")
echo "   /api/event/health → HTTP $API_CODE"
if [ "$API_CODE" != "200" ]; then
  echo "   ❌ Backend не відповідає. Логи: sudo journalctl -u rentalhub-backend -n 50 --no-pager"
fi

# ==========================================================================
# [7/7] Nightly backups cron
# ==========================================================================
echo ""
echo "═══ [7/7] Cron нічні бекапи ═══"
BACKUP_SCRIPT="$REPO_ROOT/deploy/backup_local_db.sh"
if [ -f "$BACKUP_SCRIPT" ]; then
  CRON_FILE="/etc/cron.d/farforrent-backup"
  cat > "$CRON_FILE" <<EOF
# Farforrent local MySQL nightly backup (30-day rotation)
0 3 * * * root bash $BACKUP_SCRIPT >> /var/log/farforrent_backup.log 2>&1
EOF
  chmod 644 "$CRON_FILE"
  echo "✅ Cron: щоночі о 03:00 → $BACKUP_DIR (rotation 30d)"
else
  echo "⚠️  $BACKUP_SCRIPT не існує. Пропускаю."
fi

# ==========================================================================
# Верифікація
# ==========================================================================
echo ""
echo "═══════════════ ✅ РЕЗУЛЬТАТ ═══════════════"
mysql -u "$LOCAL_USER" -p"$LOCAL_PASS" "$CLOUD_RH_DB" -e "
SELECT
  (SELECT COUNT(*) FROM orders)            AS orders,
  (SELECT COUNT(*) FROM products)          AS products,
  (SELECT COUNT(*) FROM client_users)      AS clients;" 2>/dev/null \
  || echo "  (перевір вручну: mysql -u $LOCAL_USER -p $CLOUD_RH_DB)"

echo ""
echo "🎉 Ваш VPS тепер повністю автономний."
echo "   • Backend читає з 127.0.0.1"
echo "   • Cloud вимкнено (можете скасувати тариф на adm.tools MySQL)"
echo "   • Нічні бекапи щодня о 3:00 у $BACKUP_DIR"
echo ""
echo "🔙 ROLLBACK: sudo cp $ENV_FILE.bak.$TS $ENV_FILE && sudo systemctl restart rentalhub-backend"
