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

### 2026-02-25 — Cabinet 2.0: Платники CRUD (UI + бекенд фікс)
- **UI**: нова вкладка "Платники" в `UserProfile.js` — список карток платників, форма create/edit (тип/назва/ЄДРПОУ/директор/адреса/тел/email/IBAN/банк), кнопки "Зробити основним", "Редагувати", "Відв'язати"
- **Бекенд фікс**: в усіх 5 endpoints `/cabinet/payers*` cuid резолвиться через `customer_id` (раніше падав з NULL у `client_payer_links.client_user_id`)
- **Перевірено E2E через curl**: LIST→CREATE(126)→UPDATE→MAKE-DEFAULT→DELETE — усе OK
- Платник прив'язується через `client_payer_links`, сам запис лишається в `payer_profiles` (відв'язка не видаляє платника)

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

### ⚠️ КРИТИЧНИЙ ПРИНЦИП: ВИКОРИСТОВУВАТИ ІСНУЮЧІ ТАБЛИЦІ
**Категорично заборонено** створювати дублюючі таблиці. Перед будь-якою імплементацією — обов'язково:

1. **Зробити SHOW TABLES + DESCRIBE** для пошуку існуючої структури:
   ```sql
   SHOW TABLES FROM farforre_vps LIKE '%payer%';
   SHOW TABLES FROM farforre_vps LIKE '%agreement%';
   SHOW TABLES FROM farforre_vps LIKE '%document%';
   SHOW TABLES FROM farforre_vps LIKE '%signature%';
   SHOW TABLES FROM farforre_vps LIKE '%client%';
   SHOW TABLES FROM farforre_vps LIKE '%customer%';
   ```

2. **Відомі існуючі таблиці** (підтверджені у скрінах):
   - `customers` — основні дані клієнта (firstname, lastname, telephone, email, address)
   - `client_users` — клієнтські юзери (для логіну в кабінет)
   - `client_payer_links` — зв'язок клієнт ↔ платник
   - `master_agreements` — РІЧНІ ДОГОВОРИ (саме сюди підпис, ані не нові таблиці!)
   - `documents` — кошториси, рахунки-оферти, ФОП (RH вже зберігає, треба тільки READ для клієнта)
   - `document_signatures` — підписи документів (вже існує)
   - `document_email_log`, `document_emails`, `document_templates`, `document_number_sequences` — суміжне
   - `orders` (має `customer_id`, можливо `customer_email`, `client_user_id`) — для JOIN

3. **Правило виявлення колонок** для будь-якого SQL: використовувати динамічну перевірку (як у `/event/products` через `SHOW COLUMNS FROM <table>` + fallback). Це усуває падіння при різниці схем `farforre_vps` ↔ продакшен.

4. **Якщо колонки немає** — додавати тільки ALTER ADD COLUMN (не нова таблиця). Наприклад для бейджа "новий документ" → `documents.first_viewed_at TIMESTAMP NULL` замість окремої таблиці `document_views`.

### 1. Документи (RH → кабінет клієнта, read-only)
- Тягнемо з існуючої таблиці `documents` (НЕ створювати нову `client_documents`!)
- **NEW** `GET /api/event/cabinet/documents` — `SELECT FROM documents WHERE customer_id = :cid OR customer_email = :email`
- Endpoints для preview вже існують: `/api/documents/estimate/{order_id}/preview`, `/api/documents/invoice-offer/{order_id}/preview`
- **NEW** вкладка "📄 Документи" у `UserProfile.js`: групування по `order_id`, кнопки на існуючі preview-endpoints
- Бейдж "Новий" — через ALTER `documents` ADD COLUMN `first_viewed_at TIMESTAMP NULL` (один альтер, без нової таблиці)
- Лічильник на іконці кабінету

### 2. ✍️ Річний договір (master_agreements + document_signatures)
- Використовуємо існуючі таблиці `master_agreements` та `document_signatures`. **Не створювати нових.**
- Структура буде з'ясована через `DESCRIBE master_agreements` + `DESCRIBE document_signatures` у початку сесії.
- **NEW** endpoints:
  - `GET /api/event/cabinet/master-agreement` — `SELECT FROM master_agreements WHERE customer_id = :cid AND status = 'active' AND valid_until > NOW()`
  - `POST /api/event/cabinet/master-agreement/sign` — INSERT у `document_signatures` (signer_role='client', signed_at=NOW(), signature_data=base64, signature_ip, signature_user_agent) + UPDATE `master_agreements` status='active'
- **NEW** вкладка "📜 Договір": canvas для підпису + чекбокс згоди + кнопка
- Перед оформленням замовлення (CheckoutModal): перевірка наявності активного. Якщо немає → редирект на підпис.
- У `orders` додати поле `agreement_id` (тільки якщо ще немає — через DESCRIBE orders + ALTER if missing). У RH менеджер бачить "Договір підписано ✓".

### 3. Платники — CRUD на існуючу `client_payer_links` (+ зв'язана таблиця платників)
- Знайти точну назву таблиці платників через SHOW TABLES + перевірити її структуру через DESCRIBE
- **NEW** endpoints:
  - `GET /api/event/cabinet/payers` — JOIN client_payer_links + payers по поточному customer
  - `POST /api/event/cabinet/payers`
  - `PUT /api/event/cabinet/payers/{id}` (edit телефон/банк/рахунок/реквізити)
  - `DELETE /api/event/cabinet/payers/{id}`
  - `PUT /api/event/cabinet/payers/{id}/make-default`
- **NEW** вкладка "💼 Мої платники" — UI як у RH (картки)

### 4. Профіль клієнта — edit existing `customers`
- **NEW** `PUT /api/event/cabinet/profile` — UPDATE `customers` SET (телефон/ПІБ/адреса) WHERE customer_id = :cid
- Вкладка "👤 Профіль" з формою (lock на email, edit phone/ПІБ/адресу)

### 5. Push-сповіщення (потребує HTTPS)
- Використовуємо існуючу таблицю `push_subscriptions` (вже створена в попередніх сесіях)
- Тригери:
  - INSERT у `documents` для клієнта → "Новий документ"
  - INSERT у `order_chat_messages` → "Нове повідомлення від менеджера"
  - UPDATE `orders.status` → "Статус замовлення змінено"
- Залежить від `certbot --nginx -d farforrent.com.ua`

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
