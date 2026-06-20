# RentalHub Migrations Guide

## 📁 Що в `migrations/`

| File | Що робить |
|------|-----------|
| `005_fix_fin_triggers_recursion.sql` | Виправляє error 1442 у тригерах fin_payments — БЕЗ нього не зберігаються платежі/списання |
| `006_drop_fin_transactions_after_insert.sql` | Прибирає циркулярний тригер для запобігання дублікатів |
| `007_event_favorites.sql` | Створює `event_favorites` (♡ Обране) |
| `008_push_subscriptions.sql` | Створює `push_subscriptions` (Web Push) |
| `009_order_chat.sql` | Створює `order_chat_messages` (чат менеджер↔клієнт) |
| `010_document_signatures.sql` | Створює `document_signatures` (підписи + inline approval) |
| `011_company_profiles.sql` | Створює `company_profiles` + 2 колонки в `orders` (наші юр.особи) |

## 🚀 Як застосувати ВСІ міграції на VPS

### Передумова
У `/var/www/farforrent/backend/.env` повинні бути:
```
# Cloud (вже є)
RH_DB_HOST=farforre.mysql.tools
RH_DB_USERNAME=...
RH_DB_PASSWORD=...
RH_DB_DATABASE=farforre_rentalhub

# Local VPS MySQL (додати):
LOCAL_DB_HOST=127.0.0.1
LOCAL_DB_USER=root
LOCAL_DB_PASS=<your-root-pass>
LOCAL_DB_NAME=farforre_rentalhub
```

### Команди

```bash
cd /var/www/farforrent/backend

# 1. Перевірити що буде запущено (dry-run, нічого не змінює):
python3 apply_all_migrations.py --target=local --dry-run

# 2. Застосувати всі міграції з автоматичним бекапом:
python3 apply_all_migrations.py --target=local

# 3. (Опціонально) Якщо потрібна data migration return_cards:
python3 apply_all_migrations.py --target=local --include-data-migration

# 4. Перезапустити backend:
sudo systemctl restart rentalhub-backend
```

### Що відбувається покроково

1. ✅ **Бекап** локальної БД у `/var/www/farforrent/db_backups/pre_migration_*.sql.gz`
2. ✅ Послідовний запуск 005 → 011
3. ✅ **Ідемпотентність**: помилки "уже існує" (codes 1050, 1060, 1061, 1146 тощо) **ігноруються**
4. ❌ Інші помилки → **fail-fast**, скрипт зупиняється на проблемі (наступні міграції не виконуються)
5. 📊 Підсумкова статистика "які таблиці тепер є"

## 🔄 Безпека

- ❌ Жодна міграція **НЕ** видаляє існуючі таблиці чи дані
- ❌ Жодна міграція **НЕ** робить `TRUNCATE` / `DELETE`
- ✅ Всі `CREATE TABLE` мають `IF NOT EXISTS`
- ✅ Всі `ALTER TABLE ADD COLUMN` обгорнуті в pre-check (через скрипт)
- ✅ Тригери: `DROP TRIGGER IF EXISTS` + `CREATE` — заміна, не накопичення
- ✅ Бекап на старті — у разі чого `gunzip -c backup.sql.gz | mysql -u root db`

## 🚨 Якщо щось пішло не так

```bash
# Список бекапів
ls -lh /var/www/farforrent/db_backups/

# Відновити з останнього бекапу
gunzip -c /var/www/farforrent/db_backups/pre_migration_*.sql.gz \
    | mysql -u root -p farforre_rentalhub

# Подивитися логи backend
sudo journalctl -u rentalhub-backend -n 50 --no-pager
```

## 🌐 Запуск на cloud (не рекомендовано)

Cloud вже синхронна (всі міграції застосовано в Emergent-сесіях). Але якщо хочеш переконатися:

```bash
python3 apply_all_migrations.py --target=cloud --no-backup --dry-run
```

Перевірить що все на місці без жодних змін.
