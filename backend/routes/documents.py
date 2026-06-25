"""
Documents API - генерація, перегляд та управління документами
"""
from fastapi import APIRouter, Depends, HTTPException, Response, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime
from typing import Optional, List
import json
import os

from database_rentalhub import get_rh_db
from services.company_config import get_company_config

# Base URL for images - use backend URL from environment
BACKEND_BASE_URL = os.environ.get("BACKEND_BASE_URL", "https://backrentalhub.farforrent.com.ua")

def _get_full_image_url(image_url: str) -> str:
    """Convert relative image path to full URL"""
    if not image_url:
        return None
    # Already a full URL
    if image_url.startswith("http://") or image_url.startswith("https://"):
        return image_url
    # Relative path - prepend backend URL
    # Remove leading slash if present
    image_path = image_url.lstrip("/")
    return f"{BACKEND_BASE_URL}/{image_path}"

def _email_to_name(val: str) -> str:
    """Convert email to display name: katia@farforrent.com.ua -> Katia"""
    if not val:
        return "—"
    if "@" in val:
        return val.split("@")[0].capitalize()
    return val
from services.doc_engine.registry import DOC_REGISTRY, get_doc_config, get_docs_for_entity
from services.doc_engine.data_builders import build_document_data
from services.doc_engine.render import render_html, render_pdf, get_template_path
from services.doc_engine.numbering import generate_doc_number

router = APIRouter(prefix="/api/documents", tags=["documents"])


# ============ Довідники ============

@router.get("/types")
async def list_document_types():
    """Список всіх типів документів"""
    return [
        {"doc_type": key, **value}
        for key, value in DOC_REGISTRY.items()
    ]


@router.get("/available-invoices/{order_id}")
async def get_available_invoices(order_id: int, db: Session = Depends(get_rh_db)):
    """Get available invoice/document types for an order based on its payer profile"""
    
    payer = _get_order_payer(db, order_id)
    
    result = {
        "has_payer": payer is not None,
        "payer": None,
        "available_types": []
    }
    
    if not payer:
        return result
    
    result["payer"] = {
        "id": payer["id"],
        "type": payer["type"],
        "display_name": payer["display_name"],
        "edrpou": payer.get("edrpou"),
        "tax_mode": payer.get("tax_mode")
    }
    
    payer_type = payer["type"]  # fop, tov, individual, fop_simple
    
    # Always available: invoice payment and service act
    if payer_type in ("fop", "fop_simple"):
        result["available_types"] = [
            {"value": "invoice_payment_fop", "label": "Рахунок на оплату (ФОП)", "endpoint": "invoice-payment", "executor_type": "fop"},
            {"value": "service_act_fop", "label": "Акт надання послуг (ФОП)", "endpoint": "service-act", "executor_type": "fop"},
        ]
    elif payer_type == "tov":
        result["available_types"] = [
            {"value": "invoice_payment_tov", "label": "Рахунок на оплату (ТОВ)", "endpoint": "invoice-payment", "executor_type": "tov"},
            {"value": "service_act_tov", "label": "Акт надання послуг (ТОВ)", "endpoint": "service-act", "executor_type": "tov"},
        ]
    else:
        # Individual - show both FOP options (most common for rental)
        result["available_types"] = [
            {"value": "invoice_payment_fop", "label": "Рахунок на оплату (ФОП)", "endpoint": "invoice-payment", "executor_type": "fop"},
            {"value": "service_act_fop", "label": "Акт надання послуг (ФОП)", "endpoint": "service-act", "executor_type": "fop"},
        ]
    
    return result

@router.get("/types/{entity_type}")
async def list_documents_for_entity(entity_type: str):
    """Список документів для типу сутності (order, issue, return, damage_case)"""
    return get_docs_for_entity(entity_type)


# ============ Генерація документів ============

from pydantic import BaseModel

class GenerateDocumentRequest(BaseModel):
    doc_type: str
    entity_id: str
    format: Optional[str] = "html"
    options: Optional[dict] = None

@router.post("/generate")
async def generate_document(
    request: GenerateDocumentRequest,
    db: Session = Depends(get_rh_db)
):
    """
    Генерує новий документ.
    
    Args:
        doc_type: Тип документа (invoice_offer, contract_rent, etc.)
        entity_id: ID сутності (order_id, issue_card_id, etc.)
        format: Формат виводу (html, pdf)
        options: Додаткові опції (lang, notes, etc.)
    
    Returns:
        Інформація про згенерований документ
    """
    doc_type = request.doc_type
    entity_id = request.entity_id
    options = request.options
    try:
        # Отримуємо конфігурацію
        config = get_doc_config(doc_type)
        
        # Генеруємо номер документа
        doc_number = generate_doc_number(db, config["series"])
        
        # Збираємо дані
        data = build_document_data(db, doc_type, entity_id, options or {})
        data["doc_number"] = doc_number
        
        # Рендеримо HTML
        template_path = get_template_path(doc_type, "v1", options.get("lang", "uk") if options else "uk")
        html_content = render_html(template_path, data)
        
        # Зберігаємо в БД
        doc_id = save_document(
            db=db,
            doc_type=doc_type,
            doc_number=doc_number,
            entity_type=config["entity_type"],
            entity_id=entity_id,
            data_snapshot=data,
            html_content=html_content,
            options=options
        )
        
        # Повертаємо результат з HTML контентом
        result = {
            "success": True,
            "document_id": doc_id,
            "doc_number": doc_number,
            "doc_type": doc_type,
            "entity_id": entity_id,
            "preview_url": f"/api/documents/{doc_id}/preview",
            "download_url": f"/api/documents/{doc_id}/pdf",
            "html_content": html_content  # Додаємо HTML для прямого рендерингу
        }
        
        return result
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Помилка генерації: {str(e)}")


@router.get("/{document_id}/preview", response_class=HTMLResponse)
async def preview_document(document_id: str, db: Session = Depends(get_rh_db)):
    """Повертає HTML-превʼю документа"""
    
    doc = get_document_by_id(db, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Документ не знайдено")
    
    return HTMLResponse(content=doc["html_content"])


@router.get("/{document_id}/pdf")
async def download_pdf(document_id: str, db: Session = Depends(get_rh_db)):
    """Повертає PDF документа"""
    
    doc = get_document_by_id(db, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Документ не знайдено")
    
    # Генеруємо PDF з HTML
    pdf_bytes = render_pdf(doc["html_content"])
    
    filename = f"{doc['doc_number']}.pdf"
    
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        }
    )


@router.get("/{document_id}")
async def get_document(document_id: str, db: Session = Depends(get_rh_db)):
    """Отримує інформацію про документ включаючи html_content"""
    
    doc = get_document_by_id(db, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Документ не знайдено")
    
    return {
        "id": doc["id"],
        "doc_type": doc["doc_type"],
        "doc_number": doc["doc_number"],
        "entity_type": doc["entity_type"],
        "entity_id": doc["entity_id"],
        "version": doc["version"],
        "status": doc["status"],
        "signed_at": doc["signed_at"],
        "created_at": doc["created_at"],
        "html_content": doc.get("html_content", ""),
        "preview_url": f"/api/documents/{doc['id']}/preview",
        "pdf_url": f"/api/documents/{doc['id']}/pdf"
    }


# ============ Список документів для сутності ============

@router.get("/entity/{entity_type}/{entity_id}")
async def list_entity_documents(
    entity_type: str, 
    entity_id: str, 
    db: Session = Depends(get_rh_db)
):
    """Список документів для конкретної сутності"""
    
    result = db.execute(text("""
        SELECT id, doc_type, doc_number, version, status, signed_at, created_at
        FROM documents
        WHERE entity_type = :entity_type AND entity_id = :entity_id
        ORDER BY created_at DESC
    """), {"entity_type": entity_type, "entity_id": entity_id})
    
    documents = []
    for row in result:
        config = DOC_REGISTRY.get(row[1], {})
        documents.append({
            "id": row[0],
            "doc_type": row[1],
            "doc_type_name": config.get("name", row[1]),
            "doc_number": row[2],
            "version": row[3],
            "status": row[4],
            "signed_at": row[5].isoformat() if row[5] else None,
            "created_at": row[6].isoformat() if row[6] else None,
            "preview_url": f"/api/documents/{row[0]}/preview",
            "pdf_url": f"/api/documents/{row[0]}/pdf"
        })
    
    # Додаємо доступні типи документів
    available_types = get_docs_for_entity(entity_type)
    
    return {
        "documents": documents,
        "available_types": available_types
    }


@router.post("/batch-by-orders")
async def batch_documents_by_orders(
    body: dict,
    db: Session = Depends(get_rh_db)
):
    """Отримати всі згенеровані документи для списку замовлень, згруповані по order_id"""
    order_ids = body.get("order_ids", [])
    if not order_ids:
        return {}
    
    placeholders = ",".join([f":oid_{i}" for i in range(len(order_ids))])
    params = {f"oid_{i}": str(oid) for i, oid in enumerate(order_ids)}
    
    result = db.execute(text(f"""
        SELECT id, doc_type, doc_number, version, status, entity_id, created_at
        FROM documents
        WHERE entity_type = 'order' AND entity_id IN ({placeholders})
        ORDER BY created_at DESC
    """), params)
    
    doc_type_labels = {
        "issue_act": "Акт видачі",
        "return_act": "Акт повернення",
        "defect_act": "Дефектний акт",
        "contract_rent": "Договір оренди",
        "invoice_offer": "Рахунок-оферта",
        "delivery_note": "ТТН",
        "rental_extension": "Додаткова угода",
        "damage_settlement_act": "Акт утримання",
        "deposit_refund_act": "Акт повернення застави",
        "deposit_settlement_act": "Акт взаєморозрахунків",
        "invoice_additional": "Додатковий рахунок",
        "invoice_legal": "Рахунок (юр. особа)",
        "partial_return_act": "Акт часткового повернення",
        "settlement_act": "Акт взаєморозрахунків",
        "service_act": "Акт виконаних робіт",
        "goods_invoice": "Видаткова накладна",
        "order_modification": "Дозамовлення",
    }
    
    grouped = {}
    seen = {}
    for row in result:
        oid = str(row[5])
        doc_type = row[1]
        key = f"{oid}_{doc_type}"
        if key in seen:
            continue
        seen[key] = True
        
        if oid not in grouped:
            grouped[oid] = []
        grouped[oid].append({
            "id": row[0],
            "doc_type": doc_type,
            "label": doc_type_labels.get(doc_type, doc_type),
            "doc_number": row[2],
            "version": row[3],
            "preview_url": f"/api/documents/{row[0]}/preview",
        })
    
    return grouped



# ============ Підписання ============

@router.post("/{document_id}/sign")
async def sign_document(
    document_id: str,
    signature_data: dict = None,
    db: Session = Depends(get_rh_db)
):
    """
    Позначає документ як підписаний.
    
    Args:
        signature_data: Опційні дані підпису (signature_image, signer_name, etc.)
    """
    
    doc = get_document_by_id(db, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Документ не знайдено")
    
    db.execute(text("""
        UPDATE documents 
        SET status = 'signed', 
            signed_at = NOW(),
            signature_payload = :signature_payload
        WHERE id = :doc_id
    """), {
        "doc_id": document_id,
        "signature_payload": json.dumps(signature_data) if signature_data else None
    })
    
    db.commit()
    
    return {"success": True, "message": "Документ позначено як підписаний"}


# ============ Відправка Email ============

class SendEmailRequest(BaseModel):
    email: str

@router.post("/{document_id}/send-email")
async def send_document_email(
    document_id: str,
    request: SendEmailRequest,
    db: Session = Depends(get_rh_db)
):
    """
    Відправляє документ на email як HTML в тілі листа.
    Відправляється тільки сам документ без додаткових обгорток.
    """
    from services.email_service import send_email
    
    doc = get_document_by_id(db, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Документ не знайдено")
    
    # Отримуємо HTML документа
    html_content = doc.get("html_content")
    if not html_content:
        raise HTTPException(status_code=400, detail="Документ не має HTML вмісту")
    
    # Тема листа
    doc_type_name = DOC_REGISTRY.get(doc["doc_type"], {}).get("name", doc["doc_type"])
    subject = f"FarforDecorOrenda - {doc_type_name} {doc['doc_number']}"
    
    try:
        result = send_email(
            to_email=request.email,
            subject=subject,
            html_content=html_content  # Відправляємо документ як є
        )
        
        if not result["success"]:
            raise Exception(result["message"])
        
        # Логуємо відправку
        db.execute(text("""
            INSERT INTO document_email_log (document_id, email, sent_at, status)
            VALUES (:doc_id, :email, NOW(), 'sent')
        """), {"doc_id": document_id, "email": request.email})
        db.commit()
        
        return {"success": True, "message": f"Документ відправлено на {request.email}"}
    except Exception as e:
        # Логуємо помилку
        try:
            db.execute(text("""
                INSERT INTO document_email_log (document_id, email, sent_at, status, error)
                VALUES (:doc_id, :email, NOW(), 'failed', :error)
            """), {"doc_id": document_id, "email": request.email, "error": str(e)})
            db.commit()
        except:
            pass
        
        raise HTTPException(status_code=500, detail=f"Помилка відправки email: {str(e)}")


@router.post("/{document_id}/regenerate")
async def regenerate_document(
    document_id: str,
    options: dict = None,
    db: Session = Depends(get_rh_db)
):
    """
    Перегенеровує документ (створює нову версію).
    Використовується якщо потрібно оновити дані.
    """
    
    doc = get_document_by_id(db, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Документ не знайдено")
    
    # Генеруємо новий документ з тим самим номером, але новою версією
    return await generate_document(
        doc_type=doc["doc_type"],
        entity_id=doc["entity_id"],
        options=options,
        db=db
    )


# ============ Допоміжні функції ============

def save_document(
    db: Session,
    doc_type: str,
    doc_number: str,
    entity_type: str,
    entity_id: str,
    data_snapshot: dict,
    html_content: str,
    options: dict = None
) -> str:
    """Зберігає документ в БД"""
    
    # Перевіряємо чи є попередні версії
    result = db.execute(text("""
        SELECT MAX(version) FROM documents 
        WHERE entity_type = :entity_type AND entity_id = :entity_id AND doc_type = :doc_type
    """), {"entity_type": entity_type, "entity_id": entity_id, "doc_type": doc_type})
    
    max_version = result.fetchone()[0]
    version = (max_version or 0) + 1
    
    # Генеруємо ID
    doc_id = f"DOC-{doc_number.replace('-', '')}-V{version}"
    
    # Зберігаємо
    db.execute(text("""
        INSERT INTO documents (
            id, doc_type, doc_number, entity_type, entity_id,
            version, status, data_snapshot, html_content, options_json,
            created_at
        ) VALUES (
            :id, :doc_type, :doc_number, :entity_type, :entity_id,
            :version, 'draft', :data_snapshot, :html_content, :options_json,
            NOW()
        )
    """), {
        "id": doc_id,
        "doc_type": doc_type,
        "doc_number": doc_number,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "version": version,
        "data_snapshot": json.dumps(data_snapshot, default=str, ensure_ascii=False),
        "html_content": html_content,
        "options_json": json.dumps(options, ensure_ascii=False) if options else None
    })
    
    db.commit()
    
    # Push-сповіщення клієнту про новий документ.
    # Безпечно: будь-яка помилка push не має ламати створення документа.
    try:
        if entity_type == "order":
            from services.push_notifications import notify_document_ready
            try:
                order_id_int = int(entity_id)
            except (TypeError, ValueError):
                order_id_int = None
            if order_id_int:
                notify_document_ready(db, order_id_int, doc_type, doc_number)
    except Exception as _e:
        import logging
        logging.getLogger("documents").warning(f"push notify failed: {_e}")
    
    return doc_id


def get_document_by_id(db: Session, document_id: str) -> dict:
    """Отримує документ за ID"""
    
    result = db.execute(text("""
        SELECT id, doc_type, doc_number, entity_type, entity_id,
               version, status, signed_at, html_content, created_at
        FROM documents
        WHERE id = :doc_id
    """), {"doc_id": document_id})
    
    row = result.fetchone()
    if not row:
        return None
    
    return {
        "id": row[0],
        "doc_type": row[1],
        "doc_number": row[2],
        "entity_type": row[3],
        "entity_id": row[4],
        "version": row[5],
        "status": row[6],
        "signed_at": row[7],
        "html_content": row[8],
        "created_at": row[9]
    }



def get_latest_document(db: Session, entity_type: str, entity_id: str, doc_type: str) -> dict:
    """Отримує останній згенерований документ певного типу для сутності"""
    
    result = db.execute(text("""
        SELECT id, doc_type, doc_number, entity_type, entity_id,
               version, status, signed_at, html_content, created_at
        FROM documents
        WHERE entity_type = :entity_type 
          AND entity_id = :entity_id 
          AND doc_type = :doc_type
        ORDER BY version DESC
        LIMIT 1
    """), {"entity_type": entity_type, "entity_id": entity_id, "doc_type": doc_type})
    
    row = result.fetchone()
    if not row:
        return None
    
    return {
        "id": row[0],
        "doc_type": row[1],
        "doc_number": row[2],
        "entity_type": row[3],
        "entity_id": row[4],
        "version": row[5],
        "status": row[6],
        "signed_at": row[7],
        "html_content": row[8],
        "created_at": row[9]
    }


# ============ Останній документ для перегляду ============

@router.get("/latest/{entity_type}/{entity_id}/{doc_type}")
async def get_latest_entity_document(
    entity_type: str,
    entity_id: str,
    doc_type: str,
    db: Session = Depends(get_rh_db)
):
    """
    Отримує останній згенерований документ певного типу.
    Використовується для перегляду без повторної генерації.
    """
    doc = get_latest_document(db, entity_type, entity_id, doc_type)
    
    if not doc:
        return {
            "exists": False,
            "message": "Документ ще не згенеровано"
        }
    
    config = DOC_REGISTRY.get(doc_type, {})
    
    return {
        "exists": True,
        "id": doc["id"],
        "doc_type": doc["doc_type"],
        "doc_type_name": config.get("name", doc_type),
        "doc_number": doc["doc_number"],
        "version": doc["version"],
        "status": doc["status"],
        "signed_at": doc["signed_at"].isoformat() if doc["signed_at"] else None,
        "created_at": doc["created_at"].isoformat() if doc["created_at"] else None,
        "preview_url": f"/api/documents/{doc['id']}/preview",
        "pdf_url": f"/api/documents/{doc['id']}/pdf",
        "html_content": doc["html_content"]
    }


# ============ Batch endpoint для паралельного завантаження версій ============

class LatestBatchRequest(BaseModel):
    """Запит на отримання останніх версій документів batch"""
    entity_type: str
    entity_id: str
    doc_types: List[str]

@router.post("/latest-batch")
async def get_latest_batch(request: LatestBatchRequest, db: Session = Depends(get_rh_db)):
    """Get latest versions of multiple document types in one request"""
    results = {}
    for doc_type in request.doc_types:
        doc = get_latest_document(db, request.entity_type, request.entity_id, doc_type)
        if doc:
            results[doc_type] = {
                "id": doc["id"],
                "doc_number": doc["doc_number"],
                "version": doc["version"],
                "status": doc["status"]
            }
    return results


# ============================================================
# ESTIMATE (КОШТОРИС) - Quick Preview
# ============================================================

from services.pdf_generator import jinja_env, EXECUTORS

def _format_date_ua(date_val) -> str:
    """Format date to DD.MM.YYYY"""
    if not date_val:
        return "—"
    if isinstance(date_val, str):
        try:
            date_val = datetime.fromisoformat(date_val.replace('Z', '+00:00'))
        except:
            return date_val
    return date_val.strftime("%d.%m.%Y")

def _format_date_ua_long(date_val) -> str:
    """Format date to «DD» місяця YYYY року"""
    if not date_val:
        return "«____» ____________ 202_ року"
    if isinstance(date_val, str):
        try:
            date_val = datetime.fromisoformat(date_val.replace('Z', '+00:00'))
        except:
            return date_val
    months = ['січня', 'лютого', 'березня', 'квітня', 'травня', 'червня',
              'липня', 'серпня', 'вересня', 'жовтня', 'листопада', 'грудня']
    return f"«{date_val.day}» {months[date_val.month - 1]} {date_val.year} року"

def _format_currency(value) -> str:
    """Format number as currency"""
    if value is None:
        return "0,00"
    return f"{float(value):,.2f}".replace(",", " ").replace(".", ",")

def _get_order_with_items(db: Session, order_id: int):
    """Get order with all items including extended fields for documents"""
    order = db.execute(text("""
        SELECT 
            o.order_id,           -- 0
            o.order_number,       -- 1
            o.customer_id,        -- 2
            o.customer_name,      -- 3
            o.customer_phone,     -- 4
            o.customer_email,     -- 5
            o.rental_start_date,  -- 6
            o.rental_end_date,    -- 7
            o.issue_date,         -- 8
            o.return_date,        -- 9
            o.status,             -- 10
            o.total_price,        -- 11
            o.deposit_amount,     -- 12
            o.notes,              -- 13
            o.created_at,         -- 14
            o.rental_days,        -- 15
            o.city,               -- 16
            o.delivery_address,   -- 17
            o.delivery_type,      -- 18
            o.event_type,         -- 19
            o.customer_comment,   -- 20
            o.phone,              -- 21
            o.email,              -- 22
            o.discount_amount,    -- 23
            o.discount_percent,   -- 24
            COALESCE(o.service_fee, 0), -- 25
            o.service_fee_name    -- 26
        FROM orders o WHERE o.order_id = :id
    """), {"id": order_id}).fetchone()
    
    if not order:
        return None, None
    
    # Join with products to get SKU, rental_price and purchase_price
    items = db.execute(text("""
        SELECT 
            oi.id,                -- 0
            oi.product_id,        -- 1
            oi.product_name,      -- 2
            oi.quantity,          -- 3
            oi.price,             -- 4 (rental price per day from order)
            oi.total_rental,      -- 5
            oi.image_url,         -- 6
            p.sku,                -- 7
            p.rental_price,       -- 8 (rental price per day from product)
            p.price               -- 9 (purchase price - for deposit calculation)
        FROM order_items oi
        LEFT JOIN products p ON oi.product_id = p.product_id
        WHERE oi.order_id = :id AND oi.status = 'active'
    """), {"id": order_id}).fetchall()
    
    return order, items


def _enrich_template_with_agreement(db: Session, order, template_data: dict, order_id=None, customer_name=None) -> dict:
    """
    Enrich template_data with agreement (contract number + date), landlord, tenant, meta.
    Called from ALL document generation endpoints so templates can reference:
      {{ agreement.contract_number }}, {{ agreement.contract_date }}
      {{ tenant.type_label }}, {{ landlord.name }}, etc.
    """
    # Find client_user_id from order
    client_user_id = None
    if not customer_name and order:
        customer_name = order[3] if len(order) > 3 else None
    if not order_id and order:
        order_id = order[0] if len(order) > 0 else None
    
    if order_id:
        # Try to get client_user_id directly from order
        try:
            cuid_row = db.execute(text(
                "SELECT client_user_id FROM orders WHERE order_id = :oid"
            ), {"oid": order_id}).fetchone()
            if cuid_row and cuid_row[0]:
                client_user_id = cuid_row[0]
        except:
            pass
        
        # Fallback: match by customer_name
        if not client_user_id and customer_name:
            try:
                cu_row = db.execute(text(
                    "SELECT id FROM client_users WHERE full_name = :name LIMIT 1"
                ), {"name": customer_name}).fetchone()
                if cu_row:
                    client_user_id = cu_row[0]
            except:
                pass
    
    # Load client data
    client_data = {}
    if client_user_id:
        try:
            cr = db.execute(text("""
                SELECT full_name, email, phone, payer_type, tax_id, company_name, 
                       director_name, bank_details
                FROM client_users WHERE id = :cid
            """), {"cid": client_user_id}).fetchone()
            if cr:
                client_data = {
                    "full_name": cr[0] or "",
                    "email": cr[1] or "",
                    "phone": cr[2] or "",
                    "payer_type": cr[3] or "individual",
                    "tax_id": cr[4] or "",
                    "company_name": cr[5] or "",
                    "director_name": cr[6] or "",
                    "bank_details": cr[7],
                }
        except:
            pass
    
    # Load active master agreement
    agreement_data = {}
    if client_user_id:
        try:
            ma_row = db.execute(text("""
                SELECT id, contract_number, valid_from, valid_until, signed_at, status, snapshot_json
                FROM master_agreements 
                WHERE client_user_id = :cid AND status = 'signed'
                AND valid_until >= CURDATE()
                ORDER BY signed_at DESC LIMIT 1
            """), {"cid": client_user_id}).fetchone()
            
            if not ma_row:
                # Try draft
                ma_row = db.execute(text("""
                    SELECT id, contract_number, valid_from, valid_until, signed_at, status, snapshot_json
                    FROM master_agreements 
                    WHERE client_user_id = :cid AND status IN ('draft', 'sent')
                    ORDER BY created_at DESC LIMIT 1
                """), {"cid": client_user_id}).fetchone()
            
            if ma_row:
                snapshot = {}
                if ma_row[6]:
                    try:
                        snapshot = json.loads(ma_row[6]) if isinstance(ma_row[6], str) else ma_row[6]
                    except:
                        pass
                
                contract_date_raw = snapshot.get("contract_date") or (ma_row[2].isoformat() if ma_row[2] else None)
                
                agreement_data = {
                    "id": ma_row[0],
                    "contract_number": ma_row[1],
                    "contract_date": _format_date_ua(ma_row[2]),
                    "contract_date_long": _format_date_ua_long(ma_row[2]),
                    "valid_from": _format_date_ua(ma_row[2]),
                    "valid_until": _format_date_ua_long(ma_row[3]),
                    "signed_at": _format_date_ua(ma_row[4]) if ma_row[4] else None,
                    "status": ma_row[5],
                }
                
                # Extract executor from snapshot
                executor_type = snapshot.get("executor_type", "tov")
                executor = snapshot.get("executor") or EXECUTORS.get(executor_type, EXECUTORS.get("tov", {}))
                agreement_data["executor"] = executor
                agreement_data["executor_type"] = executor_type
        except:
            pass
    
    # Build mappings
    payer_type = client_data.get("payer_type", "individual")
    payer_type_labels = {
        "individual": "фізична особа",
        "fop": "фізична особа-підприємець",
        "tov": "юридична особа (ТОВ)",
        "pp": "приватне підприємство",
    }
    
    executor = agreement_data.get("executor", EXECUTORS.get("tov", {}))
    
    template_data["agreement"] = agreement_data
    
    template_data["landlord"] = {
        "name": executor.get("name", ""),
        "tax_id": executor.get("edrpou", executor.get("tax_id", "")),
        "iban": executor.get("iban", ""),
        "address": executor.get("address", ""),
    }
    
    template_data["tenant"] = {
        "legal_name": client_data.get("company_name") or client_data.get("full_name", customer_name or ""),
        "signer_name": client_data.get("director_name") or client_data.get("full_name", customer_name or ""),
        "full_name": client_data.get("full_name", customer_name or ""),
        "address": "",
        "iban": "",
        "type": payer_type,
        "type_label": payer_type_labels.get(payer_type, payer_type or ""),
        "tax_id": client_data.get("tax_id", ""),
        "phone": client_data.get("phone", ""),
        "email": client_data.get("email", ""),
    }
    
    # Parse bank_details for tenant
    bd = client_data.get("bank_details")
    if bd:
        if isinstance(bd, str):
            try:
                bd = json.loads(bd)
            except:
                bd = None
        if isinstance(bd, dict):
            template_data["tenant"]["iban"] = bd.get("iban", "")
            template_data["tenant"]["address"] = bd.get("address", "")
    
    # Meta (date parts for templates)
    contract_date_raw = None
    if agreement_data:
        try:
            snapshot = agreement_data.get("_snapshot", {})
            contract_date_raw = snapshot.get("contract_date") or agreement_data.get("valid_from")
        except:
            pass
    
    meta_day, meta_month, meta_year = "", "", ""
    if contract_date_raw:
        try:
            from datetime import date as dt_date
            if isinstance(contract_date_raw, str) and len(contract_date_raw) >= 8:
                d = datetime.fromisoformat(contract_date_raw).date() if 'T' in contract_date_raw else datetime.strptime(contract_date_raw, "%Y-%m-%d").date()
                months_ua = ["січня","лютого","березня","квітня","травня","червня",
                            "липня","серпня","вересня","жовтня","листопада","грудня"]
                meta_day = str(d.day)
                meta_month = months_ua[d.month - 1]
                meta_year = str(d.year)
        except:
            pass
    
    template_data["meta"] = template_data.get("meta", {})
    template_data["meta"].update({
        "watermark_text": "",
        "contract_day": meta_day,
        "contract_month": meta_month, 
        "contract_year": meta_year,
    })
    
    return template_data



@router.get("/estimate/{order_id}/preview", response_class=HTMLResponse)
async def preview_estimate(order_id: int, db: Session = Depends(get_rh_db)):
    """Generate HTML preview of estimate (Кошторис) using new quote.html template"""
    
    order, items = _get_order_with_items(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Замовлення не знайдено")
    
    # Calculate rental days
    rental_days = order[15] if order[15] else 1
    if not rental_days and order[6] and order[7]:
        rental_days = (order[7] - order[6]).days + 1
    
    # Format items for template
    formatted_items = []
    rent_total = 0.0
    deposit_total = 0.0
    loss_total = 0.0  # Загальна сума збитку
    
    for item in items:
        # item structure: [id, product_id, product_name, quantity, price, total_rental, image_url, sku, rental_price, purchase_price]
        qty = item[3] or 1
        rental_price_day = float(item[4] or item[8] or 0)  # Use order price or product rental_price
        total_rental = float(item[5] or 0)
        
        # Збиток = повна вартість товару (purchase_price * qty)
        # Завдаток = 50% від збитку
        purchase_price = float(item[9] or 0)
        loss_per_item = purchase_price * qty  # Повна сума збитку
        deposit_per_item = loss_per_item / 2 if loss_per_item > 0 else 0  # 50% = завдаток
        
        rent_total += total_rental
        deposit_total += deposit_per_item
        loss_total += loss_per_item  # Загальна сума збитку
        
        formatted_items.append({
            "product_name": item[2],
            "sku": item[7] or "—",
            "quantity": qty,
            "rental_price_fmt": _format_currency(rental_price_day),
            "price_per_day_fmt": _format_currency(rental_price_day),
            "loss_fmt": _format_currency(loss_per_item),  # Збиток (повна ціна)
            "deposit_fmt": _format_currency(deposit_per_item),  # Завдаток (50%)
            "image_url": _get_full_image_url(item[6]),
            "note": None
        })
    
    # Calculate totals (use order values if available, otherwise calculated)
    order_rent = float(order[11] or 0) if order[11] else rent_total
    # Use calculated deposit (50% of purchase price) instead of order deposit
    order_deposit = deposit_total
    discount_amount = float(order[23] or 0) if order[23] else 0
    discount_percent = order[24] or 0
    # ВАЖЛИВО: order_rent (total_price) = вартість ВЖЕ зі знижкою
    rent_before_discount = order_rent + discount_amount  # Повна сума до знижки
    # Якщо відсоток 0, але є сума — розрахувати динамічно
    if (not discount_percent or discount_percent == 0) and discount_amount > 0 and rent_before_discount > 0:
        discount_percent = round((discount_amount / rent_before_discount) * 100, 1)
    service_fee = float(order[25] or 0)
    service_fee_name = order[26] or "Додаткова послуга"
    
    # Кошторис: order_rent = повна вартість оренди (ДО знижки)
    # grand_total = order_rent - знижка + послуги = сума до оплати
    grand_total = order_rent - discount_amount + service_fee
    
    # Delivery type label mapping
    delivery_type_labels = {
        "self_pickup": "Самовивіз",
        "delivery": "Доставка",
        "self": "Самовивіз",
        None: "Самовивіз"
    }
    delivery_type_label = delivery_type_labels.get(order[18], order[18] or "Самовивіз")
    
    # Завантажити індивідуальні додаткові послуги
    additional_services_raw = db.execute(text("""
        SELECT name, amount FROM order_additional_services 
        WHERE order_id = :oid ORDER BY id
    """), {"oid": order_id}).fetchall()
    additional_services = [
        {"name": row[0], "amount": float(row[1] or 0), "amount_fmt": _format_currency(float(row[1] or 0))}
        for row in additional_services_raw
    ]
    
    # Build template data matching quote.html structure
    template_data = {
        "order": {
            "order_number": order[1],
            "customer_name": order[3],
            "customer_phone": order[4] or order[21],  # customer_phone or phone
            "customer_email": order[5] or order[22],  # customer_email or email
            "phone": order[4] or order[21],
            "email": order[5] or order[22],
            "rental_start_date": _format_date_ua(order[6]),
            "rental_end_date": _format_date_ua(order[7]),
            "rental_days": rental_days,
            "delivery_type": order[18],
            "delivery_type_label": delivery_type_label,
            # For self_pickup show company address
            "city": order[16] if order[16] else ("Київ" if order[18] in ("self_pickup", "self", None) else "—"),
            "delivery_address": order[17] if order[17] else ("вул. Будіндустрії, 4" if order[18] in ("self_pickup", "self", None) else "—"),
            "event_type": order[19],
            "event_name": None,
            "event_location": None,
            "customer_comment": order[20],
            "total_price": order_rent,
            "total_price_fmt": _format_currency(order_rent),
            "deposit_amount": order_deposit,
            "deposit_amount_fmt": _format_currency(order_deposit),
            "discount_amount": discount_amount,
            "discount_percent": discount_percent,
            "service_fee": service_fee,
            "service_fee_name": service_fee_name
        },
        "items": formatted_items,
        "totals": {
            "rent_total_fmt": _format_currency(order_rent),  # Вартість оренди (зі знижкою, до сплати)
            "loss_total_fmt": _format_currency(loss_total),  # Повна сума збитку
            "deposit_total_fmt": _format_currency(order_deposit),  # Завдаток (50% від збитку)
            "discount_fmt": _format_currency(discount_amount) if discount_amount > 0 else None,
            "service_fee_fmt": _format_currency(service_fee) if service_fee > 0 else None,
            "service_fee_name": service_fee_name if service_fee > 0 else None,
            "grand_total_fmt": _format_currency(grand_total),  # РАЗОМ (оренда + послуги)
            "grand_total": grand_total
        },
        "company": get_company_config(db),
        "additional_services": additional_services,
        "generated_at": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "watermark": None  # Can be set to "ПОПЕРЕДНІЙ" or "ЗАТВЕРДЖЕНО"
    }
    
    template = jinja_env.get_template("documents/quote.html")
    _enrich_template_with_agreement(db, order, template_data)
    return HTMLResponse(content=template.render(**template_data), media_type="text/html")


@router.get("/estimate/{order_id}/pdf", response_class=HTMLResponse)
async def download_estimate_pdf(order_id: int, db: Session = Depends(get_rh_db)):
    """Generate printable HTML for estimate (use browser Print to PDF)"""
    
    order, items = _get_order_with_items(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Замовлення не знайдено")
    
    rental_days = order[15] if order[15] else 1
    if not rental_days and order[6] and order[7]:
        rental_days = (order[7] - order[6]).days + 1
    
    formatted_items = []
    rent_total = 0.0
    deposit_total = 0.0
    loss_total = 0.0  # Загальна сума збитку
    
    for item in items:
        qty = item[3] or 1
        rental_price_day = float(item[4] or item[8] or 0)
        total_rental = float(item[5] or 0)
        purchase_price = float(item[9] or 0)
        loss_per_item = purchase_price * qty  # Повна сума збитку
        deposit_per_item = loss_per_item / 2 if loss_per_item > 0 else 0  # 50% = завдаток
        
        rent_total += total_rental
        deposit_total += deposit_per_item
        loss_total += loss_per_item
        
        formatted_items.append({
            "product_name": item[2], "sku": item[7] or "—", "quantity": qty,
            "rental_price_fmt": _format_currency(rental_price_day),
            "price_per_day_fmt": _format_currency(rental_price_day),
            "loss_fmt": _format_currency(loss_per_item),  # Збиток (повна ціна)
            "deposit_fmt": _format_currency(deposit_per_item),
            "image_url": _get_full_image_url(item[6]), "note": None
        })
    
    order_rent = float(order[11] or 0) if order[11] else rent_total
    order_deposit = deposit_total
    discount_amount = float(order[23] or 0) if order[23] else 0
    discount_percent = order[24] or 0
    # ВАЖЛИВО: order_rent (total_price) = вартість ВЖЕ зі знижкою
    rent_before_discount = order_rent + discount_amount
    if (not discount_percent or discount_percent == 0) and discount_amount > 0 and rent_before_discount > 0:
        discount_percent = round((discount_amount / rent_before_discount) * 100, 1)
    service_fee = float(order[25] or 0)
    service_fee_name = order[26] or "Додаткова послуга"
    grand_total = order_rent - discount_amount + service_fee
    
    delivery_type_labels = {"self_pickup": "Самовивіз", "delivery": "Доставка", "self": "Самовивіз", None: "Самовивіз"}
    delivery_type_label = delivery_type_labels.get(order[18], order[18] or "Самовивіз")
    
    # Завантажити індивідуальні додаткові послуги (PDF)
    pdf_services_raw = db.execute(text("""
        SELECT name, amount FROM order_additional_services 
        WHERE order_id = :oid ORDER BY id
    """), {"oid": order_id}).fetchall()
    additional_services = [
        {"name": row[0], "amount": float(row[1] or 0), "amount_fmt": _format_currency(float(row[1] or 0))}
        for row in pdf_services_raw
    ]

    template_data = {
        "order": {
            "order_number": order[1], "customer_name": order[3],
            "customer_phone": order[4] or order[21], "customer_email": order[5] or order[22],
            "phone": order[4] or order[21], "email": order[5] or order[22],
            "rental_start_date": _format_date_ua(order[6]), "rental_end_date": _format_date_ua(order[7]),
            "rental_days": rental_days, "delivery_type": order[18], "delivery_type_label": delivery_type_label,
            "city": order[16] if order[16] else ("Київ" if order[18] in ("self_pickup", "self", None) else "—"),
            "delivery_address": order[17] if order[17] else ("вул. Будіндустрії, 4" if order[18] in ("self_pickup", "self", None) else "—"),
            "event_type": order[19], "event_name": None, "event_location": None, "customer_comment": order[20],
            "total_price": order_rent, "total_price_fmt": _format_currency(order_rent),
            "deposit_amount": order_deposit, "deposit_amount_fmt": _format_currency(order_deposit),
            "discount_amount": discount_amount, "discount_percent": discount_percent,
            "service_fee": service_fee, "service_fee_name": service_fee_name
        },
        "items": formatted_items,
        "totals": {
            "rent_total_fmt": _format_currency(order_rent),  # Вартість оренди (зі знижкою, до сплати)
            "loss_total_fmt": _format_currency(loss_total),  # Повна сума збитку
            "deposit_total_fmt": _format_currency(order_deposit),  # Завдаток (50%)
            "discount_fmt": _format_currency(discount_amount) if discount_amount > 0 else None,
            "service_fee_fmt": _format_currency(service_fee) if service_fee > 0 else None,
            "service_fee_name": service_fee_name if service_fee > 0 else None,
            "grand_total_fmt": _format_currency(grand_total),  # РАЗОМ (оренда + послуги)
            "grand_total": grand_total
        },
        "company": get_company_config(db),
        "additional_services": additional_services,
        "generated_at": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "watermark": None,
        "auto_print": True  # Trigger print dialog
    }
    
    template = jinja_env.get_template("documents/quote.html")
    _enrich_template_with_agreement(db, order, template_data)
    html_content = template.render(**template_data)
    print_script = '''<script>window.onload = function() { window.print(); }</script>'''
    html_content = html_content.replace('</body>', f'{print_script}</body>')
    
    return HTMLResponse(content=html_content, media_type="text/html")


class SendEstimateEmailRequest(BaseModel):
    recipient_email: str
    recipient_name: Optional[str] = None


@router.post("/estimate/{order_id}/send-email")
async def send_estimate_email(order_id: int, request: SendEstimateEmailRequest, db: Session = Depends(get_rh_db)):
    """Send estimate (Кошторис) via email"""
    from services.email_service import send_document_email
    
    order, items = _get_order_with_items(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Замовлення не знайдено")
    
    # Generate HTML (same logic as preview)
    rental_days = order[15] if order[15] else 1
    if not rental_days and order[6] and order[7]:
        rental_days = (order[7] - order[6]).days + 1
    
    formatted_items = []
    rent_total = 0.0
    deposit_total = 0.0
    loss_total = 0.0  # Загальна сума збитку
    
    for item in items:
        qty = item[3] or 1
        rental_price_day = float(item[4] or item[8] or 0)
        total_rental = float(item[5] or 0)
        purchase_price = float(item[9] or 0)
        loss_per_item = purchase_price * qty  # Повна сума збитку
        deposit_per_item = loss_per_item / 2 if loss_per_item > 0 else 0  # 50% = завдаток
        
        rent_total += total_rental
        deposit_total += deposit_per_item
        loss_total += loss_per_item
        
        formatted_items.append({
            "product_name": item[2],
            "sku": item[7] or "—",
            "quantity": qty,
            "rental_price_fmt": _format_currency(rental_price_day),
            "price_per_day_fmt": _format_currency(rental_price_day),
            "loss_fmt": _format_currency(loss_per_item),  # Збиток (повна ціна)
            "deposit_fmt": _format_currency(deposit_per_item),
            "image_url": _get_full_image_url(item[6]),
            "note": None
        })
    
    order_rent = float(order[11] or 0) if order[11] else rent_total
    order_deposit = deposit_total
    discount_amount = float(order[23] or 0) if order[23] else 0
    discount_percent = order[24] or 0
    # ВАЖЛИВО: order_rent (total_price) = вартість ВЖЕ зі знижкою
    rent_before_discount = order_rent + discount_amount
    if (not discount_percent or discount_percent == 0) and discount_amount > 0 and rent_before_discount > 0:
        discount_percent = round((discount_amount / rent_before_discount) * 100, 1)
    service_fee = float(order[25] or 0)
    service_fee_name = order[26] or "Додаткова послуга"
    grand_total = order_rent - discount_amount + service_fee
    
    delivery_type_labels = {"self_pickup": "Самовивіз", "delivery": "Доставка", "self": "Самовивіз", None: "Самовивіз"}
    delivery_type_label = delivery_type_labels.get(order[18], order[18] or "Самовивіз")
    
    # Завантажити індивідуальні додаткові послуги (Email)
    email_services_raw = db.execute(text("""
        SELECT name, amount FROM order_additional_services 
        WHERE order_id = :oid ORDER BY id
    """), {"oid": order_id}).fetchall()
    additional_services = [
        {"name": row[0], "amount": float(row[1] or 0), "amount_fmt": _format_currency(float(row[1] or 0))}
        for row in email_services_raw
    ]

    template_data = {
        "order": {
            "order_number": order[1], "customer_name": order[3],
            "customer_phone": order[4] or order[21], "customer_email": order[5] or order[22],
            "phone": order[4] or order[21], "email": order[5] or order[22],
            "rental_start_date": _format_date_ua(order[6]), "rental_end_date": _format_date_ua(order[7]),
            "rental_days": rental_days, "delivery_type": order[18], "delivery_type_label": delivery_type_label,
            "city": order[16] if order[16] else ("Київ" if order[18] in ("self_pickup", "self", None) else "—"),
            "delivery_address": order[17] if order[17] else ("вул. Будіндустрії, 4" if order[18] in ("self_pickup", "self", None) else "—"),
            "event_type": order[19], "event_name": None, "event_location": None, "customer_comment": order[20],
            "total_price": order_rent, "total_price_fmt": _format_currency(order_rent),
            "deposit_amount": order_deposit, "deposit_amount_fmt": _format_currency(order_deposit),
            "discount_amount": discount_amount, "discount_percent": discount_percent,
            "service_fee": service_fee, "service_fee_name": service_fee_name
        },
        "items": formatted_items,
        "totals": {
            "rent_total_fmt": _format_currency(order_rent),  # Вартість оренди (зі знижкою, до сплати)
            "loss_total_fmt": _format_currency(loss_total),  # Повна сума збитку
            "deposit_total_fmt": _format_currency(order_deposit),  # Завдаток (50%)
            "discount_fmt": _format_currency(discount_amount) if discount_amount > 0 else None,
            "service_fee_fmt": _format_currency(service_fee) if service_fee > 0 else None,
            "service_fee_name": service_fee_name if service_fee > 0 else None,
            "grand_total_fmt": _format_currency(grand_total),  # РАЗОМ (оренда + послуги)
            "grand_total": grand_total
        },
        "company": get_company_config(db),
        "additional_services": additional_services,
        "generated_at": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "watermark": None
    }
    
    # Use email-specific template with inline styles
    template = jinja_env.get_template("documents/quote_email.html")
    html_content = template.render(**template_data)
    
    # Send email
    result = send_document_email(
        to_email=request.recipient_email,
        document_type="estimate",
        document_html=html_content,
        order_number=order[1],
        customer_name=request.recipient_name or order[3]
    )
    
    if not result["success"]:
        raise HTTPException(status_code=500, detail=result["message"])
    
    return {"success": True, "message": f"Кошторис відправлено на {request.recipient_email}"}


# ============================================================
# ANNEX (ДОДАТОК) - Quick Preview  
# ============================================================

@router.get("/annex/{order_id}/preview", response_class=HTMLResponse)
async def preview_annex(
    order_id: int,
    agreement_id: Optional[int] = Query(None),
    db: Session = Depends(get_rh_db)
):
    """Generate HTML preview of annex (Додаток)"""
    
    order, items = _get_order_with_items(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Замовлення не знайдено")
    
    agreement = None
    executor = EXECUTORS["tov"]
    
    if agreement_id:
        agreement_row = db.execute(text("""
            SELECT ma.id, ma.contract_number, ma.valid_from, ma.snapshot_json
            FROM master_agreements ma WHERE ma.id = :id
        """), {"id": agreement_id}).fetchone()
        
        if agreement_row:
            agreement = {"id": agreement_row[0], "number": agreement_row[1], "date": _format_date_ua(agreement_row[2])}
            if agreement_row[3]:
                try:
                    snapshot = json.loads(agreement_row[3]) if isinstance(agreement_row[3], str) else agreement_row[3]
                    executor = snapshot.get("executor") or EXECUTORS.get(snapshot.get("executor_type", "tov"), EXECUTORS["tov"])
                except:
                    pass
    
    if not agreement:
        agreement = {"number": "_____", "date": "«___» _______ 202_ р."}
    
    rental_days = order[15] or 1
    if not rental_days and order[6] and order[7]:
        rental_days = (order[7] - order[6]).days + 1
    
    annex_number = 1
    if agreement_id:
        count = db.execute(text("SELECT COUNT(*) FROM order_annexes WHERE master_agreement_id = :aid"), {"aid": agreement_id}).fetchone()[0]
        annex_number = count + 1
    
    formatted_items = []
    total_qty = 0
    for item in items:
        # New structure: [id, product_id, product_name, quantity, price, total_rental, image_url, sku, rental_price]
        formatted_items.append({"name": item[2], "quantity": item[3], "total_rental": _format_currency(item[5]), "packing_type": None})
        total_qty += item[3]
    
    client = {"name": order[3], "phone": order[4] or order[21], "email": order[5] or order[22], "payer_type": "individual", "director_name": None,
              "contact_person": order[3], "contact_channel": "phone", "contact_value": order[4] or order[21]}
    
    # Check if client has payer_type
    if order[2]:
        client_row = db.execute(text("SELECT payer_type FROM client_users WHERE id = :id"), {"id": order[2]}).fetchone()
        if client_row:
            client["payer_type"] = client_row[0] or "individual"
    
    template_data = {
        "annex": {"number": annex_number, "date": _format_date_ua(datetime.now())},
        "agreement": agreement, "executor": executor, "client": client, "items": formatted_items,
        "rental_days": rental_days,
        "rental_start_date": _format_date_ua_long(order[6]), "rental_end_date": _format_date_ua_long(order[7]),
        "issue_date": _format_date_ua_long(order[8] or order[6]), "return_date": _format_date_ua_long(order[9] or order[7]),
        "totals": {"quantity": total_qty, "rental": _format_currency(order[11]), "deposit": _format_currency(order[12])}
    }
    
    template = jinja_env.get_template("documents/annex.html")
    _enrich_template_with_agreement(db, order, template_data)
    return HTMLResponse(content=template.render(**template_data), media_type="text/html")


# ============================================================
# INVOICE OFFER (РАХУНОК-ОФЕРТА)
# ============================================================

@router.get("/invoice-offer/{order_id}/preview", response_class=HTMLResponse)
async def preview_invoice_offer(
    order_id: int,
    db: Session = Depends(get_rh_db)
):
    """Generate HTML preview of invoice offer (Рахунок-оферта) - official document with bank details"""
    
    order, items = _get_order_with_items(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Замовлення не знайдено")
    
    rental_days = order[15] or 1
    if not rental_days and order[6] and order[7]:
        rental_days = (order[7] - order[6]).days + 1
    
    # Format items
    formatted_items = []
    rent_total = 0.0
    deposit_total = 0.0
    
    for item in items:
        qty = item[3] or 1
        rental_price_day = float(item[4] or item[8] or 0)
        total_rental = float(item[5] or 0)
        
        # Deposit = purchase_price * qty (full item value as deposit)
        purchase_price = float(item[9] or 0)
        deposit_per_item = purchase_price * qty
        
        rent_total += total_rental
        deposit_total += deposit_per_item
        
        formatted_items.append({
            "product_name": item[2],
            "sku": item[7] or "—",
            "quantity": qty,
            "rental_price_day_fmt": _format_currency(rental_price_day),
            "rental_total_fmt": _format_currency(total_rental),
            "deposit_fmt": _format_currency(deposit_per_item),
        })
    
    # Totals
    order_rent = float(order[11] or 0) if order[11] else rent_total
    order_deposit = float(order[12] or 0) if order[12] else deposit_total
    discount_amount = float(order[23] or 0) if order[23] else 0
    discount_percent = order[24] or 0
    
    # Additional services
    service_fee = float(order[25] or 0)
    service_fee_name = order[26] or "Додаткова послуга"
    
    additional_services_raw = db.execute(text("""
        SELECT name, amount FROM order_additional_services 
        WHERE order_id = :oid
    """), {"oid": order_id}).fetchall()
    additional_services = [{"name": row[0], "amount": _format_currency(row[1])} for row in additional_services_raw]
    
    # ВАЖЛИВО: order_rent (total_price) вже зі знижкою — не віднімаємо ще раз
    grand_total = order_rent + service_fee + order_deposit
    
    # Delivery type
    delivery_type_labels = {"self_pickup": "Самовивіз", "delivery": "Доставка", "self": "Самовивіз", None: "Самовивіз"}
    delivery_type_label = delivery_type_labels.get(order[18], order[18] or "Самовивіз")
    
    company = get_company_config(db)
    
    template_data = {
        "order": {
            "order_number": order[1],
            "customer_name": order[3],
            "customer_phone": order[4] or order[21],
            "customer_email": order[5] or order[22],
            "phone": order[4] or order[21],
            "email": order[5] or order[22],
            "rental_start_date": _format_date_ua(order[6]),
            "rental_end_date": _format_date_ua(order[7]),
            "rental_days": rental_days,
            "delivery_type_label": delivery_type_label,
            "discount_percent": discount_percent,
            "service_fee": service_fee,
            "service_fee_name": service_fee_name,
        },
        "items": formatted_items,
        "totals": {
            "rental_fmt": _format_currency(order_rent),
            "deposit_fmt": _format_currency(order_deposit),
            "discount_fmt": _format_currency(discount_amount) if discount_amount > 0 else None,
            "service_fee_fmt": _format_currency(service_fee) if service_fee > 0 else None,
            "service_fee_name": service_fee_name if service_fee > 0 else None,
            "grand_total_fmt": _format_currency(grand_total),
        },
        "additional_services": additional_services,
        "company": company,
        "generated_at": datetime.now().strftime("%d.%m.%Y %H:%M"),
    }
    
    template = jinja_env.get_template("documents/invoice_offer.html")
    _enrich_template_with_agreement(db, order, template_data)
    return HTMLResponse(content=template.render(**template_data), media_type="text/html")


@router.get("/invoice-offer/{order_id}/pdf")
async def download_invoice_offer_pdf(
    order_id: int,
    db: Session = Depends(get_rh_db)
):
    """Download invoice offer as PDF (print dialog)"""
    
    order, items = _get_order_with_items(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Замовлення не знайдено")
    
    rental_days = order[15] or 1
    if not rental_days and order[6] and order[7]:
        rental_days = (order[7] - order[6]).days + 1
    
    formatted_items = []
    rent_total = 0.0
    deposit_total = 0.0
    
    for item in items:
        qty = item[3] or 1
        rental_price_day = float(item[4] or item[8] or 0)
        total_rental = float(item[5] or 0)
        purchase_price = float(item[9] or 0)
        deposit_per_item = purchase_price * qty
        rent_total += total_rental
        deposit_total += deposit_per_item
        formatted_items.append({
            "product_name": item[2],
            "sku": item[7] or "—",
            "quantity": qty,
            "rental_price_day_fmt": _format_currency(rental_price_day),
            "rental_total_fmt": _format_currency(total_rental),
            "deposit_fmt": _format_currency(deposit_per_item),
        })
    
    order_rent = float(order[11] or 0) if order[11] else rent_total
    order_deposit = float(order[12] or 0) if order[12] else deposit_total
    discount_amount = float(order[23] or 0) if order[23] else 0
    discount_percent = order[24] or 0
    
    service_fee = float(order[25] or 0)
    service_fee_name = order[26] or "Додаткова послуга"
    
    additional_services_raw = db.execute(text("""
        SELECT name, amount FROM order_additional_services WHERE order_id = :oid
    """), {"oid": order_id}).fetchall()
    additional_services = [{"name": row[0], "amount": _format_currency(row[1])} for row in additional_services_raw]
    
    # ВАЖЛИВО: order_rent (total_price) вже зі знижкою — не віднімаємо ще раз
    grand_total = order_rent + service_fee + order_deposit
    
    delivery_type_labels = {"self_pickup": "Самовивіз", "delivery": "Доставка", "self": "Самовивіз", None: "Самовивіз"}
    delivery_type_label = delivery_type_labels.get(order[18], order[18] or "Самовивіз")
    
    company = get_company_config(db)
    
    template_data = {
        "order": {
            "order_number": order[1],
            "customer_name": order[3],
            "customer_phone": order[4] or order[21],
            "customer_email": order[5] or order[22],
            "rental_start_date": _format_date_ua(order[6]),
            "rental_end_date": _format_date_ua(order[7]),
            "rental_days": rental_days,
            "delivery_type_label": delivery_type_label,
            "discount_percent": discount_percent,
        },
        "items": formatted_items,
        "totals": {
            "rental_fmt": _format_currency(order_rent),
            "deposit_fmt": _format_currency(order_deposit),
            "discount_fmt": _format_currency(discount_amount) if discount_amount > 0 else None,
            "service_fee_fmt": _format_currency(service_fee) if service_fee > 0 else None,
            "service_fee_name": service_fee_name if service_fee > 0 else None,
            "grand_total_fmt": _format_currency(grand_total),
        },
        "additional_services": additional_services,
        "company": company,
        "generated_at": datetime.now().strftime("%d.%m.%Y %H:%M"),
    }
    
    template = jinja_env.get_template("documents/invoice_offer.html")
    _enrich_template_with_agreement(db, order, template_data)
    html_content = template.render(**template_data)
    
    # Add auto-print script
    print_script = '''<script>window.onload = function() { window.print(); }</script>'''
    html_content = html_content.replace('</body>', f'{print_script}</body>')
    
    return HTMLResponse(content=html_content, media_type="text/html")


# ============================================================
# ISSUE ACT (АКТ ВИДАЧІ)
# ============================================================

def _build_issue_act_data(db: Session, order_id: int, executor_type: str = "fop"):
    """Build data for the issue act template."""
    order, items = _get_order_with_items(db, order_id)
    if not order:
        return None
    
    executor = EXECUTORS.get(executor_type, EXECUTORS["tov"])
    rental_days = order[15] or 1
    
    # Load per-item packaging from issue_cards
    item_packaging_map = {}
    ITEM_PACK_LABELS = {
        "native_cover": "Рідний чохол",
        "native_box": "Рідна коробка",
        "felt": "Войлок",
        "special": "Спец. пакування",
        # "other" handled separately with other_text
        # Legacy keys
        "cover": "Чохол",
        "box": "Коробка",
    }
    try:
        ic_row = db.execute(text("""
            SELECT items FROM issue_cards WHERE order_id = :oid ORDER BY id DESC LIMIT 1
        """), {"oid": order_id}).fetchone()
        if ic_row and ic_row[0]:
            ic_items = json.loads(ic_row[0]) if isinstance(ic_row[0], str) else ic_row[0]
            for ic_item in ic_items:
                item_id = ic_item.get("id")
                sku = ic_item.get("sku")
                pkg = ic_item.get("packaging", {})
                if pkg:
                    labels = []
                    for key, label in ITEM_PACK_LABELS.items():
                        val = pkg.get(key)
                        qty = int(val) if isinstance(val, (int, float)) else (1 if val else 0)
                        if qty > 0:
                            labels.append(f"{label}: {qty}" if qty > 1 else label)
                    if pkg.get("other"):
                        other_text = pkg.get("other_text", "")
                        other_qty = int(pkg["other"]) if isinstance(pkg["other"], (int, float)) else 1
                        other_label = f"Інше ({other_text})" if other_text else "Інше"
                        labels.append(f"{other_label}: {other_qty}" if other_qty > 1 else other_label)
                    if labels:
                        if item_id:
                            item_packaging_map[int(item_id)] = labels
                            item_packaging_map[str(item_id)] = labels
                        if sku:
                            item_packaging_map[sku] = labels
    except Exception:
        pass
    
    # Format items with full details
    formatted_items = []
    total_qty = 0
    for it in items:
        qty = it[3] or 1
        total_qty += qty
        sku = it[7] or "—"
        item_id = it[1]  # product_id to match issue_cards items
        
        # Per-item packaging
        pack_labels = item_packaging_map.get(item_id, []) or item_packaging_map.get(sku, [])
        
        # Load damage history for this product by SKU
        damages = []
        if sku and sku != "—":
            try:
                damage_rows = db.execute(text("""
                    SELECT damage_type, note, photo_url, stage, created_at, created_by
                    FROM product_damage_history
                    WHERE sku = :sku
                    ORDER BY created_at DESC
                """), {"sku": sku}).fetchall()
                for d in damage_rows:
                    damages.append({
                        "damage_type": d[0] or "Дефект",
                        "note": d[1],
                        "photo_url": d[2],
                        "stage": d[3],
                        "created_at": _format_date_ua(d[4]) if d[4] else "",
                        "created_by": d[5] or ""
                    })
            except Exception:
                pass
        
        formatted_items.append({
            "name": it[2],
            "sku": sku,
            "quantity": qty,
            "image_url": _get_full_image_url(it[6]),
            "damages": damages,
            "has_damage": len(damages) > 0,
            "packaging_labels": pack_labels,
            "has_packaging": len(pack_labels) > 0,
        })
    
    # Load packaging
    packaging_items = []
    PACKAGING_LABELS = {
        "bag_s": "Сумка S",
        "bag_m": "Сумка M",
        "bag_l": "Сумка L",
        "cover": "Чохол",
        "black_box": "Чорний ящик",
    }
    try:
        pkg_rows = db.execute(text("""
            SELECT item_key, quantity FROM order_packaging
            WHERE order_id = :oid AND quantity > 0
        """), {"oid": order_id}).fetchall()
        for r in pkg_rows:
            packaging_items.append({
                "key": r[0],
                "label": PACKAGING_LABELS.get(r[0], r[0]),
                "quantity": r[1]
            })
    except Exception:
        pass
    
    act_number = f"В-{datetime.now().strftime('%Y')}-{order[0]:06d}"
    
    return {
        "act_number": act_number,
        "act_date": datetime.now().strftime("%d.%m.%Y"),
        "generated_at": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "executor": executor,
        "client": {
            "name": order[3],
            "phone": order[4] or order[21],
            "email": order[5] or order[22] or "",
            "contact_person": order[3]
        },
        "order": {
            "number": order[1],
            "rental_start_date": _format_date_ua(order[6]),
            "rental_end_date": _format_date_ua(order[7]),
            "rental_days": rental_days,
        },
        "items": formatted_items,
        "packaging": packaging_items,
        "has_packaging": len(packaging_items) > 0,
        "has_any_damage": any(it["has_damage"] for it in formatted_items),
        "rental_days": rental_days,
        "rental_start_date": _format_date_ua(order[6]),
        "rental_end_date": _format_date_ua(order[7]),
        "return_date": _format_date_ua(order[9] or order[7]),
        "totals": {"items_count": len(items), "quantity": total_qty},
        "company": get_company_config(db),
    }
    
    _enrich_template_with_agreement(db, order, template_data)
    return template_data


@router.get("/issue-act/{order_id}/preview", response_class=HTMLResponse)
async def preview_issue_act(
    order_id: int,
    executor_type: str = Query("fop"),
    db: Session = Depends(get_rh_db)
):
    """Generate HTML preview of issue act (Акт видачі)"""
    template_data = _build_issue_act_data(db, order_id, executor_type)
    if not template_data:
        raise HTTPException(status_code=404, detail="Замовлення не знайдено")
    
    template = jinja_env.get_template("documents/issue_act.html")
    return HTMLResponse(content=template.render(**template_data), media_type="text/html")


@router.get("/issue-act/{order_id}/pdf", response_class=HTMLResponse)
async def download_issue_act_pdf(
    order_id: int,
    executor_type: str = Query("fop"),
    db: Session = Depends(get_rh_db)
):
    """Generate printable HTML for issue act (use browser Print to PDF)"""
    template_data = _build_issue_act_data(db, order_id, executor_type)
    if not template_data:
        raise HTTPException(status_code=404, detail="Замовлення не знайдено")
    
    template = jinja_env.get_template("documents/issue_act.html")
    return HTMLResponse(content=template.render(**template_data), media_type="text/html")



# ============================================================
# PICKING LIST (ЛИСТ КОМПЛЕКТАЦІЇ)
# ============================================================

@router.get("/picking-list/{order_id}/preview", response_class=HTMLResponse)
async def preview_picking_list(order_id: int, db: Session = Depends(get_rh_db)):
    """Generate HTML preview of picking list (Лист комплектації)"""
    
    order, items = _get_order_with_items(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Замовлення не знайдено")
    
    rental_days = order[15] or 1
    
    # Format items with full details + location from products
    formatted_items = []
    total_qty = 0
    for it in items:
        qty = it[3] or 1
        total_qty += qty
        
        # Get location from products table
        location = "—"
        if it[1]:
            try:
                loc_row = db.execute(text("""
                    SELECT zone, aisle, shelf FROM products WHERE product_id = :pid
                """), {"pid": it[1]}).fetchone()
                if loc_row:
                    parts = [str(x) for x in [loc_row[0], loc_row[1], loc_row[2]] if x]
                    location = "-".join(parts) if parts else "—"
            except Exception:
                pass
        
        formatted_items.append({
            "name": it[2],
            "sku": it[7] or "—",
            "quantity": qty,
            "image_url": _get_full_image_url(it[6]),
            "location": location,
        })
    
    template_data = {
        "order": {
            "number": order[1],
            "customer_name": order[3],
            "customer_phone": order[4] or order[21],
            "rental_start_date": _format_date_ua(order[6]),
            "rental_end_date": _format_date_ua(order[7]),
            "rental_days": rental_days,
        },
        "items": formatted_items,
        "totals": {"items_count": len(items), "quantity": total_qty},
        "generated_at": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "company": get_company_config(db),
    }
    
    template = jinja_env.get_template("documents/picking_list.html")
    return HTMLResponse(content=template.render(**template_data), media_type="text/html")


@router.get("/annex/{order_id}/pdf")
async def download_annex_pdf(order_id: int, agreement_id: Optional[int] = Query(None), db: Session = Depends(get_rh_db)):
    """Download annex as PDF"""
    
    order, items = _get_order_with_items(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Замовлення не знайдено")
    
    agreement = None
    executor = EXECUTORS["tov"]
    
    if agreement_id:
        agreement_row = db.execute(text("SELECT id, contract_number, valid_from, snapshot_json FROM master_agreements WHERE id = :id"), {"id": agreement_id}).fetchone()
        if agreement_row:
            agreement = {"number": agreement_row[1], "date": _format_date_ua(agreement_row[2])}
            if agreement_row[3]:
                try:
                    snapshot = json.loads(agreement_row[3]) if isinstance(agreement_row[3], str) else agreement_row[3]
                    executor = snapshot.get("executor") or EXECUTORS.get(snapshot.get("executor_type", "tov"), EXECUTORS["tov"])
                except:
                    pass
    
    if not agreement:
        agreement = {"number": "_____", "date": "«___» _______ 202_ р."}
    
    rental_days = order[15] or 1
    annex_number = 1
    if agreement_id:
        count = db.execute(text("SELECT COUNT(*) FROM order_annexes WHERE master_agreement_id = :aid"), {"aid": agreement_id}).fetchone()[0]
        annex_number = count + 1
    
    # New structure: [id, product_id, product_name, quantity, price, total_rental, image_url, sku, rental_price]
    formatted_items = [{"name": it[2], "quantity": it[3], "total_rental": _format_currency(it[5]), "packing_type": None} for it in items]
    total_qty = sum(it[3] for it in items)
    
    client = {"name": order[3], "payer_type": "individual", "director_name": None, "contact_person": order[3], "contact_channel": "phone", "contact_value": order[4] or order[21]}
    
    template_data = {
        "annex": {"number": annex_number, "date": _format_date_ua(datetime.now())},
        "agreement": agreement, "executor": executor, "client": client, "items": formatted_items,
        "rental_days": rental_days,
        "rental_start_date": _format_date_ua_long(order[6]), "rental_end_date": _format_date_ua_long(order[7]),
        "issue_date": _format_date_ua_long(order[8] or order[6]), "return_date": _format_date_ua_long(order[9] or order[7]),
        "totals": {"quantity": total_qty, "rental": _format_currency(order[11]), "deposit": _format_currency(order[12])}
    }
    
    template = jinja_env.get_template("documents/annex.html")
    _enrich_template_with_agreement(db, order, template_data)
    html_content = template.render(**template_data)
    
    return HTMLResponse(content=html_content, media_type="text/html")

async def get_latest_documents_batch(
    request: LatestBatchRequest,
    db: Session = Depends(get_rh_db)
):
    """
    ОПТИМІЗОВАНИЙ endpoint: Отримує останні версії кількох документів одним запитом.
    Замість N окремих запитів на /latest/{type}/{id}/{doc_type} - один запит.
    """
    if not request.doc_types:
        return {"documents": {}}
    
    # Один SQL запит для всіх типів документів
    placeholders = ", ".join([f":doc_type_{i}" for i in range(len(request.doc_types))])
    params = {
        "entity_type": request.entity_type,
        "entity_id": str(request.entity_id),
    }
    for i, dt in enumerate(request.doc_types):
        params[f"doc_type_{i}"] = dt
    
    result = db.execute(text(f"""
        SELECT d1.id, d1.doc_type, d1.doc_number, d1.version, d1.status, 
               d1.signed_at, d1.created_at, d1.html_content
        FROM documents d1
        INNER JOIN (
            SELECT doc_type, MAX(version) as max_version
            FROM documents
            WHERE entity_type = :entity_type AND entity_id = :entity_id
              AND doc_type IN ({placeholders})
            GROUP BY doc_type
        ) d2 ON d1.doc_type = d2.doc_type AND d1.version = d2.max_version
        WHERE d1.entity_type = :entity_type AND d1.entity_id = :entity_id
    """), params)
    
    documents = {}
    for row in result:
        doc_type = row[1]
        config = DOC_REGISTRY.get(doc_type, {})
        documents[doc_type] = {
            "exists": True,
            "id": row[0],
            "doc_type": doc_type,
            "doc_type_name": config.get("name", doc_type),
            "doc_number": row[2],
            "version": row[3],
            "status": row[4],
            "signed_at": row[5].isoformat() if row[5] else None,
            "created_at": row[6].isoformat() if row[6] else None,
            "preview_url": f"/api/documents/{row[0]}/preview",
            "pdf_url": f"/api/documents/{row[0]}/pdf",
            "html_content": row[7]
        }
    
    # Для типів без документів - повертаємо exists: false
    for doc_type in request.doc_types:
        if doc_type not in documents:
            documents[doc_type] = {
                "exists": False,
                "message": "Документ ще не згенеровано"
            }
    
    return {"documents": documents}


@router.get("/history/{entity_type}/{entity_id}/{doc_type}")
async def get_document_history(
    entity_type: str,
    entity_id: str,
    doc_type: str,
    db: Session = Depends(get_rh_db)
):
    """
    Отримує історію всіх версій документа певного типу.
    """
    result = db.execute(text("""
        SELECT id, doc_type, doc_number, version, status, signed_at, created_at
        FROM documents
        WHERE entity_type = :entity_type 
          AND entity_id = :entity_id 
          AND doc_type = :doc_type
        ORDER BY version DESC
    """), {"entity_type": entity_type, "entity_id": entity_id, "doc_type": doc_type})
    
    config = DOC_REGISTRY.get(doc_type, {})
    
    versions = []
    for row in result:
        versions.append({
            "id": row[0],
            "doc_type": row[1],
            "doc_type_name": config.get("name", doc_type),
            "doc_number": row[2],
            "version": row[3],
            "status": row[4],
            "signed_at": row[5].isoformat() if row[5] else None,
            "created_at": row[6].isoformat() if row[6] else None,
            "preview_url": f"/api/documents/{row[0]}/preview",
            "pdf_url": f"/api/documents/{row[0]}/pdf"
        })
    
    return {
        "doc_type": doc_type,
        "doc_type_name": config.get("name", doc_type),
        "total_versions": len(versions),
        "versions": versions
    }


# ============================================================
# PROCESSING QUEUE LISTS (Списки мийки / реставрації / партій)
# ============================================================

@router.get("/processing-list/{queue_type}/preview", response_class=HTMLResponse)
async def preview_processing_list(queue_type: str, db: Session = Depends(get_rh_db)):
    """Generate HTML list of items in processing queue (wash/restoration)"""
    
    if queue_type not in ('wash', 'restoration', 'laundry'):
        raise HTTPException(status_code=400, detail="queue_type must be 'wash', 'restoration' or 'laundry'")
    
    titles = {'wash': 'Мийка', 'restoration': 'Реставрація', 'laundry': 'Пральня'}
    
    rows = db.execute(text("""
        SELECT pdh.id, pdh.product_id, pdh.sku, pdh.product_name, pdh.damage_type,
               pdh.note, pdh.created_at, pdh.created_by, pdh.order_number,
               pdh.photo_url, pdh.processing_status, pdh.qty, pdh.processed_qty,
               p.image_url AS product_image
        FROM product_damage_history pdh
        LEFT JOIN products p ON p.product_id = pdh.product_id
        WHERE pdh.processing_type = :ptype
          AND COALESCE(pdh.processing_status, '') NOT IN ('completed', 'returned_to_stock', 'hidden', 'deleted')
          AND (COALESCE(pdh.qty, 1) - COALESCE(pdh.processed_qty, 0)) > 0
        ORDER BY pdh.created_at DESC
    """), {"ptype": queue_type}).fetchall()
    
    items = []
    for r in rows:
        total_qty = r[11] or 1
        processed = r[12] or 0
        remaining = total_qty - processed
        items.append({
            "sku": r[2] or "—",
            "name": r[3] or "—",
            "damage_type": r[4] or "—",
            "note": r[5] or "",
            "created_at": r[6].strftime("%d.%m.%Y %H:%M") if r[6] else "—",
            "created_by": _email_to_name(r[7]),
            "order_number": r[8] or "—",
            "image_url": _get_full_image_url(r[13] or r[9]),
            "status": r[10] or "pending",
            "qty": remaining,
            "total_qty": total_qty,
            "processed_qty": processed,
        })
    
    template_data = {
        "title": titles.get(queue_type, queue_type),
        "queue_type": queue_type,
        "items": items,
        "total_count": len(items),
        "total_qty": sum(i["qty"] for i in items),
        "generated_at": datetime.now().strftime("%d.%m.%Y %H:%M"),
    }
    
    template = jinja_env.get_template("documents/processing_list.html")
    return HTMLResponse(content=template.render(**template_data), media_type="text/html")


@router.get("/laundry-batch/{batch_id}/preview", response_class=HTMLResponse)
async def preview_laundry_batch(batch_id: str, db: Session = Depends(get_rh_db)):
    """Generate HTML list of items in a laundry batch"""
    
    batch_row = db.execute(text("""
        SELECT id, batch_number, laundry_company, status, sent_date, 
               total_items, returned_items, created_by, batch_type, notes
        FROM laundry_batches WHERE id = :bid
    """), {"bid": batch_id}).fetchone()
    
    if not batch_row:
        raise HTTPException(status_code=404, detail="Партію не знайдено")
    
    items_rows = db.execute(text("""
        SELECT li.id, li.batch_id, li.product_name, li.sku, li.quantity,
               li.returned_quantity, li.notes, li.category,
               p.image_url AS product_image
        FROM laundry_items li
        LEFT JOIN products p ON li.product_id = p.product_id
        WHERE li.batch_id = :bid
        ORDER BY li.product_name
    """), {"bid": batch_id}).fetchall()
    
    items = []
    for r in items_rows:
        items.append({
            "name": r[2] or "—",
            "sku": r[3] or "—",
            "quantity": r[4] or 1,
            "returned_qty": r[5] or 0,
            "notes": r[6] or "",
            "damage_type": r[7] or "—",
            "order_number": "—",
            "sent_by": _email_to_name(batch_row[7]),
            "image_url": _get_full_image_url(r[8]),
        })
    
    status_labels = {
        'sent': 'Відправлено',
        'partial_return': 'Часткове повернення',
        'returned': 'Повернено',
        'completed': 'Завершено',
    }
    batch_type_labels = {'laundry': 'Хімчистка', 'washing': 'Прання'}
    
    template_data = {
        "title": f"Партія {batch_type_labels.get(batch_row[8], 'Пральня')}",
        "batch": {
            "number": batch_row[1],
            "company": batch_row[2],
            "status": status_labels.get(batch_row[3], batch_row[3]),
            "sent_date": batch_row[4].strftime("%d.%m.%Y") if batch_row[4] else "—",
            "total_items": batch_row[5] or 0,
            "returned_items": batch_row[6] or 0,
            "created_by": _email_to_name(batch_row[7]),
            "batch_type": batch_type_labels.get(batch_row[8], batch_row[8] or "—"),
            "notes": batch_row[9] or "",
        },
        "items": items,
        "total_qty": sum(i["quantity"] for i in items),
        "total_returned": sum(i["returned_qty"] for i in items),
        "generated_at": datetime.now().strftime("%d.%m.%Y %H:%M"),
    }
    
    template = jinja_env.get_template("documents/processing_list.html")
    return HTMLResponse(content=template.render(**template_data), media_type="text/html")



# ============================================================
# INVOICE PAYMENT (РАХУНОК НА ОПЛАТУ) & SERVICE ACT (АКТ НАДАННЯ ПОСЛУГ)
# ============================================================

def _number_to_text_ua(amount: float) -> str:
    """Convert number to Ukrainian text for documents"""
    units = ['', 'одна', 'дві', 'три', 'чотири', "п'ять", 'шість', 'сім', 'вісім', "дев'ять"]
    teens = ['десять', 'одинадцять', 'дванадцять', 'тринадцять', 'чотирнадцять',
             "п'ятнадцять", 'шістнадцять', 'сімнадцять', 'вісімнадцять', "дев'ятнадцять"]
    tens = ['', 'десять', 'двадцять', 'тридцять', 'сорок', "п'ятдесят",
            'шістдесят', 'сімдесят', 'вісімдесят', "дев'яносто"]
    hundreds = ['', 'сто', 'двісті', 'триста', 'чотириста', "п'ятсот",
                'шістсот', 'сімсот', 'вісімсот', "дев'ятсот"]
    
    int_part = int(amount)
    kopecks = round((amount - int_part) * 100)
    
    if int_part == 0:
        result = "нуль"
    else:
        parts = []
        # Thousands
        thousands = int_part // 1000
        remainder = int_part % 1000
        
        if thousands > 0:
            if thousands == 1:
                parts.append("одна тисяча")
            elif thousands == 2:
                parts.append("дві тисячі")
            elif thousands in (3, 4):
                t_units = ['', 'одна', 'дві', 'три', 'чотири']
                parts.append(f"{t_units[thousands]} тисячі")
            elif 5 <= thousands <= 20:
                t_text = []
                if thousands >= 10:
                    t_text.append(teens[thousands - 10] if thousands < 20 else tens[thousands // 10])
                else:
                    t_text.append(units[thousands] if thousands < 10 else teens[thousands - 10])
                parts.append(f"{''.join(t_text)} тисяч")
            else:
                parts.append(f"{thousands} тисяч")
        
        if remainder > 0:
            h = remainder // 100
            t = (remainder % 100) // 10
            u = remainder % 10
            
            if h > 0:
                parts.append(hundreds[h])
            
            if t == 1:
                parts.append(teens[u])
            else:
                if t > 0:
                    parts.append(tens[t])
                if u > 0:
                    parts.append(units[u])
        
        result = ' '.join(parts)
    
    result = result.strip()
    if result:
        result = result[0].upper() + result[1:]
    
    # Гривень / гривня / гривні
    last_digit = int_part % 10
    last_two = int_part % 100
    if last_two in (11, 12, 13, 14):
        hrn_word = "гривень"
    elif last_digit == 1:
        hrn_word = "гривня"
    elif last_digit in (2, 3, 4):
        hrn_word = "гривні"
    else:
        hrn_word = "гривень"
    
    return f"{result} {hrn_word} {kopecks:02d} копійок"


def _get_order_payer(db: Session, order_id: int):
    """Get payer profile linked to the order's client (default payer)"""
    # First check if order has a direct payer_profile_id
    order_payer = db.execute(text("""
        SELECT pp.id, pp.type, pp.display_name, pp.legal_name, pp.edrpou,
               pp.iban, pp.email_for_docs, pp.phone_for_docs,
               pp.signatory_name, pp.signatory_basis, pp.tax_mode
        FROM orders o
        JOIN payer_profiles pp ON pp.id = o.payer_profile_id
        WHERE o.order_id = :order_id AND pp.is_active = TRUE
    """), {"order_id": order_id}).fetchone()
    
    if order_payer:
        return {
            "id": order_payer[0], "type": order_payer[1],
            "display_name": order_payer[2], "legal_name": order_payer[3],
            "edrpou": order_payer[4], "iban": order_payer[5],
            "email_for_docs": order_payer[6], "phone_for_docs": order_payer[7],
            "signatory_name": order_payer[8], "signatory_basis": order_payer[9],
            "tax_mode": order_payer[10]
        }
    
    # Try via client_user_id on order
    client_payer = db.execute(text("""
        SELECT pp.id, pp.type, pp.display_name, pp.legal_name, pp.edrpou,
               pp.iban, pp.email_for_docs, pp.phone_for_docs,
               pp.signatory_name, pp.signatory_basis, pp.tax_mode
        FROM orders o
        JOIN client_payer_links cpl ON cpl.client_user_id = o.client_user_id AND cpl.is_default = TRUE
        JOIN payer_profiles pp ON pp.id = cpl.payer_profile_id
        WHERE o.order_id = :order_id AND pp.is_active = TRUE
    """), {"order_id": order_id}).fetchone()
    
    if client_payer:
        return {
            "id": client_payer[0], "type": client_payer[1],
            "display_name": client_payer[2], "legal_name": client_payer[3],
            "edrpou": client_payer[4], "iban": client_payer[5],
            "email_for_docs": client_payer[6], "phone_for_docs": client_payer[7],
            "signatory_name": client_payer[8], "signatory_basis": client_payer[9],
            "tax_mode": client_payer[10]
        }
    
    # Fallback: match by customer_name -> client_users.full_name
    name_payer = db.execute(text("""
        SELECT pp.id, pp.type, pp.display_name, pp.legal_name, pp.edrpou,
               pp.iban, pp.email_for_docs, pp.phone_for_docs,
               pp.signatory_name, pp.signatory_basis, pp.tax_mode
        FROM orders o
        JOIN client_users cu ON cu.full_name COLLATE utf8mb4_unicode_ci = o.customer_name COLLATE utf8mb4_unicode_ci
        JOIN client_payer_links cpl ON cpl.client_user_id = cu.id AND cpl.is_default = TRUE
        JOIN payer_profiles pp ON pp.id = cpl.payer_profile_id
        WHERE o.order_id = :order_id AND pp.is_active = TRUE
        LIMIT 1
    """), {"order_id": order_id}).fetchone()
    
    if name_payer:
        return {
            "id": name_payer[0], "type": name_payer[1],
            "display_name": name_payer[2], "legal_name": name_payer[3],
            "edrpou": name_payer[4], "iban": name_payer[5],
            "email_for_docs": name_payer[6], "phone_for_docs": name_payer[7],
            "signatory_name": name_payer[8], "signatory_basis": name_payer[9],
            "tax_mode": name_payer[10]
        }
    
    return None


def _format_date_ua_long_nominative(date_val) -> str:
    """Format date to 'DD місяця YYYY р.' for documents"""
    if not date_val:
        return "__ ________ 202_ р."
    if isinstance(date_val, str):
        try:
            date_val = datetime.fromisoformat(date_val.replace('Z', '+00:00'))
        except:
            return date_val
    months = ['січня', 'лютого', 'березня', 'квітня', 'травня', 'червня',
              'липня', 'серпня', 'вересня', 'жовтня', 'листопада', 'грудня']
    return f"{date_val.day:02d} {months[date_val.month - 1]} {date_val.year} р."


@router.get("/invoice-payment/{order_id}/preview", response_class=HTMLResponse)
async def preview_invoice_payment(
    order_id: int,
    executor_type: str = Query("fop", description="fop or tov"),
    payer_id: Optional[int] = Query(None, description="Override payer profile ID"),
    db: Session = Depends(get_rh_db)
):
    """Generate HTML preview of Invoice for Payment (Рахунок на оплату)"""
    
    order, items = _get_order_with_items(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Замовлення не знайдено")
    
    executor = EXECUTORS.get(executor_type, EXECUTORS["fop"])
    
    # Get payer
    if payer_id:
        payer_row = db.execute(text("""
            SELECT id, type, display_name, legal_name, edrpou, iban,
                   email_for_docs, phone_for_docs, signatory_name, signatory_basis, tax_mode
            FROM payer_profiles WHERE id = :id AND is_active = TRUE
        """), {"id": payer_id}).fetchone()
        payer = {
            "id": payer_row[0], "type": payer_row[1], "display_name": payer_row[2],
            "legal_name": payer_row[3], "edrpou": payer_row[4], "iban": payer_row[5],
            "email_for_docs": payer_row[6], "signatory_name": payer_row[8]
        } if payer_row else None
    else:
        payer = _get_order_payer(db, order_id)
    
    if not payer:
        raise HTTPException(status_code=400, detail="Не знайдено платника для замовлення. Додайте платника в картці клієнта.")
    
    # Calculate totals
    total_amount = float(order[11] or 0)
    discount = float(order[23] or 0)
    service_fee = float(order[25] or 0)
    grand_total = total_amount - discount + service_fee
    if grand_total <= 0:
        grand_total = total_amount
    
    # Build items for invoice (simplified: one line "Прокат декору")
    formatted_items = []
    if items:
        formatted_items.append({
            "num": 1,
            "name": "Прокат декору",
            "quantity": 1,
            "unit": "послуга",
            "price": _format_currency(grand_total),
            "amount": _format_currency(grand_total)
        })
    
    # Generate invoice number based on order
    invoice_number = order[0]
    
    template_data = {
        "invoice_number": invoice_number,
        "invoice_date": _format_date_ua_long_nominative(datetime.now()),
        "executor": executor,
        "payer": payer,
        "items": formatted_items,
        "total_fmt": _format_currency(grand_total),
        "total_items_count": len(formatted_items),
        "total_text": _number_to_text_ua(grand_total),
        "generated_at": datetime.now().strftime("%d.%m.%Y %H:%M")
    }
    
    template = jinja_env.get_template("documents/invoice_payment.html")
    _enrich_template_with_agreement(db, order, template_data)
    return HTMLResponse(content=template.render(**template_data), media_type="text/html")


@router.get("/invoice-payment/{order_id}/pdf")
async def download_invoice_payment_pdf(
    order_id: int,
    executor_type: str = Query("fop"),
    payer_id: Optional[int] = Query(None),
    db: Session = Depends(get_rh_db)
):
    """Download Invoice for Payment as printable HTML"""
    response = await preview_invoice_payment(order_id, executor_type, payer_id, db)
    html_content = response.body.decode()
    print_script = '<script>window.onload = function() { window.print(); }</script>'
    html_content = html_content.replace('</body>', f'{print_script}</body>')
    return HTMLResponse(content=html_content, media_type="text/html")


@router.get("/service-act/{order_id}/preview", response_class=HTMLResponse)
async def preview_service_act(
    order_id: int,
    executor_type: str = Query("fop", description="fop or tov"),
    payer_id: Optional[int] = Query(None),
    act_date: Optional[str] = Query(None, description="Act date in YYYY-MM-DD format"),
    db: Session = Depends(get_rh_db)
):
    """Generate HTML preview of Service Act (Акт надання послуг)"""
    
    order, items = _get_order_with_items(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Замовлення не знайдено")
    
    executor = EXECUTORS.get(executor_type, EXECUTORS["fop"])
    
    # Get payer
    if payer_id:
        payer_row = db.execute(text("""
            SELECT id, type, display_name, legal_name, edrpou, iban,
                   email_for_docs, phone_for_docs, signatory_name, signatory_basis, tax_mode
            FROM payer_profiles WHERE id = :id AND is_active = TRUE
        """), {"id": payer_id}).fetchone()
        payer = {
            "id": payer_row[0], "type": payer_row[1], "display_name": payer_row[2],
            "legal_name": payer_row[3], "edrpou": payer_row[4], "iban": payer_row[5],
            "email_for_docs": payer_row[6], "signatory_name": payer_row[8],
            "signatory_basis": payer_row[9]
        } if payer_row else None
    else:
        payer = _get_order_payer(db, order_id)
    
    if not payer:
        raise HTTPException(status_code=400, detail="Не знайдено платника для замовлення. Додайте платника в картці клієнта.")
    
    # Calculate totals
    total_amount = float(order[11] or 0)
    discount = float(order[23] or 0)
    service_fee = float(order[25] or 0)
    grand_total = total_amount - discount + service_fee
    if grand_total <= 0:
        grand_total = total_amount
    
    # Signatory short names
    executor_short = executor.get("short_name", executor["name"])
    payer_short = payer.get("display_name", "")
    # Build short name from display_name: "ФОП Мельник Олександр Анатолійович" -> "Мельник О.А."
    parts = payer_short.replace("ФОП ", "").replace("ТОВ ", "").split()
    if len(parts) >= 3:
        payer_initials = f"{parts[0]} {parts[1][0]}.{parts[2][0]}."
    elif len(parts) >= 2:
        payer_initials = f"{parts[0]} {parts[1][0]}."
    else:
        payer_initials = payer_short
    
    # Determine act date: rental start date (видача)
    if act_date:
        try:
            parsed_date = datetime.fromisoformat(act_date)
        except:
            parsed_date = datetime.now()
    else:
        parsed_date = order[6] or order[7] or datetime.now()  # rental_start_date or rental_end_date or now
    
    formatted_items = []
    if items:
        formatted_items.append({
            "num": 1,
            "name": "Прокат декору",
            "quantity": 1,
            "unit": "шт",
            "price": _format_currency(grand_total),
            "amount": _format_currency(grand_total)
        })
    
    act_number = order[0]
    
    template_data = {
        "act_number": act_number,
        "act_date": _format_date_ua_long_nominative(parsed_date),
        "act_date_short": _format_date_ua(parsed_date),
        "executor": executor,
        "payer": payer,
        "payer_initials": payer_initials,
        "items": formatted_items,
        "total_fmt": _format_currency(grand_total),
        "total_text": _number_to_text_ua(grand_total),
        "contract_name": "Основний",
        "generated_at": datetime.now().strftime("%d.%m.%Y %H:%M")
    }
    
    template = jinja_env.get_template("documents/service_act.html")
    _enrich_template_with_agreement(db, None, template_data, order_id=order_id)
    return HTMLResponse(content=template.render(**template_data), media_type="text/html")


@router.get("/service-act/{order_id}/pdf")
async def download_service_act_pdf(
    order_id: int,
    executor_type: str = Query("fop"),
    payer_id: Optional[int] = Query(None),
    act_date: Optional[str] = Query(None),
    db: Session = Depends(get_rh_db)
):
    """Download Service Act as printable HTML"""
    response = await preview_service_act(order_id, executor_type, payer_id, act_date, db)
    html_content = response.body.decode()
    print_script = '<script>window.onload = function() { window.print(); }</script>'
    html_content = html_content.replace('</body>', f'{print_script}</body>')
    return HTMLResponse(content=html_content, media_type="text/html")



# ============================================================
# SETTLEMENT ACT (Акт взаєморозрахунків)
# ============================================================

@router.get("/settlement-act/{order_id}/preview", response_class=HTMLResponse)
async def preview_settlement_act(
    order_id: int,
    final_amount: Optional[float] = Query(None, description="Manager override: final amount (positive = client pays, negative = refund to client)"),
    manager_note: Optional[str] = Query(None, description="Manager note for override"),
    db: Session = Depends(get_rh_db)
):
    """
    Generate Settlement Act (Акт взаєморозрахунків) for an order.
    Consolidates all financial data: rent, payments, deposit, damages, late fees.
    Manager can override final settlement amount via final_amount parameter.
    """
    # === 1. ORDER INFO ===
    order_row = db.execute(text("""
        SELECT o.order_id, o.order_number, o.customer_name, o.customer_phone,
               o.customer_email, o.status, o.total_price, o.deposit_amount,
               o.rental_start_date, o.rental_end_date,
               COALESCE(o.discount_amount, 0) as discount_amount,
               COALESCE(o.discount_percent, 0) as discount_percent
        FROM orders o WHERE o.order_id = :order_id
    """), {"order_id": order_id}).fetchone()

    if not order_row:
        raise HTTPException(status_code=404, detail="Замовлення не знайдено")

    status_labels = {
        "pending": "Очікує", "confirmed": "Підтверджено", "processing": "Комплектація",
        "ready_for_issue": "Готове", "issued": "Видано", "on_rent": "В оренді",
        "returning": "Повернення", "returned": "Повернено", "completed": "Завершено",
        "cancelled": "Скасовано", "partial_return": "Часткове повернення"
    }

    # === 2. PAYMENTS ===
    payments_rows = db.execute(text("""
        SELECT id, payment_type, method, amount, currency,
               payer_name, occurred_at, note, status, description
        FROM fin_payments
        WHERE order_id = :order_id
        ORDER BY occurred_at ASC
    """), {"order_id": order_id}).fetchall()

    rent_paid = 0
    damage_paid = 0
    late_paid = 0
    payments_detail = []
    type_labels = {"rent": "Оренда", "additional": "Донарахування", "damage": "Пошкодження",
                   "deposit": "Застава", "late": "Прострочення", "advance": "Передплата",
                   "refund": "Повернення", "loss": "Втрата"}
    method_labels = {"cash": "Готівка", "card": "Картка", "bank": "Безготівка",
                     "iban": "IBAN", "online": "Онлайн", "p2p": "P2P"}

    for p in payments_rows:
        amt = float(p[3] or 0)
        ptype = p[1]
        status = p[8]
        if status in ('completed', 'confirmed'):
            if ptype in ('rent', 'additional'):
                rent_paid += amt
            elif ptype == 'damage':
                damage_paid += amt
            elif ptype == 'late':
                late_paid += amt

            # Тільки реальні оплати (confirmed/completed) в деталях
            payments_detail.append({
                "date": _format_date_ua(p[6]),
                "type_label": type_labels.get(ptype, ptype),
                "method_label": method_labels.get(p[2], p[2] or "—"),
                "amount": _format_currency(amt),
                "note": p[9] or p[7] or ""
            })

    total_paid = rent_paid + damage_paid + late_paid

    # === 3. DEPOSIT ===
    deposit_row = db.execute(text("""
        SELECT id, held_amount, used_amount, refunded_amount, status,
               actual_amount, currency, exchange_rate
        FROM fin_deposit_holds
        WHERE order_id = :order_id LIMIT 1
    """), {"order_id": order_id}).fetchone()

    dep_held_uah = 0
    dep_actual = 0
    dep_currency = "UAH"
    dep_used = 0
    dep_refunded = 0
    dep_available = 0

    if deposit_row:
        dep_held_uah = float(deposit_row[1] or 0)
        dep_actual = float(deposit_row[5]) if deposit_row[5] else dep_held_uah
        dep_currency = deposit_row[6] or "UAH"
        dep_used = float(deposit_row[2] or 0)
        dep_refunded = float(deposit_row[3] or 0)
        dep_available = dep_held_uah - dep_used - dep_refunded

    currency_symbol = {"UAH": "грн", "USD": "$", "EUR": "€"}.get(dep_currency, dep_currency)

    # Deposit refund events (для деталізації в акті)
    deposit_refund_events = []
    if deposit_row:
        dep_events = db.execute(text("""
            SELECT event_type, amount, occurred_at, note
            FROM fin_deposit_events WHERE deposit_id = :dep_id AND event_type = 'refunded'
            ORDER BY occurred_at
        """), {"dep_id": deposit_row[0]}).fetchall()
        deposit_refund_events = [
            {"amount": _format_currency(float(e[1] or 0)),
             "date": _format_date_ua(e[2]),
             "note": e[3] or "Повернення застави"}
            for e in dep_events
        ]

    # === 4. DAMAGE ===
    damage_total_val = db.execute(text("""
        SELECT COALESCE(SUM(fee), 0) FROM product_damage_history WHERE order_id = :order_id
    """), {"order_id": order_id}).scalar() or 0

    damage_items_rows = db.execute(text("""
        SELECT pdh.id, p.sku, COALESCE(p.name, 'Ручне нарахування'), pdh.damage_type, pdh.fee, pdh.note
        FROM product_damage_history pdh
        LEFT JOIN products p ON p.product_id = pdh.product_id
        WHERE pdh.order_id = :order_id
        ORDER BY pdh.created_at
    """), {"order_id": order_id}).fetchall()

    damage_items = [{
        "sku": r[1] or "—", "name": r[2] or r[3] or "—",
        "fee": _format_currency(float(r[4] or 0)), "note": r[5] or ""
    } for r in damage_items_rows]

    # === 5. LATE FEES (from fin_payments - тільки нарахування менеджера, status='pending') ===
    late_total_row = db.execute(text("""
        SELECT COALESCE(SUM(amount), 0) FROM fin_payments
        WHERE order_id = :order_id AND payment_type = 'late' AND status = 'pending'
    """), {"order_id": order_id}).fetchone()
    late_final = float(late_total_row[0]) if late_total_row else 0

    # === 5b. DAMAGE (from product_damage_history - manager-decided amounts) ===
    # Use damage_total_val already computed above
    damage_final = float(damage_total_val)

    # === 6. ADDITIONAL SERVICES ===
    additional_services = db.execute(text("""
        SELECT name, amount FROM order_additional_services
        WHERE order_id = :order_id ORDER BY id
    """), {"order_id": order_id}).fetchall()
    additional_services_list = [
        {"name": r[0], "amount": _format_currency(float(r[1] or 0))}
        for r in additional_services
    ]
    additional_total = sum(float(r[1] or 0) for r in additional_services)

    # === 7. CALCULATE TOTALS ===
    total_price_stored = float(order_row[6] or 0)
    discount = float(order_row[10] or 0)
    discount_percent = float(order_row[11] or 0)
    
    # Визначаємо чи total_price ДО чи ПІСЛЯ знижки
    has_discount_payment = any(p[1] == 'discount' for p in payments_rows)
    
    if has_discount_payment and discount > 0:
        # total_price = ціна ДО знижки
        rent_total = total_price_stored
        rent_after_discount = total_price_stored - discount
    else:
        # total_price = ціна ПІСЛЯ знижки (або без знижки)
        rent_total = total_price_stored + discount
        rent_after_discount = total_price_stored

    grand_total_charges = rent_after_discount + additional_total + damage_final + late_final

    # Calculated balance: positive = client owes, negative = refund to client
    # Balance = total charges - all cash payments - net deposit coverage
    # Net deposit coverage = what's already used for charges + what's still available
    # (NOT the full held amount, because part was already refunded to client)
    deposit_net_for_charges = dep_used + max(0, dep_available)
    calculated_balance = grand_total_charges - total_paid - deposit_net_for_charges

    # Manager override
    is_manager_override = final_amount is not None
    final_balance = final_amount if is_manager_override else calculated_balance

    # === 8. BUILD TEMPLATE CONTEXT ===
    template_data = {
        "company": get_company_config(db),
        "order": {
            "order_number": order_row[1],
            "customer_name": order_row[2] or "—",
            "customer_phone": order_row[3] or "—",
            "customer_email": order_row[4] or "",
            "rental_start": _format_date_ua(order_row[8]),
            "rental_end": _format_date_ua(order_row[9]),
            "status_label": status_labels.get(order_row[5], order_row[5] or "—"),
        },
        "charges": {
            "rent_total": _format_currency(rent_total),
            "discount": _format_currency(discount),
            "discount_raw": discount,
            "discount_percent": f"{discount_percent:.0f}" if discount_percent else None,
            "additional_services": additional_services_list,
            "damage_total": _format_currency(damage_final),
            "damage_total_raw": damage_final,
            "late_total": _format_currency(late_final),
            "late_total_raw": late_final,
            "grand_total": _format_currency(grand_total_charges),
        },
        "damage_items": damage_items,
        "payments_summary": {
            "rent_paid": _format_currency(rent_paid),
            "rent_paid_raw": rent_paid,
            "damage_paid": _format_currency(damage_paid),
            "damage_paid_raw": damage_paid,
            "late_paid": _format_currency(late_paid),
            "late_paid_raw": late_paid,
            "total_paid": _format_currency(total_paid),
        },
        "payments_detail": payments_detail,
        "deposit": {
            "display_held": f"{_format_currency(dep_actual)} {currency_symbol}" if dep_currency != "UAH" else f"{_format_currency(dep_held_uah)} грн",
            "held_uah": _format_currency(dep_held_uah),
            "used": dep_used,
            "used_display": _format_currency(dep_used),
            "refunded": dep_refunded,
            "refunded_display": _format_currency(dep_refunded),
            "available": dep_available,
            "available_display": f"{_format_currency(dep_available)} грн",
            "net_for_charges": _format_currency(deposit_net_for_charges),
            "refund_events": deposit_refund_events,
        },
        "settlement": {
            "calculated_balance": calculated_balance,
            "final_balance": final_balance,
            "final_balance_display": _format_currency(abs(final_balance)),
            "refund_display": _format_currency(abs(final_balance)),
            "is_manager_override": is_manager_override,
            "manager_note": manager_note or "",
        },
        "generated_at": datetime.now().strftime("%d.%m.%Y %H:%M"),
    }

    template = jinja_env.get_template("documents/settlement_act.html")
    _enrich_template_with_agreement(db, None, template_data, order_id=order_id, customer_name=order_row[2])
    return HTMLResponse(content=template.render(**template_data), media_type="text/html")


@router.get("/settlement-act/{order_id}/pdf")
async def download_settlement_act_pdf(
    order_id: int,
    final_amount: Optional[float] = Query(None),
    manager_note: Optional[str] = Query(None),
    db: Session = Depends(get_rh_db)
):
    """Download Settlement Act as printable HTML (with auto-print)"""
    response = await preview_settlement_act(order_id, final_amount, manager_note, db)
    html_content = response.body.decode()
    print_script = '<script>window.onload = function() { window.print(); }</script>'
    html_content = html_content.replace('</body>', f'{print_script}</body>')
    return HTMLResponse(content=html_content, media_type="text/html")
