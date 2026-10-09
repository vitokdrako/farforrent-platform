# 🌙 ПОВНА МІГРАЦІЯ ВСІХ ЗОБРАЖЕНЬ (БЕЗ ЛІМІТУ)

## ✅ КОМАНДА ДЛЯ CRON - МІГРУВАТИ ВСІ ТОВАРИ

```bash
0 3 * * * cd /home/farforre/farforrent.com.ua/rentalhub/backend && /opt/alt/python311/bin/python3.11 migrate_images_from_opencart.py >> /home/farforre/image_migration.log 2>&1
```

**Запускається:** Щодня о 3:00 ночі  
**Мігрує:** ВСІ товари (без ліміту)  
**Логи:** `/home/farforre/image_migration.log`

---

## 🚀 АБО ЗАПУСТИТИ ВРУЧНУ ПРЯМО ЗАРАЗ

### Якщо хочете запустити зараз (в фоні):

```bash
cd /home/farforre/farforrent.com.ua/rentalhub/backend

nohup /opt/alt/python311/bin/python3.11 migrate_images_from_opencart.py >> /home/farforre/image_migration.log 2>&1 &

echo "✅ Міграція запущена в фоні! PID: $!"
```

**Після запуску відразу можете закрити термінал - скрипт продовжить працювати.**

---

## 📊 ВІДСТЕЖИТИ ПРОГРЕС

### Дивитись в реальному часі:
```bash
tail -f /home/farforre/image_migration.log
```

**Побачите:**
```
[03:00:03] INFO: 📦 Found 6523 products with images

[1/6523] Product ID: 123
📥 Processing: SKU FI8685 - Тарілка десертна...
  ✅ Updated DB: uploads/products/FI8685_1733075432.jpg

[2/6523] Product ID: 124
📥 Processing: SKU FI8686 - Чашка чайна...
  ✅ Updated DB: uploads/products/FI8686_1733075445.jpg
...
```

### Швидка статистика:
```bash
# Скільки вже мігровано
grep -c "✅ Updated DB" /home/farforre/image_migration.log

# Скільки помилок
grep -c "❌" /home/farforre/image_migration.log

# Останні 20 рядків
tail -n 20 /home/farforre/image_migration.log
```

### Перевірити чи ще працює:
```bash
ps aux | grep migrate_images_from_opencart
```

Якщо побачите процес - значить ще працює.

---

## ⏱️ СКІЛЬКИ ТРИВАТИМЕ?

**Приблизні розрахунки:**

- **Швидкість:** ~0.3-0.5 секунди на товар
- **6500 товарів:** ~30-50 хвилин

**Але може бути довше якщо:**
- Повільний інтернет
- Великі зображення
- Проблеми з деякими фото (retry 3 рази)

**Реально:** 1-2 години для 6500 товарів з усіма помилками та retry.

---

## 🔍 DASHBOARD ДЛЯ МОНІТОРИНГУ

```bash
watch -n 10 'echo "=== МІГРАЦІЯ ЗОБРАЖЕНЬ ===" && \
echo "⏰ Час: $(date +%H:%M:%S)" && \
echo "✅ Мігровано: $(grep -c "✅ Updated DB" /home/farforre/image_migration.log)" && \
echo "❌ Помилки: $(grep -c "❌" /home/farforre/image_migration.log)" && \
echo "📦 Файлів на диску: $(ls -1 /home/farforre/farforrent.com.ua/rentalhub/backend/uploads/products/*.{jpg,png,jpeg,webp} 2>/dev/null | wc -l)" && \
echo "💾 Розмір: $(du -sh /home/farforre/farforrent.com.ua/rentalhub/backend/uploads/products/ 2>/dev/null | cut -f1)" && \
tail -n 3 /home/farforre/image_migration.log'
```

**Це оновлюватиме статистику кожні 10 секунд автоматично!**

Натисніть `Ctrl+C` щоб вийти з моніторингу.

---

## ⚠️ ЯКЩО ПОТРІБНО ЗУПИНИТИ

```bash
# Знайти процес
ps aux | grep migrate_images_from_opencart

# Зупинити (замініть PID)
kill <PID>

# Або швидко:
pkill -f migrate_images_from_opencart
```

**Не хвилюйтесь!** Можна запустити знову - скрипт пропустить вже мігровані товари.

---

## 📧 EMAIL ПРИ ЗАВЕРШЕННІ (ОПЦІОНАЛЬНО)

Якщо хочете отримати email коли завершиться:

```bash
0 3 * * * cd /home/farforre/farforrent.com.ua/rentalhub/backend && /opt/alt/python311/bin/python3.11 migrate_images_from_opencart.py >> /home/farforre/image_migration.log 2>&1 && mail -s "✅ Image Migration Complete" your-email@example.com < /home/farforre/image_migration.log
```

---

## ✅ ПІСЛЯ ЗАВЕРШЕННЯ

### 1. Перевірити фінальну статистику:

```bash
tail -n 30 /home/farforre/image_migration.log
```

**Побачите:**
```
======================================================================
✅ МІГРАЦІЯ ЗАВЕРШЕНА
======================================================================
📊 Всього товарів:     6523
✅ Успішно:            6489
❌ Помилки:            34
⏱️  Тривалість:        3245.8s (54.1 хв)
📈 Середній час/товар: 0.50s
======================================================================
```

### 2. Перевірити скільки місця зайняло:

```bash
du -sh /home/farforre/farforrent.com.ua/rentalhub/backend/uploads/products/
du -sh /home/farforre/farforrent.com.ua/rentalhub/backend/uploads/products/thumbnails/
du -sh /home/farforre/farforrent.com.ua/rentalhub/backend/uploads/products/medium/
```

### 3. Перевірити в БД:

```bash
mysql -h farforre.mysql.tools -u farforre_rentalhub -p -e "
SELECT 
    COUNT(*) as total_products,
    SUM(CASE WHEN image_url LIKE 'uploads/products/%' THEN 1 ELSE 0 END) as local_images,
    SUM(CASE WHEN image_url NOT LIKE 'uploads/products/%' AND image_url IS NOT NULL THEN 1 ELSE 0 END) as external_images
FROM farforre_rentalhub.products;
"
```

### 4. Перевірити на сайті:

Зайти на `https://rentalhub.farforrent.com.ua` → Каталог → Перевірити фото

---

## 🎯 РЕКОМЕНДАЦІЯ

### Для першого запуску:

**Варіант 1: Запустити вручну зараз (в фоні)**
```bash
cd /home/farforre/farforrent.com.ua/rentalhub/backend
nohup /opt/alt/python311/bin/python3.11 migrate_images_from_opencart.py >> /home/farforre/image_migration.log 2>&1 &
```

Це мігрує ВСІ товари прямо зараз. Можете закрити термінал.

**Варіант 2: Додати в cron на завтра о 3:00**
```bash
0 3 * * * cd /home/farforre/farforrent.com.ua/rentalhub/backend && /opt/alt/python311/bin/python3.11 migrate_images_from_opencart.py >> /home/farforre/image_migration.log 2>&1
```

---

## 💡 ПОРАДА

Після першої повної міграції, скрипт при наступних запусках буде:
- Пропускати вже мігровані товари
- Мігрувати тільки нові товари
- Працювати дуже швидко (~5-10 хвилин на день)

Тому можна сміливо додавати в cron - він не буде перемігровувати все заново!

---

**Готово! Запускайте на всю ніч! 🌙**
