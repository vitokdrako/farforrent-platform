"""
Document Registry - повний реєстр з 14 типів документів
FarforRent Document Engine v2.0
"""

DOC_REGISTRY = {
    # ═══════════════════════════════════════════════════════════════
    # 1. Рахунок-оферта (Invoice / Offer)
    # ═══════════════════════════════════════════════════════════════
    "invoice_offer": {
        "name": "Рахунок-оферта",
        "name_en": "Invoice Offer",
        "entity_type": "order",
        "series": "INV",
        "template": "invoice_offer/v1.html",
        "requirements": ["order_id"],
        "description": "Рахунок на передоплату з переліком позицій",
        "trigger_stage": "draft_to_confirm",
        "trigger_before": "payment",
        "print_required": False,
        "pdf_always": True,
        "critical_for": ["legal", "finance"],
        "purpose": "юридичний акцепт, фіксація сум, дат, застави"
    },
    
    # ═══════════════════════════════════════════════════════════════
    # 2. Акт передачі (Issue Act)
    # ═══════════════════════════════════════════════════════════════
    "issue_act": {
        "name": "Акт передачі",
        "name_en": "Issue Act",
        "entity_type": "issue",
        "series": "ISS",
        "template": "issue_act/v1.html",
        "requirements": ["issue_card_id"],
        "description": "Акт передачі товарів клієнту",
        "trigger_stage": "ready_to_issued",
        "trigger_at": "issue",
        "print_required": True,
        "pdf_always": True,
        "critical_for": ["legal"],
        "purpose": "що саме передали, старт відповідальності клієнта"
    },
    
    # ═══════════════════════════════════════════════════════════════
    # 3. Лист комплектації (Picking List)
    # ═══════════════════════════════════════════════════════════════
    "picking_list": {
        "name": "Лист комплектації",
        "name_en": "Picking List",
        "entity_type": "issue",
        "series": "PCK",
        "template": "picking_list/v1.html",
        "requirements": ["issue_card_id"],
        "description": "Список товарів для збору на складі",
        "trigger_stage": "packing_shipping",
        "trigger_at": "picking",
        "print_required": True,
        "pdf_always": True,
        "critical_for": ["operations"],
        "purpose": "склад → видача, контроль кількості"
    },
    
    # ═══════════════════════════════════════════════════════════════
    # 4. Акт приймання / повернення (Return Act)
    # ═══════════════════════════════════════════════════════════════
    "return_act": {
        "name": "Акт повернення",
        "name_en": "Return Act",
        "entity_type": "return",
        "series": "RET",
        "template": "return_act/v1.html",
        "requirements": ["order_id"],
        "description": "Акт повернення товарів від клієнта",
        "trigger_stage": "return_intake",
        "trigger_at": "return",
        "print_required": True,
        "pdf_always": True,
        "critical_for": ["legal"],
        "purpose": "що прийнято, початок перевірки"
    },
    
    # ═══════════════════════════════════════════════════════════════
    # 5. Дефектний акт (Defect Act)
    # ═══════════════════════════════════════════════════════════════
    "defect_act": {
        "name": "Дефектний акт",
        "name_en": "Defect Act",
        "entity_type": "order",
        "series": "DEF",
        "template": "defect_act/v1.html",
        "requirements": ["order_id"],
        "description": "Акт фіксації дефектів/пошкоджень повернутого декору",
        "trigger_stage": "after_return",
        "trigger_at": "return_settlement",
        "print_required": True,
        "pdf_always": True,
        "critical_for": ["legal", "finance"],
        "purpose": "фіксація дефектів, підстава для утримання коштів"
    },
    
    # ═══════════════════════════════════════════════════════════════
    # 6. Акт взаєморозрахунків
    # ═══════════════════════════════════════════════════════════════
    "deposit_settlement_act": {
        "name": "Акт взаєморозрахунків",
        "name_en": "Deposit Settlement Act",
        "entity_type": "order",
        "series": "DSA",
        "template": "deposit_settlement_act/v1.html",
        "requirements": ["order_id"],
        "description": "Акт взаєморозрахунків по заставі",
        "trigger_stage": "settlement",
        "print_required": True,
        "pdf_always": True,
        "critical_for": ["finance"],
        "purpose": "взаєморозрахунки із заставою"
    },
    
    # ═══════════════════════════════════════════════════════════════
    # ДОКУМЕНТИ ДЛЯ ЮРИДИЧНИХ ОСІБ (ФОП / ТОВ) — НЕ ЧІПАЄМО
    # ═══════════════════════════════════════════════════════════════
    "invoice_legal": {
        "name": "Рахунок (юр. особа)",
        "name_en": "Legal Entity Invoice",
        "entity_type": "order",
        "series": "INV",
        "template": "invoice_legal/v1.html",
        "requirements": ["order_id"],
        "description": "Рахунок на оплату для ФОП/ТОВ",
        "trigger_stage": "draft_to_confirm",
        "trigger_before": "payment",
        "print_required": False,
        "pdf_always": True,
        "critical_for": ["legal", "finance"],
        "purpose": "Офіційний рахунок для юр. осіб з реквізитами сторін",
        "payer_types": ["fop_simple", "fop_general", "llc_simple", "llc_general"]
    },
    "service_act": {
        "name": "Акт надання послуг",
        "name_en": "Service Completion Act",
        "entity_type": "order",
        "series": "ACT",
        "template": "service_act/v1.html",
        "requirements": ["order_id"],
        "description": "Акт виконаних робіт для спрощеної системи (послуга)",
        "trigger_stage": "after_return",
        "trigger_at": "settlement",
        "print_required": True,
        "pdf_always": True,
        "critical_for": ["legal", "finance"],
        "purpose": "Підтвердження надання послуг для ФОП/ТОВ",
        "payer_types": ["fop_simple", "llc_simple"]
    },
    "goods_invoice": {
        "name": "Видаткова накладна",
        "name_en": "Goods Invoice / Delivery Note",
        "entity_type": "order",
        "series": "VN",
        "template": "goods_invoice/v1.html",
        "requirements": ["order_id"],
        "description": "Видаткова накладна для загальної системи (товар)",
        "trigger_stage": "issue",
        "trigger_at": "issue",
        "print_required": True,
        "pdf_always": True,
        "critical_for": ["legal", "finance"],
        "purpose": "Документ відпуску товару для ФОП/ТОВ на загальній системі",
        "payer_types": ["fop_general", "llc_general"]
    },
}

# ═══════════════════════════════════════════════════════════════
# Helper Functions
# ═══════════════════════════════════════════════════════════════

def get_doc_config(doc_type: str) -> dict:
    """Отримати конфігурацію документа за типом"""
    if doc_type not in DOC_REGISTRY:
        raise ValueError(f"Unknown document type: {doc_type}")
    return DOC_REGISTRY[doc_type]

def get_docs_for_entity(entity_type: str) -> list:
    """Отримати список доступних документів для типу сутності"""
    return [
        {"doc_type": key, **value}
        for key, value in DOC_REGISTRY.items()
        if value["entity_type"] == entity_type
    ]

def get_required_print_docs() -> list:
    """Отримати список документів з обов'язковим друком"""
    return [
        {"doc_type": key, **value}
        for key, value in DOC_REGISTRY.items()
        if value.get("print_required") == True
    ]

def get_docs_by_trigger(trigger_stage: str) -> list:
    """Отримати документи за стадією тригера"""
    return [
        {"doc_type": key, **value}
        for key, value in DOC_REGISTRY.items()
        if value.get("trigger_stage") == trigger_stage
    ]

def get_critical_docs(critical_type: str) -> list:
    """Отримати критичні документи (legal/finance/operations)"""
    return [
        {"doc_type": key, **value}
        for key, value in DOC_REGISTRY.items()
        if critical_type in value.get("critical_for", [])
    ]
