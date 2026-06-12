"""
Client Users API - CRUD для клієнтів/контактів
Один email = один клієнт
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional, List
from pydantic import BaseModel, EmailStr
from datetime import datetime
import logging

from database_rentalhub import get_rh_db

router = APIRouter(prefix="/api/clients", tags=["clients"])
logger = logging.getLogger(__name__)


# ============================================================================
# SCHEMAS
# ============================================================================

class ClientCreate(BaseModel):
    email: str
    full_name: Optional[str] = None
    phone: Optional[str] = None
    company_hint: Optional[str] = None
    company: Optional[str] = None
    notes: Optional[str] = None
    preferred_contact: Optional[str] = None
    source: Optional[str] = "rentalhub"
    payer_type: Optional[str] = "individual"
    tax_id: Optional[str] = None
    is_regular: Optional[bool] = False
    rating: Optional[int] = 0
    rating_labels: Optional[str] = None
    internal_notes: Optional[str] = None
    instagram: Optional[str] = None

class ClientUpdate(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    company_hint: Optional[str] = None
    company: Optional[str] = None
    notes: Optional[str] = None
    preferred_contact: Optional[str] = None
    is_active: Optional[bool] = None
    payer_type: Optional[str] = None
    tax_id: Optional[str] = None
    bank_details: Optional[dict] = None
    is_regular: Optional[bool] = None
    rating: Optional[int] = None
    rating_labels: Optional[str] = None
    internal_notes: Optional[str] = None
    instagram: Optional[str] = None

class ClientResponse(BaseModel):
    id: int
    email: str
    email_normalized: str
    full_name: Optional[str]
    phone: Optional[str]
    company_hint: Optional[str]
    company: Optional[str] = None
    source: Optional[str]
    notes: Optional[str]
    preferred_contact: Optional[str]
    is_active: bool
    created_at: Optional[str]
    updated_at: Optional[str]
    payer_type: Optional[str] = "individual"
    tax_id: Optional[str] = None
    bank_details: Optional[dict] = None
    # Нові поля
    is_regular: Optional[bool] = False
    rating: Optional[int] = 0
    rating_labels: Optional[str] = None
    internal_notes: Optional[str] = None
    instagram: Optional[str] = None
    total_revenue: Optional[float] = 0
    last_order_date: Optional[str] = None
    # MA info
    has_agreement: Optional[bool] = False
    agreement_status: Optional[str] = None
    agreement_number: Optional[str] = None
    # Статистика
    orders_count: Optional[int] = 0
    payers_count: Optional[int] = 0
    default_payer_id: Optional[int] = None
    default_payer_name: Optional[str] = None


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.get("")
async def list_clients(
    search: Optional[str] = None,
    source: Optional[str] = None,
    has_payer: Optional[bool] = None,
    skip: int = 0,
    limit: int = 500,  # Збільшено ліміт для завантаження всіх клієнтів
    db: Session = Depends(get_rh_db)
):
    """Список клієнтів з пошуком та фільтрами

    Об'єднує дані з client_users (нові клієнти з Event Tool) і
    customers (legacy OpenCart) — щоб менеджер бачив усіх в одному місці.
    """

    # Перевіряємо чи існує legacy таблиця customers (OpenCart)
    legacy_exists = False
    try:
        db.execute(text("SHOW COLUMNS FROM customers")).fetchall()
        legacy_exists = True
    except Exception:
        legacy_exists = False

    sql = """
        SELECT 
            c.id, c.email, c.email_normalized, c.full_name, c.phone,
            c.company_hint, c.source, c.notes, c.preferred_contact,
            c.is_active, c.created_at, c.updated_at,
            c.payer_type, c.tax_id, c.bank_details,
            COUNT(DISTINCT o.order_id) as orders_count,
            COUNT(DISTINCT cpl.payer_profile_id) as payers_count,
            (SELECT payer_profile_id FROM client_payer_links 
             WHERE client_user_id = c.id AND is_default = TRUE LIMIT 1) as default_payer_id,
            ma.id as ma_id, ma.contract_number as ma_number, ma.status as ma_status,
            c.is_regular, c.company, c.rating, c.rating_labels, c.internal_notes,
            c.total_revenue, c.last_order_date, c.instagram
        FROM client_users c
        LEFT JOIN orders o ON o.client_user_id = c.id
        LEFT JOIN client_payer_links cpl ON cpl.client_user_id = c.id
        LEFT JOIN master_agreements ma ON ma.client_user_id = c.id 
            AND ma.status IN ('draft', 'sent', 'signed')
            AND (ma.valid_until IS NULL OR ma.valid_until >= CURDATE())
        WHERE 1=1
    """
    params = {}
    
    if search:
        sql += """ AND (
            c.email LIKE :search OR 
            c.full_name LIKE :search OR 
            c.phone LIKE :search OR
            c.company_hint LIKE :search OR
            c.company LIKE :search OR
            c.instagram LIKE :search
        )"""
        params["search"] = f"%{search}%"
    
    if source:
        sql += " AND c.source = :source"
        params["source"] = source
    
    sql += " GROUP BY c.id ORDER BY c.updated_at DESC LIMIT :limit OFFSET :skip"
    params["limit"] = limit
    params["skip"] = skip
    
    result = db.execute(text(sql), params)
    
    clients = []
    for row in result:
        import json as json_lib
        bank_details = None
        if row[14]:
            try:
                bank_details = json_lib.loads(row[14]) if isinstance(row[14], str) else row[14]
            except:
                pass
        
        clients.append({
            "id": row[0],
            "email": row[1],
            "email_normalized": row[2],
            "full_name": row[3],
            "phone": row[4],
            "company_hint": row[5],
            "source": row[6],
            "notes": row[7],
            "preferred_contact": row[8],
            "is_active": bool(row[9]),
            "created_at": row[10].isoformat() if row[10] else None,
            "updated_at": row[11].isoformat() if row[11] else None,
            "payer_type": row[12] or "individual",
            "tax_id": row[13],
            "bank_details": bank_details,
            "orders_count": row[15] or 0,
            "payers_count": row[16] or 0,
            "default_payer_id": row[17],
            "has_agreement": bool(row[18]),
            "agreement_number": row[19],
            "agreement_status": row[20],
            "is_regular": bool(row[21]) if row[21] is not None else False,
            "company": row[22],
            "rating": row[23] or 0,
            "rating_labels": row[24],
            "internal_notes": row[25],
            "total_revenue": float(row[26]) if row[26] else 0,
            "last_order_date": row[27].isoformat() if row[27] else None,
            "instagram": row[28]
        })
    
    # Фільтр has_payer після агрегації
    if has_payer is not None:
        if has_payer:
            clients = [c for c in clients if c["payers_count"] > 0]
        else:
            clients = [c for c in clients if c["payers_count"] == 0]

    # ✨ LEGACY: додаємо клієнтів з OpenCart customers (якщо таблиця існує)
    # Це показує менеджеру ВСІХ клієнтів в одному списку, незалежно від джерела.
    if legacy_exists and not source:  # не показуємо legacy якщо явний фільтр source
        try:
            # Знаходимо доступні колонки в customers
            cust_cols_rows = db.execute(text("SHOW COLUMNS FROM customers")).fetchall()
            cust_cols = {r[0] for r in cust_cols_rows}
            def cc(name, default="NULL"):
                return name if name in cust_cols else default

            legacy_sql = f"""
                SELECT
                    {cc('customer_id')} AS id,
                    {cc('email', "''")} AS email,
                    LOWER({cc('email', "''")}) AS email_normalized,
                    CONCAT_WS(' ', {cc('firstname', "''")}, {cc('lastname', "''")}) AS full_name,
                    {cc('telephone', "''")} AS phone,
                    {cc('date_added')} AS created_at,
                    {cc('status', '1')} AS is_active
                FROM customers
                WHERE 1=1
                {("AND (CONCAT_WS(' ', " + cc('firstname',"''") + "," + cc('lastname',"''") + ") LIKE :s OR " + cc('email',"''") + " LIKE :s OR " + cc('telephone',"''") + " LIKE :s)") if search else ""}
                ORDER BY {cc('date_added','customer_id')} DESC
                LIMIT 500
            """
            legacy_params = {"s": f"%{search}%"} if search else {}
            legacy_rows = db.execute(text(legacy_sql), legacy_params).fetchall()

            # Email-и які вже є в client_users — щоб не дублювати
            existing_emails = {(c.get("email") or "").lower() for c in clients}

            for r in legacy_rows:
                email_norm = (r[2] or "").lower().strip()
                if email_norm and email_norm in existing_emails:
                    continue  # вже є в client_users — пропускаємо дублікат
                clients.append({
                    "id": f"legacy_{r[0]}",   # префікс щоб не плутати з client_users.id
                    "legacy_customer_id": r[0],
                    "email": r[1] or "",
                    "email_normalized": email_norm,
                    "full_name": (r[3] or "").strip() or (r[1] or "—"),
                    "phone": r[4] or "",
                    "company_hint": None,
                    "source": "opencart_legacy",
                    "notes": None,
                    "preferred_contact": None,
                    "is_active": bool(r[6]) if r[6] is not None else True,
                    "created_at": r[5].isoformat() if r[5] and hasattr(r[5], 'isoformat') else None,
                    "updated_at": None,
                    "payer_type": "individual",
                    "tax_id": None,
                    "bank_details": None,
                    "orders_count": 0,
                    "payers_count": 0,
                    "default_payer_id": None,
                    "has_agreement": False,
                    "agreement_number": None,
                    "agreement_status": None,
                    "is_regular": False,
                    "company": None,
                    "rating": 0,
                    "rating_labels": None,
                    "internal_notes": None,
                    "total_revenue": 0,
                    "last_order_date": None,
                    "instagram": None,
                })
        except Exception as legacy_err:
            print(f"[clients.list] legacy customers query failed: {legacy_err}")
    
    return clients


# ============================================================================
# FIND CLIENT BY NAME/PHONE (for order linking)
# ============================================================================

@router.get("/find-match")
async def find_client_match(
    name: Optional[str] = None,
    phone: Optional[str] = None,
    email: Optional[str] = None,
    db: Session = Depends(get_rh_db)
):
    """
    Знайти клієнта по імені, телефону або email.
    Використовується для автоприв'язки ордерів до клієнтів.
    """
    if not name and not phone and not email:
        return {"found": False, "message": "Вкажіть name, phone або email"}
    
    # Normalize phone (remove spaces, dashes, +38)
    if phone:
        phone_clean = phone.replace(" ", "").replace("-", "").replace("+38", "").replace("+", "")
        if len(phone_clean) == 10:
            phone_clean = phone_clean  # Ukrainian format without country code
        phone_pattern = f"%{phone_clean[-9:]}%"  # Last 9 digits
    
    sql = """
        SELECT 
            c.id, c.email, c.full_name, c.phone, c.payer_type, c.tax_id,
            ma.id as ma_id, ma.contract_number as ma_number, ma.status as ma_status
        FROM client_users c
        LEFT JOIN master_agreements ma ON ma.client_user_id = c.id 
            AND ma.status IN ('draft', 'sent', 'signed')
            AND (ma.valid_until IS NULL OR ma.valid_until >= CURDATE())
        WHERE c.is_active = 1 AND (
    """
    
    conditions = []
    params = {}
    
    if email:
        conditions.append("LOWER(TRIM(c.email)) = LOWER(TRIM(:email))")
        params["email"] = email
    
    if phone:
        conditions.append("c.phone LIKE :phone")
        params["phone"] = phone_pattern
    
    if name:
        # Fuzzy match by name
        conditions.append("c.full_name LIKE :name")
        params["name"] = f"%{name}%"
    
    sql += " OR ".join(conditions) + ") ORDER BY c.updated_at DESC LIMIT 5"
    
    result = db.execute(text(sql), params)
    matches = []
    
    for row in result:
        matches.append({
            "id": row[0],
            "email": row[1],
            "full_name": row[2],
            "phone": row[3],
            "payer_type": row[4] or "individual",
            "tax_id": row[5],
            "has_agreement": bool(row[6]),
            "agreement_number": row[7],
            "agreement_status": row[8]
        })
    
    if matches:
        return {
            "found": True,
            "count": len(matches),
            "best_match": matches[0],
            "all_matches": matches
        }
    
    return {"found": False, "message": "Клієнта не знайдено"}


@router.get("/{client_id}")
async def get_client(client_id: int, db: Session = Depends(get_rh_db)):
    """Отримати клієнта за ID з усіма деталями"""
    
    result = db.execute(text("""
        SELECT 
            c.id, c.email, c.email_normalized, c.full_name, c.phone,
            c.company_hint, c.source, c.notes, c.preferred_contact,
            c.is_active, c.created_at, c.updated_at,
            c.payer_type, c.tax_id, c.is_regular, c.company,
            c.rating, c.rating_labels, c.internal_notes,
            c.total_revenue, c.last_order_date, c.instagram
        FROM client_users c
        WHERE c.id = :id
    """), {"id": client_id})
    row = result.fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail="Клієнта не знайдено")
    
    client = {
        "id": row[0],
        "email": row[1],
        "email_normalized": row[2],
        "full_name": row[3],
        "phone": row[4],
        "company_hint": row[5],
        "source": row[6],
        "notes": row[7],
        "preferred_contact": row[8],
        "is_active": bool(row[9]),
        "created_at": row[10].isoformat() if row[10] else None,
        "updated_at": row[11].isoformat() if row[11] else None,
        "payer_type": row[12] or "individual",
        "tax_id": row[13],
        "is_regular": bool(row[14]) if row[14] is not None else False,
        "company": row[15],
        "rating": row[16] or 0,
        "rating_labels": row[17],
        "internal_notes": row[18],
        "total_revenue": float(row[19]) if row[19] else 0,
        "last_order_date": row[20].isoformat() if row[20] else None,
        "instagram": row[21]
    }
    
    # Отримати платників клієнта
    payers_result = db.execute(text("""
        SELECT 
            pp.id, pp.type, pp.display_name, pp.tax_mode, pp.edrpou,
            cpl.is_default, cpl.label
        FROM client_payer_links cpl
        JOIN payer_profiles pp ON pp.id = cpl.payer_profile_id
        WHERE cpl.client_user_id = :client_id AND pp.is_active = TRUE
        ORDER BY cpl.is_default DESC, pp.display_name
    """), {"client_id": client_id})
    
    client["payers"] = [{
        "id": p[0],
        "type": p[1],
        "display_name": p[2],
        "tax_mode": p[3],
        "edrpou": p[4],
        "is_default": bool(p[5]),
        "label": p[6]
    } for p in payers_result]
    
    # Отримати останні замовлення
    orders_result = db.execute(text("""
        SELECT 
            o.order_id, o.order_number, o.status, o.total_price,
            o.rental_start_date, o.created_at, o.source,
            pp.display_name as payer_name,
            COALESCE(o.service_fee, 0) as service_fee,
            COALESCE(o.discount_amount, 0) as discount_amount,
            o.service_fee_name
        FROM orders o
        LEFT JOIN payer_profiles pp ON pp.id = o.payer_profile_id
        WHERE o.client_user_id = :client_id
        ORDER BY o.created_at DESC
        LIMIT 20
    """), {"client_id": client_id})
    
    client["recent_orders"] = []
    for o in orders_result:
        tp = float(o[3]) if o[3] else 0
        sf = float(o[8]) if o[8] else 0
        da = float(o[9]) if o[9] else 0
        total_to_pay = round(max(0, tp - da) + sf, 2)
        client["recent_orders"].append({
            "order_id": o[0],
            "order_number": o[1],
            "status": o[2],
            "total_price": tp,
            "rental_start_date": o[4].isoformat() if o[4] else None,
            "created_at": o[5].isoformat() if o[5] else None,
            "source": o[6],
            "payer_name": o[7],
            "service_fee": sf,
            "service_fee_name": o[10] or "",
            "discount_amount": da,
            "total_to_pay": total_to_pay,
        })
    
    # Статистика
    stats = db.execute(text("""
        SELECT 
            COUNT(*) as total_orders,
            SUM(CASE WHEN source = 'event_tool' THEN 1 ELSE 0 END) as event_orders,
            SUM(CASE WHEN source = 'opencart' OR source IS NULL THEN 1 ELSE 0 END) as oc_orders
        FROM orders WHERE client_user_id = :client_id
    """), {"client_id": client_id}).fetchone()
    
    client["stats"] = {
        "total_orders": stats[0] or 0,
        "event_orders": stats[1] or 0,
        "oc_orders": stats[2] or 0
    }
    
    return client


@router.post("")
async def create_client(data: ClientCreate, db: Session = Depends(get_rh_db)):
    """Створити нового клієнта"""
    
    email_normalized = data.email.lower().strip()
    
    # Перевірити чи email вже існує
    existing = db.execute(text("""
        SELECT id FROM client_users WHERE email_normalized = :email
    """), {"email": email_normalized}).fetchone()
    
    if existing:
        raise HTTPException(
            status_code=400, 
            detail=f"Клієнт з email {data.email} вже існує (ID: {existing[0]})"
        )
    
    db.execute(text("""
        INSERT INTO client_users 
        (email, email_normalized, full_name, phone, company_hint, company, notes, 
         preferred_contact, source, is_regular, rating, rating_labels, internal_notes, instagram)
        VALUES 
        (:email, :email_norm, :name, :phone, :company_hint, :company, :notes, 
         :contact, :source, :is_regular, :rating, :rating_labels, :internal_notes, :instagram)
    """), {
        "email": data.email,
        "email_norm": email_normalized,
        "name": data.full_name,
        "phone": data.phone,
        "company_hint": data.company_hint,
        "company": data.company,
        "notes": data.notes,
        "contact": data.preferred_contact,
        "source": data.source or "rentalhub",
        "is_regular": data.is_regular or False,
        "rating": data.rating or 0,
        "rating_labels": data.rating_labels,
        "internal_notes": data.internal_notes,
        "instagram": data.instagram
    })
    db.commit()
    
    # Отримати створеного клієнта
    result = db.execute(text("""
        SELECT id FROM client_users WHERE email_normalized = :email
    """), {"email": email_normalized}).fetchone()
    
    logger.info(f"✅ Created client: {email_normalized} (ID: {result[0]})")
    
    return await get_client(result[0], db)


@router.patch("/{client_id}")
async def update_client(client_id: int, data: ClientUpdate, db: Session = Depends(get_rh_db)):
    """Оновити клієнта"""
    
    # Перевірити існування
    existing = db.execute(text("SELECT id FROM client_users WHERE id = :id"), {"id": client_id}).fetchone()
    if not existing:
        raise HTTPException(status_code=404, detail="Клієнта не знайдено")
    
    updates = []
    params = {"id": client_id}
    
    if data.full_name is not None:
        updates.append("full_name = :name")
        params["name"] = data.full_name
    if data.phone is not None:
        updates.append("phone = :phone")
        params["phone"] = data.phone
    if data.company_hint is not None:
        updates.append("company_hint = :company")
        params["company"] = data.company_hint
    if data.notes is not None:
        updates.append("notes = :notes")
        params["notes"] = data.notes
    if data.preferred_contact is not None:
        updates.append("preferred_contact = :contact")
        params["contact"] = data.preferred_contact
    if data.is_active is not None:
        updates.append("is_active = :active")
        params["active"] = data.is_active
    if data.payer_type is not None:
        updates.append("payer_type = :payer_type")
        params["payer_type"] = data.payer_type if data.payer_type else None
    if data.tax_id is not None:
        updates.append("tax_id = :tax_id")
        params["tax_id"] = data.tax_id if data.tax_id else None
    if data.email is not None:
        updates.append("email = :email")
        params["email"] = data.email
        updates.append("email_normalized = :email_normalized")
        params["email_normalized"] = data.email.lower().strip() if data.email else None
    if data.is_regular is not None:
        updates.append("is_regular = :is_regular")
        params["is_regular"] = data.is_regular
    if data.company is not None:
        updates.append("company = :company")
        params["company"] = data.company if data.company else None
    if data.rating is not None:
        updates.append("rating = :rating")
        params["rating"] = data.rating
    if data.rating_labels is not None:
        updates.append("rating_labels = :rating_labels")
        params["rating_labels"] = data.rating_labels if data.rating_labels else None
    if data.internal_notes is not None:
        updates.append("internal_notes = :internal_notes")
        params["internal_notes"] = data.internal_notes if data.internal_notes else None
    if data.instagram is not None:
        updates.append("instagram = :instagram")
        params["instagram"] = data.instagram if data.instagram else None
    
    if updates:
        updates.append("updated_at = NOW()")
        sql = f"UPDATE client_users SET {', '.join(updates)} WHERE id = :id"
        db.execute(text(sql), params)
        db.commit()
    
    return await get_client(client_id, db)


@router.get("/{client_id}/payers")
async def get_client_payers(client_id: int, db: Session = Depends(get_rh_db)):
    """Отримати платників клієнта"""
    
    result = db.execute(text("""
        SELECT 
            pp.id, pp.type, pp.display_name, pp.tax_mode, pp.details_json,
            pp.legal_name, pp.edrpou, pp.iban, pp.email_for_docs, pp.phone_for_docs,
            pp.signatory_name, pp.signatory_basis, pp.is_active, pp.created_at,
            cpl.is_default, cpl.label
        FROM client_payer_links cpl
        JOIN payer_profiles pp ON pp.id = cpl.payer_profile_id
        WHERE cpl.client_user_id = :client_id
        ORDER BY cpl.is_default DESC, pp.display_name
    """), {"client_id": client_id})
    
    return [{
        "id": row[0],
        "type": row[1],
        "display_name": row[2],
        "tax_mode": row[3],
        "details_json": row[4],
        "legal_name": row[5],
        "edrpou": row[6],
        "iban": row[7],
        "email_for_docs": row[8],
        "phone_for_docs": row[9],
        "signatory_name": row[10],
        "signatory_basis": row[11],
        "is_active": bool(row[12]),
        "created_at": row[13].isoformat() if row[13] else None,
        "is_default": bool(row[14]),
        "label": row[15]
    } for row in result]


@router.post("/{client_id}/payers/{payer_id}/link")
async def link_payer_to_client(
    client_id: int, 
    payer_id: int, 
    is_default: bool = False,
    label: Optional[str] = None,
    db: Session = Depends(get_rh_db)
):
    """Прив'язати платника до клієнта"""
    
    # Перевірити існування
    client = db.execute(text("SELECT id FROM client_users WHERE id = :id"), {"id": client_id}).fetchone()
    if not client:
        raise HTTPException(status_code=404, detail="Клієнта не знайдено")
    
    payer = db.execute(text("SELECT id FROM payer_profiles WHERE id = :id"), {"id": payer_id}).fetchone()
    if not payer:
        raise HTTPException(status_code=404, detail="Платника не знайдено")
    
    # Перевірити чи вже є зв'язок
    existing = db.execute(text("""
        SELECT id FROM client_payer_links 
        WHERE client_user_id = :client AND payer_profile_id = :payer
    """), {"client": client_id, "payer": payer_id}).fetchone()
    
    if existing:
        # Оновити
        db.execute(text("""
            UPDATE client_payer_links 
            SET is_default = :default, label = :label
            WHERE id = :id
        """), {"id": existing[0], "default": is_default, "label": label})
    else:
        # Створити
        db.execute(text("""
            INSERT INTO client_payer_links (client_user_id, payer_profile_id, is_default, label)
            VALUES (:client, :payer, :default, :label)
        """), {"client": client_id, "payer": payer_id, "default": is_default, "label": label})
    
    # Якщо is_default - зняти з інших
    if is_default:
        db.execute(text("""
            UPDATE client_payer_links 
            SET is_default = FALSE 
            WHERE client_user_id = :client AND payer_profile_id != :payer
        """), {"client": client_id, "payer": payer_id})
    
    db.commit()
    
    return {"success": True, "message": "Платника прив'язано"}


@router.delete("/{client_id}/payers/{payer_id}/unlink")
async def unlink_payer_from_client(client_id: int, payer_id: int, db: Session = Depends(get_rh_db)):
    """Відв'язати платника від клієнта"""
    
    result = db.execute(text("""
        DELETE FROM client_payer_links 
        WHERE client_user_id = :client AND payer_profile_id = :payer
    """), {"client": client_id, "payer": payer_id})
    db.commit()
    
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Зв'язок не знайдено")
    
    return {"success": True, "message": "Платника відв'язано"}


@router.post("/sync-from-orders")
async def sync_clients_from_orders(db: Session = Depends(get_rh_db)):
    """
    Знайти всі ордери без client_user_id
    і створити/прив'язати клієнтів автоматично.
    """
    # 1. Завантажити всіх існуючих клієнтів у словник
    all_clients = db.execute(text("""
        SELECT id, email_normalized, phone, full_name FROM client_users WHERE is_active = 1
    """)).fetchall()
    
    email_map = {}  # email_normalized -> client_id
    phone_map = {}  # last 9 digits -> client_id
    
    for c in all_clients:
        cid, email_n, phone, name = c[0], (c[1] or '').strip(), (c[2] or '').strip(), c[3]
        if email_n and '@' in email_n:
            email_map[email_n] = cid
        if phone:
            digits = ''.join(ch for ch in phone if ch.isdigit())
            if len(digits) >= 9:
                phone_map[digits[-9:]] = cid
    
    # 2. Знайти всі непов'язані ордери
    result = db.execute(text("""
        SELECT order_id, customer_name, customer_phone, customer_email
        FROM orders
        WHERE (client_user_id IS NULL OR client_user_id = 0)
          AND customer_name IS NOT NULL AND customer_name != ''
        ORDER BY created_at ASC
    """))
    unlinked = result.fetchall()
    
    created = 0
    linked = 0
    errors = 0
    
    for row in unlinked:
        order_id, name, phone, email = row[0], (row[1] or '').strip(), (row[2] or '').strip(), (row[3] or '').strip()
        email_normalized = email.lower().strip() if email else ''
        
        try:
            found_client_id = None
            
            # Пошук по email
            if email_normalized and '@' in email_normalized:
                found_client_id = email_map.get(email_normalized)
            
            # Пошук по телефону
            if not found_client_id and phone:
                digits = ''.join(ch for ch in phone if ch.isdigit())
                if len(digits) >= 9:
                    found_client_id = phone_map.get(digits[-9:])
            
            if not found_client_id and name:
                # Створити нового клієнта
                db.execute(text("""
                    INSERT INTO client_users 
                        (email, email_normalized, full_name, phone, source, is_active, created_at, updated_at)
                    VALUES (:email, :email_norm, :name, :phone, 'opencart', 1, NOW(), NOW())
                """), {
                    "email": email or None,
                    "email_norm": email_normalized,
                    "name": name,
                    "phone": phone or None
                })
                found_client_id = db.execute(text("SELECT LAST_INSERT_ID()")).scalar()
                created += 1
                # Додати в кеш для наступних ордерів
                if email_normalized and '@' in email_normalized:
                    email_map[email_normalized] = found_client_id
                if phone:
                    digits = ''.join(ch for ch in phone if ch.isdigit())
                    if len(digits) >= 9:
                        phone_map[digits[-9:]] = found_client_id
            
            if found_client_id:
                db.execute(text("""
                    UPDATE orders SET client_user_id = :cid WHERE order_id = :oid
                """), {"cid": found_client_id, "oid": order_id})
                linked += 1
                
        except Exception as e:
            errors += 1
            logger.error(f"Error syncing client for order {order_id}: {e}")
            continue
    
    db.commit()
    
    return {
        "success": True,
        "total_unlinked": len(unlinked),
        "clients_created": created,
        "orders_linked": linked,
        "errors": errors
    }


@router.get("/resolve/by-email")
async def resolve_client_by_email(email: str, db: Session = Depends(get_rh_db)):
    """
    Знайти або отримати інформацію про клієнта по email.
    Використовується при checkout в EventTool.
    
    Повертає:
    - exists: чи існує клієнт
    - client: дані клієнта (id, name, phone, email)
    - payers: список платників [{id, type, display_name, tax_mode, is_default}]
    - default_payer_id: ID платника за замовчуванням
    """
    email_normalized = email.lower().strip()
    
    if not email_normalized or '@' not in email_normalized:
        return {
            "exists": False,
            "email": email,
            "error": "Invalid email format"
        }
    
    result = db.execute(text("""
        SELECT id, email, full_name, phone, company_hint, source
        FROM client_users 
        WHERE email_normalized = :email
    """), {"email": email_normalized}).fetchone()
    
    if not result:
        return {
            "exists": False,
            "email": email,
            "email_normalized": email_normalized,
            "client": None,
            "payers": [],
            "default_payer_id": None
        }
    
    client_id = result[0]
    
    # Отримати платників
    payers_result = db.execute(text("""
        SELECT 
            pp.id, pp.type, pp.display_name, pp.tax_mode, pp.edrpou,
            cpl.is_default
        FROM client_payer_links cpl
        JOIN payer_profiles pp ON pp.id = cpl.payer_profile_id
        WHERE cpl.client_user_id = :client_id AND pp.is_active = TRUE
        ORDER BY cpl.is_default DESC, pp.display_name
    """), {"client_id": client_id})
    
    payers = []
    default_payer_id = None
    for p in payers_result:
        payer = {
            "id": p[0],
            "type": p[1],
            "display_name": p[2],
            "tax_mode": p[3],
            "edrpou": p[4],
            "is_default": bool(p[5])
        }
        payers.append(payer)
        if payer["is_default"]:
            default_payer_id = payer["id"]
    
    return {
        "exists": True,
        "client_user_id": client_id,
        "client": {
            "id": client_id,
            "email": result[1],
            "full_name": result[2],
            "phone": result[3],
            "company_hint": result[4],
            "source": result[5]
        },
        "payers": payers,
        "default_payer_id": default_payer_id,
        "payer_status": "ok" if any(p["type"] != "pending" for p in payers) else ("pending" if payers else "missing")
    }
