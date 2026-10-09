"""
Document Templates Admin API - управління шаблонами документів
"""
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import os
import shutil
import json

from database_rentalhub import get_rh_db
from services.doc_engine.registry import DOC_REGISTRY
from services.doc_engine.render import TEMPLATES_DIR, render_html

router = APIRouter(prefix="/api/admin/templates", tags=["Admin Templates"])

# ============================================
# Models
# ============================================

class TemplateInfo(BaseModel):
    doc_type: str
    name: str
    name_en: str
    entity_type: str
    series: str
    description: str
    print_required: bool
    current_version: str
    versions: List[str]
    has_custom: bool

class TemplateContent(BaseModel):
    content: str
    version: str = "v1"

class TemplateUpdateRequest(BaseModel):
    content: str
    create_backup: bool = True

# ============================================
# Endpoints
# ============================================

@router.get("/")
@router.get("")
async def list_templates():
    """Список всіх шаблонів документів з метаданими"""
    templates = []
    
    for doc_type, config in DOC_REGISTRY.items():
        # Перевіряємо наявність шаблону
        template_dir = os.path.join(TEMPLATES_DIR, doc_type)
        versions = []
        has_custom = False
        
        if os.path.exists(template_dir):
            for f in os.listdir(template_dir):
                if f.endswith('.html') and not f.startswith('_'):
                    version = f.replace('.html', '')
                    versions.append(version)
                    if version.startswith('custom'):
                        has_custom = True
        
        templates.append({
            "doc_type": doc_type,
            "name": config.get("name", doc_type),
            "name_en": config.get("name_en", ""),
            "entity_type": config.get("entity_type", ""),
            "series": config.get("series", ""),
            "description": config.get("description", ""),
            "print_required": config.get("print_required", False),
            "trigger_stage": config.get("trigger_stage", ""),
            "critical_for": config.get("critical_for", []),
            "current_version": "v1",
            "versions": sorted(versions),
            "has_custom": has_custom,
            "template_exists": len(versions) > 0
        })
    
    return {
        "templates": templates,
        "total": len(templates),
        "templates_dir": TEMPLATES_DIR
    }


@router.get("/{doc_type}")
async def get_template(doc_type: str, version: str = "v1"):
    """Отримати вміст шаблону"""
    if doc_type not in DOC_REGISTRY:
        raise HTTPException(status_code=404, detail=f"Unknown doc_type: {doc_type}")
    
    config = DOC_REGISTRY[doc_type]
    template_path = os.path.join(TEMPLATES_DIR, doc_type, f"{version}.html")
    
    if not os.path.exists(template_path):
        raise HTTPException(status_code=404, detail=f"Template not found: {template_path}")
    
    with open(template_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Get base template
    base_path = os.path.join(TEMPLATES_DIR, '_base.html')
    base_content = ""
    if os.path.exists(base_path):
        with open(base_path, 'r', encoding='utf-8') as f:
            base_content = f.read()
    
    # List all versions
    versions = []
    template_dir = os.path.join(TEMPLATES_DIR, doc_type)
    if os.path.exists(template_dir):
        for f in os.listdir(template_dir):
            if f.endswith('.html') and not f.startswith('_'):
                versions.append(f.replace('.html', ''))
    
    return {
        "doc_type": doc_type,
        "name": config.get("name", doc_type),
        "version": version,
        "versions": sorted(versions),
        "content": content,
        "base_template": base_content,
        "template_path": template_path,
        "variables": get_template_variables(doc_type)
    }


@router.put("/{doc_type}")
async def update_template(
    doc_type: str,
    request: TemplateUpdateRequest,
    version: str = "v1"
):
    """Оновити шаблон документа"""
    if doc_type not in DOC_REGISTRY:
        raise HTTPException(status_code=404, detail=f"Unknown doc_type: {doc_type}")
    
    template_dir = os.path.join(TEMPLATES_DIR, doc_type)
    template_path = os.path.join(template_dir, f"{version}.html")
    
    if not os.path.exists(template_dir):
        os.makedirs(template_dir, exist_ok=True)
    
    # Create backup if requested
    backup_path = None
    if request.create_backup and os.path.exists(template_path):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = os.path.join(template_dir, 'backups')
        os.makedirs(backup_dir, exist_ok=True)
        backup_path = os.path.join(backup_dir, f"{version}_{timestamp}.html")
        shutil.copy(template_path, backup_path)
    
    # Save new content
    with open(template_path, 'w', encoding='utf-8') as f:
        f.write(request.content)
    
    return {
        "success": True,
        "message": f"Template {doc_type}/{version} updated",
        "backup_path": backup_path
    }


@router.post("/{doc_type}/preview")
async def preview_template(
    doc_type: str,
    content: str = Body(..., embed=True),
    db: Session = Depends(get_rh_db)
):
    """Превью шаблону з тестовими даними"""
    if doc_type not in DOC_REGISTRY:
        raise HTTPException(status_code=404, detail=f"Unknown doc_type: {doc_type}")
    
    # Generate sample data based on doc_type
    sample_data = generate_sample_data(doc_type)
    
    try:
        # Create temporary template
        from jinja2 import Environment, BaseLoader
        
        # Load base template
        base_path = os.path.join(TEMPLATES_DIR, '_base.html')
        with open(base_path, 'r', encoding='utf-8') as f:
            base_content = f.read()
        
        # Create environment with base template
        env = Environment(loader=BaseLoader())
        
        # First render the content template
        # Since we use {% extends '_base.html' %}, we need a different approach
        # For preview, we'll just insert content into base
        
        # Extract content block from user template
        import re
        content_match = re.search(r'{%\s*block\s+content\s*%}(.*?){%\s*endblock\s*%}', content, re.DOTALL)
        title_match = re.search(r'{%\s*block\s+title\s*%}(.*?){%\s*endblock\s*%}', content, re.DOTALL)
        styles_match = re.search(r'{%\s*block\s+extra_styles\s*%}(.*?){%\s*endblock\s*%}', content, re.DOTALL)
        
        content_block = content_match.group(1) if content_match else content
        title_block = title_match.group(1) if title_match else "Превью документа"
        styles_block = styles_match.group(1) if styles_match else ""
        
        # Build full HTML
        full_html = base_content.replace(
            '{% block title %}Документ{% endblock %}',
            title_block
        ).replace(
            '{% block extra_styles %}{% endblock %}',
            styles_block
        ).replace(
            '{% block content %}{% endblock %}',
            content_block
        )
        
        # Render with Jinja2
        template = env.from_string(full_html)
        
        # Add filters
        template.environment.filters['money'] = lambda x: f"{float(x or 0):,.2f}".replace(",", " ")
        template.environment.filters['date'] = lambda x: str(x) if x else ""
        
        html = template.render(**sample_data)
        
        return {
            "success": True,
            "html": html,
            "data_used": sample_data
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "data_used": sample_data
        }


@router.get("/{doc_type}/backups")
async def list_backups(doc_type: str):
    """Список резервних копій шаблону"""
    if doc_type not in DOC_REGISTRY:
        raise HTTPException(status_code=404, detail=f"Unknown doc_type: {doc_type}")
    
    backup_dir = os.path.join(TEMPLATES_DIR, doc_type, 'backups')
    backups = []
    
    if os.path.exists(backup_dir):
        for f in sorted(os.listdir(backup_dir), reverse=True):
            if f.endswith('.html'):
                stat = os.stat(os.path.join(backup_dir, f))
                backups.append({
                    "filename": f,
                    "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "size": stat.st_size
                })
    
    return {
        "doc_type": doc_type,
        "backups": backups,
        "total": len(backups)
    }


@router.post("/{doc_type}/restore/{backup_filename}")
async def restore_backup(doc_type: str, backup_filename: str, version: str = "v1"):
    """Відновити шаблон з резервної копії"""
    if doc_type not in DOC_REGISTRY:
        raise HTTPException(status_code=404, detail=f"Unknown doc_type: {doc_type}")
    
    backup_path = os.path.join(TEMPLATES_DIR, doc_type, 'backups', backup_filename)
    template_path = os.path.join(TEMPLATES_DIR, doc_type, f"{version}.html")
    
    if not os.path.exists(backup_path):
        raise HTTPException(status_code=404, detail=f"Backup not found: {backup_filename}")
    
    # Create backup of current before restore
    if os.path.exists(template_path):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = os.path.join(TEMPLATES_DIR, doc_type, 'backups')
        os.makedirs(backup_dir, exist_ok=True)
        current_backup = os.path.join(backup_dir, f"{version}_pre_restore_{timestamp}.html")
        shutil.copy(template_path, current_backup)
    
    # Restore
    shutil.copy(backup_path, template_path)
    
    return {
        "success": True,
        "message": f"Restored {backup_filename} to {doc_type}/{version}.html"
    }


@router.get("/base/content")
async def get_base_template():
    """Отримати базовий шаблон"""
    base_path = os.path.join(TEMPLATES_DIR, '_base.html')
    
    if not os.path.exists(base_path):
        raise HTTPException(status_code=404, detail="Base template not found")
    
    with open(base_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    return {
        "content": content,
        "path": base_path
    }


@router.put("/base/content")
async def update_base_template(request: TemplateUpdateRequest):
    """Оновити базовий шаблон"""
    base_path = os.path.join(TEMPLATES_DIR, '_base.html')
    
    # Create backup
    if request.create_backup and os.path.exists(base_path):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = os.path.join(TEMPLATES_DIR, 'backups')
        os.makedirs(backup_dir, exist_ok=True)
        backup_path = os.path.join(backup_dir, f"_base_{timestamp}.html")
        shutil.copy(base_path, backup_path)
    
    # Save
    with open(base_path, 'w', encoding='utf-8') as f:
        f.write(request.content)
    
    return {
        "success": True,
        "message": "Base template updated"
    }


# ============================================
# Helper Functions
# ============================================

def get_template_variables(doc_type: str) -> dict:
    """Повертає список змінних доступних для шаблону"""
    config = DOC_REGISTRY.get(doc_type, {})
    entity_type = config.get("entity_type", "")
    
    common_vars = {
        "doc_number": "Номер документа (PCK-2025-000001)",
        "generated_at": "Дата/час генерації (23.12.2025 10:30)",
        "company.name": "Назва компанії",
        "company.legal_name": "Юридична назва",
        "company.phone": "Телефон компанії"
    }
    
    order_vars = {
        "order.id": "ID замовлення",
        "order.order_number": "Номер замовлення (OC-7136)",
        "order.customer_name": "ПІБ клієнта",
        "order.customer_phone": "Телефон клієнта",
        "order.customer_email": "Email клієнта",
        "order.rental_start_date": "Дата початку оренди",
        "order.rental_end_date": "Дата кінця оренди",
        "order.rental_days": "Кількість днів оренди",
        "order.total_price": "Сума оренди",
        "order.deposit_amount": "Сума застави",
        "order.delivery_type": "Тип доставки (pickup/delivery)",
        "order.delivery_address": "Адреса доставки",
        "items": "Масив товарів [{name, sku, quantity, price, location}]"
    }
    
    issue_vars = {
        "issue_card.id": "ID картки видачі",
        "issue_card.order_number": "Номер замовлення",
        "issue_card.customer_name": "ПІБ клієнта",
        "issue_card.customer_phone": "Телефон клієнта",
        "issue_card.rental_start_date": "Дата видачі",
        "issue_card.rental_end_date": "Дата повернення",
        "items": "Масив товарів [{name, sku, quantity, location}]",
        "requisitors": "Список реквізиторів"
    }
    
    damage_vars = {
        "damage_case.id": "ID кейсу",
        "damage_case.order_number": "Номер замовлення",
        "damage_case.customer_name": "ПІБ клієнта",
        "damage_case.total_damage": "Загальна сума шкоди",
        "items": "Масив пошкоджень [{name, damage_type, fee}]"
    }
    
    if entity_type == "order":
        return {**common_vars, **order_vars}
    elif entity_type == "issue":
        return {**common_vars, **issue_vars}
    elif entity_type == "damage_case":
        return {**common_vars, **damage_vars}
    else:
        return common_vars


def generate_sample_data(doc_type: str) -> dict:
    """Генерує тестові дані для превью"""
    config = DOC_REGISTRY.get(doc_type, {})
    entity_type = config.get("entity_type", "")
    
    common = {
        "doc_number": "SAMPLE-2025-000001",
        "generated_at": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "company": {
            "name": "FarforRent",
            "legal_name": "ФОП Николенко Наталя Станіславівна",
            "phone": "+380 XX XXX XX XX",
            "email": "rfarfordecor@gmail.com.ua",
            "address": "м. Харків, Військовий провулок, 1",
            "iban": "UA043220010000026003340091618",
            "edrpou": "3606801844",
            "mfo": "322001",
            "bank_name": "АТ «УНІВЕРСАЛ БАНК»"
        }
    }
    
    sample_items = [
        {"name": "Тарілка керамічна 26см", "sku": "PL001", "quantity": 10, "price": 50.0, "location": "A-1-2", "article": "PL001"},
        {"name": "Келих для вина 350мл", "sku": "GL002", "quantity": 20, "price": 30.0, "location": "B-2-1", "article": "GL002"},
        {"name": "Серветка тканинна біла", "sku": "NP003", "quantity": 50, "price": 10.0, "location": "C-1-3", "article": "NP003"},
    ]
    
    if entity_type == "order":
        return {
            **common,
            "order": {
                "id": "9999",
                "order_number": "OC-9999",
                "status": "confirmed",
                "customer_name": "Тестовий Клієнт",
                "customer_phone": "+380 99 999 99 99",
                "customer_email": "test@example.com",
                "rental_start_date": "25.12.2025",
                "rental_end_date": "27.12.2025",
                "rental_days": 3,
                "total_price": 1500.0,
                "deposit_amount": 3000.0,
                "discount_amount": 0,
                "delivery_type": "delivery",
                "delivery_address": "м. Київ, вул. Тестова, 10",
                "notes": "Тестове замовлення"
            },
            "items": sample_items,
            "totals": {
                "items_count": 3,
                "total_quantity": 80,
                "subtotal": 1500.0,
                "discount": 0,
                "total": 1500.0,
                "deposit": 3000.0
            }
        }
    
    elif entity_type == "issue":
        return {
            **common,
            "issue_card": {
                "id": "IC-9999-20251225",
                "order_id": 9999,
                "order_number": "OC-9999",
                "status": "preparation",
                "customer_name": "Тестовий Клієнт",
                "customer_phone": "+380 99 999 99 99",
                "rental_start_date": "25.12.2025",
                "rental_end_date": "27.12.2025",
                "rental_days": 3,
                "delivery_type": "delivery",
                "delivery_address": "м. Київ, вул. Тестова, 10",
                "preparation_notes": "Тестові примітки"
            },
            "items": sample_items,
            "requisitors": [
                {"name": "Іван Іванов", "role": "requisitor"},
                {"name": "Петро Петров", "role": "requisitor"}
            ]
        }
    
    elif entity_type == "damage_case":
        return {
            **common,
            "damage_case": {
                "id": "DMG-9999",
                "order_number": "OC-9999",
                "customer_name": "Тестовий Клієнт",
                "customer_phone": "+380 99 999 99 99",
                "total_damage": 500.0,
                "deposit_available": 3000.0,
                "status": "open"
            },
            "items": [
                {"name": "Тарілка керамічна 26см", "sku": "PL001", "damage_type": "broken", "qty": 2, "fee": 200.0},
                {"name": "Келих для вина 350мл", "sku": "GL002", "damage_type": "chipped", "qty": 1, "fee": 150.0},
            ],
            "totals": {
                "total_items": 3,
                "total_fee": 350.0,
                "to_deduct": 350.0,
                "deposit_remaining": 2650.0
            }
        }
    
    else:
        return {
            **common,
            "items": sample_items
        }
