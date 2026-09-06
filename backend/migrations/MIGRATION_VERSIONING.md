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
2. застосувати 000_baseline.sql        ← поки НЕ існує, див. SCHEMA_GAP.md §7
3. застосувати 001..N по зростанню version
4. записати кожну в schema_migrations
```

Наразі крок 2 неможливий: 71 об'єкт відсутній у Git. Тому clean install
**заблокований** до отримання дампу — і runner мусить сказати це прямо, а не
впасти на середині з `Table 'orders' doesn't exist`:

```python
if state is State.EMPTY and not baseline_exists():
    raise MigrationError(
        "Clean install unavailable: 000_baseline.sql is missing. "
        "See backend/migrations/SCHEMA_GAP.md §7."
    )
```

### 6.2 Upgrade existing installation (наш production)

```
1. detect_state() -> LEGACY_UNTRACKED
2. створити schema_migrations
3. STAMP: записати 000..011 як applied (applied_by='stamp'), DDL НЕ виконувати
4. далі застосовувати лише 012+
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

| # | Крок | Блокер |
|---|---|---|
| 1 | `runner.py` + `schema_migrations` + `--status`/`--stamp` | немає |
| 2 | Проштампувати production як `011` | доступ до БД |
| 3 | Отримати dump → `000_baseline.sql` | доступ до БД |
| 4 | CI clean-install тест | крок 3 |
| 5 | Перенести inline DDL у міграції | крок 4 |

Кроки 1 і 2 можна робити вже зараз — вони не потребують baseline і не
змінюють структуру даних.