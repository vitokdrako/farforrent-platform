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

### 2026-02-25 — Chat: окрема сторінка ТАКОЖ для клієнта (Event Tool)
- **Новий шлях `/chat`** у Event Tool (`/app/event-tool-source/src/pages/ClientChatPage.js`): ліва панель — усі ВЛАСНІ замовлення клієнта з лічильником непрочитаних повідомлень, права — існуючий компонент `<OrderChat>` з WebSocket (key={orderId} для force-remount при перемиканні).
- **Маршрут** додано в `App.js` під `ProtectedRoute`. Inline `<OrderChat>` на деталях замовлення в `UserProfile.js` залишено — клієнт має ОБИДВА варіанти: швидкий (модальний у профілі) і повний (окрема сторінка).
- **Кнопка `💬 Чат`** у header профілю поряд із «Каталог».
- **На VPS треба перебудувати ОБИДВА фронти** (event-tool + admin), щоб маршрути з'явилися.
- **testing_agent (iteration_9.json)**: ✅ **34/34 PASS** (13 нових для клієнта + 21 регресія). 0 critical, 0 minor. Перевірено: auth, scope (тільки власні замовлення, без leak), persistence sender_type='client', read-marker advances, 404 для чужого замовлення, 400 для empty message.

**Code-review tech debt (накопичується, окремою задачкою):**
- 🟡 Admin chat endpoints все ще БЕЗ auth (тепер ре-підтверджено)
- 🟡 `SHOW COLUMNS FROM orders` на кожен запит у client_router — memoize
- 🟡 `read_marker UPDATE` на кожен GET /messages — batch або через WS ACK
- 🟡 ClientChatPage робить N паралельних HTTP-запитів `unread_count` на render → завести `GET /api/event/orders/unread_counts` що повертає `{order_id: count}` одним хопом

### 2026-02-25 — Chat з клієнтом — окрема сторінка для менеджерів (P1) + 2 backend bug-fix
**Нова сторінка `/manager/chat`:**
- `/app/frontend/src/pages/ChatPage.jsx` — повноекранна Telegram-style розкладка: ліва панель — активні замовлення з пошуком + бейджем «нових», права — стрічка з повідомленнями і input.
- Polling 10с для активної розмови, 30с для списку. Realtime WebSocket — можна підключити пізніше через існуючий `order_chat_ws.py`.
- `App.tsx`: маршрут `/manager/chat` під `ProtectedRoute`.
- `CorporateHeader.tsx`: додано кнопку «Чат» з іконкою `MessageSquare`, видима тільки manager/admin, ховається на самій сторінці чату.

**Backend bug-fix #1 (виявлений testagent):** SQL crash при push-сповіщенні з чату
- `routes/order_chat.py` + `order_chat_ws.py` зверталися до неіснуючої колонки `orders.event_tool_customer_id` — push клієнту з чату ніколи не відправлявся (silent fail в except).
- Винесено логіку у новий helper `services/push_notifications._resolve_event_customer_for_order(db, order_id)` (feature-detect колонки + fallback на email). Нова функція `notify_chat_message()` — викликається з обох місць.

**Backend bug-fix #2 (виявлений testagent):** `decode_token` 500→401
- `routes/event_tool.py:157` робив `int(payload["sub"])` без try/except → admin/manager JWT (sub=email-string) кидав 500 у будь-яких `/cabinet/*` endpoints.
- Обгорнено в `try/except (TypeError, ValueError)`. Тепер коректний 401 «Customer not found».

**testing_agent_v3_fork (iteration_8.json):** ✅ **46/46 PASS** (test_manager_chat_page + test_image_url + test_cors). 0 critical, 0 minor. backend.err.log без `1054 Unknown column`.

**Code-review note (tech debt):** admin chat endpoints поки що БЕЗ auth check. Будь-хто з знанням order_id може писати від імені «Менеджер». Виправлення — окремий harden pass.

### 2026-02-25 — Refactor: централізований image-URL mapper layer
- **Чому**: попередній баг з подвійним `/uploads/uploads/` стався через локальну `def normalize_image_url` яка shadow-перекривала імпорт. Code-reviewer рекомендував витягнути логіку в окремі серіалізатори.
- **`/app/backend/utils/image_helper.py`**: додано `serialize_product_image(path) -> str` і `serialize_order_item_image(item_image, product_fallback) -> str`. Завжди повертають `""` замість `None` (JSON-friendly). Перший — простий wrapper, другий — централізує fallback логіку для order items.
- **`/app/backend/routes/event_tool.py`**: усі 6 inline-викликів `normalize_image_url(row[X])` замінено на названі серіалізатори (лінії 542, 601, 610, 927, 1059, 1981). Прямий імпорт `normalize_image_url` видалено — щоб неможливо було випадково shadow-перекрити.
- **testing_agent (iteration_6.json)**: 37/37 PASS (23 unit + 14 integration). Live дані Vita's orders все ще `uploads/products/LA277_LA277.jpg`. Жодних регресій. Контракт image_url змінився з `None` → `""` — frontend обидва трактує як falsy, тож user-facing змін немає.
- **Code-review note**: рекомендовано додати ruff `F811` / pylint `W0621` у CI, щоб ловити shadowing imports автоматично.

### 2026-02-25 — Fix: подвійний префікс `/uploads/uploads/` у URL картинок (P0)
- **Симптом** (скрін DevTools): на сторінці профілю → деталі замовлення всі картинки 404 з URL `https://farforevent.com.ua/uploads/uploads/products/TR9819_*.png`.
- **Корінь**: у `event_tool.py:get_my_order_by_id()` була оголошена **локальна функція** `normalize_image_url(url)` яка тінню перекривала глобальний імпорт `from utils.image_helper import normalize_image_url`. Локальна безумовно додавала `/uploads/` навіть до значень з префіксом `uploads/`.
- **Фікс**: видалено локальну функцію (рядки 1895-1904 у `event_tool.py`). Тепер усі 6 call-sites використовують єдиний глобальний хелпер, що коректно повертає `uploads/products/...` як є.
- **testing_agent (iteration_5.json)**: 19/19 PASS, 0 critical, 0 minor. Live перевірка Vita's orders 7795 і 7451 — image_url повертається у правильному вигляді (`uploads/products/LA277_LA277.jpg`).
- **Рекомендація CR**: увімкнути ruff `F811` / pylint `W0621` щоб ловити shadowing import-ів у майбутньому.

### 2026-02-25 — Підготовка backend до нового домену farforevent.com.ua
- **Діагноз з пода**: домен `farforevent.com.ua` має NXDOMAIN на Google DNS 8.8.8.8 — у реєстратора домену ще не створено A-запис. Це не баг коду, це настройка інфраструктури на VPS/реєстраторі. `ERR_TUNNEL_CONNECTION_FAILED` у браузері — наслідок: проксі/VPN/Cloudflare не може встановити upstream tunnel.
- **Code fix (бекенд готовий)**: у `/app/backend/server.py` додав 4 origins (`https://farforevent.com.ua`, `https://www.farforevent.com.ua`, http-варіанти) у `default_origins` ТА відрефакторив логіку CORS — env-origins тепер ОБ'ЄДНУЮТЬСЯ з default_origins (ordered de-dup), а не замінюють їх. Це усуває «footgun» з iteration_2 коли `CORS_ORIGINS` у .env приховував зміни в default_origins.
- **`.env` оновлено**: до `CORS_ORIGINS` дописані 4 нові варіанти (belt-and-suspenders).
- **Testing agent (iteration_3.json)**: 9/9 PASS. Усі 4 нові origins → 200 з правильним `Access-Control-Allow-Origin`, існуючі origins не зламані, evil-origin → 400.
- **VPS-частина** (на користувачі): `/app/deploy/SETUP_NEW_DOMAIN_farforevent.md` має покрокову інструкцію — DNS A-запис у реєстратора, Nginx vhost з `server_name farforevent.com.ua`, `certbot --nginx -d farforevent.com.ua -d www.farforevent.com.ua`.

### 2026-02-25 — CRITICAL FIX: Cross-client data leak in /cabinet/* (P0)
- **Симптом** (зі скріншоту): Vita (vitokdrako@gmail.com) у вкладці Профіль бачила дані Марини Ткачової (marinasummer80@gmail.com, +38(066)912-35-37).
- **Корінь**: ВСІ ендпоінти Cabinet 2.0 резолвили `client_users.id` через `event_customers.customer_id`. Це різні AUTO_INCREMENT простори → випадкова рівність → запит дістає чужий рядок.
- **Фікс**: новий хелпер `_resolve_client_user_id(db, customer)` в `event_tool.py` — резолвить за `client_users.email_normalized = :email` (lazy-create якщо немає). Замінено в 11 endpoints: /cabinet/profile (GET, PUT), /cabinet/payers (5 шт), /cabinet/master-agreement (3 шт), /cabinet/documents, /cabinet/documents/{id}/view, /cabinet/notifications/unread.
- **Додатково**: видалено помилковий JOIN-клоз `OR o.customer_id = :cuid` з 3 документ-запитів (порівнював OpenCart customers.customer_id з event_customers.customer_id).
- **Testing agent (iteration_1.json)**: 8/8 PASS. Vita тепер бачить власні id=54, email=vitokdrako@gmail.com, full_name=Вита Филимонихина (не Марина). Master agreement id=28 (не Марини 18/83). Payers/документи не містять рядків 'Марина' чи 'marinasummer80'.

### 2026-02-25 — Cabinet 2.0: Push-тригери на нові документи (P1)
- **Бекенд** — викликаємо `notify_document_ready(db, order_id, doc_type, doc_number)` з обох INSERT-точок: `documents.py:save_document` та `document_pdf.py:save_document_to_db`. Помилки push не ламають створення документа (try/except + log).
- **Покращення `notify_document_ready`**: fallback на `orders.customer_email` → `event_customers.email` коли `orders.event_tool_customer_id` NULL (актуально для замовлень з OpenCart).
- **«Новий документ» бейдж**: ідемпотентний ALTER `documents ADD COLUMN first_viewed_at TIMESTAMP NULL`, `/cabinet/documents` повертає `is_new` + `first_viewed_at`, `/cabinet/documents/{id}/view` помічає документ переглянутим (одноразово).
- **Новий endpoint** `GET /cabinet/notifications/unread` → `{new_documents: N}` для бейджа.
- **Frontend** — на вкладці "Документи (N нових)" автооновлюваний бейдж (1 хв), червоний пілл «НОВИЙ» біля кожного непереглянутого документа, перерахунок після кліку.
- **E2E через curl**: generate doc → unread=1 → view → unread=0 → generate знову → unread=1.
- ⚠️ **Push на пристрої** запрацює лише після HTTPS (`certbot --nginx -d farforrent.com.ua`) і коли клієнти підпишуться через `NotificationToggle` — бейджа в кабінеті це не стосується, він працює одразу.

### 2026-02-25 — Cabinet 2.0: Master Agreement (P0 закрито)
- **Backend (`event_tool.py`)**: 3 нові ендпоінти на існуючих таблицях `master_agreements` + `document_signatures` (БЕЗ нових таблиць):
  - `GET /api/event/cabinet/master-agreement` — стан договору, auto-create draft (executor=ТОВ ФАРФОР РЕНТ, 365 днів)
  - `POST /api/event/cabinet/master-agreement/sign` — приймає canvas-base64, INSERT у `document_signatures` з `document_id='master_agreement:<id>'` + signer_role='tenant' + IP + UA → UPDATE `master_agreements.status='signed'`, `client_users.active_master_agreement_id`
  - `GET /api/event/cabinet/master-agreement/view?token=...` — HTML-прев'ю через існуючий `services.pdf_generator.generate_master_agreement_html`
- **Гейт checkout**: `POST /event/boards/{id}/convert-to-order` повертає **412 + `code:"AGREEMENT_REQUIRED"`** якщо немає signed+valid договору
- **Frontend**: новий `SignMasterAgreementModal.js` (canvas + iframe прев'ю + чекбокс згоди + ПІБ), нова вкладка "Договір" у `UserProfile.js` з картою (№, статус, дійсний до, кнопки "Переглянути" / "Підписати"), `CheckoutModal` показує банер та блокує submit якщо `needs_signature=true`
- **E2E через curl**: convert→412 → sign → 200 → convert→200 path. Всі ендпоінти 401/405 на неправильний auth/method.
- **Фікс**: `LAST_INSERT_ID()` тепер викликається ДО `db.commit()` (інакше SQLAlchemy віддавав 0 через нову connection з пулу)

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
