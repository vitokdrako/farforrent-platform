"""
Data Builders - збирання даних для документів
RentalHub database compatible version
"""
from datetime import datetime
from sqlalchemy import text
from sqlalchemy.orm import Session
import json
import os
import base64
import mimetypes
from pathlib import Path
from services.company_config import get_company_config

# ============================================================
# ЗОБРАЖЕННЯ ТОВАРІВ — ЄДИНЕ ДЖЕРЕЛО ПРАВДИ
# ============================================================
# Шлях у БД: 'uploads/products/<file>'
# У документах потрібен або absolute URL, або base64 (для PDF/email).

_PRODUCTS_DIRS = [
    Path("/var/www/farforrent/backend/uploads/products"),
    Path("/home/farforre/farforrent.com.ua/rentalhub/backend/uploads/products"),
    Path(__file__).parent.parent.parent / "uploads" / "products",
]
_PRODUCTS_DIR = next((p for p in _PRODUCTS_DIRS if p.exists()), _PRODUCTS_DIRS[-1])
_BACKEND_PUBLIC_URL = os.environ.get('BACKEND_PUBLIC_URL', 'https://backrentalhub.farforrent.com.ua').rstrip('/')


def resolve_product_image(path: str) -> str:
    """
    Конвертує `products.image_url` у URL/base64 для документа.
    Пріоритет: локальний base64 → public URL → '' (порожньо).
    """
    if not path:
        return ""
    if path.startswith('data:') or path.startswith('http://') or path.startswith('https://'):
        return path
    rel = path.lstrip('/')
    if rel.startswith('uploads/products/'):
        filename = rel.split('/', 2)[2]
    elif '/' in rel:
        filename = rel.rsplit('/', 1)[-1]
    else:
        filename = rel
    local = _PRODUCTS_DIR / filename
    if local.exists() and local.is_file():
        try:
            mime, _ = mimetypes.guess_type(str(local))
            with open(local, 'rb') as f:
                data = base64.b64encode(f.read()).decode('utf-8')
            return f"data:{mime or 'image/jpeg'};base64,{data}"
        except Exception as e:
            print(f"[resolve_product_image] base64 fail {local}: {e}")
    return f"{_BACKEND_PUBLIC_URL}/uploads/products/{filename}"


def pick_product_image(product_image: str | None, legacy_image: str | None = None) -> str:
    """Єдине джерело правди: products.image_url, з фолбеком на legacy oi.image_url."""
    if product_image and product_image.strip():
        return resolve_product_image(product_image)
    if legacy_image and legacy_image.strip():
        # legacy OpenCart absolute URL
        return legacy_image if legacy_image.startswith('http') else resolve_product_image(legacy_image)
    return ""

# ============================================================
# КОНВЕРТАЦІЯ СУМИ В СЛОВА (УКРАЇНСЬКА)
# ============================================================

def number_to_words_ua(number):
    """Конвертує число в українські слова"""
    if number == 0:
        return "Нуль"
    
    units = ['', 'один', 'два', 'три', 'чотири', "п'ять", 'шість', 'сім', 'вісім', "дев'ять"]
    units_fem = ['', 'одна', 'дві', 'три', 'чотири', "п'ять", 'шість', 'сім', 'вісім', "дев'ять"]
    teens = ['десять', 'одинадцять', 'дванадцять', 'тринадцять', 'чотирнадцять', 
             "п'ятнадцять", 'шістнадцять', 'сімнадцять', 'вісімнадцять', "дев'ятнадцять"]
    tens = ['', '', 'двадцять', 'тридцять', 'сорок', "п'ятдесят", 
            'шістдесят', 'сімдесят', 'вісімдесят', "дев'яносто"]
    hundreds = ['', 'сто', 'двісті', 'триста', 'чотириста', "п'ятсот", 
                'шістсот', 'сімсот', 'вісімсот', "дев'ятсот"]
    
    def get_form(n, forms):
        """Вибір форми слова залежно від числа"""
        if 11 <= n % 100 <= 19:
            return forms[2]
        elif n % 10 == 1:
            return forms[0]
        elif 2 <= n % 10 <= 4:
            return forms[1]
        else:
            return forms[2]
    
    def convert_group(n, feminine=False):
        """Конвертує групу з трьох цифр"""
        result = []
        u = units_fem if feminine else units
        
        if n >= 100:
            result.append(hundreds[n // 100])
            n %= 100
        
        if 10 <= n <= 19:
            result.append(teens[n - 10])
        else:
            if n >= 20:
                result.append(tens[n // 10])
                n %= 10
            if n > 0:
                result.append(u[n])
        
        return ' '.join(filter(None, result))
    
    num = int(number)
    if num == 0:
        return "Нуль"
    
    parts = []
    
    # Мільйони
    millions = num // 1000000
    if millions > 0:
        parts.append(convert_group(millions))
        parts.append(get_form(millions, ['мільйон', 'мільйони', 'мільйонів']))
        num %= 1000000
    
    # Тисячі (feminine)
    thousands = num // 1000
    if thousands > 0:
        parts.append(convert_group(thousands, feminine=True))
        parts.append(get_form(thousands, ['тисяча', 'тисячі', 'тисяч']))
        num %= 1000
    
    # Одиниці
    if num > 0:
        parts.append(convert_group(num, feminine=True))
    
    result = ' '.join(filter(None, parts))
    return result.capitalize() if result else "Нуль"

def build_document_data(db: Session, doc_type: str, entity_id: str, options: dict = None) -> dict:
    """
    Збирає всі дані для генерації документа.
    Повертає словник з даними для шаблону.
    """
    options = options or {}
    
    # Order-based documents
    order_docs = [
        "invoice_offer", "contract_rent", "deposit_settlement_act", 
        "invoice_additional", "return_intake_checklist", "delivery_note", 
        "rental_extension", "partial_return_act", "damage_settlement_act",
        "deposit_refund_act",
        # Документи для юр. осіб
        "invoice_legal", "service_act", "goods_invoice"
    ]
    
    # Return act - окремо, бо читає з return_cards
    return_docs = ["return_act"]
    
    # Issue card based documents
    issue_docs = ["issue_act", "picking_list", "issue_checklist"]
    
    # Damage case based documents
    damage_docs = ["damage_report", "damage_report_client", "damage_invoice"]
    
    # Damage settlement - special handling for order-based damage
    damage_settlement_docs = ["damage_settlement_act"]
    
    # Vendor task based documents
    vendor_docs = ["vendor_work_act"]
    
    # Order modification documents
    modification_docs = ["order_modification"]
    
    # Defect act - uses damage settlement data builder
    defect_docs = ["defect_act"]
    
    if doc_type in return_docs:
        return build_return_data(db, entity_id, options)
    elif doc_type in defect_docs:
        return build_defect_act_data(db, entity_id, options)
    elif doc_type in damage_settlement_docs:
        return build_damage_settlement_data(db, entity_id, options)
    elif doc_type in modification_docs:
        return build_order_modification_data(db, entity_id, options)
    elif doc_type in order_docs:
        return build_order_data(db, entity_id, options)
    elif doc_type in issue_docs:
        return build_issue_card_data(db, entity_id, options)
    elif doc_type in damage_docs:
        return build_damage_data(db, entity_id, options)
    elif doc_type in vendor_docs:
        return build_vendor_task_data(db, entity_id, options)
    else:
        raise ValueError(f"No data builder for doc_type: {doc_type}")

def build_order_data(db: Session, order_id: str, options: dict) -> dict:
    """Збирає дані замовлення для документа (RentalHub schema)"""
    
    # Основні дані замовлення + payer_profile_id
    result = db.execute(text("""
        SELECT 
            o.order_id, o.order_number, o.status,
            o.customer_name, o.customer_phone, o.customer_email,
            o.rental_start_date, o.rental_end_date, o.rental_days,
            o.total_price, o.deposit_amount, o.discount_amount,
            o.delivery_type, o.delivery_address, o.notes,
            o.created_at, o.phone
        FROM orders o
        WHERE o.order_id = :order_id
    """), {"order_id": order_id})
    
    order_row = result.fetchone()
    if not order_row:
        raise ValueError(f"Order not found: {order_id}")
    
    # Use customer_phone or phone fallback
    phone = order_row[4] or order_row[16] or ""
    
    order = {
        "id": order_row[0],
        "order_number": order_row[1] or f"OC-{order_row[0]}",
        "status": order_row[2],
        "customer_name": order_row[3] or "",
        "customer_phone": phone,
        "customer_email": order_row[5] or "",
        "rental_start_date": order_row[6].strftime("%d.%m.%Y") if order_row[6] else "",
        "rental_end_date": order_row[7].strftime("%d.%m.%Y") if order_row[7] else "",
        "rental_days": order_row[8] or 1,
        "total_price": float(order_row[9] or 0),
        "deposit_amount": float(order_row[10] or 0),
        "discount_amount": float(order_row[11] or 0),
        "delivery_type": order_row[12] or "pickup",
        "delivery_address": order_row[13] or "",
        "notes": order_row[14] or "",
        "created_at": order_row[15].strftime("%d.%m.%Y %H:%M") if order_row[15] else ""
    }
    
    # Позиції замовлення (RentalHub schema) — єдине джерело фото: products.image_url
    items_result = db.execute(text("""
        SELECT 
            oi.product_name, oi.product_id, oi.quantity, 
            oi.price, oi.total_rental, oi.image_url,
            p.sku, p.zone, p.aisle, p.shelf, p.price as damage_price,
            p.image_url AS product_image
        FROM order_items oi
        LEFT JOIN products p ON p.product_id = oi.product_id
        WHERE oi.order_id = :order_id
    """), {"order_id": order["id"]})
    
    items = []
    total_rent = 0
    total_deposit = 0
    
    for row in items_result:
        qty = int(row[2] or 1)
        price_per_day = float(row[3] or 0)
        total_rental = float(row[4] or 0) or (price_per_day * qty * order["rental_days"])
        # Застава = 50% від повного збитку (damage_price)
        damage_price = float(row[10] or 0) if row[10] else 0
        full_damage_cost = damage_price if damage_price else price_per_day * 6  # fallback: 6 днів оренди
        deposit_per_item = full_damage_cost / 2  # Застава = 50% від повного збитку
        
        item_deposit = deposit_per_item * qty
        
        # Build location
        location = None
        if row[7] or row[8] or row[9]:
            location = "-".join(filter(None, [row[7], row[8], row[9]]))
        
        items.append({
            "name": row[0] or "",
            "sku": row[6] or f"P-{row[1]}" if row[1] else "",
            "quantity": qty,
            "price_per_day": price_per_day,
            "deposit_per_item": deposit_per_item,
            "total_rent": total_rental,
            "total_deposit": item_deposit,
            "image_url": pick_product_image(row[11] if len(row) > 11 else None, row[5]),
            "location": location
        })
        
        total_rent += total_rental
        total_deposit += item_deposit
    
    # Use calculated totals or order totals
    if not total_rent:
        total_rent = order["total_price"]
    if not total_deposit:
        total_deposit = order["deposit_amount"]
    
    # === ФІНАНСОВІ ДАНІ (платежі, шкода, застава) ===
    # Конвертуємо order_id в int для коректного порівняння
    order_id_int = int(order_id) if order_id else 0
    
    # Платежі по ордеру (status може бути 'completed' або 'confirmed')
    payments_result = db.execute(text("""
        SELECT payment_type, method, amount, note, occurred_at
        FROM fin_payments
        WHERE order_id = :order_id AND status IN ('completed', 'confirmed')
        ORDER BY occurred_at
    """), {"order_id": order_id_int})
    
    payments = []
    rent_paid = 0
    damage_paid = 0
    additional_paid = 0
    
    for p in payments_result:
        payments.append({
            "type": p[0],
            "method": p[1],
            "amount": float(p[2] or 0),
            "note": p[3] or "",
            "date": p[4].strftime("%d.%m.%Y") if p[4] else ""
        })
        if p[0] == "rent":
            rent_paid += float(p[2] or 0)
        elif p[0] == "damage":
            damage_paid += float(p[2] or 0)
        elif p[0] == "additional":
            additional_paid += float(p[2] or 0)
    
    # Шкода по ордеру
    damage_result = db.execute(text("""
        SELECT SUM(fee) as total_fee
        FROM product_damage_history
        WHERE order_id = :order_id
    """), {"order_id": order_id_int})
    damage_row = damage_result.fetchone()
    total_damage = float(damage_row[0]) if damage_row and damage_row[0] else 0
    
    # Застава
    deposit_result = db.execute(text("""
        SELECT held_amount, used_amount, refunded_amount, actual_amount, currency, exchange_rate
        FROM fin_deposit_holds
        WHERE order_id = :order_id
        LIMIT 1
    """), {"order_id": order_id_int})
    deposit_row = deposit_result.fetchone()
    
    deposit_data = None
    if deposit_row:
        deposit_data = {
            "held": float(deposit_row[0] or 0),
            "used": float(deposit_row[1] or 0),
            "refunded": float(deposit_row[2] or 0),
            "actual_amount": float(deposit_row[3] or 0),
            "currency": deposit_row[4] or "UAH",
            "exchange_rate": float(deposit_row[5] or 1),
            "available": float(deposit_row[0] or 0) - float(deposit_row[1] or 0) - float(deposit_row[2] or 0)
        }
    
    # Компанія - вибір на основі executor_type з options
    from services.pdf_generator import EXECUTORS
    
    executor_type = options.get("executor_type", "fop")
    executor = EXECUTORS.get(executor_type, EXECUTORS["fop"])
    
    company = get_company_config(db)

    # === COMPANY PROFILE OVERRIDE ===
    # Перевага: snapshot з orders.company_snapshot_json → live company_profiles → defaults
    try:
        cp_row = db.execute(text("""
            SELECT company_profile_id, company_snapshot_json FROM orders WHERE order_id = :oid
        """), {"oid": order_id_int}).fetchone()
        cp_data = None
        if cp_row and cp_row[1]:
            try:
                cp_data = json.loads(cp_row[1]) if isinstance(cp_row[1], str) else cp_row[1]
            except Exception:
                cp_data = None
        if not cp_data and cp_row and cp_row[0]:
            live = db.execute(text("""
                SELECT display_name, legal_name, payer_type, tax_status, edrpou, iban, bank_name,
                       address, warehouse_address, director_name, signer_name, signer_role,
                       is_vat_payer, phone, email, website, logo_url, stamp_url
                FROM company_profiles WHERE id = :id
            """), {"id": cp_row[0]}).fetchone()
            if live:
                cp_data = {
                    "display_name": live[0], "legal_name": live[1], "payer_type": live[2],
                    "tax_status": live[3], "edrpou": live[4], "iban": live[5], "bank_name": live[6],
                    "address": live[7], "warehouse_address": live[8], "director_name": live[9],
                    "signer_name": live[10], "signer_role": live[11], "is_vat_payer": bool(live[12]),
                    "phone": live[13], "email": live[14], "website": live[15],
                    "logo_url": live[16], "stamp_url": live[17],
                }
        if cp_data:
            company.update({
                "name": cp_data.get("display_name") or company.get("name"),
                "legal_name": cp_data.get("legal_name") or company.get("legal_name"),
                "short_name": cp_data.get("display_name") or company.get("short_name"),
                "tax_status": cp_data.get("tax_status") or company.get("tax_status"),
                "tax_id": cp_data.get("edrpou") or company.get("tax_id"),
                "edrpou": cp_data.get("edrpou") or company.get("edrpou"),
                "iban": cp_data.get("iban") or company.get("iban"),
                "bank_name": cp_data.get("bank_name") or company.get("bank_name"),
                "address": cp_data.get("address") or company.get("address"),
                "warehouse": cp_data.get("warehouse_address") or company.get("warehouse"),
                "director_name": cp_data.get("director_name") or company.get("director_name"),
                "signer_name": cp_data.get("signer_name") or company.get("signer_name"),
                "phone": cp_data.get("phone") or company.get("phone"),
                "email": cp_data.get("email") or company.get("email"),
                "website": cp_data.get("website") or company.get("website"),
                "logo_url": cp_data.get("logo_url"),
                "stamp_url": cp_data.get("stamp_url"),
            })
    except Exception as e:
        print(f"[company_profile] override skipped: {e}")

    # Merge executor-specific data
    company.update({
        "tax_id": company.get("tax_id") or executor.get("edrpou"),
        "edrpou": company.get("edrpou") or executor.get("edrpou"),
        "iban": company.get("iban") or executor.get("iban"),
        "mfo": executor.get("mfo", ""),
        "bank_name": company.get("bank_name") or executor.get("bank"),
        "director_name": company.get("director_name") or executor.get("director"),
        "tax_status": company.get("tax_status") or executor.get("tax_status"),
        # Правові документи
        "terms_url": "https://www.farforrent.com.ua/terms",
        "privacy_url": "https://www.farforrent.com.ua/privacy",
        "offer_url": "https://www.farforrent.com.ua/oferta",
        "damage_url": "https://www.farforrent.com.ua/opis-zbitk%D1%96v",
        # Умови оренди
        "min_order": 2000,
        "discount_threshold": 30000,
        "discount_percent": 10,
        "deposit_rule": "50% від повної вартості можливого збитку",
        "prepayment_percent": 50,
        "cancellation_days": 2,
        "penalty_daily_percent": 0.5,
        # Робочі години
        "working_hours": "пн-пт 10:00-18:00",
        "issue_hours": "пн-сб 10:00-17:00",
    })
    
    # === ДАНІ ПЛАТНИКА (PAYER PROFILE) ===
    payer = {
        "payer_type": "individual",
        "company_name": order["customer_name"],
        "director_name": order["customer_name"],
        "edrpou": None,
        "iban": None,
        "bank_name": None,
        "address": None,
        "is_vat_payer": False
    }
    
    # Спробуємо отримати профіль платника якщо вказано в options або прив'язано до замовлення
    payer_profile_id = options.get("payer_profile_id")
    if not payer_profile_id:
        # Перевіримо чи є payer_profile_id в замовленні
        try:
            # Спочатку перевіримо чи існує колонка
            check_col = db.execute(text("""
                SELECT COUNT(*) FROM information_schema.COLUMNS 
                WHERE TABLE_NAME = 'orders' AND COLUMN_NAME = 'payer_profile_id'
            """))
            if check_col.fetchone()[0] > 0:
                payer_result = db.execute(text("""
                    SELECT payer_profile_id FROM orders WHERE order_id = :order_id
                """), {"order_id": order_id_int})
                payer_row = payer_result.fetchone()
                if payer_row and payer_row[0]:
                    payer_profile_id = payer_row[0]
        except Exception as e:
            print(f"Warning: Could not check payer_profile_id: {e}")
    
    if payer_profile_id:
        try:
            profile_result = db.execute(text("""
                SELECT payer_type, company_name, edrpou, iban, bank_name, 
                       director_name, address, tax_number, is_vat_payer
                FROM payer_profiles WHERE id = :id
            """), {"id": payer_profile_id})
            profile_row = profile_result.fetchone()
            if profile_row:
                payer = {
                    "payer_type": profile_row[0] or "individual",
                    "company_name": profile_row[1] or order["customer_name"],
                    "edrpou": profile_row[2],
                    "iban": profile_row[3],
                    "bank_name": profile_row[4],
                    "director_name": profile_row[5] or order["customer_name"],
                    "address": profile_row[6],
                    "tax_number": profile_row[7],
                    "is_vat_payer": bool(profile_row[8])
                }
        except Exception as e:
            print(f"Warning: Could not load payer profile {payer_profile_id}: {e}")
    
    # Визначення типу товару/послуги на основі типу платника
    # Якщо payer_type прийшов через options — використовуємо його (пріоритет)
    if options.get("payer_type"):
        payer["payer_type"] = options["payer_type"]
    
    payer_type = payer.get("payer_type", "individual")
    if payer_type in ["fop_simple", "llc_simple"]:
        item_type = "service"  # Послуга "Прокат декору"
    elif payer_type in ["fop_general", "llc_general"]:
        item_type = "goods"  # Товар "Декор"
    else:
        item_type = "service"  # За замовчуванням для фіз. осіб
    
    # Розрахунок балансу
    rent_due = max(0, total_rent - rent_paid)
    damage_due = max(0, total_damage - damage_paid)
    deposit_available = deposit_data["available"] if deposit_data else 0
    deposit_to_refund = max(0, deposit_available - damage_due) if deposit_data else 0
    
    return {
        "order": order,
        "items": items,
        "totals": {
            "rent": total_rent,
            "deposit": total_deposit,
            "discount": order["discount_amount"],
            "grand_total": total_rent + total_deposit - order["discount_amount"]
        },
        "finance": {
            "rent_paid": rent_paid,
            "rent_due": rent_due,
            "damage_total": total_damage,
            "damage_paid": damage_paid,
            "damage_due": damage_due,
            "additional_paid": additional_paid,
            "deposit_held": deposit_data["held"] if deposit_data else 0,
            "deposit_used": deposit_data["used"] if deposit_data else 0,
            "deposit_refunded": deposit_data["refunded"] if deposit_data else 0,
            "deposit_available": deposit_available,
            "deposit_to_refund": deposit_to_refund,
            "deposit_currency": deposit_data["currency"] if deposit_data else "UAH",
            "deposit_actual": deposit_data["actual_amount"] if deposit_data else 0,
        },
        "payments": payments,
        "deposit_data": deposit_data,
        "company": company,
        "payer": payer,
        "item_type": item_type,
        "total_words": number_to_words_ua(total_rent),
        "generated_at": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "options": options
    }


def build_damage_settlement_data(db: Session, order_id: str, options: dict) -> dict:
    """
    Збирає дані для Акту утримання із застави з реальними даними шкоди.
    Підтягує product_damage_history для цього ордера.
    """
    
    # Основні дані замовлення
    result = db.execute(text("""
        SELECT 
            order_id, order_number, status, customer_name, customer_phone,
            total_price, deposit_amount, rental_start_date, rental_end_date,
            damage_fee
        FROM orders
        WHERE order_id = :order_id
    """), {"order_id": order_id})
    
    order_row = result.fetchone()
    if not order_row:
        raise ValueError(f"Order not found: {order_id}")
    
    order = {
        "id": order_row[0],
        "order_number": order_row[1] or f"OC-{order_row[0]}",
        "status": order_row[2],
        "customer_name": order_row[3] or "",
        "customer_phone": order_row[4] or "",
        "total_price": float(order_row[5] or 0),
        "deposit_amount": float(order_row[6] or 0),
        "rental_start_date": order_row[7].strftime("%d.%m.%Y") if order_row[7] else "",
        "rental_end_date": order_row[8].strftime("%d.%m.%Y") if order_row[8] else "",
        "damage_fee": float(order_row[9] or 0),
    }
    
    # Отримуємо дані про шкоду з product_damage_history
    damage_result = db.execute(text("""
        SELECT 
            pdh.id, pdh.product_name, pdh.sku, pdh.damage_type, pdh.severity,
            pdh.fee, pdh.note, pdh.processing_type, pdh.processing_status,
            pdh.qty, pdh.fee_per_item,
            DATE_FORMAT(pdh.created_at, '%d.%m.%Y') as damage_date
        FROM product_damage_history pdh
        WHERE pdh.order_id = :order_id
        ORDER BY pdh.created_at DESC
    """), {"order_id": order_id})
    
    damage_items = []
    total_damage_fee = 0
    total_laundry_fee = 0
    
    damage_type_names = {
        "broken": "Зламано",
        "scratched": "Подряпано", 
        "stained": "Плями",
        "chipped": "Відколото",
        "cracked": "Тріщина",
        "missing": "Відсутнє",
        "dirty": "Забруднено",
        "other": "Інше"
    }
    
    severity_names = {
        "low": "Незначна",
        "medium": "Середня",
        "high": "Значна",
        "critical": "Критична"
    }
    
    for row in damage_result:
        fee = float(row[5] or 0)
        qty = int(row[9] or 1)
        fee_per_item = float(row[10] or 0) if row[10] else (fee / qty if qty else fee)
        processing_type = row[7] or "none"
        
        if processing_type == "laundry":
            total_laundry_fee += fee
        else:
            total_damage_fee += fee
        
        damage_items.append({
            "id": row[0],
            "product_name": row[1] or "",
            "sku": row[2] or "",
            "damage_type": damage_type_names.get(row[3], row[3] or ""),
            "damage_type_code": row[3] or "",
            "severity": severity_names.get(row[4], row[4] or ""),
            "severity_code": row[4] or "",
            "fee": fee,
            "fee_per_item": fee_per_item,
            "qty": qty,
            "note": row[6] or "",
            "processing_type": row[7] or "",
            "processing_status": row[8] or "",
            "damage_date": row[11] or ""
        })
    
    # Розрахунки
    deposit = order["deposit_amount"]
    damage_amount = total_damage_fee
    cleaning_fee = total_laundry_fee
    
    # Прострочення (якщо є в options)
    late_days = options.get("late_days", 0)
    late_fee = options.get("late_fee", 0)
    
    total_deduction = damage_amount + cleaning_fee + late_fee
    refund_amount = max(0, deposit - total_deduction)
    
    company = get_company_config(db)
    
    return {
        "order": order,
        "damage_items": damage_items,
        "totals": {
            "deposit": deposit,
            "damage_count": len(damage_items),
        },
        "deductions": {
            "damage_amount": damage_amount,
            "cleaning_fee": cleaning_fee,
            "late_days": late_days,
            "late_fee": late_fee,
            "total_deduction": total_deduction,
            "refund_amount": refund_amount,
        },
        "company": company,
        "generated_at": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "options": options
    }



def build_defect_act_data(db: Session, order_id: str, options: dict) -> dict:
    """
    Збирає дані для Дефектного акту.
    Шаблон defect_act.html очікує: meta, landlord, tenant, agreement, order, damage.
    """
    result = db.execute(text("""
        SELECT order_id, order_number, status, customer_name, customer_phone,
               total_price, deposit_amount, rental_start_date, rental_end_date,
               damage_fee
        FROM orders WHERE order_id = :order_id
    """), {"order_id": order_id})
    
    order_row = result.fetchone()
    if not order_row:
        raise ValueError(f"Order not found: {order_id}")
    
    # Get master agreement number if exists
    agreement_number = ""
    try:
        agr = db.execute(text("SELECT agreement_number FROM master_agreements WHERE client_name = :name ORDER BY id DESC LIMIT 1"), {"name": order_row[3]}).fetchone()
        if agr:
            agreement_number = agr[0] or ""
    except:
        pass
    
    # Get damage items (ALL types: state write, photo_only, written_off)
    damage_result = db.execute(text("""
        SELECT pdh.product_name, pdh.sku, pdh.damage_type, pdh.severity,
               pdh.fee, pdh.note, pdh.qty, pdh.fee_per_item,
               pdh.photo_url, pdh.processing_type, pdh.damage_code, pdh.stage
        FROM product_damage_history pdh
        WHERE pdh.order_id = :order_id
        ORDER BY pdh.created_at
    """), {"order_id": order_id})
    
    damage_type_names = {
        "broken": "Зламано", "scratched": "Подряпано", "stained": "Плями",
        "chipped": "Відколото", "cracked": "Тріщина", "missing": "Відсутнє",
        "dirty": "Забруднено", "other": "Інше"
    }
    
    damage_rows = []
    total_fee = 0
    for row in damage_result:
        fee = float(row[4] or 0)
        total_fee += fee
        proc_type = row[9] or ""
        damage_code = row[10] or ""
        stage = row[11] or ""
        is_photo_only = proc_type == 'photo_only'
        is_total_loss = damage_code == 'TOTAL_LOSS' or proc_type == 'written_off'
        
        if is_photo_only:
            label = "Фіксація (без запису у стан)"
        elif is_total_loss:
            label = "Повна втрата"
        elif stage == 'pre_issue':
            label = "До видачі"
        else:
            label = "В стан декору"
        
        damage_rows.append({
            "name": row[0] or "",
            "sku": row[1] or "",
            "description": f"{damage_type_names.get(row[2], row[2] or '')}. {row[5] or ''}".strip(". "),
            "amount": fee,
            "fee": fee,
            "qty": int(row[6] or 1),
            "photo_url": row[8] or "",
            "processing_type": proc_type,
            "is_photo_only": is_photo_only,
            "is_total_loss": is_total_loss,
            "label": label,
            "stage": stage,
        })
    
    # Get late fees
    late_result = db.execute(text("""
        SELECT amount, status, note FROM fin_payments 
        WHERE order_id = :order_id AND payment_type = 'late'
        ORDER BY occurred_at
    """), {"order_id": order_id})
    
    late_rows = []
    late_total = 0
    for row in late_result:
        amt = float(row[0] or 0)
        late_total += amt
        late_rows.append({
            "note": row[2] or "Прострочення повернення",
            "amount": amt,
            "status": row[1],
        })
    
    now = datetime.now()
    months_ua = ["січня","лютого","березня","квітня","травня","червня",
                 "липня","серпня","вересня","жовтня","листопада","грудня"]
    
    company = get_company_config(db)
    
    return {
        "meta": {
            "act_day": now.strftime("%d"),
            "act_month": months_ua[now.month - 1],
            "act_year": now.strftime("%Y"),
        },
        "landlord": {
            "name": company["short_name"],
            "legal_name": company["legal_name"],
        },
        "tenant": {
            "legal_name": order_row[3] or "",
            "signer_name": order_row[3] or "",
            "signer_role": "",
        },
        "agreement": {
            "contract_number": agreement_number,
        },
        "order": {
            "order_number": order_row[1] or f"OC-{order_row[0]}",
        },
        "damage": {
            "rows": damage_rows,
            "total": total_fee,
        },
        "late": {
            "rows": late_rows,
            "total": late_total,
        },
        "grand_total": total_fee + late_total,
        "generated_at": now.strftime("%d.%m.%Y %H:%M"),
    }



def build_issue_card_data(db: Session, issue_card_id: str, options: dict) -> dict:
    """Збирає дані картки видачі для документа (RentalHub schema)"""
    
    # Helper функція для формування URL фото
    import os
    import base64
    from pathlib import Path
    
    BACKEND_URL = os.environ.get('BACKEND_PUBLIC_URL', 'https://backrentalhub.farforrent.com.ua')
    PROD_UPLOADS = Path("/home/farforre/farforrent.com.ua/rentalhub/backend/uploads/damage_photos")
    LOCAL_UPLOADS = Path(__file__).parent.parent.parent / "uploads" / "damage_photos"
    UPLOADS_DIR = PROD_UPLOADS if PROD_UPLOADS.exists() else LOCAL_UPLOADS
    
    def get_photo_url_for_doc(photo_path: str) -> str:
        """Формує URL/base64 для фото в документі"""
        if not photo_path:
            return None
        if photo_path.startswith('http') or photo_path.startswith('data:'):
            return photo_path
        
        filename = photo_path.split('/')[-1] if '/' in photo_path else photo_path
        local_path = UPLOADS_DIR / filename
        
        if local_path.exists():
            try:
                import mimetypes
                mime_type, _ = mimetypes.guess_type(str(local_path))
                if not mime_type:
                    mime_type = 'image/jpeg'
                with open(local_path, 'rb') as f:
                    data = base64.b64encode(f.read()).decode('utf-8')
                return f"data:{mime_type};base64,{data}"
            except Exception as e:
                print(f"Warning: Could not read {local_path}: {e}")
        
        return f"{BACKEND_URL}/api/uploads/damage_photos/{filename}"
    
    result = db.execute(text("""
        SELECT 
            ic.id, ic.order_id, ic.order_number, ic.status,
            ic.items, ic.prepared_at, ic.issued_at,
            o.customer_name, o.customer_phone, o.phone,
            o.rental_start_date, o.rental_end_date, o.rental_days,
            o.delivery_type, o.delivery_address, o.notes,
            ic.requisitors, ic.preparation_notes
        FROM issue_cards ic
        JOIN orders o ON o.order_id = ic.order_id
        WHERE ic.id = :id
    """), {"id": issue_card_id})
    
    row = result.fetchone()
    if not row:
        raise ValueError(f"Issue card not found: {issue_card_id}")
    
    order_id = row[1]
    
    # ЗАВЖДИ беремо items з order_items для актуальних product_id
    items = []
    if order_id:
        items_result = db.execute(text("""
            SELECT 
                oi.product_name as name, oi.product_id, oi.quantity,
                p.sku, p.zone, p.aisle, p.shelf, p.image_url
            FROM order_items oi
            LEFT JOIN products p ON p.product_id = oi.product_id
            WHERE oi.order_id = :order_id AND (oi.status = 'active' OR oi.status IS NULL)
        """), {"order_id": order_id})
        
        for item_row in items_result:
            location_parts = [item_row[4], item_row[5], item_row[6]]
            location = "-".join(filter(None, [str(x) for x in location_parts if x])) if any(location_parts) else "N/A"
            items.append({
                "name": item_row[0] or "",
                "product_id": item_row[1],
                "quantity": item_row[2] or 1,
                "sku": item_row[3] or "",
                "location": location,
                "image_url": pick_product_image(item_row[7])
            })
    
    # Use customer_phone or phone fallback
    phone = row[8] or row[9] or ""
    
    # Parse requisitors (row[16])
    requisitors_json = row[16] if len(row) > 16 else None
    requisitors = []
    if requisitors_json:
        try:
            requisitors = json.loads(requisitors_json) if isinstance(requisitors_json, str) else requisitors_json
        except:
            requisitors = []
    
    # Preparation notes (row[17])
    preparation_notes = row[17] if len(row) > 17 else ""
    
    # Load pre_damage (шкода зафіксована при видачі) for each item
    # AND full damage_history (всі пошкодження товару з будь-яких замовлень)
    for item in items:
        product_id = item.get('product_id') or item.get('inventory_id')
        sku = item.get('sku')
        
        # Pre-damage for THIS order
        if product_id and order_id:
            try:
                damage_result = db.execute(text("""
                    SELECT damage_type, note, severity, photo_url, created_by,
                           DATE_FORMAT(created_at, '%d.%m.%Y %H:%i') as created_at
                    FROM product_damage_history
                    WHERE order_id = :order_id 
                    AND product_id = :product_id 
                    AND stage = 'pre_issue'
                    ORDER BY created_at
                """), {"order_id": order_id, "product_id": product_id})
                
                pre_damage = []
                for d_row in damage_result:
                    pre_damage.append({
                        "damage_type": d_row[0],
                        "type": d_row[0],  # alias for template
                        "note": d_row[1] or "",
                        "severity": d_row[2] or "low",
                        "photo_url": d_row[3],
                        "created_by": d_row[4],
                        "created_at": d_row[5]
                    })
                
                if pre_damage:
                    item['pre_damage'] = pre_damage
                    item['has_pre_damage'] = True
                else:
                    item['pre_damage'] = []
                    item['has_pre_damage'] = False
            except Exception as e:
                print(f"Warning: Could not load pre_damage for product {product_id}: {e}")
                item['pre_damage'] = []
                item['has_pre_damage'] = False
        
        # Full damage_history (ALL damages for this product from any order)
        try:
            if product_id:
                history_result = db.execute(text("""
                    SELECT id, damage_type, note, severity, photo_url, created_by,
                           DATE_FORMAT(created_at, '%d.%m.%Y %H:%i') as created_at,
                           order_number, stage, fee
                    FROM product_damage_history
                    WHERE product_id = :product_id
                    ORDER BY created_at DESC
                    LIMIT 20
                """), {"product_id": product_id})
            elif sku:
                history_result = db.execute(text("""
                    SELECT id, damage_type, note, severity, photo_url, created_by,
                           DATE_FORMAT(created_at, '%d.%m.%Y %H:%i') as created_at,
                           order_number, stage, fee
                    FROM product_damage_history
                    WHERE sku = :sku
                    ORDER BY created_at DESC
                    LIMIT 20
                """), {"sku": sku})
            else:
                history_result = None
            
            damage_history = []
            if history_result:
                for h_row in history_result:
                    # Конвертуємо photo_url для документа
                    photo_url = get_photo_url_for_doc(h_row[4])
                    
                    damage_history.append({
                        "id": h_row[0],
                        "damage_type": h_row[1],
                        "type": h_row[1],
                        "note": h_row[2] or "",
                        "severity": h_row[3] or "low",
                        "photo_url": photo_url,
                        "created_by": h_row[5],
                        "created_at": h_row[6],
                        "order_number": h_row[7],
                        "stage": h_row[8],
                        "stage_label": "До видачі" if h_row[8] == "pre_issue" else "При поверненні" if h_row[8] == "return" else "Аудит",
                        "fee": float(h_row[9]) if h_row[9] else 0.0
                    })
            
            if damage_history:
                item['damage_history'] = damage_history
                item['has_damage_history'] = True
                item['total_damages'] = len(damage_history)
            else:
                item['damage_history'] = []
                item['has_damage_history'] = False
                item['total_damages'] = 0
        except Exception as e:
            print(f"Warning: Could not load damage_history for product {product_id or sku}: {e}")
            item['damage_history'] = []
            item['has_damage_history'] = False
            item['total_damages'] = 0
    
    issue_card = {
        "id": row[0],
        "order_id": row[1],
        "order_number": row[2] or f"OC-{row[1]}",
        "status": row[3],
        "customer_name": row[7] or "",
        "customer_phone": phone,
        "prepared_at": row[5].strftime("%d.%m.%Y %H:%M") if row[5] else "",
        "issued_at": row[6].strftime("%d.%m.%Y %H:%M") if row[6] else "",
        "rental_start_date": row[10].strftime("%d.%m.%Y") if row[10] else "",
        "rental_end_date": row[11].strftime("%d.%m.%Y") if row[11] else "",
        "rental_days": row[12] or 1,
        "delivery_type": row[13] or "pickup",
        "delivery_address": row[14] or "",
        "notes": row[15] or "",
        "preparation_notes": preparation_notes or ""
    }
    
    company = get_company_config(db)
    
    return {
        "issue_card": issue_card,
        "items": items,
        "requisitors": requisitors,
        "company": company,
        "generated_at": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "options": options
    }

def build_return_data(db: Session, order_id: str, options: dict) -> dict:
    """Збирає повні дані повернення для Акту приймання-повернення"""
    
    company = get_company_config(db)
    
    # --- Order data ---
    order_row = db.execute(text("""
        SELECT order_id, order_number, status, customer_name, customer_phone,
               customer_email, rental_start_date, rental_end_date, rental_days,
               total_price, deposit_amount, discount_amount,
               payer_profile_id, deal_mode
        FROM orders WHERE order_id = :order_id
    """), {"order_id": order_id}).fetchone()
    
    if not order_row:
        raise ValueError(f"Order not found: {order_id}")
    
    months_ua = ["січня","лютого","березня","квітня","травня","червня",
                 "липня","серпня","вересня","жовтня","листопада","грудня"]
    now = datetime.now()
    
    order = {
        "order_id": order_row[0],
        "order_number": order_row[1] or f"OC-{order_row[0]}",
        "status": order_row[2],
        "customer_name": order_row[3] or "",
        "customer_phone": order_row[4] or "",
        "customer_email": order_row[5] or "",
        "rental_start_date": order_row[6].strftime("%d.%m.%Y") if order_row[6] else "",
        "rental_end_date": order_row[7].strftime("%d.%m.%Y") if order_row[7] else "",
        "rental_days": order_row[8] or 1,
        "number": order_row[1] or f"OC-{order_row[0]}",
    }
    
    rent_total = float(order_row[9] or 0)
    deposit_security = float(order_row[10] or 0)
    
    # --- Payer / tenant info ---
    tenant = {"legal_name": order_row[3] or "", "signer_name": order_row[3] or ""}
    agreement = {"contract_number": ""}
    payer_profile_id = order_row[12]
    if payer_profile_id:
        payer_row = db.execute(text("""
            SELECT company_name, payer_type, director_name, edrpou, phone, email
            FROM payer_profiles WHERE id = :pid
        """), {"pid": payer_profile_id}).fetchone()
        if payer_row:
            tenant["legal_name"] = payer_row[0] or order_row[3] or ""
            tenant["signer_name"] = payer_row[2] or order_row[3] or ""
            tenant["phone"] = payer_row[4] or order_row[4] or ""
            tenant["email"] = payer_row[5] or order_row[5] or ""
        
        agr_row = db.execute(text("""
            SELECT contract_number FROM master_agreements
            WHERE payer_profile_id = :pid AND status = 'signed'
            ORDER BY signed_at DESC LIMIT 1
        """), {"pid": payer_profile_id}).fetchone()
        if agr_row:
            agreement["contract_number"] = agr_row[0] or ""
    
    # --- Return card data ---
    receivers = []
    return_items_raw = []
    fees = {}
    
    try:
        rc = db.execute(text("""
            SELECT items, receivers, notes, fees
            FROM return_cards WHERE order_id = :order_id
        """), {"order_id": order_id}).fetchone()
        if rc:
            if rc[0]:
                return_items_raw = json.loads(rc[0]) if isinstance(rc[0], str) else rc[0]
            if rc[1]:
                receivers = json.loads(rc[1]) if isinstance(rc[1], str) else rc[1]
            if rc[3]:
                fees = json.loads(rc[3]) if isinstance(rc[3], str) else rc[3]
    except Exception:
        pass
    
    # --- Order items + images ---
    oi_result = db.execute(text("""
        SELECT oi.product_name, oi.product_id, oi.quantity, oi.price, oi.total_rental, p.sku, p.image_url
        FROM order_items oi
        LEFT JOIN products p ON p.product_id = oi.product_id
        WHERE oi.order_id = :order_id AND (oi.status = 'active' OR oi.status IS NULL)
    """), {"order_id": order_id})
    
    order_items_map = {}
    for r in oi_result:
        pid = r[1]
        order_items_map[pid] = {
            "name": r[0], "product_id": pid, "qty": r[2],
            "price_per_day": float(r[3] or 0), "sku": r[5] or "",
            "image_url": pick_product_image(r[6]),
        }
    
    # --- Damage records (ALL types) ---
    dmg_result = db.execute(text("""
        SELECT product_id, product_name, sku, damage_type, damage_code, severity,
               fee, note, photo_url, processing_type, stage, qty, fee_per_item, created_by
        FROM product_damage_history
        WHERE order_id = :order_id
        ORDER BY created_at
    """), {"order_id": order_id})
    
    pre_issue_by_product = {}
    return_damages_by_product = {}
    all_damages = []
    damage_total = 0
    damage_count = 0
    fixation_count = 0
    lost_count = 0
    
    for d in dmg_result:
        pid = d[0]
        proc_type = d[9] or ""
        stage_val = d[10] or ""
        damage_code = d[4] or ""
        is_photo_only = proc_type == 'photo_only'
        is_total_loss = damage_code == 'TOTAL_LOSS' or proc_type == 'written_off'
        fee = float(d[6] or 0)
        
        rec = {
            "product_id": pid, "product_name": d[1], "sku": d[2],
            "damage_type": d[3], "damage_code": damage_code, "severity": d[5],
            "fee": fee, "note": d[7], "photo_url": d[8] or "",
            "processing_type": proc_type, "stage": stage_val,
            "qty": d[11] or 1, "created_by": d[13] or "",
            "is_photo_only": is_photo_only, "is_total_loss": is_total_loss,
        }
        all_damages.append(rec)
        
        if stage_val == 'pre_issue':
            pre_issue_by_product.setdefault(pid, []).append(rec)
        else:
            return_damages_by_product.setdefault(pid, []).append(rec)
            damage_total += fee
            if is_total_loss:
                lost_count += 1
            elif is_photo_only:
                fixation_count += 1
            else:
                damage_count += 1
    
    # --- Calculate loss qty per product ---
    # Рахуємо лише записи з fee > 0, щоб уникнути дублювання (fee=0 = фіксація перед списанням)
    loss_qty_by_product = {}
    for d in all_damages:
        if d.get('is_total_loss') and d.get('fee', 0) > 0:
            pid = d['product_id']
            loss_qty_by_product[pid] = loss_qty_by_product.get(pid, 0) + (d.get('qty', 1) or 1)
    
    # Якщо всі loss записи мають fee=0, використаємо MAX qty як fallback
    for d in all_damages:
        if d.get('is_total_loss'):
            pid = d['product_id']
            if pid not in loss_qty_by_product:
                current = loss_qty_by_product.get(pid, 0)
                loss_qty_by_product[pid] = max(current, d.get('qty', 1) or 1)
    
    # --- Build final items list ---
    items = []
    issued_qty_total = 0
    returned_qty_total = 0
    
    if return_items_raw:
        for ri in return_items_raw:
            pid = ri.get('product_id') or ri.get('id')
            oi = order_items_map.get(pid, {})
            issued = ri.get('rented_qty') or ri.get('qty') or oi.get('qty', 1)
            returned = ri.get('returned_qty') or issued
            findings = ri.get('findings', [])
            
            # Віднімаємо втрачені одиниці
            loss_qty = loss_qty_by_product.get(pid, 0)
            returned = max(0, returned - loss_qty)
            
            issued_qty_total += issued
            returned_qty_total += returned
            
            pre_dmg = pre_issue_by_product.get(pid, [])
            ret_dmg = return_damages_by_product.get(pid, [])
            
            has_total_loss = any(dd.get('is_total_loss') for dd in ret_dmg)
            has_return_damage = any(not dd.get('is_photo_only') for dd in ret_dmg)
            
            items.append({
                "name": ri.get('name') or oi.get('name', ''),
                "sku": ri.get('sku') or oi.get('sku', ''),
                "image_url": oi.get('image_url', ''),
                "issued_qty": issued,
                "returned_qty": returned,
                "loss_qty": loss_qty,
                "findings": findings,
                "pre_issue_damages": pre_dmg,
                "damages": ret_dmg,
                "has_return_damage": has_return_damage,
                "is_total_loss": has_total_loss,
                "has_packaging": False,
                "packaging_labels": [],
            })
    else:
        for pid, oi in order_items_map.items():
            pre_dmg = pre_issue_by_product.get(pid, [])
            ret_dmg = return_damages_by_product.get(pid, [])
            has_total_loss = any(dd.get('is_total_loss') for dd in ret_dmg)
            has_return_damage = any(not dd.get('is_photo_only') for dd in ret_dmg)
            qty = oi.get('qty', 1)
            
            # Віднімаємо втрачені одиниці
            loss_qty = loss_qty_by_product.get(pid, 0)
            returned = max(0, qty - loss_qty)
            
            issued_qty_total += qty
            returned_qty_total += returned
            
            items.append({
                "name": oi.get('name', ''),
                "sku": oi.get('sku', ''),
                "image_url": oi.get('image_url', ''),
                "issued_qty": qty,
                "returned_qty": returned,
                "loss_qty": loss_qty,
                "findings": [],
                "pre_issue_damages": pre_dmg,
                "damages": ret_dmg,
                "has_return_damage": has_return_damage,
                "is_total_loss": has_total_loss,
                "has_packaging": False,
                "packaging_labels": [],
            })
    
    # --- Packaging ---
    packaging = []
    has_packaging = False
    try:
        pkg_result = db.execute(text("""
            SELECT packaging_type, quantity FROM order_packaging WHERE order_id = :oid
        """), {"oid": order_id})
        pkg_labels = {"bag": "Мішок", "box": "Коробка", "pallet": "Палета", "crate": "Ящик"}
        for p in pkg_result:
            if p[1] and p[1] > 0:
                has_packaging = True
                packaging.append({"label": pkg_labels.get(p[0], p[0]), "issued": p[1], "returned": p[1], "missing": 0})
    except Exception:
        pass
    
    total_lost_qty = sum(loss_qty_by_product.values())
    
    return_totals = {
        "issued_items": len(items),
        "returned_items": len([i for i in items if i["returned_qty"] > 0]),
        "issued_qty": issued_qty_total,
        "returned_qty": returned_qty_total,
        "damage_count": damage_count + fixation_count,
        "lost_count": total_lost_qty,
        "damage_total": damage_total,
    }
    
    return {
        "meta": {
            "act_day": now.strftime("%d"),
            "act_month": months_ua[now.month - 1],
            "act_year": now.strftime("%Y"),
            "doc_number": "",
        },
        "order": order,
        "client": {
            "name": order["customer_name"],
            "phone": order["customer_phone"],
            "email": order.get("customer_email", ""),
        },
        "tenant": tenant,
        "agreement": agreement,
        "company": company,
        "items": items,
        "receivers": receivers,
        "fees": fees,
        "totals": return_totals,
        "has_packaging": has_packaging,
        "packaging": packaging,
        "damage": {
            "has_damage": len(all_damages) > 0,
            "rows": all_damages,
            "total": damage_total,
        },
        "generated_at": now.strftime("%d.%m.%Y %H:%M"),
        "return_date": now.strftime("%d.%m.%Y"),
        "issue_date": order.get("rental_start_date", ""),
        "late_days": 0,
        "not_returned_items": [],
        "executor": {"name": ""},
        "options": options,
    }


def build_damage_data(db: Session, damage_case_id: str, options: dict) -> dict:
    """Збирає дані кейсу пошкодження для документа"""
    # Company data
    company = get_company_config(db)
    
    # If damage_case_id is actually an order_id, get order data
    if damage_case_id:
        order_data = build_order_data(db, damage_case_id, options)
        return {
            "damage_case": options.get("damage_case", {}),
            "order": order_data.get("order", {}),
            "items": options.get("damage_items", order_data.get("items", [])),
            "totals": order_data.get("totals", {}),
            "company": company,
            "generated_at": datetime.now().strftime("%d.%m.%Y %H:%M"),
            "options": options
        }
    
    return {
        "damage_case": options.get("damage_case", {}),
        "items": options.get("damage_items", []),
        "totals": {},
        "company": company,
        "generated_at": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "options": options
    }


def build_vendor_task_data(db: Session, vendor_task_id: str, options: dict) -> dict:
    """Збирає дані завдання підрядника для документа"""
    company = get_company_config(db)
    
    # Try to get vendor task from database
    vendor_task = options.get("vendor_task", {
        "vendor_name": options.get("vendor_name", ""),
        "work_type": options.get("work_type", "Хімчистка"),
        "items_description": options.get("items_description", ""),
        "total_cost": options.get("total_cost", 0),
        "items": options.get("items", [])
    })
    
    return {
        "vendor_task": vendor_task,
        "company": company,
        "generated_at": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "options": options
    }



def build_order_modification_data(db: Session, order_id: str, options: dict) -> dict:
    """
    Збирає дані для документа Дозамовлення
    Включає історію змін та відмовлені позиції
    """
    
    # Основні дані замовлення
    result = db.execute(text("""
        SELECT 
            order_id, order_number, customer_name, customer_phone, customer_email,
            rental_start_date, rental_end_date, rental_days,
            total_price, deposit_amount, status
        FROM orders
        WHERE order_id = :order_id
    """), {"order_id": order_id})
    
    order_row = result.fetchone()
    if not order_row:
        raise ValueError(f"Order not found: {order_id}")
    
    order = {
        "order_id": order_row[0],
        "order_number": order_row[1] or f"OC-{order_row[0]}",
        "customer_name": order_row[2] or "",
        "customer_phone": order_row[3] or "",
        "customer_email": order_row[4] or "",
        "rental_start_date": order_row[5].strftime("%d.%m.%Y") if order_row[5] else "",
        "rental_end_date": order_row[6].strftime("%d.%m.%Y") if order_row[6] else "",
        "rental_days": order_row[7] or 1,
        "status": order_row[10]
    }
    
    # Поточні суми
    new_totals = {
        "total_price": float(order_row[8] or 0),
        "deposit_amount": float(order_row[9] or 0)
    }
    
    # Історія змін
    modifications = []
    total_price_change = 0
    total_deposit_change = 0
    
    try:
        mod_result = db.execute(text("""
            SELECT id, modification_type, product_id, product_name,
                   old_quantity, new_quantity, old_price, new_price,
                   price_change, deposit_change, reason, created_by,
                   DATE_FORMAT(created_at, '%d.%m.%Y %H:%i') as created_at
            FROM order_modifications
            WHERE order_id = :order_id
            ORDER BY created_at ASC
        """), {"order_id": order_id})
        
        for row in mod_result:
            price_change = float(row[8] or 0)
            deposit_change = float(row[9] or 0)
            
            total_price_change += price_change
            total_deposit_change += deposit_change
            
            modifications.append({
                "id": row[0],
                "modification_type": row[1],
                "product_id": row[2],
                "product_name": row[3] or "",
                "old_quantity": row[4] or 0,
                "new_quantity": row[5] or 0,
                "old_price": float(row[6] or 0),
                "new_price": float(row[7] or 0),
                "price_change": price_change,
                "deposit_change": deposit_change,
                "reason": row[10] or "",
                "created_by": row[11] or "",
                "created_at": row[12] or ""
            })
    except Exception as e:
        # Table might not exist yet
        print(f"Warning: Could not fetch modifications: {e}")
    
    # Відмовлені позиції
    refused_items = []
    try:
        refused_result = db.execute(text("""
            SELECT product_id, product_name, quantity, original_quantity, refusal_reason
            FROM order_items
            WHERE order_id = :order_id AND status = 'refused'
        """), {"order_id": order_id})
        
        for row in refused_result:
            refused_items.append({
                "product_id": row[0],
                "product_name": row[1] or "",
                "quantity": row[2] or 0,
                "original_quantity": row[3] or row[2] or 0,
                "refusal_reason": row[4] or "Відмова клієнта"
            })
    except Exception as e:
        print(f"Warning: Could not fetch refused items: {e}")
    
    company = get_company_config(db)
    
    return {
        "order": order,
        "modifications": modifications,
        "refused_items": refused_items,
        "new_totals": new_totals,
        "total_price_change": total_price_change,
        "total_deposit_change": total_deposit_change,
        "company": company,
        "generated_at": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "options": options
    }


def build_damage_breakdown_data(db: Session, order_id: str, options: dict) -> dict:
    """
    Збирає дані для Розшифровки пошкоджень.
    Включає ВСІ пошкодження товарів, що є в замовленні (з будь-яких замовлень).
    Це єдине джерело правди про стан товару.
    """
    
    # Основні дані замовлення
    result = db.execute(text("""
        SELECT 
            order_id, order_number, customer_name, customer_phone, customer_email,
            rental_start_date, rental_end_date, rental_days, status
        FROM orders
        WHERE order_id = :order_id
    """), {"order_id": order_id})
    
    order_row = result.fetchone()
    if not order_row:
        raise ValueError(f"Order not found: {order_id}")
    
    order = {
        "order_id": order_row[0],
        "order_number": order_row[1] or f"OC-{order_row[0]}",
        "customer_name": order_row[2] or "",
        "customer_phone": order_row[3] or "",
        "customer_email": order_row[4] or "",
        "rental_start_date": order_row[5].strftime("%d.%m.%Y") if order_row[5] else "",
        "rental_end_date": order_row[6].strftime("%d.%m.%Y") if order_row[6] else "",
        "rental_days": order_row[7] or 1,
        "status": order_row[8]
    }
    
    # Отримуємо SKU всіх товарів у замовленні
    items_result = db.execute(text("""
        SELECT DISTINCT oi.sku, oi.product_id, oi.name
        FROM order_items oi
        WHERE oi.order_id = :order_id AND (oi.status = 'active' OR oi.status IS NULL)
    """), {"order_id": order_id})
    
    order_items = []
    order_skus = []
    order_product_ids = []
    for row in items_result:
        order_items.append({"sku": row[0], "product_id": row[1], "name": row[2]})
        if row[0]:
            order_skus.append(row[0])
        if row[1]:
            order_product_ids.append(row[1])
    
    # Отримуємо ВСІ пошкодження для цих товарів (з будь-яких замовлень)
    damage_result = db.execute(text("""
        SELECT 
            pdh.id, pdh.product_id, pdh.sku, pdh.product_name,
            pdh.damage_type, pdh.severity, pdh.note,
            pdh.photo_url, pdh.created_by,
            DATE_FORMAT(pdh.created_at, '%d.%m.%Y %H:%i') as created_at,
            pdh.order_number, pdh.stage
        FROM product_damage_history pdh
        WHERE (pdh.sku IN :skus OR pdh.product_id IN :product_ids)
        ORDER BY pdh.product_name, pdh.created_at DESC
    """), {"skus": tuple(order_skus) if order_skus else ('',), "product_ids": tuple(order_product_ids) if order_product_ids else (0,)})
    
    damage_type_names = {
        "broken": "Зламано",
        "scratched": "Подряпано", 
        "stained": "Плями",
        "chipped": "Відколото",
        "cracked": "Тріщина",
        "missing": "Відсутнє",
        "dirty": "Забруднено",
        "wax": "Віск / залишки свічок",
        "other": "Інше"
    }
    
    stage_labels = {
        "pre_issue": "До видачі",
        "return": "При поверненні",
        "inventory": "Аудит",
        "audit": "Аудит"
    }
    
    damages = []
    product_ids_with_damage = set()
    
    # Базовий URL для фото (через API для сумісності з production)
    import os
    import base64
    from pathlib import Path
    
    BACKEND_URL = os.environ.get('BACKEND_PUBLIC_URL', 'https://backrentalhub.farforrent.com.ua')
    
    # Визначаємо шлях до папки з фото пошкоджень
    PROD_UPLOADS = Path("/home/farforre/farforrent.com.ua/rentalhub/backend/uploads/damage_photos")
    LOCAL_UPLOADS = Path(__file__).parent.parent.parent / "uploads" / "damage_photos"
    UPLOADS_DIR = PROD_UPLOADS if PROD_UPLOADS.exists() else LOCAL_UPLOADS
    
    def get_photo_for_document(photo_path: str) -> str:
        """
        Отримує фото для документа.
        Спочатку намагається завантажити локально (для base64),
        якщо не знаходить - повертає URL через API.
        """
        if not photo_path:
            return None
        
        # Якщо вже повний URL або base64 - повертаємо як є
        if photo_path.startswith('http') or photo_path.startswith('data:'):
            return photo_path
        
        # Визначаємо ім'я файлу
        filename = photo_path
        if '/' in photo_path:
            filename = photo_path.split('/')[-1]
        
        # Спробуємо знайти локально і конвертувати в base64
        local_path = UPLOADS_DIR / filename
        if local_path.exists():
            try:
                import mimetypes
                mime_type, _ = mimetypes.guess_type(str(local_path))
                if not mime_type:
                    mime_type = 'image/jpeg'
                with open(local_path, 'rb') as f:
                    data = base64.b64encode(f.read()).decode('utf-8')
                return f"data:{mime_type};base64,{data}"
            except Exception as e:
                print(f"Warning: Could not read local file {local_path}: {e}")
        
        # Формуємо URL через API (працює з nginx proxy)
        return f"{BACKEND_URL}/api/uploads/damage_photos/{filename}"
    
    for row in damage_result:
        product_id = row[1]
        product_ids_with_damage.add(product_id)
        
        # Формуємо URL/base64 для фото
        photo_url = get_photo_for_document(row[7])
        
        stage = row[11] or "inventory"
        
        damages.append({
            "id": row[0],
            "product_id": product_id,
            "sku": row[2] or "",
            "product_name": row[3] or "",
            "damage_type": damage_type_names.get(row[4], row[4] or "Інше"),
            "damage_type_code": row[4],
            "severity": row[5] or "low",
            "note": row[6] or "",
            "photo_url": photo_url,
            "created_by": row[8] or "Система",
            "created_at": row[9] or "",
            "order_number": row[10] or "",
            "stage": stage,
            "stage_label": stage_labels.get(stage, stage)
        })
    
    company = get_company_config(db)
    
    return {
        "order": order,
        "damages": damages,
        "items_with_damage": len(product_ids_with_damage),
        "total_items": len(order_items),
        "company": company,
        "generated_at": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "options": options
    }
