#!/bin/bash
# Скрипт для перевірки прогресу міграції

echo "=== 📊 ПРОГРЕС МІГРАЦІЇ ЗОБРАЖЕНЬ ==="
echo ""

# Перевірити чи працює процес
if pgrep -f migrate_images.py > /dev/null; then
    echo "✅ Процес міграції ПРАЦЮЄ"
    echo "   PID: $(pgrep -f migrate_images.py)"
else
    echo "⏸️  Процес міграції НЕ ПРАЦЮЄ"
fi

echo ""

# Статистика файлів
echo "🗂️ Файли на диску:"
FILE_COUNT=$(find /app/backend/static/images/products -type f 2>/dev/null | wc -l)
echo "   Кількість: $FILE_COUNT файлів"

DISK_SIZE=$(du -sh /app/backend/static/images/products 2>/dev/null | cut -f1)
echo "   Розмір: $DISK_SIZE"

echo ""

# Останні рядки логу
if [ -f /tmp/migration_4200.log ]; then
    echo "📝 Останні 10 рядків логу:"
    tail -10 /tmp/migration_4200.log | grep -E "^\[|✅|❌|📊"
fi

echo ""

# База даних
python3 << 'PYEOF'
import pymysql

try:
    conn = pymysql.connect(
        host='farforre.mysql.tools',
        user='farforre_rentalhub',
        password='-nu+3Gp54L',
        database='farforre_rentalhub',
        charset='utf8mb4'
    )
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM products WHERE image_url LIKE 'static/%'")
    migrated = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM products WHERE image_url IS NOT NULL AND image_url != ''")
    total = cursor.fetchone()[0]
    
    percent = (migrated * 100 / total) if total > 0 else 0
    
    print("💾 База даних:")
    print(f"   Мігровано: {migrated} / {total} ({percent:.1f}%)")
    
    cursor.close()
    conn.close()
except Exception as e:
    print(f"⚠️  Помилка з'єднання з БД: {e}")
PYEOF

echo ""
echo "=== Команди для управління ==="
echo "Запустити міграцію:"
echo "  cd /app/backend && nohup python3 scripts/migrate_images.py --limit 1200 > /tmp/migration_4200.log 2>&1 &"
echo ""
echo "Зупинити міграцію:"
echo "  pkill -f migrate_images.py"
echo ""
echo "Дивитись лог в реальному часі:"
echo "  tail -f /tmp/migration_4200.log"
