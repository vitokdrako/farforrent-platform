#!/bin/bash
# ============================================================================
# Нічний бекап локальної MySQL. Викликається з /etc/cron.d/farforrent-backup
# Rotation: 30 днів. Записує у /var/backups/mysql/.
# ============================================================================
set -euo pipefail

BACKUP_DIR="/var/backups/mysql"
RETENTION_DAYS=30
TS=$(date +%Y%m%d_%H%M%S)

mkdir -p "$BACKUP_DIR"

for DB in farforre_rentalhub farforre_db; do
  # Пропускаємо якщо БД не існує
  if ! mysql -e "USE \`$DB\`;" 2>/dev/null; then
    echo "⚠️  БД $DB не існує — пропускаю"
    continue
  fi
  FILE="$BACKUP_DIR/${DB}_${TS}.sql.gz"
  echo "📦 Backup $DB → $FILE"
  mysqldump \
    --single-transaction --quick --routines --triggers --events \
    "$DB" | gzip > "$FILE"
  SIZE=$(du -h "$FILE" | cut -f1)
  echo "   ✓ $SIZE"
done

# Видаляємо файли старші за $RETENTION_DAYS днів
echo "🧹 Видаляю бекапи старші за $RETENTION_DAYS днів…"
find "$BACKUP_DIR" -name "*.sql.gz" -mtime +$RETENTION_DAYS -print -delete

TOTAL=$(du -sh "$BACKUP_DIR" | cut -f1)
echo "✅ Готово. Загальний розмір $BACKUP_DIR: $TOTAL"
