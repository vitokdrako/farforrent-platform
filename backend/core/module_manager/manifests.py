"""Манифести модулів Rental OS.

Склад модулів і графи залежностей узяті з фактичного коду
(audit/ARCHITECTURAL_MAP.md), а не з бажаної архітектури.

Префікси роутерів відтворюють `server.py` байт-в-байт:
    * `event_tool.router`         -> prefix="/api"
    * `order_chat.client_router`  -> prefix="/api"
    * `order_chat.admin_router`   -> prefix="/api"
    * `order_chat_ws.router`      -> prefix="/api"
Решта роутерів мають власний prefix і реєструються без аргументу.

НЕ включений у жоден модуль (мертвий код за аудитом):
    * `routes/test_orders.py` — імпортує відсутній модуль `test_database`.
      Роутер при цьому зареєстрований у `server.py`, тому сам файл
      збережений: видалення змінило б кількість endpoints і API-контракт.

`routes/callbell_webhooks.py` видалений під час dead code cleanup —
його роутер ніколи не реєструвався у `server.py`, отже endpoints
`/api/webhooks/*` у застосунку не існувало.
"""
from typing import List

from .manifest import ModuleManifest, RouteDescriptor as R

# ----------------------------------------------------------------------
# CORE — існує завжди, вимкнути неможливо
# ----------------------------------------------------------------------
CORE = ModuleManifest(
    name="core",
    version="1.0.0",
    title="Core",
    description=(
        "Авторизація, користувачі, файли, налаштування, юр.особи, "
        "audit log, notifications, availability engine."
    ),
    core=True,
    default_enabled=True,
    routes=(
        R("routes.auth"),
        R("routes.users"),
        R("routes.admin"),
        R("routes.cabinet"),
        R("routes.settings"),
        R("routes.company_profiles"),
        R("routes.user_tracking"),
        R("routes.uploads"),
        R("routes.image_proxy"),
        R("routes.photos"),
        R("routes.email"),
        R("routes.migrations"),
    ),
    permissions=(
        "core.view",
        "core.users.view",
        "core.users.create",
        "core.users.edit",
        "core.users.delete",
        "core.roles.manage",
        "core.settings.view",
        "core.settings.edit",
        "core.company.manage",
        "core.files.upload",
        "core.files.delete",
        "core.audit.view",
        "core.modules.manage",
    ),
    tables=(
        "users",
        "oc_user",
        "system_settings",
        "company_profiles",
        "audit_records",
        "order_notes",
        "order_item_packing",
    ),
    notes=(
        "routes/migrations.py виконує DDL через HTTP — захистити перед production.",
        "JWT_SECRET_KEY має небезпечний default у 5 файлах — звести в один модуль.",
        "routes/email.py викликає відсутній services.doc_engine.generator.",
    ),
)

# ----------------------------------------------------------------------
# 01 — Inventory
# ----------------------------------------------------------------------
INVENTORY = ModuleManifest(
    name="inventory",
    version="1.0.0",
    title="Inventory",
    description="Товари, категорії, родини, набори, фото, штрих-коди, інвентаризація.",
    requires=("core",),
    default_enabled=True,
    routes=(
        R("routes.products"),
        R("routes.catalog"),
        R("routes.extended_catalog"),
        R("routes.bulk_products"),
        R("routes.inventory"),
        R("routes.inventory_adjustments"),
        R("routes.product_sets"),
        R("routes.product_images"),
        R("routes.product_images_multi"),
        R("routes.product_images_multi", attr="delete_router"),
        R("routes.product_reservations"),
        R("routes.qr_codes"),
        R("routes.audit"),
    ),
    permissions=(
        "inventory.view",
        "inventory.create",
        "inventory.edit",
        "inventory.delete",
        "inventory.bulk_edit",
        "inventory.images.manage",
        "inventory.sets.manage",
        "inventory.audit.perform",
        "inventory.adjustments.create",
        "inventory.export",
        "inventory.import",
    ),
    tables=(
        "products",
        "categories",
        "product_images",
        "product_families",
        "product_family_items",
        "product_history",
        "product_sets",
        "product_set_items",
        "product_hashtags_dict",
        "product_reservations",
        "inventory_recounts",
        "processing_queue",
    ),
    notes=(
        "catalog.py має власну реалізацію availability — уніфікувати з core.",
        "routes/audit.py читає обидві БД (RentalHub + OpenCart).",
        "inventory_recount vs inventory_recounts — перевірити на живій БД.",
    ),
)

# ----------------------------------------------------------------------
# 02 — Rental / Orders
# ----------------------------------------------------------------------
RENTAL = ModuleManifest(
    name="rental",
    version="1.0.0",
    title="Rental / Orders",
    description=(
        "Життєвий цикл замовлення: quote -> reservation -> issue -> "
        "rental -> return -> settlement. Часткові повернення, архів."
    ),
    requires=("core", "inventory"),
    default_enabled=True,
    routes=(
        R("routes.orders"),
        R("routes.orders", attr="decor_router"),
        R("routes.order_modifications"),
        R("routes.order_internal_notes"),
        R("routes.order_sync"),
        R("routes.issue_cards"),
        R("routes.return_cards"),
        R("routes.return_versions"),
        R("routes.partial_returns"),
        R("routes.archive"),
        R("routes.admin_orders"),
    ),
    permissions=(
        "rental.view",
        "rental.create",
        "rental.edit",
        "rental.delete",
        "rental.confirm",
        "rental.issue",
        "rental.return",
        "rental.partial_return",
        "rental.cancel",
        "rental.archive.view",
        "rental.notes.write",
        "rental.items.modify",
    ),
    tables=(
        "orders",
        "order_items",
        "order_lifecycle",
        "order_internal_notes",
        "order_modifications",
        "order_additional_services",
        "order_packaging",
        "order_extensions",
        "order_section_versions",
        "issue_cards",
        "return_cards",
        "partial_return_versions",
        "partial_return_version_items",
        "partial_return_log",
    ),
    notes=(
        "Три паралельні системи повернень: return_cards, decor_return_cards, "
        "partial_return_versions.",
        "12 routes роблять SHOW COLUMNS FROM orders — схема нестабільна.",
        "routes/test_orders.py навмисно не включений: імпортує відсутній test_database.",
    ),
)

# ----------------------------------------------------------------------
# 03 — Warehouse
# ----------------------------------------------------------------------
WAREHOUSE = ModuleManifest(
    name="warehouse",
    version="1.0.0",
    title="Warehouse",
    description="Damage cases, мийка, прання, реставрація, laundry-батчі, picking.",
    requires=("core", "inventory", "rental"),
    default_enabled=True,
    routes=(
        R("routes.warehouse"),
        R("routes.picking_list"),
        R("routes.product_damage_history"),
        R("routes.damage_cases"),
        R("routes.damages"),
        R("routes.product_cleaning"),
        R("routes.laundry"),
    ),
    permissions=(
        "warehouse.view",
        "warehouse.picking",
        "warehouse.issue",
        "warehouse.return",
        "warehouse.damage.create",
        "warehouse.damage.edit",
        "warehouse.damage.approve",
        "warehouse.cleaning.manage",
        "warehouse.laundry.manage",
    ),
    tables=(
        "product_damage_history",
        "laundry_batches",
        "laundry_items",
        "damage_case_archive",
    ),
    notes=(
        "product_damage_history перевантажена: damage + wash + laundry + "
        "restoration + черга обробки.",
        "routes/damages.py — legacy, дублює product_damage_history.",
    ),
)

# ----------------------------------------------------------------------
# 04 — Finance
# ----------------------------------------------------------------------
FINANCE = ModuleManifest(
    name="finance",
    version="1.0.0",
    title="Finance",
    description=(
        "Double-entry ledger, платежі, витрати, депозити (DEP_LIAB), "
        "закриття місяця, HR/payroll."
    ),
    requires=("core", "rental"),
    default_enabled=True,
    routes=(
        R("routes.finance"),
        R("routes.finance", attr="manager_router"),
        R("routes.admin_finance"),
        R("routes.expense_management"),
        R("routes.payer_profiles"),
    ),
    permissions=(
        "finance.view",
        "finance.create",
        "finance.edit",
        "finance.delete",
        "finance.payments",
        "finance.expenses",
        "finance.deposits",
        "finance.encashment",
        "finance.payroll",
        "finance.close_month",
        "finance.reports",
    ),
    tables=(
        "fin_accounts",
        "fin_transactions",
        "fin_ledger_entries",
        "fin_categories",
        "fin_payments",
        "fin_expenses",
        "fin_deposit_holds",
        "fin_deposit_events",
        "fin_vendors",
        "fin_encashments",
        "monthly_reports",
        "cash_summaries",
        "expense_templates",
        "expense_due_items",
        "rh_employees",
        "hr_payroll",
        "v_order_finance",
    ),
    notes=(
        "v_order_finance — VIEW без DDL у репозиторії: блокер чистої установки.",
        "6 місць пишуть у fin_payments напряму, обходячи ledger.",
        "finance.py частково використовує raw DB-API cursor (%s).",
        "Дублікати HR: rh_employees/hr_payroll vs fin_employees/fin_payroll.",
        "Тригери на fin_payments (міграції 005/006) — логіка невидима з коду.",
    ),
)

# ----------------------------------------------------------------------
# 05 — CRM
# ----------------------------------------------------------------------
CRM = ModuleManifest(
    name="crm",
    version="1.0.0",
    title="CRM",
    description="Клієнти, payer-профілі, командний чат, чат замовлень.",
    requires=("core",),
    default_enabled=True,
    routes=(
        R("routes.clients"),
        R("routes.team_chat"),
        R("routes.order_chat", attr="client_router", prefix="/api"),
        R("routes.order_chat", attr="admin_router", prefix="/api"),
        R("routes.order_chat_ws", prefix="/api"),
    ),
    permissions=(
        "crm.view",
        "crm.clients.create",
        "crm.clients.edit",
        "crm.clients.delete",
        "crm.chat.read",
        "crm.chat.write",
        "crm.chat.moderate",
    ),
    tables=(
        "client_users",
        "client_payer_links",
        "payer_profiles",
        "chat_channels",
        "chat_channel_members",
        "chat_messages",
        "chat_read_status",
        "order_chat_messages",
    ),
    hard_imports=("portal",),
    notes=(
        "order_chat.py та order_chat_ws.py імпортують routes.event_tool "
        "(Portal) — вимикання Portal зламає чат у рантаймі.",
        "routes/callbell_webhooks.py видалений (dead code cleanup): "
        "його роутер не був зареєстрований у server.py.",
    ),
)

# ----------------------------------------------------------------------
# 06 — Documents
# ----------------------------------------------------------------------
DOCUMENTS = ModuleManifest(
    name="documents",
    version="1.0.0",
    title="Documents",
    description=(
        "Doc engine, рендер шаблонів, PDF, підписи, email-розсилка, "
        "рамкові договори та додатки."
    ),
    # Finance більше НЕ в requires: після введення FinanceService (Завдання №6)
    # Documents не звертається до fin_* напряму і при Finance = OFF
    # деградує контрольовано (нулі + status="disabled"), а не падає з 500.
    requires=("core", "rental", "crm"),
    default_enabled=True,
    routes=(
        R("routes.documents"),
        R("routes.document_render"),
        R("routes.document_pdf"),
        R("routes.document_signatures"),
        R("routes.document_manual_fields"),
        R("routes.document_email"),
        R("routes.document_policy"),
        R("routes.master_agreements"),
        R("routes.order_annexes"),
        R("routes.template_admin"),
        R("routes.pdf"),
    ),
    permissions=(
        "documents.view",
        "documents.generate",
        "documents.edit",
        "documents.delete",
        "documents.sign",
        "documents.send_email",
        "documents.templates.manage",
        "documents.agreements.manage",
        "documents.annexes.manage",
    ),
    tables=(
        "documents",
        "document_signatures",
        "document_emails",
        "document_email_log",
        "document_templates",
        "master_agreements",
        "order_annexes",
    ),
    notes=(
        "Finance-дані читаються ТІЛЬКИ через services.finance.FinanceService "
        "(read-only фасад). Прямих SQL до fin_payments / fin_deposit_holds / "
        "fin_deposit_events у модулі немає — 'Finance = OFF' тепер допустимий.",
        "При Finance = OFF документи генеруються з нульовими фінансовими "
        "блоками і status='disabled'; це очікувана деградація, не помилка.",
        "Нові Finance-поля в документах додавати лише через FinanceService, "
        "не новим raw SQL — інакше boundary знову зламається.",
        "routes/pdf.py — legacy reportlab проти OpenCart.",
    ),
)

# ----------------------------------------------------------------------
# 07 — Tasks
# ----------------------------------------------------------------------
TASKS = ModuleManifest(
    name="tasks",
    version="1.0.0",
    title="Tasks",
    description="Задачі та kanban для команди.",
    requires=("core",),
    default_enabled=False,
    routes=(R("routes.tasks"),),
    permissions=(
        "tasks.view",
        "tasks.create",
        "tasks.edit",
        "tasks.delete",
        "tasks.assign",
        "tasks.complete",
    ),
    tables=("tasks",),
    hard_imports=("crm",),
    notes=(
        "tasks.py імпортує routes.team_chat (CRM) для нотифікацій — "
        "вимикання CRM зламає створення задач.",
    ),
)

# ----------------------------------------------------------------------
# 08 — Calendar
# ----------------------------------------------------------------------
CALENDAR = ModuleManifest(
    name="calendar",
    version="1.0.0",
    title="Calendar",
    description="Уніфікований календар: видачі, повернення, платежі, задачі.",
    requires=("core", "rental"),
    default_enabled=True,
    routes=(R("routes.calendar_events"),),
    permissions=("calendar.view", "calendar.edit"),
    tables=("orders", "product_damage_history", "fin_payments", "tasks"),
    notes=(
        "Фактично читає таблиці Warehouse, Finance і Tasks напряму — "
        "при їх вимиканні частина подій просто зникне з календаря.",
    ),
)

# ----------------------------------------------------------------------
# 09 — Analytics
# ----------------------------------------------------------------------
ANALYTICS = ModuleManifest(
    name="analytics",
    version="1.0.0",
    title="Analytics",
    description="Звіти, dashboard менеджера, експорт CSV/Excel.",
    requires=("core", "rental", "inventory", "finance"),
    default_enabled=False,
    routes=(
        R("routes.analytics"),
        R("routes.dashboard_overview"),
        R("routes.export"),
    ),
    permissions=(
        "analytics.view",
        "analytics.reports",
        "analytics.export",
        "analytics.dashboard",
    ),
    tables=(
        "orders",
        "order_items",
        "products",
        "product_damage_history",
        "fin_payments",
        "fin_expenses",
        "tasks",
    ),
    notes=(
        "analytics.py джойнить таблицю 'clients', тоді як актуальна — "
        "'client_users'. Перевірити на живій БД.",
    ),
)

# ----------------------------------------------------------------------
# 10 — Portal (Event Tool) — client-facing
# ----------------------------------------------------------------------
PORTAL = ModuleManifest(
    name="portal",
    version="1.0.0",
    title="Portal (Event Tool)",
    description=(
        "Клієнтський портал: каталог, дошки події, soft reservations, "
        "обране, push-нотифікації, конвертація дошки в замовлення."
    ),
    requires=("core", "inventory", "rental", "crm", "documents"),
    default_enabled=True,
    routes=(
        R("routes.event_tool", prefix="/api"),
        R("routes.event_tool_integration"),
    ),
    permissions=(
        "portal.view",
        "portal.boards.manage",
        "portal.reservations.manage",
        "portal.convert_to_order",
    ),
    tables=(
        "event_customers",
        "event_boards",
        "event_board_items",
        "event_soft_reservations",
        "event_favorites",
        "event_managers",
        "push_subscriptions",
    ),
    notes=(
        "Від Portal напряму залежать CRM-чати (order_chat, order_chat_ws).",
        "Має власну реалізацію availability — уніфікувати з core.",
    ),
)

# ----------------------------------------------------------------------
# 11 — Integrations / OpenCart
# ----------------------------------------------------------------------
INTEGRATIONS_OPENCART = ModuleManifest(
    name="integrations_opencart",
    version="1.0.0",
    title="Integrations: OpenCart",
    description="Синхронізація товарів, цін і замовлень із legacy OpenCart MySQL.",
    requires=("core", "inventory"),
    default_enabled=False,
    routes=(
        R("routes.price_sync"),
        R("routes.sync"),
    ),
    permissions=(
        "integrations.opencart.view",
        "integrations.opencart.sync",
        "integrations.opencart.price_sync",
    ),
    tables=("oc_product", "oc_order", "oc_order_product", "oc_category", "products"),
    notes=(
        "routes/sync.py виконує subprocess через HTTP — RCE-поверхня.",
        "Єдиний модуль, що легітимно потребує другої БД (database.py).",
    ),
)


def default_manifests() -> List[ModuleManifest]:
    """Усі манифести у canonical-порядку реєстрації.

    Порядок реєстрації визначає порядок виводу у status(),
    а порядок завантаження роутерів обчислюється топологічно.
    """
    return [
        CORE,
        INVENTORY,
        RENTAL,
        WAREHOUSE,
        FINANCE,
        CRM,
        DOCUMENTS,
        TASKS,
        CALENDAR,
        ANALYTICS,
        PORTAL,
        INTEGRATIONS_OPENCART,
    ]


__all__ = [
    "CORE",
    "INVENTORY",
    "RENTAL",
    "WAREHOUSE",
    "FINANCE",
    "CRM",
    "DOCUMENTS",
    "TASKS",
    "CALENDAR",
    "ANALYTICS",
    "PORTAL",
    "INTEGRATIONS_OPENCART",
    "default_manifests",
]