# Повний аналіз системи RentalHub — Березень 2026

## 1. Архітектура

### Дві бази даних MySQL
| БД | Хост | Таблиць | Призначення |
|---|---|---|---|
| `farforre_db` (OpenCart) | farforre.mysql.tools | 206 | E-commerce, товари, замовлення сайту |
| `farforre_rentalhub` | farforre.mysql.tools | 72 | Бекофіс: замовлення, фінанси, документи, шкода |

### Потік даних
```
OpenCart (сайт) → Sync → RentalHub (бекофіс)
                          ↓
                    Frontend (React)
```

Синхронізація: `sync.py`, `order_sync.py` — копіюють замовлення та товари з OpenCart у RentalHub.

---

## 2. КРИТИЧНІ ПРОБЛЕМИ

### 2.1. Дубляж систем статусу товару (4 місця!)

Стан товару зберігається в **4 різних місцях**, які часто суперечать одне одному:

| Джерело | Поле | Приклад значень | Рядків з даними |
|---|---|---|---|
| `products.state` | varchar(50) | `available`, `on_wash`, `on_repair`, `on_laundry`, `damaged`, `written_off` | ~127 з ненульовим frozen_qty |
| `products.product_state` | varchar(50) | `available`, `shelf` | Не використовується активно |
| `product_cleaning_status` | enum status | `clean`, `wash`, `dry`, `repair` | 494 записи |
| `product_damage_history` | processing_type + processing_status | `wash/pending`, `restoration/hidden` тощо | 230 записів |

**Проблема:** Каталог читає `products.state` і `products.frozen_quantity`, а Кабінет Шкоди читає `product_damage_history`. Синхронізація між ними — ручна і нестабільна.

**Рекомендація:** `product_damage_history` має бути **єдиним джерелом істини** для стану обробки. `products.state` та `product_cleaning_status` — видалити або зробити кешованим полем.

### 2.2. Подвійна фінансова система

| Таблиця | Рядків | Дати | Використання |
|---|---|---|---|
| `finance_transactions` | 299 | 2026-01 — 2026-03 | Стара система (orders.py, user_tracking.py) |
| `fin_transactions` | 199 | 2026-01 — 2026-03 | Нова система (finance.py) |
| `fin_payments` | 223 | — | Нова система |
| `fin_deposit_holds` | 12 | — | Нова система |
| `fin_ledger_entries` | 398 | — | Нова система (подвійний запис) |

**Проблема:** Дві паралельні фінансові системи, які обидві активні. `finance_transactions` використовується в `orders.py` для запису транзакцій, а `fin_*` таблиці — в `finance.py` для FinanceHub.

**Рекомендація:** Мігрувати всі записи з `finance_transactions` в `fin_transactions` та видалити стару таблицю.

### 2.3. Подвійна система пошкоджень

| Таблиця | Рядків | Призначення |
|---|---|---|
| `damages` + `damage_items` | 49 + 49 | Стара система "кейсів шкоди" |
| `product_damage_history` | 230 | Нова система (Кабінет Шкоди) |

**Проблема:** `damages` + `damage_items` — це стара система, яка все ще використовується в `damage_cases.py` і `audit.py`. Нова система `product_damage_history` — це те, що використовує Кабінет Шкоди.

**Рекомендація:** Визначити, чи потрібні обидві. Якщо `damages` використовується лише для архівних даних — позначити як legacy.

### 2.4. `processing_type` enum неконсистентний

Поточні значення в `product_damage_history.processing_type`:
- `wash` — мийка (стара назва)
- `washing` — прання (нова назва)
- `laundry` — хімчистка/пральня
- `restoration` — реставрація
- `none`, `''` — не призначено

**Проблема:** `wash` vs `washing` створює плутанину. В UI "Мийка" = `wash`+`washing`, "Пральня" = `laundry`. Але в коді їх обробка дублюється (`IN ('wash', 'washing')`).

**Рекомендація:** Уніфікувати: `wash` (мийка), `laundry` (пральня), `restoration` (реставрація). Мігрувати всі `washing` → `wash`.

---

## 3. ПОРОЖНІ ТАБЛИЦІ (18 шт.) — кандидати на видалення

| Таблиця | Статус | Рекомендація |
|---|---|---|
| `customers` | 0 рядків | Дубляж OpenCart `oc_customer` + `client_users`. **ВИДАЛИТИ** |
| `inventory` | 0 рядків | Замінена полями в `products`. **ВИДАЛИТИ** |
| `inventory_recounts` | 0 рядків | Ніколи не використовувалась. **ВИДАЛИТИ** |
| `product_cleaning` | 0 рядків | Замінена `product_damage_history`. **ВИДАЛИТИ** |
| `product_lifecycle` | 0 рядків | Ніколи не використовувалась. **ВИДАЛИТИ** |
| `product_reservations` | 0 рядків | Ніколи не використовувалась. **ВИДАЛИТИ** |
| `product_sets` + `product_set_items` | 0 рядків | Функціонал не реалізований. **ЗАЛИШИТИ** (може знадобитися) |
| `order_annexes` | 0 рядків | Частина документ-системи. **ЗАЛИШИТИ** |
| `order_notes` | 0 рядків | Замінена `order_internal_notes` (162 рядки). **ВИДАЛИТИ** |
| `order_item_packing` | 0 рядків | Функціонал пакування не реалізований. **ВИДАЛИТИ** |
| `document_signatures` | 0 рядків | Частина документ-системи. **ЗАЛИШИТИ** |
| `expense_due_items` + `expense_templates` | 0 рядків | Функціонал шаблонів витрат. **ЗАЛИШИТИ** |
| `fin_encashments` | 0 рядків | Інкасація. **ЗАЛИШИТИ** |
| `fin_vendors` | 0 рядків | Постачальники. **ЗАЛИШИТИ** |
| `rh_employees` + `hr_payroll` | 0 рядків | HR модуль не реалізований. **ЗАЛИШИТИ** |

**Безпечно видалити:** `customers`, `inventory`, `inventory_recounts`, `product_cleaning`, `product_lifecycle`, `product_reservations`, `order_notes`, `order_item_packing` = **8 таблиць**

---

## 4. СТАРІ/BACKUP ФАЙЛИ (кандидати на видалення)

### Backend route files:
| Файл | Рядків | Статус |
|---|---|---|
| `archive_old.py` | — | Замінений `archive.py`. **ВИДАЛИТИ** |
| `audit.py.backup` | — | Бекап. **ВИДАЛИТИ** |
| `catalog_old.py` | 532 | Замінений `catalog.py`. **ВИДАЛИТИ** |
| `damages.py.backup` | — | Бекап. **ВИДАЛИТИ** |
| `damages_old.py` | — | Замінений `damages.py`. **ВИДАЛИТИ** |
| `extended_catalog_old.py` | 640 | Замінений `extended_catalog.py`. **ВИДАЛИТИ** |
| `finance_old.py` | 638 | Замінений `finance.py`. **ВИДАЛИТИ** |
| `issue_cards_old.py` | — | Замінений `issue_cards.py`. **ВИДАЛИТИ** |
| `orders.py.backup` | — | Бекап. **ВИДАЛИТИ** |
| `orders_old_full.py` | 2413 | Стара версія `orders.py`. **ВИДАЛИТИ** |
| `orders_simple_backup.py` | — | Бекап. **ВИДАЛИТИ** |
| `products.py.backup` | — | Бекап. **ВИДАЛИТИ** |
| `return_cards_old.py` | — | Замінений `return_cards.py`. **ВИДАЛИТИ** |
| `tasks_old.py` | — | Замінений `tasks.py`. **ВИДАЛИТИ** |

**Всього: 14 файлів для видалення** (не імпортуються в server.py)

### Frontend files:
| Файл | Статус |
|---|---|
| `DamageCabinet.tsx.backup` | Замінений `DamageHubApp.jsx`. **ВИДАЛИТИ** |
| `DamageCabinet.tsx.broken` | Зламаний. **ВИДАЛИТИ** |
| `DamageCabinet_New.tsx` | Не використовується (є DamageHubApp.jsx). **ПЕРЕВІРИТИ** |
| `FinanceConsoleApp_old.jsx` | Замінений `FinanceHub.jsx`. **ВИДАЛИТИ** |

---

## 5. ПРОБЛЕМА ПРОДУКТИВНОСТІ

### Каталог API (`/api/catalog/items-by-category`)
**Проблема:** Для кожного запиту виконується 4-5 окремих SQL запитів:
1. Основний запит products
2. reserved_dict (orders)
3. in_rent_dict (orders)
4. who_has_dict (orders)
5. partial_return_dict (partial returns)
6. processing_dict (product_damage_history)

**Рекомендація:** Об'єднати в один SQL з JOIN/subquery або використовувати кешування.

### `/api/catalog/families`
**Проблема:** N+1 запитів — для кожного набору виконується окремий запит на товари.

**Рекомендація:** Зробити один JOIN запит замість циклу.

---

## 6. СХЕМА РЕКОМЕНДОВАНИХ ЗМІН

### Фаза 1: Очистка (низький ризик)
- [ ] Видалити 14 backup файлів бекенду
- [ ] Видалити 3-4 старі frontend файли
- [ ] Видалити 8 порожніх таблиць
- [ ] Уніфікувати `washing` → `wash` в product_damage_history

### Фаза 2: Консолідація статусів (середній ризик)
- [ ] Зробити `product_damage_history` єдиним джерелом для стану обробки
- [ ] Видалити або deprecated `product_cleaning_status` (494 рядки → мігрувати в pdh)
- [ ] Видалити `products.product_state` (не використовується)
- [ ] `products.state` та `products.frozen_quantity` — розраховувати динамічно або оновлювати через тригери

### Фаза 3: Фінансова консолідація (високий ризик)
- [ ] Мігрувати `finance_transactions` → `fin_transactions`
- [ ] Оновити `orders.py` для використання `fin_*` таблиць
- [ ] Видалити `finance_transactions`

### Фаза 4: Оптимізація продуктивності
- [ ] Оптимізувати `/api/catalog/families` (N+1 → JOIN)
- [ ] Додати індекси на часто використовувані JOIN умови
- [ ] Кешувати processing_dict (рідко змінюється)

---

## 7. ЗАГАЛЬНА СТАТИСТИКА

| Метрика | Значення |
|---|---|
| Таблиць RentalHub | 72 |
| Порожніх таблиць | 18 (25%) |
| Безпечно видалити | 8 таблиць |
| Backup файлів бекенду | 14 |
| Backend route файлів | 57 |
| Frontend сторінок | ~30 |
| Найбільший route файл | `orders.py` (3280 рядків) |
| Найбільша frontend сторінка | `FinanceHub.jsx` (3330 рядків) |

---

## 8. ТОВАРИ З НЕКОРЕКТНИМ frozen_quantity

На даний момент лише **1 товар** має frozen_quantity яка не відповідає активним записам damage_history:
- `product_id=77, sku=GL004, state=on_wash, frozen=7` — немає активного запису в PDH

Також є **3 товари з state=available але frozen_quantity > 0**:
- Це означає що frozen_quantity не було очищене при завершенні обробки

**Рекомендація:** Запустити `/api/product-damage-history/fix-frozen-quantities` ще раз для синхронізації.
