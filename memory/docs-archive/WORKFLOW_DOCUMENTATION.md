# 📋 Повний Workflow Системи Управління Орендою

## 🔄 Життєвий цикл замовлення (Order Lifecycle)

---

## 1️⃣ СТВОРЕННЯ ЗАМОВЛЕННЯ (NewOrder)

### Frontend: `/app/frontend/src/pages/NewOrderView.jsx`

**Користувач вводить:**
- Клієнт (client_id)
- Дати: rental_start_date, rental_end_date
- Товари: [{product_id, quantity, price}]

**Перевірка доступності:**
```javascript
POST /api/orders/check-availability
Request: {
  start_date: "2025-11-25",
  end_date: "2025-11-27",
  items: [{product_id: 8653, quantity: 2}]
}
```

### Backend: `/app/backend/utils/availability_checker.py`

**Читає з таблиць:**
```sql
-- 1. Загальна кількість товару
SELECT quantity FROM products 
WHERE product_id = 8653
→ Результат: total_qty = 100

-- 2. Заморожені товари (в активних замовленнях)
SELECT SUM(oi.quantity)
FROM order_items oi
JOIN orders o ON oi.order_id = o.order_id
WHERE oi.product_id = 8653
  AND o.status IN ('processing', 'ready_for_issue', 'issued', 'on_rent')
  AND o.rental_start_date <= '2025-11-27'
  AND o.rental_end_date >= '2025-11-25'
→ Результат: reserved_qty = 3

-- 3. Доступно
available = total_qty - reserved_qty = 97
→ Запит на 2 шт: ✅ ДОСТУПНО
```

**Response:**
```json
{
  "all_available": true,
  "items": [{
    "product_id": 8653,
    "total_quantity": 100,
    "reserved_quantity": 3,
    "available_quantity": 97,
    "requested_quantity": 2,
    "is_available": true
  }]
}
```

### Створення замовлення

**Пише в таблиці:**

**1. `orders` (основна інформація)**
```sql
INSERT INTO orders (
  order_id,           -- AUTO_INCREMENT
  order_number,       -- 'OC-{order_id}'
  client_id,          -- ID клієнта
  rental_start_date,  -- Дата видачі
  rental_end_date,    -- Дата повернення
  status,             -- 'awaiting_customer' (початковий статус)
  total_amount,       -- Загальна вартість оренди
  deposit_amount,     -- Сума застави
  total_loss_value,   -- Загальна вартість втрати (EAN)
  rental_days,        -- Кількість днів
  created_at,         -- NOW()
  client_confirmed    -- FALSE (клієнт ще не підтвердив)
)
```

**2. `order_items` (товари в замовленні)**
```sql
INSERT INTO order_items (
  id,                 -- AUTO_INCREMENT
  order_id,           -- Посилання на orders.order_id
  product_id,         -- ID товару
  product_name,       -- Назва товару (копія)
  quantity,           -- Кількість
  price,              -- Ціна за день оренди
  total_rental        -- price * quantity * rental_days
)
```

**Статус замовлення:** 
```
orders.status = 'awaiting_customer'
```
**Товари:** ❌ НЕ заморожені (клієнт ще не підтвердив)

---

## 2️⃣ ПІДТВЕРДЖЕННЯ ЗАМОВЛЕННЯ (Manager Confirmation)

### Frontend: `ManagerDashboard.jsx` → "Відправити на збір"

**Натискає кнопку:**
```javascript
POST /api/decor-orders/{order_id}/move-to-preparation
```

### Backend: `/app/backend/routes/orders.py`

**Читає:**
```sql
-- 1. Перевірити поточний статус
SELECT status, rental_start_date, rental_end_date
FROM orders
WHERE order_id = 6996
→ status = 'awaiting_customer'

-- 2. Отримати товари для перевірки
SELECT product_id, quantity
FROM order_items
WHERE order_id = 6996
```

**Перевірка доступності (КРИТИЧНО!):**
```python
# Використовує availability_checker.check_order_availability()
# exclude_order_id = 6996 (виключає поточне замовлення)

availability = check_order_availability(
  db, items, start_date, end_date, 
  exclude_order_id=6996
)

if not availability["all_available"]:
  raise HTTPException(400, "Товари недоступні")
```

**Якщо ВСЕ доступно, пише:**

**1. Оновлює `orders`**
```sql
UPDATE orders
SET status = 'processing',           -- ЗАМОРОЖУЄ ТОВАРИ!
    client_confirmed = TRUE
WHERE order_id = 6996
```

**2. Створює `issue_cards` (картка комплектації)**
```sql
INSERT INTO issue_cards (
  id,              -- 'IC-6996-20251125120000'
  order_id,        -- 6996
  order_number,    -- 'OC-6996'
  status,          -- 'preparation' (на комплектації)
  items,           -- JSON товарів з order_items
  created_at,      -- NOW()
  updated_at       -- NOW()
)
```

**3. Створює `finance_transactions`**
```sql
-- Транзакція на оренду
INSERT INTO finance_transactions (
  id,                  -- UUID
  order_id,            -- 6996
  transaction_type,    -- 'rent_accrual'
  amount,              -- orders.total_amount
  currency,            -- 'UAH'
  status,              -- 'pending'
  description,         -- 'Оренда за замовлення OC-6996'
  created_at           -- NOW()
)

-- Транзакція на заставу
INSERT INTO finance_transactions (
  id,                  -- UUID
  order_id,            -- 6996
  transaction_type,    -- 'deposit_hold'
  amount,              -- orders.deposit_amount
  status,              -- 'pending'
  description,         -- 'Застава за замовлення OC-6996'
  created_at           -- NOW()
)
```

**Статус замовлення:**
```
orders.status = 'processing'
```
**Товари:** ✅ ЗАМОРОЖЕНІ (недоступні для нових замовлень)

**Логіка заморожування:**
```sql
-- Будь-який запит на check-availability тепер враховує це замовлення:
SELECT SUM(oi.quantity)
FROM order_items oi
JOIN orders o ON oi.order_id = o.order_id
WHERE o.status IN ('processing', ...) -- ✅ ВКЛЮЧАЄ це замовлення
```

---

## 3️⃣ КОМПЛЕКТАЦІЯ ТОВАРІВ (IssueCard - Warehouse)

### Frontend: `/app/frontend/src/pages/IssueCard.jsx`

**Працівник складу:**
1. Відкриває картку: `GET /api/issue-cards/{id}`
2. Сканує товари (або вводить вручну)
3. Відзначає зібрані позиції

**Читає з таблиць:**
```sql
-- 1. Картка комплектації
SELECT id, order_id, order_number, status, items, checklist
FROM issue_cards
WHERE id = 'IC-6996-...'

-- 2. Деталі замовлення
SELECT rental_start_date, rental_end_date, client_name, total_amount
FROM orders
WHERE order_id = 6996

-- 3. Деталі товарів
SELECT p.sku, p.name, p.image_url, p.zone, p.aisle, p.shelf
FROM products p
JOIN order_items oi ON p.product_id = oi.product_id
WHERE oi.order_id = 6996
```

**Фіксація пошкоджень ДО видачі:**
```javascript
// Якщо знайдено пошкодження при комплектації
onSaveDamage() → POST /api/product-damage-history/
```

**Пише в таблиці:**

**1. `issue_cards` (прогрес комплектації)**
```sql
UPDATE issue_cards
SET picked_qty = 2,              -- Скільки зібрано
    checklist = JSON,            -- Список зібраних товарів
    manager_notes = 'текст',     -- Примітки
    updated_at = NOW()
WHERE id = 'IC-6996-...'
```

**2. `product_damage_history` (якщо є пошкодження)**
```sql
INSERT INTO product_damage_history (
  id,              -- UUID
  product_id,      -- 8653
  sku,             -- 'D8602'
  product_name,    -- 'Підвіс 46 см'
  category,        -- 'Новий рік'
  order_id,        -- 6996
  order_number,    -- 'OC-6996'
  stage,           -- 'pre_issue' (ДО видачі!)
  damage_type,     -- 'Брудний'
  damage_code,     -- 'dirty'
  severity,        -- 'low'
  fee,             -- 150.00
  photo_url,       -- 'photo.jpg'
  note,            -- 'Примітка'
  created_by,      -- 'manager'
  created_at       -- NOW()
)
```

**Позначити "Готово до видачі":**
```javascript
PUT /api/issue-cards/{id}
{ status: 'ready' }
```

**Пише:**
```sql
-- 1. Оновити картку
UPDATE issue_cards
SET status = 'ready'
WHERE id = 'IC-6996-...'

-- 2. Оновити замовлення
UPDATE orders
SET status = 'ready_for_issue'  -- ТОВАРИ ВСЕ ЩЕ ЗАМОРОЖЕНІ
WHERE order_id = 6996
```

**Статус замовлення:**
```
orders.status = 'ready_for_issue'
```
**Товари:** ✅ ЗАМОРОЖЕНІ

---

## 4️⃣ ВИДАЧА КЛІЄНТУ (Issue to Client)

### Frontend: `IssueCard.jsx` → "Видати"

**Натискає "Видати":**
```javascript
PUT /api/issue-cards/{id}
{ status: 'issued' }
```

### Backend: `/app/backend/routes/issue_cards.py`

**Пише:**
```sql
-- 1. Оновити картку
UPDATE issue_cards
SET status = 'issued',
    issued_at = NOW()
WHERE id = 'IC-6996-...'

-- 2. Оновити замовлення
UPDATE orders
SET status = 'issued'          -- ТОВАРИ В ОРЕНДІ
WHERE order_id = 6996
```

**Статус замовлення:**
```
orders.status = 'issued' або 'on_rent'
```
**Товари:** ✅ ЗАМОРОЖЕНІ (клієнт використовує)

---

## 5️⃣ ПОВЕРНЕННЯ (Return from Client)

### Frontend: `/app/frontend/src/pages/ReturnOrderClean.jsx`

**Менеджер приймає повернення:**
1. Відкриває картку: `GET /api/decor-orders/{id}`
2. Перевіряє кожен товар
3. Фіксує пошкодження (якщо є)
4. Нараховує збитки

**Читає з таблиць:**
```sql
-- 1. Замовлення
SELECT order_id, order_number, status, 
       rental_start_date, rental_end_date,
       total_amount, deposit_amount,
       late_fee, cleaning_fee, damage_fee
FROM orders
WHERE order_id = 6996

-- 2. Товари
SELECT oi.product_id, oi.quantity, 
       p.sku, p.name, p.category_name
FROM order_items oi
JOIN products p ON oi.product_id = p.product_id
WHERE oi.order_id = 6996
```

**Фіксація пошкоджень ПРИ поверненні:**
```javascript
onSaveFinding() → POST /api/product-damage-history/
```

**Пише в таблиці:**

**1. `product_damage_history` (пошкодження при поверненні)**
```sql
INSERT INTO product_damage_history (
  id,              -- UUID
  product_id,      -- 8653
  stage,           -- 'return' (ПРИ поверненні!)
  damage_type,     -- 'Пропал або дірка'
  damage_code,     -- 'burn_or_hole'
  severity,        -- 'high'
  fee,             -- 5000.00
  order_id,        -- 6996
  created_at       -- NOW()
)
```

**2. `orders` (нараховані збитки)**
```sql
UPDATE orders
SET late_fee = 200,         -- Пеня за прострочку
    cleaning_fee = 500,     -- Чистка
    damage_fee = 5000       -- Пошкодження
WHERE order_id = 6996
```

**Завершити повернення:**
```javascript
POST /api/decor-orders/{id}/complete-return
{
  late_fee: 200,
  cleaning_fee: 500,
  damage_fee: 5000
}
```

### Backend: `/app/backend/routes/orders.py`

**Пише:**

**1. `orders` (завершити повернення)**
```sql
UPDATE orders
SET status = 'returned'      -- РОЗМОРОЖУЄ ТОВАРИ!
WHERE order_id = 6996
```

**2. `decor_return_cards` (якщо є)**
```sql
UPDATE decor_return_cards
SET status = 'completed'
WHERE order_id = 6996
```

**3. `finance_transactions` (якщо є збитки)**
```sql
INSERT INTO finance_transactions (
  id,                  -- UUID
  order_id,            -- 6996
  transaction_type,    -- 'charge'
  amount,              -- 5700 (200+500+5000)
  currency,            -- 'UAH'
  status,              -- 'pending'
  description,         -- 'Збитки після повернення: Пеня: 200, Чистка: 500, Пошкодження: 5000'
  created_at           -- NOW()
)
```

**Статус замовлення:**
```
orders.status = 'returned'
```
**Товари:** ✅ РОЗМОРОЖЕНІ (знову доступні для нових замовлень)

**Логіка розморожування:**
```sql
-- Запит на check-availability більше НЕ враховує це замовлення:
SELECT SUM(oi.quantity)
FROM order_items oi
JOIN orders o ON oi.order_id = o.order_id
WHERE o.status IN ('processing', ...)  -- ❌ 'returned' НЕ включено
```

---

## 6️⃣ ВТРАТА ТОВАРУ (Write-off)

**Якщо товар не повернуто або критично пошкоджений:**

```javascript
POST /api/inventory-adjustments/write-off
{
  product_id: 8653,
  quantity: 1,
  reason: "lost",
  note: "Втрачено клієнтом"
}
```

**Пише:**
```sql
-- Вичитати з обігу
UPDATE products
SET quantity = quantity - 1
WHERE product_id = 8653

-- Було: 100
-- Стало: 99
```

**Результат:** Товар назавжди вилучено з обігу

---

## 📊 ТАБЛИЦІ ТА ЇХ РОЛЬ

### **Основні таблиці:**

**1. `orders` - Замовлення (головна таблиця)**
- Зберігає: статус, дати, клієнт, фінанси
- Статус визначає заморожування товарів
- Використовується СКРІЗЬ

**2. `order_items` - Товари в замовленні**
- Посилання на `orders.order_id`
- Посилання на `products.product_id`
- Використовується для розрахунку заморожених товарів

**3. `products` - Каталог товарів**
- Зберігає: кількість (`quantity`), ціни, фото
- `quantity` - фізична кількість на складі
- Оновлюється при списанні

**4. `issue_cards` - Картки комплектації**
- Посилання на `orders.order_id`
- Використовується складом для збору товарів
- Зберігає прогрес (`picked_qty`, `checklist`)

**5. `product_damage_history` - Історія пошкоджень**
- Зберігає ВСІ пошкодження (до видачі та при поверненні)
- `stage`: 'pre_issue' або 'return'
- Використовується для аналітики

**6. `finance_transactions` - Фінансові транзакції**
- Зберігає: оренда, застава, збитки
- Створюються автоматично
- `status`: 'pending' → 'paid' → 'completed'

---

## 🔐 ЛОГІКА ЗАМОРОЖУВАННЯ

### **Коли товари ЗАМОРОЖЕНІ:**
```sql
orders.status IN (
  'processing',        -- На комплектації
  'ready_for_issue',   -- Готово до видачі
  'issued',            -- Видано
  'on_rent'            -- В оренді
)
```

### **Коли товари РОЗМОРОЖЕНІ:**
```sql
orders.status IN (
  'returned',          -- Повернуто
  'cancelled',         -- Скасовано
  'completed'          -- Завершено
)
```

### **Початковий статус (НЕ заморожено):**
```sql
orders.status IN (
  'awaiting_customer',  -- Очікує підтвердження
  'new'                 -- Новий
)
```

---

## 🔄 СХЕМА ПОТОКУ ДАНИХ

```
┌─────────────┐
│  NewOrder   │ → INSERT orders (status='awaiting_customer')
│  (Frontend) │ → INSERT order_items
└─────────────┘
      ↓
┌─────────────┐
│   Manager   │ → UPDATE orders (status='processing') ✅ ЗАМОРОЖУЄ
│   Confirm   │ → INSERT issue_cards
└─────────────┘ → INSERT finance_transactions
      ↓
┌─────────────┐
│  IssueCard  │ → UPDATE issue_cards (picked_qty)
│  (Warehouse)│ → INSERT product_damage_history (stage='pre_issue')
└─────────────┘ → UPDATE orders (status='ready_for_issue')
      ↓
┌─────────────┐
│   Issue to  │ → UPDATE issue_cards (status='issued')
│   Client    │ → UPDATE orders (status='issued')
└─────────────┘
      ↓
┌─────────────┐
│   Return    │ → INSERT product_damage_history (stage='return')
│   (Client)  │ → UPDATE orders (late_fee, damage_fee)
└─────────────┘ → INSERT finance_transactions (збитки)
      ↓
┌─────────────┐
│  Complete   │ → UPDATE orders (status='returned') ✅ РОЗМОРОЖУЄ
│   Return    │ → UPDATE decor_return_cards (completed)
└─────────────┘
```

---

## 🎯 КЛЮЧОВІ МОМЕНТИ

1. **Єдине джерело правди:** `orders.status` визначає заморожування
2. **Автоматичне заморожування:** Зміна статусу автоматично впливає на доступність
3. **Історія пошкоджень:** Зберігається окремо для аналітики
4. **Фінансові транзакції:** Створюються автоматично
5. **Списання товарів:** Тільки вручну через API

Система працює цілісно і консистентно! 🚀
