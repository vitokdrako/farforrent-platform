# Phase 1 — Multi-Warehouse Core (детальний план)

**Scope**: створити фундамент multi-warehouse БЕЗ EU вітрини поки.
Після Phase 1 система працюватиме так само як зараз (одна вітрина UA),
але код і БД готові приймати EU вітрину одним INSERT.

**Таймлайн**: 3-4 робочі дні  
**Ризик**: 🟢 Низький — всі зміни additive, старий код продовжує працювати

---

## 📁 Файли що з'являться / зміняться

### SQL міграції
- 🆕 `backend/migrations/add_warehouses_multi_v1.sql` — таблиці + seed UA

### Backend
- 🆕 `backend/routes/warehouses.py` — CRUD складів + stock per warehouse
- 🆕 `backend/middleware/warehouse_access.py` — перевірка прав на склад (базова)
- ✏️ `backend/server.py` — підключити router + middleware
- ✏️ `backend/routes/products.py` — повертати total stock = SUM(product_warehouses.quantity)
- ✏️ `backend/routes/event_tool.py` — читати storefront_slug з Host header (поки fallback='default')

### Frontend (Admin RentalHub)
- 🆕 `frontend/src/pages/WarehousesPage.tsx` — список + CRUD
- 🆕 `frontend/src/components/WarehouseStockEditor.tsx` — табулятор на картці товару
- ✏️ `frontend/src/App.tsx` — route `/admin/warehouses`
- ✏️ `frontend/src/pages/ProductEditPage.*` — додати вкладку "Склади"
- ✏️ `frontend/src/components/CorporateHeader.tsx` — показувати обраний склад (якщо > 1)

---

## 🗄️ SQL міграція

```sql
-- backend/migrations/add_warehouses_multi_v1.sql
START TRANSACTION;

-- 1. Таблиця складів
CREATE TABLE IF NOT EXISTS warehouses (
  id INT PRIMARY KEY AUTO_INCREMENT,
  code VARCHAR(16) UNIQUE NOT NULL,
  name VARCHAR(255) NOT NULL,
  country VARCHAR(2) NOT NULL,
  city VARCHAR(100),
  address TEXT,
  currency VARCHAR(3) NOT NULL DEFAULT 'UAH',
  timezone VARCHAR(50) DEFAULT 'Europe/Kyiv',
  phone VARCHAR(50),
  email VARCHAR(255),
  is_default BOOLEAN DEFAULT FALSE,
  is_active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- 2. Товар на складі (ключова M2M таблиця)
CREATE TABLE IF NOT EXISTS product_warehouses (
  product_id INT NOT NULL,
  warehouse_id INT NOT NULL,
  quantity INT DEFAULT 0,
  reserved_qty INT DEFAULT 0,
  min_quantity INT DEFAULT 0,
  price_override DECIMAL(10,2) NULL,
  cost_override DECIMAL(10,2) NULL,
  is_available BOOLEAN DEFAULT TRUE,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (product_id, warehouse_id),
  INDEX (warehouse_id),
  INDEX (is_available)
);

-- 3. User → warehouse (базова рольова модель)
CREATE TABLE IF NOT EXISTS user_warehouses (
  user_id INT NOT NULL,
  warehouse_id INT NOT NULL,
  role VARCHAR(32) DEFAULT 'manager',
  PRIMARY KEY (user_id, warehouse_id),
  INDEX (warehouse_id)
);

-- 4. Додати мультимовність на товар (денормалізовано)
ALTER TABLE products
  ADD COLUMN IF NOT EXISTS name_en VARCHAR(500) NULL AFTER name,
  ADD COLUMN IF NOT EXISTS name_es VARCHAR(500) NULL,
  ADD COLUMN IF NOT EXISTS description_en TEXT NULL AFTER description,
  ADD COLUMN IF NOT EXISTS description_es TEXT NULL;

-- 5. Прив'язка замовлень/клієнтів до складу (NULLABLE — беквард-сумісність)
ALTER TABLE orders
  ADD COLUMN IF NOT EXISTS warehouse_id INT NULL AFTER order_number,
  ADD INDEX IF NOT EXISTS idx_orders_warehouse (warehouse_id);

ALTER TABLE client_users
  ADD COLUMN IF NOT EXISTS warehouse_id INT NULL AFTER id,
  ADD INDEX IF NOT EXISTS idx_clients_warehouse (warehouse_id);

ALTER TABLE users
  ADD COLUMN IF NOT EXISTS is_super_admin BOOLEAN DEFAULT FALSE;

-- 6. SEED: Основний склад UA
INSERT INTO warehouses (code, name, country, city, currency, is_default)
VALUES ('UA', 'Київ (основний)', 'UA', 'Київ', 'UAH', TRUE)
ON DUPLICATE KEY UPDATE name = VALUES(name);

SET @ua_id = (SELECT id FROM warehouses WHERE code = 'UA');

-- 7. Копіюємо залишки з products.quantity → product_warehouses
INSERT INTO product_warehouses (product_id, warehouse_id, quantity, is_available)
SELECT product_id, @ua_id, COALESCE(quantity, 0), 1
FROM products
ON DUPLICATE KEY UPDATE quantity = VALUES(quantity);

-- 8. Всі існуючі замовлення → UA
UPDATE orders SET warehouse_id = @ua_id WHERE warehouse_id IS NULL;

-- 9. Всі існуючі клієнти → UA
UPDATE client_users SET warehouse_id = @ua_id WHERE warehouse_id IS NULL;

-- 10. Всі існуючі admin юзери → UA з роллю manager
INSERT IGNORE INTO user_warehouses (user_id, warehouse_id, role)
SELECT user_id, @ua_id, 'manager' FROM users;

-- 11. Головний адмін vitokdrako → super_admin + всі склади
UPDATE users SET is_super_admin = TRUE WHERE email = 'vitokdrako@gmail.com';

COMMIT;

-- Перевірка:
-- SELECT COUNT(*) FROM warehouses;             -- має бути >= 1
-- SELECT COUNT(*) FROM product_warehouses;     -- має == кількість products
-- SELECT COUNT(*) FROM orders WHERE warehouse_id IS NULL; -- має = 0
```

---

## 🔌 Backend API

### `routes/warehouses.py`

| Метод | Endpoint | Опис | Хто може |
|---|---|---|---|
| GET | `/api/admin/warehouses` | список активних складів | super_admin / власники |
| GET | `/api/admin/warehouses/{id}` | деталі складу | super_admin |
| POST | `/api/admin/warehouses` | створити | super_admin |
| PUT | `/api/admin/warehouses/{id}` | редагувати | super_admin |
| DELETE | `/api/admin/warehouses/{id}` | архівувати (is_active=FALSE) | super_admin |
| GET | `/api/admin/products/{id}/stock` | залишки по всіх складах | user з доступом до цього product |
| PUT | `/api/admin/products/{id}/stock/{wh_id}` | оновити залишок | user з доступом |

### Приклад response
```json
GET /api/admin/products/123/stock
{
  "product_id": 123,
  "name": "Ваза Атлантида",
  "sku": "VU-100",
  "warehouses": [
    {"warehouse_id": 1, "code": "UA", "name": "Київ",
     "quantity": 10, "reserved_qty": 2, "min_quantity": 0,
     "price_override": null, "cost_override": 180.0,
     "currency": "UAH", "is_available": true},
    {"warehouse_id": 2, "code": "EU", "name": "Варшава",
     "quantity": 3, "reserved_qty": 0, "min_quantity": 1,
     "price_override": 12.0, "cost_override": 5.0,
     "currency": "EUR", "is_available": true}
  ],
  "total_stock": 13,
  "available_stock": 11
}
```

### Middleware `warehouse_access.py`
```python
async def require_warehouse_access(request, warehouse_id):
    user = request.state.user
    if user.is_super_admin:
        return True
    allowed_ids = [row[0] for row in db.execute(
        text("SELECT warehouse_id FROM user_warehouses WHERE user_id=:uid"),
        {"uid": user.user_id}
    )]
    if warehouse_id not in allowed_ids:
        raise HTTPException(403, "No access to this warehouse")
```

На Phase 1 застосовуємо тільки до `warehouses.py` та `product_warehouses` endpoints.
Інші існуючі ендпоінти (orders, products, issue_cards) — **не чіпаємо** щоб не ламати продакшн. Їх прив'яжемо в Phase 4.

---

## 🎨 Admin UI

### 3.1 Сторінка `/admin/warehouses`
Шлях: `frontend/src/pages/WarehousesPage.tsx`

```
╔════════════════════════════════════════════════════════════════╗
║ Склади                                     [+ Новий склад]     ║
╠════════════════════════════════════════════════════════════════╣
║ [пошук.................]                                       ║
║                                                                ║
║ ┌────┬──────┬──────────────┬─────┬──────┬──────┬──────┬─────┐ ║
║ │ 🇺🇦 │ UA   │ Київ (осн.)  │ UA  │ UAH  │ 7943 │ ✅   │ ✏️  │ ║
║ │ 🇵🇱 │ EU   │ Варшава      │ PL  │ EUR  │ 120  │ ✅   │ ✏️  │ ║
║ └────┴──────┴──────────────┴─────┴──────┴──────┴──────┴─────┘ ║
╚════════════════════════════════════════════════════════════════╝
```

Клік на рядок → sidepanel з деталями:
- Назва, країна, адреса, контакти
- Статистика: товарів, замовлень, оборот/міс
- Кнопка "Переглянути залишки" (список продуктів на цьому складі)

### 3.2 Модалка "Створити склад"
```
┌─ Новий склад ──────────────────────────────┐
│                                            │
│ Код *      : [ EU             ]            │
│ Назва *    : [ Варшава        ]            │
│ Країна *   : [ Польща (PL)  ▼ ]            │
│ Місто      : [ Warsaw         ]            │
│ Адреса     : [ ul. Krakowska… ]            │
│ Валюта *   : [ EUR          ▼ ]            │
│ Часовий п. : [ Europe/Warsaw ▼]            │
│ Телефон    : [ +48 123 456    ]            │
│ Email      : [ eu@farforevent ]            │
│ ☐ Зробити складом за замовчуванням          │
│                                            │
│                      [Скасувати]  [Створити]│
└────────────────────────────────────────────┘
```

### 3.3 Віджет "Склади" на картці товару
Шлях: `frontend/src/components/WarehouseStockEditor.tsx`  
Інтегрується в `ProductEditPage` як нова вкладка.

```
┌─ Залишки по складах ───────────────────────────────────┐
│                                                        │
│ 🇺🇦 UA (Київ, UAH)                        [❌ Прибрати] │
│   ├ Залишок:    [  10 ] шт                             │
│   ├ Броня:      [   2 ]                                │
│   ├ Мін.:       [   0 ]                                │
│   ├ Ціна:       □ Інша: [       ] UAH                  │
│   │             (стандартна: 350 ₴)                    │
│   ├ С-сть:      [ 180 ] UAH                            │
│   └ Доступний на вітрині: ☑                           │
│                                                        │
│ 🇵🇱 EU (Варшава, EUR)                     [❌ Прибрати] │
│   ├ Залишок:    [   3 ] шт                             │
│   ├ Броня:      [   0 ]                                │
│   ├ Мін.:       [   1 ]                                │
│   ├ Ціна:       ☑ Інша: [ 12.00 ] EUR                  │
│   ├ С-сть:      [ 5.00] EUR                            │
│   └ Доступний на вітрині: ☑                           │
│                                                        │
│ [+ Додати на ще один склад]                            │
│                                                        │
│ ─────────────────────────────────────                  │
│ Всього на всіх складах: 13 шт на 2 складах            │
│ Доступно до продажу:    11 шт                          │
│                                                        │
│                             [💾 Зберегти залишки]       │
└────────────────────────────────────────────────────────┘
```

### 3.4 Хедер — перемикач складу (якщо > 1)
```
┌───────────────────────────────────────────────────┐
│ RentalHub   [🇺🇦 UA ▼]   пошук...   🔔 2   👤 Max │
│              ├ 🇺🇦 UA (default)                   │
│              ├ 🇵🇱 EU                             │
│              └ 👁️ Переглянути всі (super_admin)   │
└───────────────────────────────────────────────────┘
```

Вибір складу зберігається в `localStorage.active_warehouse_id`. У Phase 1 — лише візуальний індикатор, фактично не фільтрує дані (щоб не ламати існуючі флоу). У Phase 4 — буде по-справжньому фільтрувати.

---

## 🧪 Test Plan

### API curl тести

```bash
TOKEN=$(curl -s -X POST ... /api/auth/login | jq -r .token)

# 1. Список складів
curl -s -H "Authorization: Bearer $TOKEN" \
  https://farforevent.com.ua/api/admin/warehouses | jq .

# 2. Створити EU склад
curl -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"code":"EU","name":"Варшава","country":"PL","currency":"EUR"}' \
  https://farforevent.com.ua/api/admin/warehouses

# 3. Stock товару
curl -s -H "Authorization: Bearer $TOKEN" \
  https://farforevent.com.ua/api/admin/products/123/stock | jq .

# 4. Оновити stock
curl -X PUT -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"quantity":5,"min_quantity":1}' \
  https://farforevent.com.ua/api/admin/products/123/stock/2
```

### Smoke test (testing_agent)
1. Логін як super_admin
2. Перейти на `/admin/warehouses` → побачити UA
3. Створити EU склад → побачити в списку
4. Відкрити товар → побачити вкладку "Склади" → додати на EU → 3 шт
5. Запросити `/api/admin/products/{id}/stock` → побачити 2 склади
6. Перевірити що існуючі флоу (видача, повернення) не зламалися
7. Logout → login як manager → не бачить "Створити склад"

### Регресія (critical)
- `/api/event/products` на farforevent.com.ua повертає всі товари UA (як було)
- Не змінюється behavior видачі/повернення
- Чати працюють
- Дашборд менеджера показує ті самі дані

---

## 🚨 Rollback Plan

Якщо щось зламається після деплою:
```sql
-- Повернути залишки в products.quantity
UPDATE products p
JOIN product_warehouses pw ON p.product_id = pw.product_id
SET p.quantity = pw.quantity
WHERE pw.warehouse_id = (SELECT id FROM warehouses WHERE code='UA');

-- Dропнути нові таблиці (НЕ рекомендую, краще просто вимкнути code який їх читає)
-- DROP TABLE product_warehouses;
-- DROP TABLE user_warehouses;
-- DROP TABLE warehouses;
```

Також: `.env` можна додати `FEATURE_MULTI_WAREHOUSE=0` щоб миттєво вимкнути нові API без відкату БД.

---

## ✅ Критерії прийому Phase 1

- [ ] SQL міграція пройшла без помилок на production VPS
- [ ] `/admin/warehouses` відкривається, список містить `UA`
- [ ] Можна створити 2-й склад `EU`
- [ ] На картці товару є вкладка "Склади" з редактором
- [ ] Можна виставити залишок товару на EU (без зв'язку з існуючою `products.quantity`)
- [ ] Існуючі флоу (видача, повернення, дашборд) **не зламані**
- [ ] Smoke-test через testing_agent — PASS

---

## 📝 Що робити у наступному кроці

Коли Phase 1 буде готовий і стабільний:
1. **Phase 2** — модалка переміщень + журнал транзитів
2. **Phase 3** — storefronts, перекладу товарів, EU домен
3. **Phase 4** — повноцінне warehouse-scoped RBAC для менеджерів

