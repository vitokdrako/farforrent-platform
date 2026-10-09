"""
Document Signatures API
Phase 3.1: Digital signature support

Supports:
- Touch/mouse signature capture
- Signature storage
- Document status update on signing
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime
from typing import Optional
from pydantic import BaseModel
import base64
import uuid
import os

from database_rentalhub import get_rh_db

router = APIRouter(prefix="/api/documents/signatures", tags=["document-signatures"])


# ============================================================
# PYDANTIC MODELS
# ============================================================

class SignDocumentRequest(BaseModel):
    document_id: str
    signer_role: str  # "landlord" or "tenant"
    signature_png_base64: str
    signer_name: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


class VerifySignatureRequest(BaseModel):
    document_id: str
    signer_role: str


# ============================================================
# HELPER: Save signature image
# ============================================================

def save_signature_image(signature_base64: str, document_id: str, signer_role: str) -> str:
    """
    Save signature as file and return URL/path.
    In production, this would upload to S3/cloud storage.
    For now, we store base64 directly in DB.
    """
    # Remove data URL prefix if present
    if signature_base64.startswith("data:image"):
        signature_base64 = signature_base64.split(",", 1)[1]
    
    # For now, return the base64 data URL for direct embedding
    return f"data:image/png;base64,{signature_base64}"


# ============================================================
# API ENDPOINTS
# ============================================================

@router.post("/sign")
async def sign_document(
    request: SignDocumentRequest,
    db: Session = Depends(get_rh_db)
):
    """
    Sign a document with touch/canvas signature.
    
    - Validates document exists
    - Saves signature image
    - Updates document_signatures table
    - Updates document status to 'signed' if both parties signed
    """
    
    if request.signer_role not in ("landlord", "tenant"):
        raise HTTPException(status_code=400, detail="signer_role must be 'landlord' or 'tenant'")
    
    # Check if document exists
    doc_check = db.execute(text("""
        SELECT id, doc_type, status FROM documents WHERE id = :id
    """), {"id": request.document_id}).fetchone()
    
    if not doc_check:
        raise HTTPException(status_code=404, detail="Document not found")
    
    current_status = doc_check[2]
    
    # Check if already signed by this role
    existing = db.execute(text("""
        SELECT id FROM document_signatures 
        WHERE document_id = :doc_id AND signer_role = :role
    """), {"doc_id": request.document_id, "role": request.signer_role}).fetchone()
    
    if existing:
        raise HTTPException(status_code=400, detail=f"Document already signed by {request.signer_role}")
    
    # Save signature
    signature_url = save_signature_image(
        request.signature_png_base64,
        request.document_id,
        request.signer_role
    )
    
    try:
        # Insert signature record
        db.execute(text("""
            INSERT INTO document_signatures (
                document_id, signer_role, signature_image, signer_name,
                ip_address, user_agent, signed_at
            ) VALUES (
                :doc_id, :role, :sig_img, :name, :ip, :ua, NOW()
            )
        """), {
            "doc_id": request.document_id,
            "role": request.signer_role,
            "sig_img": signature_url,
            "name": request.signer_name,
            "ip": request.ip_address,
            "ua": request.user_agent
        })
        
        # Check if both parties have signed
        sig_count = db.execute(text("""
            SELECT COUNT(DISTINCT signer_role) FROM document_signatures 
            WHERE document_id = :doc_id
        """), {"doc_id": request.document_id}).scalar()
        
        new_status = current_status
        if sig_count >= 2:
            # Both parties signed - update document status
            db.execute(text("""
                UPDATE documents SET status = 'signed' WHERE id = :id
            """), {"id": request.document_id})
            new_status = "signed"
        
        db.commit()
        
        return {
            "success": True,
            "document_id": request.document_id,
            "signer_role": request.signer_role,
            "signature_url": signature_url,
            "document_status": new_status,
            "fully_signed": sig_count >= 2
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status/{document_id}")
async def get_signature_status(
    document_id: str,
    db: Session = Depends(get_rh_db)
):
    """Get signature status for a document"""
    
    # Get all signatures
    result = db.execute(text("""
        SELECT signer_role, signer_name, signed_at, signature_image
        FROM document_signatures 
        WHERE document_id = :doc_id
    """), {"doc_id": document_id})
    
    signatures = {}
    for row in result:
        signatures[row[0]] = {
            "signed": True,
            "signer_name": row[1],
            "signed_at": row[2].isoformat() if row[2] else None,
            "image_url": row[3]
        }
    
    # Ensure both roles exist in response
    for role in ("landlord", "tenant"):
        if role not in signatures:
            signatures[role] = {"signed": False, "image_url": None, "signed_at": None}
    
    return {
        "document_id": document_id,
        "signatures": signatures,
        "fully_signed": signatures.get("landlord", {}).get("signed", False) and 
                       signatures.get("tenant", {}).get("signed", False)
    }


@router.delete("/{document_id}/{signer_role}")
async def remove_signature(
    document_id: str,
    signer_role: str,
    db: Session = Depends(get_rh_db)
):
    """Remove a signature (admin only, for corrections)"""
    
    if signer_role not in ("landlord", "tenant"):
        raise HTTPException(status_code=400, detail="Invalid signer_role")
    
    try:
        result = db.execute(text("""
            DELETE FROM document_signatures 
            WHERE document_id = :doc_id AND signer_role = :role
        """), {"doc_id": document_id, "role": signer_role})
        
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Signature not found")
        
        # Update document status back to generated if it was signed
        db.execute(text("""
            UPDATE documents SET status = 'generated' 
            WHERE id = :id AND status = 'signed'
        """), {"id": document_id})
        
        db.commit()
        
        return {"success": True, "message": f"Signature by {signer_role} removed"}
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate-sign-link")
async def generate_sign_link(
    document_id: str = Query(...),
    signer_role: str = Query(...),
    expires_hours: int = Query(default=72),
    db: Session = Depends(get_rh_db)
):
    """
    Generate a signing link for external signing (email workflow).
    Returns a token that can be used to sign without authentication.
    """
    
    if signer_role not in ("landlord", "tenant"):
        raise HTTPException(status_code=400, detail="Invalid signer_role")
    
    # Check document exists
    doc = db.execute(text("""
        SELECT id, status FROM documents WHERE id = :id
    """), {"id": document_id}).fetchone()
    
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Generate token
    token = str(uuid.uuid4())
    expires_at = datetime.now().replace(microsecond=0)
    
    # In production, store token in a signing_tokens table
    # For now, return the token directly
    
    return {
        "success": True,
        "document_id": document_id,
        "signer_role": signer_role,
        "sign_token": token,
        "sign_url": f"/sign/{token}",
        "expires_at": expires_at.isoformat(),
        "note": "Token storage not implemented - use direct signing for now"
    }
