# RentalHub - Rental Management Platform

## Original Problem Statement
Comprehensive rental management platform (React + FastAPI + MySQL) syncing from OpenCart DB. Manages orders, inventory, auditing, damage tracking, issue cards, returns, and financial workflows.

VPS: `173.242.49.48` (Ubuntu 24.04). Two React apps + single FastAPI backend on `:8001`. Nginx routes `/` → Event Tool, `:8080` → RentalHub Admin.

## Core Requirements
- Multi-role: Admin, Manager, Requisitor
- Order lifecycle: Draft → Awaiting → Processing → Issued → Returned
- Inventory sync from OpenCart (RentalHub as source of truth — reverse sync)
- Damage tracking with photos and history
- Financial tracking (payments, deposits, refunds)
- Calendar, catalog, moodboard features
- Mobile-friendly UI for warehouse workers
- Event Tool client app (Favorites, Push, WS Chat, Moodboard)

## DB Architecture (важливо!)
- **Production**: `farforre_rentalhub` на `farforre.mysql.tools` — менеджери працюють тут
- **VPS-копія (для розробки)**: `farforre_vps` на тому ж хості — ізольована, безпечна
- **OpenCart**: `farforre_db` — джерело продуктів (read-only тут)
- VPS backend підключений до `farforre_vps` (не до прода!)

## Test Credentials
See `/app/memory/test_credentials.md`

---

## What's Been Implemented (latest first)

### 2026-02-23 — Smart Search + Photo Sync + Multiple Bug Fixes
**Розумний пошук (`backend/utils/smart_search.py` + `routes/event_tool.py`):**
- Багатопольний: name, sku, color, material, description, hashtags, components, categories, size, shape
- Tolerantний до опечаток через `rapidfuzz` ("злена ваза" → "зелена ваза")
- Семантичний для розмірів: "маленький" ≤15см, "середній" 15-40см, "великий" >40см
- Парсинг розмірів: height_cm → diameter_cm → fallback на парсинг з name ("Ваза 26 см")
- Threshold = 65 (балансує між false positive і recall)
- Frontend `App.js`: прибрана подвійна client-side фільтрація (довіряємо серверу)

**OpenCart Image Sync (`backend/sync_images_only.py`):**
- Cron `*/5 * * * * /usr/local/bin/farforrent-image-sync.sh` тягне нові фото з OC → VPS
- Завантажує оригінал + thumbnails (300x300) + medium (800x800)
- Оновлює `products.image_url` + `product_images` (source='opencart_sync')
- BATCH=100 на запуск, лог `/var/log/farforrent/image_sync.log`

**Bug fixes:**
- `product_images_multi.py`: route приймає і SKU і числовий ID (фікс 422 на upload)
- `event_tool.py`: створено таблицю `product_images` у `farforre_vps` (раніше не існувала)
- `populate_product_images_from_thumbnails.py`: змаповано 9409 файлів thumbnails → 7248 товарів
- Видалено 9777 битих HTML-PNG файлів → `db_backups/broken_pngs/`
- Очищено `image_url` для ~440 товарів з битими посиланнями (тепер показують placeholder)
- `partial_return_versions`: додано колонку `completed_at` (фікс 500 на `/api/orders/{id}/lifecycle`)

**UI/UX:**
- Повзунок "Мінімум на складі" → числове поле (десктоп `ProductFilters.js`, мобайл `CategoryChips.js`)
- Прибрано `useAvailability` з `ProductCard` (було 100+ запитів `check-availability`/render → 0)
- `App.js loadInitialData`: products завантажується одразу з датами активного борду (без подвійного fetch)
- Mobile: прибрано сірий простір між хедером і chips категорій

**VPS Recovery:**
- Бекенд переключено на `farforre_vps` (продакшн `farforre_rentalhub` недоторканий)
- Cron `cron_refresh_db.sh` (drop+import) вимкнено — більше не дропає БД
- `event-tool-backend.service` зупинено (267k+ рестартів через відсутність `sync_all.py`)
- Cron `*/5 * * * * /usr/local/bin/farforrent-sync.sh` залишено (працює з продакшеном)
- `cloud_full.sql` (67 МБ) — страховий бекап у `/var/www/farforrent/db_backups/`

---

### 2026-02-13 — P3 Backlog (WS Chat, Push, Favorites, Company Profiles, Document Signatures)
[Зберігається з попередньої версії — не змінювалось]

---

## Known Issues / Quirks
- ~440 нових товарів (created після 5 червня 2026) не мають фото на VPS — підтягуються cron з OpenCart (`*/5 хв`)
- Деякі поля у `farforre_vps` можуть відрізнятись від продакшна — нові міграції треба робити вручну на копії
- `event_tool.py` ще має застарілі lint warnings (F811, F821) — старий код, не критично

---

## Roadmap / Backlog

### P1 — Картка оформлення замовлення (наступна сесія)
1. **Логіка перерахунку діб** (клієнтська, орієнтовна — менеджер фіналізує в RH):
   - 1 доба: Пн→Ср, Вт→Чт, Ср→Пт, Чт→Сб, Пт→Сб, Сб→Пн (повернення до 17:00)
   - 2 доби: Пн→Чт, Вт→Пт, Ср→Сб, Пт→Пн, Сб→Вт (повернення до 17:00)
2. **Час видачі/повернення** — додати поля `pickup_time_slot` (slot enum), `return_time` (default 17:00) у `orders`
3. **Розширити модалку** "Оформити замовлення" на десктопі (max-width 800px, два стовпці)
4. **Показати заставу клієнту** в модалці (sum(products.price/2 * qty))
5. **Згенерувати попередній кошторис** PDF при `awaiting_customer` → видно в кабінеті клієнта

### P2 — Платежі
- Stripe / LiqPay для внесення депозиту з кабінету клієнта
- Webhook для статусу payment → orders.deposit_paid

### P3 — AI
- AI-асистент для чату клієнта (підказки відповідей менеджеру)

### Refactoring
- Видалити `routes/return_cards.py` (deprecated, дані мігровані у `partial_return_versions`)

---

## Files of Reference
- `/app/backend/routes/event_tool.py` — Event Tool API (smart search тут)
- `/app/backend/utils/smart_search.py` — пошуковий движок
- `/app/backend/sync_images_only.py` — image sync (на VPS, не в репо)
- `/app/backend/routes/product_images_multi.py` — upload фото (з SKU/ID resolver)
- `/app/event-tool-source/src/App.js` — головний компонент Event Tool
- `/app/event-tool-source/src/components/ProductFilters.js` — десктоп фільтри
- `/app/event-tool-source/src/components/CategoryChips.js` — мобайл chips + ввід кількості
- `/app/event-tool-source/src/components/ProductCard.js` — картка товару (без useAvailability)
- `/app/deploy/deploy.sh` — повний скрипт деплою на VPS

## Deploy Workflow
1. Зміни в `/app/` (Emergent)
2. Натиснути "Save to GitHub" в Emergent UI
3. На VPS: `cd /var/www/farforrent && bash deploy/deploy.sh`
   - git pull (force reset)
   - pip install -r requirements.txt у venv
   - yarn build обох фронтів
   - systemctl restart rentalhub-backend
