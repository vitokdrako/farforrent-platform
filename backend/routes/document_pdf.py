"""
PDF Generation API
Phase 3.2: HTML to PDF with WeasyPrint

Supports:
- HTML rendering to PDF
- Watermarks (ЧЕРНЕТКА / ПІДПИСАНО)
- File storage
- Download URL generation
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel
import os
import uuid

from database_rentalhub import get_rh_db
from routes.document_render import (
    build_document_context, 
    jinja_env, 
    DOCUMENT_TEMPLATES,
    get_watermark_text
)

router = APIRouter(prefix="/api/documents", tags=["document-pdf"])

# ============================================================
# CONFIGURATION
# ============================================================

# Directory for storing generated PDFs
PDF_STORAGE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads", "documents")
os.makedirs(PDF_STORAGE_DIR, exist_ok=True)

# Try to import WeasyPrint (may fail on some systems due to missing system libs)
WEASYPRINT_AVAILABLE = False
HTML = None
CSS = None
try:
    from weasyprint import HTML, CSS
    WEASYPRINT_AVAILABLE = True
except (ImportError, OSError) as e:
    print(f"WARNING: WeasyPrint not available ({e}). PDF generation will return HTML fallback.")


# ============================================================
# PYDANTIC MODELS
# ============================================================

class GeneratePdfRequest(BaseModel):
    doc_type: str
    order_id: Optional[int] = None
    payer_profile_id: Optional[int] = None
    agreement_id: Optional[int] = None
    annex_id: Optional[int] = None
    manual_fields: Optional[Dict[str, Any]] = None
    status: str = "draft"  # draft, signed


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def generate_pdf_filename(doc_type: str, doc_number: str) -> str:
    """Generate unique filename for PDF"""
    year = datetime.now().strftime("%Y")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_doc_number = doc_number.replace("/", "-").replace(" ", "_")
    return f"{year}/{doc_type}_{safe_doc_number}_{timestamp}.pdf"


def html_to_pdf(html_content: str, output_path: str) -> bool:
    """Convert HTML to PDF using WeasyPrint"""
    if not WEASYPRINT_AVAILABLE:
        # Fallback: save HTML as file
        html_path = output_path.replace(".pdf", ".html")
        os.makedirs(os.path.dirname(html_path), exist_ok=True)
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        return False
    
    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Render PDF
        html_doc = HTML(string=html_content)
        html_doc.write_pdf(output_path)
        
        return True
    except Exception as e:
        print(f"PDF generation error: {e}")
        return False


# ============================================================
# API ENDPOINTS
# ============================================================

@router.post("/generate-pdf")
async def generate_pdf(
    request: GeneratePdfRequest,
    db: Session = Depends(get_rh_db)
):
    """
    Generate PDF document from template.
    
    1. Builds context from database
    2. Renders HTML template
    3. Converts to PDF (if WeasyPrint available)
    4. Stores file and returns URL
    """
    
    if request.doc_type not in DOCUMENT_TEMPLATES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown document type: {request.doc_type}"
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
        status=request.status
    )
    
    # Render HTML
    template_name = DOCUMENT_TEMPLATES[request.doc_type]
    try:
        template = jinja_env.get_template(template_name)
        html_content = template.render(**context)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Template error: {str(e)}")
    
    # Generate filename and path
    doc_number = context["meta"].get("doc_number", str(uuid.uuid4())[:8])
    filename = generate_pdf_filename(request.doc_type, doc_number)
    output_path = os.path.join(PDF_STORAGE_DIR, filename)
    
    # Convert to PDF
    pdf_success = html_to_pdf(html_content, output_path)
    
    # Build response
    if pdf_success:
        # Return PDF URL
        pdf_url = f"/api/documents/download/{filename}"
        return {
            "success": True,
            "doc_type": request.doc_type,
            "doc_number": doc_number,
            "pdf_url": pdf_url,
            "file_path": output_path,
            "format": "pdf"
        }
    else:
        # Return HTML fallback info
        html_path = output_path.replace(".pdf", ".html")
        return {
            "success": True,
            "doc_type": request.doc_type,
            "doc_number": doc_number,
            "pdf_url": None,
            "html_url": f"/api/documents/download/{filename.replace('.pdf', '.html')}",
            "file_path": html_path,
            "format": "html",
            "warning": "WeasyPrint not available. Generated HTML instead."
        }


@router.get("/download/{year}/{filename}")
async def download_document(year: str, filename: str):
    """Download generated document (PDF or HTML)"""
    
    file_path = os.path.join(PDF_STORAGE_DIR, year, filename)
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Determine media type
    if filename.endswith(".pdf"):
        media_type = "application/pdf"
    elif filename.endswith(".html"):
        media_type = "text/html"
    else:
        media_type = "application/octet-stream"
    
    return FileResponse(
        path=file_path,
        media_type=media_type,
        filename=filename
    )


@router.get("/status")
async def get_pdf_status():
    """Check PDF generation capabilities"""
    return {
        "weasyprint_available": WEASYPRINT_AVAILABLE,
        "storage_dir": PDF_STORAGE_DIR,
        "storage_exists": os.path.exists(PDF_STORAGE_DIR)
    }


@router.post("/save-to-db")
async def save_document_to_db(
    doc_type: str,
    order_id: Optional[int] = None,
    annex_id: Optional[int] = None,
    agreement_id: Optional[int] = None,
    file_path: Optional[str] = None,
    snapshot_json: Optional[Dict[str, Any]] = None,
    db: Session = Depends(get_rh_db)
):
    """
    Save generated document record to documents table.
    Creates immutable record with snapshot.
    """
    
    doc_id = str(uuid.uuid4())
    
    try:
        db.execute(text("""
            INSERT INTO documents (
                id, doc_type, order_id, annex_id, master_agreement_id,
                file_path, snapshot_json, status, is_legal, category, created_at
            ) VALUES (
                :id, :doc_type, :order_id, :annex_id, :agreement_id,
                :file_path, :snapshot_json, 'generated', :is_legal, :category, NOW()
            )
        """), {
            "id": doc_id,
            "doc_type": doc_type,
            "order_id": order_id,
            "annex_id": annex_id,
            "agreement_id": agreement_id,
            "file_path": file_path,
            "snapshot_json": str(snapshot_json) if snapshot_json else None,
            "is_legal": doc_type not in ("quote",),
            "category": {
                "master_agreement": "contract",
                "annex_to_contract": "annex",
                "issue_act": "act",
                "return_act": "act",
                "defect_act": "act",
                "quote": "quote"
            }.get(doc_type, "other")
        })
        
        db.commit()
        
        # Push-сповіщення клієнту про новий документ (best-effort).
        try:
            if order_id:
                from services.push_notifications import notify_document_ready
                notify_document_ready(db, int(order_id), doc_type, None)
        except Exception as _e:
            import logging
            logging.getLogger("document_pdf").warning(f"push notify failed: {_e}")
        
        return {
            "success": True,
            "document_id": doc_id
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
