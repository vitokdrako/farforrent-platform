"""
Master Agreements API - Рамкові договори
Phase 3: Documents Engine
Updated: Now supports client_user_id (primary) and payer_profile_id (legacy)
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime, date, timedelta
from typing import Optional, List
from pydantic import BaseModel
import json

from database_rentalhub import get_rh_db

router = APIRouter(prefix="/api/agreements", tags=["master-agreements"])


# ============================================================
# PYDANTIC MODELS
# ============================================================

class MasterAgreementCreate(BaseModel):
    client_user_id: Optional[int] = None  # Primary - link to client
    payer_profile_id: Optional[int] = None  # Legacy - for backward compatibility
    executor_type: str = "tov"  # "tov" = ТОВ ФАРФОР РЕНТ, "fop" = ФОП Николенко
    contract_date: Optional[str] = None  # ISO date for contract, default = today
    valid_months: int = 12
    note: Optional[str] = None


class MasterAgreementUpdate(BaseModel):
    status: Optional[str] = None  # draft, sent, signed, expired
    signed_at: Optional[str] = None
    note: Optional[str] = None


# ============================================================
# EXECUTOR DATA
# ============================================================

EXECUTORS = {
    "tov": {
        "name": "ТОВ «ФАРФОР РЕНТ»",
        "short_name": "ТОВ «ФАРФОР РЕНТ»",
        "edrpou": "44651557",
        "address": "02000, м. Київ, вул. Магнітогорська, буд. 1, корп. 34",
        "bank": "АТ КБ «ПРИВАТБАНК»",
        "iban": "UA913052990000026002015020709",
        "director": "Драко В.А.",
        "tax_status": "платник податку на прибуток на загальних умовах"
    },
    "fop": {
        "name": "ФОП Николенко Наталя Станіславівна",
        "short_name": "ФОП Николенко Н.С.",
        "edrpou": "3606801844",
        "address": "02000, м. Київ, вул. Магнітогорська, буд. 1, корп. 34",
        "bank": "АТ «УНІВЕРСАЛ БАНК»",
        "iban": "UA043220010000026003340091618",
        "mfo": "322001",
        "director": None,
        "tax_status": "платник єдиного податку"
    }
}


# ============================================================
# HELPER: Generate Contract Number (new format: DDMMYYYY-N)
# ============================================================

def generate_contract_number(db: Session, contract_date: date) -> str:
    """Generate unique contract number: DDMMYYYY-N"""
    date_str = contract_date.strftime("%d%m%Y")
    
    # Count existing contracts for this date
    result = db.execute(text("""
        SELECT COUNT(*) FROM master_agreements 
        WHERE DATE(valid_from) = :contract_date
    """), {"contract_date": contract_date})
    seq = result.fetchone()[0] + 1
    
    return f"{date_str}-{seq}"


# ============================================================
# LIST AGREEMENTS
# ============================================================

@router.get("")
async def list_agreements(
    payer_profile_id: Optional[int] = None,
    status: Optional[str] = None,
    active_only: bool = False,
    db: Session = Depends(get_rh_db)
):
    """List master agreements with filters"""
    query = """
        SELECT 
            ma.id, ma.payer_profile_id, ma.contract_number, ma.template_version,
            ma.signed_at, ma.valid_from, ma.valid_until, ma.status,
            ma.created_at, ma.note,
            pp.company_name, pp.payer_type, pp.director_name
        FROM master_agreements ma
        LEFT JOIN payer_profiles pp ON pp.id = ma.payer_profile_id
        WHERE 1=1
    """
    params = {}
    
    if payer_profile_id:
        query += " AND ma.payer_profile_id = :payer_profile_id"
        params["payer_profile_id"] = payer_profile_id
    
    if status:
        query += " AND ma.status = :status"
        params["status"] = status
    
    if active_only:
        query += " AND ma.status = 'signed' AND ma.valid_until >= CURDATE()"
    
    query += " ORDER BY ma.created_at DESC"
    
    result = db.execute(text(query), params)
    
    agreements = []
    for row in result:
        agreements.append({
            "id": row[0],
            "payer_profile_id": row[1],
            "contract_number": row[2],
            "template_version": row[3],
            "signed_at": row[4].isoformat() if row[4] else None,
            "valid_from": row[5].isoformat() if row[5] else None,
            "valid_until": row[6].isoformat() if row[6] else None,
            "status": row[7],
            "created_at": row[8].isoformat() if row[8] else None,
            "note": row[9],
            "payer": {
                "company_name": row[10],
                "payer_type": row[11],
                "director_name": row[12]
            }
        })
    
    return {"agreements": agreements}


# ============================================================
# GET SINGLE AGREEMENT
# ============================================================

@router.get("/{agreement_id}")
async def get_agreement(agreement_id: int, db: Session = Depends(get_rh_db)):
    """Get single master agreement with full details"""
    result = db.execute(text("""
        SELECT 
            ma.id, ma.payer_profile_id, ma.contract_number, ma.template_version,
            ma.signed_at, ma.valid_from, ma.valid_until, ma.status,
            ma.snapshot_json, ma.pdf_path, ma.created_at, ma.note,
            pp.company_name, pp.payer_type, pp.director_name, pp.edrpou,
            pp.iban, pp.bank_name, pp.address
        FROM master_agreements ma
        LEFT JOIN payer_profiles pp ON pp.id = ma.payer_profile_id
        WHERE ma.id = :id
    """), {"id": agreement_id})
    
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Agreement not found")
    
    # Count annexes
    annex_count = db.execute(text("""
        SELECT COUNT(*) FROM order_annexes WHERE master_agreement_id = :id
    """), {"id": agreement_id}).fetchone()[0]
    
    return {
        "id": row[0],
        "payer_profile_id": row[1],
        "contract_number": row[2],
        "template_version": row[3],
        "signed_at": row[4].isoformat() if row[4] else None,
        "valid_from": row[5].isoformat() if row[5] else None,
        "valid_until": row[6].isoformat() if row[6] else None,
        "status": row[7],
        "snapshot_json": json.loads(row[8]) if row[8] else None,
        "pdf_path": row[9],
        "created_at": row[10].isoformat() if row[10] else None,
        "note": row[11],
        "payer": {
            "company_name": row[12],
            "payer_type": row[13],
            "director_name": row[14],
            "edrpou": row[15],
            "iban": row[16],
            "bank_name": row[17],
            "address": row[18]
        },
        "annex_count": annex_count
    }


# ============================================================
# CREATE AGREEMENT
# ============================================================

@router.post("/create")
async def create_agreement(data: MasterAgreementCreate, db: Session = Depends(get_rh_db)):
    """Create new master agreement for CLIENT"""
    
    # Must have client_user_id
    if not data.client_user_id:
        raise HTTPException(status_code=400, detail="client_user_id required")
    
    # Get client data
    client = db.execute(text("""
        SELECT id, full_name, email, phone, payer_type, tax_id, bank_details
        FROM client_users WHERE id = :id AND is_active = 1
    """), {"id": data.client_user_id}).fetchone()
    
    if not client:
        raise HTTPException(status_code=400, detail="Клієнта не знайдено")
    
    # Check for existing active agreement for this CLIENT
    existing = db.execute(text("""
        SELECT id, contract_number FROM master_agreements 
        WHERE client_user_id = :cid AND status IN ('draft', 'sent', 'signed')
        AND (valid_until IS NULL OR valid_until >= CURDATE())
    """), {"cid": data.client_user_id}).fetchone()
    
    if existing:
        raise HTTPException(
            status_code=400, 
            detail=f"Активний договір вже існує: {existing[1]}"
        )
    
    # Get executor data
    executor_type = data.executor_type if data.executor_type in EXECUTORS else "tov"
    executor = EXECUTORS[executor_type]
    
    # Calculate dates
    contract_date = datetime.fromisoformat(data.contract_date).date() if data.contract_date else date.today()
    valid_until = contract_date + timedelta(days=data.valid_months * 30)
    
    # Generate contract number (DDMMYYYY-N format)
    contract_number = generate_contract_number(db, contract_date)
    
    # Build snapshot with all contract data
    snapshot = {
        "contract_number": contract_number,
        "contract_date": contract_date.isoformat(),
        "valid_from": contract_date.isoformat(),
        "valid_until": valid_until.isoformat(),
        "executor_type": executor_type,
        "executor": executor,
        "generated_at": datetime.now().isoformat(),
        "client": {
            "id": client[0],
            "full_name": client[1],
            "email": client[2],
            "phone": client[3],
            "payer_type": client[4],  # individual, fop, tov
            "tax_id": client[5],
            "bank_details": json.loads(client[6]) if client[6] else None
        }
    }
    
    try:
        db.execute(text("""
            INSERT INTO master_agreements (
                client_user_id, payer_profile_id, contract_number, template_version,
                valid_from, valid_until, status, snapshot_json, note
            ) VALUES (
                :client_user_id, NULL, :contract_number, :executor_type,
                :valid_from, :valid_until, 'draft', :snapshot_json, :note
            )
        """), {
            "client_user_id": data.client_user_id,
            "contract_number": contract_number,
            "executor_type": executor_type,
            "valid_from": contract_date,
            "valid_until": valid_until,
            "snapshot_json": json.dumps(snapshot, ensure_ascii=False),
            "note": data.note
        })
        
        agreement_id = db.execute(text("SELECT LAST_INSERT_ID()")).fetchone()[0]
        db.commit()
        
        return {
            "success": True,
            "agreement_id": agreement_id,
            "contract_number": contract_number,
            "valid_from": contract_date.isoformat(),
            "valid_until": valid_until.isoformat()
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# UPDATE AGREEMENT STATUS
# ============================================================

@router.put("/{agreement_id}")
async def update_agreement(
    agreement_id: int, 
    data: MasterAgreementUpdate, 
    db: Session = Depends(get_rh_db)
):
    """Update agreement status"""
    
    # Check exists
    existing = db.execute(text("""
        SELECT status FROM master_agreements WHERE id = :id
    """), {"id": agreement_id}).fetchone()
    
    if not existing:
        raise HTTPException(status_code=404, detail="Agreement not found")
    
    updates = []
    params = {"id": agreement_id}
    
    if data.status:
        valid_statuses = ["draft", "sent", "signed", "expired", "cancelled"]
        if data.status not in valid_statuses:
            raise HTTPException(status_code=400, detail=f"Invalid status: {data.status}")
        updates.append("status = :status")
        params["status"] = data.status
        
        # Auto-set signed_at when marking as signed
        if data.status == "signed" and not data.signed_at:
            updates.append("signed_at = NOW()")
    
    if data.signed_at:
        updates.append("signed_at = :signed_at")
        params["signed_at"] = datetime.fromisoformat(data.signed_at)
    
    if data.note is not None:
        updates.append("note = :note")
        params["note"] = data.note
    
    if not updates:
        return {"success": True, "message": "Nothing to update"}
    
    try:
        db.execute(text(f"""
            UPDATE master_agreements SET {', '.join(updates)} WHERE id = :id
        """), params)
        db.commit()
        return {"success": True}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# GET ACTIVE AGREEMENT FOR PAYER
# ============================================================

@router.get("/active/{payer_profile_id}")
async def get_active_agreement(payer_profile_id: int, db: Session = Depends(get_rh_db)):
    """Get active (signed, not expired) agreement for payer, or latest draft if none signed"""
    
    # First try to find signed agreement
    result = db.execute(text("""
        SELECT 
            id, contract_number, valid_from, valid_until, signed_at, status, pdf_path
        FROM master_agreements 
        WHERE payer_profile_id = :pid 
        AND status = 'signed'
        AND valid_until >= CURDATE()
        ORDER BY signed_at DESC
        LIMIT 1
    """), {"pid": payer_profile_id})
    
    row = result.fetchone()
    
    # If no signed, try to find draft
    if not row:
        result = db.execute(text("""
            SELECT 
                id, contract_number, valid_from, valid_until, signed_at, status, pdf_path
            FROM master_agreements 
            WHERE payer_profile_id = :pid 
            AND status IN ('draft', 'sent')
            ORDER BY created_at DESC
            LIMIT 1
        """), {"pid": payer_profile_id})
        row = result.fetchone()
    
    if not row:
        return {"exists": False, "message": "No agreement found"}
    
    return {
        "exists": True,
        "id": row[0],
        "contract_number": row[1],
        "valid_from": row[2].isoformat() if row[2] else None,
        "valid_until": row[3].isoformat() if row[3] else None,
        "signed_at": row[4].isoformat() if row[4] else None,
        "status": row[5],
        "pdf_path": row[6]
    }


# ============================================================
# GET ACTIVE AGREEMENT FOR CLIENT (NEW)
# ============================================================

@router.get("/client/{client_user_id}")
async def get_client_agreement(client_user_id: int, db: Session = Depends(get_rh_db)):
    """Get active agreement for client (or terminated if no active)"""
    
    # Ensure columns exist
    has_terminated_cols = True
    try:
        db.execute(text("SELECT terminated_at FROM master_agreements LIMIT 0"))
    except Exception:
        has_terminated_cols = False
        try:
            db.execute(text("""
                ALTER TABLE master_agreements 
                ADD COLUMN terminated_at DATETIME NULL,
                ADD COLUMN termination_reason TEXT NULL
            """))
            db.commit()
            has_terminated_cols = True
        except Exception:
            pass
    
    terminated_select = ", ma.terminated_at, ma.termination_reason" if has_terminated_cols else ", NULL, NULL"
    
    # First try to find signed agreement
    result = db.execute(text(f"""
        SELECT 
            id, contract_number, valid_from, valid_until, signed_at, status, pdf_path {terminated_select}
        FROM master_agreements ma
        WHERE client_user_id = :cid 
        AND status = 'signed'
        AND valid_until >= CURDATE()
        ORDER BY signed_at DESC
        LIMIT 1
    """), {"cid": client_user_id})
    
    row = result.fetchone()
    
    # If no signed, try to find draft
    if not row:
        result = db.execute(text(f"""
            SELECT 
                id, contract_number, valid_from, valid_until, signed_at, status, pdf_path {terminated_select}
            FROM master_agreements ma
            WHERE client_user_id = :cid 
            AND status IN ('draft', 'sent')
            ORDER BY created_at DESC
            LIMIT 1
        """), {"cid": client_user_id})
        row = result.fetchone()
    
    # If no active/draft, check for terminated (show most recent)
    if not row:
        terminated_order = "terminated_at DESC, created_at DESC" if has_terminated_cols else "created_at DESC"
        result = db.execute(text(f"""
            SELECT 
                id, contract_number, valid_from, valid_until, signed_at, status, pdf_path {terminated_select}
            FROM master_agreements ma
            WHERE client_user_id = :cid 
            AND status = 'terminated'
            ORDER BY {terminated_order}
            LIMIT 1
        """), {"cid": client_user_id})
        row = result.fetchone()
    
    if not row:
        return {"exists": False, "message": "Договір не знайдено"}
    
    return {
        "exists": True,
        "id": row[0],
        "contract_number": row[1],
        "valid_from": row[2].isoformat() if row[2] else None,
        "valid_until": row[3].isoformat() if row[3] else None,
        "signed_at": row[4].isoformat() if row[4] else None,
        "status": row[5],
        "pdf_path": row[6],
        "terminated_at": row[7].isoformat() if row[7] else None,
        "termination_reason": row[8] if len(row) > 8 else None
    }


# ============================================================
# SIGN AGREEMENT (mark as signed)
# ============================================================

class SignAgreementRequest(BaseModel):
    signed_by: str
    signed_at: Optional[str] = None  # ISO date, default = now

@router.post("/{agreement_id}/sign")
async def sign_agreement(
    agreement_id: int,
    data: SignAgreementRequest,
    db: Session = Depends(get_rh_db)
):
    """Sign a master agreement and set it as active for the payer"""
    
    # Get agreement
    agreement = db.execute(text("""
        SELECT id, payer_profile_id, contract_number, status
        FROM master_agreements WHERE id = :id
    """), {"id": agreement_id}).fetchone()
    
    if not agreement:
        raise HTTPException(status_code=404, detail="Agreement not found")
    
    if agreement[3] not in ("draft", "sent"):
        raise HTTPException(status_code=400, detail=f"Cannot sign agreement with status: {agreement[3]}")
    
    signed_at = datetime.fromisoformat(data.signed_at) if data.signed_at else datetime.now()
    
    try:
        # Update agreement status
        db.execute(text("""
            UPDATE master_agreements 
            SET status = 'signed', signed_at = :signed_at, note = CONCAT(IFNULL(note, ''), '\nПідписано: ', :signed_by)
            WHERE id = :id
        """), {
            "id": agreement_id,
            "signed_at": signed_at,
            "signed_by": data.signed_by
        })
        
        # Set as active for payer profile
        db.execute(text("""
            UPDATE payer_profiles 
            SET active_master_agreement_id = :agreement_id
            WHERE id = :payer_id
        """), {
            "agreement_id": agreement_id,
            "payer_id": agreement[1]
        })
        
        db.commit()
        
        return {
            "success": True,
            "message": f"Agreement {agreement[2]} signed successfully",
            "agreement_id": agreement_id,
            "contract_number": agreement[2]
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# CREATE AGREEMENT (alternative endpoint - POST /api/agreements)
# ============================================================

@router.post("")
async def create_agreement_simple(data: MasterAgreementCreate, db: Session = Depends(get_rh_db)):
    """Create new master agreement (alias for /create)"""
    return await create_agreement(data, db)


# ============================================================
# SEND AGREEMENT (mark as sent + email with PDF)
# ============================================================

class SendAgreementRequest(BaseModel):
    email: str

@router.post("/{agreement_id}/send")
async def send_agreement(
    agreement_id: int,
    data: SendAgreementRequest,
    db: Session = Depends(get_rh_db)
):
    """Send agreement PDF to email"""
    from services.pdf_generator import generate_master_agreement_pdf
    from services.email_service import send_email
    
    # Get agreement with client data
    agreement = db.execute(text("""
        SELECT 
            ma.id, ma.contract_number, ma.status, ma.valid_from, ma.valid_until,
            ma.signed_at, ma.client_user_id, ma.snapshot_json,
            cu.full_name, cu.email, cu.phone, cu.payer_type, cu.tax_id, cu.bank_details
        FROM master_agreements ma
        LEFT JOIN client_users cu ON cu.id = ma.client_user_id
        WHERE ma.id = :id
    """), {"id": agreement_id}).fetchone()
    
    if not agreement:
        raise HTTPException(status_code=404, detail="Договір не знайдено")
    
    # Parse snapshot
    snapshot = None
    if agreement[7]:  # snapshot_json field
        try:
            snapshot = json.loads(agreement[7]) if isinstance(agreement[7], str) else agreement[7]
        except:
            pass
    
    # Prepare data for PDF
    agreement_data = {
        "id": agreement[0],
        "contract_number": agreement[1],
        "status": agreement[2],
        "valid_from": agreement[3].isoformat() if agreement[3] else None,
        "valid_until": agreement[4].isoformat() if agreement[4] else None,
        "signed_at": agreement[5].isoformat() if agreement[5] else None,
        "snapshot": snapshot
    }
    
    client_data = {
        "full_name": agreement[8],
        "email": agreement[9],
        "phone": agreement[10],
        "payer_type": agreement[11],
        "tax_id": agreement[12],
        "bank_details": agreement[13]
    }
    
    # Generate PDF
    pdf_result = generate_master_agreement_pdf(agreement_data, client_data)
    
    if not pdf_result.get("success"):
        raise HTTPException(status_code=500, detail=f"Помилка генерації PDF: {pdf_result.get('error')}")
    
    # Prepare email
    subject = f"Договір оренди № {agreement[1]} | FarforRent"
    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; color: #333;">
        <h2>Договір оренди № {agreement[1]}</h2>
        <p>Шановний(а) {client_data.get('full_name', 'клієнте')},</p>
        <p>Надсилаємо вам Договір оренди обладнання.</p>
        <p><strong>Номер договору:</strong> {agreement[1]}</p>
        <p><strong>Дійсний до:</strong> {agreement_data.get('valid_until', '—')}</p>
        <p>Будь ласка, ознайомтесь з умовами договору у вкладеному PDF файлі.</p>
        <p>Якщо у вас виникли питання, будь ласка, зв'яжіться з нами.</p>
        <br>
        <p>З повагою,<br>Команда FarforRent<br>info@farforrent.com.ua</p>
    </body>
    </html>
    """
    
    # Send email with PDF attachment
    email_result = send_email(
        to_email=data.email,
        subject=subject,
        html_content=html_body,
        attachments=[{
            "filename": pdf_result["pdf_filename"],
            "content": pdf_result["pdf_bytes"],
            "content_type": "application/pdf"
        }]
    )
    
    if not email_result.get("success"):
        raise HTTPException(status_code=500, detail=f"Помилка відправки email: {email_result.get('message')}")
    
    # Update status to 'sent' if was draft
    try:
        db.execute(text("""
            UPDATE master_agreements 
            SET status = 'sent' 
            WHERE id = :id AND status = 'draft'
        """), {"id": agreement_id})
        db.commit()
    except:
        pass  # Ignore if already sent
    
    return {
        "success": True,
        "message": f"Договір {agreement[1]} відправлено на {data.email}"
    }


# ============================================================
# PREVIEW AGREEMENT (HTML)
# ============================================================

@router.get("/{agreement_id}/preview")
async def preview_agreement(agreement_id: int, db: Session = Depends(get_rh_db)):
    """Get HTML preview of agreement"""
    from fastapi.responses import HTMLResponse
    from services.pdf_generator import generate_master_agreement_html
    
    # Get agreement with client data
    agreement = db.execute(text("""
        SELECT 
            ma.id, ma.contract_number, ma.status, ma.valid_from, ma.valid_until,
            ma.signed_at, ma.client_user_id, ma.snapshot_json, ma.note,
            cu.full_name, cu.email, cu.phone, cu.payer_type, cu.tax_id, cu.bank_details
        FROM master_agreements ma
        LEFT JOIN client_users cu ON cu.id = ma.client_user_id
        WHERE ma.id = :id
    """), {"id": agreement_id}).fetchone()
    
    if not agreement:
        raise HTTPException(status_code=404, detail="Договір не знайдено")
    
    # Extract signed_by from note if present
    signed_by = None
    if agreement[8]:  # note field
        note = agreement[8]
        if "Підписано:" in note:
            try:
                signed_by = note.split("Підписано:")[1].strip().split("\n")[0]
            except:
                pass
    
    # Parse snapshot
    snapshot = None
    if agreement[7]:  # snapshot_json field
        try:
            snapshot = json.loads(agreement[7]) if isinstance(agreement[7], str) else agreement[7]
        except:
            pass
    
    agreement_data = {
        "contract_number": agreement[1],
        "status": agreement[2],
        "valid_from": agreement[3].isoformat() if agreement[3] else None,
        "valid_until": agreement[4].isoformat() if agreement[4] else None,
        "signed_at": agreement[5].isoformat() if agreement[5] else None,
        "signed_by": signed_by,
        "snapshot": snapshot
    }
    
    client_data = {
        "full_name": agreement[9],
        "email": agreement[10],
        "phone": agreement[11],
        "payer_type": agreement[12],
        "tax_id": agreement[13],
        "bank_details": agreement[14]
    }
    
    html_content = generate_master_agreement_html(agreement_data, client_data)
    
    return HTMLResponse(content=html_content, media_type="text/html")


# ============================================================
# DOWNLOAD AGREEMENT PDF
# ============================================================

@router.get("/{agreement_id}/pdf")
async def download_agreement_pdf(agreement_id: int, db: Session = Depends(get_rh_db)):
    """Download agreement as PDF"""
    from fastapi.responses import Response
    from services.pdf_generator import generate_master_agreement_pdf
    
    # Get agreement with client data
    agreement = db.execute(text("""
        SELECT 
            ma.id, ma.contract_number, ma.status, ma.valid_from, ma.valid_until,
            ma.signed_at, ma.client_user_id, ma.snapshot_json, ma.note,
            cu.full_name, cu.email, cu.phone, cu.payer_type, cu.tax_id, cu.bank_details
        FROM master_agreements ma
        LEFT JOIN client_users cu ON cu.id = ma.client_user_id
        WHERE ma.id = :id
    """), {"id": agreement_id}).fetchone()
    
    if not agreement:
        raise HTTPException(status_code=404, detail="Договір не знайдено")
    
    # Extract signed_by from note if present
    signed_by = None
    if agreement[8]:
        note = agreement[8]
        if "Підписано:" in note:
            try:
                signed_by = note.split("Підписано:")[1].strip().split("\n")[0]
            except:
                pass
    
    # Parse snapshot
    snapshot = None
    if agreement[7]:  # snapshot_json field
        try:
            snapshot = json.loads(agreement[7]) if isinstance(agreement[7], str) else agreement[7]
        except:
            pass
    
    agreement_data = {
        "contract_number": agreement[1],
        "status": agreement[2],
        "valid_from": agreement[3].isoformat() if agreement[3] else None,
        "valid_until": agreement[4].isoformat() if agreement[4] else None,
        "signed_at": agreement[5].isoformat() if agreement[5] else None,
        "signed_by": signed_by,
        "snapshot": snapshot
    }
    
    client_data = {
        "full_name": agreement[9],
        "email": agreement[10],
        "phone": agreement[11],
        "payer_type": agreement[12],
        "tax_id": agreement[13],
        "bank_details": agreement[14]
    }
    
    pdf_result = generate_master_agreement_pdf(agreement_data, client_data)
    
    if not pdf_result.get("success"):
        raise HTTPException(status_code=500, detail=f"Помилка генерації PDF: {pdf_result.get('error')}")
    
    return Response(
        content=pdf_result["pdf_bytes"],
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename={pdf_result['pdf_filename']}"
        }
    )


# ============================================================
# EXPIRE OLD AGREEMENTS (for cron)
# ============================================================

@router.post("/expire-old")
async def expire_old_agreements(db: Session = Depends(get_rh_db)):
    """Mark expired agreements (for cron job)"""
    try:
        result = db.execute(text("""
            UPDATE master_agreements 
            SET status = 'expired' 
            WHERE status = 'signed' AND valid_until < CURDATE()
        """))
        db.commit()
        return {"success": True, "expired_count": result.rowcount}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))



# ============================================================
# TERMINATE AGREEMENT
# ============================================================

class TerminateAgreementRequest(BaseModel):
    reason: str
    terminated_at: Optional[str] = None  # ISO date, default = today

@router.post("/{agreement_id}/terminate")
async def terminate_agreement(
    agreement_id: int,
    data: TerminateAgreementRequest,
    db: Session = Depends(get_rh_db)
):
    """Terminate (припинити) a master agreement with reason"""
    
    # Check agreement exists
    agreement = db.execute(text("""
        SELECT id, contract_number, status, client_user_id, snapshot_json,
               valid_from, valid_until
        FROM master_agreements WHERE id = :id
    """), {"id": agreement_id}).fetchone()
    
    if not agreement:
        raise HTTPException(status_code=404, detail="Договір не знайдено")
    
    if agreement[2] == 'terminated':
        raise HTTPException(status_code=400, detail="Договір вже припинено")
    
    terminated_at = data.terminated_at or datetime.now().strftime("%Y-%m-%d")
    
    # Ensure columns exist
    try:
        db.execute(text("""
            SELECT terminated_at FROM master_agreements LIMIT 0
        """))
    except Exception:
        db.execute(text("""
            ALTER TABLE master_agreements 
            ADD COLUMN terminated_at DATETIME NULL,
            ADD COLUMN termination_reason TEXT NULL
        """))
        db.commit()
    
    # Update agreement
    db.execute(text("""
        UPDATE master_agreements 
        SET status = 'terminated',
            terminated_at = :terminated_at,
            termination_reason = :reason
        WHERE id = :id
    """), {
        "id": agreement_id,
        "terminated_at": terminated_at,
        "reason": data.reason
    })
    db.commit()
    
    return {
        "success": True,
        "message": f"Договір №{agreement[1]} припинено",
        "contract_number": agreement[1],
        "terminated_at": terminated_at
    }


# ============================================================
# TERMINATION ACT PREVIEW / PDF
# ============================================================

@router.get("/{agreement_id}/termination-act")
async def termination_act_preview(agreement_id: int, db: Session = Depends(get_rh_db)):
    """Generate HTML preview of termination act"""
    from fastapi.responses import HTMLResponse
    
    # Ensure columns exist
    try:
        db.execute(text("SELECT terminated_at FROM master_agreements LIMIT 0"))
    except Exception:
        db.execute(text("""
            ALTER TABLE master_agreements 
            ADD COLUMN terminated_at DATETIME NULL,
            ADD COLUMN termination_reason TEXT NULL
        """))
        db.commit()
    
    agreement = db.execute(text("""
        SELECT 
            ma.id, ma.contract_number, ma.status, ma.valid_from, ma.valid_until,
            ma.signed_at, ma.client_user_id, ma.snapshot_json, ma.note,
            cu.full_name, cu.email, cu.phone, cu.payer_type, cu.tax_id, cu.bank_details,
            ma.terminated_at, ma.termination_reason
        FROM master_agreements ma
        LEFT JOIN client_users cu ON cu.id = ma.client_user_id
        WHERE ma.id = :id
    """), {"id": agreement_id}).fetchone()
    
    if not agreement:
        raise HTTPException(status_code=404, detail="Договір не знайдено")
    
    # Parse snapshot
    snapshot = None
    if agreement[7]:
        try:
            snapshot = json.loads(agreement[7]) if isinstance(agreement[7], str) else agreement[7]
        except:
            snapshot = {}
    snapshot = snapshot or {}
    
    executor_type = snapshot.get("executor_type", "tov")
    executor = snapshot.get("executor") or EXECUTORS.get(executor_type, EXECUTORS["tov"])
    
    # Format dates
    def fmt_date(d):
        if not d: return "___________"
        if isinstance(d, str):
            try:
                d = datetime.fromisoformat(d).date() if 'T' in d else datetime.strptime(d, "%Y-%m-%d").date()
            except:
                return d
        months = ["січня","лютого","березня","квітня","травня","червня",
                  "липня","серпня","вересня","жовтня","листопада","грудня"]
        return f"«{d.day}» {months[d.month-1]} {d.year} р."
    
    contract_date = fmt_date(snapshot.get("contract_date") or agreement[3])
    termination_date = fmt_date(agreement[15])
    
    client_name = agreement[9] or "—"
    
    html = f"""<!DOCTYPE html>
<html lang="uk">
<head>
<meta charset="utf-8">
<title>Акт розірвання договору №{agreement[1]}</title>
<style>
  @page {{ margin: 20mm; size: A4; }}
  body {{ font-family: 'Times New Roman', serif; font-size: 14px; line-height: 1.6; color: #000; margin: 0; padding: 20px; }}
  .center {{ text-align: center; }}
  .bold {{ font-weight: bold; }}
  .mt {{ margin-top: 30px; }}
  .mt2 {{ margin-top: 15px; }}
  .signatures {{ display: flex; justify-content: space-between; margin-top: 60px; }}
  .sig-block {{ width: 45%; }}
  .sig-line {{ border-bottom: 1px solid #000; margin-top: 40px; padding-bottom: 2px; }}
  p {{ text-indent: 40px; margin: 8px 0; text-align: justify; }}
  .no-indent {{ text-indent: 0; }}
</style>
</head>
<body>
<div class="center bold" style="font-size: 16px;">
  УГОДА<br>
  про розірвання Договору оренди декору<br>
  №{agreement[1]} від {contract_date}
</div>

<p class="no-indent mt2" style="text-align: right;">
  {termination_date}
</p>

<p>
  {executor.get('name', 'Орендодавець')}, далі — «Орендодавець», з однієї сторони, та 
  {client_name}, далі — «Орендар», з іншої сторони, 
  разом іменовані «Сторони», уклали цю Угоду про наступне:
</p>

<p class="bold">1.</p>
<p>
  Сторони домовились розірвати Договір оренди декору №{agreement[1]} від {contract_date} 
  (далі — «Договір»).
</p>

<p class="bold">2.</p>
<p>
  Причина розірвання: {agreement[16] or 'за взаємною згодою Сторін'}.
</p>

<p class="bold">3.</p>
<p>
  Договір вважається розірваним з дати підписання цієї Угоди.
</p>

<p class="bold">4.</p>
<p>
  Сторони підтверджують, що не мають одна до одної взаємних претензій за Договором.
</p>

<p class="bold">5.</p>
<p>
  Ця Угода складена у двох примірниках, по одному для кожної зі Сторін, 
  що мають однакову юридичну силу.
</p>

<div class="signatures">
  <div class="sig-block">
    <div class="bold">ОРЕНДОДАВЕЦЬ:</div>
    <div class="mt2">{executor.get('name', '')}</div>
    <div>ЄДРПОУ: {executor.get('edrpou', '')}</div>
    <div class="sig-line"></div>
    <div style="font-size: 12px; color: #666;">підпис</div>
  </div>
  <div class="sig-block">
    <div class="bold">ОРЕНДАР:</div>
    <div class="mt2">{client_name}</div>
    <div>&nbsp;</div>
    <div class="sig-line"></div>
    <div style="font-size: 12px; color: #666;">підпис</div>
  </div>
</div>

</body>
</html>"""
    
    return HTMLResponse(content=html, media_type="text/html")
