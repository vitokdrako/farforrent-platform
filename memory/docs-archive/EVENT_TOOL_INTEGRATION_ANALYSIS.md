# 📊 ДЕТАЛЬНИЙ АНАЛІЗ ІНТЕГРАЦІЇ EVENT TOOL → RENTAL HUB

## 🎯 МЕТА
Інтегрувати Event Tool (клієнтський інтерфейс) в RentalHub (менеджерська система) з спільною БД та єдиним backend.

---

## 📋 ПОТОЧНА СИТУАЦІЯ

### RentalHub (Менеджерська система)
- **Frontend:** `rentalhub.farforrent.com.ua`
- **Backend:** `backrentalhub.farforrent.com.ua`
- **БД:** `farforre_rentalhub` (MySQL)
- **Користувачі:** Менеджери (витokdrako@gmail.com)
- **Функції:** Управління замовленнями, інвентар, фінанси, аудит

### Event Tool (Клієнтська система)
- **Frontend:** Потрібно deploy на `events.farforrent.com.ua`
- **Backend:** Буде інтегровано в RentalHub
- **БД:** Використовує ту ж `farforre_rentalhub`
- **Користувачі:** Клієнти (реєстрація/логін)
- **Функції:** Перегляд каталогу, створення event boards, замовлення

---

## 🔍 АНАЛІЗ API ENDPOINTS

### 1. КОНФЛІКТИ ROUTES (Однакові URL, різна логіка)

#### ❌ КРИТИЧНІ КОНФЛІКТИ:

| Route | RentalHub | Event Tool | Конфлікт |
|-------|-----------|------------|----------|
| `GET /api/products` | ❌ Немає | ✅ Список товарів | ✅ OK - додамо |
| `GET /api/categories` | `/api/admin/categories` | ✅ Список категорій | ✅ OK - різні префікси |
| `POST /api/auth/login` | ✅ Менеджери | ✅ Клієнти | ⚠️ КОНФЛІКТ |
| `GET /api/auth/me` | ✅ Менеджер info | ✅ Клієнт info | ⚠️ КОНФЛІКТ |

#### ✅ НОВІ ROUTES (Без конфліктів):

| Route | Event Tool | Призначення |
|-------|------------|-------------|
| `POST /api/auth/register` | ✅ | Реєстрація клієнтів |
| `GET /api/subcategories` | ✅ | Підкатегорії |
| `GET /api/products/{product_id}` | ✅ | Деталі товару |
| `POST /api/products/check-availability` | ✅ | Перевірка доступності |
| `GET /api/boards` | ✅ | Event boards клієнта |
| `POST /api/boards` | ✅ | Створити board |
| `GET /api/boards/{board_id}` | ✅ | Деталі board |
| `PATCH /api/boards/{board_id}` | ✅ | Оновити board |
| `DELETE /api/boards/{board_id}` | ✅ | Видалити board |
| `POST /api/boards/{board_id}/items` | ✅ | Додати товар в board |
| `PATCH /api/boards/{board_id}/items/{item_id}` | ✅ | Оновити товар |
| `DELETE /api/boards/{board_id}/items/{item_id}` | ✅ | Видалити товар |
| `POST /api/boards/{board_id}/convert-to-order` | ✅ | Конвертувати в замовлення |

---

## 🗂️ АНАЛІЗ СХЕМИ БД

### Існуючі таблиці (RentalHub):
```sql
- products              ✅ (товари)
- categories            ✅ (категорії)
- orders                ✅ (замовлення)
- order_items           ✅ (товари в замовленні)
- customers             ⚠️ (OpenCart клієнти, без паролів)
- users                 ✅ (менеджери)
```

### Нові таблиці (Event Tool):
```sql
- customers             ⚠️ КОНФЛІКТ - потрібна модифікація
- event_boards          ✅ НОВА
- event_board_items     ✅ НОВА
- soft_reservations     ✅ НОВА
- product_reservations  ⚠️ Можливо вже є?
```

### РІШЕННЯ ДЛЯ CUSTOMERS TABLE:

Існуюча таблиця `customers` синхронізується з OpenCart і не має `password_hash`.

**Варіант 1 (РЕКОМЕНДУЮ ✅):** Додати колонку `password_hash`
```sql
ALTER TABLE customers ADD COLUMN password_hash VARCHAR(255);
ALTER TABLE customers ADD COLUMN is_active BOOLEAN DEFAULT TRUE;
ALTER TABLE customers ADD COLUMN email_verified BOOLEAN DEFAULT FALSE;
ALTER TABLE customers ADD COLUMN last_login DATETIME;
```

**Варіант 2:** Створити окрему таблицю `event_customers`
- Недолік: дублювання даних

---

## 🎨 ЛОГІЧНЕ РОЗДІЛЕННЯ КОНТЕКСТУ

### СТРАТЕГІЯ: ПРЕФІКСИ + AUTHENTICATION

```
┌─────────────────────────────────────────────────────────┐
│                    SHARED BACKEND                        │
│            backrentalhub.farforrent.com.ua               │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  MANAGER CONTEXT (JWT: role=manager)                    │
│  ├── /api/manager/*        Менеджерські функції         │
│  ├── /api/inventory/*      Інвентар                     │
│  ├── /api/finance/*        Фінанси                      │
│  ├── /api/audit/*          Аудит                        │
│  ├── /api/admin/*          Адмін панель                 │
│  └── /api/auth/login       Логін менеджерів             │
│                                                          │
│  CUSTOMER CONTEXT (JWT: role=customer)                  │
│  ├── /api/customer/auth/*  Реєстрація/Логін клієнтів   │
│  ├── /api/customer/products/* Каталог (read-only)       │
│  ├── /api/customer/boards/*   Event boards              │
│  ├── /api/customer/orders/*   Замовлення клієнтів       │
│  └── /api/customer/profile    Профіль клієнта           │
│                                                          │
│  PUBLIC CONTEXT (No auth)                               │
│  ├── /api/public/categories   Категорії                 │
│  ├── /api/public/products     Каталог (read-only)       │
│  └── /api/health              Healthcheck                │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

---

## 📝 MAPPING EVENT TOOL → RENTALHUB

### AUTHENTICATION:

| Event Tool Route | RentalHub Mapped Route | Auth |
|------------------|------------------------|------|
| `POST /api/auth/register` | `POST /api/customer/auth/register` | None |
| `POST /api/auth/login` | `POST /api/customer/auth/login` | None |
| `GET /api/auth/me` | `GET /api/customer/auth/me` | JWT (customer) |

### CATALOG:

| Event Tool Route | RentalHub Mapped Route | Auth |
|------------------|------------------------|------|
| `GET /api/categories` | `GET /api/public/categories` | None |
| `GET /api/subcategories` | `GET /api/public/subcategories` | None |
| `GET /api/products` | `GET /api/public/products` | None |
| `GET /api/products/{id}` | `GET /api/public/products/{id}` | None |
| `POST /api/products/check-availability` | `POST /api/public/products/check-availability` | None |

### EVENT BOARDS:

| Event Tool Route | RentalHub Mapped Route | Auth |
|------------------|------------------------|------|
| `GET /api/boards` | `GET /api/customer/boards` | JWT (customer) |
| `POST /api/boards` | `POST /api/customer/boards` | JWT (customer) |
| `GET /api/boards/{id}` | `GET /api/customer/boards/{id}` | JWT (customer) |
| `PATCH /api/boards/{id}` | `PATCH /api/customer/boards/{id}` | JWT (customer) |
| `DELETE /api/boards/{id}` | `DELETE /api/customer/boards/{id}` | JWT (customer) |
| `POST /api/boards/{id}/items` | `POST /api/customer/boards/{id}/items` | JWT (customer) |
| `PATCH /api/boards/{id}/items/{item_id}` | `PATCH /api/customer/boards/{id}/items/{item_id}` | JWT (customer) |
| `DELETE /api/boards/{id}/items/{item_id}` | `DELETE /api/customer/boards/{id}/items/{item_id}` | JWT (customer) |

### ORDERS:

| Event Tool Route | RentalHub Mapped Route | Auth |
|------------------|------------------------|------|
| `POST /api/boards/{id}/convert-to-order` | `POST /api/customer/orders/create-from-board` | JWT (customer) |

---

## 🔐 AUTHENTICATION STRATEGY

### Два типи JWT токенів:

#### 1. Manager JWT
```json
{
  "sub": "user_id",
  "email": "vitokdrako@gmail.com",
  "role": "manager",
  "permissions": ["all"]
}
```
- Виданий через `/api/auth/login` (існуючий)
- Доступ до всіх `/api/manager/*`, `/api/inventory/*`, etc.

#### 2. Customer JWT
```json
{
  "sub": "customer_id",
  "email": "customer@example.com",
  "role": "customer",
  "permissions": ["read_catalog", "manage_boards", "create_orders"]
}
```
- Виданий через `/api/customer/auth/login`
- Доступ тільки до `/api/customer/*` та `/api/public/*`

### Middleware для перевірки ролей:
```python
def require_role(required_role: str):
    def decorator(func):
        async def wrapper(*args, current_user=None, **kwargs):
            if current_user.role != required_role:
                raise HTTPException(403, "Access denied")
            return await func(*args, current_user=current_user, **kwargs)
        return wrapper
    return decorator
```

---

## 📊 DATA FLOW: Products → Event Tool Catalog

### 1. Products створюються/оновлюються в RentalHub:
```
Менеджер → RentalHub UI → POST /api/inventory/products
                              ↓
                         products table
```

### 2. Products автоматично доступні в Event Tool:
```
Клієнт → Event Tool UI → GET /api/public/products
                              ↓
                         products table (read-only)
                              ↓
                         Відфільтровані (quantity > 0, status = active)
```

### Єдине джерело правди:
- ✅ `products` table в БД
- ✅ Менеджери змінюють через RentalHub
- ✅ Клієнти читають через Event Tool
- ✅ Синхронізація автоматична (одна БД)

---

## 🗃️ МІГРАЦІЇ БД

### Файли міграцій для Event Tool:

#### 1. `001_modify_customers_table.sql`
```sql
-- Додати поля для Event Tool authentication
ALTER TABLE customers 
ADD COLUMN password_hash VARCHAR(255),
ADD COLUMN is_active BOOLEAN DEFAULT TRUE,
ADD COLUMN email_verified BOOLEAN DEFAULT FALSE,
ADD COLUMN last_login DATETIME;

-- Індекс для швидкого пошуку
CREATE INDEX idx_customers_email ON customers(email);
```

#### 2. `002_create_event_boards.sql`
```sql
CREATE TABLE event_boards (
    board_id INT PRIMARY KEY AUTO_INCREMENT,
    customer_id INT NOT NULL,
    board_name VARCHAR(255) NOT NULL,
    event_date DATE,
    event_location VARCHAR(500),
    guest_count INT,
    notes TEXT,
    status VARCHAR(50) DEFAULT 'draft',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id) ON DELETE CASCADE,
    INDEX idx_customer (customer_id),
    INDEX idx_status (status)
);
```

#### 3. `003_create_event_board_items.sql`
```sql
CREATE TABLE event_board_items (
    item_id INT PRIMARY KEY AUTO_INCREMENT,
    board_id INT NOT NULL,
    product_id INT NOT NULL,
    quantity INT NOT NULL,
    notes TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (board_id) REFERENCES event_boards(board_id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products(product_id),
    INDEX idx_board (board_id),
    INDEX idx_product (product_id)
);
```

#### 4. `004_create_soft_reservations.sql`
```sql
CREATE TABLE soft_reservations (
    reservation_id INT PRIMARY KEY AUTO_INCREMENT,
    board_id INT NOT NULL,
    product_id INT NOT NULL,
    quantity INT NOT NULL,
    reserved_until DATETIME NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (board_id) REFERENCES event_boards(board_id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products(product_id),
    INDEX idx_board (board_id),
    INDEX idx_product (product_id),
    INDEX idx_expiry (reserved_until)
);
```

---

## 🚀 ПЛАН ІНТЕГРАЦІЇ (Покрокова інструкція для агента)

### PHASE 1: ПІДГОТОВКА БД ✅

**Крок 1.1:** Запустити міграції
```bash
cd /app/backend
python apply_migration.py 001_modify_customers_table.sql
python apply_migration.py 002_create_event_boards.sql
python apply_migration.py 003_create_event_board_items.sql
python apply_migration.py 004_create_soft_reservations.sql
```

**Крок 1.2:** Перевірити структуру
```bash
python check_mysql_structure.py
```

---

### PHASE 2: BACKEND ІНТЕГРАЦІЯ ✅

**Крок 2.1:** Створити нову структуру routes
```
/app/backend/routes/
├── customer_auth.py       # Реєстрація/Логін клієнтів
├── public_catalog.py      # Публічний каталог
├── customer_boards.py     # Event boards
└── customer_orders.py     # Замовлення клієнтів
```

**Крок 2.2:** Скопіювати Event Tool models
```bash
cp /tmp/event-tool/backend/models.py /app/backend/models/event_tool_models.py
```

**Крок 2.3:** Створити middleware для ролей
```python
# /app/backend/middleware/auth_roles.py
```

**Крок 2.4:** Додати routes в server.py
```python
# /app/backend/server.py
from routes import customer_auth, public_catalog, customer_boards, customer_orders

# Customer routes
app.include_router(customer_auth.router, prefix="/api/customer/auth", tags=["Customer Auth"])
app.include_router(public_catalog.router, prefix="/api/public", tags=["Public Catalog"])
app.include_router(customer_boards.router, prefix="/api/customer/boards", tags=["Event Boards"])
app.include_router(customer_orders.router, prefix="/api/customer/orders", tags=["Customer Orders"])
```

---

### PHASE 3: FRONTEND НАЛАШТУВАННЯ ✅

**Крок 3.1:** Скопіювати Event Tool frontend
```bash
cp -r /tmp/event-tool/frontend /app/event-tool-frontend
```

**Крок 3.2:** Оновити API URL в .env
```bash
# /app/event-tool-frontend/.env
REACT_APP_BACKEND_URL=https://backrentalhub.farforrent.com.ua
```

**Крок 3.3:** Оновити всі API calls з новими префіксами
```javascript
// Було: /api/auth/login
// Стало: /api/customer/auth/login

// Було: /api/products
// Стало: /api/public/products

// Було: /api/boards
// Стало: /api/customer/boards
```

**Крок 3.4:** Build для production
```bash
cd /app/event-tool-frontend
yarn build
```

---

### PHASE 4: CORS НАЛАШТУВАННЯ ✅

**Крок 4.1:** Оновити .env backend
```bash
# /app/backend/.env
CORS_ORIGINS=https://rentalhub.farforrent.com.ua,https://events.farforrent.com.ua
```

**Крок 4.2:** Restart backend
```bash
sudo supervisorctl restart rentalhub-backend
```

---

### PHASE 5: DEPLOYMENT ✅

**Крок 5.1:** Deploy Event Tool frontend
- Upload `/app/event-tool-frontend/build/` → `events.farforrent.com.ua`

**Крок 5.2:** Перевірка
1. Зайти на `https://events.farforrent.com.ua`
2. Зареєструвати нового клієнта
3. Створити event board
4. Додати товари з каталогу
5. Конвертувати в замовлення

---

## ⚠️ КРИТИЧНІ МОМЕНТИ ДЛЯ АГЕНТА

### 🔴 ОБОВ'ЯЗКОВО:

1. **НЕ ЧІПАТИ існуючі routes** - додавати тільки нові з префіксами
2. **НЕ ЗМІНЮВАТИ products table** - тільки читання для Event Tool
3. **ТЕСТУВАТИ authentication** - manager і customer токени не повинні конфліктувати
4. **ПЕРЕВІРЯТИ CORS** - обидва фронтенди повинні працювати

### ✅ ПЕРЕВІРКИ:

```bash
# 1. Менеджер логін працює
curl -X POST https://backrentalhub.farforrent.com.ua/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"vitokdrako@gmail.com","password":"test123"}'

# 2. Клієнт логін працює
curl -X POST https://backrentalhub.farforrent.com.ua/api/customer/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"customer@test.com","password":"password123"}'

# 3. Публічний каталог працює
curl https://backrentalhub.farforrent.com.ua/api/public/products

# 4. Event boards працює (з JWT)
curl -H "Authorization: Bearer <CUSTOMER_JWT>" \
  https://backrentalhub.farforrent.com.ua/api/customer/boards
```

---

## 📁 СТРУКТУРА ФАЙЛІВ ДЛЯ АГЕНТА

### Файли які треба створити:

```
/app/backend/
├── migrations/
│   ├── 001_modify_customers_table.sql
│   ├── 002_create_event_boards.sql
│   ├── 003_create_event_board_items.sql
│   └── 004_create_soft_reservations.sql
├── models/
│   └── event_tool_models.py
├── routes/
│   ├── customer_auth.py
│   ├── public_catalog.py
│   ├── customer_boards.py
│   └── customer_orders.py
└── middleware/
    └── auth_roles.py

/app/event-tool-frontend/
├── src/
│   ├── api/
│   │   └── client.js  (оновити URL)
│   └── ...
├── .env (REACT_APP_BACKEND_URL)
└── build/ (після yarn build)
```

---

## 🎯 КІНЦЕВИЙ РЕЗУЛЬТАТ

### Після інтеграції:

1. ✅ Менеджери працюють на `rentalhub.farforrent.com.ua`
2. ✅ Клієнти працюють на `events.farforrent.com.ua`
3. ✅ Обидва використовують один бекенд `backrentalhub.farforrent.com.ua`
4. ✅ Товари автоматично синхронізуються
5. ✅ Замовлення з Event Tool видимі менеджерам
6. ✅ Жодних конфліктів routes або authentication

---

## 📞 ПІДТРИМКА

Якщо виникають проблеми:
1. Перевірити логи backend: `tail -f /var/log/rentalhub/error.log`
2. Перевірити CORS: F12 → Console в браузері
3. Перевірити JWT токени: jwt.io
4. Перевірити БД: `SHOW TABLES LIKE 'event_%';`

---

**Дата створення:** 2025-12-01  
**Версія:** 1.0  
**Автор:** E1 AI Agent
