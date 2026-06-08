# ✅ User Tracking - Міграція Завершена

**Дата:** 05.12.2025

## 🎯 Що додано:

Система трекінгу користувачів для відстеження хто і коли працював з кожним замовленням.

---

## 📊 Додані Поля в Таблиці:

### **1. ORDERS**
```sql
created_by_id INT        -- Менеджер що створив замовлення
confirmed_by_id INT      -- Менеджер що підтвердив
updated_by_id INT        -- Хто останній редагував
confirmed_at TIMESTAMP   -- Коли підтверджено
```

### **2. ISSUE_CARDS**
```sql
created_by_id INT        -- Менеджер що створив картку (вже було)
prepared_by_id INT       -- Реквізитор що підготував (NEW!)
issued_by_id INT         -- Реквізитор що видав клієнту (NEW!)
received_by_id INT       -- Реквізитор що прийняв повернення
checked_by_id INT        -- Хто перевірив стан товару
prepared_at TIMESTAMP    -- Коли підготовлено (вже було)
issued_at TIMESTAMP      -- Коли видано (вже було)
received_at TIMESTAMP    -- Коли прийнято
```

### **3. PRODUCT_DAMAGE_HISTORY**
```sql
created_by_id INT        -- Хто зафіксував пошкодження
```

### **4. FINANCE_TRANSACTIONS**
```sql
created_by_id INT        -- Хто нарахував/прийняв оплату
```

---

## 📦 Нова Таблиця: ORDER_ITEM_PACKING

**Призначення:** Трекінг комплектації - хто що пакував (кілька реквізиторів можуть збирати одне замовлення)

```sql
CREATE TABLE order_item_packing (
    id VARCHAR(36) PRIMARY KEY,
    order_id INT NOT NULL,
    item_id VARCHAR(100) NOT NULL,
    product_id INT NOT NULL,
    sku VARCHAR(50) NOT NULL,
    product_name VARCHAR(255),
    quantity INT NOT NULL,              -- Кількість що запакував
    packed_by_id INT NOT NULL,          -- Реквізитор що запакував
    packed_by_name VARCHAR(100),        -- Імʼя реквізитора
    packed_at TIMESTAMP,                -- Коли запаковано
    location VARCHAR(100),              -- Локація (zone-aisle-shelf)
    notes TEXT,                         -- Примітки
    
    INDEX idx_order_id (order_id),
    INDEX idx_packed_by (packed_by_id),
    INDEX idx_sku (sku)
)
```

**Приклад використання:**
```
Order #7050 - Збирають 3 реквізитори:

ID   | SKU    | Product     | Qty | Packed By | Location
-----|--------|-------------|-----|-----------|----------
1    | VA2768 | Колба       | 10  | Іван (12) | A-05-03
2    | TY8423 | Столик      | 2   | Петро (15)| B-12-01
3    | GR1001 | Гірлянда    | 5   | Іван (12) | A-05-03
4    | VA2768 | Колба       | 5   | Ольга (18)| A-05-03

→ Іван запакував 15 шт (Колба 10 + Гірлянда 5)
→ Петро запакував 2 шт (Столик)
→ Ольга запакувала 5 шт (Колба)
```

---

## 🔗 Індекси для Швидкого Пошуку

```sql
-- Orders
idx_created_by (created_by_id)
idx_confirmed_by (confirmed_by_id)

-- Issue Cards
idx_created_by (created_by_id)
idx_prepared_by (prepared_by_id)
idx_issued_by (issued_by_id)

-- Damage History
idx_created_by_id (created_by_id)

-- Finance Transactions
idx_created_by_id (created_by_id)
```

---

## 📝 Наступні Кроки (Backend):

### **1. Додати middleware для отримання current_user:**

```python
# /app/backend/utils/auth.py
async def get_current_user(authorization: str = Header(None)):
    if not authorization:
        raise HTTPException(401, "Unauthorized")
    
    token = authorization.replace("Bearer ", "")
    # Декодувати JWT token
    user_data = decode_jwt(token)
    
    return {
        "id": user_data["user_id"],
        "name": user_data["name"],
        "email": user_data["email"],
        "role": user_data["role"]
    }
```

### **2. Оновити endpoints для збереження user_id:**

```python
# При створенні замовлення
@router.post("/api/orders")
async def create_order(
    data: dict, 
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_rh_db)
):
    db.execute(text("""
        INSERT INTO orders (..., created_by_id)
        VALUES (..., :user_id)
    """), {
        "user_id": current_user["id"]
    })

# При підтвердженні
@router.post("/api/orders/{order_id}/confirm")
async def confirm_order(..., current_user):
    db.execute(text("""
        UPDATE orders 
        SET confirmed_by_id = :user_id,
            confirmed_at = NOW()
        WHERE order_id = :order_id
    """), {"user_id": current_user["id"]})

# При комплектації товару
@router.post("/api/orders/{order_id}/pack-item")
async def pack_item(
    order_id: int,
    item_data: dict,
    current_user: dict = Depends(get_current_user)
):
    db.execute(text("""
        INSERT INTO order_item_packing 
        (id, order_id, item_id, product_id, sku, product_name, 
         quantity, packed_by_id, packed_by_name, location)
        VALUES (UUID(), :order_id, :item_id, :product_id, :sku, 
                :product_name, :qty, :user_id, :user_name, :location)
    """), {
        "order_id": order_id,
        "item_id": item_data["item_id"],
        "product_id": item_data["product_id"],
        "sku": item_data["sku"],
        "product_name": item_data["product_name"],
        "qty": item_data["quantity"],
        "user_id": current_user["id"],
        "user_name": current_user["name"],
        "location": item_data.get("location")
    })

# При видачі
@router.post("/api/issue-cards/{card_id}/issue")
async def issue_to_client(..., current_user):
    db.execute(text("""
        UPDATE issue_cards
        SET issued_by_id = :user_id,
            issued_at = NOW(),
            status = 'issued'
        WHERE id = :card_id
    """), {"user_id": current_user["id"]})
```

### **3. API для отримання історії:**

```python
@router.get("/api/orders/{order_id}/history")
async def get_order_history(order_id: int, db: Session = Depends(get_rh_db)):
    """Повна історія хто що робив з замовленням"""
    
    result = db.execute(text("""
        SELECT 
            'created' as action,
            u.name as user_name,
            o.created_at as action_at
        FROM orders o
        LEFT JOIN users u ON o.created_by_id = u.id
        WHERE o.order_id = :order_id
        
        UNION ALL
        
        SELECT 
            'confirmed',
            u.name,
            o.confirmed_at
        FROM orders o
        LEFT JOIN users u ON o.confirmed_by_id = u.id
        WHERE o.order_id = :order_id AND o.confirmed_at IS NOT NULL
        
        UNION ALL
        
        SELECT 
            CONCAT('packed_', oip.sku),
            u.name,
            oip.packed_at
        FROM order_item_packing oip
        LEFT JOIN users u ON oip.packed_by_id = u.id
        WHERE oip.order_id = :order_id
        
        ORDER BY action_at
    """), {"order_id": order_id})
    
    return [{"action": row[0], "user": row[1], "at": row[2]} for row in result]
```

---

## 📋 Наступні Кроки (Frontend):

### **1. Показувати хто працював:**

```jsx
// Issue Card
<div className="text-sm text-slate-600">
  <div>Створено: {order.created_by_name}</div>
  <div>Підтверджено: {order.confirmed_by_name}</div>
  <div>Зібрано: {card.prepared_by_name}</div>
  <div>Видано: {card.issued_by_name}</div>
</div>
```

### **2. Timeline/Історія:**

```jsx
<Timeline>
  {history.map(item => (
    <TimelineItem
      key={item.id}
      user={item.user_name}
      action={item.action}
      timestamp={item.at}
    />
  ))}
</Timeline>
```

### **3. Комплектація - показувати хто що запакував:**

```jsx
<PackingList orderId={orderId}>
  {packingItems.map(item => (
    <PackingItem>
      {item.product_name} x{item.quantity}
      <Badge>{item.packed_by_name}</Badge>
      <span>{item.location}</span>
    </PackingItem>
  ))}
</PackingList>
```

---

## ✅ Статус:

**Міграція БД:** ✅ ЗАВЕРШЕНО  
**Backend API:** ⏳ Потребує реалізації  
**Frontend UI:** ⏳ Потребує реалізації

**Час реалізації:** 2-3 дні backend + 2-3 дні frontend = **4-6 днів**

