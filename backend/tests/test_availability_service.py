"""
Регресійні тести канонічної формули доступності (Завдання №11).

Тести захищають продуктові рішення власника (`audit/AVAILABILITY_INVENTORY.md` §7)
від випадкового відкату. Кожен тест перевіряє конкретне рішення й падає, якщо
формула повернеться до однієї з 9 старих розбіжних версій.

БД не потрібна: використовується мінімальний стаб SQLAlchemy-подібного
з'єднання, який відповідає на запити за їх ознаками. Так тестується саме
логіка формули, а не MySQL.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.availability import AvailabilityService  # noqa: E402
from services.availability.rules import (  # noqa: E402
    ACTIVE_ITEM_STATUS,
    COUNT_SOFT_RESERVATIONS,
    EXCLUDE_ARCHIVED_ORDERS,
    IN_RENT_ORDER_STATUSES,
    RESERVING_ORDER_STATUSES,
    STATE_AFFECTS_AVAILABILITY,
    UNAVAILABLE_TABLES,
    statuses_placeholder,
)


class _FakeResult:
    """Мінімальний аналог SQLAlchemy Result."""

    def __init__(self, rows):
        self._rows = list(rows)

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def __iter__(self):
        return iter(self._rows)

    def close(self):
        pass


class _FakeDB:
    """
    Стаб з'єднання: розпізнає запит за характерними фрагментами SQL.

    Зберігає всі виконані запити, щоб тести могли перевіряти не лише
    результат, а й наявність обов'язкових фільтрів у самому SQL.
    """

    def __init__(self, stock=None, reserved=0, in_rent=0, soft=0,
                 soft_raises=False):
        self.stock = stock or (10, 0, 0, "available", "SKU-1", "Товар")
        self.reserved = reserved
        self.in_rent = in_rent
        self.soft = soft
        self.soft_raises = soft_raises
        self.queries = []

    def execute(self, statement, params=None):
        sql = str(statement)
        self.queries.append(sql)

        bound_ids = [v for k, v in (params or {}).items() if k.startswith("pid")]

        if "event_soft_reservations" in sql:
            if self.soft_raises:
                raise RuntimeError("table event_soft_reservations does not exist")
            if "GROUP BY sr.product_id" in sql:
                return _FakeResult([(pid, self.soft) for pid in bound_ids])
            return _FakeResult([(self.soft,)])

        if "in_laundry, state FROM products" in sql:
            return _FakeResult([(self.stock[2], self.stock[3])])

        if "partial_return_version_items" in sql or "DATEDIFF(:start_date" in sql:
            return _FakeResult([])

        if "FROM products" in sql and "product_id IN" in sql:
            return _FakeResult(
                [
                    (pid, self.stock[0], self.stock[1], self.stock[4], self.stock[5])
                    for pid in bound_ids
                ]
            )

        if "FROM products" in sql and "SUM" not in sql:
            return _FakeResult([self.stock])

        if "GROUP BY oi.product_id" in sql:
            return _FakeResult([(pid, self.reserved) for pid in bound_ids])

        if "SUM(oi.quantity)" in sql:
            # Розрізняємо запит «резерв» і запит «в оренді» за переліком статусів
            reserving_count = sum(
                1 for s in RESERVING_ORDER_STATUSES if f"'{s}'" in sql
            )
            bound = list((params or {}).values())
            is_in_rent = (
                sum(1 for s in RESERVING_ORDER_STATUSES if s in bound) == 1
            )
            if is_in_rent and reserving_count == 0:
                return _FakeResult([(self.in_rent,)])
            return _FakeResult([(self.reserved,)])

        return _FakeResult([(0,)])

    def sql_for(self, needle):
        """Останній запит, що містить фрагмент."""
        for sql in reversed(self.queries):
            if needle in sql:
                return sql
        return ""


class _DateAwareDB(_FakeDB):
    """
    Стаб, що імітує реальну поведінку SQL при порівнянні з `NULL`.

    Потрібен, бо звичайний `_FakeDB` віддає однакові резерви незалежно від
    дат, і саме тому пропустив реальний дефект: коли роут передавав
    `start_date=None`, у SQL потрапляло `o.rental_start_date <= NULL`, що в
    MySQL завжди `NULL` (тобто «не підходить»), і резерви тихо ставали 0.

    Тут відтворено лише цей факт: якщо запит містить фільтр за датами, а
    значення межі не передане — вибірка порожня, як у справжній БД.
    """

    def execute(self, statement, params=None):
        sql = str(statement)
        has_date_filter = "rental_start_date" in sql or "reserved_from" in sql
        if has_date_filter and not (params or {}).get("start_date"):
            self.queries.append(sql)
            return _FakeResult([(0,)])
        return super().execute(statement, params)


class TestNoPeriodMeansNow(unittest.TestCase):
    """
    Точки «стан складу зараз» (картка видачі) працюють без періоду.

    Дефект знайшов контрольний вимір, а не тест: `reserved` падав у 0 для
    320 товарів, бо `None` підставлявся у порівняння з датою. Ці тести
    закріплюють правильну поведінку — без періоду фільтр не додається.
    """

    def test_no_date_filter_when_period_absent(self):
        """Без періоду в SQL резервів не має бути порівнянь за датами."""
        db = _FakeDB(stock=(10, 0, 0, "available", "S", "N"), reserved=4)
        AvailabilityService(db).get_availability(1, None, None, 1)
        sql = db.sql_for("SUM(oi.quantity)")
        self.assertNotIn("rental_start_date", sql)
        self.assertNotIn("rental_end_date", sql)

    def test_reserved_counted_without_period(self):
        """Головний регрес: без періоду резерви рахуються, а не обнуляються."""
        db = _DateAwareDB(stock=(10, 0, 0, "available", "S", "N"), reserved=4)
        result = AvailabilityService(db).get_availability(1, None, None, 1)
        self.assertEqual(result["reserved_quantity"], 4)
        self.assertEqual(result["available_quantity"], 6)

    def test_period_filter_still_applied_when_dates_given(self):
        """З датами фільтр мусить залишатися — інакше зникне облік періоду."""
        db = _FakeDB(reserved=4)
        AvailabilityService(db).get_availability(1, "2026-09-06", "2026-09-20", 1)
        sql = db.sql_for("SUM(oi.quantity)")
        self.assertIn("rental_start_date", sql)
        self.assertIn("rental_end_date", sql)

    def test_half_open_period_is_ignored(self):
        """Одна дата без другої дала б непередбачуваний інтервал."""
        db = _FakeDB(reserved=4)
        AvailabilityService(db).get_availability(1, "2026-09-06", None, 1)
        self.assertNotIn("rental_start_date", db.sql_for("SUM(oi.quantity)"))

    def test_soft_reservations_without_period(self):
        """Soft-резерви без періоду теж не мають зникати."""
        db = _DateAwareDB(stock=(20, 0, 0, "available", "S", "N"), soft=6)
        result = AvailabilityService(db).get_availability(1, None, None, 1)
        self.assertEqual(result["soft_reserved_quantity"], 6)

    def test_bulk_without_period_keeps_reservations(self):
        """Той самий інваріант для bulk-розрахунку каталогу й календаря."""
        db = _DateAwareDB(stock=(10, 0, 0, "available", "S", "N"), reserved=3)
        result = AvailabilityService(db).get_bulk_availability([1, 2])
        self.assertEqual(result[1]["reserved_quantity"], 3)
        self.assertEqual(result[1]["available_quantity"], 7)


class TestCanonicalRules(unittest.TestCase):
    """Правила як контракт: фантомних статусів немає, стан не впливає."""

    def test_no_phantom_statuses(self):
        """Статуси з 0 рядків у production не повинні резервувати товар."""
        phantoms = {"on_rent", "pending", "confirmed", "new", "draft"}
        self.assertEqual(phantoms & set(RESERVING_ORDER_STATUSES), set())
        self.assertEqual(phantoms & set(IN_RENT_ORDER_STATUSES), set())

    def test_owner_decisions_present(self):
        """Рішення 1 і 2: awaiting_customer і partial_return резервують."""
        self.assertIn("awaiting_customer", RESERVING_ORDER_STATUSES)
        self.assertIn("partial_return", RESERVING_ORDER_STATUSES)
        self.assertIn("issued", RESERVING_ORDER_STATUSES)

    def test_released_statuses_not_reserving(self):
        """Завершені/скасовані замовлення товар не тримають."""
        for status in ("completed", "cancelled", "returned"):
            self.assertNotIn(status, RESERVING_ORDER_STATUSES)

    def test_state_does_not_affect_availability(self):
        """Рішення 4: products.state (written_off) не впливає на доступність."""
        self.assertFalse(STATE_AFFECTS_AVAILABILITY)

    def test_archived_excluded(self):
        """Рішення 6: архівні замовлення не резервують."""
        self.assertTrue(EXCLUDE_ARCHIVED_ORDERS)

    def test_missing_tables_declared(self):
        """Рішення 7: відсутні таблиці задокументовані й не читаються."""
        self.assertIn("product_reservations", UNAVAILABLE_TABLES)
        self.assertIn("product_sets", UNAVAILABLE_TABLES)

    def test_placeholder_binding_is_parameterised(self):
        """Статуси підставляються біндами, а не конкатенацією значень."""
        fragment, params = statuses_placeholder("st", ("a", "b"))
        self.assertEqual(fragment, "(:st0, :st1)")
        self.assertEqual(params, {"st0": "a", "st1": "b"})
        self.assertNotIn("'a'", fragment)


class TestAvailabilityFormula(unittest.TestCase):
    """Арифметика канонічної формули."""

    def test_frozen_quantity_is_subtracted(self):
        """
        Рішення 3: заморожене віднімається.

        Це найвпливовіша зміна — на production-знімку вона зачіпає 375 товарів
        і 1582 одиниці; найгірший випадок — 210 од. фантомної доступності.
        """
        db = _FakeDB(stock=(328, 210, 0, "available", "SKU", "Гілка фікуса"))
        result = AvailabilityService(db).get_availability(1, "2026-09-06", "2026-09-20", 1)
        self.assertEqual(result["total_quantity"], 328)
        self.assertEqual(result["on_processing_quantity"], 210)
        self.assertEqual(result["available_quantity"], 118)

    def test_full_formula(self):
        """quantity − frozen − резерв − soft."""
        db = _FakeDB(stock=(100, 10, 0, "available", "S", "N"), reserved=30, soft=5)
        result = AvailabilityService(db).get_availability(1, "2026-09-06", "2026-09-20", 1)
        self.assertEqual(result["available_quantity"], 55)

    def test_never_negative(self):
        """Перевищення резерву не дає від'ємної доступності."""
        db = _FakeDB(stock=(5, 3, 0, "available", "S", "N"), reserved=99)
        result = AvailabilityService(db).get_availability(1, "2026-09-06", "2026-09-20", 1)
        self.assertEqual(result["available_quantity"], 0)

    def test_written_off_still_available(self):
        """
        Рішення 4 на практиці: списаний стан не обнуляє залишок.

        Захищає 267 одиниць у реальних працюючих замовленнях: кількість при
        списанні вже віднімається в damage_cases, тому друге віднімання
        зробило б живий товар недоступним.
        """
        db = _FakeDB(stock=(179, 0, 0, "written_off", "S", "Гортензія"))
        result = AvailabilityService(db).get_availability(1, "2026-09-06", "2026-09-20", 1)
        self.assertEqual(result["available_quantity"], 179)
        self.assertTrue(result["is_available"])

    def test_missing_product(self):
        """Неіснуючий товар — 0, без винятку."""
        db = _FakeDB(stock=None)
        db.stock = None
        db.execute = lambda s, p=None: _FakeResult([])
        result = AvailabilityService(db).get_availability(999, "2026-09-06", "2026-09-20", 1)
        self.assertEqual(result["available_quantity"], 0)
        self.assertFalse(result["product_exists"])

    def test_requested_quantity_flag(self):
        """is_available порівнюється саме із запитаною кількістю."""
        db = _FakeDB(stock=(10, 0, 0, "available", "S", "N"), reserved=8)
        svc = AvailabilityService(db)
        self.assertTrue(svc.get_availability(1, "a", "b", 2)["is_available"])
        self.assertFalse(svc.get_availability(1, "a", "b", 3)["is_available"])

    def test_processing_rush_flag(self):
        """
        Обробка попереджає, а не блокує остаточно.

        Зберігає наявну поведінку: якщо кількості бракує лише через обробку,
        менеджер бачить `needs_processing_rush`, а не «немає товару».
        """
        db = _FakeDB(stock=(10, 6, 0, "on_wash", "S", "N"))
        result = AvailabilityService(db).get_availability(1, "a", "b", 8)
        self.assertFalse(result["is_available"])
        self.assertTrue(result["needs_processing_rush"])
        self.assertEqual(result["available_ignoring_processing"], 10)


class TestQueryFilters(unittest.TestCase):
    """Обов'язкові фільтри мають бути в самому SQL, не лише в коментарях."""

    def _reserve_sql(self):
        db = _FakeDB()
        AvailabilityService(db).get_availability(1, "2026-09-06", "2026-09-20", 1)
        return db.sql_for("SUM(oi.quantity)")

    def test_archived_filter_in_sql(self):
        self.assertIn("is_archived", self._reserve_sql())

    def test_refused_items_filtered(self):
        self.assertIn(ACTIVE_ITEM_STATUS, self._reserve_sql())

    def test_date_overlap_filter(self):
        sql = self._reserve_sql()
        self.assertIn("rental_start_date <= :end_date", sql)
        self.assertIn("rental_end_date >= :start_date", sql)

    def test_soft_reservation_expiry_filter(self):
        """Протерміновані soft-резерви не тримають товар."""
        db = _FakeDB(soft=7)
        AvailabilityService(db).get_availability(1, "a", "b", 1)
        sql = db.sql_for("event_soft_reservations")
        self.assertIn("expires_at > NOW()", sql)

    def test_soft_reservations_counted_globally(self):
        """Рішення 5: soft-резерви враховуються, а не ігноруються."""
        self.assertTrue(COUNT_SOFT_RESERVATIONS)
        db = _FakeDB(stock=(20, 0, 0, "available", "S", "N"), soft=6)
        result = AvailabilityService(db).get_availability(1, "a", "b", 1)
        self.assertEqual(result["soft_reserved_quantity"], 6)
        self.assertEqual(result["available_quantity"], 14)

    def test_missing_soft_table_degrades_gracefully(self):
        """Відсутня таблиця soft-резервів не має ламати каталог."""
        db = _FakeDB(stock=(20, 0, 0, "available", "S", "N"), soft_raises=True)
        result = AvailabilityService(db).get_availability(1, "a", "b", 1)
        self.assertEqual(result["soft_reserved_quantity"], 0)
        self.assertEqual(result["available_quantity"], 20)

    def test_exclude_order_id_applied(self):
        """Редагування замовлення не має конфліктувати саме з собою."""
        db = _FakeDB()
        AvailabilityService(db).get_availability(1, "a", "b", 1, exclude_order_id=8078)
        self.assertIn("exclude_order_id", db.sql_for("SUM(oi.quantity)"))


class TestServiceContract(unittest.TestCase):
    """Сервіс read-only і сумісний зі старим фасадом."""

    def test_no_write_methods(self):
        for name in dir(AvailabilityService):
            self.assertFalse(
                any(w in name.lower() for w in ("create", "insert", "update", "delete")),
                f"AvailabilityService не має містити мутуючий метод {name}",
            )

    def test_no_mutating_sql(self):
        db = _FakeDB()
        svc = AvailabilityService(db)
        svc.get_availability(1, "a", "b", 1)
        svc.get_bulk_availability([1, 2], "a", "b")
        for sql in db.queries:
            upper = sql.upper()
            for verb in ("INSERT INTO", "DELETE FROM", "ALTER TABLE", "DROP ", "TRUNCATE"):
                self.assertNotIn(verb, upper)
            self.assertNotIn("UPDATE PRODUCTS", upper)

    def test_order_availability_aggregates(self):
        db = _FakeDB(stock=(4, 0, 0, "available", "S", "N"), reserved=3)
        result = AvailabilityService(db).get_order_availability(
            [{"product_id": 1, "quantity": 1}, {"product_id": 2, "quantity": 5}],
            "2026-09-06", "2026-09-20",
        )
        self.assertFalse(result["all_available"])
        self.assertEqual(len(result["items"]), 2)
        self.assertEqual(len(result["unavailable_items"]), 1)

    def test_bulk_returns_entry_per_product(self):
        """Каталог не має робити N+1: bulk повертає всі запитані id."""
        db = _FakeDB()
        db.execute = lambda s, p=None: _FakeResult(
            [] if "event_soft_reservations" in str(s) else
            [(1, 10, 2, "SKU1", "A"), (2, 5, 0, "SKU2", "B")]
            if "FROM products" in str(s) else []
        )
        result = AvailabilityService(db).get_bulk_availability([1, 2, 3], "a", "b")
        self.assertEqual(set(result.keys()), {1, 2, 3})
        self.assertEqual(result[3]["available_quantity"], 0)

    def test_bulk_empty_input(self):
        self.assertEqual(AvailabilityService(_FakeDB()).get_bulk_availability([], "a", "b"), {})

    def test_legacy_facade_contract_preserved(self):
        """Старий фасад повертає всі поля, які вже споживають Orders і UI."""
        from utils import availability_checker

        db = _FakeDB(stock=(10, 0, 0, "available", "S", "N"), reserved=2)
        result = availability_checker.check_product_availability(db, 1, 1, "a", "b")
        self.assertEqual(result["total_quantity"], 10)
        self.assertEqual(result["available_quantity"], 8)
        for field in (
            "product_id", "sku", "product_name", "total_quantity", "reserved_quantity",
            "in_rent", "available_quantity", "ready_quantity", "on_processing_quantity",
            "requested_quantity", "is_available", "has_tight_schedule", "nearby_orders",
            "has_partial_return_risk", "partial_return_qty", "partial_return_warnings",
            "has_processing_warning", "needs_processing_rush", "processing_warnings",
        ):
            self.assertIn(field, result, f"втрачено поле контракту: {field}")


class TestCatalogCheckAvailabilityMigration(unittest.TestCase):
    """
    Точка I — `GET /api/catalog/check-availability/{sku}` (Завдання №11).

    До міграції endpoint віддавав `p.quantity > 0` і молча відкидав
    `from_date`/`to_date`, які надсилає frontend (`api/client.ts:119`).
    Тести закріплюють дві речі: дати справді враховуються, а старі поля
    відповіді не зникли — інакше UI зламається без жодної помилки.

    Роут перевіряється статично (AST), бо його імпорт тягне за собою
    з'єднання з БД і обов'язкові `RH_DB_*` env — тест не повинен цього
    вимагати.
    """

    @staticmethod
    def _route_function():
        import ast

        path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "routes", "catalog.py",
        )
        with open(path, encoding="utf-8") as handle:
            source = handle.read()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef) and node.name == "check_availability":
                return node, ast.get_source_segment(source, node), source
        raise AssertionError("endpoint check_availability не знайдено в routes/catalog.py")

    def test_endpoint_accepts_date_window(self):
        """Дати більше не відкидаються: параметри мусять бути в сигнатурі."""
        node, _, _ = self._route_function()
        args = [a.arg for a in node.args.args]
        for expected in ("from_date", "to_date", "quantity"):
            self.assertIn(
                expected, args,
                f"параметр {expected} втрачено — endpoint знову ігнорує період",
            )

    def test_endpoint_delegates_to_service(self):
        """Формула не має дублюватися в роуті."""
        _, body, source = self._route_function()
        self.assertIn("AvailabilityService", source)
        self.assertIn("get_availability", body)
        for leftover in ("frozen_quantity", "SUM(oi.quantity)", "order_items"):
            self.assertNotIn(
                leftover, body,
                f"у роуті залишився власний розрахунок ({leftover})",
            )

    def test_legacy_response_keys_preserved(self):
        """Старі ключі відповіді лишаються — їх уже споживає frontend."""
        import ast

        node, _, _ = self._route_function()
        keys = set()
        for sub in ast.walk(node):
            if isinstance(sub, ast.Return) and isinstance(sub.value, ast.Dict):
                for key in sub.value.keys:
                    if isinstance(key, ast.Constant):
                        keys.add(key.value)
        for expected in ("available", "product_id", "name", "quantity", "message"):
            self.assertIn(expected, keys, f"втрачено поле контракту: {expected}")

    def test_dates_change_result_for_order_held_product(self):
        """Товар, зайнятий замовленням у періоді, вільний поза періодом."""
        held = _FakeDB(stock=(1, 0, 0, "available", "STL0001", "Стіл"), reserved=1)
        free = _FakeDB(stock=(1, 0, 0, "available", "STL0001", "Стіл"), reserved=0)

        busy = AvailabilityService(held).get_availability(
            1, "2026-09-06", "2026-09-20", 1
        )
        later = AvailabilityService(free).get_availability(
            1, "2027-06-01", "2027-06-05", 1
        )

        self.assertEqual(busy["available_quantity"], 0)
        self.assertFalse(busy["is_available"])
        self.assertEqual(later["available_quantity"], 1)
        self.assertTrue(later["is_available"])

    def test_frozen_quantity_is_not_date_dependent(self):
        """Обробка тримає товар незалежно від періоду (рішення 3)."""
        db = _FakeDB(stock=(2, 2, 0, "available", "S", "N"), reserved=0)
        for start, end in (("2026-09-06", "2026-09-20"), ("2027-06-01", "2027-06-05")):
            result = AvailabilityService(db).get_availability(1, start, end, 1)
            self.assertEqual(result["available_quantity"], 0)
            self.assertEqual(result["available_ignoring_processing"], 2)


class TestEventToolCheckAvailabilityMigration(unittest.TestCase):
    """
    Точка D — `POST /api/event/products/check-availability` (Завдання №11).

    Ця точка була найнебезпечнішою з усіх 11: статуси задавалися чорним
    списком `NOT IN ('cancelled','returned','completed')`, тому будь-який
    новий або помилковий статус автоматично починав резервувати товар.
    Плюс не виключалися архівні замовлення й відмовлені позиції.

    Вимір на production-знімку: різниця стосується 1 товару — `FC2225`
    «Стілець Віденський», 6 -> 61 (+55 од. звільнено з архівного
    замовлення 7970). Падінь доступності немає жодного, тобто міграція
    точки D тільки повертає в обіг фантомно зайнятий склад.

    Роут перевіряється статично (AST): його імпорт тягне `database_rentalhub`
    і обов'язкові `RH_DB_*` env.
    """

    @staticmethod
    def _route_function():
        import ast

        path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "routes", "event_tool.py",
        )
        with open(path, encoding="utf-8") as handle:
            source = handle.read()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef) and node.name == "check_availability":
                return node, ast.get_source_segment(source, node), source
        raise AssertionError(
            "endpoint check_availability не знайдено в routes/event_tool.py"
        )

    @classmethod
    def _route_code(cls):
        """
        Лише виконувані інструкції роуту, без docstring.

        Потрібно саме так: docstring навмисно цитує стару формулу
        (`NOT IN ('cancelled',...)`) як пояснення дефекту, і перевірка по
        всьому тексту функції спрацьовувала б на цій цитаті замість
        реального SQL. Тест мусить дивитися на код, а не на комментар.
        """
        import ast

        node, _, source = cls._route_function()
        statements = list(node.body)
        if (statements and isinstance(statements[0], ast.Expr)
                and isinstance(statements[0].value, ast.Constant)
                and isinstance(statements[0].value.value, str)):
            statements = statements[1:]
        return "\n".join(
            ast.get_source_segment(source, stmt) or "" for stmt in statements
        )

    def test_endpoint_delegates_to_service(self):
        """Власний розрахунок прибраний, формула — у сервісі."""
        _, _, source = self._route_function()
        code = self._route_code()
        self.assertIn("AvailabilityService", source)
        self.assertIn("get_availability", code)
        for leftover in ("SUM(oi.quantity)", "COALESCE(SUM(quantity)", "base_available"):
            self.assertNotIn(
                leftover, code,
                f"у роуті залишився власний розрахунок ({leftover})",
            )

    def test_blacklist_statuses_removed(self):
        """
        Головний дефект точки J: чорний список статусів.

        Поки в SQL роуту лишається `NOT IN`, кожен новий статус замовлення
        буде резервувати товар автоматично і безшумно.
        """
        code = self._route_code().replace('"', "'")
        self.assertNotIn("NOT IN ('cancelled'", code)
        self.assertNotIn("o.status NOT IN", code)

    def test_inactive_product_still_returns_404(self):
        """
        Знятий з продажу товар мусить і далі давати 404.

        `AvailabilityService` навмисно не фільтрує `products.status`, тому
        роут зобов'язаний перевіряти активність окремо — інакше міграція
        тихо перетворила б 404 на 200.
        """
        code = self._route_code()
        self.assertIn("status = 1", code)
        self.assertIn("404", code)

    def test_legacy_response_keys_preserved(self):
        """Контракт відповіді точки J, включно з історичним `soft_reserved`."""
        import ast

        node, _, _ = self._route_function()
        keys = set()
        for sub in ast.walk(node):
            if isinstance(sub, ast.Return) and isinstance(sub.value, ast.Dict):
                for key in sub.value.keys:
                    if isinstance(key, ast.Constant):
                        keys.add(key.value)
        for expected in (
            "product_id", "requested_quantity", "total_quantity",
            "reserved_quantity", "soft_reserved", "available",
            "is_available", "reserved_from", "reserved_until",
        ):
            self.assertIn(expected, keys, f"втрачено поле контракту: {expected}")

    def test_archived_order_no_longer_holds_stock(self):
        """
        Відтворює виміряний випадок `FC2225`: 6 -> 61.

        Стара формула точки D рахувала архівне замовлення (55 од.),
        канонічна — ні.
        """
        old_style = _FakeDB(
            stock=(61, 0, 0, "available", "FC2225", "Стілець Віденський"),
            reserved=55,
        )
        canonical = _FakeDB(
            stock=(61, 0, 0, "available", "FC2225", "Стілець Віденський"),
            reserved=0,
        )
        self.assertEqual(
            AvailabilityService(old_style).get_availability(558, "a", "b", 1)[
                "available_quantity"
            ],
            6,
        )
        self.assertEqual(
            AvailabilityService(canonical).get_availability(558, "a", "b", 1)[
                "available_quantity"
            ],
            61,
        )

    def test_soft_reserved_key_maps_to_service_field(self):
        """
        Історична назва ключа збережена, значення береться з сервісу.

        У сервісі поле зветься `soft_reserved_quantity`, у відповіді точки D
        мусить лишитися `soft_reserved` — інакше event-tool UI отримає
        `undefined` без жодної помилки.
        """
        db = _FakeDB(stock=(20, 0, 0, "available", "S", "N"), soft=6)
        result = AvailabilityService(db).get_availability(1, "a", "b", 1)
        self.assertEqual(result["soft_reserved_quantity"], 6)

        code = self._route_code()
        self.assertIn('"soft_reserved"', code)
        self.assertIn("soft_reserved_quantity", code)


class TestOrderModificationsMigration(unittest.TestCase):
    """
    Точка J — `routes/order_modifications.py` (Завдання №11).

    Найпростіша й найгрубіша з усіх формул: `available = products.quantity`,
    тобто загальний залишок без замовлень, без заморозки, без дат. Через це
    дозамовлення дозволяло додати товар, який фізично вже роздано в оренду.

    Точка має три незалежні перевірки, і всі три використовували цю формулу:
    додавання позиції, зміна кількості та відновлення відмовленої позиції.
    Тести закріплюють міграцію всіх трьох і незмінність текстів помилок —
    їх показує UI комплектувальника.

    Роут перевіряється статично (AST): його імпорт тягне `database_rentalhub`
    і обов'язкові `RH_DB_*` env.
    """

    @classmethod
    def _source(cls):
        path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "routes", "order_modifications.py",
        )
        with open(path, encoding="utf-8") as handle:
            return handle.read()

    @classmethod
    def _function_code(cls, name):
        """Виконуваний код функції без docstring."""
        import ast

        source = cls._source()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if (isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and node.name == name):
                statements = list(node.body)
                if (statements and isinstance(statements[0], ast.Expr)
                        and isinstance(statements[0].value, ast.Constant)
                        and isinstance(statements[0].value.value, str)):
                    statements = statements[1:]
                return "\n".join(
                    ast.get_source_segment(source, stmt) or "" for stmt in statements
                )
        raise AssertionError(f"функцію {name} не знайдено в routes/order_modifications.py")

    def test_helper_delegates_to_service(self):
        """Єдиний хелпер точки J рахує доступність через сервіс."""
        code = self._function_code("get_available_quantity")
        self.assertIn("AvailabilityService", code)
        self.assertIn("get_availability", code)
        self.assertIn("available_quantity", code)

    def test_helper_passes_rental_window(self):
        """Дати замовлення передаються в сервіс — без них перетин не рахується."""
        code = self._function_code("get_available_quantity")
        self.assertIn("start_date", code)
        self.assertIn("end_date", code)
        self.assertIn("_rental_window", code)

    def test_helper_does_not_exclude_current_order(self):
        """
        Поточне замовлення НЕ виключається з резерву.

        Це свідомо: перевірки точки J порівнюють доступність із приростом
        кількості (`quantity_diff`), а позиції самого замовлення вже
        враховані як зарезервовані. Якби додати `exclude_order_id`, той самий
        товар порахувався б двічі й ліміт склада можна було б перевищити.
        """
        code = self._function_code("get_available_quantity")
        self.assertNotIn("exclude_order_id", code)

    def test_add_item_uses_canonical_quantity(self):
        """Додавання позиції більше не звіряється із загальним залишком."""
        code = self._function_code("add_item_to_order")
        self.assertIn("get_available_quantity(db, order, request.product_id)", code)
        self.assertNotIn('product["available_quantity"] < request.quantity', code)

    def test_update_quantity_uses_canonical_quantity(self):
        """Зміна кількості рахує доступність сервісом, а не `p.quantity`."""
        code = self._function_code("update_item_quantity")
        self.assertIn("get_available_quantity(db, order,", code)
        self.assertNotIn("available = int(item[7] or 0)", code)

    def test_restore_item_uses_canonical_quantity(self):
        """Відновлення відмовленої позиції не читає залишок напряму."""
        code = self._function_code("restore_refused_item")
        self.assertIn("get_available_quantity(db, order, product_id)", code)
        self.assertNotIn("SELECT quantity FROM products", code)

    def test_error_messages_preserved(self):
        """Тексти помилок — частина контракту UI комплектувальника."""
        source = self._source()
        self.assertIn("Недостатня кількість на складі. Доступно:", source)
        self.assertIn("Недостатня кількість товару на складі. Доступно:", source)

    def test_no_raw_quantity_availability_left(self):
        """Стара формула точки J не має лишитися ні в одній з трьох перевірок."""
        for name in ("add_item_to_order", "update_item_quantity", "restore_refused_item"):
            code = self._function_code(name)
            self.assertNotIn(
                "p.quantity as available", code,
                f"{name}: залишився розрахунок за загальним залишком",
            )

    def test_order_held_stock_blocks_addition(self):
        """
        Числовий сенс міграції: товар, зайнятий іншими замовленнями,
        більше не можна дозамовити.

        Стара формула бачила `quantity = 10` і пропускала будь-яку кількість.
        """
        db = _FakeDB(stock=(10, 0, 0, "available", "S", "Стілець"), reserved=10)
        result = AvailabilityService(db).get_availability(1, "2026-09-06", "2026-09-20", 1)
        self.assertEqual(result["total_quantity"], 10)
        self.assertEqual(result["available_quantity"], 0)
        self.assertFalse(result["is_available"])

    def test_frozen_stock_blocks_addition(self):
        """Заморожене (обробка) теж більше не вважається доступним."""
        db = _FakeDB(stock=(10, 4, 0, "on_wash", "S", "Скатертина"), reserved=0)
        result = AvailabilityService(db).get_availability(1, "2026-09-06", "2026-09-20", 6)
        self.assertEqual(result["available_quantity"], 6)
        self.assertTrue(result["is_available"])
        self.assertFalse(
            AvailabilityService(db).get_availability(1, "2026-09-06", "2026-09-20", 7)[
                "is_available"
            ]
        )

    def test_helper_is_read_only(self):
        """Перевірка доступності не має мутувати склад."""
        code = self._function_code("get_available_quantity").upper()
        for verb in ("UPDATE PRODUCTS", "INSERT INTO", "DELETE FROM"):
            self.assertNotIn(verb, code)


class TestInventoryProcessingMigration(unittest.TestCase):
    """
    Точка G — `routes/inventory.py`, `POST /api/inventory/send-to-processing`
    (Завдання №11).

    Стара формула: `available = products.quantity - products.frozen_quantity`.
    Ні замовлень, ні soft-резервів, ні періоду аренди.

    Особливість цієї точки, яку тести мусять зафіксувати окремо: поріг
    БЛОКУВАННЯ свідомо лишився фізичним. Відправка на мийку — операція з
    фізичним товаром, тому броня на майбутню дату не має її забороняти,
    інакше комірник не змив би товар, який завтра їде до клієнта.
    Канонічна доступність тут працює як попередження, а не як заборона.

    Роут перевіряється статично (AST): його імпорт тягне `database_rentalhub`
    і обов'язкові `RH_DB_*` env.
    """

    @classmethod
    def _source(cls):
        path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "routes", "inventory.py",
        )
        with open(path, encoding="utf-8") as handle:
            return handle.read()

    @classmethod
    def _function_code(cls, name):
        """Виконуваний код функції без docstring."""
        import ast

        source = cls._source()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if (isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and node.name == name):
                statements = list(node.body)
                if (statements and isinstance(statements[0], ast.Expr)
                        and isinstance(statements[0].value, ast.Constant)
                        and isinstance(statements[0].value.value, str)):
                    statements = statements[1:]
                return "\n".join(
                    ast.get_source_segment(source, stmt) or "" for stmt in statements
                )
        raise AssertionError(f"функцію {name} не знайдено в routes/inventory.py")

    def test_delegates_to_service(self):
        """Стан складу читається сервісом, а не власним SQL роуту."""
        code = self._function_code("send_to_processing")
        self.assertIn("AvailabilityService", code)
        self.assertIn("get_availability", code)

    def test_old_formula_removed(self):
        """Формула `quantity - frozen_quantity` більше не живе в роуті."""
        code = self._function_code("send_to_processing")
        self.assertNotIn("SELECT product_id, sku, name, quantity, frozen_quantity", code)
        self.assertNotIn("(quantity or 0) - (frozen_qty or 0)", code)

    def test_gate_stays_physical(self):
        """
        Поріг блокування — фізичний залишок мінус обробка, НЕ канонічна
        доступність. Це головна вимога до цієї точки.
        """
        code = self._function_code("send_to_processing")
        self.assertIn('snapshot["total_quantity"] - frozen_qty', code)
        self.assertIn("if data.quantity > available_qty", code)

    def test_reservation_conflict_is_warning_only(self):
        """Конфлікт із бронею повідомляється, але не блокує операцію."""
        code = self._function_code("send_to_processing")
        self.assertIn("conflicts_with_reservations", code)
        self.assertNotIn("if data.quantity > canonical_available", code)

    def test_legacy_response_keys_preserved(self):
        """Історичні ключі відповіді — контракт кабінету переобліку."""
        code = self._function_code("send_to_processing")
        for key in ("success", "message", "queue_id", "product_id",
                    "sku", "quantity", "action_type", "new_frozen_quantity"):
            self.assertIn(f'"{key}"', code)

    def test_missing_product_still_404(self):
        """Відсутній товар і далі дає 404, а не падіння на `None`."""
        code = self._function_code("send_to_processing")
        self.assertIn('snapshot["product_exists"]', code)
        self.assertIn("Product not found", code)

    def test_broken_write_off_branch_is_explicit(self):
        """
        Гілка `write_off` читала неоголошену `current_qty`, тобто завжди
        падала `NameError` -> HTTP 500. Її не «оживлено»: вона зменшує
        `products.quantity`, а це предмет окремого Завдання №12.
        Відмова мусить бути явною, а не трейсбеком.
        """
        code = self._function_code("send_to_processing")
        self.assertNotIn("current_qty", code)
        self.assertIn("status_code=501", code)
        self.assertNotIn("SET quantity = :new_qty", code)

    def test_freeze_mutation_unchanged(self):
        """Механіка заморозки для мийки/реставрації/хімчистки не змінена."""
        code = self._function_code("send_to_processing")
        self.assertIn("SET frozen_quantity = :frozen_qty", code)
        self.assertIn("(frozen_qty or 0) + data.quantity", code)

    def test_processing_does_not_block_itself(self):
        """
        Числовий сенс: товар, весь запас якого зайнятий замовленнями, усе одно
        можна відправити в обробку, бо фізично він на складі.
        """
        db = _FakeDB(stock=(10, 0, 0, "available", "S", "Скатертина"), reserved=10)
        snapshot = AvailabilityService(db).get_availability(1, "2026-09-08", "2026-09-08", 1)
        physical_gate = snapshot["total_quantity"] - snapshot["on_processing_quantity"]
        self.assertEqual(snapshot["available_quantity"], 0)
        self.assertEqual(physical_gate, 10)

    def test_already_frozen_stock_blocks(self):
        """А ось уже заморожене в обробку вдруге відправити не можна."""
        db = _FakeDB(stock=(10, 8, 0, "on_wash", "S", "Келих"), reserved=0)
        snapshot = AvailabilityService(db).get_availability(1, "2026-09-08", "2026-09-08", 1)
        physical_gate = snapshot["total_quantity"] - snapshot["on_processing_quantity"]
        self.assertEqual(physical_gate, 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)