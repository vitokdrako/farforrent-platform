"""
Python-копія логіки розрахунку діб з utils/rentalDays.js (frontend).
Єдине джерело правди — використовується і клієнтом, і менеджером.

Правила Farfor Decor (повернення до 17:00):
  1 доба: Пн→Ср, Вт→Чт, Ср→Пт, Чт→Сб, Пт→Сб, Сб→Пн
  2 доби: Пн→Чт, Вт→Пт, Ср→Сб, Пт→Пн, Сб→Вт
"""
from datetime import date, datetime
from typing import Optional, Union

# pickup_dow → {return_dow: days_billed}
_RULES = {
    0: {2: 1, 3: 2},   # Mon: Wed=1, Thu=2
    1: {3: 1, 4: 2},   # Tue: Thu=1, Fri=2
    2: {4: 1, 5: 2},   # Wed: Fri=1, Sat=2
    3: {5: 1},         # Thu: Sat=1
    4: {5: 1, 0: 2},   # Fri: Sat=1, Mon=2
    5: {0: 1, 1: 2},   # Sat: Mon=1, Tue=2
}


def _coerce(d: Union[str, date, datetime, None]) -> Optional[date]:
    if d is None:
        return None
    if isinstance(d, datetime):
        return d.date()
    if isinstance(d, date):
        return d
    s = str(d).strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%d.%m.%Y"):
        try:
            return datetime.strptime(s[:len(fmt) if 'T' not in fmt else 19], fmt).date()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(s.replace("Z", "")).date()
    except (ValueError, TypeError):
        return None


def calculate_rental_days(pickup_date, return_date) -> int:
    """
    Повертає кількість оплачуваних діб згідно правил Farfor.
    Якщо комбінація нестандартна — calendar_days як fallback (мінімум 1).
    """
    p = _coerce(pickup_date)
    r = _coerce(return_date)
    if not p or not r:
        return 0
    if r < p:
        return 0
    calendar = (r - p).days
    # Python: Monday=0...Sunday=6. JS: Sunday=0...Saturday=6.
    # Мої правила в JS використовують JS-формат. Конвертую: Python.weekday() = (JS_dow - 1) mod 7
    # Простіше: переробити RULES для Python weekdays.
    # weekday(): Mon=0, Tue=1, Wed=2, Thu=3, Fri=4, Sat=5, Sun=6
    rule = _RULES.get(p.weekday())
    if rule and calendar <= 6:
        days = rule.get(r.weekday())
        if days is not None:
            return days
    return max(1, calendar)
