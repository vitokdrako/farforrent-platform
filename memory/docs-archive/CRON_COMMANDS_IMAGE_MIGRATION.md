# 🕐 CRON КОМАНДИ ДЛЯ МІГРАЦІЇ ЗОБРАЖЕНЬ

## 1️⃣ Команда для Cron (рекомендована)

### Запускати щодня о 3:00 ночі, мігрувати 200 товарів

```bash
0 3 * * * cd /home/farforre/farforrent.com.ua/rentalhub/backend && /opt/alt/python311/bin/python3.11 migrate_images_from_opencart.py --limit 200 >> /home/farforre/image_migration.log 2>&1
```

**Що робить:**
- `0 3 * * *` - кожного дня о 3:00
- `cd /home/.../backend` - переходить в папку зі скриптом
- `python3.11` - використовує Python 3.11 з хостингу
- `--limit 200` - мігрує 200 товарів за раз
- `>> /home/farforre/image_migration.log` - додає output в лог файл
- `2>&1` - також логує помилки

---

## 2️⃣ Альтернативні варіанти Cron

### Варіант A: Мігрувати 100 товарів кожні 6 годин
```bash
0 */6 * * * cd /home/farforre/farforrent.com.ua/rentalhub/backend && /opt/alt/python311/bin/python3.11 migrate_images_from_opencart.py --limit 100 >> /home/farforre/image_migration.log 2>&1
```

### Варіант B: Мігрувати всі товари один раз на тиждень (неділя о 2:00)
```bash
0 2 * * 0 cd /home/farforre/farforrent.com.ua/rentalhub/backend && /opt/alt/python311/bin/python3.11 migrate_images_from_opencart.py >> /home/farforre/image_migration_full.log 2>&1
```

### Варіант C: Тестовий режим (5 товарів) щодня для перевірки
```bash
0 4 * * * cd /home/farforre/farforrent.com.ua/rentalhub/backend && /opt/alt/python311/bin/python3.11 migrate_images_from_opencart.py --test >> /home/farforre/image_migration_test.log 2>&1
```

---

## 3️⃣ Як додати в Cron на хостингу

### Через панель управління хостингом:
1. Зайдіть в **Розклад задач (cron)**
2. Натисніть **Додати завдання**
3. **Розклад:** `0 3 * * *`
4. **Команда:**
```bash
cd /home/farforre/farforrent.com.ua/rentalhub/backend && /opt/alt/python311/bin/python3.11 migrate_images_from_opencart.py --limit 200 >> /home/farforre/image_migration.log 2>&1
```

---

## 4️⃣ Відстеження процесу (моніторинг)

### A) Дивитись логи в реальному часі
```bash
tail -f /home/farforre/image_migration.log
```

**Виведе:**
```
[03:00:01] INFO: ======================================================================
[03:00:01] INFO: 🖼️  МІГРАЦІЯ ЗОБРАЖЕНЬ З OPENCART → RENTALHUB
[03:00:01] INFO: ======================================================================
[03:00:01] INFO: ✅ Using PRODUCTION path: /home/farforre/.../uploads/products
[03:00:02] INFO: 📊 Fetching products from OpenCart...
[03:00:03] INFO: 📦 Found 200 products with images
[03:00:03] INFO: 
[03:00:03] INFO: [1/200] Product ID: 123
[03:00:03] INFO: 📥 Processing: SKU FI8685 - Тарілка десертна...
[03:00:04] INFO:   ✅ Updated DB: uploads/products/FI8685_1733075432.jpg
...
```

### B) Останні 50 рядків логу
```bash
tail -n 50 /home/farforre/image_migration.log
```

### C) Шукати помилки в логах
```bash
grep "❌" /home/farforre/image_migration.log
grep "ERROR" /home/farforre/image_migration.log
```

### D) Порахувати успішні/failed
```bash
# Скільки успішно мігровано
grep "✅ Updated DB" /home/farforre/image_migration.log | wc -l

# Скільки помилок
grep "❌" /home/farforre/image_migration.log | wc -l
```

### E) Статистика останнього запуску
```bash
tail -n 20 /home/farforre/image_migration.log | grep -A 10 "МІГРАЦІЯ ЗАВЕРШЕНА"
```

---

## 5️⃣ Ручний запуск з логуванням

### Якщо хочете запустити вручну:

```bash
# Перейти в директорію
cd /home/farforre/farforrent.com.ua/rentalhub/backend

# Запустити з логуванням (200 товарів)
/opt/alt/python311/bin/python3.11 migrate_images_from_opencart.py --limit 200 2>&1 | tee -a /home/farforre/image_migration_manual.log
```

**`tee -a`** - показує output в консолі І пише в файл одночасно

### Запуск в фоні:
```bash
nohup /opt/alt/python311/bin/python3.11 migrate_images_from_opencart.py --limit 500 >> /home/farforre/image_migration.log 2>&1 &

# Дізнатись PID процесу
ps aux | grep migrate_images

# Відстежувати прогрес
tail -f /home/farforre/image_migration.log
```

---

## 6️⃣ Корисні команди для моніторингу

### Перевірити чи працює cron
```bash
# Подивитись список cron задач
crontab -l

# Подивитись логи cron (загальні)
tail -f /var/log/cron
```

### Перевірити скільки зображень вже мігровано
```bash
# Порахувати файли
ls -1 /home/farforre/farforrent.com.ua/rentalhub/backend/uploads/products/*.jpg | wc -l

# Перевірити останні додані
ls -lt /home/farforre/.../uploads/products/ | head -20

# Розмір всіх зображень
du -sh /home/farforre/.../uploads/products/
```

### Перевірити в БД
```bash
mysql -h farforre.mysql.tools -u farforre_rentalhub -p farforre_rentalhub -e "
SELECT 
    COUNT(*) as total,
    SUM(CASE WHEN image_url LIKE 'uploads/products/%' THEN 1 ELSE 0 END) as migrated,
    SUM(CASE WHEN image_url NOT LIKE 'uploads/products/%' AND image_url IS NOT NULL THEN 1 ELSE 0 END) as not_migrated
FROM products;
"
```

---

## 7️⃣ Notification при завершенні (опціонально)

### Відправити email коли завершиться:

```bash
0 3 * * * cd /home/farforre/farforrent.com.ua/rentalhub/backend && /opt/alt/python311/bin/python3.11 migrate_images_from_opencart.py --limit 200 >> /home/farforre/image_migration.log 2>&1 && echo "Image migration completed at $(date)" | mail -s "RentalHub Image Migration" your-email@example.com
```

---

## 8️⃣ Rotating логів (щоб не росли безкінечно)

### Автоматичне очищення старих логів:

```bash
# Додати в cron: Очищати логи старші 30 днів кожної неділі
0 1 * * 0 find /home/farforre/image_migration*.log -mtime +30 -delete
```

### Або зберігати тільки останні 1000 рядків:

```bash
# Додати після міграції
0 3 * * * cd /home/farforre/farforrent.com.ua/rentalhub/backend && /opt/alt/python311/bin/python3.11 migrate_images_from_opencart.py --limit 200 >> /home/farforre/image_migration.log 2>&1 && tail -n 1000 /home/farforre/image_migration.log > /home/farforre/image_migration_temp.log && mv /home/farforre/image_migration_temp.log /home/farforre/image_migration.log
```

---

## 9️⃣ Приклад повного workflow

### 1. Додати cron задачу:
```bash
0 3 * * * cd /home/farforre/farforrent.com.ua/rentalhub/backend && /opt/alt/python311/bin/python3.11 migrate_images_from_opencart.py --limit 200 >> /home/farforre/image_migration.log 2>&1
```

### 2. Наступного дня перевірити:
```bash
# Подивитись останній запуск
tail -n 30 /home/farforre/image_migration.log

# Порахувати успішні
grep "✅ Updated DB" /home/farforre/image_migration.log | wc -l

# Чи були помилки?
grep "❌" /home/farforre/image_migration.log | tail -10
```

### 3. Перевірити на сайті:
- Зайти в RentalHub
- Відкрити каталог
- Перевірити чи відображаються фото

---

## 🔟 Troubleshooting

### ❓ Cron не працює?

```bash
# Перевірити чи cron service запущений
sudo systemctl status cron

# Подивитись системні логи
tail -f /var/log/syslog | grep CRON
```

### ❓ Не знаю де Python на хостингу?

```bash
# Знайти Python 3.11
which python3.11
# або
ls -la /opt/alt/python*/bin/python*
```

### ❓ Права доступу?

```bash
# Дати права на виконання скрипту
chmod +x /home/farforre/farforrent.com.ua/rentalhub/backend/migrate_images_from_opencart.py

# Дати права на запис логів
chmod 664 /home/farforre/image_migration.log
```

---

## 📊 Dashboard для моніторингу (одна команда)

```bash
echo "=== IMAGE MIGRATION STATUS ===" && \
echo "📅 Last run: $(tail -n 100 /home/farforre/image_migration.log | grep 'Started:' | tail -1)" && \
echo "✅ Success: $(grep -c '✅ Updated DB' /home/farforre/image_migration.log)" && \
echo "❌ Failed: $(grep -c '❌' /home/farforre/image_migration.log)" && \
echo "📦 Local images: $(ls -1 /home/farforre/farforrent.com.ua/rentalhub/backend/uploads/products/*.{jpg,png,jpeg,webp} 2>/dev/null | wc -l)" && \
echo "💾 Total size: $(du -sh /home/farforre/.../uploads/products/ 2>/dev/null | cut -f1)" && \
echo "=============================="
```

---

**Готово!** Тепер ви можете легко відстежувати процес міграції через логи! 📊
