# 📋 EVENT TOOL INTEGRATION - TODO LIST ДЛЯ НАСТУПНОГО АГЕНТА

## ✅ ЩО ВЖЕ ЗРОБЛЕНО

### 1. Аналіз і Документація ✅
- ✅ Детальний аналіз API conflicts
- ✅ Логічне розділення контексту (Manager vs Customer)
- ✅ План міграцій БД
- ✅ Документація для інтеграції

### 2. SQL Міграції ✅
- ✅ `001_modify_customers_table.sql` - додає password_hash, is_active, email_verified, last_login
- ✅ `002_create_event_boards.sql` - таблиця для event boards
- ✅ `003_create_event_board_items.sql` - товари в boards
- ✅ `004_create_soft_reservations.sql` - тимчасові резервації

### 3. Файли Event Tool ✅
- ✅ Event Tool склоновано в `/tmp/event-tool/`
- ✅ Проаналізовано структуру

---

## 🚀 ЩО ТРЕБА ЗРОБИТИ (Покроковий план)

### КРОК 1: Запустити міграції БД

**Завдання:** Додати нові таблиці в продакшн БД

**Файли:** 
- `/app/backend/migrations/001_modify_customers_table.sql`
- `/app/backend/migrations/002_create_event_boards.sql`
- `/app/backend/migrations/003_create_event_board_items.sql`
- `/app/backend/migrations/004_create_soft_reservations.sql`

**Команди:**
```bash
# На продакшн сервері
mysql -h farforre.mysql.tools -u farforre_rentalhub -p farforre_rentalhub < 001_modify_customers_table.sql
mysql -h farforre.mysql.tools -u farforre_rentalhub -p farforre_rentalhub < 002_create_event_boards.sql
mysql -h farforre.mysql.tools -u farforre_rentalhub -p farforre_rentalhub < 003_create_event_board_items.sql
mysql -h farforre.mysql.tools -u farforre_rentalhub -p farforre_rentalhub < 004_create_soft_reservations.sql
```

**Перевірка:**
```sql
-- Перевірити нові колонки в customers
DESCRIBE customers;

-- Перевірити нові таблиці
SHOW TABLES LIKE 'event_%';
SHOW TABLES LIKE 'soft_reservations';

-- Має вивести:
-- event_boards
-- event_board_items
-- soft_reservations
```

---

### КРОК 2: Створити Customer Auth routes

**Завдання:** Створити authentication для клієнтів

**Файл:** `/app/backend/routes/customer_auth.py`

**Що має бути:**
```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timedelta
import bcrypt
import jwt

router = APIRouter()

# POST /api/customer/auth/register
# POST /api/customer/auth/login
# GET /api/customer/auth/me
# POST /api/customer/auth/logout
```

**Ключові моменти:**
- Використовувати bcrypt для паролів
- JWT токени з `role: "customer"`
- Зберігати в `customers` table
- last_login оновлювати при логіні

**Джерело коду:** 
- `/tmp/event-tool/backend/server.py` - лінії 77-145
- `/tmp/event-tool/backend/auth.py`

---

### КРОК 3: Створити Public Catalog routes

**Завдання:** Публічний каталог товарів (read-only для клієнтів)

**Файл:** `/app/backend/routes/public_catalog.py`

**Що має бути:**
```python
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import List, Optional

router = APIRouter()

# GET /api/public/categories - всі категорії
# GET /api/public/subcategories - підкатегорії по category_id
# GET /api/public/products - список товарів з фільтрами
# GET /api/public/products/{product_id} - деталі товару
# POST /api/public/products/check-availability - перевірка доступності
```

**Ключові моменти:**
- READ-ONLY доступ
- Фільтрувати: `quantity > 0`, `status = 1`
- Використовувати існуючу таблицю `products`
- Розрахунки доступності враховуючи резервації

**Джерело коду:**
- `/tmp/event-tool/backend/server.py` - лінії 148-432

---

### КРОК 4: Створити Customer Boards routes

**Завдання:** Event boards для планування подій

**Файл:** `/app/backend/routes/customer_boards.py`

**Що має бути:**
```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, delete
from typing import List

router = APIRouter()

# GET /api/customer/boards - всі boards клієнта
# POST /api/customer/boards - створити board
# GET /api/customer/boards/{board_id} - деталі board
# PATCH /api/customer/boards/{board_id} - оновити board
# DELETE /api/customer/boards/{board_id} - видалити board

# POST /api/customer/boards/{board_id}/items - додати товар
# PATCH /api/customer/boards/{board_id}/items/{item_id} - оновити товар
# DELETE /api/customer/boards/{board_id}/items/{item_id} - видалити товар
```

**Ключові моменти:**
- JWT authentication обов'язкова
- Клієнт бачить тільки свої boards (`customer_id = current_user.id`)
- При додаванні товару перевіряти доступність
- Створювати soft_reservations при додаванні товару

**Джерело коду:**
- `/tmp/event-tool/backend/server.py` - лінії 433-1048

---

### КРОК 5: Створити Customer Orders routes

**Завдання:** Конвертація board в замовлення

**Файл:** `/app/backend/routes/customer_orders.py`

**Що має бути:**
```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

router = APIRouter()

# POST /api/customer/orders/create-from-board
```

**Ключові моменти:**
- Перевірити чи board належить клієнту
- Перевірити доступність всіх товарів
- Створити order в таблиці `orders`
- Створити order_items для кожного товару
- Видалити soft_reservations
- Оновити статус board на 'converted'

**Джерело коду:**
- `/tmp/event-tool/backend/server.py` - лінії 1050-1229
- `/app/backend/routes/event_tool_integration.py` - існуюча логіка

---

### КРОК 6: Додати routes в server.py

**Завдання:** Зареєструвати нові routes

**Файл:** `/app/backend/server.py`

**Додати після існуючих routes:**
```python
# Import нові routes
from routes import customer_auth, public_catalog, customer_boards, customer_orders

# Додати в app
app.include_router(customer_auth.router, prefix="/api/customer/auth", tags=["Customer Auth"])
app.include_router(public_catalog.router, prefix="/api/public", tags=["Public Catalog"])
app.include_router(customer_boards.router, prefix="/api/customer/boards", tags=["Event Boards"])
app.include_router(customer_orders.router, prefix="/api/customer/orders", tags=["Customer Orders"])
```

---

### КРОК 7: Оновити CORS

**Завдання:** Дозволити запити з Event Tool фронтенду

**Файл:** `/app/backend/.env` (на продакшні)

**Додати:**
```bash
CORS_ORIGINS=https://rentalhub.farforrent.com.ua,https://events.farforrent.com.ua
```

**Перезапустити backend:**
```bash
sudo supervisorctl restart rentalhub-backend
```

---

### КРОК 8: Налаштувати Event Tool Frontend

**Завдання:** Підготувати фронтенд для deploy

**Файли:**
- Event Tool вже в `/tmp/event-tool/frontend/`

**Що треба зробити:**

1. **Скопіювати в робочу директорію:**
```bash
cp -r /tmp/event-tool/frontend /app/event-tool-frontend
```

2. **Оновити .env:**
```bash
# /app/event-tool-frontend/.env
REACT_APP_BACKEND_URL=https://backrentalhub.farforrent.com.ua
```

3. **Оновити всі API calls:**
```javascript
// Знайти всі файли з API calls
grep -r "api/" /app/event-tool-frontend/src/

// Оновити URL:
// Було: /api/auth/login
// Стало: /api/customer/auth/login

// Було: /api/products
// Стало: /api/public/products

// Було: /api/boards
// Стало: /api/customer/boards
```

4. **Build:**
```bash
cd /app/event-tool-frontend
yarn install
yarn build
```

5. **Результат:** `/app/event-tool-frontend/build/`

---

### КРОК 9: Deploy Event Tool Frontend

**Завдання:** Розмістити фронтенд на піддомені

**Файли:** `/app/event-tool-frontend/build/`

**Де розмістити:** `events.farforrent.com.ua`

**Як:**
- Upload всі файли з `build/` папки на хостинг
- Налаштувати піддомен `events.farforrent.com.ua`
- Вказати на папку з build файлами

---

### КРОК 10: Тестування

**Завдання:** Перевірити всі flow

**Тести:**

1. **Customer Registration:**
```bash
curl -X POST https://backrentalhub.farforrent.com.ua/api/customer/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@test.com",
    "password": "password123",
    "firstname": "Test",
    "lastname": "User",
    "telephone": "+380123456789"
  }'
```

2. **Customer Login:**
```bash
curl -X POST https://backrentalhub.farforrent.com.ua/api/customer/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@test.com",
    "password": "password123"
  }'
  
# Збережи JWT токен
```

3. **Get Products:**
```bash
curl https://backrentalhub.farforrent.com.ua/api/public/products?limit=10
```

4. **Create Event Board:**
```bash
curl -X POST https://backrentalhub.farforrent.com.ua/api/customer/boards \
  -H "Authorization: Bearer <JWT_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "board_name": "Моя весілля",
    "event_date": "2025-06-15",
    "guest_count": 50
  }'
```

5. **Add Product to Board:**
```bash
curl -X POST https://backrentalhub.farforrent.com.ua/api/customer/boards/1/items \
  -H "Authorization: Bearer <JWT_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "product_id": 123,
    "quantity": 10
  }'
```

6. **Convert to Order:**
```bash
curl -X POST https://backrentalhub.farforrent.com.ua/api/customer/orders/create-from-board \
  -H "Authorization: Bearer <JWT_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "board_id": 1,
    "rental_start_date": "2025-06-14",
    "rental_end_date": "2025-06-16"
  }'
```

---

## 📚 ДОКУМЕНТАЦІЯ ДЛЯ РОБОТИ

### Основні файли:
- `/app/EVENT_TOOL_INTEGRATION_ANALYSIS.md` - Детальний аналіз
- `/app/EVENT_TOOL_INTEGRATION_TODO.md` - Цей файл (TODO list)
- `/tmp/event-tool/` - Оригінальний Event Tool код
- `/app/backend/migrations/` - SQL міграції

### API Mapping:
```
Event Tool          →  RentalHub Mapped
======================================
POST /api/auth/register              → POST /api/customer/auth/register
POST /api/auth/login                 → POST /api/customer/auth/login
GET /api/auth/me                     → GET /api/customer/auth/me

GET /api/categories                  → GET /api/public/categories
GET /api/products                    → GET /api/public/products
GET /api/products/{id}               → GET /api/public/products/{id}
POST /api/products/check-availability → POST /api/public/products/check-availability

GET /api/boards                      → GET /api/customer/boards
POST /api/boards                     → POST /api/customer/boards
GET /api/boards/{id}                 → GET /api/customer/boards/{id}
PATCH /api/boards/{id}               → PATCH /api/customer/boards/{id}
DELETE /api/boards/{id}              → DELETE /api/customer/boards/{id}

POST /api/boards/{id}/items          → POST /api/customer/boards/{id}/items
PATCH /api/boards/{id}/items/{item_id} → PATCH /api/customer/boards/{id}/items/{item_id}
DELETE /api/boards/{id}/items/{item_id} → DELETE /api/customer/boards/{id}/items/{item_id}

POST /api/boards/{id}/convert-to-order → POST /api/customer/orders/create-from-board
```

### JWT Structure:
```json
// Manager Token (існуючий)
{
  "sub": "user_id",
  "email": "vitokdrako@gmail.com",
  "role": "manager"
}

// Customer Token (новий)
{
  "sub": "customer_id",
  "email": "customer@example.com",
  "role": "customer"
}
```

---

## ⚠️ ВАЖЛИВІ МОМЕНТИ

### НЕ РОБИТИ:
- ❌ НЕ чіпати існуючі manager routes
- ❌ НЕ змінювати таблицю products (тільки читання)
- ❌ НЕ видаляти manager authentication
- ❌ НЕ робити breaking changes в існуючих endpoints

### ОБОВ'ЯЗКОВО:
- ✅ Тестувати кожен крок окремо
- ✅ Перевіряти JWT токени (manager vs customer)
- ✅ Перевіряти CORS для обох фронтендів
- ✅ Робити backup БД перед міграціями
- ✅ Логувати всі дії для debugging

---

## 🎯 КІНЦЕВИЙ РЕЗУЛЬТАТ

Після виконання всіх кроків:

1. ✅ Менеджери працюють на `rentalhub.farforrent.com.ua` (без змін)
2. ✅ Клієнти працюють на `events.farforrent.com.ua` (новий)
3. ✅ Один бекенд `backrentalhub.farforrent.com.ua`
4. ✅ Товари з RentalHub автоматично в Event Tool каталозі
5. ✅ Замовлення з Event Tool видимі менеджерам
6. ✅ Розділення authentication (manager vs customer)
7. ✅ Жодних конфліктів

---

## 📞 ПІДТРИМКА

Якщо виникають питання:
- Дивись `/app/EVENT_TOOL_INTEGRATION_ANALYSIS.md`
- Дивись оригінальний код в `/tmp/event-tool/`
- Перевіряй логи: `tail -f /var/log/rentalhub/error.log`

**Успіху! 🚀**
