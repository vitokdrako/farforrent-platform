# 🔧 RentalHub - Інструкція для агента

## 📋 Огляд проекту
RentalHub - система управління орендою декору та меблів. 
- **Backend:** FastAPI (Python 3.11)
- **Frontend:** React 18 + TailwindCSS
- **Database:** MySQL (farforre_rentalhub на farforre.mysql.tools)

---

## 🗂️ Структура проекту

```
/app
├── backend/
│   ├── server.py              # Головний файл FastAPI
│   ├── routes/
│   │   ├── orders.py          # ⚠️ КРИТИЧНИЙ ФАЙЛ - замовлення та фінанси
│   │   ├── finance.py         # Фінансовий модуль
│   │   ├── catalog.py         # Каталог товарів
│   │   ├── documents.py       # Генерація документів
│   │   └── ...
│   ├── database_rentalhub.py  # Підключення до MySQL
│   ├── requirements.txt
│   └── .env                   # Конфігурація (НЕ копіювати в git!)
│
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── ManagerDashboard.jsx    # Головний дашборд
│   │   │   ├── NewOrderViewWorkspace.jsx # Перегляд/редагування замовлення
│   │   │   ├── CatalogBoard.jsx        # Каталог
│   │   │   └── ...
│   │   └── components/
│   │       └── order-workspace/
│   │           └── zones/
│   │               ├── ZoneItemsPickup.jsx  # Комплектація
│   │               ├── ZoneItemsReturn.jsx  # Повернення
│   │               └── ZoneItemsList.jsx    # Список товарів
│   ├── package.json
│   └── .env
│
└── deployment_v2/             # 📦 ГОТОВИЙ ПАКЕТ ДЛЯ ДЕПЛОЮ
    ├── backend/
    └── frontend_build/
```

---

## ⚙️ Налаштування Backend

### 1. Встановлення залежностей
```bash
cd /app/backend
pip install -r requirements.txt
```

### 2. Конфігурація .env
```env
# База даних RentalHub
DB_HOST=farforre.mysql.tools
DB_PORT=3306
DB_USER=farforre_rentalhub
DB_PASSWORD=-nu+3Gp54L
DB_DATABASE=farforre_rentalhub

# OpenCart (для синхронізації)
OC_DB_HOST=farforre.mysql.tools
OC_DB_USER=farforre_db
OC_DB_PASSWORD=gPpAHTvv
OC_DB_NAME=farforre_db

# MongoDB (локальний)
MONGO_URL=mongodb://localhost:27017
```

### 3. Запуск сервера
```bash
uvicorn server:app --host 0.0.0.0 --port 8001 --reload
```

---

## ⚙️ Налаштування Frontend

### 1. Встановлення залежностей
```bash
cd /app/frontend
yarn install
```

### 2. Конфігурація .env
```env
REACT_APP_BACKEND_URL=http://localhost:8001
# Або для production:
# REACT_APP_BACKEND_URL=https://your-domain.com
```

### 3. Запуск dev сервера
```bash
yarn start
```

### 4. Збірка для production
```bash
yarn build
# Результат в /app/frontend/build/
```

---

## 🔴 КРИТИЧНІ ЗМІНИ (21 січня 2026)

### 1. Фінансова синхронізація - ОБОВ'ЯЗКОВО!

**Файл:** `backend/routes/orders.py`

При редагуванні замовлення фінансові дані (`total_price`, `deposit_amount`) повинні зберігатись в таблиці `orders`.

**Два ендпоінти які були виправлені:**

#### A) PUT /api/decor-orders/{id}
Додано поля до `field_mapping`:
```python
field_mapping = {
    'rental_start_date': 'rental_start_date',
    'rental_end_date': 'rental_end_date',
    'issue_time': 'issue_time',
    'return_time': 'return_time',
    'rental_days': 'rental_days',
    'manager_comment': 'manager_comment',
    'discount': 'discount_amount',
    # ✅ КРИТИЧНО: Фінансові поля
    'total_price': 'total_price',
    'deposit_amount': 'deposit_amount',
    'total_loss_value': 'total_loss_value',
}
```

#### B) PUT /api/decor-orders/{id}/items
При оновленні товарів автоматично перераховуються фінанси:
```python
# Акумулювати фінанси в циклі
total_rent += price_per_day * quantity * rental_days
total_deposit += deposit * quantity

# Після циклу - оновити orders
db.execute(text("""
    UPDATE orders 
    SET total_price = :total_price,
        deposit_amount = :deposit_amount,
        total_loss_value = :deposit_amount
    WHERE order_id = :order_id
"""), {...})
```

### 2. Відображення локації товарів

**Файли:**
- `frontend/src/components/order-workspace/zones/ZoneItemsPickup.jsx`
- `frontend/src/components/order-workspace/zones/ZoneItemsReturn.jsx`
- `frontend/src/components/order-workspace/zones/ZoneItemsList.jsx`

Формат: `📍 Зона: A • Полиця: 7`

Важливо фільтрувати `'None'` і `'null'` значення з бекенду.

### 3. Кнопки "Показати всі" на дашборді

**Файл:** `frontend/src/pages/ManagerDashboard.jsx`

Додано стейти:
```javascript
const [showAllPreparation, setShowAllPreparation] = useState(false);
const [showAllReady, setShowAllReady] = useState(false);
```

---

## 🧪 Тестування

### Тестовий акаунт
- **Email:** vitokdrako@gmail.com
- **Password:** test123

### API тести через curl
```bash
# Логін
TOKEN=$(curl -s -X POST "http://localhost:8001/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"vitokdrako@gmail.com","password":"test123"}' | \
  python3 -c "import sys,json; print(json.load(sys.stdin).get('token',''))")

# Отримати замовлення
curl -s "http://localhost:8001/api/orders?status=awaiting_customer" \
  -H "Authorization: Bearer $TOKEN"

# Тест оновлення замовлення
curl -s -X PUT "http://localhost:8001/api/decor-orders/7236" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"rental_days": 2, "total_price": 4800, "deposit_amount": 20000}'
```

---

## 📦 Деплой

Готовий пакет для деплою знаходиться в `/app/deployment_v2/`:
- `backend/` - повний бекенд
- `frontend_build/` - скомпільований фронтенд

**Production сервер:**
1. Скопіювати `deployment_v2/backend/` на сервер
2. Скопіювати `deployment_v2/frontend_build/` як static files
3. Налаштувати nginx для проксі /api/* на бекенд
4. Перезапустити сервіси

---

## 🗄️ Структура БД (ключові таблиці)

### orders
- `order_id` - PK
- `total_price` - **ДЖЕРЕЛО ПРАВДИ для суми оренди**
- `deposit_amount` - **ДЖЕРЕЛО ПРАВДИ для застави**
- `rental_days` - кількість днів
- `status` - статус замовлення

### order_items
- `order_id` - FK
- `product_id` - FK
- `quantity`
- `price` - ціна за день
- `total_rental` - загальна сума за товар

### products
- `product_id` - PK
- `zone`, `aisle`, `shelf` - локація на складі

---

## ⚠️ Відомі проблеми

1. **Кеш браузера** - після оновлення фронтенду очистіть кеш
2. **`shelf: 'None'`** - бекенд повертає Python None як строку, фронтенд має фільтрувати
3. **Supervisor** - на preview сервері використовується supervisor для управління сервісами

---

## 📞 Контакти

Якщо є питання по коду - перегляньте файли в `/app/deployment_v2/` - це найсвіжіша версія.
