# MIGRATION VERSIONING — DESIGN

Дизайн-документ. **Код ще не реалізований**, схема БД не змінювалася.
Складено разом із `SCHEMA_GAP.md` (Завдання №7).

---

## 1. Проблема поточного стану

Три незалежні механізми змінюють схему, і жоден не знає про інші:

| Механізм | Де | Веде історію? | Ідемпотентний? |
|---|---|---|---|
| SQL-файли `001`–`011` | `backend/migrations/*.sql` | ні | частково |
| `apply_all_migrations.py` | runner для 005–011 | ні | залежить від файлу |
| Inline DDL в API | `routes/migrations.py` та ~10 роутів | ні | зазвичай `IF NOT EXISTS` |

Наслідки, які вже спостерігаються:

* **немає поняття «версія БД»** — неможливо сказати, що застосовано;
* **порядок не гарантований** — `006` скасовує тригер із `005`, але ніщо не
  забороняє накатити `006` без `005`;
* **різні середовища розходяться** — об'єкт з'являється, лише якщо хтось
  викликав endpoint;
* **немає baseline** — 71 об'єкт існує тільки в production (див. `SCHEMA_GAP.md`).

---

## 2. Таблиця історії

Єдине джерело правди. Створюється сама собою, першою, і сама є частиною
bootstrap-логіки (тому — не міграція).

```sql
CREATE TABLE IF NOT EXISTS schema_migrations (
    version       VARCHAR(32)  NOT NULL,
    name          VARCHAR(255) NOT NULL,
    checksum      CHAR(64)     NOT NULL,           -- SHA-256 тексту міграції
    applied_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    applied_by    VARCHAR(128) NOT NULL,           -- os user / CI job / "stamp"
    execution_ms  INT UNSIGNED NULL,
    success       TINYINT(1)   NOT NULL DEFAULT 1,
    error_message TEXT         NULL,
    PRIMARY KEY (version),
    KEY idx_schema_migrations_applied_at (applied_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

Рішення й причини:

* **`version` як PK, а не autoincrement** — повторний накат неможливий
  фізично, а не «за домовленістю».
* **`checksum`** — виявляє редагування вже застосованої міграції. Це
  найчастіша причина «у мене працює, на проді ні».
* **`VARCHAR(32)` для версії** — вміщує `000_baseline` і майбутні
  `20260905_1200`, якщо колись перейдемо на timestamp-нумерацію.
* **невдалі спроби теж пишуться** (`success=0`) — інакше причина падіння
  зникає разом із процесом.

---

## 3. Формат міграції

```
backend/migrations/<version>_<slug>.sql
```

* `version` — 3 цифри, зростає монотонно; `000` зарезервовано за baseline;
* один файл = одна логічна зміна;
* обов'язковий header-комментар:

```sql
-- migration: 012
-- name: add_order_source_index
-- requires: 000
-- idempotent: yes
-- rollback: DROP INDEX idx_orders_source ON orders;
```

`rollback` — текстом, довідково. Автоматичний rollback DDL у MySQL
неможливий (немає транзакційного DDL), тому обіцяти його не будемо;
реальний відкат — з бекапу.

---

## 4. Ідемпотентність

Кожна міграція мусить безпечно виконуватись двічі — це страховка на випадок,
коли `schema_migrations` втрачено, а схема ні (саме наш сьогоднішній стан).

Дозволені патерни:

```sql
CREATE TABLE IF NOT EXISTS ...;
CREATE INDEX IF NOT EXISTS ...;          -- MySQL 8.0+
DROP TRIGGER IF EXISTS ...;
INSERT ... ON DUPLICATE KEY UPDATE ...;
```

`ADD COLUMN` не має `IF NOT EXISTS` у MySQL, тому — перевірка через
`information_schema` (патерн уже застосований у `001_modify_customers_table.sql`
і працює):

```sql
SET @sql = (SELECT IF(
  (SELECT COUNT(*) FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'orders' AND COLUMN_NAME = 'source') = 0,
  'ALTER TABLE orders ADD COLUMN source VARCHAR(32) NULL',
  'DO 0'));
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;
```

Runner **не** зобов'язаний парсити це — він просто виконує файл. Ідемпотентність
— відповідальність автора міграції, і вона перевіряється в CI (§8).

---

## 5. Визначення поточної версії

```python
def detect_state(conn) -> State:
    if not table_exists(conn, "schema_migrations"):
        if table_exists(conn, "orders"):
            return State.LEGACY_UNTRACKED   # жива БД без історії
        return State.EMPTY                  # чиста MySQL
    return State.TRACKED
```

Три стани, і кожен обробляється по-різному — це ядро дизайну:

| Стан | Ознака | Дія |
|---|---|---|
| `EMPTY` | немає `schema_migrations` і немає `orders` | clean install |
| `LEGACY_UNTRACKED` | немає `schema_migrations`, але є `orders` | **stamp**, без DDL |
| `TRACKED` | є `schema_migrations` | звичайний upgrade |

Помилковий вибір між `EMPTY` і `LEGACY_UNTRACKED` — найнебезпечніший сценарій
(накат baseline на живу БД). Тому перевірка йде по наявності `orders`, а не
по кількості рядків чи змінних середовища.

---

## 6. Сценарії

### 6.1 Clean install (порожня MySQL)

```
1. створити schema_migrations
2. застосувати 000_baseline.sql        ← згенерований 2026-09-05 з live dump
3. застосувати лише APPLICABLE-міграції (§11) по зростанню version
4. записати кожну в schema_migrations; STALE — як skipped, без DDL
```

**Оновлено 2026-09-05.** Крок 2 більше не заблокований: `000_baseline.sql`
згенерований із живого дампа (§11). Перевірку відсутності baseline лишаємо —
вона потрібна для середовищ, куди файл не потрапив:

```python
if state is State.EMPTY and not baseline_exists():
    raise MigrationError(
        "Clean install unavailable: 000_baseline.sql is missing. "
        "See backend/migrations/SCHEMA_GAP.md §7."
    )
```

Крок 3 змінився принципово: **не** «застосувати 001..N». Дві legacy-міграції
звертаються до таблиць, яких у RentalHub-базі не існує, тому на чистій
установці вони впадуть із `Table doesn't exist`. Runner мусить знати список
STALE (§11) і пропускати їх, записуючи як skipped.

### 6.2 Upgrade existing installation (наш production)

```
1. detect_state() -> LEGACY_UNTRACKED
2. створити schema_migrations
3. STAMP: записати 000..011 як applied (applied_by='stamp'), DDL НЕ виконувати
4. STALE-міграції (§11) штампувати як skipped, а не applied
5. далі застосовувати лише 012+
```

Штампування без виконання — принципове рішення. Схема вже містить результат
001–011; повторний накат у найкращому разі нічого не зробить, у гіршому —
впаде на `006` (тригер уже видалено) або зруйнує дані.

Штамп виконується явною командою, ніколи автоматично:

```
python -m migrations.runner --stamp 011
```

### 6.3 Повторний запуск (idempotent rerun)

```
python -m migrations.runner --upgrade
```

* застосовані версії пропускаються за `PRIMARY KEY (version)`;
* checksum кожної застосованої порівнюється з файлом; розбіжність → **stop**
  із переліком змінених файлів (не «warning», бо це означає, що середовища
  вже розійшлися);
* якщо попередній запуск лишив `success=0` — runner відмовляється йти далі,
  доки стан не розібрано вручну.

### 6.4 Dry run

```
python -m migrations.runner --upgrade --dry-run
```

Друкує план (які версії, у якому порядку, який стан визначено) без єдиного
DDL. Обов'язковий крок перед production.

---

## 7. CLI

```
runner --status              # стан + список pending/applied + перевірка checksum
runner --upgrade [--to N]    # застосувати pending
runner --dry-run             # план без виконання
runner --stamp N             # позначити 000..N як applied без DDL
runner --verify              # тільки checksum-перевірка, exit code для CI
```

Місце: `backend/migrations/runner.py`, окремим модулем.
`apply_all_migrations.py` **не видаляється** — залишається до підтвердження,
що новий runner покриває всі середовища.

---

## 8. Перевірка в CI

1. підняти порожню MySQL;
2. `runner --upgrade` → мусить дати повну схему (після появи baseline);
3. `runner --upgrade` ще раз → **0 змін** (доказ ідемпотентності);
4. `runner --verify` → checksum-и цілі;
5. порівняти отриману схему з `baseline_schema.sql` — розбіжність = провал.

Крок 3 — головний: він відловлює неідемпотентні міграції до того, як вони
дійдуть до production.

---

## 9. Взаємодія з migration guard і Module Manager

### 9.0 Визначення «живої» БД (contract для оператора)

Імена production-хостів **не** зберігаються в коді: baseline свідомо чистився
від хоста, тож хардкод у `runner.py` повернув би той самий рядок у Git.
Перелік живих хостів задає оператор:

| Змінна | Призначення |
|--------|-------------|
| `MIGRATION_PRODUCTION_HOSTS` | Кома-розділені фрагменти імен живих хостів. Збіг = відмова від змінюючих команд. |
| `MIGRATION_TARGET_IS_STAGING` | `1/true/yes/on` — оператор явно підтверджує, що віддалена цільова БД не є production. |

**Default навмисно суворий:** будь-який НЕ-локальний хост вважається
production, доки не виставлено `MIGRATION_TARGET_IS_STAGING`. Тому для накату
на віддалений staging знадобиться:

```bash
export MIGRATION_TARGET_IS_STAGING=true
python -m migrations install
```

Причина такого default: guard за списком імен захищає лише від хостів, які
хтось не забув перелічити. Зайва відмова коштує хвилини роботи, помилковий
накат на живу БД — відновлення з бекапу. Локальні цілі (`localhost`,
`127.0.0.1`, `::1`, `0.0.0.0`) працюють без додаткових змінних.

* Runtime-endpoints `/api/migrations/*` (Завдання №3) залишаються закритими
  `ALLOW_RUNTIME_MIGRATIONS` + `X-Migration-Token`. Новий runner — окремий
  CLI-шлях, він **не** відкриває HTTP-доступ до DDL.
* Inline DDL (`SCHEMA_GAP.md` §5) переноситься у версіоновані міграції
  поступово: спершу дублюється як міграція, потім прибирається з роуту.
  Одночасне видалення зламало б середовища, де endpoint ще не викликали.
* Міграції **не** залежать від стану модулів. Вимкнений Finance не означає
  відсутність `fin_*`: схема лишається повною, змінюється лише доступ.
  Інакше вимикання модуля ставало б необоротною втратою даних.

---

## 10. Порядок реалізації

| # | Крок | Статус |
|---|---|---|
| 1 | `runner.py` + `schema_migrations` + `--status`/`--stamp` | не зроблено |
| 2 | Проштампувати production як `011` | блокує доступ до БД |
| 3 | Отримати dump → `000_baseline.sql` | **зроблено 2026-09-05** |
| 4 | CI clean-install тест на порожній MySQL | блокує відсутність MySQL |
| 5 | Перенести inline DDL у міграції | після кроку 4 |

Крок 1 можна робити вже зараз — він не потребує доступу до БД і не змінює
структуру даних.

---

## 11. Результати live dump (2026-09-05)

Baseline згенерований `scripts/extract_baseline.py` з phpMyAdmin-дампа
(75,7 МБ, MySQL 5.7.44). Дамп у Git **не** комітився.

### 11.1 Склад baseline

| Об'єкт | Кількість |
|---|---|
| Таблиці | 64 |
| View (`v_order_finance`) | 1 |
| Тригери | 2 |
| `ALTER TABLE` | 128 |
| PRIMARY KEY | 64 |
| UNIQUE KEY | 24 |
| KEY (index) | 134 |
| FOREIGN KEY | 22 |

Відкинуто: 428 блоків даних, 2 транзакційні інструкції, 8 службових
комментарів заголовка, 3 backup-таблиці (`fin_payments_bk_20260617_1955`,
`fin_transactions_bk_20260617_1955`, `orders_discount_bk_20260617_1955`).

Автоматичні safety-перевірки в екстракторі (усі мусять бути 0): залишкові
`INSERT`, `DEFINER=`, `*_bk_*`, `COMMIT`/`START TRANSACTION`, ім'я
production-хоста. Ненульовий результат — ненульовий exit code.

### 11.2 Чому прибрано `START TRANSACTION` / `COMMIT`

Транзакційними межами володіє runner. Залишений у файлі `COMMIT` тихо
закрив би транзакцію runner-а посередині накату й зламав відкат при збої.

### 11.3 Зіставлення з legacy-міграціями

`scripts/compare_baseline_migrations.py` (read-only) порівнює таблиці, яких
вимагає кожна міграція, зі складом baseline. Результат: 12 узгоджених, 2 STALE.

| Міграція | Відсутня таблиця | Причина |
|---|---|---|
| `001_modify_customers_table.sql` | `customers` | Це таблиця OpenCart (інша БД). У RentalHub її ніколи не було |
| `add_user_tracking.sql` | `finance_transactions` | У production таблиця зветься `fin_transactions`; `finance_transactions` існує лише в ORM-моделі |

Наслідок для §6.2: штамп «000..011 як applied» був би неправдою. `001`
ніколи не застосовувався до цієї БД, і його треба записати як skipped —
інакше checksum-історія фіксує зміну, якої в схемі немає.

Наслідок для коду: `models_sqlalchemy.py:700` оголошує
`__tablename__ = 'finance_transactions'` для таблиці, якої не існує. Модель
не видаляємо в межах цієї задачі, але фіксуємо як розходження ORM↔схема.

`routes/clients.py` звертається до `customers` під `try/except` навколо
`SHOW COLUMNS`, тому відсутність таблиці не є runtime-помилкою: блок legacy
просто не активується.

### 11.4 Що НЕ перевірено

Реальний накат baseline на MySQL не виконувався: у середовищі немає
MySQL/MariaDB, встановлення неможливе (`setgroups: Operation not permitted`).
Отже **не підтверджено**: порядок створення view після таблиць, коректність
тригерів, застосовність усіх 22 FK, поведінка `AUTO_INCREMENT` без
counter-ів. Перевірка структури — лише статична: усі 12 цілей FK присутні,
`ALTER TABLE` без відповідного `CREATE TABLE` немає.

**Baseline не можна вважати перевіреним і не можна застосовувати до жодного
середовища до накату на порожню MySQL 5.7 у staging.**

## 12. Реалізація runner-а (2026-09-06)

Дизайн §2–§10 реалізований у трьох модулях. Production-схема, API-контракти
та ORM-моделі не змінювалися.

| Файл | Роль |
|---|---|
| `migrations/catalog.py` | Пошук файлів, версії, SHA-256, правила skip, MySQL-aware розбиття SQL |
| `migrations/history.py` | DDL `schema_migrations`, статуси, конфіг БД, MySQL-backend |
| `migrations/runner.py` | Команди `status` / `install` / `stamp` / `upgrade` / `verify` |
| `scripts/verify_staging_schema.py` | Read-only порівняння живої БД із baseline |
| `tests/test_migration_runner.py` | 23 тести на in-memory backend |

### 12.1 Що робить runner і чого не робить

`install` — лише на `EMPTY`; на непорожній БД відмова замість накату.
`stamp` — записує `stamped` **без виконання SQL** (`statements_executed = 0`)
і лише в межах запитаного діапазону. `upgrade` — застосовує тільки pending,
fail-fast: перша ж помилка записується як `failed` і зупиняє прогін.
`verify` — читає історію й не змінює нічого. `--dry-run` не виконує жодного
запису, включно з `schema_migrations`.

Повторний накат вже врегульованої версії неможливий фізично: PK по `version`.
Зміна файлу після застосування ловиться checksum-ом і блокує `upgrade`
(тест `test_checksum_mismatch_is_detected_and_blocks_upgrade`). Запис в
історії без файлу на диску також блокує прогін — середовище, де міграцію
видалили з репозиторію, не вважається валідним.

### 12.2 Дві STALE-міграції

`001_modify_customers_table.sql` і `add_user_tracking.sql` позначаються
`skipped` із причиною в `notes`, а не `applied` (§11.3). Тест
`test_stale_migration_would_really_fail_if_it_were_not_skipped` доказує, що
без skip вони справді падають, — правило skip перевірене, а не задеклароване.

`add_user_tracking` не має числового префікса, тому сортується після `011`
і **не** входить у `stamp --to 011`: штамп врегульовує рівно те, що просили.
Файл лишається pending і буде записаний `skipped` на першому `upgrade`
(тест `test_stale_legacy_migration_left_pending_by_stamp_is_skipped_on_upgrade`).

### 12.3 Захист від запуску по production

`looks_like_production()` порівнює host/ім'я БД із production-ознаками.
Без явного `--allow-production` будь-яка команда, що пише, відмовляється
стартувати. Тести не використовують production credentials — вони працюють
на in-memory backend і не відкривають з'єднань.

### 12.4 Staging verification — процедура

`scripts/verify_staging_schema.py` парсить baseline і порівнює очікуване з
`information_schema` живої БД: 64 таблиці, 1 view (саме як view, не як
phpMyAdmin-заглушка), 2 тригери, 22 FK (включно з перевіркою, що FK висить
на правильній таблиці), 222 індекси, 49 `AUTO_INCREMENT`-колонок.

```bash
# порожня MySQL 5.7 у staging
export MIGRATION_DB_HOST=127.0.0.1 MIGRATION_DB_USER=root \
       MIGRATION_DB_PASSWORD=... MIGRATION_DB_NAME=rentalhub_staging

python -m migrations status                 # очікується EMPTY
python -m migrations install --dry-run      # план без запису
python -m migrations install                # baseline + skip двох stale
python scripts/verify_staging_schema.py     # структура vs baseline
python -m migrations upgrade                # має бути no-op
python -m migrations verify                 # історія без failed
```

Критерії приймання: `install` завершується без помилок; verification дає
`RESULT: PASSED`; повторний `upgrade` — no-op; `verify` не показує `failed`.

### 12.5 Що НЕ перевірено (станом на 2026-09-06)

Логіка runner-а перевірена 23 тестами на in-memory backend; розбиття
реального `000_baseline.sql` на інструкції та цілісність тіл тригерів —
перевірені на самому файлі. Але **реальний накат на MySQL так і не
виконувався**: у середовищі немає ні MySQL/MariaDB, ні Docker
(`mysqld`, `mariadbd`, `docker` відсутні; встановлення блокує
`setgroups: Operation not permitted`). Наявний лише клієнтський драйвер
`pymysql` без сервера.

Отже досі **не підтверджено емпірично**: порядок створення view після
таблиць, реальна застосовність усіх 22 FK, коректність тригерів у MySQL,
поведінка `AUTO_INCREMENT` без counter-ів, а також те, що `install`
проходить від початку до кінця на порожній БД.

**Clean install не можна називати перевіреним, а baseline — застосовним,
доки §12.4 не виконано на справжній порожній MySQL 5.7.** Скрипт
verification для цього готовий; бракує лише сервера.