"""
Catalog API routes - inventory management
✅ MIGRATED: Using RentalHub DB
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime

from database_rentalhub import get_rh_db
from utils.image_helper import normalize_image_url

router = APIRouter(prefix="/api/catalog", tags=["catalog"])


@router.get("/categories")
async def get_categories(
    db: Session = Depends(get_rh_db)
):
    """
    Отримати дерево категорій та підкатегорій з кількістю товарів
    """
    try:
        # Отримати всі категорії з кількістю товарів
        result = db.execute(text("""
            SELECT 
                p.category_name,
                p.subcategory_name,
                COUNT(DISTINCT p.product_id) as product_count,
                SUM(p.quantity) as total_qty
            FROM products p
            WHERE p.status = 1 AND p.category_name IS NOT NULL
            GROUP BY p.category_name, p.subcategory_name
            ORDER BY p.category_name, p.subcategory_name
        """))
        
        categories_map = {}
        for row in result:
            cat_name = row[0] or "Без категорії"
            subcat_name = row[1]
            count = row[2]
            qty = row[3] or 0
            
            if cat_name not in categories_map:
                categories_map[cat_name] = {
                    "name": cat_name,
                    "product_count": 0,
                    "total_qty": 0,
                    "subcategories": []
                }
            
            categories_map[cat_name]["product_count"] += count
            categories_map[cat_name]["total_qty"] += qty
            
            if subcat_name:
                categories_map[cat_name]["subcategories"].append({
                    "name": subcat_name,
                    "product_count": count,
                    "total_qty": qty
                })
        
        # Отримати унікальні кольори (розпарсити через кому)
        colors_result = db.execute(text("""
            SELECT color, COUNT(*) as cnt FROM products 
            WHERE status = 1 AND color IS NOT NULL AND color != ''
            GROUP BY color ORDER BY cnt DESC
        """))
        color_counts = {}
        for row in colors_result:
            parts = [c.strip() for c in row[0].split(',') if c.strip()]
            for p in parts:
                color_counts[p] = color_counts.get(p, 0) + row[1]
        colors = sorted(color_counts.keys())
        
        # Отримати унікальні матеріали (розпарсити через кому)
        materials_result = db.execute(text("""
            SELECT material, COUNT(*) as cnt FROM products 
            WHERE status = 1 AND material IS NOT NULL AND material != ''
            GROUP BY material ORDER BY cnt DESC
        """))
        mat_counts = {}
        for row in materials_result:
            parts = [m.strip() for m in row[0].split(',') if m.strip()]
            for p in parts:
                mat_counts[p] = mat_counts.get(p, 0) + row[1]
        materials = sorted(mat_counts.keys())
        
        return {
            "categories": list(categories_map.values()),
            "colors": colors,
            "materials": materials
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Помилка: {str(e)}")


@router.get("/items-by-category")
async def get_items_by_category(
    category: str = None,
    subcategory: str = None,
    color: str = None,
    material: str = None,
    min_qty: int = None,
    max_qty: int = None,
    search: str = None,
    availability: str = None,  # 'available', 'in_rent', 'reserved', 'on_wash', 'on_restoration', 'on_laundry'
    date_from: str = None,  # YYYY-MM-DD - початок періоду оренди
    date_to: str = None,    # YYYY-MM-DD - кінець періоду оренди
    limit: int = 200,
    db: Session = Depends(get_rh_db)
):
    """
    Отримати товари з фільтрами по категоріям, кольору, матеріалу, кількості
    З підтримкою перевірки доступності на конкретний період
    
    Статуси:
    - reserved: awaiting_customer, processing, ready_for_issue, pending (очікують видачі)
    - in_rent: issued, on_rent (видані клієнту)
    - on_wash: на мийці (products.state = 'on_wash')
    - on_restoration: на реставрації (products.state = 'on_repair')
    - on_laundry: в хімчистці (products.state = 'on_laundry')
    
    ВАЖЛИВО: Статус товару береться з products.state та products.frozen_quantity
    """
    try:
        # Маппінг фільтрів до значень state в БД
        state_filter_map = {
            'on_wash': 'on_wash',
            'on_restoration': 'on_repair',
            'on_laundry': 'on_laundry'
        }
        
        # Спеціальна обробка для фільтрів по статусу обробки
        processing_filter = availability in ('on_wash', 'on_restoration', 'on_laundry')
        rent_filter = availability in ('in_rent', 'reserved')
        
        if processing_filter:
            # Знайти товари на обробці з product_damage_history (SSOT)
            pdh_type_map = {
                'on_wash': ('wash', 'washing'),
                'on_restoration': ('restoration',),
                'on_laundry': ('laundry',)
            }
            pdh_types = pdh_type_map[availability]
            pdh_type_placeholders = ','.join(f"'{t}'" for t in pdh_types)
            
            # Спочатку знайти product_ids з PDH
            pdh_product_result = db.execute(text(f"""
                SELECT product_id, SUM(COALESCE(qty, 1) - COALESCE(processed_qty, 0)) as active_qty
                FROM product_damage_history
                WHERE processing_type IN ({pdh_type_placeholders})
                AND COALESCE(processing_status, '') NOT IN ('completed', 'returned_to_stock', 'hidden', 'deleted')
                GROUP BY product_id
                HAVING active_qty > 0
            """)).fetchall()
            
            pdh_product_ids = [row[0] for row in pdh_product_result]
            
            if not pdh_product_ids:
                return {"items": [], "stats": {"total": 0, "available": 0, "in_rent": 0, "reserved": 0, "on_wash": 0, "on_restoration": 0, "on_laundry": 0}, "date_filter_active": bool(date_from and date_to)}
            
            pdh_ids_str = ','.join(str(int(pid)) for pid in pdh_product_ids)
            sql_parts = [f"""
                SELECT 
                    p.product_id, p.sku, p.name, p.price, p.rental_price, p.image_url,
                    p.category_name, p.subcategory_name,
                    p.quantity, p.zone, p.aisle, p.shelf,
                    p.color, p.material, p.size,
                    p.cleaning_status, p.product_state,
                    p.description, p.state, p.frozen_quantity, p.in_laundry, p.family_id
                FROM products p
                WHERE p.status = 1 AND p.product_id IN ({pdh_ids_str})
            """]
            params = {}
            
        elif rent_filter:
            # Знайти товари в оренді або резерві
            if availability == 'in_rent':
                # Товари в реальній оренді
                rent_sql = """
                    SELECT DISTINCT oi.product_id
                    FROM order_items oi
                    JOIN orders o ON oi.order_id = o.order_id
                    WHERE o.status IN ('issued', 'on_rent')
                """
                # + Товари в часткових поверненнях (pending)
                partial_sql = """
                    SELECT DISTINCT prvi.product_id
                    FROM partial_return_version_items prvi
                    JOIN partial_return_versions prv ON prvi.version_id = prv.version_id
                    WHERE prvi.status = 'pending' AND prv.status = 'active'
                """
                # Об'єднуємо
                combined_sql = f"SELECT product_id FROM ({rent_sql} UNION {partial_sql}) as combined"
            else:  # reserved
                combined_sql = """
                    SELECT DISTINCT oi.product_id
                    FROM order_items oi
                    JOIN orders o ON oi.order_id = o.order_id
                    WHERE o.status IN ('processing', 'ready_for_issue', 'awaiting_customer', 'pending')
                    AND o.rental_end_date >= CURDATE()
                """
            
            try:
                rent_result = db.execute(text(combined_sql)).fetchall()
            except Exception:
                # Fallback якщо таблиці часткових повернень не існують
                rent_result = db.execute(text(rent_sql if availability == 'in_rent' else combined_sql)).fetchall()
            rent_product_ids = [row[0] for row in rent_result]
            
            if not rent_product_ids:
                return {"items": [], "stats": {"total": 0, "available": 0, "in_rent": 0, "reserved": 0, "on_wash": 0, "on_restoration": 0, "on_laundry": 0}, "date_filter_active": bool(date_from and date_to)}
            
            sql_parts = ["""
                SELECT 
                    p.product_id, p.sku, p.name, p.price, p.rental_price, p.image_url,
                    p.category_name, p.subcategory_name,
                    p.quantity, p.zone, p.aisle, p.shelf,
                    p.color, p.material, p.size,
                    p.cleaning_status, p.product_state,
                    p.description, p.state, p.frozen_quantity, p.in_laundry, p.family_id
                FROM products p
                WHERE p.status = 1 AND p.product_id IN :rent_ids
            """]
            params = {"rent_ids": tuple(rent_product_ids)}
            
        else:
            # Звичайний запит
            sql_parts = ["""
                SELECT 
                    p.product_id, p.sku, p.name, p.price, p.rental_price, p.image_url,
                    p.category_name, p.subcategory_name,
                    p.quantity, p.zone, p.aisle, p.shelf,
                    p.color, p.material, p.size,
                    p.cleaning_status, p.product_state,
                    p.description, p.state, p.frozen_quantity, p.in_laundry, p.family_id
                FROM products p
                WHERE p.status = 1
            """]
            params = {}
        
        # Category filter
        if category and category != 'all':
            sql_parts.append("AND p.category_name = :category")
            params['category'] = category
        
        # Subcategory filter
        if subcategory and subcategory != 'all':
            sql_parts.append("AND p.subcategory_name = :subcategory")
            params['subcategory'] = subcategory
        
        # Color filter (multi-select via comma, LIKE for partial match)
        if color and color != 'all':
            color_parts = [c.strip() for c in color.split(',') if c.strip()]
            if color_parts:
                color_conds = []
                for i, cp in enumerate(color_parts):
                    key = f'color_{i}'
                    color_conds.append(f"p.color LIKE :{key}")
                    params[key] = f'%{cp}%'
                sql_parts.append(f"AND ({' OR '.join(color_conds)})")
        
        # Material filter (multi-select via comma, LIKE for partial match)
        if material and material != 'all':
            mat_parts = [m.strip() for m in material.split(',') if m.strip()]
            if mat_parts:
                mat_conds = []
                for i, mp in enumerate(mat_parts):
                    key = f'material_{i}'
                    mat_conds.append(f"p.material LIKE :{key}")
                    params[key] = f'%{mp}%'
                sql_parts.append(f"AND ({' OR '.join(mat_conds)})")
        
        # Quantity filter
        if min_qty is not None:
            sql_parts.append("AND p.quantity >= :min_qty")
            params['min_qty'] = min_qty
        
        if max_qty is not None:
            sql_parts.append("AND p.quantity <= :max_qty")
            params['max_qty'] = max_qty
        
        # Search filter
        if search:
            sql_parts.append("""
                AND (
                    p.sku LIKE :search 
                    OR p.name LIKE :search 
                    OR p.color LIKE :search 
                    OR p.material LIKE :search
                )
            """)
            params['search'] = f"%{search}%"
        
        sql_parts.append("ORDER BY p.category_name, p.subcategory_name, p.name")
        sql_parts.append(f"LIMIT {limit}")
        
        final_sql = " ".join(sql_parts)
        results = db.execute(text(final_sql), params).fetchall()
        
        # Отримати всі product_ids для оптимізації запитів
        product_ids = [row[0] for row in results]
        
        if not product_ids:
            return {"items": [], "stats": {"total": 0, "available": 0, "in_rent": 0, "reserved": 0}, "date_filter_active": bool(date_from and date_to)}
        
        # Якщо вказані дати - перевіряємо доступність на конкретний період
        use_date_filter = date_from and date_to
        
        if use_date_filter:
            # Резерви на конкретний період (перетинання дат)
            reserved_result = db.execute(text("""
                SELECT oi.product_id, COALESCE(SUM(oi.quantity), 0) as reserved
                FROM order_items oi
                JOIN orders o ON oi.order_id = o.order_id
                WHERE oi.product_id IN :product_ids
                AND o.status IN ('processing', 'ready_for_issue', 'awaiting_customer', 'pending')
                AND o.rental_start_date <= :date_to
                AND o.rental_end_date >= :date_from
                GROUP BY oi.product_id
            """).bindparams(product_ids=tuple(product_ids) if len(product_ids) > 1 else (product_ids[0],)), 
            {"date_from": date_from, "date_to": date_to})
            reserved_dict = {row[0]: int(row[1]) for row in reserved_result}
            
            # В оренді на конкретний період
            in_rent_result = db.execute(text("""
                SELECT oi.product_id, COALESCE(SUM(oi.quantity), 0) as in_rent
                FROM order_items oi
                JOIN orders o ON oi.order_id = o.order_id
                WHERE oi.product_id IN :product_ids
                AND o.status IN ('issued', 'on_rent')
                AND o.rental_start_date <= :date_to
                AND o.rental_end_date >= :date_from
                GROUP BY oi.product_id
            """).bindparams(product_ids=tuple(product_ids) if len(product_ids) > 1 else (product_ids[0],)),
            {"date_from": date_from, "date_to": date_to})
            in_rent_dict = {row[0]: int(row[1]) for row in in_rent_result}
            
            # У кого в оренді на цей період
            who_has_result = db.execute(text("""
                SELECT 
                    oi.product_id, 
                    o.order_number, 
                    o.customer_name,
                    o.customer_phone,
                    o.rental_start_date,
                    o.rental_end_date,
                    oi.quantity,
                    o.status
                FROM order_items oi
                JOIN orders o ON oi.order_id = o.order_id
                WHERE oi.product_id IN :product_ids
                AND o.status IN ('processing', 'ready_for_issue', 'issued', 'on_rent', 'awaiting_customer', 'pending')
                AND o.rental_start_date <= :date_to
                AND o.rental_end_date >= :date_from
                ORDER BY o.rental_start_date
            """).bindparams(product_ids=tuple(product_ids) if len(product_ids) > 1 else (product_ids[0],)),
            {"date_from": date_from, "date_to": date_to})
        else:
            # Без дат - показуємо поточний стан: один запит замість трьох
            combined_result = db.execute(text("""
                SELECT 
                    oi.product_id,
                    SUM(CASE WHEN o.status IN ('processing', 'ready_for_issue', 'awaiting_customer', 'pending') THEN oi.quantity ELSE 0 END) as reserved,
                    SUM(CASE WHEN o.status IN ('issued', 'on_rent') THEN oi.quantity ELSE 0 END) as in_rent
                FROM order_items oi
                JOIN orders o ON oi.order_id = o.order_id
                WHERE oi.product_id IN :product_ids
                AND o.status IN ('processing', 'ready_for_issue', 'awaiting_customer', 'pending', 'issued', 'on_rent')
                AND o.rental_end_date >= CURDATE()
                GROUP BY oi.product_id
            """).bindparams(product_ids=tuple(product_ids) if len(product_ids) > 1 else (product_ids[0],)))
            reserved_dict = {}
            in_rent_dict = {}
            for row in combined_result:
                reserved_dict[row[0]] = int(row[1] or 0)
                in_rent_dict[row[0]] = int(row[2] or 0)
            
            who_has_result = db.execute(text("""
                SELECT 
                    oi.product_id, 
                    o.order_number, 
                    o.customer_name,
                    o.customer_phone,
                    o.rental_start_date,
                    o.rental_end_date,
                    oi.quantity,
                    o.status
                FROM order_items oi
                JOIN orders o ON oi.order_id = o.order_id
                WHERE oi.product_id IN :product_ids
                AND o.status IN ('processing', 'ready_for_issue', 'issued', 'on_rent', 'pending', 'awaiting_customer')
                ORDER BY o.rental_start_date
            """).bindparams(product_ids=tuple(product_ids) if len(product_ids) > 1 else (product_ids[0],)))
        
        who_has_dict = {}
        for row in who_has_result:
            pid = row[0]
            if pid not in who_has_dict:
                who_has_dict[pid] = []
            who_has_dict[pid].append({
                "order_number": row[1],
                "customer": row[2] or '',  # client_name
                "phone": row[3],  # client_phone
                "start_date": str(row[4]) if row[4] else None,
                "return_date": str(row[5]) if row[5] else None,
                "qty": row[6],
                "status": row[7]
            })
        
        # ========== ЧАСТКОВІ ПОВЕРНЕННЯ ==========
        # Товари що ще у клієнта (активні версії часткових повернень)
        partial_return_dict = {}
        try:
            partial_return_result = db.execute(text("""
                SELECT 
                    prvi.product_id,
                    prv.display_number,
                    prv.customer_name,
                    prv.customer_phone,
                    prv.rental_end_date,
                    prvi.qty,
                    DATEDIFF(CURDATE(), prv.rental_end_date) as days_overdue
                FROM partial_return_version_items prvi
                JOIN partial_return_versions prv ON prvi.version_id = prv.version_id
                WHERE prvi.product_id IN :product_ids
                AND prvi.status = 'pending'
                AND prv.status = 'active'
            """).bindparams(product_ids=tuple(product_ids) if len(product_ids) > 1 else (product_ids[0],)))
            
            for row in partial_return_result:
                pid = row[0]
                if pid not in partial_return_dict:
                    partial_return_dict[pid] = {"qty": 0, "orders": []}
                partial_return_dict[pid]["qty"] += row[5]
                partial_return_dict[pid]["orders"].append({
                    "order_number": row[1],
                    "customer": row[2] or '',
                    "phone": row[3],
                    "return_date": str(row[4]) if row[4] else None,
                    "qty": row[5],
                    "days_overdue": row[6] or 0,
                    "status": "partial_return"
                })
        except Exception as e:
            # Таблиці можуть не існувати
            pass
        # ========== КІНЕЦЬ ЧАСТКОВИХ ПОВЕРНЕНЬ ==========
        
        # Тепер рахуємо реальні дані обробки з product_damage_history
        processing_dict = {}  # product_id -> {wash: N, restoration: N, laundry: N}
        try:
            processing_rows = db.execute(text("""
                SELECT product_id, processing_type, 
                       SUM(COALESCE(qty, 1) - COALESCE(processed_qty, 0)) as active_qty
                FROM product_damage_history
                WHERE processing_type IN ('wash', 'restoration', 'laundry', 'washing')
                AND COALESCE(processing_status, '') NOT IN ('completed', 'returned_to_stock', 'hidden', 'deleted')
                GROUP BY product_id, processing_type
            """)).fetchall()
            for pr in processing_rows:
                pid = pr[0]
                ptype = pr[1]
                pqty = int(pr[2] or 0)
                if pqty <= 0:
                    continue
                if pid not in processing_dict:
                    processing_dict[pid] = {"wash": 0, "restoration": 0, "laundry": 0}
                if ptype in ('wash', 'washing'):
                    processing_dict[pid]["wash"] += pqty
                elif ptype == 'restoration':
                    processing_dict[pid]["restoration"] += pqty
                elif ptype == 'laundry':
                    processing_dict[pid]["laundry"] += pqty
        except Exception:
            pass
        
        # Формуємо результат
        items = []
        stats = {
            "total": 0, 
            "available": 0, 
            "in_rent": 0, 
            "reserved": 0,
            "on_wash": 0,
            "on_restoration": 0,
            "on_laundry": 0
        }
        
        for row in results:
            product_id = row[0]
            total_qty = row[8] or 0
            reserved_qty = reserved_dict.get(product_id, 0)
            in_rent_qty = in_rent_dict.get(product_id, 0)
            
            # ✅ Додаємо товари з часткових повернень до "в оренді"
            partial_return_info = partial_return_dict.get(product_id, {"qty": 0, "orders": []})
            partial_return_qty = partial_return_info["qty"]
            in_rent_qty += partial_return_qty  # Рахуємо як "в оренді"
            
            # Отримуємо реальні кількості з product_damage_history
            product_state = row[18] if len(row) > 18 else None
            family_id = row[21] if len(row) > 21 else None
            
            # Кількість на обробці з реальних даних кабінету шкоди (SSOT)
            proc = processing_dict.get(product_id, {"wash": 0, "restoration": 0, "laundry": 0})
            on_wash_qty = proc["wash"]
            on_restoration_qty = proc["restoration"]
            on_laundry_qty = proc["laundry"]
            
            # Доступно = всього - резерв - в оренді - на обробці (з PDH, а не frozen_quantity)
            total_processing = on_wash_qty + on_restoration_qty + on_laundry_qty
            available_qty = max(0, total_qty - reserved_qty - in_rent_qty - total_processing)
            
            # Stats
            stats["total"] += total_qty
            stats["available"] += available_qty
            stats["in_rent"] += in_rent_qty
            stats["reserved"] += reserved_qty
            stats["on_wash"] += on_wash_qty
            stats["on_restoration"] += on_restoration_qty
            stats["on_laundry"] += on_laundry_qty
            
            # Availability filter
            if availability == 'available' and available_qty == 0:
                continue
            if availability == 'in_rent' and in_rent_qty == 0:
                continue
            if availability == 'reserved' and reserved_qty == 0:
                continue
            if availability == 'on_wash' and on_wash_qty == 0:
                continue
            if availability == 'on_restoration' and on_restoration_qty == 0:
                continue
            if availability == 'on_laundry' and on_laundry_qty == 0:
                continue
            
            # Конфлікти на період - додаємо часткові повернення до who_has
            conflicts = who_has_dict.get(product_id, [])
            # ✅ Додаємо записи про часткові повернення
            for pr_order in partial_return_info["orders"]:
                conflicts.append(pr_order)
            has_conflict = use_date_filter and (reserved_qty > 0 or in_rent_qty > 0)
            
            items.append({
                "product_id": product_id,
                "sku": row[1],
                "name": row[2],
                "price": float(row[3]) if row[3] else 0.0,
                "rental_price": float(row[4]) if row[4] else 0.0,
                "image": normalize_image_url(row[5]),
                "category": row[6],
                "subcategory": row[7],
                "total": total_qty,
                "available": available_qty,
                "reserved": reserved_qty,
                "in_rent": in_rent_qty,
                "on_wash": on_wash_qty,
                "on_restoration": on_restoration_qty,
                "on_laundry": on_laundry_qty,
                "has_conflict": has_conflict,
                "location": {
                    "zone": row[9] or "",
                    "aisle": row[10] or "",
                    "shelf": row[11] or ""
                },
                "color": row[12],
                "material": row[13],
                "size": row[14],
                "cleaning_status": row[15],
                "product_state": product_state,  # Тепер з products.state
                "description": row[17],
                "who_has": conflicts,
                "family_id": family_id
            })
        
        return {
            "items": items, 
            "stats": stats,
            "date_filter_active": use_date_filter,
            "date_from": date_from,
            "date_to": date_to
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Помилка: {str(e)}")


@router.get("")
async def get_catalog_items(
    category: str = None,
    search: str = None,
    limit: int = 1000,
    include_reservations: bool = False,
    db: Session = Depends(get_rh_db)
):
    """
    Отримати каталог товарів (оптимізовано)
    ✅ MIGRATED: Using products + categories from RentalHub DB
    """
    sql = """
        SELECT 
            p.product_id, p.sku, p.name, p.price, p.image_url, p.status,
            p.category_id, p.category_name, 
            p.subcategory_id, p.subcategory_name,
            p.quantity, p.zone, p.aisle, p.shelf,
            p.family_id, pf.name as family_name, pf.description as family_description,
            p.frozen_quantity, p.in_laundry, p.state
        FROM products p
        LEFT JOIN product_families pf ON p.family_id = pf.id
        WHERE p.status = 1
    """
    
    params = {}
    
    if search:
        sql += " AND (p.name LIKE :search OR p.sku LIKE :search)"
        params['search'] = f"%{search}%"
    
    if category:
        sql += " AND (p.category_name LIKE :category OR p.subcategory_name LIKE :category)"
        params['category'] = f"%{category}%"
    
    sql += f" ORDER BY p.product_id DESC LIMIT {limit}"
    
    result = db.execute(text(sql), params)
    
    # Оптимізація: отримати статистику для всіх товарів одним запитом
    reserved_dict = {}
    in_rent_dict = {}
    in_restore_dict = {}
    
    # Реальні дані обробки з product_damage_history
    processing_dict = {}
    try:
        proc_rows = db.execute(text("""
            SELECT product_id, processing_type,
                   SUM(COALESCE(qty, 1) - COALESCE(processed_qty, 0)) as active_qty
            FROM product_damage_history
            WHERE processing_type IN ('wash', 'restoration', 'laundry', 'washing')
            AND COALESCE(processing_status, '') NOT IN ('completed', 'returned_to_stock', 'hidden', 'deleted')
            GROUP BY product_id, processing_type
        """)).fetchall()
        for pr in proc_rows:
            pid, ptype, pqty = pr[0], pr[1], int(pr[2] or 0)
            if pqty <= 0:
                continue
            if pid not in processing_dict:
                processing_dict[pid] = {"wash": 0, "restoration": 0, "laundry": 0}
            if ptype in ('wash', 'washing'):
                processing_dict[pid]["wash"] += pqty
            elif ptype == 'restoration':
                processing_dict[pid]["restoration"] += pqty
            elif ptype == 'laundry':
                processing_dict[pid]["laundry"] += pqty
    except Exception:
        pass
    
    if include_reservations:
        # Об'єднаний запит: резерви + оренда за один раз
        combined_result = db.execute(text("""
            SELECT 
                oi.product_id,
                SUM(CASE WHEN o.status IN ('processing', 'ready_for_issue', 'awaiting_customer', 'pending') THEN oi.quantity ELSE 0 END) as reserved,
                SUM(CASE WHEN o.status IN ('issued', 'on_rent') THEN oi.quantity ELSE 0 END) as in_rent
            FROM order_items oi
            JOIN orders o ON oi.order_id = o.order_id
            WHERE o.status IN ('processing', 'ready_for_issue', 'awaiting_customer', 'pending', 'issued', 'on_rent')
            AND o.rental_end_date >= CURDATE()
            GROUP BY oi.product_id
        """))
        for row in combined_result:
            reserved_dict[row[0]] = int(row[1] or 0)
            in_rent_dict[row[0]] = int(row[2] or 0)
        
        # На реставрації - тепер з product_damage_history (єдине джерело)
        in_restore_result = db.execute(text("""
            SELECT pdh.product_id, SUM(COALESCE(pdh.qty, 1) - COALESCE(pdh.processed_qty, 0)) as restore_qty
            FROM product_damage_history pdh
            WHERE pdh.processing_type = 'restoration'
            AND COALESCE(pdh.processing_status, '') NOT IN ('completed', 'returned_to_stock', 'hidden', 'deleted')
            AND (COALESCE(pdh.qty, 1) - COALESCE(pdh.processed_qty, 0)) > 0
            GROUP BY pdh.product_id
        """))
        in_restore_dict = {row[0]: int(row[1]) for row in in_restore_result}
    
    items = []
    for row in result:
        family_id = row[14] if len(row) > 14 else None
        family_name = row[15] if len(row) > 15 else None
        family_description = row[16] if len(row) > 16 else None
        product_state = row[19] if len(row) > 19 else None
        
        normalized_image = normalize_image_url(row[4])
        product_id = row[0]
        total_qty = row[10] or 0
        
        # Отримати статистику з pre-loaded словників
        reserved_qty = reserved_dict.get(product_id, 0)
        in_rent_qty = in_rent_dict.get(product_id, 0)
        in_restore_qty = in_restore_dict.get(product_id, 0)
        
        # Визначити on_wash/restoration/laundry з реальних даних кабінету шкоди (SSOT)
        proc = processing_dict.get(product_id, {"wash": 0, "restoration": 0, "laundry": 0})
        on_wash_qty = proc["wash"]
        on_restoration_qty = proc["restoration"]
        on_laundry_qty = proc["laundry"]
        
        # Доступно = всього - резерв - в оренді - на обробці (з PDH)
        total_processing = on_wash_qty + on_restoration_qty + on_laundry_qty
        available_qty = max(0, total_qty - reserved_qty - in_rent_qty - total_processing)
        
        items.append({
            "id": row[0],
            "product_id": row[0],
            "sku": row[1],
            "name": row[2],
            "price": float(row[3]) if row[3] else 0.0,
            "damage_cost": float(row[3]) if row[3] else 0.0,  # EAN/збиток
            "image": normalized_image,
            "photo": normalized_image,
            "cover": normalized_image,
            "status": row[5],
            "state": "ok" if available_qty > 0 else "unavailable",
            "product_state": product_state,
            "cat": row[7],  # Frontend очікує cat
            "category": row[7],
            "category_id": row[6],
            "category_name": row[7],
            "subcategory_id": row[8],
            "subcategory": row[9],
            "subcategory_name": row[9],
            "quantity": row[10] or 0,
            "total": total_qty,
            "available": available_qty,
            "reserved": reserved_qty,
            "in_rent": in_rent_qty,
            "rented": in_rent_qty,
            "in_restore": in_restore_qty,
            "on_wash": on_wash_qty,
            "on_restoration": on_restoration_qty,
            "on_laundry": on_laundry_qty,
            "frozen_quantity": total_processing,
            "in_laundry": on_laundry_qty,
            "location": {
                "zone": row[11] or "",
                "aisle": row[12] or "",
                "shelf": row[13] or "",
                "state": "shelf"
            },
            "cleaning": {
                "status": "clean",  # За замовчуванням
                "date": None
            },
            "barcode": row[1] or "",  # SKU як barcode
            "barcodes": [row[1]] if row[1] else [],  # Список штрихкодів
            "who_has": [],  # TODO: список активних замовлень
            "due_back": [],  # TODO: список замовлень на повернення
            "variants": [],  # TODO: варіанти товару
            # Family Groups (набори)
            "family_id": family_id,
            "family": {
                "id": family_id,
                "name": family_name,
                "description": family_description
            } if family_id else None
        })
    
    return items



@router.get("/debug/reservations/{product_id}")
async def debug_reservations(
    product_id: int,
    db: Session = Depends(get_rh_db)
):
    """Debug endpoint to check reservations for a specific product"""
    
    # Check order_items for this product
    order_items = db.execute(text("""
        SELECT oi.id, oi.order_id, oi.product_id, oi.quantity, 
               o.order_number, o.status, o.rental_start_date, o.rental_end_date
        FROM order_items oi
        JOIN orders o ON oi.order_id = o.order_id
        WHERE oi.product_id = :product_id
        ORDER BY o.created_at DESC
        LIMIT 20
    """), {"product_id": product_id}).fetchall()
    
    items_list = []
    for row in order_items:
        items_list.append({
            "item_id": row[0],
            "order_id": row[1],
            "product_id": row[2],
            "quantity": row[3],
            "order_number": row[4],
            "status": row[5],
            "rental_start": str(row[6]) if row[6] else None,
            "rental_end": str(row[7]) if row[7] else None
        })
    
    # Check reserved count
    reserved = db.execute(text("""
        SELECT COALESCE(SUM(oi.quantity), 0) as reserved
        FROM order_items oi
        JOIN orders o ON oi.order_id = o.order_id
        WHERE oi.product_id = :product_id
        AND o.status IN ('processing', 'ready_for_issue', 'awaiting_customer', 'pending')
        AND o.rental_end_date >= CURDATE()
    """), {"product_id": product_id}).scalar()
    
    return {
        "product_id": product_id,
        "order_items_found": len(items_list),
        "items": items_list,
        "reserved_count": int(reserved) if reserved else 0
    }


@router.get("/families/{family_id}/products")
async def get_family_products(
    family_id: int,
    db: Session = Depends(get_rh_db)
):
    """
    Отримати всі товари з набору (Family Group)
    """
    try:
        result = db.execute(text("""
            SELECT p.product_id, p.sku, p.name, p.price, p.image_url, 
                   p.quantity, p.zone, p.aisle, p.shelf
            FROM products p
            WHERE p.family_id = :family_id
            ORDER BY p.sku
        """), {"family_id": family_id})
        
        products = []
        for row in result:
            products.append({
                "product_id": row[0],
                "sku": row[1],
                "name": row[2],
                "price": float(row[3]) if row[3] else 0.0,
                "image": row[4],
                "quantity": row[5] or 0,
                "location": {
                    "zone": row[6],
                    "aisle": row[7],
                    "shelf": row[8]
                }
            })
        
        return products
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Помилка: {str(e)}"
        )





@router.get("/products-lite")
async def get_products_lite(
    search: str = None,
    category: str = None,
    limit: int = 10000,
    db: Session = Depends(get_rh_db)
):
    """
    Легкий ендпоінт для FamiliesManager - мінімум полів, максимум швидкості
    """
    sql = """
        SELECT 
            p.product_id, p.sku, p.name, p.image_url,
            p.category_name, p.family_id, p.color, p.quantity
        FROM products p
        WHERE p.status = 1
    """
    params = {}
    
    if search:
        sql += " AND (p.name LIKE :search OR p.sku LIKE :search)"
        params['search'] = f"%{search}%"
    
    if category:
        sql += " AND (p.category_name LIKE :category OR p.subcategory_name LIKE :category)"
        params['category'] = f"%{category}%"
    
    sql += f" ORDER BY p.product_id DESC LIMIT {limit}"
    
    result = db.execute(text(sql), params).fetchall()
    
    items = []
    for row in result:
        img = normalize_image_url(row[3])
        items.append({
            "product_id": row[0],
            "sku": row[1],
            "name": row[2],
            "image": img,
            "cover": img,
            "category": row[4],
            "category_name": row[4],
            "family_id": row[5],
            "color": row[6],
            "quantity": row[7] or 0
        })
    
    return items


@router.get("/families")
async def get_all_families(
    db: Session = Depends(get_rh_db)
):
    """
    Отримати всі набори з їх товарами (оптимізовано - один JOIN замість N+1)
    """
    try:
        # Один запит замість 1 + N окремих запитів
        result = db.execute(text("""
            SELECT 
                pf.id as family_id,
                pf.name as family_name,
                pf.description as family_description,
                p.product_id,
                p.sku,
                p.name as product_name,
                p.image_url,
                p.color,
                p.material,
                p.rental_price,
                p.price,
                p.quantity,
                p.category_name,
                p.family_id as product_family_id
            FROM product_families pf
            LEFT JOIN products p ON p.family_id = pf.id AND p.status = 1
            ORDER BY pf.name, p.sku
        """)).fetchall()
        
        # Групуємо результати в Python
        families_map = {}
        for row in result:
            fid = row[0]
            if fid not in families_map:
                families_map[fid] = {
                    "id": fid,
                    "name": row[1],
                    "description": row[2],
                    "products": []
                }
            # Якщо є продукт (LEFT JOIN може дати NULL)
            if row[3] is not None:
                img = normalize_image_url(row[6])
                families_map[fid]["products"].append({
                    "product_id": row[3],
                    "sku": row[4],
                    "name": row[5],
                    "cover": img,
                    "image": img,
                    "image_url": img,
                    "color": row[7],
                    "material": row[8],
                    "rental_price": float(row[9]) if row[9] else 0,
                    "price": float(row[10]) if row[10] else 0,
                    "quantity": row[11] or 0,
                    "category_name": row[12],
                    "family_id": row[13]
                })
        
        return list(families_map.values())
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Помилка: {str(e)}"
        )


@router.post("/families")
async def create_family(
    data: dict,
    db: Session = Depends(get_rh_db)
):
    """
    Створити новий набір
    """
    try:
        result = db.execute(text("""
            INSERT INTO product_families (name, description)
            VALUES (:name, :description)
        """), {
            "name": data.get("name"),
            "description": data.get("description", "")
        })
        
        db.commit()
        
        return {
            "success": True,
            "family_id": result.lastrowid,
            "message": "Набір створено"
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Помилка: {str(e)}"
        )


@router.put("/families/{family_id}")
async def update_family(
    family_id: int,
    data: dict,
    db: Session = Depends(get_rh_db)
):
    """
    Оновити назву/опис набору
    """
    try:
        name = data.get("name")
        description = data.get("description", "")
        
        if not name:
            raise HTTPException(status_code=400, detail="Назва обов'язкова")
        
        db.execute(text("""
            UPDATE product_families 
            SET name = :name, description = :description
            WHERE id = :family_id
        """), {
            "family_id": family_id,
            "name": name,
            "description": description
        })
        
        db.commit()
        
        return {
            "success": True,
            "message": "Набір оновлено"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Помилка: {str(e)}"
        )


@router.post("/families/{family_id}/assign")
async def assign_products_to_family(
    family_id: int,
    data: dict,
    db: Session = Depends(get_rh_db)
):
    """
    Прив'язати товари до набору (batch операції)
    """
    try:
        product_ids = data.get("product_ids", [])
        if not product_ids:
            return {"success": True, "message": "Немає товарів для прив'язки", "product_ids": None}
        
        # Batch UPDATE - один запит замість циклу
        placeholders = ','.join(str(int(pid)) for pid in product_ids)
        db.execute(text(f"""
            UPDATE products SET family_id = :family_id 
            WHERE product_id IN ({placeholders})
        """), {"family_id": family_id})
        
        # Отримати всі product_ids для цієї family
        all_products = db.execute(text("""
            SELECT product_id FROM products WHERE family_id = :family_id ORDER BY product_id
        """), {"family_id": family_id}).fetchall()
        
        product_ids_str = ','.join(str(p[0]) for p in all_products) if all_products else None
        
        db.execute(text("""
            UPDATE product_families SET product_ids = :product_ids WHERE id = :family_id
        """), {"product_ids": product_ids_str, "family_id": family_id})
        
        # Оновити product_family_items - batch операція
        db.execute(text("DELETE FROM product_family_items WHERE family_id = :family_id"), {"family_id": family_id})
        if all_products:
            values = ','.join(f"({family_id},{p[0]})" for p in all_products)
            db.execute(text(f"""
                INSERT INTO product_family_items (family_id, product_id) VALUES {values}
            """))
        
        db.commit()
        
        return {
            "success": True,
            "message": f"Прив'язано {len(product_ids)} товарів",
            "product_ids": product_ids_str
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Помилка: {str(e)}"
        )


@router.post("/products/{product_id}/remove-family")
async def remove_product_from_family(
    product_id: int,
    db: Session = Depends(get_rh_db)
):
    """
    Видалити товар з набору
    """
    try:
        db.execute(text("""
            UPDATE products SET family_id = NULL WHERE product_id = :product_id
        """), {"product_id": product_id})
        
        db.commit()
        
        return {
            "success": True,
            "message": "Товар видалено з набору"
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Помилка: {str(e)}"
        )


@router.delete("/families/{family_id}")
async def delete_family(
    family_id: int,
    db: Session = Depends(get_rh_db)
):
    """
    Видалити набір
    """
    try:
        # Спочатку відв'язати всі товари
        db.execute(text("""
            UPDATE products SET family_id = NULL WHERE family_id = :family_id
        """), {"family_id": family_id})
        
        # Видалити набір
        db.execute(text("""
            DELETE FROM product_families WHERE id = :family_id
        """), {"family_id": family_id})
        
        db.commit()
        
        return {
            "success": True,
            "message": "Набір видалено"
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Помилка: {str(e)}"
        )

@router.get("/{product_id}")
async def get_product_detail(
    product_id: int,
    db: Session = Depends(get_rh_db)
):
    """
    Детальна інформація про товар
    ✅ MIGRATED: Using RentalHub DB
    """
    result = db.execute(text("""
        SELECT 
            p.product_id, p.sku, p.name, p.description, p.price, 
            p.image_url, p.status,
            p.category_id, p.category_name, p.subcategory_id, p.subcategory_name,
            p.quantity, p.zone, p.aisle, p.shelf,
            p.cleaning_status, p.product_state
        FROM products p
        WHERE p.product_id = :product_id
    """), {"product_id": product_id})
    
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Product not found")
    
    # Get product history
    history_result = db.execute(text("""
        SELECT action, actor, details, created_at
        FROM product_history
        WHERE product_id = :product_id
        ORDER BY created_at DESC
        LIMIT 10
    """), {"product_id": product_id})
    
    history = []
    for h_row in history_result:
        history.append({
            "event_type": h_row[0],
            "changed_by": h_row[1],
            "notes": h_row[2],
            "event_date": h_row[3].isoformat() if h_row[3] else None
        })
    
    return {
        "product_id": row[0],
        "sku": row[1],
        "name": row[2],
        "description": row[3],
        "price": float(row[4]) if row[4] else 0.0,
        "image": row[5],
        "status": row[6],
        "category_id": row[7],
        "category": row[8],
        "category_name": row[8],
        "subcategory_id": row[9],
        "subcategory": row[10],
        "subcategory_name": row[10],
        "quantity": row[11] or 0,
        "inventory": {
            "quantity": row[11] or 0,
            "zone": row[12],
            "aisle": row[13],
            "shelf": row[14],
            "cleaning_status": row[15],
            "product_state": row[16]
        },
        "history": history
    }

@router.put("/{product_id}")
async def update_product(
    product_id: int,
    data: dict,
    db: Session = Depends(get_rh_db)
):
    """
    Оновити товар
    ✅ MIGRATED: Using RentalHub DB
    """
    # Check if exists
    result = db.execute(text("SELECT product_id FROM products WHERE product_id = :id"), {"id": product_id})
    if not result.fetchone():
        raise HTTPException(status_code=404, detail="Product not found")
    
    # Build update query
    set_clauses = []
    params = {"product_id": product_id}
    
    if 'name' in data:
        set_clauses.append("name = :name")
        params['name'] = data['name']
    if 'price' in data:
        set_clauses.append("price = :price")
        params['price'] = data['price']
    if 'quantity' in data:
        set_clauses.append("quantity = :quantity")
        params['quantity'] = data['quantity']
    if 'status' in data:
        set_clauses.append("status = :status")
        params['status'] = data['status']
    if 'description' in data:
        set_clauses.append("description = :description")
        params['description'] = data['description']
    
    if set_clauses:
        sql = f"UPDATE products SET {', '.join(set_clauses)} WHERE product_id = :product_id"
        db.execute(text(sql), params)
        
        # Log to history
        db.execute(text("""
            INSERT INTO product_history (product_id, event_type, event_date, notes, changed_by)
            VALUES (:product_id, 'updated', NOW(), :notes, :user)
        """), {
            "product_id": product_id,
            "notes": f"Updated: {', '.join(data.keys())}",
            "user": data.get('updated_by', 'system')
        })
        
        db.commit()
    
    return {"message": "Product updated successfully"}

@router.get("/check-availability/{sku}")
async def check_availability(
    sku: str,
    db: Session = Depends(get_rh_db)
):
    """
    Перевірити доступність товару
    ✅ MIGRATED: Using RentalHub DB
    """
    result = db.execute(text("""
        SELECT p.product_id, p.name, p.quantity, p.quantity as inventory_qty
        FROM products p
        WHERE p.sku = :sku AND p.status = 1
    """), {"sku": sku})
    
    row = result.fetchone()
    if not row:
        return {
            "available": False,
            "message": "Product not found or inactive"
        }
    
    quantity = row[3] if row[3] is not None else row[2]
    
    return {
        "available": quantity > 0,
        "product_id": row[0],
        "name": row[1],
        "quantity": quantity,
        "message": f"Available: {quantity} units" if quantity > 0 else "Out of stock"
    }
