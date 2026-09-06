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

from database_rentalhub import get_rh_db
from services.company_config import get_landlord_config, get_company_config

router = APIRouter(prefix="/api/documents/render", tags=["document-rendering"])

# ============================================================
# JINJA2 ENVIRONMENT SETUP
# ============================================================

# ============================================================
# RENDERING LAYER (canonical implementation)
# ============================================================
# Jinja-середовище, шаблони й побудова контексту живуть у
# services/document_context.py, щоб routes/document_pdf.py не імпортував
# їх з цього роута (route -> route). Реекспорт нижче зберігає сумісність
# для будь-яких наявних імпортів `from routes.document_render import ...`.
from services.document_context import (  # noqa: E402
    DOCUMENT_TEMPLATES,
    MONTH_NAMES_UA,
    PAYER_TYPE_LABELS,
    TEMPLATES_DIR,
    build_document_context,
    format_date_ua,
    get_watermark_text,
    jinja_env,
)

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
