"""
Document Manual Fields API
Phase 3.2: Manual fields schema and storage for legal documents

Supports:
- JSON schema per document type
- Manual fields storage in snapshot_json.manual_fields
- Immutability enforcement (signed docs cannot be modified)
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel
import json

from database_rentalhub import get_rh_db

router = APIRouter(prefix="/api/documents", tags=["document-manual-fields"])


# ============================================================
# MANUAL FIELDS SCHEMAS BY DOCUMENT TYPE
# ============================================================

MANUAL_FIELDS_SCHEMAS = {
    "annex_to_contract": {
        "title": "Додаток до договору",
        "description": "Поля для юридичного додатку",
        "fields": [
            {
                "key": "contact_person",
                "label": "Контактна особа",
                "type": "text",
                "required": False,
                "placeholder": "Прізвище Ім'я"
            },
            {
                "key": "contact_channel",
                "label": "Канал зв'язку",
                "type": "select",
                "required": False,
                "options": ["Telegram", "Viber", "WhatsApp", "Email", "Телефон"]
            },
            {
                "key": "contact_value",
                "label": "Контакт (номер/username)",
                "type": "text",
                "required": False,
                "placeholder": "@username або +380..."
            },
            {
                "key": "pickup_time",
                "label": "Час отримання",
                "type": "time",
                "required": True,
                "default": "17:00"
            },
            {
                "key": "return_time",
                "label": "Час повернення",
                "type": "time",
                "required": True,
                "default": "10:00"
            }
        ]
    },
    "return_act": {
        "title": "Акт повернення",
        "description": "Поля для акту приймання товару",
        "fields": [
            {
                "key": "condition_mode",
                "label": "Стан товару при поверненні",
                "type": "radio",
                "required": True,
                "options": [
                    {"value": "excellent", "label": "Відмінний стан"},
                    {"value": "ok", "label": "Справний / без зауважень"},
                    {"value": "damaged", "label": "Є пошкодження (див. дефектний акт)"}
                ],
                "default": "ok"
            },
            {
                "key": "return_notes",
                "label": "Примітки при поверненні",
                "type": "textarea",
                "required": False,
                "placeholder": "Зауваження, коментарі..."
            },
            {
                "key": "defect_act_number",
                "label": "Номер дефектного акту (якщо є)",
                "type": "text",
                "required": False,
                "show_if": {"condition_mode": "damaged"}
            }
        ]
    },
    "defect_act": {
        "title": "Дефектний акт",
        "description": "Поля для акту фіксації пошкоджень",
        "fields": [
            {
                "key": "defect_notes",
                "label": "Загальні примітки щодо пошкоджень",
                "type": "textarea",
                "required": False,
                "placeholder": "Опис обставин, загальний стан..."
            },
            {
                "key": "tenant_refused_to_sign",
                "label": "Орендар відмовився підписувати акт",
                "type": "checkbox",
                "required": False,
                "default": False,
                "description": "Позначте, якщо орендар відмовляється підписувати"
            },
            {
                "key": "refusal_witnesses",
                "label": "Свідки відмови (якщо відмовився)",
                "type": "text",
                "required": False,
                "show_if": {"tenant_refused_to_sign": True},
                "placeholder": "ПІБ свідків"
            }
        ]
    },
    "issue_act": {
        "title": "Акт передачі",
        "description": "Поля для акту видачі товару",
        "fields": [
            {
                "key": "issue_notes",
                "label": "Примітки при видачі",
                "type": "textarea",
                "required": False,
                "placeholder": "Особливості стану, комплектація..."
            },
            {
                "key": "pickup_time",
                "label": "Час видачі",
                "type": "time",
                "required": False,
                "default": "17:00"
            }
        ]
    }
}


# ============================================================
# PYDANTIC MODELS
# ============================================================

class ManualFieldsUpdate(BaseModel):
    manual_fields: Dict[str, Any]


# ============================================================
# API ENDPOINTS
# ============================================================

@router.get("/{document_id}/manual-fields-schema")
async def get_manual_fields_schema(
    document_id: str,
    db: Session = Depends(get_rh_db)
):
    """
    Get JSON schema for manual fields based on document type.
    Returns field definitions for the form builder.
    """
    # Get document type
    doc = db.execute(text("""
        SELECT doc_type, status, snapshot_json FROM documents WHERE id = :id
    """), {"id": document_id}).fetchone()
    
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    doc_type = doc[0]
    status = doc[1]
    current_snapshot = doc[2]
    
    # Get schema for this doc type
    schema = MANUAL_FIELDS_SCHEMAS.get(doc_type)
    
    if not schema:
        return {
            "document_id": document_id,
            "doc_type": doc_type,
            "has_manual_fields": False,
            "schema": None,
            "current_values": {}
        }
    
    # Extract current manual_fields values from snapshot
    current_values = {}
    if current_snapshot:
        try:
            snapshot_data = json.loads(current_snapshot) if isinstance(current_snapshot, str) else current_snapshot
            current_values = snapshot_data.get("manual_fields", {})
        except:
            pass
    
    return {
        "document_id": document_id,
        "doc_type": doc_type,
        "status": status,
        "is_editable": status != "signed",
        "has_manual_fields": True,
        "schema": schema,
        "current_values": current_values
    }


@router.get("/schema/{doc_type}")
async def get_schema_by_type(doc_type: str):
    """
    Get manual fields schema by document type (without document_id).
    Useful for pre-generation forms.
    """
    schema = MANUAL_FIELDS_SCHEMAS.get(doc_type)
    
    if not schema:
        return {
            "doc_type": doc_type,
            "has_manual_fields": False,
            "schema": None
        }
    
    return {
        "doc_type": doc_type,
        "has_manual_fields": True,
        "schema": schema
    }


@router.patch("/{document_id}/manual-fields")
async def update_manual_fields(
    document_id: str,
    request: ManualFieldsUpdate,
    db: Session = Depends(get_rh_db)
):
    """
    Update manual fields in document snapshot.
    Cannot modify signed documents.
    """
    # Get document
    doc = db.execute(text("""
        SELECT id, doc_type, status, snapshot_json FROM documents WHERE id = :id
    """), {"id": document_id}).fetchone()
    
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    doc_type = doc[1]
    status = doc[2]
    current_snapshot = doc[3]
    
    # Check immutability
    if status == "signed":
        raise HTTPException(
            status_code=409, 
            detail="Cannot modify signed document. Document is immutable."
        )
    
    # Validate against schema
    schema = MANUAL_FIELDS_SCHEMAS.get(doc_type)
    if schema:
        for field in schema.get("fields", []):
            if field.get("required") and field["key"] not in request.manual_fields:
                # Check if default exists
                if "default" not in field:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Required field missing: {field['key']}"
                    )
    
    # Update snapshot
    try:
        if current_snapshot:
            snapshot_data = json.loads(current_snapshot) if isinstance(current_snapshot, str) else current_snapshot
        else:
            snapshot_data = {}
        
        snapshot_data["manual_fields"] = request.manual_fields
        snapshot_data["manual_fields_updated_at"] = datetime.now().isoformat()
        
        db.execute(text("""
            UPDATE documents 
            SET snapshot_json = :snapshot,
                updated_at = NOW()
            WHERE id = :id
        """), {
            "id": document_id,
            "snapshot": json.dumps(snapshot_data, ensure_ascii=False, default=str)
        })
        
        db.commit()
        
        return {
            "success": True,
            "document_id": document_id,
            "manual_fields": request.manual_fields,
            "updated_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/types-with-manual-fields")
async def list_types_with_manual_fields():
    """
    List all document types that have manual fields defined.
    """
    return {
        "types": list(MANUAL_FIELDS_SCHEMAS.keys()),
        "schemas": MANUAL_FIELDS_SCHEMAS
    }
