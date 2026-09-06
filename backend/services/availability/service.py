"""
AvailabilityService — єдина точка розрахунку доступності товару.

До появи цього сервісу доступність рахувалася в 11 місцях за 9 різними
формулами, які на production-даних розходилися на 294–588 товарах
(максимальний розрив — 210 одиниць на один товар). Деталі та докази:
`audit/AVAILABILITY_INVENTORY.md`.

Канонічна формула (§7.1 аудиту):

    available = products.quantity
              - products.frozen_quantity          (рішення 3)
              - зарезервоване замовленнями        (рішення 1, 2, 6)
              - soft-резерви мудборда             (рішення 5)

Сервіс лише читає дані. Він не виконує INSERT/UPDATE/DELETE і не створює
схему — так само, як `FinanceService` (Завдання №6).
"""
from typing import Dict, List, Optional

from sqlalchemy import text

from .rules import (
    ACTIVE_ITEM_STATUS,
    COUNT_SOFT_RESERVATIONS,
    EXCLUDE_ARCHIVED_ORDERS,
    IN_RENT_ORDER_STATUSES,
    RESERVING_ORDER_STATUSES,
    SOFT_RESERVATION_ACTIVE_STATUS,
    statuses_placeholder,
)


class AvailabilityService:
    """Read-only фасад над розрахунком доступності."""

    def __init__(self, db):
        self.db = db

    # ------------------------------------------------------------------
    # Складові формули
    # ------------------------------------------------------------------
    def _product_stock(self, product_id: int) -> Dict:
        """Загальний залишок, заморожене й довідкові поля товару."""
        result = self.db.execute(
            text(
                """
                SELECT quantity, frozen_quantity, in_laundry, state, sku, name
                FROM products
                WHERE product_id = :product_id
                """
            ),
            {"product_id": product_id},
        )
        row = result.fetchone()
        result.close()

        if not row:
            return {
                "total": 0,
                "frozen": 0,
                "in_laundry": 0,
                "state": None,
                "sku": None,
                "name": None,
                "exists": False,
            }

        return {
            "total": int(row[0] or 0),
            "frozen": int(row[1] or 0),
            "in_laundry": int(row[2] or 0),
            "state": row[3],
            "sku": row[4],
            "name": row[5],
            "exists": True,
        }

    def _reserved_by_orders(
        self,
        product_id: int,
        start_date: str,
        end_date: str,
        statuses: tuple,
        exclude_order_id: Optional[int] = None,
    ) -> int:
        """
        Кількість, яку тримають замовлення з перетином періоду.

        Враховує рішення 1 і 2 (перелік статусів), рішення 6 (архівні
        замовлення не резервують) і `order_items.status` — відмовлена
        позиція товар не тримає.
        """
        status_sql, status_params = statuses_placeholder("st", statuses)

        query = f"""
            SELECT COALESCE(SUM(oi.quantity), 0)
            FROM order_items oi
            JOIN orders o ON oi.order_id = o.order_id
            WHERE oi.product_id = :product_id
              AND COALESCE(oi.status, '{ACTIVE_ITEM_STATUS}') = :item_status
              AND o.status IN {status_sql}
              AND o.rental_start_date <= :end_date
              AND o.rental_end_date >= :start_date
        """
        if EXCLUDE_ARCHIVED_ORDERS:
            query += " AND COALESCE(o.is_archived, 0) = 0"

        params = {
            "product_id": product_id,
            "item_status": ACTIVE_ITEM_STATUS,
            "start_date": start_date,
            "end_date": end_date,
        }
        params.update(status_params)

        if exclude_order_id:
            query += " AND o.order_id != :exclude_order_id"
            params["exclude_order_id"] = exclude_order_id

        result = self.db.execute(text(query), params)
        row = result.fetchone()
        result.close()
        # Порожня вибірка не повинна ламати перевірку доступності —
        # відсутність рядка означає «нічого не зарезервовано».
        return int(row[0] or 0) if row else 0

    def _soft_reserved(
        self,
        product_id: int,
        start_date: str,
        end_date: str,
        exclude_board_id: Optional[str] = None,
    ) -> int:
        """
        Активні, не протерміновані soft-резерви мудборда (рішення 5).

        Раніше їх читала лише одна точка з 11, тому мудборд «тримав» товар
        непомітно для решти системи.
        """
        if not COUNT_SOFT_RESERVATIONS:
            return 0

        query = """
            SELECT COALESCE(SUM(sr.quantity), 0)
            FROM event_soft_reservations sr
            WHERE sr.product_id = :product_id
              AND COALESCE(sr.status, :active_status) = :active_status
              AND sr.expires_at > NOW()
              AND sr.reserved_from <= :end_date
              AND sr.reserved_until >= :start_date
        """
        params = {
            "product_id": product_id,
            "active_status": SOFT_RESERVATION_ACTIVE_STATUS,
            "start_date": start_date,
            "end_date": end_date,
        }
        if exclude_board_id:
            query += " AND sr.board_id != :exclude_board_id"
            params["exclude_board_id"] = exclude_board_id

        try:
            result = self.db.execute(text(query), params)
            row = result.fetchone()
            result.close()
            return int(row[0] or 0) if row else 0
        except Exception:
            # Таблиця може бути відсутня у відсталих середовищах. Доступність
            # мусить рахуватися й тоді — краще недооблік soft-резервів, ніж
            # 500 на каталозі.
            return 0

    # ------------------------------------------------------------------
    # Публічний контракт
    # ------------------------------------------------------------------
    def get_availability(
        self,
        product_id: int,
        start_date: str,
        end_date: str,
        quantity: int = 1,
        exclude_order_id: Optional[int] = None,
        exclude_board_id: Optional[str] = None,
    ) -> Dict:
        """
        Порахувати доступність одного товару на період.

        Args:
            product_id: ID товару.
            start_date: початок періоду, `YYYY-MM-DD`.
            end_date: кінець періоду, `YYYY-MM-DD`.
            quantity: запитувана кількість (для прапорця `is_available`).
            exclude_order_id: не враховувати це замовлення (редагування).
            exclude_board_id: не враховувати soft-резерви цього мудборда.

        Returns:
            dict з канонічними полями доступності.
        """
        stock = self._product_stock(product_id)

        reserved = self._reserved_by_orders(
            product_id, start_date, end_date, RESERVING_ORDER_STATUSES, exclude_order_id
        )
        in_rent = self._reserved_by_orders(
            product_id, start_date, end_date, IN_RENT_ORDER_STATUSES, exclude_order_id
        )
        soft_reserved = self._soft_reserved(
            product_id, start_date, end_date, exclude_board_id
        )

        # Заморожене віднімається як недоступний залишок (рішення 3).
        available = max(0, stock["total"] - stock["frozen"] - reserved - soft_reserved)

        # Скільки менеджер міг би видати, якщо обробку зробити терміново.
        # Потрібне, щоб не втратити наявну поведінку «обробка попереджає,
        # а не блокує» — вона лишається свідомим рішенням оператора.
        available_ignoring_processing = max(
            0, stock["total"] - reserved - soft_reserved
        )

        return {
            "product_id": product_id,
            "sku": stock["sku"],
            "product_name": stock["name"],
            "total_quantity": stock["total"],
            "reserved_quantity": reserved,
            "in_rent": in_rent,
            "soft_reserved_quantity": soft_reserved,
            "on_processing_quantity": stock["frozen"],
            "available_quantity": available,
            "ready_quantity": available,
            "available_ignoring_processing": available_ignoring_processing,
            "requested_quantity": quantity,
            "is_available": available >= quantity,
            "needs_processing_rush": (
                available < quantity
                and available_ignoring_processing >= quantity
                and stock["frozen"] > 0
            ),
            "product_exists": stock["exists"],
        }

    def get_order_availability(
        self,
        items: List[Dict],
        start_date: str,
        end_date: str,
        exclude_order_id: Optional[int] = None,
    ) -> Dict:
        """
        Порахувати доступність для набору позицій замовлення.

        Args:
            items: `[{"product_id": int, "quantity": int}, ...]`
        """
        results = []
        unavailable = []

        for item in items:
            result = self.get_availability(
                product_id=item["product_id"],
                start_date=start_date,
                end_date=end_date,
                quantity=item.get("quantity", 1),
                exclude_order_id=exclude_order_id,
            )
            results.append(result)
            if not result["is_available"]:
                unavailable.append(result)

        return {
            "all_available": len(unavailable) == 0,
            "items": results,
            "unavailable_items": unavailable,
        }

    def get_bulk_availability(
        self,
        product_ids: List[int],
        start_date: str,
        end_date: str,
    ) -> Dict[int, Dict]:
        """
        Доступність для списку товарів (каталог, календар).

        Один запит на резерви й один на soft-резерви замість N+1: каталог
        показує тисячі позицій, тому поштучний виклик тут неприйнятний.
        """
        if not product_ids:
            return {}

        id_keys = [f"pid{i}" for i in range(len(product_ids))]
        id_fragment = "(" + ", ".join(f":{k}" for k in id_keys) + ")"
        id_params = {k: v for k, v in zip(id_keys, product_ids)}

        status_sql, status_params = statuses_placeholder("st", RESERVING_ORDER_STATUSES)

        stock_result = self.db.execute(
            text(
                f"""
                SELECT product_id, quantity, frozen_quantity, sku, name
                FROM products
                WHERE product_id IN {id_fragment}
                """
            ),
            dict(id_params),
        )
        stocks = {
            int(r[0]): {
                "total": int(r[1] or 0),
                "frozen": int(r[2] or 0),
                "sku": r[3],
                "name": r[4],
            }
            for r in stock_result
        }
        stock_result.close()

        reserved_query = f"""
            SELECT oi.product_id, COALESCE(SUM(oi.quantity), 0)
            FROM order_items oi
            JOIN orders o ON oi.order_id = o.order_id
            WHERE oi.product_id IN {id_fragment}
              AND COALESCE(oi.status, '{ACTIVE_ITEM_STATUS}') = :item_status
              AND o.status IN {status_sql}
              AND o.rental_start_date <= :end_date
              AND o.rental_end_date >= :start_date
        """
        if EXCLUDE_ARCHIVED_ORDERS:
            reserved_query += " AND COALESCE(o.is_archived, 0) = 0"
        reserved_query += " GROUP BY oi.product_id"

        reserved_params = {
            "item_status": ACTIVE_ITEM_STATUS,
            "start_date": start_date,
            "end_date": end_date,
        }
        reserved_params.update(id_params)
        reserved_params.update(status_params)

        reserved_result = self.db.execute(text(reserved_query), reserved_params)
        reserved_map = {int(r[0]): int(r[1] or 0) for r in reserved_result}
        reserved_result.close()

        soft_map = {}
        if COUNT_SOFT_RESERVATIONS:
            soft_params = {
                "active_status": SOFT_RESERVATION_ACTIVE_STATUS,
                "start_date": start_date,
                "end_date": end_date,
            }
            soft_params.update(id_params)
            try:
                soft_result = self.db.execute(
                    text(
                        f"""
                        SELECT sr.product_id, COALESCE(SUM(sr.quantity), 0)
                        FROM event_soft_reservations sr
                        WHERE sr.product_id IN {id_fragment}
                          AND COALESCE(sr.status, :active_status) = :active_status
                          AND sr.expires_at > NOW()
                          AND sr.reserved_from <= :end_date
                          AND sr.reserved_until >= :start_date
                        GROUP BY sr.product_id
                        """
                    ),
                    soft_params,
                )
                soft_map = {int(r[0]): int(r[1] or 0) for r in soft_result}
                soft_result.close()
            except Exception:
                soft_map = {}

        out = {}
        for pid in product_ids:
            stock = stocks.get(
                pid, {"total": 0, "frozen": 0, "sku": None, "name": None}
            )
            reserved = reserved_map.get(pid, 0)
            soft = soft_map.get(pid, 0)
            available = max(0, stock["total"] - stock["frozen"] - reserved - soft)
            out[pid] = {
                "product_id": pid,
                "sku": stock["sku"],
                "product_name": stock["name"],
                "total_quantity": stock["total"],
                "reserved_quantity": reserved,
                "soft_reserved_quantity": soft,
                "on_processing_quantity": stock["frozen"],
                "available_quantity": available,
                "available_ignoring_processing": max(
                    0, stock["total"] - reserved - soft
                ),
            }
        return out