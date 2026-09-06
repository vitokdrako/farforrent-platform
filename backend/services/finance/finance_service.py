"""FinanceService — read-only фасад над фінансовими таблицями.

Призначення
-----------
Розв'язати модуль Documents і фінансовий домен. До появи цього шару
`routes/documents.py`, `routes/document_policy.py` та
`services/doc_engine/data_builders.py` читали `fin_payments`,
`fin_deposit_holds` і `fin_deposit_events` напряму, через що модуль
`documents` жорстко залежав від внутрішньої схеми Finance, а стан
«Finance = OFF» призводив би до рантайм-помилок.

Межі відповідальності
---------------------
Фасад **лише читає** дані. Він не проводить транзакцій, не змінює
статусів застави, не створює платежів і не дублює жодного фінансового
правила — усе це залишається у власника домену (`routes/finance.py`).
Правила формування документів (підсумки акта, manager override) також
залишаються у Documents, бо це логіка документа, а не фінансів.

Доступність модуля
------------------
Кожен метод повертає snapshot із полями ``available`` і ``status``.
Якщо модуль ``finance`` вимкнений через Module Manager, повертається
порожній snapshot зі ``status="disabled"`` — без винятків і без 500-ї.
Споживач сам вирішує, як показати відсутність фінансових даних.

Приклад:
    >>> from services.finance import get_finance_service
    >>> finance = get_finance_service()
    >>> deposit = finance.get_order_deposit(db, 123)
    >>> deposit.status
    'available'
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterable, Optional, Sequence

from sqlalchemy import text
from sqlalchemy.orm import Session

FINANCE_MODULE = "finance"
STATUS_AVAILABLE = "available"
STATUS_DISABLED = "disabled"


def is_finance_available() -> bool:
    """Чи увімкнений модуль Finance.

    Перевірка робиться через Module Manager. Якщо менеджер недоступний
    (наприклад, у скриптах або тестах без bootstrap), вважаємо Finance
    увімкненим — це збігається з історичною поведінкою кодової бази.

    Returns:
        True, якщо фінансові дані можна читати.
    """
    try:
        from core.module_manager import is_module_enabled

        return bool(is_module_enabled(FINANCE_MODULE))
    except Exception:
        return True


def _to_float(value: Any, default: float = 0.0) -> float:
    """Безпечно привести значення БД до float."""
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize_order_id(order_id: Any) -> Any:
    """Привести order_id до int, якщо це можливо без втрати значення.

    Історично одні виклики передавали int, інші — рядок. MySQL порівнює
    їх однаково, тому нормалізація не змінює результат запиту, але робить
    контракт фасаду передбачуваним.
    """
    if isinstance(order_id, int):
        return order_id
    try:
        return int(order_id)
    except (TypeError, ValueError):
        return order_id


# ============================================================
# PAYMENTS
# ============================================================


@dataclass(frozen=True)
class PaymentRecord:
    """Один платіж ордера у вигляді, придатному для документів."""

    id: Optional[int]
    payment_type: Optional[str]
    method: Optional[str]
    amount: float
    currency: str
    payer_name: Optional[str]
    occurred_at: Optional[datetime]
    note: Optional[str]
    status: Optional[str]
    description: Optional[str]

    @property
    def is_settled(self) -> bool:
        """Чи платіж реально надійшов (`completed` або `confirmed`)."""
        return self.status in ("completed", "confirmed")


@dataclass(frozen=True)
class PaymentsSnapshot:
    """Результат читання платежів ордера."""

    items: tuple[PaymentRecord, ...] = ()
    available: bool = True
    status: str = STATUS_AVAILABLE

    def __iter__(self):
        return iter(self.items)

    def __len__(self) -> int:
        return len(self.items)

    def __bool__(self) -> bool:
        return bool(self.items)

    def has_payment_type(self, payment_type: str) -> bool:
        """Чи є серед платежів запис заданого типу."""
        return any(item.payment_type == payment_type for item in self.items)


@dataclass(frozen=True)
class LateFeeSnapshot:
    """Сума нарахованого, але не оплаченого прострочення."""

    total: float = 0.0
    available: bool = True
    status: str = STATUS_AVAILABLE


# ============================================================
# DEPOSITS
# ============================================================


@dataclass(frozen=True)
class DepositRecord:
    """Застава ордера."""

    id: Optional[int]
    held_amount: float
    used_amount: float
    refunded_amount: float
    actual_amount: float
    currency: str
    exchange_rate: float
    status: Optional[str]

    @property
    def available_amount(self) -> float:
        """Залишок застави: утримано мінус використано мінус повернено."""
        return self.held_amount - self.used_amount - self.refunded_amount

    @property
    def display_amount(self) -> float:
        """Сума для показу: фактична, а за її відсутності — утримана.

        Відтворює історичне правило акта взаєморозрахунків
        (`actual_amount` якщо непорожній, інакше `held_amount`).
        """
        return self.actual_amount if self.actual_amount else self.held_amount


@dataclass(frozen=True)
class DepositSnapshot:
    """Результат читання застави ордера."""

    deposit: Optional[DepositRecord] = None
    available: bool = True
    status: str = STATUS_AVAILABLE

    def __bool__(self) -> bool:
        return self.deposit is not None

    @property
    def exists(self) -> bool:
        """Чи існує застава по ордеру."""
        return self.deposit is not None


@dataclass(frozen=True)
class DepositEventRecord:
    """Подія по заставі (наприклад, повернення)."""

    event_type: Optional[str]
    amount: float
    occurred_at: Optional[datetime]
    note: Optional[str]


@dataclass(frozen=True)
class DepositEventsSnapshot:
    """Результат читання подій застави."""

    items: tuple[DepositEventRecord, ...] = ()
    available: bool = True
    status: str = STATUS_AVAILABLE

    def __iter__(self):
        return iter(self.items)

    def __len__(self) -> int:
        return len(self.items)

    def __bool__(self) -> bool:
        return bool(self.items)


@dataclass(frozen=True)
class DepositBalanceSnapshot:
    """Агрегати застави для policy-перевірок.

    Attributes:
        deposit_held: Утримана сума застави (0, якщо застави немає).
        deposit_to_refund: Сума, доступна до повернення клієнту.
    """

    deposit_held: float = 0.0
    deposit_to_refund: float = 0.0
    available: bool = True
    status: str = STATUS_AVAILABLE


# ============================================================
# SERVICE
# ============================================================


class FinanceService:
    """Read-only контракт доступу до фінансових даних ордера."""

    def __init__(self, availability_check=is_finance_available) -> None:
        """
        Args:
            availability_check: Callable, що повертає True, якщо Finance
                увімкнений. Замінюється у тестах.
        """
        self._availability_check = availability_check

    # -- availability ------------------------------------------------

    def is_available(self) -> bool:
        """Чи доступні фінансові дані просто зараз."""
        try:
            return bool(self._availability_check())
        except Exception:
            return True

    # -- payments ----------------------------------------------------

    def list_order_payments(
        self,
        db: Session,
        order_id: Any,
        statuses: Optional[Sequence[str]] = None,
        payment_types: Optional[Sequence[str]] = None,
    ) -> PaymentsSnapshot:
        """Отримати платежі ордера.

        Args:
            db: Сесія RentalHub.
            order_id: Ідентифікатор замовлення.
            statuses: Якщо задано — лише платежі з цими статусами.
            payment_types: Якщо задано — лише платежі цих типів.

        Returns:
            PaymentsSnapshot, упорядкований за `occurred_at` за зростанням.
        """
        if not self.is_available():
            return PaymentsSnapshot(items=(), available=False, status=STATUS_DISABLED)

        params: dict[str, Any] = {"order_id": _normalize_order_id(order_id)}
        conditions = ["order_id = :order_id"]

        if statuses:
            keys = self._bind_list("st", statuses, params)
            conditions.append(f"status IN ({keys})")
        if payment_types:
            keys = self._bind_list("pt", payment_types, params)
            conditions.append(f"payment_type IN ({keys})")

        rows = db.execute(
            text(
                f"""
                SELECT id, payment_type, method, amount, currency,
                       payer_name, occurred_at, note, status, description
                FROM fin_payments
                WHERE {' AND '.join(conditions)}
                ORDER BY occurred_at
                """
            ),
            params,
        ).fetchall()

        items = tuple(
            PaymentRecord(
                id=row[0],
                payment_type=row[1],
                method=row[2],
                amount=_to_float(row[3]),
                currency=row[4] or "UAH",
                payer_name=row[5],
                occurred_at=row[6],
                note=row[7],
                status=row[8],
                description=row[9],
            )
            for row in rows
        )
        return PaymentsSnapshot(items=items)

    def get_pending_late_total(self, db: Session, order_id: Any) -> LateFeeSnapshot:
        """Сума нарахованого менеджером, але ще не оплаченого прострочення."""
        if not self.is_available():
            return LateFeeSnapshot(total=0.0, available=False, status=STATUS_DISABLED)

        row = db.execute(
            text(
                """
                SELECT COALESCE(SUM(amount), 0)
                FROM fin_payments
                WHERE order_id = :order_id
                  AND payment_type = 'late'
                  AND status = 'pending'
                """
            ),
            {"order_id": _normalize_order_id(order_id)},
        ).fetchone()

        return LateFeeSnapshot(total=_to_float(row[0]) if row else 0.0)

    # -- deposits ----------------------------------------------------

    def get_order_deposit(self, db: Session, order_id: Any) -> DepositSnapshot:
        """Отримати заставу ордера (не більше однієї)."""
        if not self.is_available():
            return DepositSnapshot(deposit=None, available=False, status=STATUS_DISABLED)

        row = db.execute(
            text(
                """
                SELECT id, held_amount, used_amount, refunded_amount, status,
                       actual_amount, currency, exchange_rate
                FROM fin_deposit_holds
                WHERE order_id = :order_id
                LIMIT 1
                """
            ),
            {"order_id": _normalize_order_id(order_id)},
        ).fetchone()

        if not row:
            return DepositSnapshot(deposit=None)

        deposit = DepositRecord(
            id=row[0],
            held_amount=_to_float(row[1]),
            used_amount=_to_float(row[2]),
            refunded_amount=_to_float(row[3]),
            actual_amount=_to_float(row[5]),
            currency=row[6] or "UAH",
            exchange_rate=_to_float(row[7], default=1.0) or 1.0,
            status=row[4],
        )
        return DepositSnapshot(deposit=deposit)

    def list_deposit_refund_events(
        self, db: Session, deposit_id: Any
    ) -> DepositEventsSnapshot:
        """Події повернення застави, за зростанням дати."""
        if not self.is_available():
            return DepositEventsSnapshot(
                items=(), available=False, status=STATUS_DISABLED
            )
        if deposit_id is None:
            return DepositEventsSnapshot(items=())

        rows = db.execute(
            text(
                """
                SELECT event_type, amount, occurred_at, note
                FROM fin_deposit_events
                WHERE deposit_id = :deposit_id AND event_type = 'refunded'
                ORDER BY occurred_at
                """
            ),
            {"deposit_id": deposit_id},
        ).fetchall()

        items = tuple(
            DepositEventRecord(
                event_type=row[0],
                amount=_to_float(row[1]),
                occurred_at=row[2],
                note=row[3],
            )
            for row in rows
        )
        return DepositEventsSnapshot(items=items)

    def get_order_deposit_balance(
        self, db: Session, order_id: Any
    ) -> DepositBalanceSnapshot:
        """Агрегати застави для policy-перевірок доступності документів.

        Відтворює історичну семантику `LEFT JOIN fin_deposit_holds` з
        `COALESCE(...)`: якщо застави немає або якісь суми `NULL`,
        відповідне значення дорівнює 0.
        """
        if not self.is_available():
            return DepositBalanceSnapshot(
                deposit_held=0.0,
                deposit_to_refund=0.0,
                available=False,
                status=STATUS_DISABLED,
            )

        row = db.execute(
            text(
                """
                SELECT COALESCE(held_amount, 0) AS deposit_held,
                       COALESCE(held_amount - used_amount - refunded_amount, 0)
                           AS deposit_to_refund
                FROM fin_deposit_holds
                WHERE order_id = :order_id
                LIMIT 1
                """
            ),
            {"order_id": _normalize_order_id(order_id)},
        ).fetchone()

        if not row:
            return DepositBalanceSnapshot()

        return DepositBalanceSnapshot(
            deposit_held=_to_float(row[0]),
            deposit_to_refund=_to_float(row[1]),
        )

    # -- internals ---------------------------------------------------

    @staticmethod
    def _bind_list(prefix: str, values: Iterable[str], params: dict[str, Any]) -> str:
        """Розкласти список значень у named-параметри для `IN (...)`."""
        keys = []
        for index, value in enumerate(values):
            key = f"{prefix}_{index}"
            params[key] = value
            keys.append(f":{key}")
        return ", ".join(keys)


_finance_service: Optional[FinanceService] = None


def get_finance_service() -> FinanceService:
    """Отримати процес-глобальний екземпляр FinanceService."""
    global _finance_service
    if _finance_service is None:
        _finance_service = FinanceService()
    return _finance_service