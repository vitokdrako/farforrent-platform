"""
Company Profiles API — централізоване сховище наших юр. осіб (landlord side).
Замовлення можуть посилатися на company_profile_id (наша сторона) +
payer_profile_id (клієнтська сторона).
"""
from fastapi import APIRouter, Depends, HTTPException, Body
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session
from typing import Optional, List
import json
import logging

from database_rentalhub import get_rh_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin/company-profiles", tags=["company-profiles"])


# ============================================================================
# Pydantic
# ============================================================================
class CompanyProfilePayload(BaseModel):
    code: Optional[str] = None
    display_name: str = Field(..., min_length=1, max_length=255)
    legal_name: str = Field(..., min_length=1, max_length=500)
    payer_type: str = "fop_simple"
    tax_status: Optional[str] = None
    edrpou: Optional[str] = None
    iban: Optional[str] = None
    bank_name: Optional[str] = None
    address: Optional[str] = None
    warehouse_address: Optional[str] = None
    director_name: Optional[str] = None
    signer_name: Optional[str] = None
    signer_role: Optional[str] = None
    is_vat_payer: bool = False
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    logo_url: Optional[str] = None
    stamp_url: Optional[str] = None
    is_default: bool = False
    is_active: bool = True
    sort_order: int = 0


# ============================================================================
# Helpers
# ============================================================================
def _row_to_dict(row) -> dict:
    return {
        "id": row[0], "code": row[1], "display_name": row[2], "legal_name": row[3],
        "payer_type": row[4], "tax_status": row[5], "edrpou": row[6], "iban": row[7],
        "bank_name": row[8], "address": row[9], "warehouse_address": row[10],
        "director_name": row[11], "signer_name": row[12], "signer_role": row[13],
        "is_vat_payer": bool(row[14]), "phone": row[15], "email": row[16],
        "website": row[17], "logo_url": row[18], "stamp_url": row[19],
        "is_default": bool(row[20]), "is_active": bool(row[21]), "sort_order": row[22],
        "created_at": row[23].isoformat() if row[23] else None,
        "updated_at": row[24].isoformat() if row[24] else None,
    }


_SELECT_COLS = """
    id, code, display_name, legal_name, payer_type, tax_status, edrpou, iban,
    bank_name, address, warehouse_address, director_name, signer_name, signer_role,
    is_vat_payer, phone, email, website, logo_url, stamp_url,
    is_default, is_active, sort_order, created_at, updated_at
"""


# ============================================================================
# Routes
# ============================================================================
@router.get("")
async def list_company_profiles(
    only_active: bool = True,
    db: Session = Depends(get_rh_db),
):
    where = "WHERE is_active = 1" if only_active else ""
    rows = db.execute(text(f"""
        SELECT {_SELECT_COLS} FROM company_profiles {where}
        ORDER BY is_default DESC, sort_order ASC, display_name ASC
    """)).fetchall()
    return {"profiles": [_row_to_dict(r) for r in rows]}


@router.get("/default")
async def get_default_profile(db: Session = Depends(get_rh_db)):
    row = db.execute(text(f"""
        SELECT {_SELECT_COLS} FROM company_profiles
        WHERE is_default = 1 AND is_active = 1 LIMIT 1
    """)).fetchone()
    if not row:
        row = db.execute(text(f"""
            SELECT {_SELECT_COLS} FROM company_profiles
            WHERE is_active = 1 ORDER BY sort_order ASC, id ASC LIMIT 1
        """)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="No active company profile found")
    return _row_to_dict(row)


@router.get("/{profile_id}")
async def get_company_profile(profile_id: int, db: Session = Depends(get_rh_db)):
    row = db.execute(text(f"""
        SELECT {_SELECT_COLS} FROM company_profiles WHERE id = :id
    """), {"id": profile_id}).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Profile not found")
    return _row_to_dict(row)


def _make_code(display_name: str) -> str:
    import re, unicodedata
    s = unicodedata.normalize('NFKD', display_name).encode('ascii', 'ignore').decode().lower()
    s = re.sub(r'[^a-z0-9]+', '_', s).strip('_') or 'company'
    return s[:48]


@router.post("")
async def create_company_profile(
    payload: CompanyProfilePayload,
    db: Session = Depends(get_rh_db),
):
    code = (payload.code or _make_code(payload.display_name)).lower()
    # Ensure unique
    n = 0
    base = code
    while db.execute(text("SELECT 1 FROM company_profiles WHERE code = :c"),
                     {"c": code}).scalar():
        n += 1
        code = f"{base}_{n}"

    # If is_default → reset others
    if payload.is_default:
        db.execute(text("UPDATE company_profiles SET is_default = 0 WHERE is_default = 1"))

    db.execute(text("""
        INSERT INTO company_profiles
          (code, display_name, legal_name, payer_type, tax_status, edrpou, iban, bank_name,
           address, warehouse_address, director_name, signer_name, signer_role,
           is_vat_payer, phone, email, website, logo_url, stamp_url,
           is_default, is_active, sort_order)
        VALUES (:code, :dn, :ln, :pt, :ts, :ed, :iban, :bn, :addr, :wh, :dir, :sn, :sr,
                :vat, :phone, :email, :web, :logo, :stamp, :def, :act, :so)
    """), {
        "code": code, "dn": payload.display_name, "ln": payload.legal_name,
        "pt": payload.payer_type, "ts": payload.tax_status, "ed": payload.edrpou,
        "iban": payload.iban, "bn": payload.bank_name, "addr": payload.address,
        "wh": payload.warehouse_address, "dir": payload.director_name,
        "sn": payload.signer_name, "sr": payload.signer_role,
        "vat": 1 if payload.is_vat_payer else 0,
        "phone": payload.phone, "email": payload.email, "web": payload.website,
        "logo": payload.logo_url, "stamp": payload.stamp_url,
        "def": 1 if payload.is_default else 0,
        "act": 1 if payload.is_active else 0,
        "so": payload.sort_order,
    })
    db.commit()
    new_id = db.execute(text("SELECT LAST_INSERT_ID()")).scalar()
    return await get_company_profile(new_id, db)


@router.put("/{profile_id}")
@router.patch("/{profile_id}")
async def update_company_profile(
    profile_id: int,
    payload: dict = Body(...),
    db: Session = Depends(get_rh_db),
):
    exists = db.execute(text("SELECT 1 FROM company_profiles WHERE id = :id"),
                        {"id": profile_id}).scalar()
    if not exists:
        raise HTTPException(status_code=404, detail="Profile not found")

    if payload.get("is_default"):
        db.execute(text("UPDATE company_profiles SET is_default = 0 WHERE id != :id AND is_default = 1"),
                   {"id": profile_id})

    allowed = {"display_name", "legal_name", "payer_type", "tax_status", "edrpou",
               "iban", "bank_name", "address", "warehouse_address",
               "director_name", "signer_name", "signer_role", "is_vat_payer",
               "phone", "email", "website", "logo_url", "stamp_url",
               "is_default", "is_active", "sort_order"}
    sets = []
    params = {"id": profile_id}
    for k, v in payload.items():
        if k in allowed:
            sets.append(f"{k} = :{k}")
            params[k] = (1 if v else 0) if isinstance(v, bool) else v
    if not sets:
        raise HTTPException(status_code=400, detail="No fields to update")
    db.execute(text(f"UPDATE company_profiles SET {', '.join(sets)} WHERE id = :id"), params)
    db.commit()
    return await get_company_profile(profile_id, db)


@router.delete("/{profile_id}")
async def delete_company_profile(profile_id: int, db: Session = Depends(get_rh_db)):
    # Soft-delete (deactivate) — preserves historical data
    db.execute(text("UPDATE company_profiles SET is_active = 0 WHERE id = :id"),
               {"id": profile_id})
    db.commit()
    return {"ok": True, "deactivated": profile_id}


@router.post("/order/{order_id}/assign/{profile_id}")
async def assign_to_order(order_id: int, profile_id: int, db: Session = Depends(get_rh_db)):
    """Прив'язати company_profile до замовлення + зберегти snapshot."""
    profile = db.execute(text(f"""
        SELECT {_SELECT_COLS} FROM company_profiles WHERE id = :id AND is_active = 1
    """), {"id": profile_id}).fetchone()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found or inactive")

    snapshot = _row_to_dict(profile)
    snap_json = json.dumps(snapshot, ensure_ascii=False, default=str)

    db.execute(text("""
        UPDATE orders SET company_profile_id = :pid, company_snapshot_json = :snap
        WHERE order_id = :oid
    """), {"pid": profile_id, "snap": snap_json, "oid": order_id})
    db.commit()
    return {"ok": True, "order_id": order_id, "profile_id": profile_id}


@router.get("/order/{order_id}")
async def get_assigned_to_order(order_id: int, db: Session = Depends(get_rh_db)):
    """Витягнути prefer snapshot з замовлення; інакше — live з company_profiles."""
    row = db.execute(text("""
        SELECT company_profile_id, company_snapshot_json FROM orders WHERE order_id = :oid
    """), {"oid": order_id}).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Order not found")

    if row[1]:
        try:
            data = json.loads(row[1]) if isinstance(row[1], str) else row[1]
            return {"source": "snapshot", "profile": data}
        except Exception:
            pass
    if row[0]:
        return {"source": "live", "profile": await get_company_profile(row[0], db)}
    return {"source": "default", "profile": await get_default_profile(db)}
