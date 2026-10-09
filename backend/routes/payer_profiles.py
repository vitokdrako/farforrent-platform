"""
Payer Profiles API - управління реквізитами контрагентів
Підтримка: Фіз особа, ФОП спрощена, ФОП загальна, ТОВ спрощена, ТОВ загальна
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

from database_rentalhub import get_rh_db

router = APIRouter(prefix="/api/payer-profiles", tags=["payer-profiles"])

# ============================================================
# PYDANTIC MODELS
# ============================================================

class PayerProfileCreate(BaseModel):
    """Створення/оновлення профілю платника"""
    type: str  # individual, fop, company, foreign, pending
    display_name: str  # Як показувати в UI
    tax_mode: Optional[str] = "none"  # none/simplified/general/vat
    
    # Юридичні дані
    legal_name: Optional[str] = None  # Юридична назва
    edrpou: Optional[str] = None  # ЄДРПОУ/ІПН
    iban: Optional[str] = None  # IBAN рахунок
    bank_name: Optional[str] = None
    address: Optional[str] = None
    
    # Підписант
    signatory_name: Optional[str] = None  # ПІБ підписанта
    signatory_basis: Optional[str] = None  # "Статуту" / "Довіреності"
    
    # Контакти для документів
    email_for_docs: Optional[str] = None
    phone_for_docs: Optional[str] = None
    
    # Інше
    details_json: Optional[dict] = None  # Додаткові реквізити
    note: Optional[str] = None

class PayerProfileResponse(BaseModel):
    id: int
    payer_type: str
    payer_type_label: str
    company_name: Optional[str]
    edrpou: Optional[str]
    iban: Optional[str]
    bank_name: Optional[str]
    director_name: Optional[str]
    address: Optional[str]
    tax_number: Optional[str]
    is_vat_payer: bool
    phone: Optional[str]
    email: Optional[str]
    note: Optional[str]
    created_at: Optional[str]

# ============================================================
# CONSTANTS
# ============================================================

PAYER_TYPES = {
    "individual": {
        "label": "Фізична особа",
        "tax_system": "none",
        "documents": ["quote", "invoice_offer"],
        "requires_edrpou": False,
        "vat_applicable": False
    },
    "fop": {
        "label": "ФОП",
        "tax_system": "varies",  # simplified/general/vat - визначається tax_mode
        "documents": ["quote", "invoice_offer", "master_agreement", "annex", "service_act"],
        "requires_edrpou": True,
        "vat_applicable": True  # Залежить від tax_mode
    },
    "company": {
        "label": "Юридична особа",
        "tax_system": "varies",
        "documents": ["quote", "invoice_offer", "master_agreement", "annex", "service_act", "goods_invoice"],
        "requires_edrpou": True,
        "vat_applicable": True
    },
    "foreign": {
        "label": "Нерезидент",
        "tax_system": "foreign",
        "documents": ["quote", "invoice_offer", "contract_foreign"],
        "requires_edrpou": False,
        "vat_applicable": False
    },
    "pending": {
        "label": "Вкажу пізніше",
        "tax_system": None,
        "documents": ["quote"],  # Тільки кошторис
        "requires_edrpou": False,
        "vat_applicable": False
    }
}

# Tax modes для ФОП та компаній
TAX_MODES = {
    "none": {"label": "Без оподаткування", "vat": False},
    "simplified": {"label": "Спрощена система (1-3 група)", "vat": False},
    "general": {"label": "Загальна система", "vat": False},
    "vat": {"label": "Платник ПДВ", "vat": True}
}

# ============================================================
# DATABASE INIT
# ============================================================

def ensure_table_exists(db: Session):
    """Створення таблиці payer_profiles якщо не існує"""
    try:
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS payer_profiles (
                id INT AUTO_INCREMENT PRIMARY KEY,
                payer_type VARCHAR(50) NOT NULL DEFAULT 'individual',
                company_name VARCHAR(255),
                edrpou VARCHAR(20),
                iban VARCHAR(34),
                bank_name VARCHAR(255),
                director_name VARCHAR(255),
                address TEXT,
                tax_number VARCHAR(20),
                is_vat_payer BOOLEAN DEFAULT FALSE,
                phone VARCHAR(50),
                email VARCHAR(100),
                note TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_payer_type (payer_type),
                INDEX idx_edrpou (edrpou)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """))
        
        # Додаємо поле payer_profile_id до orders якщо не існує
        try:
            db.execute(text("""
                ALTER TABLE orders ADD COLUMN payer_profile_id INT NULL,
                ADD FOREIGN KEY (payer_profile_id) REFERENCES payer_profiles(id) ON DELETE SET NULL
            """))
        except:
            pass  # Поле вже існує
        
        db.commit()
    except Exception as e:
        print(f"Table setup warning: {e}")

# ============================================================
# API ENDPOINTS
# ============================================================

@router.get("/types")
async def get_payer_types():
    """Отримати всі типи платників з описом"""
    return {
        "types": [
            {
                "value": key,
                "label": val["label"],
                "requires_edrpou": val["requires_edrpou"],
                "documents": val["documents"],
                "vat_applicable": val["vat_applicable"]
            }
            for key, val in PAYER_TYPES.items()
        ],
        "tax_modes": [
            {"value": key, "label": val["label"], "vat": val["vat"]}
            for key, val in TAX_MODES.items()
        ]
    }

@router.get("")
async def list_payer_profiles(
    payer_type: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_rh_db)
):
    """Список профілів платників"""
    ensure_table_exists(db)
    
    query = """
        SELECT id, payer_type, company_name, edrpou, iban, bank_name, 
               director_name, address, tax_number, is_vat_payer, 
               phone, email, note, created_at
        FROM payer_profiles 
        WHERE is_active = TRUE
    """
    params = {"limit": limit}
    
    if payer_type:
        query += " AND payer_type = :payer_type"
        params["payer_type"] = payer_type
    
    if search:
        query += " AND (company_name LIKE :search OR edrpou LIKE :search OR director_name LIKE :search)"
        params["search"] = f"%{search}%"
    
    query += " ORDER BY created_at DESC LIMIT :limit"
    
    result = db.execute(text(query), params)
    
    profiles = []
    for row in result:
        payer_type_info = PAYER_TYPES.get(row[1], {"label": row[1]})
        profiles.append({
            "id": row[0],
            "payer_type": row[1],
            "payer_type_label": payer_type_info["label"],
            "company_name": row[2],
            "edrpou": row[3],
            "iban": row[4],
            "bank_name": row[5],
            "director_name": row[6],
            "address": row[7],
            "tax_number": row[8],
            "is_vat_payer": bool(row[9]),
            "phone": row[10],
            "email": row[11],
            "note": row[12],
            "created_at": row[13].isoformat() if row[13] else None
        })
    
    return {"profiles": profiles, "total": len(profiles)}

@router.get("/{profile_id}")
async def get_payer_profile(profile_id: int, db: Session = Depends(get_rh_db)):
    """Отримати профіль платника за ID"""
    ensure_table_exists(db)
    
    result = db.execute(text("""
        SELECT id, payer_type, company_name, edrpou, iban, bank_name, 
               director_name, address, tax_number, is_vat_payer, 
               phone, email, note, created_at
        FROM payer_profiles 
        WHERE id = :id AND is_active = TRUE
    """), {"id": profile_id})
    
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Профіль не знайдено")
    
    payer_type_info = PAYER_TYPES.get(row[1], {"label": row[1]})
    return {
        "id": row[0],
        "payer_type": row[1],
        "payer_type_label": payer_type_info["label"],
        "company_name": row[2],
        "edrpou": row[3],
        "iban": row[4],
        "bank_name": row[5],
        "director_name": row[6],
        "address": row[7],
        "tax_number": row[8],
        "is_vat_payer": bool(row[9]),
        "phone": row[10],
        "email": row[11],
        "note": row[12],
        "created_at": row[13].isoformat() if row[13] else None
    }

@router.post("")
async def create_payer_profile(data: PayerProfileCreate, db: Session = Depends(get_rh_db)):
    """Створити новий профіль платника"""
    ensure_table_exists(db)
    
    # Валідація типу
    if data.type not in PAYER_TYPES:
        raise HTTPException(status_code=400, detail=f"Невідомий тип платника: {data.type}")
    
    # Визначаємо is_vat_payer на основі tax_mode
    is_vat = data.tax_mode == "vat"
    
    try:
        # Зберігаємо в таблицю з маппінгом нових полів на старі колонки
        db.execute(text("""
            INSERT INTO payer_profiles 
            (payer_type, company_name, edrpou, iban, bank_name, director_name, 
             address, tax_number, is_vat_payer, phone, email, note,
             type, display_name, tax_mode, legal_name, signatory_name, signatory_basis,
             email_for_docs, phone_for_docs, details_json)
            VALUES 
            (:payer_type, :company_name, :edrpou, :iban, :bank_name, :director_name,
             :address, :tax_number, :is_vat_payer, :phone, :email, :note,
             :type, :display_name, :tax_mode, :legal_name, :signatory_name, :signatory_basis,
             :email_for_docs, :phone_for_docs, :details_json)
        """), {
            # Старі поля (для сумісності)
            "payer_type": data.type,
            "company_name": data.legal_name or data.display_name,
            "edrpou": data.edrpou,
            "iban": data.iban,
            "bank_name": data.bank_name,
            "director_name": data.signatory_name,
            "address": data.address,
            "tax_number": data.edrpou,  # ІПН = ЄДРПОУ для ФОП
            "is_vat_payer": is_vat,
            "phone": data.phone_for_docs,
            "email": data.email_for_docs,
            "note": data.note,
            # Нові поля
            "type": data.type,
            "display_name": data.display_name,
            "tax_mode": data.tax_mode,
            "legal_name": data.legal_name,
            "signatory_name": data.signatory_name,
            "signatory_basis": data.signatory_basis,
            "email_for_docs": data.email_for_docs,
            "phone_for_docs": data.phone_for_docs,
            "details_json": str(data.details_json) if data.details_json else None
        })
        
        profile_id = db.execute(text("SELECT LAST_INSERT_ID()")).fetchone()[0]
        db.commit()
        
        # Повернути створений профіль
        return {
            "success": True, 
            "id": profile_id,
            "profile_id": profile_id,
            "type": data.type,
            "display_name": data.display_name
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/{profile_id}")
@router.patch("/{profile_id}")
async def update_payer_profile(profile_id: int, data: PayerProfileCreate, db: Session = Depends(get_rh_db)):
    """Оновити профіль платника"""
    ensure_table_exists(db)
    
    # Валідація типу
    if data.type not in PAYER_TYPES:
        raise HTTPException(status_code=400, detail=f"Невідомий тип платника: {data.type}")
    
    # Визначаємо is_vat_payer на основі tax_mode
    is_vat = data.tax_mode == "vat"
    
    try:
        db.execute(text("""
            UPDATE payer_profiles SET
                payer_type = :payer_type,
                company_name = :company_name,
                edrpou = :edrpou,
                iban = :iban,
                bank_name = :bank_name,
                director_name = :director_name,
                address = :address,
                tax_number = :tax_number,
                is_vat_payer = :is_vat_payer,
                phone = :phone,
                email = :email,
                note = :note,
                type = :type,
                display_name = :display_name,
                tax_mode = :tax_mode,
                legal_name = :legal_name,
                signatory_name = :signatory_name,
                signatory_basis = :signatory_basis,
                email_for_docs = :email_for_docs,
                phone_for_docs = :phone_for_docs,
                details_json = :details_json
            WHERE id = :id
        """), {
            "id": profile_id,
            # Старі поля (для сумісності)
            "payer_type": data.type,
            "company_name": data.legal_name or data.display_name,
            "edrpou": data.edrpou,
            "iban": data.iban,
            "bank_name": data.bank_name,
            "director_name": data.signatory_name,
            "address": data.address,
            "tax_number": data.edrpou,
            "is_vat_payer": is_vat,
            "phone": data.phone_for_docs,
            "email": data.email_for_docs,
            "note": data.note,
            # Нові поля
            "type": data.type,
            "display_name": data.display_name,
            "tax_mode": data.tax_mode,
            "legal_name": data.legal_name,
            "signatory_name": data.signatory_name,
            "signatory_basis": data.signatory_basis,
            "email_for_docs": data.email_for_docs,
            "phone_for_docs": data.phone_for_docs,
            "details_json": str(data.details_json) if data.details_json else None
        })
        db.commit()
        
        return {"success": True, "id": profile_id}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{profile_id}")
async def delete_payer_profile(profile_id: int, db: Session = Depends(get_rh_db)):
    """Видалити (деактивувати) профіль платника"""
    try:
        db.execute(text("UPDATE payer_profiles SET is_active = FALSE WHERE id = :id"), {"id": profile_id})
        db.commit()
        return {"success": True}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/order/{order_id}/assign/{profile_id}")
async def assign_payer_to_order(order_id: int, profile_id: int, db: Session = Depends(get_rh_db)):
    """Прив'язати профіль платника до замовлення"""
    ensure_table_exists(db)
    
    try:
        db.execute(text("""
            UPDATE orders SET payer_profile_id = :profile_id WHERE order_id = :order_id
        """), {"profile_id": profile_id, "order_id": order_id})
        db.commit()
        return {"success": True}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/order/{order_id}")
async def get_order_payer(order_id: int, db: Session = Depends(get_rh_db)):
    """Отримати профіль платника для замовлення"""
    ensure_table_exists(db)
    
    # Спробуємо отримати payer_profile_id
    try:
        result = db.execute(text("""
            SELECT payer_profile_id FROM orders WHERE order_id = :order_id
        """), {"order_id": order_id})
        row = result.fetchone()
        
        if not row or not row[0]:
            return {"profile": None, "payer_type": "individual"}
        
        profile = await get_payer_profile(row[0], db)
        return {"profile": profile, "payer_type": profile["payer_type"]}
    except Exception as e:
        # Якщо колонки ще немає
        return {"profile": None, "payer_type": "individual"}
