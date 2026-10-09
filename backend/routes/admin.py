"""
Admin Panel API - Адмін-панель
Управління користувачами та категоріями
"""
from fastapi import APIRouter, HTTPException, Depends, Header
from sqlalchemy.orm import Session
from sqlalchemy import text
from database_rentalhub import get_rh_db
from datetime import datetime
import bcrypt
import jwt
import os

router = APIRouter(prefix="/api/admin", tags=["admin"])

# JWT Configuration
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"

def get_current_user(authorization: str = Header(None)):
    """Extract user info from JWT token"""
    if not authorization or not authorization.startswith('Bearer '):
        print("[Admin] No authorization header")
        return None
    
    try:
        token = authorization.split(' ')[1]
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user = {
            'email': payload.get('email'),
            'username': payload.get('username') or payload.get('sub'),
            'user_id': payload.get('user_id'),
            'role': payload.get('role')
        }
        print(f"[Admin] User from token: {user.get('email')}, role: {user.get('role')}")
        return user
    except jwt.ExpiredSignatureError:
        print("[Admin] Token expired")
        return None
    except jwt.InvalidTokenError as e:
        print(f"[Admin] Invalid token: {e}")
        return None
    except Exception as e:
        print(f"[Admin] Token decode error: {e}")
        return None

def require_admin(authorization: str = Header(None)):
    """Require admin role"""
    user = get_current_user(authorization)
    if not user:
        print("[Admin] No user found from token")
        raise HTTPException(status_code=403, detail="Доступ тільки для адміністраторів")
    if user.get('role') != 'admin':
        print(f"[Admin] User {user.get('email')} has role {user.get('role')}, not admin")
        raise HTTPException(status_code=403, detail="Доступ тільки для адміністраторів")
    return user


# ============= КОРИСТУВАЧІ =============

@router.get("/users")
async def get_users(
    authorization: str = Header(None),
    rh_db: Session = Depends(get_rh_db)
):
    """Отримати всіх користувачів (тільки для адмінів)"""
    require_admin(authorization)
    
    try:
        query = text("""
            SELECT 
                user_id, username, email, firstname, lastname, 
                role, is_active, created_at, last_login
            FROM users
            ORDER BY created_at DESC
        """)
        
        results = rh_db.execute(query).fetchall()
        
        users = []
        for row in results:
            users.append({
                'user_id': row[0],
                'username': row[1],
                'email': row[2],
                'firstname': row[3],
                'lastname': row[4],
                'role': row[5],
                'is_active': bool(row[6]),
                'created_at': row[7].isoformat() if row[7] else None,
                'last_login': row[8].isoformat() if row[8] else None
            })
        
        return users
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Помилка: {str(e)}")


@router.get("/staff")
async def get_staff_by_role(
    role: str = None,
    rh_db: Session = Depends(get_rh_db)
):
    """
    Отримати активних співробітників за ролями (публічний endpoint)
    
    Query params:
    - role: filter by role (manager, requisitor, admin, office_manager)
    
    Returns staff grouped by role if no role specified
    """
    try:
        if role:
            query = text("""
                SELECT user_id, username, email, firstname, lastname, role
                FROM users
                WHERE role = :role AND is_active = 1
                ORDER BY firstname
            """)
            results = rh_db.execute(query, {'role': role}).fetchall()
        else:
            query = text("""
                SELECT user_id, username, email, firstname, lastname, role
                FROM users
                WHERE is_active = 1
                ORDER BY role, firstname
            """)
            results = rh_db.execute(query).fetchall()
        
        staff = []
        for row in results:
            staff.append({
                'user_id': row[0],
                'username': row[1],
                'email': row[2],
                'firstname': row[3],
                'lastname': row[4],
                'full_name': f"{row[3] or ''} {row[4] or ''}".strip(),
                'role': row[5]
            })
        
        # Групуємо за ролями якщо не вказано конкретну роль
        if not role:
            grouped = {
                'managers': [s for s in staff if s['role'] in ('manager', 'admin', 'office_manager')],
                'requisitors': [s for s in staff if s['role'] == 'requisitor'],
                'all': staff
            }
            return grouped
        
        return staff
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Помилка: {str(e)}")


@router.post("/users")
async def create_user(
    data: dict,
    authorization: str = Header(None),
    rh_db: Session = Depends(get_rh_db)
):
    """Створити нового користувача"""
    require_admin(authorization)
    
    try:
        username = data.get('username')
        email = data.get('email')
        password = data.get('password', 'temp123')
        firstname = data.get('firstname')
        lastname = data.get('lastname')
        role = data.get('role', 'requisitor')
        
        if not username or not email:
            raise HTTPException(status_code=400, detail="Username та email обов'язкові")
        
        # Хешуємо пароль
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        query = text("""
            INSERT INTO users (username, email, password_hash, firstname, lastname, role)
            VALUES (:username, :email, :password_hash, :firstname, :lastname, :role)
        """)
        
        rh_db.execute(query, {
            'username': username,
            'email': email,
            'password_hash': password_hash,
            'firstname': firstname,
            'lastname': lastname,
            'role': role
        })
        
        rh_db.commit()
        
        return {
            'success': True,
            'message': f'Користувача {username} створено'
        }
        
    except Exception as e:
        rh_db.rollback()
        raise HTTPException(status_code=500, detail=f"Помилка: {str(e)}")


@router.put("/users/{user_id}")
async def update_user(
    user_id: int,
    data: dict,
    authorization: str = Header(None),
    rh_db: Session = Depends(get_rh_db)
):
    """Оновити користувача"""
    require_admin(authorization)
    
    try:
        updates = []
        params = {'user_id': user_id}
        
        if 'username' in data:
            updates.append("username = :username")
            params['username'] = data['username']
        
        if 'email' in data:
            updates.append("email = :email")
            params['email'] = data['email']
        
        if 'firstname' in data:
            updates.append("firstname = :firstname")
            params['firstname'] = data['firstname']
        
        if 'lastname' in data:
            updates.append("lastname = :lastname")
            params['lastname'] = data['lastname']
        
        if 'role' in data:
            updates.append("role = :role")
            params['role'] = data['role']
        
        if 'is_active' in data:
            updates.append("is_active = :is_active")
            params['is_active'] = data['is_active']
        
        if 'password' in data:
            password_hash = bcrypt.hashpw(data['password'].encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            updates.append("password_hash = :password_hash")
            params['password_hash'] = password_hash
        
        if not updates:
            raise HTTPException(status_code=400, detail="Немає даних для оновлення")
        
        query = text(f"UPDATE users SET {', '.join(updates)} WHERE user_id = :user_id")
        rh_db.execute(query, params)
        rh_db.commit()
        
        return {
            'success': True,
            'message': 'Користувача оновлено'
        }
        
    except Exception as e:
        rh_db.rollback()
        raise HTTPException(status_code=500, detail=f"Помилка: {str(e)}")


@router.post("/users/{user_id}/reset-password")
async def reset_user_password(
    user_id: int,
    data: dict,
    authorization: str = Header(None),
    rh_db: Session = Depends(get_rh_db)
):
    """Скинути пароль користувача (тільки для адмінів)"""
    require_admin(authorization)
    
    new_password = data.get('password')
    if not new_password or len(new_password) < 4:
        raise HTTPException(status_code=400, detail="Пароль має бути мінімум 4 символи")
    
    try:
        # Хешуємо новий пароль
        password_hash = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        query = text("UPDATE users SET password_hash = :password_hash WHERE user_id = :user_id")
        result = rh_db.execute(query, {'password_hash': password_hash, 'user_id': user_id})
        rh_db.commit()
        
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Користувача не знайдено")
        
        return {
            'success': True,
            'message': 'Пароль успішно змінено'
        }
        
    except HTTPException:
        raise
    except Exception as e:
        rh_db.rollback()
        raise HTTPException(status_code=500, detail=f"Помилка: {str(e)}")


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    authorization: str = Header(None),
    rh_db: Session = Depends(get_rh_db)
):
    """Видалити користувача"""
    admin = require_admin(authorization)
    
    # Не можна видалити себе
    if admin.get('user_id') == user_id:
        raise HTTPException(status_code=400, detail="Не можна видалити свій власний акаунт")
    
    try:
        query = text("DELETE FROM users WHERE user_id = :user_id")
        result = rh_db.execute(query, {'user_id': user_id})
        rh_db.commit()
        
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Користувача не знайдено")
        
        return {
            'success': True,
            'message': 'Користувача видалено'
        }
        
    except Exception as e:
        rh_db.rollback()
        raise HTTPException(status_code=500, detail=f"Помилка: {str(e)}")


# ============= КАТЕГОРІЇ =============

@router.get("/categories")
async def get_categories(
    authorization: str = Header(None),
    rh_db: Session = Depends(get_rh_db)
):
    """
    Отримати всі категорії (використовує ту саму логіку що і audit/categories)
    ДЖЕРЕЛО ПРАВДИ: /api/audit/categories
    """
    require_admin(authorization)
    
    try:
        # ✅ Використовуємо ту саму логіку що і в audit/categories (джерело правди)
        
        # 1. Головні категорії (parent_id = 0)
        main_categories_query = rh_db.execute(text("""
            SELECT DISTINCT name, category_id, description, sort_order, is_active, created_at
            FROM categories
            WHERE parent_id = 0
            ORDER BY name
        """))
        
        main_categories_list = [
            {
                'category_id': row[1],
                'name': row[0],
                'parent_id': 0,
                'description': row[2],
                'sort_order': row[3] or 0,
                'is_active': bool(row[4]) if row[4] is not None else True,
                'created_at': row[5].isoformat() if row[5] else None,
                'subcategories_count': 0  # Буде заповнено нижче
            }
            for row in main_categories_query if row[0]
        ]
        
        # 2. Підкатегорії
        if main_categories_list:
            main_cat_ids = [cat['category_id'] for cat in main_categories_list]
            all_subcategories_query = rh_db.execute(text("""
                SELECT parent_id, category_id, name, description, sort_order, is_active, created_at
                FROM categories
                WHERE parent_id IN :parent_ids
                ORDER BY parent_id, name
            """), {"parent_ids": tuple(main_cat_ids)})
            
            # Рахуємо підкатегорії для кожної головної
            subcategories_count = {}
            all_subcategories = []
            
            for row in all_subcategories_query:
                parent_id = row[0]
                subcategories_count[parent_id] = subcategories_count.get(parent_id, 0) + 1
                
                all_subcategories.append({
                    'category_id': row[1],
                    'name': row[2],
                    'parent_id': parent_id,
                    'description': row[3],
                    'sort_order': row[4] or 0,
                    'is_active': bool(row[5]) if row[5] is not None else True,
                    'created_at': row[6].isoformat() if row[6] else None
                })
            
            # Оновлюємо кількість підкатегорій
            for cat in main_categories_list:
                cat['subcategories_count'] = subcategories_count.get(cat['category_id'], 0)
            
            # Повертаємо головні категорії + підкатегорії разом
            return main_categories_list + all_subcategories
        
        return main_categories_list
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Помилка: {str(e)}")


@router.post("/categories")
async def create_category(
    data: dict,
    authorization: str = Header(None),
    rh_db: Session = Depends(get_rh_db)
):
    """Створити нову категорію та синхронізувати з OpenCart"""
    require_admin(authorization)
    
    try:
        name = data.get('name')
        parent_id = data.get('parent_id')
        description = data.get('description', '')
        sort_order = data.get('sort_order', 0)
        
        if not name:
            raise HTTPException(status_code=400, detail="Назва категорії обов'язкова")
        
        # Створюємо в RentalHub
        query = text("""
            INSERT INTO categories (name, parent_id, description, sort_order)
            VALUES (:name, :parent_id, :description, :sort_order)
        """)
        
        rh_db.execute(query, {
            'name': name,
            'parent_id': parent_id,
            'description': description,
            'sort_order': sort_order
        })
        
        rh_db.commit()
        
        # Отримуємо новий ID
        new_id = rh_db.execute(text("SELECT LAST_INSERT_ID()")).fetchone()[0]
        
        # Синхронізація з OpenCart
        try:
            from database import get_db
            oc_db = next(get_db())
            
            # Знаходимо OpenCart parent_id
            oc_parent_id = 0
            if parent_id:
                parent_query = text("SELECT category_id FROM categories WHERE category_id = :id")
                parent_result = rh_db.execute(parent_query, {'id': parent_id}).fetchone()
                if parent_result:
                    oc_parent_id = parent_result[0]
            
            # Створюємо в oc_category
            oc_insert = text("""
                INSERT INTO oc_category (parent_id, top, sort_order, status, date_added, date_modified)
                VALUES (:parent_id, 0, :sort_order, 1, NOW(), NOW())
            """)
            
            oc_db.execute(oc_insert, {
                'parent_id': oc_parent_id,
                'sort_order': sort_order
            })
            
            oc_category_id = oc_db.execute(text("SELECT LAST_INSERT_ID()")).fetchone()[0]
            
            # Додаємо опис (українська мова - language_id 1)
            oc_desc_insert = text("""
                INSERT INTO oc_category_description (category_id, language_id, name, description, meta_title)
                VALUES (:category_id, 1, :name, :description, :name)
            """)
            
            oc_db.execute(oc_desc_insert, {
                'category_id': oc_category_id,
                'name': name,
                'description': description
            })
            
            oc_db.commit()
            
            return {
                'success': True,
                'message': f'Категорію "{name}" створено та синхронізовано з OpenCart'
            }
        except Exception as oc_error:
            print(f"OpenCart sync error: {oc_error}")
            return {
                'success': True,
                'message': f'Категорію "{name}" створено (помилка синхронізації з OpenCart)'
            }
        
    except Exception as e:
        rh_db.rollback()
        raise HTTPException(status_code=500, detail=f"Помилка: {str(e)}")


@router.put("/categories/{category_id}")
async def update_category(
    category_id: int,
    data: dict,
    authorization: str = Header(None),
    rh_db: Session = Depends(get_rh_db)
):
    """Оновити категорію та синхронізувати з OpenCart"""
    require_admin(authorization)
    
    try:
        updates = []
        params = {'category_id': category_id}
        
        if 'name' in data:
            updates.append("name = :name")
            params['name'] = data['name']
        
        if 'parent_id' in data:
            updates.append("parent_id = :parent_id")
            params['parent_id'] = data['parent_id']
        
        if 'description' in data:
            updates.append("description = :description")
            params['description'] = data['description']
        
        if 'sort_order' in data:
            updates.append("sort_order = :sort_order")
            params['sort_order'] = data['sort_order']
        
        if 'is_active' in data:
            updates.append("is_active = :is_active")
            params['is_active'] = data['is_active']
        
        if not updates:
            raise HTTPException(status_code=400, detail="Немає даних для оновлення")
        
        # Оновлюємо в RentalHub
        query = text(f"UPDATE categories SET {', '.join(updates)} WHERE category_id = :category_id")
        rh_db.execute(query, params)
        rh_db.commit()
        
        # Синхронізація з OpenCart
        try:
            from database import get_db
            oc_db = next(get_db())
            
            # Оновлюємо в oc_category
            oc_updates = []
            oc_params = {'category_id': category_id}
            
            if 'sort_order' in data:
                oc_updates.append("sort_order = :sort_order")
                oc_params['sort_order'] = data['sort_order']
            
            if 'is_active' in data:
                oc_updates.append("status = :status")
                oc_params['status'] = 1 if data['is_active'] else 0
            
            if oc_updates:
                oc_query = text(f"UPDATE oc_category SET {', '.join(oc_updates)}, date_modified = NOW() WHERE category_id = :category_id")
                oc_db.execute(oc_query, oc_params)
            
            # Оновлюємо опис
            if 'name' in data or 'description' in data:
                oc_desc_updates = []
                oc_desc_params = {'category_id': category_id}
                
                if 'name' in data:
                    oc_desc_updates.append("name = :name, meta_title = :name")
                    oc_desc_params['name'] = data['name']
                
                if 'description' in data:
                    oc_desc_updates.append("description = :description")
                    oc_desc_params['description'] = data['description']
                
                oc_desc_query = text(f"UPDATE oc_category_description SET {', '.join(oc_desc_updates)} WHERE category_id = :category_id AND language_id = 1")
                oc_db.execute(oc_desc_query, oc_desc_params)
            
            oc_db.commit()
            
            return {
                'success': True,
                'message': 'Категорію оновлено та синхронізовано з OpenCart'
            }
        except Exception as oc_error:
            print(f"OpenCart sync error: {oc_error}")
            return {
                'success': True,
                'message': 'Категорію оновлено (помилка синхронізації з OpenCart)'
            }
        
    except Exception as e:
        rh_db.rollback()
        raise HTTPException(status_code=500, detail=f"Помилка: {str(e)}")


@router.delete("/categories/{category_id}")
async def delete_category(
    category_id: int,
    authorization: str = Header(None),
    rh_db: Session = Depends(get_rh_db)
):
    """Видалити категорію"""
    require_admin(authorization)
    
    try:
        # Перевіряємо чи є підкатегорії
        check_query = text("SELECT COUNT(*) FROM categories WHERE parent_id = :category_id")
        result = rh_db.execute(check_query, {'category_id': category_id}).fetchone()
        
        if result[0] > 0:
            raise HTTPException(
                status_code=400, 
                detail=f"Не можна видалити категорію, яка має {result[0]} підкатегорій"
            )
        
        query = text("DELETE FROM categories WHERE category_id = :category_id")
        result = rh_db.execute(query, {'category_id': category_id})
        rh_db.commit()
        
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Категорію не знайдено")
        
        return {
            'success': True,
            'message': 'Категорію видалено'
        }
        
    except HTTPException:
        raise
    except Exception as e:
        rh_db.rollback()
        raise HTTPException(status_code=500, detail=f"Помилка: {str(e)}")


# ============================================================
# DOCUMENT STATS
# ============================================================
@router.get("/document-stats")
async def get_document_stats(
    authorization: str = Header(None),
    rh_db: Session = Depends(get_rh_db)
):
    require_admin(authorization)
    rows = rh_db.execute(text("SELECT doc_type, COUNT(*) FROM documents GROUP BY doc_type")).fetchall()
    return {r[0]: r[1] for r in rows}

# ============================================================
# COMPANY SETTINGS
# ============================================================
@router.get("/settings")
async def get_settings(
    authorization: str = Header(None),
    rh_db: Session = Depends(get_rh_db)
):
    require_admin(authorization)
    try:
        rows = rh_db.execute(text("SELECT setting_key, setting_value FROM system_settings")).fetchall()
        return {r[0]: r[1] for r in rows}
    except:
        return {
            "name": "Фізична особа-підприємець Николенко Наталя Станіславівна",
            "tax_status": "платник єдиного податку",
            "tax_id": "3606801844",
            "iban": "UA043220010000026003340091618",
            "bank_name": "ПАТ \"УНІВЕРСАЛ БАНК\"",
            "address": "м. Київ",
            "signer_name": "Николенко Н.С.", "signer_role": "",
            "warehouse_address": "м. Київ, вул. Будіндустрії 4"
        }

@router.put("/settings")
async def update_settings(
    data: dict,
    authorization: str = Header(None),
    rh_db: Session = Depends(get_rh_db)
):
    require_admin(authorization)
    try:
        rh_db.execute(text("""
            CREATE TABLE IF NOT EXISTS system_settings (
                setting_key VARCHAR(100) PRIMARY KEY,
                setting_value TEXT,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
        """))
        rh_db.commit()
        for key, value in data.items():
            rh_db.execute(text("""
                INSERT INTO system_settings (setting_key, setting_value) VALUES (:k, :v)
                ON DUPLICATE KEY UPDATE setting_value = :v
            """), {"k": key, "v": str(value) if value else ""})
        rh_db.commit()
        return {"success": True}
    except Exception as e:
        rh_db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# DOCUMENT TEMPLATES
# ============================================================

TEMPLATE_FILE_MAP = {
    "quote": "quote.html",
    "invoice_offer": "invoice_offer.html",
    "master_agreement": "master_agreement.html",
    "issue_act": "issue_act.html",
    "settlement_act": "settlement_act.html",
    "picking_list": "picking_list.html",
    "service_act": "service_act.html",
    # Subdirectory templates (doc_engine)
    "defect_act": "defect_act/v1.html",
    "deposit_settlement_act": "deposit_settlement_act/v1.html",
    "invoice_legal": "invoice_legal/v1.html",
    "goods_invoice": "goods_invoice/v1.html",
}

TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates", "documents")


def _ensure_templates_table(db):
    db.execute(text("""
        CREATE TABLE IF NOT EXISTS document_templates (
            doc_type VARCHAR(100) PRIMARY KEY,
            template_content LONGTEXT NOT NULL,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            updated_by VARCHAR(100)
        )
    """))
    db.commit()


@router.get("/templates")
async def list_templates(
    authorization: str = Header(None),
    rh_db: Session = Depends(get_rh_db)
):
    """List all templates with source info (file / db)."""
    require_admin(authorization)
    _ensure_templates_table(rh_db)

    db_rows = rh_db.execute(text(
        "SELECT doc_type, updated_at, updated_by FROM document_templates"
    )).fetchall()
    db_map = {r[0]: {"updated_at": r[1].isoformat() if r[1] else None, "updated_by": r[2]} for r in db_rows}

    result = []
    for doc_type, file_path in TEMPLATE_FILE_MAP.items():
        full_path = os.path.join(TEMPLATES_DIR, file_path)
        has_file = os.path.exists(full_path)
        in_db = doc_type in db_map
        result.append({
            "doc_type": doc_type,
            "file_path": file_path,
            "has_file": has_file,
            "source": "db" if in_db else ("file" if has_file else "missing"),
            "updated_at": db_map[doc_type]["updated_at"] if in_db else None,
            "updated_by": db_map[doc_type]["updated_by"] if in_db else None,
        })
    return result


@router.get("/templates/{doc_type}")
async def get_template(
    doc_type: str,
    authorization: str = Header(None),
    rh_db: Session = Depends(get_rh_db)
):
    """Get template content — DB first, file fallback."""
    require_admin(authorization)
    _ensure_templates_table(rh_db)

    # Check DB
    row = rh_db.execute(text(
        "SELECT template_content, updated_at, updated_by FROM document_templates WHERE doc_type = :dt"
    ), {"dt": doc_type}).fetchone()

    if row:
        return {
            "doc_type": doc_type,
            "source": "db",
            "content": row[0],
            "updated_at": row[1].isoformat() if row[1] else None,
            "updated_by": row[2],
        }

    # File fallback
    file_path = TEMPLATE_FILE_MAP.get(doc_type)
    if not file_path:
        raise HTTPException(status_code=404, detail=f"Шаблон '{doc_type}' не знайдено")
    full_path = os.path.join(TEMPLATES_DIR, file_path)
    if not os.path.exists(full_path):
        raise HTTPException(status_code=404, detail=f"Файл шаблону не знайдено: {file_path}")

    with open(full_path, "r", encoding="utf-8") as f:
        content = f.read()

    return {"doc_type": doc_type, "source": "file", "content": content, "updated_at": None, "updated_by": None}


@router.put("/templates/{doc_type}")
async def save_template(
    doc_type: str,
    data: dict,
    authorization: str = Header(None),
    rh_db: Session = Depends(get_rh_db)
):
    """Save template to DB."""
    user = require_admin(authorization)
    _ensure_templates_table(rh_db)

    content = data.get("content", "")
    if not content.strip():
        raise HTTPException(status_code=400, detail="Шаблон не може бути порожнім")

    rh_db.execute(text("""
        INSERT INTO document_templates (doc_type, template_content, updated_by)
        VALUES (:dt, :content, :by)
        ON DUPLICATE KEY UPDATE template_content = :content, updated_by = :by
    """), {"dt": doc_type, "content": content, "by": user.get("email", "admin")})
    rh_db.commit()
    return {"success": True, "message": "Шаблон збережено"}


@router.post("/templates/{doc_type}/reset")
async def reset_template(
    doc_type: str,
    authorization: str = Header(None),
    rh_db: Session = Depends(get_rh_db)
):
    """Reset template — delete DB override, revert to file."""
    require_admin(authorization)
    _ensure_templates_table(rh_db)

    rh_db.execute(text("DELETE FROM document_templates WHERE doc_type = :dt"), {"dt": doc_type})
    rh_db.commit()

    # Return file content
    file_path = TEMPLATE_FILE_MAP.get(doc_type)
    if file_path:
        full_path = os.path.join(TEMPLATES_DIR, file_path)
        if os.path.exists(full_path):
            with open(full_path, "r", encoding="utf-8") as f:
                return {"success": True, "content": f.read(), "source": "file"}

    return {"success": True, "content": "", "source": "missing"}


@router.get("/templates/{doc_type}/preview")
async def preview_template(
    doc_type: str,
    order_id: int = 7403,
    authorization: str = Header(None),
    rh_db: Session = Depends(get_rh_db)
):
    """Render template preview with real order data."""
    require_admin(authorization)

    from jinja2 import Environment
    from services.template_loader import DBOverrideLoader
    from jinja2 import FileSystemLoader
    from services.company_config import get_company_config, get_landlord_config

    _ensure_templates_table(rh_db)

    # Get template content
    row = rh_db.execute(text(
        "SELECT template_content FROM document_templates WHERE doc_type = :dt"
    ), {"dt": doc_type}).fetchone()

    if row and row[0]:
        content = row[0]
    else:
        file_path = TEMPLATE_FILE_MAP.get(doc_type)
        if not file_path:
            raise HTTPException(status_code=404, detail="Шаблон не знайдено")
        full_path = os.path.join(TEMPLATES_DIR, file_path)
        if not os.path.exists(full_path):
            raise HTTPException(status_code=404, detail="Файл не знайдено")
        with open(full_path, "r", encoding="utf-8") as f:
            content = f.read()

    # Build minimal context for preview
    company = get_company_config(rh_db)
    landlord = get_landlord_config(rh_db)

    context = {
        "company": company,
        "landlord": landlord,
        "generated_at": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "meta": {"doc_type": doc_type, "status": "draft", "watermark_text": ""},
        "order": {},
        "items": [],
        "totals": {},
    }

    # Try to load order data
    try:
        o = rh_db.execute(text("""
            SELECT order_id, order_number, customer_name, customer_phone,
                   rental_start_date, rental_end_date, rental_days,
                   total_price, deposit_amount
            FROM orders WHERE order_id = :oid
        """), {"oid": order_id}).fetchone()
        if o:
            context["order"] = {
                "order_number": o[1] or f"OC-{o[0]}",
                "customer_name": o[2] or "",
                "customer_phone": o[3] or "",
                "phone": o[3] or "",
                "email": "",
                "rental_start_date": o[4].strftime("%d.%m.%Y") if o[4] else "",
                "rental_end_date": o[5].strftime("%d.%m.%Y") if o[5] else "",
                "rental_days": o[6] or 1,
                "total_price": float(o[7] or 0),
                "total_price_fmt": f"{float(o[7] or 0):,.2f}".replace(",", " "),
                "deposit_amount": float(o[8] or 0),
                "deposit_amount_fmt": f"{float(o[8] or 0):,.2f}".replace(",", " "),
                "delivery_type_label": "Самовивіз",
                "city": "Київ",
                "delivery_address": company.get("warehouse", ""),
                "discount_amount": 0,
                "discount_percent": 0,
                "service_fee": 0,
                "service_fee_name": "",
                "customer_email": "",
                "event_type": "",
                "customer_comment": "",
            }
            items = rh_db.execute(text("""
                SELECT product_name, quantity, price, total_rental
                FROM order_items WHERE order_id = :oid AND status = 'active'
            """), {"oid": order_id}).fetchall()
            context["items"] = [
                {"product_name": i[0], "name": i[0], "quantity": i[1], "price_per_day_fmt": f"{float(i[2] or 0):,.2f}",
                 "rental_price_fmt": f"{float(i[2] or 0):,.2f}", "loss_fmt": "0,00", "deposit_fmt": "0,00",
                 "sku": "—", "image_url": None, "note": None}
                for i in items
            ]
            context["totals"] = {
                "rent_total_fmt": context["order"]["total_price_fmt"],
                "deposit_total_fmt": context["order"]["deposit_amount_fmt"],
                "loss_total_fmt": "0,00",
                "grand_total_fmt": context["order"]["total_price_fmt"],
                "grand_total": context["order"]["total_price"],
            }
    except Exception as e:
        context["_preview_error"] = str(e)

    # Additional context keys for various templates
    context.setdefault("additional_services", [])
    context.setdefault("executor", {"name": company["legal_name"], "short_name": company["short_name"]})
    context.setdefault("client", {"name": context["order"].get("customer_name", ""), "phone": context["order"].get("customer_phone", "")})
    context.setdefault("tenant", {"legal_name": context["order"].get("customer_name", ""), "signer_name": context["order"].get("customer_name", ""), "signer_role": ""})
    context.setdefault("agreement", {"contract_number": ""})
    context.setdefault("damage", {"has_damage": False, "rows": [], "total": 0})
    context.setdefault("annex", {"number": 1, "date": datetime.now().strftime("%d.%m.%Y")})
    context.setdefault("signatures", {})
    context.setdefault("return_data", {})

    # Render
    try:
        env = Environment(autoescape=False)
        # Register custom filters
        env.filters['money'] = lambda v: f"{float(v or 0):,.2f}".replace(",", " ")
        env.filters['date'] = lambda v, fmt="%d.%m.%Y": str(v) if v else ""
        template = env.from_string(content)
        html = template.render(**context)
        return {"success": True, "html": html}
    except Exception as e:
        return {"success": False, "error": str(e), "html": f"<pre style='color:red'>Помилка рендерингу:\n{str(e)}</pre>"}
