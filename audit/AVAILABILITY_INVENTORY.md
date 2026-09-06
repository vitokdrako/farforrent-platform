# Availability Inventory Map (Task #11, фаза 1)

**Правило фази:** нічого не змінювати. Тільки знайти, описати й довести числами.

**Джерело доказів:** production-знімок `farforre_rentalhub.sql`
(SHA-256 `506a79c7258dde6dbd7f2f8cd33cc6b10a49f252198aa815e055f2c34d4e752b`),
відновлений локально у схему `prod_snapshot` (MySQL 5.7.44).
Живої production-БД не торкалися. Усі запити — `SELECT`.

Період для порівняння формул: `2026-09-06 .. 2026-09-13`. Перевірено 8173 активних товари (`products.status = 1`).

---

## 1. Головний висновок

Єдиного джерела правди немає. Доступність рахується **в 11 місцях за 9 різними формулами**.
Це не стильова розбіжність — формули дають **різні числа на тих самих даних**.

| Порівняння | Товарів з різним результатом | Макс. розбіжність (шт) |
|---|---|---|
| `availability_checker` ↔ каталог (список) | **294** | **210** |
| `availability_checker` ↔ event-tool (каталог) | **429** | **210** |
| `availability_checker` ↔ inventory (заморозка) | **588** | — |
| `availability_checker` ↔ issue_cards | **60** | — |
| каталог ↔ event-tool | **162** | — |

Тобто на один і той самий товар Website, Admin, Calendar і Sets можуть показати
розбіжність **до 210 одиниць**.

---

## 2. Реєстр точок розрахунку

Легенда компонентів: `T` = `products.quantity`, `R` = резерв із замовлень,
`IR` = в оренді, `FQ` = `products.frozen_quantity`, `PDH` = `product_damage_history`,
`SR` = `event_soft_reservations`, `PR` = `product_reservations`.

| # | Місце | Формула | Фільтр дат | Статуси, що резервують |
|---|---|---|---|---|
| A | `utils/availability_checker.py` → `check_product_availability` | `T − R` | ✅ перетин | `processing, ready_for_issue, issued, on_rent` |
| B | `routes/catalog.py` → список/`items-by-category` | `T − R − IR − PDH` | ✅ / ❌ (дві гілки) | `processing, ready_for_issue, awaiting_customer, pending` + окремо `issued, on_rent` |
| C | `routes/event_tool.py` → каталог товарів | `T − FQ − IR − R` | ✅ / ❌ (дві гілки) | ті ж, що B |
| D | `routes/event_tool.py` → `POST /products/check-availability` | `T − FQ − R − SR` | ✅ перетин | `processing, ready_for_issue, issued, on_rent` |
| E | `routes/product_reservations.py` → `check_product_availability` | `T − PR` | ✅ перетин | таблиця `product_reservations` |
| F | `routes/issue_cards.py` | `T − R` | ❌ **немає** | `processing, ready_for_issue, issued, on_rent` + `is_archived = 0` |
| G | `routes/inventory.py` → заморозка | `T − FQ` | ❌ немає | — (не дивиться на замовлення) |
| H | `routes/event_tool_integration.py` → створення замовлення | `T − PR` | ✅ перетин | `product_reservations` |
| I | `routes/catalog.py` → `GET /check-availability/{sku}` | `T > 0` | ❌ **ігнорує дати** | — (жодних) |
| J | `routes/order_modifications.py` | `available = p.quantity` | ❌ немає | — (жодних) |
| K | `routes/orders.py` → позиції замовлення | `available = p.quantity`, `reserved = 0` | ❌ немає | — (`TODO` у коді) |
| L | `routes/product_sets.py` (Sets/Bundles) | **немає розрахунку** | ❌ | — |

Викликають спільне ядро (A) лише **2 місця** з 11: `orders.py` `POST /check-availability`
і перевірка перед переходом у `processing`. Решта — власні SQL-запити.

---

## 3. Доведені дефекти (числа з production-знімка)

### 3.1 Статус `partial_return` невидимий для ВСІХ формул
```
partial_return: 1 замовлення, 55 одиниць товару
```
Цього статусу немає ні в одному списку резервування. Товар фізично у клієнта,
але всі 11 точок вважають його вільним.

### 3.2 `awaiting_customer` / `pending` трактуються протилежно
```
awaiting_customer: 2 замовлення, 76 одиниць
ready_for_issue:   1 замовлення, 55 одиниць
```
`availability_checker` (A) **не** резервує `awaiting_customer`, а каталог (B, C) — **резервує**.
Одна й та сама позиція одночасно «вільна» в Admin і «зайнята» в каталозі.

### 3.3 `is_archived` фільтрується лише в одному місці
```
активні замовлення з is_archived = 1: 1 замовлення, 55 одиниць
```
`issue_cards` (F) їх виключає, `availability_checker` (A) — ні. Звідси 60 розбіжностей.

### 3.4 Два незалежні джерела «на обробці» розходяться
```
frozen_quantity > 0, але PDH порожній: 145 товарів
PDH > 0, але frozen_quantity = 0:        3 товари
будь-яка невідповідність:              181 товар
```
`event_tool` (C, D) і `inventory` (G) вірять `products.frozen_quantity`,
каталог (B) і `warehouse` — `product_damage_history`. Обидва вважаються правдою.

### 3.5 `written_off` товар досі «доступний»
```
state = 'written_off': 11 товарів, 389 одиниць, frozen лише 10
```
Жодна формула не виключає списаний товар. ~379 одиниць списаного товару
можна забронювати.

### 3.6 Три таблиці, на яких тримається логіка, у production ВІДСУТНІ
```
product_reservations  → MISSING
product_sets          → MISSING
product_set_items     → MISSING
```
Наслідки:
- **E** (`product_reservations` check) — непрацездатний;
- **H** (створення замовлення з event-tool) — `COALESCE(SUM(pr.quantity), 0)` дає **0**,
  тобто перевірка конфліктів **завжди проходить**, навіть коли товару немає;
- **L** (Sets/Bundles) — усі запити звертаються до відсутніх таблиць.

`product_reservations` створюється лише вручну через `POST /migrate` — це не міграція,
а endpoint. У `000_baseline.sql` цих таблиць немає.

### 3.7 Frontend передає дати в endpoint, який їх ігнорує
`frontend/src/api/client.ts:119` надсилає `fromDate` / `toDate` у
`GET /catalog/check-availability/{sku}`, а endpoint (I) відповідає просто `quantity > 0`.
Дати відкидаються молча — UI показує «доступно» без перевірки періоду.

### 3.8 Soft reservations враховує лише 1 точка з 11
`event_soft_reservations` читає **тільки** D. Мудборд може «тримати» товар,
і жодна інша частина системи цього не бачить.

### 3.9 Sets/Bundles не мають availability взагалі
`product_sets.py` повертає `p.quantity as stock` — сирий залишок,
без резервів, без дат, без обробки. Доступність набору = не обчислюється ніде.

---

## 4. Цільова архітектура (ще НЕ реалізована)

```
Website ─┐
Admin ───┤
Orders ──┼──→ AvailabilityService ──→ Inventory / DB
Calendar ┤
Warehouse┤
Sets ────┘
```

Кандидат на ядро — `utils/availability_checker.py`: це єдине місце, де вже є
перетин дат, `exclude_order_id`, попередження про часткові повернення й обробку.
Але його формула (`T − R`) — **не** найповніша: вона не віднімає обробку
й не фільтрує `is_archived`.

---

## 5. Блокер фази 2

Вимога «не змінювати поведінку» **неможлива для всіх точок одночасно**:
формули суперечать одна одній на 294–588 товарах. Уніфікація за визначенням
змінить результат щонайменше для 8 із 11 точок.

Тому вибір канонічної семантики — **продуктове рішення, не технічне**.
Потрібне рішення власника щодо:

1. чи резервує `awaiting_customer` / `pending` (розбіжність A ↔ B);
2. чи резервує `partial_return` (зараз — ніде, 55 одиниць);
3. джерело правди для «на обробці»: `frozen_quantity` чи `product_damage_history` (181 розбіжність);
4. чи виключати `written_off` (389 одиниць);
5. чи враховувати `event_soft_reservations` глобально;
6. чи фільтрувати `is_archived`;
7. доля відсутніх таблиць `product_reservations` / `product_sets`.

До отримання цих рішень фаза 2 не починається.

---

## 6. Що НЕ змінювалося

Жодного рядка бізнес-логіки. Жодного DDL. Жодного контакту з живою production-БД.
Цей документ — тільки опис поточного стану.