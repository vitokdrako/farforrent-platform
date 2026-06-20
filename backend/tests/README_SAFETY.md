# Testing Safety Guide

## ⚠️ Проблема

Бекенд за замовчуванням з'єднаний з **прод-БД** (`farforre.mysql.tools/farforre_rentalhub`).
Будь-який E2E тест, що створює замовлення через `convert-to-order`,
**забирає реальний auto_increment ID** і конфліктує з OpenCart cron-sync.

## 🛡️ Захист (вже встановлено)

Усі тести в `backend/tests/` тепер імпортують `_safety.assert_not_production()`.
Якщо `RH_DB_HOST = farforre.mysql.tools`, тест **відмовляється запускатись**.

## ✅ Правильні способи запустити E2E тести

### Варіант 1 — на VPS з локальною копією (рекомендовано)

1. Налаштувати періодичний sync (раз на 6 годин):
   ```bash
   sudo crontab -e
   # Додати:
   0 */6 * * * /var/www/farforrent/deploy/cron_refresh_db.sh >> /var/log/rentalhub-db-sync.log 2>&1
   ```
2. У `/var/www/farforrent/backend/.env` додати:
   ```
   LOCAL_DB_HOST=127.0.0.1
   LOCAL_DB_USER=root
   LOCAL_DB_PASS=<your-mysql-password>
   LOCAL_DB_NAME=farforre_rentalhub
   ```
3. Зробити ручний перший sync:
   ```bash
   sudo bash /var/www/farforrent/deploy/cron_refresh_db.sh
   ```
4. Запускати тести з override env:
   ```bash
   cd /var/www/farforrent/backend
   export RH_DB_HOST=127.0.0.1
   export RH_DB_PASSWORD=<local-pass>   # якщо інший від cloud
   python3 tests/test_full_order_cycle.py
   ```

### Варіант 2 — окрема test-DB у тому ж cloud-MySQL

1. У MySQL Tools панелі створити схему `farforre_rentalhub_test`
2. Скопіювати дамп з prod у test:
   ```bash
   mysqldump farforre_rentalhub | mysql farforre_rentalhub_test
   ```
3. У `.env` для тестів:
   ```
   export RH_DB_DATABASE=farforre_rentalhub_test
   python3 tests/test_full_order_cycle.py
   ```
   Захист пропустить, бо ім'я БД у списку `_TEST_DB_NAMES`.

### Варіант 3 — bypass (НЕ рекомендовано)

Якщо ти **впевнений** що знаєш що робиш (наприклад, дрібна перевірка з ручним cleanup):
```bash
python3 tests/test_full_order_cycle.py --i-know-prod
# або
I_KNOW_THIS_IS_PROD=1 python3 tests/test_full_order_cycle.py
```

## 🔄 Перевірка стану cron-sync

```bash
tail -50 /var/log/rentalhub-db-sync.log
ls -lh /var/www/farforrent/db_backups/   # бекапи зберігаються 14 днів
```
