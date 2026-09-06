"""Finance service layer — єдина точка доступу до фінансових даних.

Модулі-споживачі (Documents та інші) не повинні звертатися до таблиць
`fin_payments` / `fin_deposit_holds` / `fin_deposit_events` напряму.
Замість цього вони використовують read-only фасад `FinanceService`.

Приклад:
    >>> from services.finance import get_finance_service
    >>> finance = get_finance_service()
    >>> snapshot = finance.get_order_deposit(db, 123)
    >>> snapshot.available
    True
"""
from .finance_service import (
    FINANCE_MODULE,
    STATUS_AVAILABLE,
    STATUS_DISABLED,
    DepositBalanceSnapshot,
    DepositEventRecord,
    DepositEventsSnapshot,
    DepositRecord,
    DepositSnapshot,
    FinanceService,
    LateFeeSnapshot,
    PaymentRecord,
    PaymentsSnapshot,
    get_finance_service,
    is_finance_available,
)

__all__ = [
    "FINANCE_MODULE",
    "STATUS_AVAILABLE",
    "STATUS_DISABLED",
    "FinanceService",
    "get_finance_service",
    "is_finance_available",
    "PaymentRecord",
    "PaymentsSnapshot",
    "LateFeeSnapshot",
    "DepositRecord",
    "DepositSnapshot",
    "DepositEventRecord",
    "DepositEventsSnapshot",
    "DepositBalanceSnapshot",
]