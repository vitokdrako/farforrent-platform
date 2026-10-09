"""
FarforDecorOrenda Company Configuration
© FarforDecorOrenda 2025
Based on official documents from farforrent.com.ua
"""

COMPANY_INFO = {
    "name": "FarforDecorOrenda",
    "legal_name": "ФОП Николенко Наталя Станіславівна",
    "tax_id": "3606801844",
    "edrpou": "3606801844",
    "iban": "UA043220010000026003340091618",
    "mfo": "322001",
    "bank_name": "АТ «УНІВЕРСАЛ БАНК»",
    "address": "61082, Харківська обл., місто Харків, ПРОСПЕКТ МОСКОВСЬКИЙ, будинок 216/3А, квартира 46",
    "warehouse_address": "Військовий провулок 1",
    "email": "rfarfordecor@gmail.com.ua",
    "website": "https://www.farforrent.com.ua",
    "year": 2025,
}

WORKING_HOURS = {
    "order_processing": {"days": "пн–пт", "hours": "10:00–18:00"},
    "issue_return": {"days": "пн-сб", "hours": "10:00–17:00"},
    "after_hours_fee": 1500,  # грн
}

RENTAL_TERMS = {
    "min_order_amount": 2000,
    "discount_threshold": 30000,
    "discount_percent": 10,
    "urgent_order_surcharge": 30,  # %
    "late_return_fee": "daily_rate",
    "min_rental_period_days": 1,
    "deposit_rule": "50% від повної вартості можливого збитку",
}

PAYMENT_TERMS = {
    "advance_payment_percent": 50,
    "final_payment_percent": 50,
    "full_prepayment_allowed": True,
    "cancellation_policy_days": 2,
    "penalty_rate_daily": 0.5,  # %
}

DAMAGE_CATEGORIES = [
    {"code": "LOST", "name": "Втрата", "rule": "повна вартість"},
    {"code": "DAMAGED", "name": "Пошкодження", "rule": "вартість ремонту або повна вартість"},
    {"code": "DIRTY", "name": "Брудний/мокрий", "rule": "згідно з прайсом збитків"},
    {"code": "PACKAGING_LOST", "name": "Втрата пакування", "rule": "нараховуються збитки"},
    {"code": "LATE_RETURN", "name": "Прострочення повернення", "rule": "добова оренда"},
]

LEGAL_LINKS = {
    "terms": "https://www.farforrent.com.ua/terms",
    "privacy": "https://www.farforrent.com.ua/privacy",
    "offer": "https://www.farforrent.com.ua/oferta",
    "damage_rules": "https://www.farforrent.com.ua/opis-zbitkiv",
}

# Document templates config
DOCUMENT_FOOTER = f"© {COMPANY_INFO['name']} {COMPANY_INFO['year']}"
