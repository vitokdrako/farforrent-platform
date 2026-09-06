# Завдання №6 — Inventory залежностей Documents → Finance

Дата: 2026-09-05
Метод: `Editor.grep` по `fin_payments|fin_deposit_holds|fin_deposit_events` у всьому `backend/`,
далі точкове читання кожного блоку.

## 1. Межі аудиту

Модуль `documents` (за манифестом `core/module_manager/manifests.py`) містить 11 роутів:
`documents`, `document_render`, `document_pdf`, `document_signatures`, `document_manual_fields`,
`document_email`, `document_policy`, `master_agreements`, `order_annexes`, `template_admin`, `pdf`.

Результат сканування `fin_*` у цих файлах:

| Файл | Кількість `fin_*` |
|------|-------------------|
| `routes/documents.py` | 5 |
| `routes/document_policy.py` | 2 |
| `services/doc_engine/data_builders.py` | 3 |
| `routes/document_render.py`, `document_pdf.py`, `document_signatures.py`, `document_manual_fields.py`, `document_email.py`, `master_agreements.py`, `order_annexes.py`, `template_admin.py`, `pdf.py` | **0** |
| `services/document_context.py`, `doc_engine/render.py`, `doc_engine/numbering.py`, `doc_engine/registry.py`, `pdf_generator.py`, `company_config.py`, `template_loader.py` | **0** |

Отже реальна поверхня зв'язності Documents → Finance — **3 файли, 10 SQL-звернень**.

**Поза межами Завдання №6** (не Documents-модуль, не чіпаємо):
`finance.py` (80 — власник домену), `migrations.py` (16), `admin_orders.py` (10), `return_versions.py` (8),
`partial_returns.py` (6), `admin_finance.py` (3), `orders.py`, `issue_cards.py`, `product_damage_history.py`,
`dashboard_overview.py`, `calendar_events.py`, `archive.py`, `analytics.py` (по 1–2), тести, манифести.

## 2. Повний перелік звернень

Усі 10 звернень — **READ-ONLY**. Documents не робить жодного `INSERT`/`UPDATE`/`DELETE` у `fin_*`.
Це критичний факт: FinanceService для Documents може бути **read-only фасадом**,
і жодна фінансова бізнес-логіка (проведення транзакцій, зміна статусів застави) не переноситься.

### D1 — `routes/documents.py:2526` · `preview_settlement_act`
- Таблиця: `fin_payments` · Операція: **READ**
- SQL: `SELECT id, payment_type, method, amount, currency, payer_name, occurred_at, note, status, description ... WHERE order_id = :order_id ORDER BY occurred_at ASC`
- Призначення: акт взаєморозрахунків — розкладка `rent_paid` / `damage_paid` / `late_paid` (лише `completed|confirmed`), деталізація оплат, і окремо перевірка наявності запису `payment_type='discount'` (визначає, чи `orders.total_price` вже містить знижку).
- Необхідний результат: список платежів ордера з типом, методом, сумою, статусом, датою, notе/description.

### D2 — `routes/documents.py:2568` · `preview_settlement_act`
- Таблиця: `fin_deposit_holds` · Операція: **READ**
- SQL: `SELECT id, held_amount, used_amount, refunded_amount, status, actual_amount, currency, exchange_rate ... WHERE order_id = :order_id LIMIT 1`
- Призначення: блок «Застава» акта + розрахунок `deposit_net_for_charges = used + max(0, available)`, що входить у `calculated_balance`.
- Необхідний результат: одна застава ордера; `actual_amount` тут читається за правилом «`actual` якщо непорожній, інакше `held`».

### D3 — `routes/documents.py:2595` · `preview_settlement_act`
- Таблиця: `fin_deposit_events` · Операція: **READ**
- SQL: `SELECT event_type, amount, occurred_at, note ... WHERE deposit_id = :dep_id AND event_type = 'refunded' ORDER BY occurred_at`
- Призначення: деталізація фактичних повернень застави в акті.
- Необхідний результат: перелік подій повернення (сума, дата, примітка) для конкретної застави.

### D4 — `routes/documents.py:2626` · `preview_settlement_act`
- Таблиця: `fin_payments` · Операція: **READ (агрегація)**
- SQL: `SELECT COALESCE(SUM(amount), 0) ... WHERE order_id = :order_id AND payment_type = 'late' AND status = 'pending'`
- Призначення: `late_final` — нараховане менеджером прострочення, що ще не оплачене; входить у `grand_total_charges`.
- Необхідний результат: одне число — сума pending late-нарахувань.

### D5 — `services/doc_engine/data_builders.py:302` · `build_order_data`
- Таблиця: `fin_payments` · Операція: **READ**
- SQL: `SELECT payment_type, method, amount, note, occurred_at ... WHERE order_id = :order_id AND status IN ('completed','confirmed') ORDER BY occurred_at`
- Призначення: універсальний контекст документів — `payments[]`, `rent_paid`, `damage_paid`, `additional_paid`.
- Необхідний результат: підтверджені платежі ордера.

### D6 — `services/doc_engine/data_builders.py:339` · `build_order_data`
- Таблиця: `fin_deposit_holds` · Операція: **READ**
- SQL: `SELECT held_amount, used_amount, refunded_amount, actual_amount, currency, exchange_rate ... WHERE order_id = :order_id LIMIT 1`
- Призначення: `deposit_data` у контексті документів (`held`, `used`, `refunded`, `actual_amount`, `currency`, `exchange_rate`, `available`).
- Необхідний результат: одна застава ордера. Увага: тут `actual_amount` читається «сирим» (`or 0`), а `exchange_rate` з дефолтом `1` — семантика відрізняється від D2, обидві треба зберегти дослівно.

### D7 — `services/doc_engine/data_builders.py:761` · `build_defect_act_data`
- Таблиця: `fin_payments` · Операція: **READ**
- SQL: `SELECT amount, status, note ... WHERE order_id = :order_id AND payment_type = 'late' ORDER BY occurred_at`
- Призначення: рядки прострочення в акті дефектів + `late_total`.
- Необхідний результат: усі late-записи ордера (будь-який статус) з сумою, статусом, примiткою.

### D8 — `routes/document_policy.py:507` · `check_document_policy`
- Таблиця: `fin_deposit_holds` · Операція: **READ (через `LEFT JOIN`)**
- SQL: `... COALESCE(d.held_amount, 0) AS deposit_held, COALESCE(d.held_amount - d.used_amount - d.refunded_amount, 0) AS deposit_to_refund FROM orders o LEFT JOIN fin_deposit_holds d ON d.order_id = o.order_id WHERE o.order_id = :order_id`
- Призначення: поля `deposit_held` / `deposit_to_refund` в `order_data`, за якими policy-матриця вирішує доступність документів повернення застави.
- Необхідний результат: дві величини по ордеру. `LEFT JOIN` + `fetchone()` фактично бере одну заставу — еквівалент `LIMIT 1`.

### D9 — `routes/document_policy.py:616` · другий policy-хендлер
- Таблиця: `fin_deposit_holds` · Операція: **READ (через `LEFT JOIN`)**
- Ідентичний D8 запит і призначення (дубль SQL у другому endpoint).

### D10 — Похідна залежність манифеста
- `core/module_manager/manifests.py`: `DOCUMENTS.requires = (core, rental, crm, finance)` + note «Finance = OFF поки неможливий».
- Після Завдання №6 нота має відображати, що доступ іде через фасад і Finance OFF деградує контрольовано.

## 3. Зведення

| ID | Файл | Таблиця | Оп. | Що саме потрібно |
|----|------|---------|-----|------------------|
| D1 | documents.py | fin_payments | R | усі платежі ордера |
| D2 | documents.py | fin_deposit_holds | R | застава ордера (actual-or-held) |
| D3 | documents.py | fin_deposit_events | R | події `refunded` застави |
| D4 | documents.py | fin_payments | R | SUM pending late |
| D5 | data_builders.py | fin_payments | R | підтверджені платежі |
| D6 | data_builders.py | fin_deposit_holds | R | застава ордера (raw actual) |
| D7 | data_builders.py | fin_payments | R | усі late-записи |
| D8 | document_policy.py | fin_deposit_holds | R | held + to_refund |
| D9 | document_policy.py | fin_deposit_holds | R | held + to_refund |

Записів: **0**. Транзакцій/проведень: **0**. Тобто Documents — чистий читач Finance.

## 4. Контракт фасаду (рішення)

`backend/services/finance/finance_service.py` — read-only фасад над `fin_*`:

- `list_order_payments(db, order_id, statuses=None, payment_types=None) -> PaymentsSnapshot` → D1, D5, D7
- `get_pending_late_total(db, order_id) -> LateFeeSnapshot` → D4
- `get_order_deposit(db, order_id) -> DepositSnapshot` → D2, D6
- `list_deposit_refund_events(db, deposit_id) -> DepositEventsSnapshot` → D3
- `get_order_deposit_balance(db, order_id) -> DepositBalanceSnapshot` → D8, D9

Кожен snapshot несе `available: bool` + `status: "available" | "disabled"`.
Коли модуль `finance` вимкнений — повертається порожній snapshot зі `status="disabled"`,
без винятків і без 500-ї; документ рендериться з нульовими фінансовими блоками
і прапорцем `finance_unavailable` у контексті.

Жодна фінансова бізнес-логіка не переноситься й не дублюється: правила розрахунку
акта (`grand_total_charges`, `calculated_balance`, manager override) залишаються в Documents,
бо це логіка документа, а не фінансів. Фасад віддає лише дані.