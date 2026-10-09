"""
Document Policy Matrix API
Phase 3: Documents Engine

Визначає які документи доступні, коли, для кого
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional, List, Dict, Any
from pydantic import BaseModel

from database_rentalhub import get_rh_db

router = APIRouter(prefix="/api/documents/policy", tags=["document-policy"])


# ============================================================
# POLICY MATRIX DEFINITION
# ============================================================

DOCUMENT_POLICY = {
    # ═══════════════════════════════════════════════════════════
    # QUOTES (Кошториси) - не юридичні документи
    # ═══════════════════════════════════════════════════════════
    "quote": {
        "name": "Кошторис",
        "category": "quote",
        "is_legal": False,
        "requires_master_agreement": False,
        "requires_annex": False,
        "payer_types": ["individual", "fop_simple", "fop_general", "llc_simple", "llc_general"],
        "order_statuses": ["draft", "negotiation", "pending_confirmation", "confirmed", "ready", "processing", "ready_for_issue"],
        "deal_modes": ["rent", "sale"],
        "conditions": [],
        "description": "Попередня оцінка вартості оренди"
    },
    
    "invoice_offer": {
        "name": "Рахунок-оферта",
        "category": "quote",
        "is_legal": False,
        "requires_master_agreement": False,
        "requires_annex": False,
        "payer_types": ["individual"],
        "order_statuses": ["draft", "negotiation", "pending_confirmation", "confirmed", "processing", "ready_for_issue"],
        "deal_modes": ["rent", "sale"],
        "conditions": [],
        "description": "Рахунок на передоплату для фіз. осіб"
    },
    
    # ═══════════════════════════════════════════════════════════
    # CONTRACTS (Договори)
    # ═══════════════════════════════════════════════════════════
    "master_agreement": {
        "name": "Рамковий договір",
        "category": "contract",
        "is_legal": True,
        "requires_master_agreement": False,  # Сам є договором
        "requires_annex": False,
        "requires_order": False,  # Можна створити без замовлення
        "payer_types": ["individual", "fop_simple", "fop_general", "llc_simple", "llc_general"],
        "order_statuses": None,  # Не залежить від замовлення
        "deal_modes": None,
        "conditions": ["has_payer_profile"],
        "description": "Річний рамковий договір оренди"
    },
    
    "contract_rent": {
        "name": "Договір оренди",
        "category": "contract",
        "is_legal": True,
        "requires_master_agreement": False,  # Legacy - для індивідуальних
        "requires_annex": False,
        "payer_types": ["individual"],
        "order_statuses": ["confirmed", "ready", "issued", "processing", "ready_for_issue"],
        "deal_modes": ["rent"],
        "conditions": [],
        "description": "Договір оренди для фіз. осіб (без рамкового)"
    },
    
    # ═══════════════════════════════════════════════════════════
    # ANNEXES (Додатки до договорів) - ЮРИДИЧНІ
    # ═══════════════════════════════════════════════════════════
    "annex": {
        "name": "Додаток до договору",
        "category": "annex",
        "is_legal": True,
        "requires_master_agreement": True,
        "requires_annex": False,
        "payer_types": ["individual", "fop_simple", "fop_general", "llc_simple", "llc_general"],
        "order_statuses": ["confirmed", "ready", "issued", "returning", "returned"],
        "deal_modes": ["rent"],
        "conditions": ["has_active_agreement"],
        "description": "Юридичний опис конкретної оренди"
    },
    
    "rental_extension": {
        "name": "Додаткова угода (продовження)",
        "category": "annex",
        "is_legal": True,
        "requires_master_agreement": True,
        "requires_annex": True,
        "payer_types": ["individual", "fop_simple", "fop_general", "llc_simple", "llc_general"],
        "order_statuses": ["issued", "returning"],
        "deal_modes": ["rent"],
        "conditions": ["has_active_agreement", "dates_changed"],
        "description": "Угода про зміну умов оренди"
    },
    
    # ═══════════════════════════════════════════════════════════
    # ACTS (Акти) - ЮРИДИЧНІ
    # ═══════════════════════════════════════════════════════════
    "issue_act": {
        "name": "Акт передачі",
        "category": "act",
        "is_legal": True,
        "requires_master_agreement": False,
        "requires_annex": False,  # Бажано, але не обов'язково
        "payer_types": ["individual", "fop_simple", "fop_general", "llc_simple", "llc_general"],
        "order_statuses": ["issued"],
        "deal_modes": ["rent", "sale"],
        "conditions": ["has_issue_card"],
        "description": "Акт передачі товарів клієнту"
    },
    
    "return_act": {
        "name": "Акт приймання",
        "category": "act",
        "is_legal": True,
        "requires_master_agreement": False,
        "requires_annex": False,
        "payer_types": ["individual", "fop_simple", "fop_general", "llc_simple", "llc_general"],
        "order_statuses": ["returning", "returned", "closed"],
        "deal_modes": ["rent"],
        "conditions": [],
        "description": "Акт повернення товарів від клієнта"
    },
    
    "partial_return_act": {
        "name": "Акт часткового повернення",
        "category": "act",
        "is_legal": True,
        "requires_master_agreement": False,
        "requires_annex": False,
        "payer_types": ["individual", "fop_simple", "fop_general", "llc_simple", "llc_general"],
        "order_statuses": ["issued", "returning"],
        "deal_modes": ["rent"],
        "conditions": ["has_partial_return"],
        "description": "Акт приймання частини товарів"
    },
    
    "damage_report": {
        "name": "Акт фіксації пошкоджень",
        "category": "act",
        "is_legal": True,
        "requires_master_agreement": False,
        "requires_annex": False,
        "payer_types": ["individual", "fop_simple", "fop_general", "llc_simple", "llc_general"],
        "order_statuses": ["returning", "returned", "closed"],
        "deal_modes": ["rent"],
        "conditions": ["has_damage"],
        "description": "Акт з фото та описом пошкоджень"
    },
    
    "damage_settlement_act": {
        "name": "Акт утримання із застави",
        "category": "act",
        "is_legal": True,
        "requires_master_agreement": False,
        "requires_annex": False,
        "payer_types": ["individual", "fop_simple", "fop_general", "llc_simple", "llc_general"],
        "order_statuses": ["returned", "closed"],
        "deal_modes": ["rent"],
        "conditions": ["has_damage", "has_deposit"],
        "description": "Акт взаєморозрахунків по збитках"
    },
    
    "deposit_refund_act": {
        "name": "Акт повернення застави",
        "category": "act",
        "is_legal": True,
        "requires_master_agreement": False,
        "requires_annex": False,
        "payer_types": ["individual", "fop_simple", "fop_general", "llc_simple", "llc_general"],
        "order_statuses": ["returned", "closed"],
        "deal_modes": ["rent"],
        "conditions": ["has_deposit", "deposit_to_refund"],
        "description": "Підтвердження повернення застави"
    },
    
    # ═══════════════════════════════════════════════════════════
    # FINANCE DOCUMENTS (Фінансові)
    # ═══════════════════════════════════════════════════════════
    "invoice_legal": {
        "name": "Рахунок (юр. особа)",
        "category": "finance",
        "is_legal": True,
        "requires_master_agreement": True,
        "requires_annex": False,
        "payer_types": ["fop_simple", "fop_general", "llc_simple", "llc_general"],
        "order_statuses": ["confirmed", "ready", "issued"],
        "deal_modes": ["rent", "sale"],
        "conditions": ["has_active_agreement"],
        "description": "Рахунок на оплату для ФОП/ТОВ"
    },
    
    "service_act": {
        "name": "Акт виконаних робіт",
        "category": "finance",
        "is_legal": True,
        "requires_master_agreement": True,
        "requires_annex": True,
        "payer_types": ["fop_simple", "llc_simple"],
        "order_statuses": ["returned", "closed"],
        "deal_modes": ["rent"],
        "conditions": ["has_active_agreement", "is_simple_tax"],
        "description": "Акт виконаних робіт для спрощеної системи"
    },
    
    "goods_invoice": {
        "name": "Видаткова накладна",
        "category": "finance",
        "is_legal": True,
        "requires_master_agreement": True,
        "requires_annex": True,
        "payer_types": ["fop_general", "llc_general"],
        "order_statuses": ["issued", "returning", "returned"],
        "deal_modes": ["rent", "sale"],
        "conditions": ["has_active_agreement", "is_general_tax"],
        "description": "Видаткова накладна для загальної системи"
    },
    
    "damage_invoice": {
        "name": "Рахунок на пошкодження",
        "category": "finance",
        "is_legal": True,
        "requires_master_agreement": False,
        "requires_annex": False,
        "payer_types": ["individual", "fop_simple", "fop_general", "llc_simple", "llc_general"],
        "order_statuses": ["returned", "closed"],
        "deal_modes": ["rent"],
        "conditions": ["has_damage", "damage_exceeds_deposit"],
        "description": "Рахунок на доплату за пошкодження"
    },
    
    # ═══════════════════════════════════════════════════════════
    # OPERATIONS (Операційні - внутрішні)
    # ═══════════════════════════════════════════════════════════
    "picking_list": {
        "name": "Лист комплектації",
        "category": "operations",
        "is_legal": False,
        "requires_master_agreement": False,
        "requires_annex": False,
        "payer_types": ["individual", "fop_simple", "fop_general", "llc_simple", "llc_general"],
        "order_statuses": ["confirmed", "ready"],
        "deal_modes": ["rent", "sale"],
        "conditions": ["has_issue_card"],
        "description": "Список товарів для збору на складі"
    },
    
    "issue_checklist": {
        "name": "Чеклист видачі",
        "category": "operations",
        "is_legal": False,
        "requires_master_agreement": False,
        "requires_annex": False,
        "payer_types": ["individual", "fop_simple", "fop_general", "llc_simple", "llc_general"],
        "order_statuses": ["confirmed", "ready"],
        "deal_modes": ["rent", "sale"],
        "conditions": ["has_issue_card"],
        "description": "Чеклист для складу: упаковка, маркування"
    },
    
    "delivery_note": {
        "name": "ТТН / Накладна доставки",
        "category": "operations",
        "is_legal": True,
        "requires_master_agreement": False,
        "requires_annex": False,
        "payer_types": ["individual", "fop_simple", "fop_general", "llc_simple", "llc_general"],
        "order_statuses": ["ready", "issued"],
        "deal_modes": ["rent", "sale"],
        "conditions": ["is_delivery"],
        "description": "Товарно-транспортна накладна"
    },
}


# ============================================================
# POLICY CHECK FUNCTION
# ============================================================

def check_document_availability(
    doc_type: str,
    order_data: Dict[str, Any],
    payer_data: Optional[Dict[str, Any]] = None,
    agreement_data: Optional[Dict[str, Any]] = None,
    annex_data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Check if a document type is available for given order context.
    
    Returns:
        {
            "available": bool,
            "reason": str (if not available),
            "warnings": list (optional warnings)
        }
    """
    policy = DOCUMENT_POLICY.get(doc_type)
    if not policy:
        return {"available": False, "reason": f"Unknown document type: {doc_type}"}
    
    warnings = []
    
    # Check if requires order
    if policy.get("requires_order", True) and not order_data:
        return {"available": False, "reason": "Потрібне замовлення"}
    
    # Check order status
    if order_data and policy.get("order_statuses"):
        order_status = order_data.get("status")
        if order_status not in policy["order_statuses"]:
            return {
                "available": False, 
                "reason": f"Неправильний статус замовлення: {order_status}. Потрібен: {', '.join(policy['order_statuses'])}"
            }
    
    # Check deal mode
    if order_data and policy.get("deal_modes"):
        deal_mode = order_data.get("deal_mode", "rent")
        if deal_mode not in policy["deal_modes"]:
            return {
                "available": False,
                "reason": f"Недоступно для режиму: {deal_mode}"
            }
    
    # Check payer type
    if payer_data and policy.get("payer_types"):
        payer_type = payer_data.get("payer_type", "individual")
        if payer_type not in policy["payer_types"]:
            return {
                "available": False,
                "reason": f"Недоступно для типу платника: {payer_type}"
            }
    
    # Check master agreement requirement
    if policy.get("requires_master_agreement"):
        if not agreement_data or agreement_data.get("status") != "signed":
            return {
                "available": False,
                "reason": "Потрібен підписаний рамковий договір"
            }
        if agreement_data.get("is_expired"):
            return {
                "available": False,
                "reason": "Рамковий договір закінчився"
            }
    
    # Check annex requirement
    if policy.get("requires_annex"):
        if not annex_data:
            return {
                "available": False,
                "reason": "Потрібен додаток до договору (Annex)"
            }
    
    # Check conditions
    conditions = policy.get("conditions", [])
    for condition in conditions:
        if condition == "has_payer_profile":
            if not payer_data:
                return {"available": False, "reason": "Потрібен профіль платника"}
        
        elif condition == "has_active_agreement":
            if not agreement_data or agreement_data.get("status") != "signed":
                return {"available": False, "reason": "Потрібен активний рамковий договір"}
        
        elif condition == "has_damage":
            if not order_data.get("has_damage"):
                return {"available": False, "reason": "Немає зафіксованої шкоди"}
        
        elif condition == "has_deposit":
            if not order_data.get("deposit_held", 0) > 0:
                return {"available": False, "reason": "Немає застави"}
        
        elif condition == "deposit_to_refund":
            if not order_data.get("deposit_to_refund", 0) > 0:
                return {"available": False, "reason": "Немає застави до повернення"}
        
        elif condition == "damage_exceeds_deposit":
            damage = order_data.get("damage_total", 0)
            deposit = order_data.get("deposit_held", 0)
            if damage <= deposit:
                return {"available": False, "reason": "Шкода не перевищує заставу"}
        
        elif condition == "has_issue_card":
            if not order_data.get("has_issue_card"):
                warnings.append("Картка видачі не створена")
        
        elif condition == "has_partial_return":
            if not order_data.get("has_partial_return"):
                return {"available": False, "reason": "Немає часткового повернення"}
        
        elif condition == "is_delivery":
            delivery_type = order_data.get("delivery_type", "pickup")
            if delivery_type == "pickup":
                return {"available": False, "reason": "Тільки для доставки (не самовивіз)"}
        
        elif condition == "is_simple_tax":
            payer_type = payer_data.get("payer_type") if payer_data else None
            if payer_type not in ["fop_simple", "llc_simple"]:
                return {"available": False, "reason": "Тільки для спрощеної системи оподаткування"}
        
        elif condition == "is_general_tax":
            payer_type = payer_data.get("payer_type") if payer_data else None
            if payer_type not in ["fop_general", "llc_general"]:
                return {"available": False, "reason": "Тільки для загальної системи оподаткування"}
        
        elif condition == "dates_changed":
            if not order_data.get("dates_changed"):
                warnings.append("Дати не змінювались")
    
    return {
        "available": True,
        "warnings": warnings if warnings else None,
        "policy": {
            "name": policy["name"],
            "category": policy["category"],
            "is_legal": policy["is_legal"]
        }
    }


def get_available_documents(
    order_data: Dict[str, Any],
    payer_data: Optional[Dict[str, Any]] = None,
    agreement_data: Optional[Dict[str, Any]] = None,
    annex_data: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """
    Get list of all available documents for given context.
    Groups by category.
    """
    available = []
    
    for doc_type, policy in DOCUMENT_POLICY.items():
        result = check_document_availability(
            doc_type, order_data, payer_data, agreement_data, annex_data
        )
        
        available.append({
            "doc_type": doc_type,
            "name": policy["name"],
            "category": policy["category"],
            "is_legal": policy["is_legal"],
            "available": result["available"],
            "reason": result.get("reason"),
            "warnings": result.get("warnings"),
            "description": policy["description"]
        })
    
    return available


# ============================================================
# API ENDPOINTS
# ============================================================

@router.get("/matrix")
async def get_policy_matrix():
    """Get full document policy matrix"""
    return {
        "policies": DOCUMENT_POLICY,
        "categories": ["quote", "contract", "annex", "act", "finance", "operations"]
    }


@router.get("/check/{doc_type}")
async def check_document_policy(
    doc_type: str,
    order_id: Optional[int] = None,
    payer_profile_id: Optional[int] = None,
    db: Session = Depends(get_rh_db)
):
    """Check if specific document type is available"""
    
    order_data = None
    payer_data = None
    agreement_data = None
    annex_data = None
    
    # Load order data
    if order_id:
        order_result = db.execute(text("""
            SELECT 
                o.order_id, o.status, o.deal_mode, o.delivery_type,
                o.payer_profile_id, o.active_annex_id,
                COALESCE(d.held_amount, 0) as deposit_held,
                COALESCE(d.held_amount - d.used_amount - d.refunded_amount, 0) as deposit_to_refund,
                COALESCE((SELECT SUM(fee) FROM product_damage_history WHERE order_id = o.order_id), 0) as damage_total,
                (SELECT COUNT(*) > 0 FROM product_damage_history WHERE order_id = o.order_id) as has_damage,
                (SELECT COUNT(*) > 0 FROM issue_cards WHERE order_id = o.order_id) as has_issue_card
            FROM orders o
            LEFT JOIN fin_deposit_holds d ON d.order_id = o.order_id
            WHERE o.order_id = :order_id
        """), {"order_id": order_id})
        
        row = order_result.fetchone()
        if row:
            order_data = {
                "order_id": row[0],
                "status": row[1],
                "deal_mode": row[2] or "rent",
                "delivery_type": row[3] or "pickup",
                "payer_profile_id": row[4],
                "active_annex_id": row[5],
                "deposit_held": float(row[6] or 0),
                "deposit_to_refund": float(row[7] or 0),
                "damage_total": float(row[8] or 0),
                "has_damage": bool(row[9]),
                "has_issue_card": bool(row[10])
            }
            
            # Use order's payer if not specified
            if not payer_profile_id and order_data.get("payer_profile_id"):
                payer_profile_id = order_data["payer_profile_id"]
    
    # Load payer data
    if payer_profile_id:
        payer_result = db.execute(text("""
            SELECT id, payer_type, company_name, director_name
            FROM payer_profiles WHERE id = :id
        """), {"id": payer_profile_id})
        
        prow = payer_result.fetchone()
        if prow:
            payer_data = {
                "id": prow[0],
                "payer_type": prow[1],
                "company_name": prow[2],
                "director_name": prow[3]
            }
        
        # Load active agreement
        agreement_result = db.execute(text("""
            SELECT id, contract_number, status, valid_until,
                   valid_until < CURDATE() as is_expired
            FROM master_agreements 
            WHERE payer_profile_id = :pid AND status = 'signed'
            ORDER BY signed_at DESC LIMIT 1
        """), {"pid": payer_profile_id})
        
        arow = agreement_result.fetchone()
        if arow:
            agreement_data = {
                "id": arow[0],
                "contract_number": arow[1],
                "status": arow[2],
                "valid_until": arow[3].isoformat() if arow[3] else None,
                "is_expired": bool(arow[4])
            }
    
    # Load annex data
    if order_data and order_data.get("active_annex_id"):
        annex_result = db.execute(text("""
            SELECT id, annex_number, version, status
            FROM order_annexes WHERE id = :id
        """), {"id": order_data["active_annex_id"]})
        
        xrow = annex_result.fetchone()
        if xrow:
            annex_data = {
                "id": xrow[0],
                "annex_number": xrow[1],
                "version": xrow[2],
                "status": xrow[3]
            }
    
    result = check_document_availability(
        doc_type, order_data or {}, payer_data, agreement_data, annex_data
    )
    
    return {
        "doc_type": doc_type,
        **result,
        "context": {
            "order": order_data,
            "payer": payer_data,
            "agreement": agreement_data,
            "annex": annex_data
        }
    }


@router.get("/available")
async def get_available_documents_for_order(
    order_id: int,
    db: Session = Depends(get_rh_db)
):
    """Get all available documents for an order"""
    
    # Load full context
    order_result = db.execute(text("""
        SELECT 
            o.order_id, o.status, o.deal_mode, o.delivery_type,
            o.payer_profile_id, o.active_annex_id,
            COALESCE(d.held_amount, 0) as deposit_held,
            COALESCE(d.held_amount - d.used_amount - d.refunded_amount, 0) as deposit_to_refund,
            COALESCE((SELECT SUM(fee) FROM product_damage_history WHERE order_id = o.order_id), 0) as damage_total,
            (SELECT COUNT(*) > 0 FROM product_damage_history WHERE order_id = o.order_id) as has_damage,
            (SELECT COUNT(*) > 0 FROM issue_cards WHERE order_id = o.order_id) as has_issue_card
        FROM orders o
        LEFT JOIN fin_deposit_holds d ON d.order_id = o.order_id
        WHERE o.order_id = :order_id
    """), {"order_id": order_id})
    
    row = order_result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Order not found")
    
    order_data = {
        "order_id": row[0],
        "status": row[1],
        "deal_mode": row[2] or "rent",
        "delivery_type": row[3] or "pickup",
        "payer_profile_id": row[4],
        "active_annex_id": row[5],
        "deposit_held": float(row[6] or 0),
        "deposit_to_refund": float(row[7] or 0),
        "damage_total": float(row[8] or 0),
        "has_damage": bool(row[9]),
        "has_issue_card": bool(row[10])
    }
    
    payer_data = None
    agreement_data = None
    annex_data = None
    
    payer_profile_id = order_data.get("payer_profile_id")
    if payer_profile_id:
        payer_result = db.execute(text("""
            SELECT id, payer_type, company_name, director_name
            FROM payer_profiles WHERE id = :id
        """), {"id": payer_profile_id})
        
        prow = payer_result.fetchone()
        if prow:
            payer_data = {
                "id": prow[0],
                "payer_type": prow[1],
                "company_name": prow[2],
                "director_name": prow[3]
            }
        
        agreement_result = db.execute(text("""
            SELECT id, contract_number, status, valid_until,
                   valid_until < CURDATE() as is_expired
            FROM master_agreements 
            WHERE payer_profile_id = :pid AND status = 'signed'
            ORDER BY signed_at DESC LIMIT 1
        """), {"pid": payer_profile_id})
        
        arow = agreement_result.fetchone()
        if arow:
            agreement_data = {
                "id": arow[0],
                "contract_number": arow[1],
                "status": arow[2],
                "valid_until": arow[3].isoformat() if arow[3] else None,
                "is_expired": bool(arow[4])
            }
    
    if order_data.get("active_annex_id"):
        annex_result = db.execute(text("""
            SELECT id, annex_number, version, status
            FROM order_annexes WHERE id = :id
        """), {"id": order_data["active_annex_id"]})
        
        xrow = annex_result.fetchone()
        if xrow:
            annex_data = {
                "id": xrow[0],
                "annex_number": xrow[1],
                "version": xrow[2],
                "status": xrow[3]
            }
    
    documents = get_available_documents(order_data, payer_data, agreement_data, annex_data)
    
    # Group by category
    by_category = {}
    for doc in documents:
        cat = doc["category"]
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(doc)
    
    return {
        "order_id": order_id,
        "documents": documents,
        "by_category": by_category,
        "context": {
            "order_status": order_data["status"],
            "deal_mode": order_data["deal_mode"],
            "has_payer": payer_data is not None,
            "payer_type": payer_data["payer_type"] if payer_data else None,
            "has_agreement": agreement_data is not None,
            "has_annex": annex_data is not None
        }
    }
