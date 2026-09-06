# Завдання №5 — план розриву cross-route dependencies

Статус: **план зафіксований, модифікація не розпочата.**

Базова лінія перед змінами: `70` `include_router`, `582` endpoints, security tests 19/19.

Цільове правило після рефакторингу:

```
routes  ->  services / core  ->  models / database
```

і **ніколи** `route A -> route B`.

---

## 1. Повний список фактичних cross-route imports (5/5)

Виявлено статичним скануванням усіх 70 файлів у `backend/routes/`.
Врахований і top-level, і lazy (in-function) import.

### #1 `order_chat_ws.py:31` -> `order_chat` (top-level)

| Поле | Значення |
|------|----------|
| Хто імпортує | `routes/order_chat_ws.py`, рядок 31 (module-level) |
| Що імпортується | `_serialize_message`, `_list_messages`, `_verify_order_belongs_to_client` |
| Навіщо | WebSocket-хендлери віддають той самий формат повідомлень і застосовують ту саму перевірку належності замовлення клієнту, що й HTTP-роут чату |
| Спосіб розриву | Перенести три хелпери в новий `services/chat_service.py`. `order_chat.py` реекспортує ті самі імена (щоб його власні виклики та формат відповіді не змінилися), `order_chat_ws.py` імпортує з сервісу. SQL-запити переносяться без змін |
| Ризик | Низький. Формат `_serialize_message` — це частина payload WS та HTTP; переносимо код 1:1, без правок |

### #2 `order_chat_ws.py:131` -> `event_tool.decode_token` (lazy, у WS-хендлері)

| Поле | Значення |
|------|----------|
| Хто імпортує | `routes/order_chat_ws.py`, рядок 131, всередині `chat_client_ws` |
| Що імпортується | `decode_token(token) -> dict` |
| Навіщо | Автентифікація клієнтського WebSocket через JWT у query-параметрі `?token=` |
| Спосіб розриву | Перенести декодування в `core/security.py`: `decode_jwt_token(token) -> dict` (чистий, без FastAPI-залежностей, кидає нейтральний `TokenError`). `event_tool.decode_token` залишається тонкою обгорткою, яка мапить `TokenError` у ті самі `HTTPException(401, "Token expired" / "Invalid token")`. `order_chat_ws` імпортує з `core.security` |
| Незмінне | Алгоритм HS256, секрет із `get_jwt_secret()`, приведення `sub` до int із тим самим `try/except`, тексти помилок 401 |
| Ризик | Низький. `order_chat_ws` уже ловить `except Exception` і віддає `{"type":"error"}` + close 4401 — поведінка WS не змінюється |

### #3 `order_chat.py:85` -> `event_tool.get_current_customer` (lazy, у функції)

| Поле | Значення |
|------|----------|
| Хто імпортує | `routes/order_chat.py`, рядок 85 |
| Що імпортується | `get_current_customer(token, db) -> dict` |
| Навіщо | Ідентифікація клієнта кабінету: декод JWT + вибірка з `event_customers` |
| Спосіб розриву | Перенести в `services/customer_identity.py`. `event_tool.get_current_customer` стає обгорткою над сервісом (його власні endpoints не змінюються), `order_chat.py` імпортує сервіс |
| Незмінне | Статуси й тексти: `401 "Invalid token"`, `401 "Customer not found"`; набір полів повернутого dict |
| Ризик | Низький |

### #4 `tasks.py:246,375` -> `team_chat` (lazy, у хендлерах)

| Поле | Значення |
|------|----------|
| Хто імпортує | `routes/tasks.py`, рядок 246 і рядок 375 |
| Що імпортується | `notify_task_in_chat(...)`, `notify_task_status_change(...)` |
| Навіщо | Створити повідомлення в каналі «Загальний» при створенні задачі та додати відповідь у тред при зміні статусу |
| Спосіб розриву | Перенести обидві функції в `services/chat_notifications.py`. `team_chat.py` реекспортує їх, `tasks.py` імпортує сервіс |
| Додатково | Обидві функції вже мають early-return, коли каналу немає (`if not general: return None`). Зберігаємо цю семантику: за відсутнього CRM нотифікація тихо пропускається, створення задачі не падає |
| Ризик | Низький |

### #5 `document_pdf.py:22` -> `document_render` (top-level)

| Поле | Значення |
|------|----------|
| Хто імпортує | `routes/document_pdf.py`, рядок 22 (module-level) |
| Що імпортується | `build_document_context`, `jinja_env`, `DOCUMENT_TEMPLATES`, `get_watermark_text` |
| Навіщо | Генерація PDF повторно використовує той самий Jinja-рендер, реєстр шаблонів і логіку водяного знака, що й HTML-рендер |
| Спосіб розриву | Перенести чотири символи в шар `services/doc_engine/` (у ньому вже є `render.py`, `registry.py`, `data_builders.py` — спершу перевірити, що там, щоб не дублювати). `document_render.py` реекспортує, `document_pdf.py` імпортує із сервісу |
| Ризик | Середній: `jinja_env` — модульний singleton із `FileSystemLoader`. Шлях до каталогу шаблонів має залишитися той самий, інакше зламається рендер. Перевіряти окремо |

---

## 2. Пункт B із завдання — фактична розбіжність

Завдання формулює B як «`documents` не повинен напряму імпортувати finance route/functions»
і вимагає прибрати ризик `ImportError` під час запуску Documents.

**Фактично Python-імпорту `documents -> finance` не існує.** Скан усіх імпортів
`routes/documents.py` не дав жодного `from routes.finance import` чи `import finance`.
Отже:

* `ImportError` при Finance=OFF **неможливий** — його не було й раніше;
* «5 cross-route imports» — це саме #1–#5 вище, finance до них не входить.

Реальна залежність Documents на Finance — **на рівні даних**, не коду.
`routes/documents.py` читає фінансові таблиці напряму:

| Рядок | Таблиця |
|-------|---------|
| 2529 | `fin_payments` |
| 2571 | `fin_deposit_holds` |
| 2597 | `fin_deposit_events` |
| 2627 | `fin_payments` (late fees, `status='pending'`) |

Це один блок розрахунку (settlement) в межах одного endpoint.

**Пропозиція (потребує підтвердження, бо виходить за межі «розриву імпортів»):**
винести ці 4 запити в `services/finance_facade.py` як одну операцію
`get_order_settlement_financials(db, order_id)`; Documents залежить від контракту
сервісу, а не від фінансового роуту. Додати перевірку доступності:
якщо `fin_*` недоступні — сервіс повертає визначену структуру
«financials unavailable» замість винятку, і endpoint віддає graceful-відповідь.
Бізнес-логіка **переноситься**, не дублюється.

Якщо ви вважаєте, що це варто зробити окремим завданням — пункти #1–#5
виконуються незалежно й повністю закривають «route -> route».

---

## 3. Порядок виконання

1. `core/security.py`: додати `TokenError` + `decode_jwt_token`.
2. Створити `services/chat_service.py`, `services/customer_identity.py`, `services/chat_notifications.py`.
3. Прочитати наявний `services/doc_engine/` і винести рендер-символи без дублювання.
4. Перевести 5 споживачів на сервісний шар; у старих модулях залишити реекспорт.
5. Старий код не видаляти, поки нова реалізація не перевірена.

## 4. Перевірки (обов'язкові до commit)

* [ ] `py_compile` усіх змінених файлів
* [ ] імпорт **усіх** 70 route-модулів (виявити помилки на етапі імпорту)
* [ ] route inventory: `582` endpoints до і після
* [ ] `tests/test_security_config.py` — 19/19
* [ ] окремий тест `order_chat_ws` (декод токена + WS auth)
* [ ] окремий тест Documents без доступного Finance
* [ ] повторний скан: 0 `route -> route` imports
* [ ] JWT-формат не змінено (той самий секрет, HS256, ті самі claims)

## 5. Обмеження

Не змінюються: API contracts, URL/HTTP-методи, JWT-формат, схема БД,
бізнес-логіка, наявна реєстрація роутів. Module Manager до `server.py` НЕ підключається.