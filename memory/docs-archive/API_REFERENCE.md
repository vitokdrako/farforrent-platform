# 🔌 API Reference - Швидкий Довідник

## 📦 Управління Замовленнями

### **Перевірка доступності товарів**
```http
POST /api/orders/check-availability
Content-Type: application/json

{
  "start_date": "2025-11-25",
  "end_date": "2025-11-27",
  "items": [
    {"product_id": 8653, "quantity": 2},
    {"product_id": 8611, "quantity": 1}
  ]
}

Response:
{
  "all_available": true,
  "items": [{
    "product_id": 8653,
    "total_quantity": 100,
    "reserved_quantity": 3,
    "available_quantity": 97,
    "requested_quantity": 2,
    "is_available": true
  }],
  "unavailable_items": []
}
```
**Використовує:** `availability_checker.check_order_availability()`  
**Таблиці:** `products`, `order_items`, `orders`

---

### **Підтвердження замовлення (Відправити на збір)**
```http
POST /api/decor-orders/{order_id}/move-to-preparation

Response:
{
  "success": true,
  "message": "Замовлення відправлено на збір",
  "order_id": 6996,
  "status": "processing",
  "issue_card_id": "IC-6996-20251125120000"
}
```
**Що робить:**
1. ✅ Перевіряє доступність (`check_order_availability`)
2. ✅ Змінює статус: `awaiting_customer` → `processing` (ЗАМОРОЖУЄ)
3. ✅ Створює `issue_cards`
4. ✅ Створює `finance_transactions`

**Таблиці:** `orders`, `issue_cards`, `finance_transactions`

---

### **Отримати замовлення**
```http
GET /api/decor-orders/{order_id}

Response:
{
  "order_id": 6996,
  "order_number": "OC-6996",
  "status": "processing",
  "rental_start_date": "2025-11-25",
  "rental_end_date": "2025-11-27",
  "items": [{
    "product_id": 8653,
    "sku": "D8602",
    "name": "Підвіс 46 см",
    "category": "Новий рік",
    "quantity": 2,
    "price": 50.00
  }],
  "total_amount": 200.00,
  "deposit_amount": 500.00
}
```
**Таблиці:** `orders`, `order_items`, `products`

---

### **Завершити повернення**
```http
POST /api/decor-orders/{order_id}/complete-return
Content-Type: application/json

{
  "late_fee": 200,
  "cleaning_fee": 500,
  "damage_fee": 5000
}

Response:
{
  "success": true,
  "message": "Повернення успішно завершено",
  "order_id": 6996,
  "fees_charged": 5700,
  "finance_transaction_created": true
}
```
**Що робить:**
1. ✅ Змінює статус: `issued` → `returned` (РОЗМОРОЖУЄ)
2. ✅ Оновлює `orders` (збитки)
3. ✅ Створює `finance_transactions` для збитків
4. ✅ Оновлює `decor_return_cards`

**Таблиці:** `orders`, `decor_return_cards`, `finance_transactions`

---

## 🏭 Картки Комплектації

### **Отримати картку комплектації**
```http
GET /api/issue-cards/{card_id}

Response:
{
  "id": "IC-6996-20251125120000",
  "order_id": 6996,
  "order_number": "OC-6996",
  "status": "preparation",
  "items": [{...}],
  "picked_qty": 0,
  "checklist": {},
  "manager_notes": ""
}
```
**Таблиці:** `issue_cards`, `orders`, `order_items`

---

### **Оновити картку (позначити готово)**
```http
PUT /api/issue-cards/{card_id}
Content-Type: application/json

{
  "status": "ready",
  "picked_qty": 2,
  "checklist": {...},
  "manager_notes": "Всі товари зібрані"
}

Response:
{
  "success": true,
  "message": "Картка оновлена",
  "order_status": "ready_for_issue"
}
```
**Що робить:**
1. ✅ Оновлює `issue_cards`
2. ✅ Змінює статус orders: `processing` → `ready_for_issue`

**Таблиці:** `issue_cards`, `orders`

---

## 📋 Історія Пошкоджень

### **Зафіксувати пошкодження**
```http
POST /api/product-damage-history/
Content-Type: application/json

{
  "product_id": 8653,
  "sku": "D8602",
  "product_name": "Підвіс 46 см",
  "category": "Новий рік",
  "order_id": 6996,
  "order_number": "OC-6996",
  "stage": "pre_issue",  // або "return"
  "damage_type": "Брудний",
  "damage_code": "dirty",
  "severity": "low",
  "fee": 150.00,
  "photo_url": "photo.jpg",
  "note": "Примітка",
  "created_by": "manager"
}

Response:
{
  "success": true,
  "message": "Пошкодження зафіксовано",
  "damage_id": "uuid"
}
```
**Таблиці:** `product_damage_history`

---

### **Отримати історію пошкоджень товару**
```http
GET /api/product-damage-history/product/{product_id}

Response:
{
  "product_id": 8653,
  "total_damages": 5,
  "total_fees": 7500.00,
  "history": [{
    "id": "uuid",
    "stage": "pre_issue",
    "stage_label": "До видачі",
    "damage_type": "Брудний",
    "severity": "low",
    "fee": 150.00,
    "order_number": "OC-6996",
    "created_at": "2025-11-25T12:00:00",
    "created_by": "manager"
  }]
}
```
**Таблиці:** `product_damage_history`

---

### **Історія за SKU**
```http
GET /api/product-damage-history/sku/{sku}
```

### **Історія за замовленням**
```http
GET /api/product-damage-history/order/{order_id}
```

---

## 📦 Каталог та Інвентар

### **Отримати каталог**
```http
GET /api/catalog?include_reservations=true&limit=100

Response: [
  {
    "product_id": 8653,
    "sku": "D8602",
    "name": "Підвіс 46 см",
    "category": "Новий рік",
    "price": 50.00,
    "total": 100,
    "reserved": 5,
    "in_rent": 3,
    "available": 95,
    "state": "ok"
  }
]
```
**Параметри:**
- `include_reservations=true` - розраховує резерви (повільно, за потребою)
- `category` - фільтр по категорії
- `search` - пошук по SKU/назві
- `limit` - кількість записів

**Таблиці:** `products`, `order_items`, `orders`, `product_damage_history`

---

### **Статус товару (детально)**
```http
GET /api/inventory-adjustments/product/{product_id}/status

Response:
{
  "product_id": 8653,
  "total_quantity": 100,
  "frozen_quantity": 5,
  "in_rent_quantity": 3,
  "available_quantity": 95,
  "status": {
    "in_stock": true,
    "available_for_rent": true,
    "all_in_use": false
  }
}
```
**Таблиці:** `products`, `order_items`, `orders`

---

### **Списати товар з обігу**
```http
POST /api/inventory-adjustments/write-off
Content-Type: application/json

{
  "product_id": 8653,
  "sku": "D8602",
  "quantity": 1,
  "reason": "lost",
  "note": "Втрачено клієнтом"
}

Response:
{
  "success": true,
  "message": "Списано 1 од. з обігу",
  "product_id": 8653,
  "previous_quantity": 100,
  "new_quantity": 99,
  "reason": "lost"
}
```
**Що робить:**
1. ✅ Зменшує `products.quantity`
2. ✅ Логує операцію

**Таблиці:** `products`

---

### **Коригування інвентарю**
```http
POST /api/inventory-adjustments/adjust
Content-Type: application/json

{
  "product_id": 8653,
  "adjustment": -5,  // або +10
  "reason": "manual_correction",
  "note": "Виправлення помилки інвентаризації"
}

Response:
{
  "success": true,
  "message": "Інвентар скориговано: -5",
  "product_id": 8653,
  "previous_quantity": 100,
  "new_quantity": 95,
  "adjustment": -5
}
```
**Таблиці:** `products`

---

## 💰 Фінансові Транзакції

### **Отримати транзакції замовлення**
```http
GET /api/finance/transactions?order_id={order_id}

Response: [
  {
    "id": "uuid",
    "order_id": 6996,
    "transaction_type": "rent_accrual",
    "amount": 200.00,
    "currency": "UAH",
    "status": "pending",
    "description": "Оренда за замовлення OC-6996",
    "created_at": "2025-11-25T12:00:00"
  },
  {
    "transaction_type": "deposit_hold",
    "amount": 500.00,
    "status": "pending",
    "description": "Застава за замовлення OC-6996"
  },
  {
    "transaction_type": "charge",
    "amount": 5700.00,
    "status": "pending",
    "description": "Збитки після повернення"
  }
]
```
**Таблиці:** `finance_transactions`

---

## 🔍 Корисні SQL Запити

### **Заморожені товари на період:**
```sql
SELECT 
  oi.product_id,
  p.sku,
  p.name,
  SUM(oi.quantity) as frozen
FROM order_items oi
JOIN orders o ON oi.order_id = o.order_id
JOIN products p ON oi.product_id = p.product_id
WHERE o.status IN ('processing', 'ready_for_issue', 'issued', 'on_rent')
  AND o.rental_start_date <= '2025-11-27'
  AND o.rental_end_date >= '2025-11-25'
GROUP BY oi.product_id
```

### **Товари в оренді зараз:**
```sql
SELECT 
  oi.product_id,
  p.sku,
  COUNT(DISTINCT o.order_id) as orders_count,
  SUM(oi.quantity) as qty_in_rent
FROM order_items oi
JOIN orders o ON oi.order_id = o.order_id
JOIN products p ON oi.product_id = p.product_id
WHERE o.status IN ('issued', 'on_rent')
  AND CURDATE() BETWEEN o.rental_start_date AND o.rental_end_date
GROUP BY oi.product_id
```

### **Топ пошкоджених товарів:**
```sql
SELECT 
  product_id,
  sku,
  COUNT(*) as damage_count,
  SUM(fee) as total_fees
FROM product_damage_history
WHERE created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)
GROUP BY product_id
ORDER BY damage_count DESC
LIMIT 10
```

---

Вся система працює через ці API! 🚀
