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
