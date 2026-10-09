"""
Order Annexes API - Додатки до замовлень
Phase 3: Documents Engine
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel
import json

from database_rentalhub import get_rh_db

router = APIRouter(prefix="/api/annexes", tags=["order-annexes"])


# ============================================================
# PYDANTIC MODELS
# ============================================================

class AnnexGenerateRequest(BaseModel):
    order_id: int
    master_agreement_id: Optional[int] = None  # Auto-detect if not provided
    contact_person: Optional[str] = None
    note: Optional[str] = None


# ============================================================
# HELPER: Generate Annex Number
# ============================================================

def generate_annex_number(db: Session, contract_number: str) -> str:
    """Generate unique annex number: {CONTRACT}-A{NNN}"""
    result = db.execute(text("""
        SELECT COUNT(*) + 1 FROM order_annexes oa
        JOIN master_agreements ma ON ma.id = oa.master_agreement_id
        WHERE ma.contract_number = :contract
    """), {"contract": contract_number})
    seq = result.fetchone()[0]
    return f"{contract_number}-A{seq:03d}"


# ============================================================
# LIST ANNEXES
# ============================================================

@router.get("")
async def list_annexes(
    order_id: Optional[int] = None,
    master_agreement_id: Optional[int] = None,
    status: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_rh_db)
):
    """List order annexes with filters"""
    query = """
        SELECT 
            oa.id, oa.order_id, oa.master_agreement_id, oa.annex_number,
            oa.version, oa.status, oa.created_at,
            o.order_number, o.customer_name,
            ma.contract_number
        FROM order_annexes oa
        LEFT JOIN orders o ON o.order_id = oa.order_id
        LEFT JOIN master_agreements ma ON ma.id = oa.master_agreement_id
        WHERE 1=1
    """
    params = {"limit": limit}
    
    if order_id:
        query += " AND oa.order_id = :order_id"
        params["order_id"] = order_id
    
    if master_agreement_id:
        query += " AND oa.master_agreement_id = :master_agreement_id"
        params["master_agreement_id"] = master_agreement_id
    
    if status:
        query += " AND oa.status = :status"
        params["status"] = status
    
    query += " ORDER BY oa.created_at DESC LIMIT :limit"
    
    result = db.execute(text(query), params)
    
    annexes = []
    for row in result:
        annexes.append({
            "id": row[0],
            "order_id": row[1],
            "master_agreement_id": row[2],
            "annex_number": row[3],
            "version": row[4],
            "status": row[5],
            "created_at": row[6].isoformat() if row[6] else None,
            "order_number": row[7],
            "customer_name": row[8],
            "contract_number": row[9]
        })
    
    return {"annexes": annexes}


# ============================================================
# GET SINGLE ANNEX
# ============================================================

@router.get("/{annex_id}")
async def get_annex(annex_id: int, db: Session = Depends(get_rh_db)):
    """Get single annex with full snapshot data"""
    result = db.execute(text("""
        SELECT 
            oa.id, oa.order_id, oa.master_agreement_id, oa.annex_number,
            oa.version, oa.snapshot_json, oa.pdf_path, oa.status, oa.created_at,
            o.order_number, o.customer_name, o.rental_start_date, o.rental_end_date,
            ma.contract_number, ma.payer_profile_id
        FROM order_annexes oa
        LEFT JOIN orders o ON o.order_id = oa.order_id
        LEFT JOIN master_agreements ma ON ma.id = oa.master_agreement_id
        WHERE oa.id = :id
    """), {"id": annex_id})
    
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Annex not found")
    
    return {
        "id": row[0],
        "order_id": row[1],
        "master_agreement_id": row[2],
        "annex_number": row[3],
        "version": row[4],
        "snapshot": json.loads(row[5]) if row[5] else None,
        "pdf_path": row[6],
        "status": row[7],
        "created_at": row[8].isoformat() if row[8] else None,
        "order": {
            "order_number": row[9],
            "customer_name": row[10],
            "rental_start_date": row[11].isoformat() if row[11] else None,
            "rental_end_date": row[12].isoformat() if row[12] else None
        },
        "contract_number": row[13],
        "payer_profile_id": row[14]
    }


# ============================================================
# GENERATE ANNEX FOR ORDER
# ============================================================

@router.post("/generate-for-order/{order_id}")
async def generate_annex_for_order(
    order_id: int,
    master_agreement_id: Optional[int] = None,
    contact_person: Optional[str] = None,
    db: Session = Depends(get_rh_db)
):
    """
    Generate new annex for order.
    Requires active master agreement (auto-detected or specified).
    Creates immutable snapshot of order data.
    """
    
    # Get order data
    order = db.execute(text("""
        SELECT 
            o.order_id, o.order_number, o.status, o.customer_name, o.customer_phone,
            o.rental_start_date, o.rental_end_date, o.rental_days,
            o.total_price, o.deposit_amount, o.discount_amount,
            o.payer_profile_id, o.deal_mode
        FROM orders o
        WHERE o.order_id = :id
    """), {"id": order_id}).fetchone()
    
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Check order status - must be confirmed or later
    valid_statuses = ["confirmed", "ready", "issued", "returning", "returned", "closed"]
    if order[2] not in valid_statuses:
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot generate annex for order in status '{order[2]}'. Required: confirmed+"
        )
    
    payer_profile_id = order[11]
    if not payer_profile_id:
        raise HTTPException(status_code=400, detail="Order has no payer profile assigned")
    
    # Find active master agreement
    if master_agreement_id:
        agreement = db.execute(text("""
            SELECT id, contract_number, status, valid_until, payer_profile_id
            FROM master_agreements WHERE id = :id
        """), {"id": master_agreement_id}).fetchone()
        
        if not agreement:
            raise HTTPException(status_code=400, detail="Master agreement not found")
        
        if agreement[4] != payer_profile_id:
            raise HTTPException(status_code=400, detail="Agreement does not match order's payer profile")
    else:
        # Auto-find active agreement
        agreement = db.execute(text("""
            SELECT id, contract_number, status, valid_until, payer_profile_id
            FROM master_agreements 
            WHERE payer_profile_id = :pid 
            AND status = 'signed'
            AND valid_until >= CURDATE()
            ORDER BY signed_at DESC
            LIMIT 1
        """), {"pid": payer_profile_id}).fetchone()
        
        if not agreement:
            raise HTTPException(
                status_code=400, 
                detail="No active master agreement found. Please create and sign a master agreement first."
            )
    
    agreement_id = agreement[0]
    contract_number = agreement[1]
    agreement_status = agreement[2]
    valid_until = agreement[3]
    
    # === P1: CONTRACT EXPIRATION CHECK ===
    # Block annex creation for expired contracts
    from datetime import date
    if valid_until and valid_until < date.today():
        raise HTTPException(
            status_code=400, 
            detail=f"Рамковий договір {contract_number} закінчився {valid_until.strftime('%d.%m.%Y')}. Потрібно продовжити або створити новий договір."
        )
    
    # Warn if contract expires within 30 days
    warning_message = None
    if valid_until:
        days_until_expiry = (valid_until - date.today()).days
        if days_until_expiry <= 30:
            warning_message = f"⚠️ Договір {contract_number} закінчується через {days_until_expiry} днів ({valid_until.strftime('%d.%m.%Y')})"
    
    # Get order items for snapshot
    items_result = db.execute(text("""
        SELECT 
            oi.product_name, oi.product_id, oi.quantity,
            oi.price, oi.total_rental, p.sku
        FROM order_items oi
        LEFT JOIN products p ON p.product_id = oi.product_id
        WHERE oi.order_id = :order_id AND (oi.status = 'active' OR oi.status IS NULL)
    """), {"order_id": order_id})
    
    items = []
    for row in items_result:
        items.append({
            "name": row[0],
            "product_id": row[1],
            "quantity": row[2],
            "price_per_day": float(row[3] or 0),
            "total_rental": float(row[4] or 0),
            "sku": row[5]
        })
    
    # Get payer data for snapshot
    payer = db.execute(text("""
        SELECT company_name, payer_type, director_name, edrpou, iban, bank_name, address, phone, email
        FROM payer_profiles WHERE id = :id
    """), {"id": payer_profile_id}).fetchone()
    
    # Build snapshot (immutable)
    snapshot = {
        "contract_number": contract_number,
        "payer": {
            "company_name": payer[0],
            "payer_type": payer[1],
            "director_name": payer[2],
            "edrpou": payer[3],
            "iban": payer[4],
            "bank_name": payer[5],
            "address": payer[6],
            "phone": payer[7],
            "email": payer[8]
        },
        "order": {
            "order_id": order[0],
            "order_number": order[1],
            "customer_name": order[3],
            "customer_phone": order[4],
            "deal_mode": order[12] or "rent"
        },
        "items": items,
        "period": {
            "start_date": order[5].isoformat() if order[5] else None,
            "end_date": order[6].isoformat() if order[6] else None,
            "days": order[7]
        },
        "totals": {
            "rent_total": float(order[8] or 0),
            "deposit_total": float(order[9] or 0),
            "discount": float(order[10] or 0)
        },
        "contact_person": contact_person or order[3],
        "generated_at": datetime.now().isoformat()
    }
    
    # Get next version for this order
    version_result = db.execute(text("""
        SELECT COALESCE(MAX(version), 0) + 1 FROM order_annexes WHERE order_id = :order_id
    """), {"order_id": order_id})
    version = version_result.fetchone()[0]
    
    # Generate annex number
    annex_number = generate_annex_number(db, contract_number)
    
    try:
        db.execute(text("""
            INSERT INTO order_annexes (
                order_id, master_agreement_id, annex_number, version,
                snapshot_json, status
            ) VALUES (
                :order_id, :master_agreement_id, :annex_number, :version,
                :snapshot_json, 'generated'
            )
        """), {
            "order_id": order_id,
            "master_agreement_id": agreement_id,
            "annex_number": annex_number,
            "version": version,
            "snapshot_json": json.dumps(snapshot, ensure_ascii=False)
        })
        
        annex_id = db.execute(text("SELECT LAST_INSERT_ID()")).fetchone()[0]
        
        # Update order with active annex
        db.execute(text("""
            UPDATE orders SET active_annex_id = :annex_id WHERE order_id = :order_id
        """), {"annex_id": annex_id, "order_id": order_id})
        
        db.commit()
        
        response = {
            "success": True,
            "annex_id": annex_id,
            "annex_number": annex_number,
            "version": version,
            "contract_number": contract_number,
            "snapshot": snapshot
        }
        
        # Add warning if contract expiring soon
        if warning_message:
            response["warning"] = warning_message
        
        return response
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# UPDATE ANNEX STATUS
# ============================================================

@router.put("/{annex_id}/status")
async def update_annex_status(
    annex_id: int,
    status: str = Query(..., description="New status: draft, generated, signed"),
    db: Session = Depends(get_rh_db)
):
    """Update annex status"""
    valid_statuses = ["draft", "generated", "signed"]
    if status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
    
    try:
        db.execute(text("""
            UPDATE order_annexes SET status = :status WHERE id = :id
        """), {"id": annex_id, "status": status})
        db.commit()
        return {"success": True}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# GET LATEST ANNEX FOR ORDER
# ============================================================

@router.get("/latest/{order_id}")
async def get_latest_annex(order_id: int, db: Session = Depends(get_rh_db)):
    """Get latest annex for order"""
    result = db.execute(text("""
        SELECT 
            oa.id, oa.annex_number, oa.version, oa.status, oa.snapshot_json, oa.created_at,
            ma.contract_number
        FROM order_annexes oa
        LEFT JOIN master_agreements ma ON ma.id = oa.master_agreement_id
        WHERE oa.order_id = :order_id
        ORDER BY oa.version DESC
        LIMIT 1
    """), {"order_id": order_id})
    
    row = result.fetchone()
    if not row:
        return {"exists": False}
    
    return {
        "exists": True,
        "id": row[0],
        "annex_number": row[1],
        "version": row[2],
        "status": row[3],
        "snapshot": json.loads(row[4]) if row[4] else None,
        "created_at": row[5].isoformat() if row[5] else None,
        "contract_number": row[6]
    }


# ============================================================
# ANNEX HISTORY FOR ORDER
# ============================================================

@router.get("/history/{order_id}")
async def get_annex_history(order_id: int, db: Session = Depends(get_rh_db)):
    """Get all annex versions for order"""
    result = db.execute(text("""
        SELECT 
            oa.id, oa.annex_number, oa.version, oa.status, oa.created_at,
            ma.contract_number
        FROM order_annexes oa
        LEFT JOIN master_agreements ma ON ma.id = oa.master_agreement_id
        WHERE oa.order_id = :order_id
        ORDER BY oa.version DESC
    """), {"order_id": order_id})
    
    versions = []
    for row in result:
        versions.append({
            "id": row[0],
            "annex_number": row[1],
            "version": row[2],
            "status": row[3],
            "created_at": row[4].isoformat() if row[4] else None,
            "contract_number": row[5]
        })
    
    return {"order_id": order_id, "versions": versions, "total": len(versions)}
