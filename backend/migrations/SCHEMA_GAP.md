# SCHEMA GAP REPORT

Автоматично зібрано `backend/scripts/schema_inventory.py` (read-only статичний
аналіз репозиторію), перевірено вручну. **Production schema не змінювалася.**

Дата: 2026-09-05
Джерело: тільки Git-репозиторій.

> **ОНОВЛЕНО 2026-09-05 (після отримання live dump).** Цифри нижче описують
> стан **Git-репозиторію**, і в цій ролі залишаються чинними. Але GAP більше
> не є невідомістю: схему production отримано з дампа й зафіксовано в
> `000_baseline.sql` (64 таблиці, 1 view, 2 тригери, 22 FK). Тобто «71
> відсутній об'єкт» тепер закриті baseline-ом, а не кодом.
>
> Дві важливі поправки, які дамп вніс у попередні висновки:
>
> * таблиці `customers` у RentalHub-базі **не існує** — це об'єкт OpenCart,
>   тому `001_modify_customers_table.sql` до цієї БД ніколи не застосовувався;
> * таблиці `finance_transactions` **не існує** — у production вона зветься
>   `fin_transactions`, а `finance_transactions` живе лише в ORM-моделі
>   (`models_sqlalchemy.py:700`) і в `add_user_tracking.sql`.
>
> Деталі та наслідки для штампування — `MIGRATION_VERSIONING.md` §11.

---

## 1. Метод

Сканер аналізує:

* `*.sql` у `backend/migrations/` — повний текст;
* `*.py` — **лише SQL-літерали**, витягнуті через AST (не regex по всьому файлу),
  тому коментарі та python-код не дають хибних співпадінь;
* вкладений SQL: `001_modify_customers_table.sql` тримає `ALTER TABLE` /
  `CREATE INDEX` всередині рядка для динамічного `PREPARE`. Такі літерали
  розкриваються рекурсивно, інакше інвентар втратив би реальні об'єкти;
* `__tablename__` у SQLAlchemy-моделях.

Обмеження методу, які треба знати при читанні цифр:

* назви таблиць, зібрані динамічно (f-string, конкатенація), могли не потрапити;
* повний перелік **foreign keys поза `CREATE TABLE`** не зібраний — див. §6;
* «є в репозиторії» означає «є `CREATE`-інструкція», а **не** «структура
  співпадає з production».

---

## 2. Підсумок

| Категорія | Кількість |
|---|---|
| Об'єкти, створювані з репозиторію | **46** |
| — tables | 36 |
| — views | 1 |
| — triggers | 2 |
| — standalone indexes | 7 |
| ORM-моделі (`__tablename__`) | 33 |
| **GAP — використовуються, але `CREATE` відсутній** | **71** |
| OpenCart external (`oc_*`, чужа БД) | 12 |

**Головний висновок:** репозиторій **не містить** повної схеми. Відсутні не
периферійні, а базові таблиці — `orders`, `products`, `users`, `documents`,
усі `fin_*`. Тому `000_initial.sql` **не створено**: будь-який його варіант був
би вигаданим, а не відтвореним.

---

## 3. KNOWN FROM REPOSITORY

Ці об'єкти можна створити з наявного коду.

### 3.1 Tables (36)

| Таблиця | Джерело `CREATE` | Залежить від |
|---|---|---|
| `cash_summaries` | `routes/finance.py` | — |
| `client_payer_links` | `routes/migrations.py` | `client_users`, `payer_profiles` |
| `client_users` | `routes/migrations.py` | — |
| `company_profiles` | `011_company_profiles.sql` | — |
| `damage_case_archive` | `routes/product_damage_history.py` | — |
| `document_emails` | `routes/migrations.py` | — |
| `document_signatures` | `010_document_signatures.sql`, `routes/migrations.py` | — |
| `document_templates` | `routes/admin.py` | — |
| `event_board_items` | `003_create_event_board_items.sql`, `routes/event_tool.py` | `event_boards`, **`products`** |
| `event_boards` | `002_create_event_boards.sql`, `routes/event_tool.py` | **`customers`** |
| `event_customers` | `routes/event_tool.py` | — |
| `event_favorites` | `007_event_favorites.sql` | — |
| `event_soft_reservations` | `routes/event_tool.py` | — |
| `fin_vendors` | `routes/finance.py` | — |
| `hr_payroll` | `routes/finance.py` | — |
| `laundry_queue` | `add_laundry_queue.sql` | **`laundry_batches`** |
| `master_agreements` | `routes/migrations.py` | `payer_profiles` |
| `monthly_reports` | `routes/finance.py` | — |
| `order_annexes` | `routes/migrations.py` | **`orders`**, `master_agreements` |
| `order_chat_messages` | `009_order_chat.sql` | — |
| `order_extensions` | `routes/partial_returns.py` | — |
| `order_item_packing` | `add_user_tracking.sql` | **`orders`** |
| `order_modifications` | `routes/order_modifications.py` | — |
| `order_section_versions` | `scripts/create_order_versions_table.py` | — |
| `partial_return_log` | `routes/partial_returns.py` | — |
| `partial_return_version_items` | `routes/return_versions.py` | `partial_return_versions` |
| `partial_return_versions` | `routes/return_versions.py` | — |
| `payer_profiles` | `routes/migrations.py`, `routes/payer_profiles.py` | — |
| `processing_queue` | `routes/inventory.py` | — |
| `product_damage_history` | `create_product_damage_history.sql`, `routes/product_damage_history.py` | **`products`** |
| `product_hashtags_dict` | `routes/migrations.py` | — |
| `product_reservations` | `routes/product_reservations.py` | **`orders`** |
| `push_subscriptions` | `008_push_subscriptions.sql` | — |
| `rh_employees` | `routes/finance.py` | — |
| `soft_reservations` | `004_create_soft_reservations.sql` | `event_boards`, **`products`** |
| `system_settings` | `routes/admin.py` | — |

Виділені жирним залежності — це **посилання на таблиці з GAP**. Тобто навіть
«відомі» таблиці не створюються на порожній БД: FK впаде.

### 3.2 Views (1)

| View | Джерело |
|---|---|
| `order_action_history` | `add_user_tracking.sql` |

### 3.3 Triggers (2)

| Trigger | Джерело | Примітка |
|---|---|---|
| `fin_payments_after_insert` | `005_fix_fin_triggers_recursion.sql` | існує **лише** як `DROP` + `CREATE` у fix-міграції |
| `fin_transactions_after_insert` | `005_fix_fin_triggers_recursion.sql` | `006_drop_fin_transactions_after_insert.sql` його потім видаляє |

Це важливий нюанс: міграція 005 — це *виправлення рекурсії*, а не первинне
створення. Оригінальні тригери були створені поза Git. Тому послідовність
005 → 006 на порожній БД дасть інший результат, ніж на production.

### 3.4 Standalone indexes (7)

| Index | Джерело |
|---|---|
| `idx_customers_email` | `001_modify_customers_table.sql` (через `PREPARE`) |
| `idx_expenses_category_method` | `routes/migrations.py` |
| `idx_laundry_queue_batch` | `add_laundry_queue.sql` |
| `idx_laundry_queue_damage` | `add_laundry_queue.sql` |
| `idx_laundry_queue_order` | `add_laundry_queue.sql` |
| `idx_payments_order_type` | `routes/migrations.py` |
| `idx_payments_stats` | `routes/migrations.py` |

Індекси, оголошені всередині `CREATE TABLE` (`KEY`, `INDEX`), тут не рахуються —
вони приходять разом зі своєю таблицею.

### 3.5 ALTER-only об'єкти

Репозиторій **дописує колонки** до таблиць, яких сам не створює:

| Таблиця | Хто змінює |
|---|---|
| `customers` | `001_modify_customers_table.sql` |
| `documents` | `routes/event_tool.py`, `routes/migrations.py` |
| `fin_payments` | `routes/migrations.py` |
| `finance_transactions` | `add_user_tracking.sql` |
| `issue_cards` | `add_user_tracking.sql` |
| `order_items` | `routes/order_modifications.py` |
| `orders` | `011_company_profiles.sql`, `add_user_tracking.sql`, `routes/event_tool_integration.py`, `routes/migrations.py`, `routes/partial_returns.py`, `routes/payer_profiles.py` |
| `products` | `routes/migrations.py` |

---

## 4. REQUIRES LIVE DB / DUMP (GAP, 71)

Об'єкти читаються/пишуться кодом, але `CREATE` у Git відсутній.
Позначки: `ORM` — є SQLAlchemy-модель; `W` — запис; `R` — читання;
`ALT` — репозиторій додає колонки.

### 4.1 CORE — критичний блок (8)

Без них не працює нічого. Саме через них clean install неможливий.

| Об'єкт | Використання | Колонки, які додає репозиторій |
|---|---|---|
| `orders` | W/R/ALT | 16: `active_annex_id`, `client_user_id`, `company_profile_id`, `company_snapshot_json`, `confirmed_at`, `confirmed_by_id`, `created_by_id`, `damage_fee`, `deal_mode`, `event_board_id`, `has_partial_return`, `manager_comment`, `payer_profile_id`, `payer_snapshot_json`, `source`, `updated_by_id` |
| `documents` | W/R/ALT | 6: `annex_id`, `category`, `first_viewed_at`, `is_legal`, `master_agreement_id`, `snapshot_json` |
| `order_items` | W/R/ALT | 3: `original_quantity`, `refusal_reason`, `status` |
| `products` | W/R/ALT | 2: `hashtags`, `shape` |
| `customers` | R/ALT | 4: `email_verified`, `is_active`, `last_login`, `password_hash` |
| `users` | W/R | — |
| `categories` | W/R | — |
| `clients` | R | — |

Наявність 16 доданих колонок у `orders` означає: базова структура `orders`
історично прийшла з іншого джерела, а Git тримає лише інкременти.

### 4.2 FINANCE (15)

| Об'єкт | Тип | Використання |
|---|---|---|
| `v_order_finance` | **VIEW** | R (`routes/admin_finance.py`) |
| `fin_payments` | table | W/R/ALT (`annex_id`) |
| `fin_transactions` | table | W/R |
| `fin_ledger_entries` | table | W/R |
| `fin_expenses` | table | W/R |
| `fin_categories` | table | W/R |
| `fin_encashments` | table | W/R |
| `fin_deposits` | table | R |
| `fin_deposit_holds` | table | W/R |
| `fin_deposit_events` | table | W/R |
| `fin_accounts` | table | R |
| `fin_employees` | table | R |
| `fin_payroll` | table | R |
| `finance_transactions` | table | ORM/ALT (`created_by_id`) |
| `regular_payments` | table | ORM |

Окремо про `v_order_finance`: це **єдиний view у GAP**, він читається
`routes/admin_finance.py`, але `CREATE VIEW` у репозиторії немає в жодному
файлі. Його визначення (список колонок, агрегації, які саме `fin_*` він
об'єднує) відтворити з коду **неможливо** — потрібен `SHOW CREATE VIEW`.

Окремо про тригери `fin_payments`: див. §3.3. Тригер існує в Git тільки як
патч; сама таблиця `fin_payments` — у GAP. Тобто пара «таблиця + тригер»
розірвана між live-БД і репозиторієм.

### 4.3 DECOR — legacy ORM-блок (20)

`decor_damage_items`, `decor_damages`, `decor_deposits`,
`decor_inventory_extended`, `decor_inventory_items`, `decor_invoices`,
`decor_issue_cards`, `decor_order_items`, `decor_order_lifecycle`,
`decor_orders`, `decor_payments`, `decor_photos`, `decor_product_audits` (W/R),
`decor_product_catalog` (ORM/W), `decor_product_extended`,
`decor_product_history`, `decor_product_lifecycle`, `decor_qr_codes`,
`decor_return_cards` (ORM/W), `decor_tasks`.

18 з 20 — **тільки ORM-моделі без SQL-звернень**. Це кандидати на перевірку:
можливо, таблиць уже немає в БД, а моделі залишилися. Рішення вимагає live-БД —
видаляти моделі «за здогадкою» заборонено.

### 4.4 OTHER (28)

| Об'єкт | Використання |
|---|---|
| `issue_cards` | W/R/ALT — 8 колонок: `checked_by_id`, `created_by_id`, `issued_at`, `issued_by_id`, `prepared_at`, `prepared_by_id`, `received_at`, `received_by_id` |
| `tasks`, `audit_records`, `doc_number_sequences`, `event_managers` | W/R |
| `chat_channels`, `chat_channel_members`, `chat_messages`, `chat_read_status` | W/R |
| `order_lifecycle`, `order_notes`, `order_internal_notes`, `order_packaging`, `order_additional_services` | W/R |
| `product_families`, `product_family_items`, `product_sets`, `product_set_items`, `product_history`, `product_images` | W/R |
| `laundry_batches`, `laundry_items` | W/R |
| `inventory_recount` (W), `inventory_recounts` (W/R) | ⚠ дві схожі назви — потребує перевірки, чи це не помилка в коді |
| `expense_templates`, `expense_due_items` | W/R |
| `return_cards` | W/R |
| `document_email_log` | W |

`laundry_batches` варта уваги: `add_laundry_queue.sql` створює `laundry_queue`
з FK на `laundry_batches`, якої в Git немає. Міграція **не** застосується до
порожньої БД.

### 4.5 OpenCart external (12) — не GAP

`oc_category`, `oc_category_description`, `oc_customer`, `oc_order`,
`oc_order_product`, `oc_order_simple_fields`, `oc_product`,
`oc_product_attribute`, `oc_product_description`, `oc_product_image`,
`oc_product_to_category`, `oc_user`.

Це **чужа БД** (OpenCart, окреме підключення `database.py`). Ці об'єкти
**не повинні** входити в наші міграції ні за яких умов.

---

## 5. Inline DDL (DDL всередині API-обробників)

`routes/migrations.py` та низка інших роутів виконують DDL у рантаймі, а не
через файли-міграції. Створювані там об'єкти:

* через `routes/migrations.py`: `client_users`, `client_payer_links`,
  `payer_profiles`, `master_agreements`, `order_annexes`, `document_emails`,
  `document_signatures`, `product_hashtags_dict`, індекси
  `idx_payments_order_type`, `idx_payments_stats`,
  `idx_expenses_category_method`, а також `ALTER` для `orders`, `documents`,
  `products`, `fin_payments`;
* через доменні роути: `routes/finance.py` (`cash_summaries`, `fin_vendors`,
  `hr_payroll`, `monthly_reports`, `rh_employees`), `routes/admin.py`
  (`system_settings`, `document_templates`), `routes/inventory.py`
  (`processing_queue`), `routes/partial_returns.py`, `routes/return_versions.py`,
  `routes/product_reservations.py`, `routes/order_modifications.py`,
  `routes/product_damage_history.py`, `routes/event_tool.py`.

Це основне джерело розходження між середовищами: об'єкт з'являється лише після
того, як хтось викликав відповідний endpoint. Наразі ці endpoints закриті
migration guard (`ALLOW_RUNTIME_MIGRATIONS` + `X-Migration-Token`, Завдання №3),
але сам патерн залишився.

---

## 6. Foreign keys та indexes — окреме застереження

* **FK у `CREATE TABLE`** зібрані (колонка «Залежить від» у §3.1) — 11 таблиць
  мають inline `REFERENCES`.
* **FK, додані через `ALTER TABLE ... ADD CONSTRAINT`**, у репозиторії
  системно не оголошуються. Повний граф FK production-БД **невідомий** і
  вимагає `information_schema.KEY_COLUMN_USAGE`.
* **Indexes:** 7 standalone у Git (§3.4). Реальна кількість індексів у
  production напевно більша (індекси на `orders`, `products`, `fin_*` очевидно
  існують, бо код робить фільтрацію й агрегації по цих таблицях), але вони
  не описані ніде. Потрібен `SHOW INDEX` по кожній таблиці.

Тобто навіть повний dump `CREATE TABLE` без FK/index-інвентаря дасть
працездатну, але **повільну** й **без цілісності** копію.

---

## 7. Installer readiness для порожньої MySQL

**Статус: НЕ ГОТОВИЙ.** Оцінка нижче — не формальність, вона обґрунтована.

| Крок installer-а | Стан | Причина |
|---|---|---|
| Створити базові таблиці | ❌ | `orders`, `products`, `users`, `customers`, `documents`, `categories`, `clients` — у GAP |
| Створити Finance | ❌ | усі 13 `fin_*` + `finance_transactions` — у GAP |
| Створити `v_order_finance` | ❌ | визначення view не існує в Git |
| Застосувати 001 | ❌ | `ALTER TABLE customers` — таблиці немає |
| Застосувати 002–004 | ❌ | FK на `customers`, `products` |
| Застосувати 005–006 | ❌ | тригери на `fin_payments`, якої немає |
| Застосувати `add_laundry_queue.sql` | ❌ | FK на `laundry_batches` |
| Застосувати `add_user_tracking.sql` | ❌ | `ALTER` на `orders`, `issue_cards`, `finance_transactions` |
| Застосувати 007–011 | ⚠ | частково; 011 робить `ALTER TABLE orders` |
| ORM-моделі | ⚠ | 33 моделі, 20 `decor_*` — статус невідомий |

Кількісно: **71 із ~117** задіяних об'єктів неможливо створити. Це не «майже
готово» — це відсутність фундаменту при наявності надбудови.

### Що конкретно потрібно, щоб installer став можливим

Один артефакт з живої БД:

```
mysqldump --no-data --routines --triggers --events \
          --single-transaction --set-gtid-purged=OFF \
          "$DB_NAME" > baseline_schema.sql
```

плюс окремо, бо `--no-data` не дає зручного зведення:

```
SHOW CREATE VIEW v_order_finance;
SELECT TABLE_NAME, INDEX_NAME, COLUMN_NAME, SEQ_IN_INDEX, NON_UNIQUE
  FROM information_schema.STATISTICS  WHERE TABLE_SCHEMA = DATABASE();
SELECT TABLE_NAME, COLUMN_NAME, CONSTRAINT_NAME,
       REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME
  FROM information_schema.KEY_COLUMN_USAGE
 WHERE TABLE_SCHEMA = DATABASE() AND REFERENCED_TABLE_NAME IS NOT NULL;
```

Дамп знімається з **RentalHub** БД. OpenCart (`oc_*`) — не включати.

---

## 8. Що НЕ зроблено умисно

* **`000_initial.sql` не створювався «за здогадкою».** Відтворити 71 об'єкт
  реконструкцією означало б зафіксувати неправильні типи, довжини,
  `NULL`-політику, колації та дефолти. Така міграція виглядала б робочою і
  зламала б production при першому ж накаті.
  Замість цього baseline згенерований детерміновано з реального дампа —
  `000_baseline.sql` (`scripts/extract_baseline.py`), і його накат перевірений
  емпірично на MySQL 5.7.44.
* **Production schema не змінена.** Жодного DDL не виконано; сканер
  read-only і не підключається до БД.
* **ORM-моделі `decor_*` не видалені** — потрібна перевірка по live-БД.

---

## 9. Наступні кроки

Статус на 2026-09-06.

1. ~~Отримати `baseline_schema.sql` + інвентар view/index/FK (§7).~~ — зроблено.
2. ~~Згенерувати `000_baseline.sql` з дампу, **без ручного редагування
   структур**.~~ — зроблено `scripts/extract_baseline.py`.
3. ~~Реалізувати `schema_migrations` за дизайном у
   `MIGRATION_VERSIONING.md`.~~ — зроблено, runner + історія + checksums.
4. ~~Перевірити clean install на порожній MySQL.~~ — зроблено на MySQL 5.7.44:
   `RESULT: PASSED` (64 таблиці, 1 view, 2 тригери, 22 FK).
   Деталі — `MIGRATION_VERSIONING.md §13`.

Лишилося:

5. **Проштампувати production** як `baseline + 001..011`
   (`stamp --to 011`, без виконання DDL). Механізм перевірено на копії схеми,
   але на production ще не запускався. Обов'язкові умови: свіжий backup,
   явний дозвіл, перевірений план відкату — `MIGRATION_VERSIONING.md §13.3`.

   Готовність підтверджена аудитом на снапшоті production-дампа
   (`MIGRATION_VERSIONING.md §14`): baseline і production розходяться **лише**
   на трьох ручних backup-таблицях `*_bk_20260617_1955`
   (`fin_payments`, `fin_transactions`, `orders_discount`) — це операційні
   копії оператора, які навмисно не входять у baseline і не створюються
   жодною міграцією. Типи, дефолти, `NULL`-політика, індекси, 22 FK з
   правилами, 1 view і 2 тригери — ідентичні. Реальний `stamp --to 011` на
   клоні снапшоту виконав **0 SQL-інструкцій** і не змінив жодного об'єкта.
   Там же знайдено й виправлено дефект, через який
   `create_product_damage_history` після штампу планувалася як `apply` і дала
   б хибний `applied`.
6. Перенести inline DDL (§5) у версіоновані міграції.
7. Винести послідовність clean-install перевірки в CI-джоб (локально вона
   вже відтворювана).