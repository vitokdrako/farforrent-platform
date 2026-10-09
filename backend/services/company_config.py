"""
Company Config - центральне місце для отримання даних компанії з БД.
Використовується в шаблонах документів (company.*, landlord.*).
"""
from sqlalchemy import text
from sqlalchemy.orm import Session

DEFAULTS = {
    "name": "Фізична особа-підприємець Николенко Наталя Станіславівна",
    "short_name": "FarforDecorOrenda",
    "tax_status": "платник єдиного податку",
    "tax_id": "3606801844",
    "iban": "UA043220010000026003340091618",
    "bank_name": "ПАТ \"УНІВЕРСАЛ БАНК\"",
    "address": "м. Київ",
    "signer_name": "Николенко Н.С.",
    "signer_role": "",
    "warehouse_address": "м. Київ, вул. Будіндустрії 4",
    "phone": "(097) 123 09 93, (093) 375 09 40",
    "email": "info@farforrent.com.ua",
    "website": "https://www.farforrent.com.ua",
}


def get_settings_from_db(db: Session) -> dict:
    """Fetch raw settings from system_settings table."""
    try:
        rows = db.execute(text("SELECT setting_key, setting_value FROM system_settings")).fetchall()
        if rows:
            return {r[0]: r[1] for r in rows}
    except Exception:
        pass
    return {}


def get_landlord_config(db: Session) -> dict:
    """Landlord dict for templates using landlord.* variables."""
    settings = get_settings_from_db(db)
    return {
        "name": settings.get("name", DEFAULTS["name"]),
        "tax_status": settings.get("tax_status", DEFAULTS["tax_status"]),
        "tax_id": settings.get("tax_id", DEFAULTS["tax_id"]),
        "iban": settings.get("iban", DEFAULTS["iban"]),
        "bank_name": settings.get("bank_name", DEFAULTS["bank_name"]),
        "address": settings.get("address", DEFAULTS["address"]),
        "signer_name": settings.get("signer_name", DEFAULTS["signer_name"]),
        "signer_role": settings.get("signer_role", DEFAULTS["signer_role"]),
        "warehouse_address": settings.get("warehouse_address", DEFAULTS["warehouse_address"]),
    }


def get_company_config(db: Session) -> dict:
    """Company dict for templates using company.* variables.
    
    Returns a unified dict compatible with all document templates:
    - company.name, company.legal_name, company.short_name
    - company.phone, company.email, company.website
    - company.address, company.warehouse
    - company.tax_id, company.edrpou, company.iban, company.bank_name
    - company.director_name, company.tax_status
    """
    settings = get_settings_from_db(db)
    legal_name = settings.get("name", DEFAULTS["name"])
    short_name = settings.get("short_name", DEFAULTS["short_name"])
    return {
        "name": short_name,
        "legal_name": legal_name,
        "short_name": short_name,
        "address": settings.get("address", DEFAULTS["address"]),
        "warehouse": settings.get("warehouse_address", DEFAULTS["warehouse_address"]),
        "phone": settings.get("phone", DEFAULTS["phone"]),
        "email": settings.get("email", DEFAULTS["email"]),
        "website": settings.get("website", DEFAULTS["website"]),
        "tax_id": settings.get("tax_id", DEFAULTS["tax_id"]),
        "edrpou": settings.get("tax_id", DEFAULTS["tax_id"]),
        "iban": settings.get("iban", DEFAULTS["iban"]),
        "bank_name": settings.get("bank_name", DEFAULTS["bank_name"]),
        "director_name": settings.get("signer_name", DEFAULTS["signer_name"]),
        "tax_status": settings.get("tax_status", DEFAULTS["tax_status"]),
        "signer_name": settings.get("signer_name", DEFAULTS["signer_name"]),
        "mfo": settings.get("mfo", "322001"),
    }
