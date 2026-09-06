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


if __name__ == "__main__":
    unittest.main(verbosity=2)