# Детальний аналіз взаємодії кабінетів RentalHub
## Як модулі взаємодіють та де є дубляж

---

## 1. КАРТА МОДУЛІВ І ТАБЛИЦЬ

```
┌─────────────────────────────────────────────────────────────────────┐
│                        FRONTEND КАБІНЕТИ                           │
├──────────────┬───────────────┬──────────────┬──────────────────────┤
│ DamageHubApp │ LaundryCab.   │ CatalogBoard │ FinanceHub           │
│ /damages     │ (не в роутах) │ /catalog     │ /kasa                │
├──────────────┴───────────────┴──────────────┴──────────────────────┤
│                        BACKEND ROUTES                              │
├──────────────┬───────────────┬──────────────┬──────────────────────┤
│ product_     │ laundry.py    │ catalog.py   │ finance.py           │
│ damage_      │               │              │                      │
│ history.py   │               │              │                      │
├──────────────┼───────────────┼──────────────┼──────────────────────┤
│ damage_      │               │ product_     │                      │
│ cases.py     │               │ cleaning.py  │                      │
├──────────────┼───────────────┼──────────────┼──────────────────────┤
│ damages.py   │               │              │                      │
├──────────────┴───────────────┴──────────────┴──────────────────────┤
│                        ТАБЛИЦІ БД                                  │
├──────────────┬───────────────┬──────────────┬──────────────────────┤
│ product_     │ laundry_      │ products     │ fin_transactions     │
│ damage_      │ batches       │              │ fin_payments         │
│ history      │               │              │ fin_ledger_entries   │
│              │ laundry_      │ product_     │ fin_deposit_holds    │
│ damages      │ items         │ cleaning_    │ fin_expenses         │
│ damage_items │               │ status       │ fin_accounts         │
│              │               │              │                      │
│ damage_case_ │               │              │ finance_transactions │
│ archive      │               │              │ (СТАРА!)             │
└──────────────┴───────────────┴──────────────┴──────────────────────┘
```

---

## 2. ПОТОКИ ДАНИХ МІЖ КАБІНЕТАМИ

### 2.1. Потік "Товар отримав пошкодження"

```
Повернення замовлення (return_cards.py)
    │
    ├─→ damages + damage_items       ← СТАРА система кейсів
    │
    └─→ DamageModal (frontend)
         │
         ├─→ product_damage_history   ← НОВА система (DamageHubApp)
         │     │
         │     ├─ processing_type = 'wash'        → Черга Мийки
         │     ├─ processing_type = 'restoration'  → Черга Реставрації  
         │     └─ processing_type = 'laundry'      → Черга Пральні
         │
         └─→ product_cleaning_status  ← ЩЕ ОДНА паралельна система!
               (записується в orders.py при поверненні)
```

**ПРОБЛЕМА:** При поверненні товару дані записуються в **3 різні місця**:
1. `damages` + `damage_items` (через return_cards.py, рядок 418)
2. `product_damage_history` (через DamageModal → product_damage_history.py)
3. `product_cleaning_status` (через orders.py, рядок 2838)

### 2.2. Потік "Товар на обробці → Каталог"

```
product_damage_history (processing_type + processing_status)
    │
    └─→ catalog.py (рядки 1100+)
         Рахує on_wash, on_restoration, on_laundry
         
product_cleaning_status (status = wash/dry/repair)
    │
    └─→ catalog.py (рядок 649)
         Також читає для визначення cleaning_status товару!
         
products.state (on_wash/on_repair/on_laundry/damaged)
    │
    └─→ НЕ ВИКОРИСТОВУЄТЬСЯ в каталозі для фільтрації
         (але все ще показується в UI!)
         
products.frozen_quantity
    │
    └─→ catalog.py: available_qty = quantity - frozen_quantity
```

**ПРОБЛЕМА:** Каталог читає дані про обробку з **2 різних таблиць** (`product_damage_history` та `product_cleaning_status`), які можуть суперечити одне одному.

### 2.3. Потік "Пральня/Хімчистка"

```
DamageHubApp (frontend)
    │
    ├─→ product_damage_history (processing_type='laundry')
    │     │
    │     └─→ laundry.py: GET /queue → читає з product_damage_history
    │           │
    │           └─→ POST /queue/add-to-batch
    │                 │
    │                 ├─→ laundry_items (копіює дані з PDH)  ← ДУБЛЯЖ!
    │                 └─→ product_damage_history.laundry_batch_id (зв'язок)
    │
    └─→ Повернення з партії:
          │
          ├─→ laundry_items.returned_quantity++
          ├─→ products.frozen_quantity--
          └─→ product_damage_history.processed_qty++
```

**ПРОБЛЕМА:** `laundry_items` дублює інформацію з `product_damage_history`:
- `laundry_items`: product_id, product_name, sku, category, quantity, returned_quantity
- `product_damage_history`: product_id, product_name, sku, category, qty, processed_qty

### 2.4. Потік "Фінанси"

```
Оплата замовлення (orders.py)
    │
    ├─→ finance_transactions (СТАРА! рядки 1278, 1296, 2513, 2531, 2874)
    │     Використовується: orders.py, user_tracking.py
    │
    └─→ fin_payments (НОВА)
          Використовується: finance.py (FinanceHub)
          
Витрати (expense_management.py)
    │
    └─→ fin_expenses → fin_transactions → fin_ledger_entries
    
Депозити (finance.py)
    │
    └─→ fin_deposit_holds → fin_deposit_events
```

**ПРОБЛЕМА:** `orders.py` пише в `finance_transactions` (стару таблицю), а `FinanceHub` читає з `fin_*` (нових таблиць). Фінансові дані замовлень **НЕ ПОТРАПЛЯЮТЬ** в FinanceHub!

### 2.5. Потік "Реаудит → Шкода"

```
ReauditCabinetFull (frontend)
    │
    └─→ damage_cases.py: POST /create
          │
          ├─→ product_damage_history (рядки 100+)
          │     (processing_type = repair/restoration/washing)
          │
          └─→ products (frozen_quantity++)
```

**OK:** Цей потік коректний. Реаудит використовує `damage_cases.py`, який правильно пише в `product_damage_history`.

---

## 3. ДУБЛЯЖ ROUTE ФАЙЛІВ

### 3.1. Три файли для роботи зі шкодою

| Файл | Таблиця | UI | Функціонал |
|---|---|---|---|
| `damages.py` | `damages` + `damage_items` | `DamageCabinet_New.tsx` (legacy) | CRUD кейсів шкоди (стара) |
| `damage_cases.py` | `product_damage_history` + `damages` | `ReauditCabinetFull.tsx` | Створення кейсів з реаудиту |
| `product_damage_history.py` | `product_damage_history` | `DamageHubApp.jsx` | Черги, часткові повернення (нова) |

**Рекомендація:** `damages.py` → legacy, можна об'єднати з `product_damage_history.py`.

### 3.2. Два файли для чистки/статусу

| Файл | Таблиця | Функціонал |
|---|---|---|
| `product_cleaning.py` | `product_cleaning_status` | CRUD статусу чистки |
| `product_damage_history.py` | `product_damage_history` | Обробка (wash/restoration/laundry) |

**Рекомендація:** `product_cleaning_status` дублює `product_damage_history`. Можна видалити `product_cleaning.py`.

---

## 4. КОНКРЕТНІ РЕКОМЕНДАЦІЇ ПО ОБ'ЄДНАННЮ

### 4.1. Об'єднати `product_cleaning_status` → `product_damage_history`

**Зараз:**
- `product_cleaning_status`: 494 записи (wash=469, repair=25)
- `product_damage_history`: 230 записів

**Дія:**
1. Мігрувати дані з `product_cleaning_status` в `product_damage_history` (якщо немає дублів)
2. Оновити `catalog.py` (рядок 649) — прибрати читання з `product_cleaning_status`
3. Оновити `orders.py` (рядок 2838) — замість `product_cleaning_status` писати в `product_damage_history`
4. Видалити `product_cleaning.py`
5. Видалити таблицю `product_cleaning_status`

**Результат:** Одне джерело істини для статусу обробки товару.

### 4.2. Об'єднати `damages` → `product_damage_history`

**Зараз:**
- `damages` + `damage_items`: 49 + 49 записів (фінансові кейси шкоди)
- `product_damage_history`: 230 записів (черги обробки)

**Різниця:** `damages` зберігає фінансову інформацію (claimed_total, paid_total, withheld_total), яку `product_damage_history` не має.

**Дія:**
1. Додати фінансові поля в `product_damage_history` (claimed_total, paid_total, withheld_total, finance_status)
2. Мігрувати дані
3. Оновити `damage_cases.py`, `return_cards.py`, `orders.py`
4. Видалити `damages.py`, таблиці `damages` + `damage_items`

**Ризик:** СЕРЕДНІЙ. Потрібно ретельно перевірити всі 7 файлів що звертаються до `damages`.

### 4.3. Спростити `laundry_items`

**Зараз:** `laundry_items` дублює дані з `product_damage_history`.

**Дія:**
1. `laundry_items` зберігає тільки: `id, batch_id, product_damage_history_id, returned_quantity`
2. Всі інші поля (product_name, sku, category тощо) брати через JOIN з `product_damage_history`

**Ризик:** НИЗЬКИЙ. Зменшує дубляж даних.

### 4.4. Консолідувати фінанси

**Зараз:** `orders.py` пише в `finance_transactions`, FinanceHub читає з `fin_transactions`.

**Дія:**
1. Замінити в `orders.py` всі INSERT INTO `finance_transactions` → INSERT INTO `fin_transactions`
2. Мігрувати існуючі записи
3. Видалити таблицю `finance_transactions`

**Ризик:** ВИСОКИЙ. `orders.py` — найбільший файл (3280 рядків), зміни потрібно ретельно тестувати.

---

## 5. ПРІОРИТЕТНИЙ ПЛАН ДІЙ

| # | Дія | Ризик | Вигода |
|---|---|---|---|
| 1 | Видалити 14 backup файлів | 🟢 НУЛЬ | Чистота коду |
| 2 | Видалити 8 порожніх таблиць | 🟢 НУЛЬ | Чистота БД |
| 3 | Уніфікувати `washing` → `wash` | 🟢 НИЗЬКИЙ | Консистентність |
| 4 | Об'єднати `product_cleaning_status` → PDH | 🟡 СЕРЕДНІЙ | Одне джерело істини |
| 5 | Спростити `laundry_items` | 🟡 СЕРЕДНІЙ | Менше дубляжу |
| 6 | Консолідувати фінанси | 🔴 ВИСОКИЙ | Точні фінанси |
| 7 | Об'єднати `damages` → PDH | 🔴 ВИСОКИЙ | Менше таблиць |

---

## 6. ПОТЕНЦІЙНА ЦІЛЬОВА АРХІТЕКТУРА

### До (зараз):
```
products.state ──────────────── НЕ НАДІЙНЕ
products.frozen_quantity ────── OK (але розсинхронізується)
product_cleaning_status ─────── ДУБЛЯЖ
product_damage_history ──────── ДЖЕРЕЛО ІСТИНИ
damages + damage_items ──────── СТАРА СИСТЕМА
laundry_items ───────────────── ДУБЛЯЖ product_damage_history
finance_transactions ────────── СТАРА СИСТЕМА
fin_* таблиці ───────────────── НОВА СИСТЕМА
```

### Після (ціль):
```
products.frozen_quantity ────── Розраховується з PDH
product_damage_history ──────── ЄДИНЕ ДЖЕРЕЛО (обробка + фінанси шкоди)
laundry_items ───────────────── Тільки зв'язок batch↔pdh + returned_qty
fin_* таблиці ───────────────── ЄДИНА ФІНАНСОВА СИСТЕМА
```

**Видалені таблиці:** `product_cleaning_status`, `damages`, `damage_items`, `finance_transactions`, `damage_case_archive`, + 8 порожніх = **13 таблиць**

**Видалені route файли:** `product_cleaning.py`, `damages.py`, + 14 backup = **16 файлів**
