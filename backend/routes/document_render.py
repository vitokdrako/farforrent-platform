"""
Document Rendering API - Production Documents Engine
Phase 3.1: Template-based document generation with Jinja2

Supports:
- HTML rendering from templates
- PDF generation with watermarks
- Signature integration
- Email workflow
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime, date, timedelta
from typing import Optional, Dict, Any, List
from pydantic import BaseModel
import json
import os
import base64
import uuid

from jinja2 import Environment, FileSystemLoader, select_autoescape
from database_rentalhub import get_rh_db
from services.company_config import get_landlord_config, get_company_config

router = APIRouter(prefix="/api/documents/render", tags=["document-rendering"])

# ============================================================
# JINJA2 ENVIRONMENT SETUP
# ============================================================

TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates", "documents")

from services.template_loader import DBOverrideLoader
_file_loader_render = FileSystemLoader(TEMPLATES_DIR)
jinja_env = Environment(
    loader=DBOverrideLoader(_file_loader_render),
    autoescape=select_autoescape(['html', 'xml'])
)

PAYER_TYPE_LABELS = {
    "individual": "Фізична особа",
    "fop_simple": "ФОП (єдиний податок)",
    "fop_general": "ФОП (загальна система)",
    "llc_simple": "ТОВ (єдиний податок)",
    "llc_general": "ТОВ (загальна система)"
}

MONTH_NAMES_UA = {
    1: "січня", 2: "лютого", 3: "березня", 4: "квітня",
    5: "травня", 6: "червня", 7: "липня", 8: "серпня",
    9: "вересня", 10: "жовтня", 11: "листопада", 12: "грудня"
}

DOCUMENT_TEMPLATES = {
    "master_agreement": "master_agreement.html",
    "annex_to_contract": "annex_to_contract.html",
    "issue_act": "issue_act.html",
    "return_act": "return_act.html",
    "defect_act": "defect_act.html",
    "quote": "quote.html",
    "invoice_offer": "invoice_offer.html"
}

# ============================================================
# PYDANTIC MODELS
# ============================================================

class RenderRequest(BaseModel):
    doc_type: str
    order_id: Optional[int] = None
    payer_profile_id: Optional[int] = None
    agreement_id: Optional[int] = None
    annex_id: Optional[int] = None
    manual_fields: Optional[Dict[str, Any]] = None
    include_watermark: bool = True


class SignRequest(BaseModel):
    signer_role: str  # "landlord" or "tenant"
    signature_png_base64: str


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def format_date_ua(d) -> Dict[str, str]:
    """Format date for Ukrainian documents"""
    if isinstance(d, str):
        try:
            d = datetime.fromisoformat(d.replace("Z", "+00:00")).date()
        except:
            d = date.today()
    elif isinstance(d, datetime):
        d = d.date()
    elif d is None:
        d = date.today()
    
    return {
        "day": str(d.day).zfill(2),
        "month": MONTH_NAMES_UA.get(d.month, ""),
        "year": str(d.year),
        "formatted": d.strftime("%d.%m.%Y")
    }


def get_watermark_text(status: str) -> str:
    """Get watermark text based on document status"""
    if status == "draft":
        return "ЧЕРНЕТКА"
    elif status == "signed":
        return "ПІДПИСАНО"
    return ""


def build_document_context(
    db: Session,
    doc_type: str,
    order_id: Optional[int] = None,
    payer_profile_id: Optional[int] = None,
    agreement_id: Optional[int] = None,
    annex_id: Optional[int] = None,
    manual_fields: Optional[Dict[str, Any]] = None,
    status: str = "draft"
) -> Dict[str, Any]:
    """Build full document context from database"""
    
    landlord = get_landlord_config(db)
    company = get_company_config(db)
    
    context = {
        "meta": {
            "doc_type": doc_type,
            "status": status,
            "watermark_text": get_watermark_text(status),
            "generated_at": datetime.now().strftime("%d.%m.%Y %H:%M")
        },
        "agreement": {},
        "order": {},
        "landlord": {k: v for k, v in landlord.items() if k != "warehouse_address"},
        "company": company,
        "tenant": {},
        "items": [],
        "totals": {},
        "damage": {"has_damage": False, "rows": [], "total": 0},
        "return_data": {},
        "signatures": {}
    }
    
    now_date = format_date_ua(date.today())
    context["meta"]["doc_day"] = now_date["day"]
    context["meta"]["doc_month"] = now_date["month"]
    context["meta"]["doc_year"] = now_date["year"]
    context["meta"]["act_day"] = now_date["day"]
    context["meta"]["act_month"] = now_date["month"]
    context["meta"]["act_year"] = now_date["year"]
    context["meta"]["contract_day"] = now_date["day"]
    context["meta"]["contract_month"] = now_date["month"]
    context["meta"]["contract_year"] = now_date["year"]
    
    # === Load Order Data ===
    if order_id:
        order_row = db.execute(text("""
            SELECT 
                o.order_id, o.order_number, o.status, o.customer_name, o.customer_phone,
                o.rental_start_date, o.rental_end_date, o.rental_days,
                o.total_price, o.deposit_amount, o.discount_amount,
                o.payer_profile_id, o.deal_mode, o.active_annex_id
            FROM orders o
            WHERE o.order_id = :id
        """), {"id": order_id}).fetchone()
        
        if order_row:
            issue_date = format_date_ua(order_row[5])
            return_date = format_date_ua(order_row[6])
            
            context["order"] = {
                "order_id": order_row[0],
                "order_number": order_row[1],
                "status": order_row[2],
                "customer_name": order_row[3],
                "customer_phone": order_row[4],
                "issue_date": issue_date["formatted"],
                "return_date": return_date["formatted"],
                "days": order_row[7] or 1,
                "warehouse_address": landlord.get("warehouse_address", "м. Київ, вул. Будіндустрії 4"),
                "pickup_time": "17:00",
                "deal_mode": order_row[12] or "rent"
            }
            
            context["totals"] = {
                "rent_total": float(order_row[8] or 0),
                "deposit_security": float(order_row[9] or 0),
                "discount": float(order_row[10] or 0),
                "currency": "UAH"
            }
            if context["order"]["days"] > 0:
                context["totals"]["rent_per_day"] = round(context["totals"]["rent_total"] / context["order"]["days"], 2)
            
            # Auto-set payer_profile_id from order if not provided
            if not payer_profile_id and order_row[11]:
                payer_profile_id = order_row[11]
            
            # Auto-set annex_id from order if not provided
            if not annex_id and order_row[13]:
                annex_id = order_row[13]
            
            # Load order items
            items_result = db.execute(text("""
                SELECT 
                    oi.product_name, oi.product_id, oi.quantity,
                    oi.price, oi.total_rental, p.sku
                FROM order_items oi
                LEFT JOIN products p ON p.product_id = oi.product_id
                WHERE oi.order_id = :order_id AND (oi.status = 'active' OR oi.status IS NULL)
            """), {"order_id": order_id})
            
            context["items"] = []
            for row in items_result:
                context["items"].append({
                    "name": row[0],
                    "product_id": row[1],
                    "qty": row[2],
                    "price_per_day": float(row[3] or 0),
                    "rent_price_total": float(row[4] or 0),
                    "total_rental": float(row[4] or 0),
                    "sku": row[5],
                    "packaging_type": ""  # Can be added later if needed
                })
            
            # Load damage data
            damage_result = db.execute(text("""
                SELECT 
                    pdh.product_name, pdh.damage_type, pdh.note, pdh.fee,
                    pdh.photo_url, pdh.sku, pdh.qty, pdh.severity,
                    pdh.damage_code, pdh.processing_type
                FROM product_damage_history pdh
                WHERE pdh.order_id = :order_id
            """), {"order_id": order_id})
            
            damage_rows = []
            damage_total = 0
            for drow in damage_result:
                proc_type = drow[9] or ""
                is_photo_only = proc_type == 'photo_only'
                damage_rows.append({
                    "name": drow[0],
                    "description": drow[1] + (f" - {drow[2]}" if drow[2] else ""),
                    "amount": float(drow[3] or 0),
                    "photo_url": drow[4] or "",
                    "sku": drow[5] or "",
                    "qty": drow[6] or 1,
                    "severity": drow[7] or "",
                    "damage_code": drow[8] or "",
                    "processing_type": proc_type,
                    "is_photo_only": is_photo_only,
                    "label": "Фіксація" if is_photo_only else ("Повна втрата" if drow[8] == 'TOTAL_LOSS' else "В стан декору"),
                })
                damage_total += float(drow[3] or 0)
            
            context["damage"] = {
                "has_damage": len(damage_rows) > 0,
                "rows": damage_rows,
                "total": damage_total
            }
    
    # === Load Payer Profile ===
    if payer_profile_id:
        payer_row = db.execute(text("""
            SELECT 
                id, company_name, payer_type, director_name, edrpou,
                iban, bank_name, address, phone, email
            FROM payer_profiles WHERE id = :id
        """), {"id": payer_profile_id}).fetchone()
        
        if payer_row:
            payer_type = payer_row[2] or "individual"
            signer_role = ""
            if payer_type in ("llc_simple", "llc_general"):
                signer_role = "Директор"
            
            context["tenant"] = {
                "payer_profile_id": payer_row[0],
                "legal_name": payer_row[1] or "",
                "type": payer_type,
                "type_label": PAYER_TYPE_LABELS.get(payer_type, ""),
                "signer_name": payer_row[3] or "",
                "signer_role": signer_role,
                "tax_id": payer_row[4] or "",
                "edrpou": payer_row[4] or "",
                "iban": payer_row[5] or "",
                "bank_name": payer_row[6] or "",
                "address": payer_row[7] or "",
                "phone": payer_row[8] or "",
                "email": payer_row[9] or "",
                "contact_person": "",
                "contact_channel": "",
                "contact_value": ""
            }
    
    # === Load Master Agreement ===
    if agreement_id:
        agreement_row = db.execute(text("""
            SELECT 
                id, contract_number, template_version, signed_at,
                valid_from, valid_until, status, created_at
            FROM master_agreements WHERE id = :id
        """), {"id": agreement_id}).fetchone()
        
        if agreement_row:
            contract_date = format_date_ua(agreement_row[7])
            context["agreement"] = {
                "id": agreement_row[0],
                "contract_number": agreement_row[1],
                "template_version": agreement_row[2],
                "signed_at": agreement_row[3].strftime("%d.%m.%Y") if agreement_row[3] else None,
                "valid_from": agreement_row[4].strftime("%d.%m.%Y") if agreement_row[4] else None,
                "valid_until": agreement_row[5].strftime("%d.%m.%Y") if agreement_row[5] else None,
                "status": agreement_row[6],
                "contract_day": contract_date["day"],
                "contract_month": contract_date["month"],
                "contract_year": contract_date["year"],
                "contract_date": contract_date["formatted"]
            }
            context["meta"]["doc_number"] = agreement_row[1]
    elif payer_profile_id:
        # Try to find active agreement for payer
        agreement_row = db.execute(text("""
            SELECT 
                id, contract_number, valid_until, status, created_at
            FROM master_agreements 
            WHERE payer_profile_id = :pid AND status = 'signed'
            ORDER BY signed_at DESC LIMIT 1
        """), {"pid": payer_profile_id}).fetchone()
        
        if agreement_row:
            contract_date = format_date_ua(agreement_row[4])
            context["agreement"] = {
                "id": agreement_row[0],
                "contract_number": agreement_row[1],
                "valid_until": agreement_row[2].strftime("%d.%m.%Y") if agreement_row[2] else None,
                "status": agreement_row[3],
                "contract_day": contract_date["day"],
                "contract_month": contract_date["month"],
                "contract_year": contract_date["year"],
                "contract_date": contract_date["formatted"]
            }
    
    # === Load Annex Data ===
    if annex_id:
        annex_row = db.execute(text("""
            SELECT 
                oa.id, oa.annex_number, oa.version, oa.status,
                ma.contract_number
            FROM order_annexes oa
            LEFT JOIN master_agreements ma ON ma.id = oa.master_agreement_id
            WHERE oa.id = :id
        """), {"id": annex_id}).fetchone()
        
        if annex_row:
            context["meta"]["annex_number"] = annex_row[1]
            context["meta"]["annex_seq"] = annex_row[2]
            context["meta"]["doc_number"] = annex_row[1]
            if annex_row[4] and not context["agreement"].get("contract_number"):
                context["agreement"]["contract_number"] = annex_row[4]
    
    # === Apply Manual Fields ===
    # Also store all manual_fields for direct template access
    context["manual_fields"] = manual_fields or {}
    
    if manual_fields:
        # Tenant contact info
        if "contact_person" in manual_fields:
            context["tenant"]["contact_person"] = manual_fields["contact_person"]
        if "contact_channel" in manual_fields:
            context["tenant"]["contact_channel"] = manual_fields["contact_channel"]
        if "contact_value" in manual_fields:
            context["tenant"]["contact_value"] = manual_fields["contact_value"]
        
        # Time fields for annex
        if "pickup_time" in manual_fields:
            context["order"]["pickup_time"] = manual_fields["pickup_time"]
        if "return_time" in manual_fields:
            context["order"]["return_time"] = manual_fields["return_time"]
        
        # Return condition
        if "condition_mode" in manual_fields:
            context["return_data"]["condition_mode"] = manual_fields["condition_mode"]
        
        # Notes
        if "issue_notes" in manual_fields:
            context["meta"]["issue_notes"] = manual_fields["issue_notes"]
        if "return_notes" in manual_fields:
            context["meta"]["return_notes"] = manual_fields["return_notes"]
        if "defect_notes" in manual_fields:
            context["meta"]["defect_notes"] = manual_fields["defect_notes"]
        
        # Defect act number reference
        if "defect_act_number" in manual_fields:
            context["meta"]["defect_act_number"] = manual_fields["defect_act_number"]
        
        # Quote validity
        if "quote_valid_days" in manual_fields:
            valid_until = date.today() + timedelta(days=manual_fields["quote_valid_days"])
            context["meta"]["quote_valid_until"] = valid_until.strftime("%d.%m.%Y")
        else:
            valid_until = date.today() + timedelta(days=7)
            context["meta"]["quote_valid_until"] = valid_until.strftime("%d.%m.%Y")
    
    # Generate doc_number if not set
    if not context["meta"].get("doc_number"):
        doc_prefix = {
            "master_agreement": "MA",
            "annex_to_contract": "ANN",
            "issue_act": "ISS",
            "return_act": "RET",
            "defect_act": "DEF",
            "quote": "QUO"
        }.get(doc_type, "DOC")
        context["meta"]["doc_number"] = f"{doc_prefix}-{datetime.now().strftime('%Y%m%d-%H%M')}"
    
    return context


# ============================================================
# API ENDPOINTS
# ============================================================

@router.post("")
async def render_document(
    request: RenderRequest,
    db: Session = Depends(get_rh_db)
):
    """
    Render document from template with data.
    Returns HTML content.
    """
    if request.doc_type not in DOCUMENT_TEMPLATES:
        raise HTTPException(
            status_code=400, 
            detail=f"Unknown document type: {request.doc_type}. Available: {list(DOCUMENT_TEMPLATES.keys())}"
        )
    
    # Build context
    context = build_document_context(
        db=db,
        doc_type=request.doc_type,
        order_id=request.order_id,
        payer_profile_id=request.payer_profile_id,
        agreement_id=request.agreement_id,
        annex_id=request.annex_id,
        manual_fields=request.manual_fields,
        status="draft"
    )
    
    # Apply watermark setting
    if not request.include_watermark:
        context["meta"]["watermark_text"] = ""
    
    # Render template
    template_name = DOCUMENT_TEMPLATES[request.doc_type]
    try:
        template = jinja_env.get_template(template_name)
        html = template.render(**context)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Template rendering error: {str(e)}")
    
    return {
        "success": True,
        "html": html,
        "doc_type": request.doc_type,
        "doc_number": context["meta"]["doc_number"],
        "context": context  # Return context for debugging/preview
    }


@router.get("/preview/{doc_type}")
async def preview_document(
    doc_type: str,
    order_id: Optional[int] = None,
    payer_profile_id: Optional[int] = None,
    agreement_id: Optional[int] = None,
    annex_id: Optional[int] = None,
    db: Session = Depends(get_rh_db)
):
    """Preview document as HTML (for iframe/popup)"""
    if doc_type not in DOCUMENT_TEMPLATES:
        raise HTTPException(status_code=400, detail=f"Unknown document type: {doc_type}")
    
    context = build_document_context(
        db=db,
        doc_type=doc_type,
        order_id=order_id,
        payer_profile_id=payer_profile_id,
        agreement_id=agreement_id,
        annex_id=annex_id,
        status="draft"
    )
    
    template_name = DOCUMENT_TEMPLATES[doc_type]
    template = jinja_env.get_template(template_name)
    html = template.render(**context)
    
    return HTMLResponse(content=html)


@router.get("/templates")
async def list_templates():
    """List available document templates"""
    return {
        "templates": list(DOCUMENT_TEMPLATES.keys()),
        "template_files": DOCUMENT_TEMPLATES
    }


@router.get("/context/{doc_type}")
async def get_document_context(
    doc_type: str,
    order_id: Optional[int] = None,
    payer_profile_id: Optional[int] = None,
    agreement_id: Optional[int] = None,
    annex_id: Optional[int] = None,
    db: Session = Depends(get_rh_db)
):
    """Get document context data (for debugging/preview)"""
    if doc_type not in DOCUMENT_TEMPLATES:
        raise HTTPException(status_code=400, detail=f"Unknown document type: {doc_type}")
    
    context = build_document_context(
        db=db,
        doc_type=doc_type,
        order_id=order_id,
        payer_profile_id=payer_profile_id,
        agreement_id=agreement_id,
        annex_id=annex_id,
        status="draft"
    )
    
    return {"context": context}
