# RentalHub - Rental Management Platform

## Original Problem Statement
Comprehensive rental management platform (React + FastAPI + MySQL) syncing from OpenCart DB. Manages orders, inventory, auditing, damage tracking, issue cards, returns, and financial workflows.

## Core Requirements
- Multi-role support: Admin, Manager, Requisitor
- Order lifecycle: Draft → Awaiting → Processing → Issued → Returned
- Inventory sync from OpenCart (RentalHub as source of truth — reverse sync)
- Damage tracking with photos and history
- Financial tracking (payments, deposits, refunds)
- Calendar, catalog, moodboard features
- Mobile-friendly UI for warehouse workers

## Test Credentials
See `/app/memory/test_credentials.md`

## What's Been Implemented (latest first)


### 2026-02-21 — VPS Deployment Recovery + OpenCart Image Sync 🔥
**Контекст:** VPS `173.242.49.48` (Ubuntu 24.04). Локальна БД `farforrent` була дропнута битим `cron_refresh_db.sh` (маскував помилки `2>/dev/null`). Бекенд лежав. Python deps не ставились через PEP 668.

**Що зроблено:**
- ✅ Створена ізольована БД-копія `farforre_vps` на `farforre.mysql.tools` (user: `farforre_vps`/`EDt869Up6y`). Продакшн `farforre_rentalhub` залишається недоторканим.
- ✅ `backend/.env` переключено на `farforre_vps` (RH_DB_HOST/USERNAME/PASSWORD/DATABASE).
- ✅ Всі Python deps вже були у venv (`/var/www/farforrent/backend/venv/`): `python-dotenv 1.2.1`, `pywebpush 2.3.0`, `websockets 16.0`, `pymysql 1.1.2`, `cryptography 46.0.3`. Глобальний `pip install` не потрібен.
- ✅ Створено таблицю `product_images` (її не було в копії) — `CREATE TABLE IF NOT EXISTS product_images (id, product_id, image_url, sort_order, is_primary, source, created_at)`. Створення товарів через адмінку запрацювало.
- ✅ Видалені 9777 битих "PNG" файлів (насправді HTML-сторінки помилок з failed wget) → перенесені в `/var/www/farforrent/db_backups/broken_pngs/`.
- ✅ Скрипт `/var/www/farforrent/backend/populate_product_images_from_thumbnails.py` — мапить файли з `thumbnails/oc_{pid}_{pid}_{N}_{ts}.jpg` → `product_images` + `products.image_url`. Заповнив **7248 товарів** з 9409 файлів.
- ✅ `image_url` обнулено для ~440 товарів з битими посиланнями (тепер фронт показує placeholder замість 404).
- ✅ Cron `cron_refresh_db.sh` (drop+import) вимкнено з кронтабу — більше не дропає БД.
- ✅ `event-tool-backend.service` зупинений+disabled (267k+ рестартів з `status=203/EXEC`, файл `sync_all.py` не існував).

**OpenCart image-only sync (НОВЕ):**
- ✅ `/var/www/farforrent/backend/sync_images_only.py` — легкий sync лише фото (без замовлень/продуктів).
  - Підключається до OC БД (`farforre_db`/`gPpAHTvv` на `farforre.mysql.tools`) READ-ONLY
  - Тягне фото з `https://www.farforrent.com.ua/image/{oc_path}` для товарів з `image_url IS NULL`
  - Зберігає у `/var/www/farforrent/backend/uploads/products/{SKU}_{TIMESTAMP}.{ext}`
  - Створює thumbnails (300x300) і medium (800x800)
  - Оновлює `farforre_vps.products.image_url` + `product_images` (source='opencart_sync')
  - BATCH=100 на запуск
- ✅ Cron `*/30 * * * * /usr/local/bin/farforrent-image-sync.sh` → log у `/var/log/farforrent/image_sync.log`
- ✅ Перший прогін: 99 ок, 0 fail, 1 skip (RH-9828 — тестовий товар без OC).

**Поточний стан:** Сайт працює (БД 541 orders, 7740 products). Event Tool, Admin, створення/редагування — все ОК. Залишилось 340 товарів без фото — догнаються наступними прогонами cron.



### 2026-02-13 (cont. 3) — P3 Backlog Execution
- **WebSockets real-time chat**: 
  - Backend: `routes/order_chat_ws.py` — WS-роутер на `/api/ws/chat/client/{order_id}?token=...` (JWT-auth) і `/api/ws/chat/admin/{order_id}`. In-memory `ChatRoom` pub/sub з broadcast'ом між учасниками. Підтримує `init/new_message/typing/read_receipt/ping/pong`.
  - Frontend `OrderChat.js` повністю переписаний: WebSocket з auto-reconnect (3s backoff), fallback на polling при відмові, heartbeat 25s, typing indicator з debouncing. Іконка Wifi/WifiOff показує тип з'єднання.
  - Push клієнту відправляється тільки коли клієнт НЕ підключений по WS (логічна оптимізація: не дублюємо real-time повідомлення).
  - Встановлено `websockets` пакет (для тестування + uvicorn WS bridge).
  - E2E тест WS: init → send (client) → broadcast → send (admin) → typing → ping/pong → PASS.

- **Centralized Company Profiles**:
  - Міграція `011_company_profiles.sql` створює таблицю + 2 колонки в `orders` (`company_profile_id`, `company_snapshot_json`).
  - Seed: дефолтна компанія "FarforDecorOrenda" з `system_settings`.
  - Backend: `routes/company_profiles.py` з CRUD (`GET / / /default / /{id}`, `POST / PUT / PATCH / DELETE` soft-delete) + assign-to-order + snapshot pattern. Префікс: `/api/admin/company-profiles`.
  - `data_builders.build_order_data` тепер бере company-info з пріоритетом: `orders.company_snapshot_json` → `company_profiles` (live by id) → `get_company_config` (fallback system_settings/defaults). Підтримує `logo_url` та `stamp_url` у документах.
  - Підтримується багато юр. осіб (ФОП/ТОВ/Individual), кожна може бути дефолтом, по умовчанню активний один.

- **Data migration `return_cards` → `partial_return_versions`**:
  - Скрипт: `migrate_return_cards.py` (з `--dry-run`).
  - Реальне виконання: 1 запис мігровано → версія 289 з 2 items, статус→active, note містить trace до оригіналу.
  - `archive.py` та `orders.py` тепер читають returns з `partial_return_versions`+`partial_return_version_items` (єдине джерело правди). Поле `return_cards` у відповідях API залишено для backward-compatibility frontend (та сама форма даних, але з нового джерела).
  - `return_cards.py` роут НЕ видалено — досі обслуговує endpoint `/api/decor-orders/{id}/complete-return` (legacy decor flow) та має ON DUPLICATE KEY savepoints. Marked DEPRECATED у docstring. Видалення = окрема ітерація після рефактору `complete-return`.


### 2026-02-13 (cont. 2) — P2 Backlog Execution
- **P2 Moodboard Export**: додано `html-to-image` (yarn add), кнопка "Завантажити PNG" у хедері `MoodboardCanvas.js`. Експорт враховує zoom (зберігає у 1200×800 @ 2x), пропускає елементи `moveable-control-box`, ставить вибраний background. PNG-файл з безпечним кирилично-латинським іменем.
- **P2 Inline погодження кошторису**:
  - Backend: новий ендпойнт `POST /api/event/orders/{order_id}/documents/{doc_id}/approve` (тільки для `doc_type ∈ {estimate, invoice_offer, quote, preliminary_estimate}` або `category=quote`). Створює `document_signatures` рядок з `signer_role='tenant', signature_image='APPROVED_INLINE'`, переводить документ у `status='approved'`, логує `order_lifecycle.estimate_approved`.
  - Frontend: кнопка "✓ Погодити" та бейдж "Погоджено" у списку документів `UserProfile.js`.
- **P2 Двосторонній чат менеджер↔клієнт**:
  - Backend: новий модуль `routes/order_chat.py` з двома роутерами (client + admin), міграція `009_order_chat.sql`. Endpoint'и: `GET/POST /chat/messages` та `GET /chat/unread_count`. Read-receipts для обох сторін (`read_by_client_at`, `read_by_manager_at`). При повідомленні менеджера — автоматичний Web Push клієнту.
  - Frontend: компонент `OrderChat.js` з polling (10s), bubble-UI, авто-скрол, Enter→send, Shift+Enter→новий рядок. Інтегрований у розгорнуту картку замовлення в `UserProfile.js`.
  - API клієнт: `api/chat.js`.
- **Migration 010 — document_signatures**: таблиця згадувалася у коді, але не була явно створена. Тепер є + міграційний файл.
- **E2E test**: `tests/test_p2_chat_approval.py` — повністю верифікує чат-flow + inline-approve + відмову для non-estimate доків.

### Database refresh tool
- Створено `deploy/refresh_db_from_cloud.sh` — безпечне (з бекапом) копіювання cloud DB на VPS. Запускається на VPS, дампить cloud → дропає локальну → імпортує. Чітка статистика по orders/products/fin_payments після завершення.


### 2026-02-13 (cont.) — P1 Backlog Execution
- **P1 Invoice_legal**: Перевірено — шаблон рендериться коректно з усіма типами `payer_type` (individual / fop_simple / fop_general / llc_simple / llc_general). Помилку було усунено в попередніх ітераціях.
- **P1 Favorites (♡)**:
  - Backend: міграція `007_event_favorites.sql` + 4 ендпойнти: `GET /api/event/favorites`, `GET /favorites/products`, `POST /favorites/{id}`, `DELETE /favorites/{id}`.
  - Frontend: `api/favorites.js`, `context/FavoritesContext.js` (з optimistic update + localStorage cache), кнопка ♡ на `ProductCard.js`, нова сторінка `pages/FavoritesPage.js` (route `/favorites`), пункт в `MobileBottomNav.js` з лічильником обраних.
  - Працює і для гостей (локальний кеш), синкається на сервер при логіні. Протестовано через curl.
- **P1 Web Push сповіщення**:
  - Backend: `services/push_notifications.py` (з VAPID keys через `pywebpush`), міграція `008_push_subscriptions.sql`. Ендпойнти: `GET /push/public-key`, `POST /push/subscribe`, `POST /push/unsubscribe`, `POST /push/test`. Helpers: `notify_order_status_change()`, `notify_document_ready()`.
  - Hook у `routes/admin_orders.py` `update_order_finance`: при зміні `status` клієнт отримає push.
  - Frontend: Service Worker `public/sw.js`, `api/push.js`, компонент `NotificationToggle.js` в профілі клієнта (з кнопкою "Надіслати тестове сповіщення"). 
  - VAPID keys згенеровано та збережено в `backend/.env` (`VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_PEM_BASE64`, `VAPID_SUBJECT`).
  - pywebpush, py-vapid, http-ece додано до залежностей backend.
- **Refactor**: `return_cards.py` помічено як DEPRECATED у docstring (видалення відкладено до міграції історичних даних в `partial_return_versions`).

**ВАЖЛИВО для VPS-деплою** — додати у `.env` сервера:
```
VAPID_PUBLIC_KEY=BDv9Q_MFsHka2tT2hI-I5E0vVEWGajomsa3qZ2Ymmj55JvUoaF_r-veEsm51aL86gVHa3wO_bsq_UhjuaOYcY3I
VAPID_PRIVATE_PEM_BASE64=<скопіювати з /app/backend/.env>
VAPID_SUBJECT=mailto:info@farforrent.com.ua
```
Та запустити міграції `005, 006, 007, 008`.


### 2026-02-13 — Fix P0: "Помилка збереження списання" + finance sync + doc photos
- **Root cause (P0)**: MySQL trigger `fin_payments_after_insert` had self-referencing `UPDATE fin_payments SET tx_id = LAST_INSERT_ID()` inside an AFTER INSERT trigger → MySQL error 1442. Trigger `fin_transactions_after_insert` then mirrored back into `fin_payments` → circular insert. Effect: ANY `fin_payments` insert (payments, write-offs) silently failed.
- **Fix applied**:
  - Migration `005_fix_fin_triggers_recursion.sql`: removed recursive UPDATE, added `[from fp #...]` guard in mirror trigger.
  - Migration `006_drop_fin_transactions_after_insert.sql`: dropped reverse-mirror trigger after refactoring `admin_finance.create_transaction` to write fin_payments only (trigger creates the matching tx).
  - `routes/return_versions.py`: fixed `SELECT order_id FROM partial_return_versions` → `parent_order_id` (column was misnamed).
- **Documents photo = single source of truth**: `services/doc_engine/data_builders.py` now resolves `products.image_url` via new `resolve_product_image()` / `pick_product_image()` helpers (base64 for local files, absolute URL via BACKEND_PUBLIC_URL otherwise). `oi.image_url` is now a legacy fallback only. All builders (rental_agreement, issue_card, return_act) use products as the canonical source.
- **E2E validation** (`backend/tests/test_full_order_cycle.py`): registers Event Tool user → creates board with items → converts to order (IT-10001) → adds rent+deposit payments via admin/finance → creates return version → marks 3 items as TOTAL LOSS → verifies finance summary (paid_rent=500, paid_deposit=200, extra_charges=1500, debt=6400) with no duplicate fin_payments rows.
- **Test cleanup**: VPS deploy is required to pick up new migrations — run `mysql ... < migrations/005...sql` and `migrations/006...sql` before restarting backend.

### 2026-02-05
- **Repo cleanup**: видалено ~50 одноразових скриптів з `/app/backend/` (sync_*, check_*, migrate_*, fix_*, update_*, setup_rentalhub_*, test_* в корені, *.xlsx).
- **Безпека**: `backend/.encryption_key` прибрано з git tracking + додано в `.gitignore`.
- **Дублікати видалено**: `models_extended.py`, `finance_rules.py` (не імпортуються), `nginx-rentalhub-unified.conf` (застарілий).
- **Event Tool mobile fix — sidebar fullscreen**: `mobile.css` тепер правильно таргетить `.fd-side-panel` (раніше селектор не співпадав, тому каталог-чіпси "проступали" через мудборд). Додано клас `body.sidebar-open` що приховує chips/FAB коли мудборд відкритий.
- **Event Tool — інфініт-скрол пагінація**: автозавантаження товарів при прокрутці до низу через `IntersectionObserver` + fallback-кнопка + лічильник "Показано N".
- **deploy.sh — авто-оновлення Python deps**: додано `pip install -r requirements.txt` у venv та діагностику бек-логів при невдалому старті (виводить останні 30 рядків при HTTP 000/502).

### 2026-05-28
- **Mobile UI: top toolbars refactored** on `ManagerDashboard.jsx` and `PickingListPage.jsx` (smaller paddings, `text-xs/sm:text-sm`, flex-wrap with smaller gaps; search and counter stack vertically on mobile).
- **Back button navigation fix**:
  - `CorporateHeader.tsx` now uses `location.key !== 'default'` to detect real history (replaces fragile `window.history.length > 1`).
  - Back button now visible on mobile (icon + label on desktop, icon only on mobile).
  - Default fallback dashboard is role-based (`/manager-cabinet` for manager, `/manager` otherwise).
  - Removed hardcoded `navigate('/manager')` overrides in `PersonalCabinet`, `AdminPanel`, `UnifiedCalendarNew` — they now use smart default.
  - Added `showBackButton` to `ReauditCabinetFull`, `CatalogBoard`, `ManagerCabinet`, `PickingListPage`.
  - Removed duplicate toolbar back button from `PickingListPage`.

### 2026-02 / Earlier
- Reverse sync from RentalHub → OpenCart (`sync_all.py`).
- Picking List page (`PickingListPage.jsx`) with task integration, kits, zone grouping.
- Reaudit CRUD: create with auto-SKU, duplicate.
- Restored 5-tab Kasa finance UI (`KasaPage.jsx`, 1900+ lines) and Admin panel (`AdminPanel.jsx`).
- Added `components` column to products table for kits.
- Damage history with photos, badges on cards.
- OpenCart sync (categories, products, inventory).
- Production build workflow: build at `/app/clean_project/frontend_admin_src/build/` → copied to `/app/clean_project/frontend_build/`.

## Pending / Roadmap

### P0
- (none currently — last P0 mobile UI + Back nav resolved 2026-05-28)

### P1
- Fix Jinja2 syntax in `invoice_legal` template (FOP/TOV conditional logic). File: `backend/services/doc_engine/data_builders.py`.
- Post-deployment health check across all major features.

### P2
- Stabilize `convert-to-order` endpoint.
- Restore Moodboard export.
- Recurring Calendar timezone bug.
- Unify Catalog + Reaudit into single `/products` interface.
- Simplify `laundry_items` table/logic.

### P3 / Future
- WebSockets for real-time client cabinet updates.
- Unify `NewOrderViewWorkspace.jsx` + `IssueCardWorkspace.jsx`.
- Full RBAC.
- HR/Ops module.
- Telegram bot integration.

## Architecture
```
/app/
├── backend/
│   ├── routes/
│   │   ├── audit.py             # Inventory CRUD
│   │   ├── picking_list.py      # Picking list API
│   │   ├── finance.py           # 4000+ line advanced finance
│   │   ├── admin_orders.py      
│   │   ├── bulk_products.py     
│   ├── sync_all.py              # OpenCart reverse-sync cron
└── frontend/
    └── src/
        ├── pages/
        │   ├── KasaPage.jsx
        │   ├── PickingListPage.jsx
        │   ├── ManagerDashboard.jsx
        │   ├── AdminPanel.jsx
        ├── components/
        │   └── CorporateHeader.tsx  # Centralized Back button logic
```

## Build Workflow (deploy)
1. Edit `/app/frontend/src/**`
2. `rsync -av --exclude node_modules --exclude build /app/frontend/src/ /app/clean_project/frontend_admin_src/src/`
3. `cd /app/clean_project/frontend_admin_src && yarn build`
4. `rsync -av --delete /app/clean_project/frontend_admin_src/build/ /app/clean_project/frontend_build/`
