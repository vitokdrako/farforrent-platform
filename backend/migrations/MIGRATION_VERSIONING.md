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

Крок 3 змінився принципово: **не** «застосувати 001..N». Чотири legacy-міграції
не застосовні до цієї схеми — одні звертаються до таблиць, яких у RentalHub-базі
не існує (падіння з `Table doesn't exist`), інші конфліктують із production-
об'єктами (реальне падіння `004` з errno 1215 на MySQL 5.7.44). Runner мусить
знати список STALE (§12.2) і пропускати їх, записуючи як skipped. Міграції,
чий ефект уже є в baseline, отримують `stamped` без DDL (`BASELINE_COVERS`).

### 6.2 Upgrade existing installation (наш production)

```
1. detect_state() -> LEGACY_UNTRACKED
2. створити schema_migrations
3. STAMP: записати 000..011 як stamped (statements_executed=0), DDL НЕ виконувати
4. STALE-міграції (§12.2) записувати як skipped, а не applied/stamped
5. далі застосовувати лише 012+
```

Штампування без виконання — принципове рішення. Схема вже містить результат
001–011; повторний накат у найкращому разі нічого не зробить, у гіршому —
впаде на `006` (тригер уже видалено) або зруйнує дані.

Штамп виконується явною командою, ніколи автоматично:

```
python -m migrations.runner stamp --to 011
```

### 6.3 Повторний запуск (idempotent rerun)

```
python -m migrations.runner upgrade
```

* застосовані версії пропускаються за `PRIMARY KEY (version)`;
* checksum кожної застосованої порівнюється з файлом; розбіжність → **stop**
  із переліком змінених файлів (не «warning», бо це означає, що середовища
  вже розійшлися);
* якщо попередній запуск лишив `success=0` — runner відмовляється йти далі,
  доки стан не розібрано вручну.

### 6.4 Dry run

```
python -m migrations.runner upgrade --dry-run
```

Друкує план (які версії, у якому порядку, який стан визначено) без єдиного
DDL. Обов'язковий крок перед production.

---

## 7. CLI

```
runner status                # стан + список pending/applied + перевірка checksum
runner install               # clean install на порожню БД (baseline + решта)
runner upgrade [--to N]      # застосувати pending
runner upgrade --dry-run     # план без виконання
runner stamp --to N          # позначити 000..N як stamped без DDL
runner verify                # тільки checksum-перевірка, exit code для CI
```

Місце: `backend/migrations/runner.py`, окремим модулем.
`apply_all_migrations.py` **не видаляється** — залишається до підтвердження,
що новий runner покриває всі середовища.

---

## 8. Перевірка в CI

1. підняти порожню MySQL;
2. `runner install` → мусить дати повну схему (baseline + застосовні міграції);
3. `runner upgrade` ще раз → **0 змін** (доказ ідемпотентності);
4. `runner verify` → checksum-и цілі;
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
| 1 | `runner.py` + `schema_migrations` + `status`/`stamp` | **зроблено 2026-09-06** (§12) |
| 2 | Проштампувати production як `011` | **не зроблено** — потребує backup + дозволу (§13.3) |
| 3 | Отримати dump → `000_baseline.sql` | **зроблено 2026-09-05** (§11) |
| 4 | Clean-install тест на порожній MySQL | **зроблено 2026-09-06** на 5.7.44 (§13) |
| 5 | Перенести inline DDL у міграції | не зроблено |

Кроки 1, 3, 4 закриті. Крок 2 свідомо лишається відкритим: штамп production —
одноразова необоротна операція, вона виконується вручну за протоколом §13.3.
Крок 4 виконано локально на portable MySQL 5.7.44; винесення цієї ж
послідовності в CI-джоб — окреме завдання.

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
вимагає кожна міграція, зі складом baseline. Результат на 2026-09-05:
12 узгоджених, 2 STALE. Реальний накат на MySQL 5.7.44 згодом знайшов ще
дві — фінальний перелік із чотирьох див. §12.2, обставини знахідки — §13.1.

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

### 11.4 Статус перевірки baseline

На момент §11 перевірка була **лише статичною** (усі 12 цілей FK присутні,
`ALTER TABLE` без відповідного `CREATE TABLE` немає), бо сервера MySQL у
середовищі не було.

Це обмеження знято — §13. Накат виконано на MySQL 5.7.44 і підтверджено
емпірично те, що раніше було під питанням: порядок створення view після
таблиць, застосовність усіх 22 FK, коректність обох тригерів, поведінка
`AUTO_INCREMENT` без counter-ів. Baseline розгортається на порожню БД від
початку до кінця, verification дає `RESULT: PASSED`.

Межі: перевірено MySQL 5.7.44 і **структуру**, не міграцію даних.
Застосування до production і далі потребує backup, плану відкату й
явного дозволу (§13.3).

## 12. Реалізація runner-а (2026-09-06)

Дизайн §2–§10 реалізований у трьох модулях. Production-схема, API-контракти
та ORM-моделі не змінювалися.

| Файл | Роль |
|---|---|
| `migrations/catalog.py` | Пошук файлів, версії, SHA-256, правила skip, MySQL-aware розбиття SQL |
| `migrations/history.py` | DDL `schema_migrations`, статуси, конфіг БД, MySQL-backend |
| `migrations/runner.py` | Команди `status` / `install` / `stamp` / `upgrade` / `verify` |
| `scripts/verify_staging_schema.py` | Read-only порівняння живої БД із baseline |
| `tests/test_migration_runner.py` | 26 тестів на in-memory backend |

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

### 12.2 Чотири STALE-міграції

Спочатку таких міграцій вважалося дві; накат на справжню MySQL 5.7.44 (§13)
знайшов ще дві. Усі чотири позначаються `skipped` із причиною в `notes`, а не
`applied`:

| Версія | Kind | Чому не запускається |
|---|---|---|
| `001_modify_customers_table` | `incompatible` | `customers` — таблиця OpenCart в іншій БД; у RentalHub її ніколи не було |
| `add_user_tracking` | `obsolete` | цілиться в `finance_transactions`; реальна таблиця — `fin_transactions`, а перша назва існує лише в ORM-моделі |
| `004_create_soft_reservations` | `superseded` | `FOREIGN KEY (board_id) REFERENCES event_boards(board_id)`, але `event_boards` має ключ `id varchar(36)` — MySQL 5.7 відмовляє з errno 1215 (перевірено на 5.7.44); робочу таблицю `event_soft_reservations` уже містить baseline |
| `add_laundry_queue` | `superseded` | `laundry_queue` не читає жоден code path: `routes/laundry.py` реалізує чергу як рядки `tasks` з `task_type='laundry_queue'` |

Тест `test_stale_migration_would_really_fail_if_it_were_not_skipped` доказує,
що без skip міграція справді падає, — правило skip перевірене, а не
задеклароване. Тест
`test_real_repository_catalog_marks_every_stale_migration_with_a_reason`
закріплює `kind` і причину кожного правила, щоб skip не можна було молча
розширити на «незручну» міграцію.

`skipped` і `BASELINE_COVERS` — взаємно виключні твердження про одну міграцію
(«її ефекту в схемі немає» проти «її ефект уже в baseline»); інваріант
перевіряє `test_skipped_migrations_are_never_also_claimed_by_the_baseline`.

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

# CLI — це `migrations.runner`; у пакета немає `__main__.py`
python -m migrations.runner status              # очікується EMPTY
python -m migrations.runner install --dry-run   # план без запису
python -m migrations.runner install             # baseline + stamp/skip legacy
python scripts/verify_staging_schema.py         # структура vs baseline
python -m migrations.runner upgrade             # має бути no-op
python -m migrations.runner verify              # історія без failed
```

Критерії приймання: `install` завершується без помилок; verification дає
`RESULT: PASSED`; повторний `upgrade` — no-op; `verify` не показує `failed`.

### 12.5 Статус верифікації

Розділ §12.5 раніше фіксував, що реального накату не було: у середовищі
не було ні MySQL/MariaDB, ні Docker. Це обмеження знято — див. §13:
portable MySQL 5.7.44 запущено локально й усі сценарії §12.4 виконано
емпірично. Baseline більше не «неперевірений».

## 13. Емпірична верифікація на MySQL 5.7.44 (2026-09-06)

Сервер: portable MySQL **5.7.44**, ізольований datadir, `127.0.0.1:13306`,
`utf8mb4` / `utf8mb4_unicode_ci`. **Production БД не торкалися жодною
командою** — усі прогони на локальних staging-схемах.

### 13.1 Що знайшов реальний накат

Перший `install` упав на `004` із `errno 1215` — саме те, чого не могли
показати in-memory тести. Розбір падіння виявив ще три розходження між
legacy-міграціями та production-baseline і призвів до двох нових правил у
`catalog.py`:

* `BASELINE_COVERS` — міграція, чий ефект уже є в baseline, отримує
  `stamped` замість повторного накату (`002`, `003`, `005`–`011`).
* `SUPERSEDED` — міграція, яку витіснила інша реалізація (`004`,
  `add_laundry_queue`), отримує `skipped` із причиною.

Без цих правил clean install був непрацездатним. Це головний результат
задачі: помилку знайшов сервер, а не рецензія коду.

### 13.2 Виконані сценарії

| # | Сценарій | Результат |
|---|---|---|
| 1 | `status` на порожній БД | `EMPTY`, 15 pending |
| 2 | `install --dry-run` | план без запису; `TABLES_AFTER_DRYRUN: 0` (навіть `schema_migrations` не створено) |
| 3 | `install` на `EMPTY` | 1 applied, 10 stamped, 4 skipped, 0 failed |
| 4 | `verify_staging_schema.py` | `RESULT: PASSED` — 64 таблиці, 1 view, 2 тригери, 22 FK, 222 індекси, `AUTO_INCREMENT` |
| 5 | `v_order_finance` | queryable як справжній view |
| 6 | `upgrade` після install | no-op, 0 pending |
| 7 | повторний `install` на непорожній БД | відмова, схема не змінена |
| 8 | fingerprint між прогонами | стабільний `9a7beeb9…33f21` |
| 9 | `upgrade` на `LEGACY_UNTRACKED` | **відмова** з вимогою спершу `stamp` |
| 10 | `stamp --to 011` (adoption) | 10 stamped, 2 skipped; 64 таблиці **без змін**, 0 виконаних SQL-інструкцій |
| 11 | повторний `stamp` | no-op: 12 рядків історії, 0 виконаних інструкцій |
| 12 | verification adopted-БД | `RESULT: PASSED` |
| 13 | checksum mismatch (правка застосованого файлу) | `verify` і `upgrade` відмовляють; після відкату файлу — `OK` |
| 14 | збій посеред `upgrade` | `012` applied, `013` `failed` з текстом помилки, `014` **не пробувався** |
| 15 | `upgrade` після збою | заблоковано, доки `failed`-рядок не прибрано вручну |

Ключове для adoption: `stamp` на legacy-БД не створив ні `soft_reservations`,
ні `laundry_queue`, залишив 2 тригери й 64 таблиці незмінними, а всі рядки
історії мають `statements_executed = 0`. Це доказ, що штамп визнає схему, а
не переписує її.

### 13.3 Межі верифікації

Перевірено MySQL **5.7.44**; на 8.x накат не запускався. Baseline
перевірений як **структура** — дані не мігрувалися й не порівнювалися.
Тестові схеми (`adopt_db`, `fail_db`) створювалися з того самого baseline,
тому це перевірка runner-а на production-*структурі*, а не на копії
production-*даних*.

Прогони №13–15 навмисно псували стан, тому виконувалися на окремій
`fail_db`; файли міграцій після них відновлені байт-у-байт (`diff -r` чистий),
пробні `012`–`014` видалені.

**Stamping production досі заборонено** без свіжого backup, перевіреного
плану відкату й явного дозволу — емпірична перевірка на staging знімає
питання про працездатність runner-а, але не замінює дозвіл на дію з живою БД.

---

## 14. Production Schema Adoption Audit (Завдання №10, 2026-09-06)

Мета — довести, що baseline відповідає **справжній** production-схемі, і що
`stamp --to 011` на ній не виконає жодного DDL. **Production БД не
контактували**: усе перевірено на снапшоті, відновленому з read-only дампа
`uploads/farforre_rentalhub.sql` у локальні `audit_*` схеми.

### 14.1 Порівняння baseline ↔ production (`scripts/compare_production_schema.py`)

Скрипт парсить сирий дамп **незалежно** від `extract_baseline.py`, піднімає
production-снапшот і baseline у дві окремі БД і порівнює їх через
`information_schema`.

| Об'єкт | Production | Baseline | Розходження |
|---|---|---|---|
| Таблиці | 67 | 64 | 3 (див. §14.2) |
| Колонки | 869 | 830 | лише колонки 3 зайвих таблиць |
| Типи / `NULL` / дефолти | — | — | **0** |
| Індекси | — | — | **0** |
| Foreign keys (+ `ON DELETE`/`ON UPDATE`) | 22 | 22 | **0** |
| Views | 1 | 1 | **0** |
| Triggers | 2 | 2 | **0** |

Серед об'єктів, які baseline декларує, розходжень немає жодного.

### 14.2 Три зайві таблиці — операційні артефакти, не контракт

* `fin_payments_bk_20260617_1955`
* `fin_transactions_bk_20260617_1955`
* `orders_discount_bk_20260617_1955`

Це ручні backup-копії, зроблені оператором 2026-06-17. Вони **навмисно не
входять** у baseline: їх не створює жодна міграція, на них не посилається код,
і clean install не має їх відтворювати. Baseline описує схему застосунку, а не
знімок операційних копій. Видаляти їх у production runner не буде — вони
просто поза його контрактом.

### 14.3 Перевірка skip-правил по реальній схемі

Кожне правило з `catalog.py` підтверджене відсутністю/наявністю об'єкта в
production-снапшоті, а не лише читанням коду:

| Міграція | Твердження | Факт у production |
|---|---|---|
| `001` | `customers` не в цій БД | таблиці немає (OpenCart) |
| `004` | ставка на `soft_reservations` | таблиці немає; `event_boards` має PK `id`, а не `board_id`; реальна — `event_soft_reservations` |
| `add_user_tracking` | цілить у `finance_transactions` | таблиці немає; реальна — `fin_transactions`, колонки `created_by_id` немає |
| `add_laundry_queue` | `laundry_queue` не використовується | таблиці немає; працюють `tasks`/`laundry_batches`/`laundry_items` |

### 14.4 Доказ нульового DDL (`scripts/verify_stamp_no_ddl.py`)

Скрипт клонує production-снапшот, знімає повний зліпок схеми, виконує
**справжній** `stamp --to 011` і порівнює зліпки до/після.

* до і після: **67 таблиць, 869 колонок, 244 частини індексів, 22 FK, 1 view, 2 тригери** — ідентично;
* записано 12 рядків історії, `statements_executed = 0` у кожному;
* єдина змінена таблиця — `schema_migrations`;
* stamped: `000`, `002`, `003`, `005`–`011`; skipped: `001`, `004`.

### 14.5 Знайдений і виправлений дефект: хибний `applied` після штампу

Аудит виявив реальний баг, а не лише підтвердив очікуване. `stamp --to 011`
закриває версії **до свого cutoff**, тому baseline-covered міграція з іменем,
що сортується після нього — `create_product_damage_history` — залишалася
`pending`, і наступний `upgrade` планував для неї **`apply`**.

Її SQL — `CREATE TABLE IF NOT EXISTS`, а `product_damage_history` у production
вже є. Тобто накат «успішно» не зробив би нічого, але історія записала б
`applied` для зміни, якої не відбулося — саме той клас брехні, який цей runner
має унеможливлювати (пор. §13.1).

Виправлення: `plan_upgrade()` тепер перевіряє `BASELINE_COVERS` і для таких
версій планує `stamp`, але **лише** якщо об'єкти справді спостережні в схемі;
якщо їх немає — залишає `apply` і пише в `reason`, чого саме бракує. Adoption
керується фактом, а не декларацією.

Перевірено на клоні production-снапшоту: план змінився з `apply` на `stamp`,
реальний `upgrade` виконав 0 інструкцій, схема (68 таблиць, 869 колонок,
однаковий fingerprint) не змінилася, рядків зі статусом `applied` — 0.
Закрито двома регресійними тестами: `..._is_stamped_not_applied` і
`..._absent_from_the_schema_is_still_applied`.

### 14.6 Стан тестів

`28 passed` (migration runner, +2 нових) та `19 passed` (security),
`py_compile` чистий.

### 14.7 Що лишилося — окремий крок із дозволом

Виконано на відновленій копії production-дампа — див. §15. На **живому**
production `stamp --to 011` досі **не виконано**: не було ні доступу, ні
credentials. Умови запуску незмінні й обов'язкові всі разом: свіжий backup
production, явний дозвіл людини, перевірений план відкату, фінальне
підтвердження підключення та ідентичності цілі (`status` мусить показати
`LEGACY_UNTRACKED` і очікуваний fingerprint). Не перевірено досі: MySQL 8.x і
міграція реальних **даних** (перевірялася структура).

## 15. Операція `stamp --to 011` на копії production-дампа (2026-09-06)

Джерело істини: `/workspace/uploads/farforre_rentalhub.sql`,
SHA-256 `506a79c7258dde6dbd7f2f8cd33cc6b10a49f252198aa815e055f2c34d4e752b`.
Дамп відновлено двічі на MySQL 5.7.44 (`127.0.0.1:13306`):
`prod_snapshot` — недоторканий еталон для перехресного порівняння,
`stamp_target` — ціль операції. Живий production не контактувався.

### 15.1 Стан ДО

| Параметр | Значення |
|---|---|
| state | `LEGACY_UNTRACKED` |
| fingerprint | `f4a34636893a2de242fbc681b37fa1334a2533c5a5fabc72995dc8c7a12c0ccc` |
| `schema_migrations` | відсутня |
| pending | 15 |
| таблиці / колонки | 67 / 869 |
| view / тригери / FK / індекси | 1 / 2 / 22 / 222 |

### 15.2 Dry-run перед записом

План: 10 `stamp`, 2 `skip` (001 incompatible, 004 superseded), жодного
`blocked` чи `unverifiable`. Після dry-run `schema_migrations` не створено,
таблиць залишилось 67 — тобто сухий прогін дійсно нічого не пише.

### 15.3 Реальна операція

`stamp --to 011` (без `upgrade`), exit code `0`:

- `STAMPED 10`, `skipped 2`, `applied 0`;
- state перейшов `LEGACY_UNTRACKED` → `TRACKED`;
- `pending 3` (`add_laundry_queue`, `add_user_tracking` — будуть skip;
  `create_product_damage_history` — залишено свідомо, поза межею `--to 011`);
- `failed 0`, `checksum mismatch 0`, `schema mismatch 0`.

### 15.4 Доказ нульового DDL

Прямий запит до історії: `total_rows: 12`, `status_applied: 0`,
`total_statements_executed: 0` — по кожному з 12 рядків `stmts=0`. Жодна
міграція не виконала SQL; штамп лишився суто обліковим записом.

### 15.5 Доказ незмінності схеми

Побудовано побайтові знімки ДО і ПІСЛЯ (колонки з типами, nullability,
defaults, extra; індекси з порядком і унікальністю; FK; тригери; таблиці):

| Зріз | diff (before → after) |
|---|---|
| columns | 0 |
| indexes | 0 |
| fks | 0 |
| triggers | 0 |
| tables | 0 |

Fingerprint не змінився: `f4a34636…` до і після. Незалежна перехресна
перевірка проти недоторканого `prod_snapshot` теж дала `0` розбіжностей по
columns / indexes / tables. Єдиний новий об'єкт у `stamp_target` —
`schema_migrations`; жодного об'єкта не втрачено (`only_in_prod_snapshot:
(none)`).

### 15.6 Пост-перевірки

`runner verify` — exit `0`, `OK`. Тести: `28 passed` (migration runner),
`19 passed` (security). `py_compile` по `runner.py`, `catalog.py`,
`history.py` — чистий. `upgrade` не запускався: `create_product_damage_history`
у таблиці історії відсутній (`0` рядків).

### 15.7 Висновок

Операція `stamp --to 011` на реальній production-схемі безпечна й
відтворювана: вона не змінює структуру, не виконує DDL і не чіпає дані. Для
живого production процедура готова, але потребує окремого запуску з backup,
credentials і фінальним підтвердженням цілі за §9.0.