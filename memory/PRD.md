# RentalHub - Rental Management Platform

## Original Problem Statement
Comprehensive rental management platform (React + FastAPI + MySQL) syncing from OpenCart DB. Manages orders, inventory, auditing, damage tracking, issue cards, returns, and financial workflows.

VPS: `173.242.49.48` (Ubuntu 24.04). Two React apps + single FastAPI backend on `:8001`. Nginx routes `/` → Event Tool, `:8080` → RentalHub Admin.

## DB Architecture
- **Production**: `farforre_rentalhub` на `farforre.mysql.tools` — менеджери працюють тут
- **VPS-копія**: `farforre_vps` на тому ж хості — ізольована, безпечна (бекенд VPS підключений сюди)
- **OpenCart**: `farforre_db` — джерело продуктів (read-only)
- Cron `*/5 * * * * /usr/local/bin/farforrent-image-sync.sh` тягне нові фото

## Test Credentials
See `/app/memory/test_credentials.md`

---

## What's Been Implemented (latest first)

### 2026-02-23 — Major UX Session
**Smart days (Farfor rules) — єдине джерело правди:**
- `backend/utils/rental_days.py` + `event-tool-source/src/utils/rentalDays.js` — спільна логіка
- Правила: Пн→Ср=1, Пн→Чт=2, Ср→Пт=1, Ср→Сб=2, Пт→Сб=1, Пт→Пн=2 тощо (повернення до 17:00)
- `convert-to-order` зберігає правильні дні + `deposit = sum(p.deposit × qty)`
- `GET /event/orders/{id}` перераховує дні на льоту (для існуючих ордерів теж)
- HTML-кошторис теж використовує цю формулу
- App.js сайдбар "МІЙ ІВЕНТ" — підпис під календарем оновлюється
- CheckoutModal — 880px, 2 колонки, з заставою+таймслотом видачі

**Smart Search (rapidfuzz):**
- Багатопольний (name, sku, color, material, description, hashtags, components)
- Опечатки: "злена ваза" → "зелена ваза"
- Розміри: "маленький" ≤15см, "середній" 15-40см, "великий" >40см

**OpenCart Image Sync:** cron 5min, ~440 нових товарів автозалиті

**Bug fixes цього циклу:**
- RentalHub admin "💾 Зберегти дати" тепер реально PUT-ає у `/api/decor-orders/{id}` + toast
- Обране endpoint `/favorites/products` — динамічна перевірка колонок (rental_price/deposit/color/material)
- Обране UI = ProductCard (один в один з каталогом)
- Прибрана кнопка "+ Знайти ще" з Обраного  
- AddToBoardModal посередині екрана + `boardsAPI.list()` → `getBoards()` (was undefined)
- CreateBoardModal: стиснення обкладинки 800×800 q=0.7 + БД `event_boards.cover_image` → MEDIUMTEXT
- Фото у "Обране" + "Мої замовлення" — фікс `/uploads/uploads/` 404 (повний шлях замість filename)
- Прибрано емоджі 📅 з дат
- `product_images_multi.py`: route приймає і SKU і ID (фікс 422)
- `partial_return_versions.completed_at` додано (фікс 500 на `/api/orders/{id}/lifecycle`)
- ProductCard: прибрано useAvailability — було 100+ запитів `check-availability` на render → 0
- App.js loadInitialData: products з датами одразу (без подвійного fetch)
- Mobile: прибрано сірий простір між хедером і chips

**SQL виконано на VPS (одноразово):**
```sql
ALTER TABLE orders ADD COLUMN pickup_time_slot VARCHAR(20) NULL;
-- return_time вже існувало
ALTER TABLE partial_return_versions ADD COLUMN completed_at TIMESTAMP NULL;
ALTER TABLE event_boards MODIFY cover_image MEDIUMTEXT;
```

---

## 🔥 Cabinet 2.0 — НАСТУПНА СЕСІЯ (P0)

User explicit request: "ми хіба при генерації не зберігаємо кошториси у себе в системі? чому клієнт не може їх бачити. також клієнт має сам редагувати свої дані якщо телефон/рахунок ФОП змінюється".

### 1. Документи (RH → кабінет клієнта)
- Існуючі endpoints у RH: `/api/documents/estimate/{order_id}/preview`, `/api/documents/invoice-offer/{order_id}/preview`
- **NEW** `GET /api/event/cabinet/documents` — список документів клієнта (JOIN на customer_id + email)
- **NEW** вкладка "📄 Документи" у `UserProfile.js`:
  - Перелік замовлень з кнопками "Кошторис" / "Рахунок-оферта" / "Рахунок ФОП"
  - Бейдж "Новий" при першому перегляді
  - Лічильник нових на іконці кабінету (red dot)
- При генерації документа в RH — клієнт **автоматично бачить** (без явного push), бо ми просто читаємо з тієї ж таблиці

### 2. Платники клієнта — CRUD
- Існуюча таблиця: `customer_payers` / `payers` (типи: ФОП, ТОВ, фіз.особа з ЕДРПОУ/ІПН, реквізити)
- **NEW** endpoints:
  - `GET /api/event/cabinet/payers`
  - `POST /api/event/cabinet/payers` (create ФОП/ТОВ/фіз.)
  - `PUT /api/event/cabinet/payers/{id}` (edit phone/банк/рахунок/реквізити)
  - `DELETE /api/event/cabinet/payers/{id}` (відв'язати)
  - `PUT /api/event/cabinet/payers/{id}/make-default`
- **NEW** вкладка "💼 Мої платники" у `UserProfile.js`:
  - Картки як у RH (на скрині: ФОП Філімоніхіна / ТОВ загальна / ТОВ спрощена / Фіз.особа)
  - Кнопки "Редагувати" / "Зробити основним" / "Відв'язати"

### 3. Профіль клієнта — edit
- Існуюча таблиця: `customers` (firstname, lastname, telephone, email, address)
- **NEW** `PUT /api/event/cabinet/profile`
- Вкладка "👤 Профіль" з формою (lock на email, edit на phone/ПІБ/адресу)

### 4. Push при отриманні нового документа (після #1)
- При `INSERT INTO documents` в RH → trigger/код → push на customer
- Залежить від HTTPS (`certbot --nginx`)

---

## Backlog (далі)
- WebSocket чат: додати `location /api/ws/` в nginx
- HTTPS через Let's Encrypt (для push)
- Stripe/LiqPay депозити з кабінету
- AI-асистент для чату клієнта
- Email-нотифікація менеджеру про нове замовлення (Resend)
- Drag-and-drop сортування товарів у мудборді
- Refactor: видалити `routes/return_cards.py`

## Files of Reference
- `/app/backend/routes/event_tool.py` — Event Tool API (smart search, smart days, HTML estimate)
- `/app/backend/utils/rental_days.py` — Farfor правила діб
- `/app/backend/utils/smart_search.py` — fuzzy search engine
- `/app/event-tool-source/src/utils/rentalDays.js` — JS-копія правил діб
- `/app/event-tool-source/src/components/UserProfile.js` — кабінет клієнта (Cabinet 2.0 тут)
- `/app/event-tool-source/src/components/CheckoutModal.js` — оформлення (з заставою/таймслотом)
- `/app/event-tool-source/src/components/ProductCard.js` — без useAvailability
- `/app/frontend/src/pages/NewOrderViewWorkspace.jsx` — RH admin (save dates fix тут)
- `/app/deploy/deploy.sh` — повний скрипт деплою

## Deploy Workflow
1. Зміни в `/app/`
2. "Save to GitHub" в Emergent UI
3. На VPS: `cd /var/www/farforrent && bash deploy/deploy.sh`
