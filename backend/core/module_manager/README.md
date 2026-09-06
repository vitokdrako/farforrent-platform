# Module Manager

Plugin-архітектура для Rental OS. Реалізує Завдання №2.

## Обмеження, яких дотримано

| Обмеження | Як виконано |
|-----------|-------------|
| Не переносити існуючі routes | Жоден файл у `routes/` не переміщений і не змінений. Манифести лише **посилаються** на них рядком (`"routes.finance"`) |
| Не змінювати API | `canonical_route_order()` відтворює ті самі роутери з тими самими префіксами. Перевірено: 73 роутери, без дублікатів, `/api`-префікси збігаються з `server.py` |
| Не змінювати database schema | Стан модулів зберігається у JSON-файлі поза БД. Жодного DDL, жодної нової таблиці |

`server.py` **не змінений** — менеджер additive і поки не підключений. Це навмисно: спершу треба розірвати прямі cross-route імпорти (див. `audit/ARCHITECTURAL_MAP.md` §6.1).

## Структура

```
core/module_manager/
├── manifest.py    ModuleManifest, RouteDescriptor — декларативний опис
├── registry.py    ModuleRegistry — зберігання + топологічне сортування
├── state.py       ModuleState — atomic JSON persistence
├── manager.py     ModuleManager — register / enable / disable / status
├── manifests.py   манифести 12 фактичних модулів
└── cli.py         `rentalos modules`
```

## Публічний контракт

```python
from core.module_manager import get_module_manager

manager = get_module_manager()

manager.register_module(manifest)          # register
manager.enable_module("finance")           # enable
manager.disable_module("analytics")        # disable
manager.module_status("finance")           # expose module status
manager.status()                           # стан усієї системи
```

### register

```python
manager.register_module(manifest, replace=False)
manager.register_all(manifests)   # + валідація графа залежностей
```

Кидає `DuplicateModule`, якщо ім'я зайняте; `DependencyError` — якщо залежність невідома або є цикл.

### enable

```python
manager.enable_module("analytics")                        # авто-вмикання залежностей
manager.enable_module("analytics", with_dependencies=False)  # DependencyError, якщо їх немає
```

Ідемпотентно: повторний виклик повертає `changed: False`.

### disable

```python
manager.disable_module("analytics")                # DependencyError, якщо є залежні
manager.disable_module("finance", cascade=True)    # вимкне documents і portal
manager.disable_module("core")                     # ModuleDisabledError — CORE захищений
```

### status

```python
manager.module_status("finance")   # детально по модулю
manager.status()                   # усі модулі + load_order + permissions + warnings
manager.active_permissions()       # permissions ЛИШЕ увімкнених модулів
manager.enabled_modules()          # порядок завантаження (залежності першими)
manager.integrity_warnings()       # конфлікти з фактичним кодом
```

## Реальне вимикання, а не приховування меню

Вимкнений модуль:

- **routes немає** — `load_enabled_modules()` імпортує роутери lazy через `importlib`, тому модуль не імпортується взагалі;
- **permissions немає** — `active_permissions()` збирає їх лише з увімкнених модулів;
- **API endpoints немає** — `include_router` для них не викликається.

Перевірено: після `disable_module("finance", cascade=True)` активних permissions стало 54 замість 78, і жодного `finance.*` не залишилось.

## CLI

```bash
python -m core.module_manager.cli list
python -m core.module_manager.cli status finance
python -m core.module_manager.cli enable finance
python -m core.module_manager.cli disable analytics
python -m core.module_manager.cli disable crm --cascade
python -m core.module_manager.cli permissions
python -m core.module_manager.cli order
python -m core.module_manager.cli set core inventory rental
```

Будь-яка команда приймає `--json`.

## Стан

Шлях: `MODULE_STATE_PATH`, за замовчуванням `backend/module_state.json`.

```json
{
  "version": 1,
  "updated_at": "2026-09-04T00:00:00+00:00",
  "enabled": ["core", "inventory", "rental"],
  "history": [{"at": "...", "action": "enable", "module": "finance"}]
}
```

Запис атомарний (`tempfile` + `os.replace`). CORE відновлюється автоматично, якщо його прибрали з файлу вручну. Незареєстровані імена у файлі ігноруються з попередженням.

**Файл стану не треба комітити** — це runtime-стан інсталяції, як `.env`.

## Модулі (за фактичним кодом)

| Модуль | requires | default | Роутери |
|--------|----------|---------|---------|
| `core` | — | ON (незмінно) | 12 |
| `inventory` | core | ON | 13 |
| `rental` | core, inventory | ON | 11 |
| `warehouse` | core, inventory, rental | ON | 7 |
| `finance` | core, rental | ON | 5 |
| `crm` | core | ON | 5 |
| `documents` | core, rental, crm, **finance** | ON | 11 |
| `tasks` | core | OFF | 1 |
| `calendar` | core, rental | ON | 1 |
| `analytics` | core, rental, inventory, finance | OFF | 3 |
| `portal` | core, inventory, rental, crm, documents | ON | 2 |
| `integrations_opencart` | core, inventory | OFF | 2 |

Разом 73 роутери = 74 виклики `include_router` у `server.py` мінус зламаний `test_orders`.

**Навмисно не включений** (мертвий код за аудитом): `routes/test_orders.py` — імпортує відсутній `test_database`, але зареєстрований у `server.py`, тому файл збережений, щоб не змінювати кількість endpoints.

`routes/callbell_webhooks.py` видалений під час dead code cleanup: роутер ніколи не реєструвався у `server.py`, тому endpoints `/api/webhooks/*` у застосунку не існувало.

## Відомі конфлікти з фактичним кодом

Менеджер не приховує проблеми, а звітує про них через `integrity_warnings()`.

**`crm` має прямий import з `portal`** — `routes/order_chat.py` і `routes/order_chat_ws.py` імпортують `routes.event_tool`. Тому `disable_module("portal")` при увімкненому `crm` дасть попередження: у рантаймі імпорт зламається. Це поле `hard_imports` у манифесті.

**`documents` requires `finance`** — не за бажанням, а тому що `documents.py` читає `fin_payments` і `fin_deposit_holds` напряму. Доки це не розірвано через Finance-API, «Finance = OFF, Documents = ON» технічно неможливий.

**`calendar` і `analytics`** читають таблиці Warehouse/Finance/Tasks напряму — при їх вимиканні частина даних просто зникне з відповіді, без помилки.

## Наступні крок

Щоб `server.py` перейшов на менеджер, потрібно спершу:

1. розірвати 5 cross-route імпортів (§6.1 аудиту);
2. додати permission-middleware, який читає `active_permissions()`;
3. замінити 74 безумовних `include_router` на `get_module_manager().load_enabled_modules(app)`.

Крок 3 змінить `server.py`, тому виходить за межі Завдання №2 і не виконаний.