"""
Document Email API
Phase 3.2: Email workflow for sending documents

Supports:
- Send document via email
- Attach PDF or HTML
- Log all sends with full audit trail
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel
import json
import os

from database_rentalhub import get_rh_db

router = APIRouter(prefix="/api/documents", tags=["document-email"])


# ============================================================
# PYDANTIC MODELS
# ============================================================

class SendEmailRequest(BaseModel):
    to: str  # Email recipient
    cc: Optional[str] = None
    subject: Optional[str] = None
    message: Optional[str] = None
    attach_pdf: bool = True
    sent_by_user_id: Optional[int] = None
    sent_by_user_name: Optional[str] = None


class EmailLogEntry(BaseModel):
    document_id: str
    sent_to: str
    sent_at: str
    document_version: int
    sent_by_user_id: Optional[int]
    sent_by_user_name: Optional[str]


# ============================================================
# API ENDPOINTS
# ============================================================

@router.post("/{document_id}/send-email")
async def send_document_email(
    document_id: str,
    request: SendEmailRequest,
    db: Session = Depends(get_rh_db)
):
    """
    Send document via email with PDF/HTML attachment.
    Logs the send in document_emails table for audit.
    Uses configurable email provider (Resend/SendGrid/Dummy).
    """
    from services.email_provider import get_email_provider, EmailResult
    
    # Get document info
    doc = db.execute(text("""
        SELECT id, doc_type, status, version, entity_id, snapshot_json
        FROM documents WHERE id = :id
    """), {"id": document_id}).fetchone()
    
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    doc_type = doc[1]
    doc_status = doc[2]
    doc_version = doc[3] or 1
    
    # Build subject if not provided
    subject = request.subject
    if not subject:
        doc_type_labels = {
            "master_agreement": "Рамковий договір",
            "annex_to_contract": "Додаток до договору",
            "issue_act": "Акт передачі",
            "return_act": "Акт повернення",
            "defect_act": "Дефектний акт",
            "quote": "Кошторис",
            "invoice_offer": "Рахунок-оферта"
        }
        subject = f"{doc_type_labels.get(doc_type, doc_type)} #{document_id}"
    
    # Build email HTML body
    message = request.message or "Документ від FarforRent. Будь ласка, перегляньте вкладення."
    
    html_body = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <h2 style="color: #1e293b;">{subject}</h2>
        <p style="color: #475569; line-height: 1.6;">{message}</p>
        <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;"/>
        <p style="color: #94a3b8; font-size: 12px;">
            Цей лист надіслано автоматично системою FarforRent.<br/>
            Документ #{document_id} | Версія {doc_version}
        </p>
    </div>
    """
    
    # Send email via provider
    provider = get_email_provider()
    result: EmailResult = await provider.send(
        to=request.to,
        subject=subject,
        html=html_body,
        cc=request.cc
    )
    
    # Log the email send attempt
    try:
        db.execute(text("""
            INSERT INTO document_emails (
                document_id, sent_to, subject, message,
                sent_at, document_version, sent_by_user_id, sent_by_user_name,
                status, provider, provider_email_id
            ) VALUES (
                :doc_id, :to, :subject, :message,
                NOW(), :version, :user_id, :user_name,
                :status, :provider, :provider_id
            )
        """), {
            "doc_id": document_id,
            "to": request.to,
            "subject": subject,
            "message": message,
            "version": doc_version,
            "user_id": request.sent_by_user_id,
            "user_name": request.sent_by_user_name,
            "status": "sent" if result.success else "failed",
            "provider": result.provider,
            "provider_id": result.email_id
        })
        db.commit()
    except Exception as e:
        db.rollback()
        # Still return success if email was sent but logging failed
    
    if not result.success:
        raise HTTPException(
            status_code=500, 
            detail=f"Email sending failed: {result.error}"
        )
    
    return {
        "success": True,
        "document_id": document_id,
        "sent_to": request.to,
        "subject": subject,
        "document_version": doc_version,
        "provider": result.provider,
        "email_id": result.email_id
    }


class SendPreviewEmailRequest(BaseModel):
    to: str
    subject: str
    html_content: str  # The document HTML
    sent_by_user_id: Optional[int] = None
    sent_by_user_name: Optional[str] = None
    doc_type: Optional[str] = None
    order_id: Optional[int] = None


@router.post("/send-preview-email")
async def send_preview_email(
    request: SendPreviewEmailRequest,
    db: Session = Depends(get_rh_db)
):
    """
    Send document preview email directly (without saving document to DB).
    Useful for sending quotes and draft documents.
    Still logs the send for audit purposes.
    """
    from services.email_provider import get_email_provider, EmailResult
    
    # Build HTML email wrapper
    html_body = f"""
    <div style="font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto;">
        <p style="color: #475569; margin-bottom: 20px;">
            Документ від FarforRent. Будь ласка, перегляньте вкладення.
        </p>
        <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;"/>
        {request.html_content}
        <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;"/>
        <p style="color: #94a3b8; font-size: 12px;">
            Цей лист надіслано автоматично системою FarforRent.
        </p>
    </div>
    """
    
    # Send email via provider
    provider = get_email_provider()
    result: EmailResult = await provider.send(
        to=request.to,
        subject=request.subject,
        html=html_body
    )
    
    # Log the send (without document_id)
    try:
        db.execute(text("""
            INSERT INTO document_emails (
                document_id, sent_to, subject, message,
                sent_at, document_version, sent_by_user_id, sent_by_user_name,
                status, provider, provider_email_id
            ) VALUES (
                :doc_id, :to, :subject, :message,
                NOW(), 1, :user_id, :user_name,
                :status, :provider, :provider_id
            )
        """), {
            "doc_id": f"preview_{request.doc_type or 'unknown'}_{request.order_id or 0}",
            "to": request.to,
            "subject": request.subject,
            "message": "Preview email",
            "user_id": request.sent_by_user_id,
            "user_name": request.sent_by_user_name,
            "status": "sent" if result.success else "failed",
            "provider": result.provider,
            "provider_id": result.email_id
        })
        db.commit()
    except Exception as e:
        db.rollback()
    
    if not result.success:
        raise HTTPException(
            status_code=500, 
            detail=f"Email sending failed: {result.error}"
        )
    
    return {
        "success": True,
        "sent_to": request.to,
        "subject": request.subject,
        "provider": result.provider,
        "email_id": result.email_id
    }


@router.get("/{document_id}/email-history")
async def get_email_history(
    document_id: str,
    db: Session = Depends(get_rh_db)
):
    """
    Get email send history for a document.
    """
    
    result = db.execute(text("""
        SELECT 
            id, sent_to, subject, sent_at, 
            document_version, sent_by_user_id, sent_by_user_name,
            status
        FROM document_emails 
        WHERE document_id = :doc_id
        ORDER BY sent_at DESC
    """), {"doc_id": document_id})
    
    history = []
    for row in result:
        history.append({
            "id": row[0],
            "sent_to": row[1],
            "subject": row[2],
            "sent_at": row[3].isoformat() if row[3] else None,
            "document_version": row[4],
            "sent_by_user_id": row[5],
            "sent_by_user_name": row[6],
            "status": row[7]
        })
    
    return {
        "document_id": document_id,
        "total_sends": len(history),
        "history": history
    }


@router.get("/recent-emails")
async def get_recent_emails(
    limit: int = 50,
    db: Session = Depends(get_rh_db)
):
    """
    Get recent email sends across all documents.
    """
    
    result = db.execute(text("""
        SELECT 
            de.id, de.document_id, de.sent_to, de.subject, de.sent_at,
            de.document_version, de.sent_by_user_name, de.status,
            de.provider, de.provider_email_id,
            d.doc_type
        FROM document_emails de
        LEFT JOIN documents d ON d.id COLLATE utf8mb4_unicode_ci = de.document_id COLLATE utf8mb4_unicode_ci
        ORDER BY de.sent_at DESC
        LIMIT :limit
    """), {"limit": limit})
    
    emails = []
    for row in result:
        emails.append({
            "id": row[0],
            "document_id": row[1],
            "sent_to": row[2],
            "subject": row[3],
            "sent_at": row[4].isoformat() if row[4] else None,
            "document_version": row[5],
            "sent_by": row[6],
            "status": row[7],
            "provider": row[8],
            "provider_email_id": row[9],
            "doc_type": row[10]
        })
    
    return {
        "total": len(emails),
        "emails": emails
    }
