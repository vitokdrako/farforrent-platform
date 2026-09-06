"""Одноразова верифікація Завдання №6 — FinanceService boundary.

Перевіряє:
1. Змінені модулі Documents імпортуються.
2. У Documents немає прямих звернень до fin_* таблиць.
3. FinanceService повертає дані при Finance = ON (fake-сесія).
4. FinanceService контрольовано деградує при Finance = OFF.
5. SQL фасаду не змінює схему і не робить записів.
"""
import os
import re
import sys
from datetime import datetime
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("JWT_SECRET_KEY", "verify-only-secret-not-for-production")
# Канонічні імена — див. backend/.env.example.
for _var in (
    "RH_DB_HOST", "RH_DB_USERNAME", "RH_DB_PASSWORD", "RH_DB_DATABASE",
    "OC_DB_HOST", "OC_DB_USERNAME", "OC_DB_PASSWORD", "OC_DB_DATABASE",
):
    os.environ.setdefault(_var, "verify")

failures: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    status = "OK  " if condition else "FAIL"
    print(f"   {status} {label}{(' — ' + detail) if detail else ''}")
    if not condition:
        failures.append(label)


print("\n" + "=" * 62)
print("ЗАВДАННЯ №6 — верифікація FinanceService boundary")
print("=" * 62)

# ---------------------------------------------------------------- 1
print("\n1. Імпорт змінених модулів Documents")
for module_name in (
    "services.finance",
    "services.doc_engine.data_builders",
    "routes.documents",
    "routes.document_policy",
):
    try:
        __import__(module_name)
        check(module_name, True)
    except Exception as exc:  # noqa: BLE001
        check(module_name, False, f"{type(exc).__name__}: {exc}")

# ---------------------------------------------------------------- 2
print("\n2. Прямі звернення до fin_* у модулі Documents")
FIN_RE = re.compile(r"fin_payments|fin_deposit_holds|fin_deposit_events")
documents_files = [
    "routes/documents.py",
    "routes/document_policy.py",
    "routes/document_render.py",
    "routes/document_pdf.py",
    "routes/document_signatures.py",
    "routes/document_manual_fields.py",
    "routes/document_email.py",
    "routes/master_agreements.py",
    "routes/order_annexes.py",
    "routes/template_admin.py",
    "routes/pdf.py",
    "services/doc_engine/data_builders.py",
    "services/document_context.py",
]
total_hits = 0
for rel in documents_files:
    path = BACKEND / rel
    if not path.exists():
        continue
    hits = len(FIN_RE.findall(path.read_text(encoding="utf-8")))
    total_hits += hits
    if hits:
        print(f"   HIT  {rel}: {hits}")
check("прямих fin_* у Documents = 0", total_hits == 0, f"знайдено {total_hits}")

# ---------------------------------------------------------------- 3
from services.finance import FinanceService, STATUS_AVAILABLE, STATUS_DISABLED


class FakeRow(tuple):
    """Рядок результату, сумісний з індексним доступом."""


class FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._rows[0] if self._rows else None


class FakeSession:
    """Мінімальна сесія: віддає підготовлені рядки, фіксує SQL."""

    def __init__(self, rows_by_table):
        self.rows_by_table = rows_by_table
        self.executed: list[str] = []

    def execute(self, statement, params=None):
        sql = str(statement)
        self.executed.append(sql)
        for table, rows in self.rows_by_table.items():
            if table in sql:
                return FakeResult(rows)
        return FakeResult([])


NOW = datetime(2026, 9, 5, 12, 0, 0)
rows = {
    "fin_payments": [
        FakeRow((1, "rent", "cash", 1000, "UAH", "Ivan", NOW, "n1", "completed", None)),
        FakeRow((2, "late", "cash", 250, "UAH", "Ivan", NOW, "n2", "pending", None)),
        FakeRow((3, "discount", "cash", 100, "UAH", "Ivan", NOW, None, "confirmed", None)),
    ],
    "fin_deposit_holds": [
        FakeRow((7, 5000, 1200, 800, "partially_used", 120, "EUR", 41.5)),
    ],
    "fin_deposit_events": [
        FakeRow(("refunded", 800, NOW, "Повернення застави")),
    ],
}

print("\n3. Finance = ON: фасад віддає дані")
service_on = FinanceService(availability_check=lambda: True)
db_on = FakeSession(rows)

payments = service_on.list_order_payments(db_on, 123)
check("list_order_payments: 3 записи", len(payments) == 3)
check("payments.status == available", payments.status == STATUS_AVAILABLE)
check("is_settled коректний", [p.is_settled for p in payments] == [True, False, True])
check("has_payment_type('discount')", payments.has_payment_type("discount") is True)
check("amount → float", isinstance(payments.items[0].amount, float))

late = service_on.get_pending_late_total(db_on, 123)
check("get_pending_late_total доступний", late.available is True)

deposit = service_on.get_order_deposit(db_on, 123).deposit
check("deposit прочитано", deposit is not None)
check("held_amount = 5000", deposit.held_amount == 5000.0)
check("available_amount = 3000", deposit.available_amount == 3000.0)
check("display_amount = actual (120)", deposit.display_amount == 120.0)
check("currency = EUR", deposit.currency == "EUR")
check("exchange_rate = 41.5", deposit.exchange_rate == 41.5)

events = service_on.list_deposit_refund_events(db_on, 7)
check("refund events: 1", len(events) == 1)

balance = service_on.get_order_deposit_balance(db_on, 123)
check("deposit_balance.available", balance.available is True)

# порожній ордер
db_empty = FakeSession({})
check("немає застави → exists False",
      service_on.get_order_deposit(db_empty, 999).exists is False)
check("немає застави → balance 0",
      service_on.get_order_deposit_balance(db_empty, 999).deposit_held == 0.0)
check("немає платежів → порожньо",
      len(service_on.list_order_payments(db_empty, 999)) == 0)

# ---------------------------------------------------------------- 4
print("\n4. Finance = OFF: контрольована деградація")
service_off = FinanceService(availability_check=lambda: False)
db_off = FakeSession(rows)

p_off = service_off.list_order_payments(db_off, 123)
check("payments порожні", len(p_off) == 0)
check("payments.available == False", p_off.available is False)
check("payments.status == disabled", p_off.status == STATUS_DISABLED)

l_off = service_off.get_pending_late_total(db_off, 123)
check("late.total == 0", l_off.total == 0.0)
check("late.status == disabled", l_off.status == STATUS_DISABLED)

d_off = service_off.get_order_deposit(db_off, 123)
check("deposit is None", d_off.deposit is None)
check("deposit.status == disabled", d_off.status == STATUS_DISABLED)

e_off = service_off.list_deposit_refund_events(db_off, 7)
check("events порожні + disabled",
      len(e_off) == 0 and e_off.status == STATUS_DISABLED)

b_off = service_off.get_order_deposit_balance(db_off, 123)
check("balance 0 + disabled",
      b_off.deposit_held == 0.0
      and b_off.deposit_to_refund == 0.0
      and b_off.status == STATUS_DISABLED)

check("при OFF жодного SQL не виконано", db_off.executed == [],
      f"виконано {len(db_off.executed)}")

# ---------------------------------------------------------------- 5
print("\n5. Фасад не змінює дані і не змінює схему")
all_sql = " ".join(db_on.executed).upper()
for forbidden in ("INSERT", "UPDATE", "DELETE", "ALTER", "CREATE", "DROP", "TRUNCATE"):
    check(f"немає {forbidden}", forbidden not in all_sql)
check("усі запити — SELECT",
      all(sql.strip().upper().startswith("SELECT") for sql in
          (s.strip() for s in db_on.executed)))

# ---------------------------------------------------------------- summary
print("\n" + "=" * 62)
if failures:
    print(f"РЕЗУЛЬТАТ: FAIL — {len(failures)} перевірок не пройшли")
    for item in failures:
        print(f"  - {item}")
    sys.exit(1)
print("РЕЗУЛЬТАТ: PASS — Documents не має прямого доступу до fin_*,")
print("           Finance ON віддає дані, Finance OFF деградує контрольовано")
print("=" * 62)