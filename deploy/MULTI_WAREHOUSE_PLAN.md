# Multi-Warehouse + Multi-Storefront для Farfor Rentalhub

**Статус**: 🟡 Проєкт на етапі планування  
**Дата**: 2026-07  
**Відповідальний**: @vitokdrako

## 🎯 Що будуємо

Один RentalHub (адмінка) керує **кількома складами** в різних країнах. Кожен склад обслуговує одну або кілька **вітрин Event Tool** (окремі сайти для клієнтів). Товари можуть лежати на кількох складах одночасно з різною кількістю, ціною та валютою. Admin має рольову модель — "менеджер UA складу" не бачить замовлень EU.

Event Tool стає **мультимовним** (UK/EN/ES перемикач) — одна кодова база, вибір мови з UI або через домен.

---

## 📊 1. Модель даних

### 1.1 Таблиці що з'являться

```sql
-- Склади
CREATE TABLE warehouses (
  id INT PRIMARY KEY AUTO_INCREMENT,
  code VARCHAR(16) UNIQUE NOT NULL,         -- 'UA', 'EU-PL', 'EU-ES'
  name VARCHAR(255) NOT NULL,               -- 'Київ, основний'
  country VARCHAR(2) NOT NULL,              -- 'UA', 'PL'
  city VARCHAR(100),
  address TEXT,
  currency VARCHAR(3) NOT NULL,             -- 'UAH', 'EUR'
  timezone VARCHAR(50) DEFAULT 'Europe/Kyiv',
  phone VARCHAR(50), email VARCHAR(255),
  is_default BOOLEAN DEFAULT FALSE,
  is_active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Товар на складі (M2M з кількістю і ціною)
CREATE TABLE product_warehouses (
  product_id INT NOT NULL,
  warehouse_id INT NOT NULL,
  quantity INT DEFAULT 0,                   -- скільки в наявності
  reserved_qty INT DEFAULT 0,               -- заброньовано
  min_quantity INT DEFAULT 0,               -- мін. залишок (не продавати нижче)
  price_override DECIMAL(10,2) NULL,        -- якщо NULL — беремо products.price
  cost_override DECIMAL(10,2) NULL,         -- собівартість per склад (різні митні витрати)
  is_available BOOLEAN DEFAULT TRUE,        -- показувати на вітрині цього складу
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (product_id, warehouse_id),
  FOREIGN KEY (product_id) REFERENCES products(product_id),
  FOREIGN KEY (warehouse_id) REFERENCES warehouses(id)
);

-- Переміщення між складами (журнал)
CREATE TABLE warehouse_transfers (
  id INT PRIMARY KEY AUTO_INCREMENT,
  product_id INT NOT NULL,
  from_warehouse_id INT NOT NULL,
  to_warehouse_id INT NOT NULL,
  quantity INT NOT NULL,
  status ENUM('draft','in_transit','completed','cancelled') DEFAULT 'draft',
  initiated_by_user_id INT,
  completed_by_user_id INT NULL,
  notes TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  shipped_at TIMESTAMP NULL,
  completed_at TIMESTAMP NULL,
  tracking_number VARCHAR(100) NULL,
  carrier VARCHAR(100) NULL,
  INDEX (status), INDEX (from_warehouse_id), INDEX (to_warehouse_id)
);

-- Вітрини (Event Tool instances)
CREATE TABLE storefronts (
  id INT PRIMARY KEY AUTO_INCREMENT,
  slug VARCHAR(32) UNIQUE NOT NULL,         -- 'default', 'eu'
  name VARCHAR(255) NOT NULL,               -- 'Основна (UA)', 'Європа'
  domain VARCHAR(255),                      -- 'farforevent.com.ua'
  default_language VARCHAR(5) DEFAULT 'uk', -- 'uk', 'en', 'es'
  supported_languages JSON,                 -- ["uk","en"]
  default_currency VARCHAR(3) DEFAULT 'UAH',
  logo_url VARCHAR(500),
  theme_json JSON,                          -- кастомізація кольорів
  contact_phone VARCHAR(50),
  contact_email VARCHAR(255),
  is_active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Яких складів "бачить" вітрина
CREATE TABLE storefront_warehouses (
  storefront_id INT NOT NULL,
  warehouse_id INT NOT NULL,
  priority INT DEFAULT 0,                   -- якщо один товар на кількох, звідки показувати першим
  PRIMARY KEY (storefront_id, warehouse_id)
);

-- Переклади назв і описів товарів
CREATE TABLE product_translations (
  product_id INT NOT NULL,
  language VARCHAR(5) NOT NULL,
  name VARCHAR(500),
  description TEXT,
  short_description VARCHAR(1000),
  PRIMARY KEY (product_id, language)
);

-- Доступ менеджера до складу (M2M з ролями)
CREATE TABLE user_warehouses (
  user_id INT NOT NULL,
  warehouse_id INT NOT NULL,
  role VARCHAR(32) DEFAULT 'manager',       -- 'manager','warehouseman','viewer','admin'
  PRIMARY KEY (user_id, warehouse_id)
);
```

### 1.2 Зміни в існуючих таблицях

```sql
-- Замовлення тепер прив'язане до складу і вітрини
ALTER TABLE orders
  ADD COLUMN warehouse_id INT NULL AFTER order_number,
  ADD COLUMN storefront_id INT NULL AFTER warehouse_id,
  ADD INDEX (warehouse_id), ADD INDEX (storefront_id);

-- Клієнт реєструється на конкретній вітрині
ALTER TABLE client_users
  ADD COLUMN storefront_id INT DEFAULT 1 AFTER id;

-- Users (admin) — має роль "super_admin" замість per-warehouse
ALTER TABLE users
  ADD COLUMN is_super_admin BOOLEAN DEFAULT FALSE;
```

### 1.3 Міграційні дані (seed)

```sql
-- Основний склад — всі існуючі товари
INSERT INTO warehouses (code, name, country, city, currency, is_default)
  VALUES ('UA', 'Київ (основний)', 'UA', 'Київ', 'UAH', TRUE);

-- Копіюємо залишки product.quantity → product_warehouses
INSERT INTO product_warehouses (product_id, warehouse_id, quantity, is_available)
SELECT product_id, 1 AS warehouse_id, quantity, 1 FROM products;

-- Основна вітрина
INSERT INTO storefronts (slug, name, domain, default_language, default_currency)
  VALUES ('default', 'Основна Україна', 'farforevent.com.ua', 'uk', 'UAH');

INSERT INTO storefront_warehouses (storefront_id, warehouse_id, priority)
  VALUES (1, 1, 0);
```

---

## 🔌 2. Backend API

### 2.1 Нові ендпоінти

| Метод | Endpoint | Опис |
|---|---|---|
| GET | `/api/admin/warehouses` | список складів |
| POST | `/api/admin/warehouses` | створити склад |
| PUT | `/api/admin/warehouses/{id}` | редагувати |
| GET | `/api/admin/warehouses/{id}/products` | товари на складі |
| GET | `/api/admin/transfers` | список переміщень |
| POST | `/api/admin/transfers` | створити переміщення |
| PUT | `/api/admin/transfers/{id}/ship` | позначити "в дорозі" |
| PUT | `/api/admin/transfers/{id}/complete` | завершити (списати source, додати target) |
| GET | `/api/admin/storefronts` | вітрини |
| POST | `/api/admin/storefronts` | створити вітрину |
| GET | `/api/admin/products/{id}/stock` | залишки по всіх складах |
| PUT | `/api/admin/products/{id}/stock/{warehouse_id}` | оновити залишок |
| GET | `/api/admin/products/{id}/translations` | переклади |
| PUT | `/api/admin/products/{id}/translations/{lang}` | зберегти переклад |

### 2.2 Зміни існуючих

| Endpoint | Зміна |
|---|---|
| `GET /api/event/products` | +`?storefront=X&lang=en` фільтрує по warehouse + повертає переклад |
| `GET /api/event/products/{id}` | те саме |
| `POST /api/event/orders` | записує `warehouse_id` і `storefront_id` |
| `GET /api/orders` (admin) | фільтр по user.warehouse_ids |
| `GET /api/products` (admin) | показує з яких складів |

### 2.3 Resolve storefront (middleware)

```python
# backend/middleware/storefront.py
async def resolve_storefront(request: Request):
    # 1. Явний параметр ?storefront=eu
    slug = request.query_params.get('storefront')
    if not slug:
        # 2. По домену (Host header)
        host = request.headers.get('host', '').lower()
        row = db.execute("SELECT slug FROM storefronts WHERE domain=:host", {'host': host}).fetchone()
        slug = row[0] if row else 'default'
    # 3. Зберігаємо в request.state
    request.state.storefront_slug = slug
    request.state.storefront = get_storefront_by_slug(slug)
```

### 2.4 Resolve language

```python
# Пріоритет:
# 1. ?lang=en в URL
# 2. Cookie 'lang'
# 3. Accept-Language header
# 4. storefront.default_language
```

---

## 🎨 3. UI макети (ASCII)

### 3.1 Admin — сторінка "Склади"

```
╔════════════════════════════════════════════════════════════════════╗
║ RentalHub › Склади                              [+ Новий склад]    ║
╠════════════════════════════════════════════════════════════════════╣
║ ┌────────┬───────────────────┬──────┬──────┬────────┬────────┐    ║
║ │ Код    │ Назва             │ Країна│ Валюта│ Товарів│ Статус │    ║
║ ├────────┼───────────────────┼──────┼──────┼────────┼────────┤    ║
║ │ 🇺🇦 UA  │ Київ (основний)   │ UA   │ UAH  │ 7943   │ ✅     │    ║
║ │ 🇵🇱 EU  │ Варшава           │ PL   │ EUR  │ 120    │ ✅     │    ║
║ │ 🇪🇸 ES  │ Барселона         │ ES   │ EUR  │ 0      │ 🔴     │    ║
║ └────────┴───────────────────┴──────┴──────┴────────┴────────┘    ║
║                                                                    ║
║ Швидкі посилання:                                                  ║
║   📥 Переміщення між складами        📊 Звіт по залишках           ║
╚════════════════════════════════════════════════════════════════════╝
```

### 3.2 Admin — Картка товару, нова вкладка "Склади"

```
╔════════════════════════════════════════════════════════════════════╗
║ Товар: Ваза Атлантида VU-100              [Деталі][Фото][Склади][Переклади]
╠════════════════════════════════════════════════════════════════════╣
║                                                                    ║
║ ДОСТУПНІСТЬ НА СКЛАДАХ                                             ║
║                                                                    ║
║ ┌─────────────────────────────────────────────────────────────┐   ║
║ │ ☑ 🇺🇦 UA (Київ, основний)                                   │   ║
║ │   Залишок: [  10  ] шт   Броня: [  2  ]  Мін: [  0  ]      │   ║
║ │   Ціна: UAH за замовчуванням ₴ 350    [□ Інша: _____]       │   ║
║ │   Собівартість: [  180  ] ₴                                 │   ║
║ ├─────────────────────────────────────────────────────────────┤   ║
║ │ ☑ 🇵🇱 EU (Варшава)                                          │   ║
║ │   Залишок: [   3  ] шт   Броня: [  0  ]  Мін: [  1  ]      │   ║
║ │   Ціна: [ 12.00 ] EUR  (замість перерахунку з UAH)          │   ║
║ │   Собівартість: [  5.00  ] EUR                              │   ║
║ ├─────────────────────────────────────────────────────────────┤   ║
║ │ ☐ 🇪🇸 ES (Барселона)                                        │   ║
║ │   Товар не доступний на цьому складі                        │   ║
║ └─────────────────────────────────────────────────────────────┘   ║
║                                                                    ║
║ Всього: 13 шт на 2 складах                   [💾 Зберегти]        ║
║                                                                    ║
║ [📤 Перемістити звідси в інший склад]                              ║
╚════════════════════════════════════════════════════════════════════╝
```

### 3.3 Admin — Модалка "Переміщення"

```
╔═══════════════════════════════════════════════════════╗
║ Перемістити товар між складами                   [✕] ║
╠═══════════════════════════════════════════════════════╣
║ Товар: Ваза Атлантида VU-100                          ║
║                                                       ║
║ ЗВІДКИ:    🇺🇦 UA (10 шт)       ▼                     ║
║ КУДИ:      🇵🇱 EU (3 шт)         ▼                     ║
║                                                       ║
║ Кількість: [  5  ] шт                                 ║
║ Залишиться:                                           ║
║   UA: 5 шт                                            ║
║   EU: 8 шт (після прибуття)                           ║
║                                                       ║
║ Перевізник:  [ Nova Poshta Int.        ]              ║
║ Трек-номер:  [ 2050120034500            ]             ║
║ Коментар:    [ Відправка 20.07.2026    ]              ║
║                                                       ║
║ Статус:  ◉ Чорновик   ◯ Відправлено одразу           ║
║                                                       ║
║                        [Скасувати]  [✅ Створити]     ║
╚═══════════════════════════════════════════════════════╝
```

### 3.4 Admin — Сторінка "Переміщення"

```
╔════════════════════════════════════════════════════════════════════╗
║ Переміщення між складами                 [+ Нове переміщення]      ║
╠════════════════════════════════════════════════════════════════════╣
║ Фільтри: [Всі склади ▼] [Всі статуси ▼] [20.07 - 27.07 ▼]         ║
║                                                                    ║
║ ┌─────┬────────────┬────────┬──────────┬──────────┬─────┬────────┐║
║ │ #   │ Товар      │ Звідки │ Куди     │ К-сть    │ Трек│ Статус │║
║ ├─────┼────────────┼────────┼──────────┼──────────┼─────┼────────┤║
║ │ 42  │ Ваза VU100 │ 🇺🇦 UA │ 🇵🇱 EU   │ 5 шт     │2050…│🚚 Доро │║
║ │ 41  │ Стіл T30   │ 🇺🇦 UA │ 🇵🇱 EU   │ 2 шт     │2050…│✅ OK   │║
║ │ 40  │ Крісло K1  │ 🇵🇱 EU │ 🇺🇦 UA   │ 10 шт    │—    │📝 Чорн.│║
║ └─────┴────────────┴────────┴──────────┴──────────┴─────┴────────┘║
║                                                                    ║
║ За цей тиждень: 17 переміщень · 342 шт · UA↔EU                    ║
╚════════════════════════════════════════════════════════════════════╝
```

### 3.5 Admin — Вкладка "Переклади" на картці товару

```
╔════════════════════════════════════════════════════════════════════╗
║ Товар: Ваза Атлантида               [Деталі][Фото][Склади][Переклади]
╠════════════════════════════════════════════════════════════════════╣
║                                                                    ║
║ 🇺🇦 Українська (основна)                                           ║
║ Назва:   Ваза Атлантида VU-100                                    ║
║ Опис:    Декоративна скляна ваза заввишки 30см...                 ║
║                                                                    ║
║ 🇬🇧 English                                           [🤖 Авто]     ║
║ Name:    [ Atlantis Vase VU-100                            ]      ║
║ Desc:    [ Decorative glass vase, 30cm tall...             ]      ║
║                                                                    ║
║ 🇪🇸 Español                                           [🤖 Авто]     ║
║ Nombre:  [ Jarrón Atlantis VU-100                          ]      ║
║ Desc:    [ Jarrón decorativo de vidrio, 30cm de alto...    ]      ║
║                                                                    ║
║                                              [💾 Зберегти всі]     ║
║                                                                    ║
║ 💡 "Авто" — переклад через GPT (треба LLM key в налаштуваннях).    ║
╚════════════════════════════════════════════════════════════════════╝
```

### 3.6 Admin — Налаштування вітрин

```
╔════════════════════════════════════════════════════════════════════╗
║ Вітрини (Storefronts)                       [+ Нова вітрина]       ║
╠════════════════════════════════════════════════════════════════════╣
║ ┌──────────┬───────────────────────┬───────────┬──────────┬──────┐║
║ │ Код      │ Домен                 │ Мови      │ Склади   │ Стат │║
║ ├──────────┼───────────────────────┼───────────┼──────────┼──────┤║
║ │ default  │ farforevent.com.ua    │ 🇺🇦 UK    │ UA       │ ✅   │║
║ │ eu       │ eu.farforevent.com.ua │ 🇬🇧🇪🇸    │ EU, ES   │ ✅   │║
║ └──────────┴───────────────────────┴───────────┴──────────┴──────┘║
║                                                                    ║
║ Відкрив редагування "eu":                                         ║
║ ┌─────────────────────────────────────────────────────────────┐   ║
║ │ Slug:          eu                                           │   ║
║ │ Назва:         Європа                                       │   ║
║ │ Домен:         eu.farforevent.com.ua                        │   ║
║ │ Основна мова:  English  ▼                                   │   ║
║ │ Мови:          ☑ English  ☑ Español  ☐ Українська          │   ║
║ │ Валюта:        EUR                                          │   ║
║ │ Склади:        ☑ EU (Варшава)   ☑ ES (Барселона)  ☐ UA     │   ║
║ │ Логотип:       [upload]                                     │   ║
║ │ Контактний:    +48 123 456 789 / info@farforevent.eu       │   ║
║ │                                            [💾 Зберегти]    │   ║
║ └─────────────────────────────────────────────────────────────┘   ║
╚════════════════════════════════════════════════════════════════════╝
```

### 3.7 Event Tool — Перемикач мови

```
┌──────────────────────────────────────────────────────────┐
│  FarforDecorOrenda           [EN ▼]  🛒 2    👤 Login    │
│                               ├ UK                        │
│                               ├ EN  (selected)            │
│                               └ ES                        │
├──────────────────────────────────────────────────────────┤
│  Catalog · Favorites · Projects                           │
├──────────────────────────────────────────────────────────┤
│  [ Vases ] [ Tables ] [ Chairs ] ...                      │
│                                                           │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐                   │
│  │ 📷      │  │ 📷      │  │ 📷      │                   │
│  │Atlantis │  │ Table   │  │Elegance │                   │
│  │Vase     │  │ Milano  │  │ Chair   │                   │
│  │ € 12.00 │  │ € 25.00 │  │ € 8.00  │                   │
│  │ Stock: 8│  │ Stock:12│  │ Stock:50│                   │
│  └─────────┘  └─────────┘  └─────────┘                   │
└──────────────────────────────────────────────────────────┘
```

### 3.8 Dashboard менеджера з warehouse-scoping

```
╔════════════════════════════════════════════════════════════╗
║ Dashboard                              [🇺🇦 UA ▼] 👤 Max  ║
╠════════════════════════════════════════════════════════════╣
║ ВИ БАЧИТЕ: 🇺🇦 Склад UA, Київ                             ║
║                                                            ║
║ 📥 Збір   📥 Повернення   ⚠️ Борги   📞 Чати               ║
║ ──────    ──────────      ────────   ───────               ║
║ 3 карт.   2 поверн.       3 боргів   1 новий               ║
║                                                            ║
║ ... (далі звичайний dashboard, тільки по UA складу)       ║
╚════════════════════════════════════════════════════════════╝
```

Якщо менеджер має доступ до двох складів — у хедері з'являється перемикач, по дефолту обирає основний.

---

## 🔐 4. Ролі та доступ

| Роль | Scope | Дозволи |
|---|---|---|
| `super_admin` | всюди | все, керування складами / вітринами / користувачами |
| `warehouse_admin` | 1+ склад | все на своєму(ніх) складі(ах) |
| `warehouse_manager` | 1 склад | замовлення, видачі, повернення, чат |
| `warehouseman` | 1 склад | тільки комплектація/прийом |
| `viewer` | 1+ склад | тільки читати |

**На API рівні**: `Depends(require_warehouse_access(warehouse_id))` — перевіряє `user_warehouses`.

---

## 🌐 5. Деплой і DNS

### 5.1 Nginx конфіг (новий файл `nginx-event-tool-eu.conf`)
```nginx
server {
    listen 443 ssl http2;
    server_name eu.farforevent.com.ua;
    
    # Той самий build Event Tool
    root /var/www/event-tool-build;
    index index.html;
    
    location / {
        try_files $uri $uri/ /index.html;
    }
    
    location /api/ {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host $host;         # ← важливо, бо бекенд читає Host
        proxy_set_header X-Forwarded-Host $host;
    }
    
    ssl_certificate /etc/letsencrypt/live/eu.farforevent.com.ua/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/eu.farforevent.com.ua/privkey.pem;
}
```

### 5.2 Кроки на VPS
```bash
# 1. DNS A-record: eu.farforevent.com.ua → IP VPS (у вас adm.tools панель)
# 2. SSL
sudo certbot --nginx -d eu.farforevent.com.ua
# 3. Активувати конфіг
sudo cp /var/www/farforrent/deploy/nginx-event-tool-eu.conf /etc/nginx/sites-available/
sudo ln -s /etc/nginx/sites-available/nginx-event-tool-eu.conf /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

### 5.3 Один код — дві вітрини
Той самий React build обслуговує обидва домени. Різниця:
- Бекенд читає `Host` header → визначає `storefront_slug`
- Фронт при завантаженні робить `GET /api/event/config` → отримує мови, валюту, склади для цієї вітрини
- Логотип, назва, контакти — з конфігу вітрини

---

## 📅 6. Фази і таймлайни

### 🟢 Phase 1: Core multi-warehouse (3-4 дні)
1. Міграції БД (всі нові таблиці + seed UA склад)
2. Backend: CRUD `/api/admin/warehouses`
3. Admin UI: сторінка "Склади"
4. Backend: `product_warehouses` CRUD + `/api/admin/products/{id}/stock`
5. Admin UI: вкладка "Склади" у картці товару
6. Event Tool: `/api/event/products?storefront=X` фільтр
7. Dashboard показує warehouse-scoped дані (поки без ролей)

### 🟡 Phase 2: Переміщення (1-2 дні)
1. Backend: `/api/admin/transfers` CRUD + state machine
2. Admin UI: сторінка "Переміщення" + модалка з картки товару
3. Audit log автоматично пише в `audit_records`

### 🔵 Phase 3: Multi-storefront + i18n (2-3 дні)
1. `storefronts` CRUD + admin UI
2. Backend: `storefront_middleware` + resolve мови
3. Таблиця `product_translations` + API
4. Event Tool: translation files (uk/en/es) + language switcher
5. Валюта: показувати ціну у валюті storefront
6. Admin UI: вкладка "Переклади" у картці товару (+ опційно GPT-авто)

### 🟣 Phase 4: Ролі warehouse-scoped (1-2 дні)
1. `user_warehouses` таблиця + міграція (всі існуючі users → UA)
2. Admin UI: редактор ролей користувача
3. Backend middleware `require_warehouse_access`
4. Фільтри по складу на всіх менеджерських ендпоінтах

### 🚀 Phase 5: EU вітрина live (1 день)
1. DNS A-record для `eu.farforevent.com.ua`
2. Certbot SSL
3. Nginx конфіг
4. Налаштувати storefront у адмінці
5. Створити EU warehouse і додати пробних товарів

**Total**: ~10 робочих днів від старту до запущеної EU вітрини.

---

## 🔄 7. Пайплайн міграції

```sql
-- Безпечна міграція без простою:
BEGIN;

-- 1. Створити нові таблиці
CREATE TABLE warehouses (...);
CREATE TABLE product_warehouses (...);
-- etc

-- 2. Seed UA склад
INSERT INTO warehouses (code, name, ...) VALUES ('UA', ...);
SET @ua_id = LAST_INSERT_ID();

-- 3. Копіюємо залишки
INSERT INTO product_warehouses (product_id, warehouse_id, quantity, is_available)
SELECT product_id, @ua_id, quantity, (status = 'enabled')
FROM products;

-- 4. Основна вітрина
INSERT INTO storefronts (...) VALUES ('default', 'farforevent.com.ua', ...);
INSERT INTO storefront_warehouses VALUES (1, @ua_id, 0);

-- 5. Всі існуючі users → UA warehouse
INSERT INTO user_warehouses (user_id, warehouse_id, role)
SELECT user_id, @ua_id, 'warehouse_manager' FROM users;

COMMIT;
```

Старий код працюватиме, бо `products.quantity` залишається (deprecated). Після випуску коду який читає з `product_warehouses` — поступово можна прибрати.

---

## ⚠️ 8. Ризики та відкриті питання

### Ризики
| Ризик | Mitigation |
|---|---|
| Існуючі замовлення без `warehouse_id` | Беквардна сумісність: NULL → UA |
| Товари лише в OpenCart `oc_product` | Треба додати shadow-запис в `product_warehouses` при читанні |
| ChatGPT-переклад може видати нісенітницю | Ручна модерація, кнопка "Авто" опційна |
| EU складові витрати (мито, курс) | Поле `cost_override` окремо на кожному складі |

### Відкриті питання
1. **OpenCart інтеграція**: чи синхронізуємо `oc_product` з новою моделлю? Чи лишаємо `oc_` як "імпорт джерело", а робочу копію тримаємо в `products` + `product_warehouses`?
2. **Клієнти**: EU клієнт реєструється на `eu.*` — чи може він потім логінитись на UA? Пропоную `client_users.storefront_id` + warning при спробі.
3. **Payers (платники)**: однакові FOP для різних країн? → ні, прив'язуємо до warehouse_id.
4. **Документи**: шаблони договору різні для UA vs EU (мова, законодавство). → додати `document_templates.warehouse_id`.
5. **Пошта/SMS**: email із іншого домену для EU? → поле `warehouse.email_from`.

---

## 💰 9. Орієнтовний бюджет LLM-витрат (переклади)

- Переклад одного товару (назва + опис, ~150 слів): ~0.001$ через GPT-4o-mini
- 7943 товари × 2 мови (EN+ES) = 15886 перекладів ≈ $16 разово
- Нові товари: автопереклад при створенні — ~$1-5/міс
- Можна ввімкнути чи вимкнути, можна редагувати вручну

---

## ✅ 10. Критерії готовності для кожної фази

### Phase 1
- [ ] Міграція пройшла, усі товари в UA warehouse
- [ ] Admin може створити EU warehouse
- [ ] Admin додає товари в EU warehouse через вкладку "Склади"
- [ ] Event Tool `?storefront=eu` показує лише EU-товари
- [ ] Smoke тести всіх ключових флоу (видача, повернення) не зламані

### Phase 2
- [ ] Переміщення з UA в EU працює через UI
- [ ] Залишки оновлюються атомарно
- [ ] Історія переміщень доступна в адмінці
- [ ] Якщо переміщення скасовано — залишок повертається

### Phase 3
- [ ] Клієнт на eu.farforevent.com бачить інтерфейс англійською
- [ ] Ціни показуються в EUR
- [ ] Назви товарів перекладені EN/ES
- [ ] Admin може редагувати переклади вручну або через GPT

### Phase 4
- [ ] Менеджер UA не бачить замовлень EU
- [ ] Супер-адмін бачить все
- [ ] Логістик може робити transfers у/зі своїх складів

### Phase 5
- [ ] eu.farforevent.com.ua відкривається з SSL
- [ ] Повний флоу: клієнт реєструється → створює замовлення → менеджер EU його бачить → видача

---

## 📝 Що робити далі

1. **Погодити цей план** або внести правки
2. Я зроблю детальний PR-план по Phase 1 (список змінених файлів, SQL міграції, test-plan)
3. Починаємо реалізацію Phase 1
4. Між фазами — пауза на тестування вами

