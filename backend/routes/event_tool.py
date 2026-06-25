"""
Event Tool API Routes
Інтеграція каталогу декораторів з RentalHub
Всі endpoints під /api/event/*
"""
from fastapi import APIRouter, Depends, HTTPException, status, Header, Response, Body, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Optional
from datetime import datetime, timedelta, date
from pydantic import BaseModel
import uuid
import logging
import os
import json
from functools import lru_cache
import time

from database_rentalhub import get_rh_db
from utils.image_helper import normalize_image_url
from utils.smart_search import filter_and_rank, parse_query
from utils.rental_days import calculate_rental_days as _calc_days

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/event", tags=["Event Tool"])

# ============================================================================
# CACHE для швидкої роботи
# ============================================================================
_categories_cache = {"data": None, "expires": 0}
_subcategories_cache = {"data": None, "expires": 0}
CACHE_TTL = 300  # 5 хвилин

# ============================================================================
# SCHEMAS
# ============================================================================

class CustomerRegister(BaseModel):
    email: str
    password: str
    firstname: str
    lastname: Optional[str] = None
    telephone: Optional[str] = None

class CustomerLogin(BaseModel):
    email: str
    password: str

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class EventBoardCreate(BaseModel):
    board_name: str
    event_date: Optional[str] = None
    event_type: Optional[str] = None
    rental_start_date: Optional[str] = None
    rental_end_date: Optional[str] = None
    notes: Optional[str] = None
    budget: Optional[float] = None
    cover_image: Optional[str] = None

class EventBoardUpdate(BaseModel):
    board_name: Optional[str] = None
    event_date: Optional[str] = None
    event_type: Optional[str] = None
    rental_start_date: Optional[str] = None
    rental_end_date: Optional[str] = None
    notes: Optional[str] = None
    budget: Optional[float] = None
    status: Optional[str] = None
    cover_image: Optional[str] = None
    canvas_layout: Optional[dict] = None

class EventBoardItemCreate(BaseModel):
    product_id: int
    quantity: int = 1
    notes: Optional[str] = None
    section: Optional[str] = None

class EventBoardItemUpdate(BaseModel):
    quantity: Optional[int] = None
    notes: Optional[str] = None
    section: Optional[str] = None

class OrderCreate(BaseModel):
    """Схема для створення замовлення з Ivent-tool
    
    Мінімальний набір даних - все інше автоматично підтягується з:
    - event_customers: email (обов'язково з токена)
    - event_boards: назва події, дати оренди, дата події
    """
    # Контактні дані - можуть бути передані або взяті з профілю
    customer_name: Optional[str] = None
    phone: Optional[str] = None
    
    # Тип платника - єдиний обов'язковий вибір клієнта
    payer_type: str = "individual"  # individual, fop, company
    
    # Коментар (опціонально)
    customer_comment: Optional[str] = None

    # Час видачі/повернення (опціонально)
    pickup_time_slot: Optional[str] = None  # "11:00-12:00"
    return_time: Optional[str] = "17:00"

# ============================================================================
# AUTH HELPERS
# ============================================================================

import hashlib
import jwt

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours
REFRESH_TOKEN_EXPIRE_DAYS = 30

def get_secret_key():
    """Отримати JWT секрет"""
    return os.getenv("JWT_SECRET_KEY", os.getenv("EVENT_JWT_SECRET", "event-tool-secret-key-change-in-production"))

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return hash_password(plain_password) == hashed_password

def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    # Конвертуємо sub в string
    if "sub" in to_encode:
        to_encode["sub"] = str(to_encode["sub"])
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, get_secret_key(), algorithm=ALGORITHM)

def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    # Конвертуємо sub в string
    if "sub" in to_encode:
        to_encode["sub"] = str(to_encode["sub"])
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, get_secret_key(), algorithm=ALGORITHM)

def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, get_secret_key(), algorithms=[ALGORITHM])
        # Конвертуємо sub назад в int
        if "sub" in payload:
            payload["sub"] = int(payload["sub"])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError as e:
        logger.error(f"JWT decode error: {e}")
        raise HTTPException(status_code=401, detail="Invalid token")

def get_current_customer(token: str, db: Session):
    """Отримати поточного користувача з токена"""
    payload = decode_token(token)
    customer_id = payload.get("sub")
    if not customer_id:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    result = db.execute(text("SELECT * FROM event_customers WHERE customer_id = :id"), {"id": customer_id})
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=401, detail="Customer not found")
    
    return {
        "customer_id": row[0],
        "email": row[1],
        "firstname": row[3],
        "lastname": row[4],
        "telephone": row[5]
    }

def get_token_from_header(authorization: Optional[str] = Header(None)) -> str:
    """Витягти токен з Authorization header"""
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header missing")
    
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization format. Use: Bearer <token>")
    
    return authorization.replace("Bearer ", "")

# ============================================================================
# INIT TABLES (create if not exist)
# ============================================================================

def init_event_tables(db: Session):
    """Створити таблиці для Event Tool якщо не існують"""
    
    # Event Customers (декоратори)
    db.execute(text("""
        CREATE TABLE IF NOT EXISTS event_customers (
            customer_id INT AUTO_INCREMENT PRIMARY KEY,
            email VARCHAR(255) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            firstname VARCHAR(255),
            lastname VARCHAR(255),
            telephone VARCHAR(50),
            is_active BOOLEAN DEFAULT TRUE,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_login DATETIME
        )
    """))
    
    # Event Boards (мудборди) - БЕЗ FK для сумісності
    db.execute(text("""
        CREATE TABLE IF NOT EXISTS event_boards (
            id VARCHAR(36) PRIMARY KEY,
            customer_id INT NOT NULL,
            board_name VARCHAR(255) NOT NULL,
            event_date DATE NULL,
            event_type VARCHAR(100) NULL,
            rental_start_date DATE NULL,
            rental_end_date DATE NULL,
            rental_days INT NULL,
            status VARCHAR(50) DEFAULT 'draft',
            notes TEXT NULL,
            budget DECIMAL(10,2) NULL,
            estimated_total DECIMAL(10,2) DEFAULT 0,
            cover_image VARCHAR(500) NULL,
            canvas_layout JSON NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            converted_to_order_id INT NULL,
            INDEX idx_event_boards_customer (customer_id),
            INDEX idx_event_boards_status (status)
        )
    """))
    
    # Event Board Items - БЕЗ FK для сумісності
    db.execute(text("""
        CREATE TABLE IF NOT EXISTS event_board_items (
            id VARCHAR(36) PRIMARY KEY,
            board_id VARCHAR(36) NOT NULL,
            product_id INT NOT NULL,
            quantity INT DEFAULT 1,
            notes TEXT NULL,
            section VARCHAR(100) NULL,
            position INT DEFAULT 0,
            added_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_event_board_items_board (board_id),
            INDEX idx_event_board_items_product (product_id)
        )
    """))
    
    # Soft Reservations (тимчасові резервації в мудбордах)
    db.execute(text("""
        CREATE TABLE IF NOT EXISTS event_soft_reservations (
            id VARCHAR(36) PRIMARY KEY,
            board_id VARCHAR(36) NOT NULL,
            product_id INT NOT NULL,
            quantity INT NOT NULL,
            reserved_from DATE NOT NULL,
            reserved_until DATE NOT NULL,
            expires_at DATETIME NOT NULL,
            customer_id INT NOT NULL,
            status VARCHAR(20) DEFAULT 'active',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_soft_res_board (board_id),
            INDEX idx_soft_res_product (product_id),
            INDEX idx_soft_res_dates (reserved_from, reserved_until),
            INDEX idx_soft_res_expires (expires_at)
        )
    """))
    
    db.commit()
    logger.info("✅ Event Tool tables initialized")

# ============================================================================
# AUTH ENDPOINTS
# ============================================================================

@router.post("/auth/register")
async def register(data: CustomerRegister, db: Session = Depends(get_rh_db)):
    """Реєстрація декоратора"""
    init_event_tables(db)
    
    # Перевірити чи email існує
    result = db.execute(text("SELECT customer_id FROM event_customers WHERE email = :email"), {"email": data.email})
    if result.fetchone():
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Створити користувача
    db.execute(text("""
        INSERT INTO event_customers (email, password_hash, firstname, lastname, telephone)
        VALUES (:email, :password_hash, :firstname, :lastname, :telephone)
    """), {
        "email": data.email,
        "password_hash": hash_password(data.password),
        "firstname": data.firstname,
        "lastname": data.lastname,
        "telephone": data.telephone
    })
    db.commit()
    
    # Отримати створеного користувача
    result = db.execute(text("SELECT customer_id, email, firstname FROM event_customers WHERE email = :email"), {"email": data.email})
    row = result.fetchone()
    
    logger.info(f"✅ New decorator registered: {data.email}")
    
    return {
        "customer_id": row[0],
        "email": row[1],
        "firstname": row[2],
        "message": "Registration successful"
    }

@router.post("/auth/login", response_model=Token)
async def login(data: CustomerLogin, db: Session = Depends(get_rh_db)):
    """Вхід декоратора"""
    init_event_tables(db)
    
    result = db.execute(text("""
        SELECT customer_id, password_hash FROM event_customers 
        WHERE email = :email AND is_active = TRUE
    """), {"email": data.email})
    row = result.fetchone()
    
    if not row or not verify_password(data.password, row[1]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    customer_id = row[0]
    
    # Оновити last_login
    db.execute(text("UPDATE event_customers SET last_login = NOW() WHERE customer_id = :id"), {"id": customer_id})
    db.commit()
    
    access_token = create_access_token({"sub": customer_id})
    refresh_token = create_refresh_token({"sub": customer_id})
    
    logger.info(f"✅ Decorator logged in: {data.email}")
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }

@router.get("/auth/me")
async def get_me(
    db: Session = Depends(get_rh_db),
    token: str = Depends(get_token_from_header)
):
    """Отримати профіль поточного декоратора"""
    customer = get_current_customer(token, db)
    return customer

# ============================================================================
# PRODUCTS ENDPOINTS (читає з RentalHub products)
# ============================================================================

@router.get("/products")
async def get_products(
    response: Response,
    search: Optional[str] = None,
    category_name: Optional[str] = None,
    subcategory_name: Optional[str] = None,
    color: Optional[str] = None,
    date_from: Optional[str] = None,  # YYYY-MM-DD - для перевірки доступності
    date_to: Optional[str] = None,    # YYYY-MM-DD
    skip: int = 0,
    limit: int = 500,
    db: Session = Depends(get_rh_db)
):
    """Отримати каталог товарів з перевіркою доступності на дати (як RentalHub)"""
    
    response.headers["Cache-Control"] = "public, max-age=30"
    
    # Якщо є search — тягнемо широку вибірку без LIKE, потім скоримо в Python
    use_smart_search = bool(search and search.strip())
    
    # Перевіряємо чи є колонка `deposit` у products (для застави)
    prod_cols_res = db.execute(text("SHOW COLUMNS FROM products")).fetchall()
    prod_cols_set = {r[0] for r in prod_cols_res}
    deposit_col_sql = "deposit" if "deposit" in prod_cols_set else "price"
    
    sql = f"""
        SELECT product_id, sku, name, category_name, subcategory_name,
               rental_price, image_url, color, material, size,
               quantity, frozen_quantity, description, price,
               height_cm, diameter_cm, width_cm, depth_cm, shape,
               components, hashtags,
               {deposit_col_sql} AS deposit_amount
        FROM products
        WHERE status = 1
    """
    params = {}
    
    if not use_smart_search:
        # Старий швидкий шлях без пошуку
        pass
    
    if category_name:
        sql += " AND category_name = :category_name"
        params["category_name"] = category_name
    
    if subcategory_name:
        sql += " AND subcategory_name = :subcategory_name"
        params["subcategory_name"] = subcategory_name
    
    if color:
        sql += " AND color LIKE :color"
        params["color"] = f"%{color}%"
    
    # Сортування — новинки зверху (за ID DESC). Якщо клієнт явно фільтрує — лишаємо групування
    if use_smart_search:
        # При smart search тягнемо ВСЕ що пройшло інші фільтри (статус/категорія/колір)
        # Skip/limit застосуємо ПІСЛЯ скорингу
        sql += " ORDER BY product_id DESC"
    else:
        sql += " ORDER BY product_id DESC LIMIT :limit OFFSET :skip"
        params["limit"] = limit
        params["skip"] = skip
    
    result = db.execute(text(sql), params)
    rows = result.fetchall()
    
    if not rows:
        return []
    
    # Якщо smart search — перетворюємо rows у dicts і фільтруємо/ранжуємо
    if use_smart_search:
        all_items = []
        for row in rows:
            all_items.append({
                "product_id": row[0],
                "sku": row[1],
                "name": row[2],
                "category_name": row[3],
                "subcategory_name": row[4],
                "color": row[7],
                "material": row[8],
                "size": row[9],
                "description": row[12],
                "height_cm": row[14],
                "diameter_cm": row[15],
                "width_cm": row[16],
                "depth_cm": row[17],
                "shape": row[18],
                "components": row[19],
                "hashtags": row[20],
                "_row": row,  # збережемо для подальшого використання
            })
        # Ранжуємо
        ranked = filter_and_rank(all_items, search, threshold=65.0)
        # skip/limit
        ranked = ranked[skip: skip + limit] if limit else ranked[skip:]
        rows = [item["_row"] for item in ranked]
        if not rows:
            return []
    
    product_ids = [row[0] for row in rows]
    
    # Перевірка доступності на дати (як в RentalHub каталозі)
    reserved_dict = {}
    in_rent_dict = {}
    
    if date_from and date_to:
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
        """), {"product_ids": tuple(product_ids), "date_from": date_from, "date_to": date_to})
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
        """), {"product_ids": tuple(product_ids), "date_from": date_from, "date_to": date_to})
        in_rent_dict = {row[0]: int(row[1]) for row in in_rent_result}
    else:
        # Без дат - поточний стан
        reserved_result = db.execute(text("""
            SELECT oi.product_id, COALESCE(SUM(oi.quantity), 0) as reserved
            FROM order_items oi
            JOIN orders o ON oi.order_id = o.order_id
            WHERE oi.product_id IN :product_ids
            AND o.status IN ('processing', 'ready_for_issue', 'awaiting_customer', 'pending')
            AND o.rental_end_date >= CURDATE()
            GROUP BY oi.product_id
        """), {"product_ids": tuple(product_ids)})
        reserved_dict = {row[0]: int(row[1]) for row in reserved_result}
        
        in_rent_result = db.execute(text("""
            SELECT oi.product_id, COALESCE(SUM(oi.quantity), 0) as in_rent
            FROM order_items oi
            JOIN orders o ON oi.order_id = o.order_id
            WHERE oi.product_id IN :product_ids
            AND o.status IN ('issued', 'on_rent')
            AND o.rental_end_date >= CURDATE()
            GROUP BY oi.product_id
        """), {"product_ids": tuple(product_ids)})
        in_rent_dict = {row[0]: int(row[1]) for row in in_rent_result}
    
    # Побудова результату
    products = []
    for row in rows:
        product_id = row[0]
        total_qty = row[10] or 0
        frozen_qty = row[11] or 0
        
        reserved = reserved_dict.get(product_id, 0)
        in_rent = in_rent_dict.get(product_id, 0)
        
        # Доступно = загальна кількість - заморожено - в оренді - в резерві
        available = max(0, total_qty - frozen_qty - in_rent - reserved)
        
        products.append({
            "product_id": product_id,
            "sku": row[1],
            "name": row[2],
            "category_name": row[3],
            "subcategory_name": row[4],
            "rental_price": float(row[5]) if row[5] else 0,
            "image_url": normalize_image_url(row[6]),
            "color": row[7],
            "material": row[8],
            "size": row[9],
            "quantity": total_qty,
            "frozen_quantity": frozen_qty,
            "reserved": reserved,
            "in_rent": in_rent,
            "available": available,
            "is_available": available > 0,
            "description": row[12],
            "price": float(row[13]) if row[13] else 0,
            "deposit": float(row[21]) if len(row) > 21 and row[21] else 0,
        })
    
    return products

@router.get("/products/{product_id}")
async def get_product(product_id: int, db: Session = Depends(get_rh_db)):
    """Деталі товару (включно з усіма фото з product_images і розмірами)"""
    # Перевіряємо які колонки реально є в `products`
    cols_rows = db.execute(text("SHOW COLUMNS FROM products")).fetchall()
    existing_cols = {r[0] for r in cols_rows}

    def col(name, default="NULL"):
        return name if name in existing_cols else default

    sql = f"""
        SELECT
            product_id, sku, name,
            {col('category_name', "''")} AS category_name,
            {col('subcategory_name', "''")} AS subcategory_name,
            {col('rental_price', '0')} AS rental_price,
            image_url,
            {col('color', "''")} AS color,
            {col('material', "''")} AS material,
            {col('size', "''")} AS size,
            {col('description', "''")} AS description,
            {col('quantity', '0')} AS quantity,
            {col('frozen_quantity', '0')} AS frozen_quantity,
            {col('price', '0')} AS price,
            {col('height', 'NULL')} AS height,
            {col('width', 'NULL')} AS width,
            {col('depth', 'NULL')} AS depth,
            {col('length', 'NULL')} AS length_cm,
            {col('diameter', 'NULL')} AS diameter,
            {col('weight', 'NULL')} AS weight,
            {col('set_contents', "''")} AS set_contents,
            {col('complectation', "''")} AS complectation,
            {col('deposit', col('price', '0'))} AS deposit_amount
        FROM products WHERE product_id = :id
    """
    row = db.execute(text(sql), {"id": product_id}).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Product not found")

    # Усі фото з product_images (якщо є)
    images = []
    primary_image = normalize_image_url(row[6])
    try:
        img_rows = db.execute(text("""
            SELECT image_url, is_primary, sort_order
            FROM product_images
            WHERE product_id = :id
            ORDER BY is_primary DESC, sort_order ASC, id ASC
        """), {"id": product_id}).fetchall()
        for ir in img_rows:
            url = normalize_image_url(ir[0])
            if url:
                images.append(url)
    except Exception:
        # таблиці може не бути на staging — не падаємо
        pass

    # Якщо в product_images немає — використовуємо image_url з products
    if not images and primary_image:
        images = [primary_image]

    return {
        "product_id": row[0],
        "sku": row[1],
        "name": row[2],
        "category_name": row[3],
        "subcategory_name": row[4],
        "rental_price": float(row[5]) if row[5] is not None else 0,
        "image_url": primary_image or (images[0] if images else None),
        "images": images,                  # <-- масив для каруселі
        "color": row[7],
        "material": row[8],
        "size": row[9],
        "description": row[10],
        "quantity": int(row[11] or 0),
        "frozen_quantity": int(row[12] or 0),
        "available": max(0, int(row[11] or 0) - int(row[12] or 0)),
        "price": float(row[13]) if row[13] is not None else 0,
        # Розміри (числові, в см / кг)
        "height": float(row[14]) if row[14] is not None else None,
        "width": float(row[15]) if row[15] is not None else None,
        "depth": float(row[16]) if row[16] is not None else None,
        "length": float(row[17]) if row[17] is not None else None,
        "diameter": float(row[18]) if row[18] is not None else None,
        "weight": float(row[19]) if row[19] is not None else None,
        # Комплектація
        "set_contents": row[20] or "",
        "complectation": row[21] or "",
        "deposit": float(row[22]) if len(row) > 22 and row[22] is not None else 0,
    }

@router.get("/categories")
async def get_categories(response: Response, db: Session = Depends(get_rh_db)):
    """
    Отримати дерево категорій та підкатегорій з кількістю товарів (як RentalHub)
    Повертає також кольори та матеріали для фільтрів
    """
    global _categories_cache
    
    now = time.time()
    if _categories_cache["data"] and _categories_cache["expires"] > now:
        response.headers["X-Cache"] = "HIT"
        response.headers["Cache-Control"] = "public, max-age=300"
        return _categories_cache["data"]
    
    response.headers["X-Cache"] = "MISS"
    response.headers["Cache-Control"] = "public, max-age=300"
    
    # Отримати всі категорії з підкатегоріями та кількістю товарів
    result = db.execute(text("""
        SELECT 
            p.category_name,
            p.subcategory_name,
            COUNT(DISTINCT p.product_id) as product_count,
            SUM(p.quantity) as total_qty
        FROM products p
        WHERE p.status = 1 AND p.category_name IS NOT NULL AND p.category_name != ''
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
    
    # Отримати унікальні кольори (розбиваємо комбінації на окремі базові)
    colors_result = db.execute(text("""
        SELECT DISTINCT color FROM products 
        WHERE status = 1 AND color IS NOT NULL AND color != ''
    """))
    
    # Розбиваємо комбінації типу "білий, золотий" на окремі кольори
    colors_set = set()
    for row in colors_result:
        if row[0]:
            # Розбиваємо по комі і нормалізуємо
            for color in row[0].split(','):
                color = color.strip().lower()
                if color:
                    colors_set.add(color)
    
    # Сортуємо українською
    colors = sorted(list(colors_set), key=lambda x: x.lower())
    
    # Отримати унікальні матеріали (так само розбиваємо)
    materials_result = db.execute(text("""
        SELECT DISTINCT material FROM products 
        WHERE status = 1 AND material IS NOT NULL AND material != ''
    """))
    
    materials_set = set()
    for row in materials_result:
        if row[0]:
            for material in row[0].split(','):
                material = material.strip().lower()
                if material:
                    materials_set.add(material)
    
    materials = sorted(list(materials_set), key=lambda x: x.lower())
    
    data = {
        "categories": list(categories_map.values()),
        "colors": colors,
        "materials": materials
    }
    
    # Зберегти в кеш
    _categories_cache = {"data": data, "expires": now + CACHE_TTL}
    return data

@router.get("/subcategories")
async def get_subcategories(response: Response, category_name: Optional[str] = None, db: Session = Depends(get_rh_db)):
    """Отримати підкатегорії для конкретної категорії"""
    response.headers["Cache-Control"] = "public, max-age=300"
    
    sql = """
        SELECT subcategory_name, COUNT(*) as product_count, SUM(quantity) as total_qty
        FROM products 
        WHERE status = 1 AND subcategory_name IS NOT NULL AND subcategory_name != ''
    """
    params = {}
    
    if category_name:
        sql += " AND category_name = :category_name"
        params["category_name"] = category_name
    
    sql += " GROUP BY subcategory_name ORDER BY subcategory_name"
    
    result = db.execute(text(sql), params)
    return [{"name": row[0], "product_count": row[1], "total_qty": row[2] or 0} for row in result]

# ============================================================================
# AVAILABILITY CHECK
# ============================================================================

class AvailabilityCheck(BaseModel):
    product_id: int
    quantity: int
    reserved_from: str
    reserved_until: str

@router.post("/products/check-availability")
async def check_availability(data: AvailabilityCheck, db: Session = Depends(get_rh_db)):
    """Перевірити доступність товару на вказані дати"""
    
    # Отримати інформацію про товар
    product_result = db.execute(text("""
        SELECT product_id, name, quantity, frozen_quantity
        FROM products WHERE product_id = :id AND status = 1
    """), {"id": data.product_id})
    product = product_result.fetchone()
    
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    total_quantity = product[2] or 0
    frozen_quantity = product[3] or 0
    base_available = total_quantity - frozen_quantity
    
    # Перевірити перетин з існуючими замовленнями
    reserved_result = db.execute(text("""
        SELECT COALESCE(SUM(oi.quantity), 0) as reserved_qty
        FROM order_items oi
        JOIN orders o ON oi.order_id = o.order_id
        WHERE oi.product_id = :product_id
        AND o.status NOT IN ('cancelled', 'returned', 'completed')
        AND o.rental_start_date <= :end_date
        AND o.rental_end_date >= :start_date
    """), {
        "product_id": data.product_id,
        "start_date": data.reserved_from,
        "end_date": data.reserved_until
    })
    reserved_qty = reserved_result.fetchone()[0] or 0
    
    # Перевірити soft reservations з інших бордів
    soft_reserved_result = db.execute(text("""
        SELECT COALESCE(SUM(quantity), 0) as soft_reserved
        FROM event_soft_reservations
        WHERE product_id = :product_id
        AND status = 'active'
        AND expires_at > NOW()
        AND reserved_from <= :end_date
        AND reserved_until >= :start_date
    """), {
        "product_id": data.product_id,
        "start_date": data.reserved_from,
        "end_date": data.reserved_until
    })
    soft_reserved = soft_reserved_result.fetchone()[0] or 0
    
    available_for_dates = base_available - reserved_qty - soft_reserved
    is_available = available_for_dates >= data.quantity
    
    return {
        "product_id": data.product_id,
        "requested_quantity": data.quantity,
        "total_quantity": total_quantity,
        "reserved_quantity": int(reserved_qty),
        "soft_reserved": int(soft_reserved),
        "available": max(0, available_for_dates),
        "is_available": is_available,
        "reserved_from": data.reserved_from,
        "reserved_until": data.reserved_until
    }

# ============================================================================
# EVENT BOARDS ENDPOINTS
# ============================================================================

@router.get("/boards")
async def get_boards(
    status: Optional[str] = None,
    db: Session = Depends(get_rh_db),
    token: str = Depends(get_token_from_header)
):
    """Отримати мудборди декоратора"""
    customer = get_current_customer(token, db)
    
    sql = """
        SELECT id, customer_id, board_name, event_date, event_type,
               rental_start_date, rental_end_date, rental_days, status,
               notes, budget, estimated_total, cover_image, canvas_layout,
               created_at, updated_at, converted_to_order_id
        FROM event_boards WHERE customer_id = :customer_id
    """
    params = {"customer_id": customer["customer_id"]}

    if status:
        sql += " AND status = :status"
        params["status"] = status
    else:
        # За замовчуванням приховуємо мудборди, які вже стали замовленнями
        # (вони мають status='converted'). Якщо потрібні усі — передай ?status=all
        sql += " AND (status IS NULL OR status NOT IN ('converted', 'archived'))"

    sql += " ORDER BY updated_at DESC"
    
    result = db.execute(text(sql), params)
    boards = []
    
    for row in result:
        board = {
            "id": row[0],
            "customer_id": row[1],
            "board_name": row[2],
            "event_date": row[3].isoformat() if row[3] else None,
            "event_type": row[4],
            "rental_start_date": row[5].isoformat() if row[5] else None,
            "rental_end_date": row[6].isoformat() if row[6] else None,
            "rental_days": row[7],
            "status": row[8],
            "notes": row[9],
            "budget": float(row[10]) if row[10] else None,
            "estimated_total": float(row[11]) if row[11] else 0,
            "cover_image": row[12],
            "canvas_layout": row[13],
            "created_at": row[14].isoformat() if row[14] else None,
            "updated_at": row[15].isoformat() if row[15] else None,
            "converted_to_order_id": row[16]
        }
        
        # Завантажити items
        items_result = db.execute(text("""
            SELECT ebi.id, ebi.board_id, ebi.product_id, ebi.quantity, ebi.notes, 
                   ebi.section, ebi.position, ebi.added_at,
                   p.sku, p.name, p.rental_price, p.image_url, p.color, p.material
            FROM event_board_items ebi
            JOIN products p ON ebi.product_id = p.product_id
            WHERE ebi.board_id = :board_id
            ORDER BY ebi.position
        """), {"board_id": row[0]})
        
        board["items"] = [{
            "id": item[0],
            "board_id": item[1],
            "product_id": item[2],
            "quantity": item[3],
            "notes": item[4],
            "section": item[5],
            "position": item[6],
            "added_at": item[7].isoformat() if item[7] else None,
            "product": {
                "sku": item[8],
                "name": item[9],
                "rental_price": float(item[10]) if item[10] else 0,
                "image_url": normalize_image_url(item[11]),
                "color": item[12],
                "material": item[13]
            }
        } for item in items_result]
        
        boards.append(board)
    
    return boards

@router.post("/boards")
async def create_board(
    data: EventBoardCreate,
    db: Session = Depends(get_rh_db),
    token: str = Depends(get_token_from_header)
):
    """Створити новий мудборд"""
    customer = get_current_customer(token, db)
    board_id = str(uuid.uuid4())
    
    rental_days = None
    if data.rental_start_date and data.rental_end_date:
        start = datetime.strptime(data.rental_start_date, "%Y-%m-%d")
        end = datetime.strptime(data.rental_end_date, "%Y-%m-%d")
        rental_days = (end - start).days + 1
    
    db.execute(text("""
        INSERT INTO event_boards (id, customer_id, board_name, event_date, event_type,
                                  rental_start_date, rental_end_date, rental_days, notes, budget, status, cover_image)
        VALUES (:id, :customer_id, :board_name, :event_date, :event_type,
                :rental_start_date, :rental_end_date, :rental_days, :notes, :budget, 'draft', :cover_image)
    """), {
        "id": board_id,
        "customer_id": customer["customer_id"],
        "board_name": data.board_name,
        "event_date": data.event_date,
        "event_type": data.event_type,
        "rental_start_date": data.rental_start_date,
        "rental_end_date": data.rental_end_date,
        "rental_days": rental_days,
        "notes": data.notes,
        "budget": data.budget,
        "cover_image": data.cover_image
    })
    db.commit()
    
    logger.info(f"✅ Event board created: {board_id}")
    
    # Повертаємо повний об'єкт борду з усіма даними
    return {
        "id": board_id,
        "customer_id": customer["customer_id"],
        "board_name": data.board_name,
        "event_date": data.event_date,
        "event_type": data.event_type,
        "rental_start_date": data.rental_start_date,
        "rental_end_date": data.rental_end_date,
        "rental_days": rental_days,
        "status": "draft",
        "notes": data.notes,
        "budget": data.budget,
        "estimated_total": 0,
        "cover_image": data.cover_image,
        "canvas_layout": None,
        "items": []
    }

@router.get("/boards/{board_id}")
async def get_board(
    board_id: str,
    db: Session = Depends(get_rh_db),
    token: str = Depends(get_token_from_header)
):
    """Отримати мудборд з товарами"""
    customer = get_current_customer(token, db)
    
    result = db.execute(text("""
        SELECT id, customer_id, board_name, event_date, event_type,
               rental_start_date, rental_end_date, rental_days, status,
               notes, budget, estimated_total, cover_image, canvas_layout,
               created_at, updated_at, converted_to_order_id
        FROM event_boards WHERE id = :id AND customer_id = :customer_id
    """), {"id": board_id, "customer_id": customer["customer_id"]})
    row = result.fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail="Board not found")
    
    board = {
        "id": row[0],
        "customer_id": row[1],
        "board_name": row[2],
        "event_date": row[3].isoformat() if row[3] else None,
        "event_type": row[4],
        "rental_start_date": row[5].isoformat() if row[5] else None,
        "rental_end_date": row[6].isoformat() if row[6] else None,
        "rental_days": row[7],
        "status": row[8],
        "notes": row[9],
        "budget": float(row[10]) if row[10] else None,
        "estimated_total": float(row[11]) if row[11] else 0,
        "cover_image": row[12],
        "canvas_layout": row[13],
        "created_at": row[14].isoformat() if row[14] else None,
        "updated_at": row[15].isoformat() if row[15] else None,
        "converted_to_order_id": row[16]
    }
    
    # Items з повною інформацією про товар
    items_result = db.execute(text("""
        SELECT ebi.id, ebi.board_id, ebi.product_id, ebi.quantity, ebi.notes, 
               ebi.section, ebi.position, ebi.added_at,
               p.sku, p.name, p.rental_price, p.image_url, p.color, p.material
        FROM event_board_items ebi
        JOIN products p ON ebi.product_id = p.product_id
        WHERE ebi.board_id = :board_id
        ORDER BY ebi.position
    """), {"board_id": board_id})
    
    board["items"] = [{
        "id": item[0],
        "board_id": item[1],
        "product_id": item[2],
        "quantity": item[3],
        "notes": item[4],
        "section": item[5],
        "position": item[6],
        "added_at": item[7].isoformat() if item[7] else None,
        "product": {
            "sku": item[8],
            "name": item[9],
            "rental_price": float(item[10]) if item[10] else 0,
            "image_url": normalize_image_url(item[11]),
            "color": item[12],
            "material": item[13]
        }
    } for item in items_result]
    
    return board

@router.patch("/boards/{board_id}")
async def update_board(
    board_id: str,
    data: EventBoardUpdate,
    db: Session = Depends(get_rh_db),
    token: str = Depends(get_token_from_header)
):
    """Оновити мудборд"""
    customer = get_current_customer(token, db)
    
    # Перевірити права
    result = db.execute(text("""
        SELECT id FROM event_boards WHERE id = :id AND customer_id = :customer_id
    """), {"id": board_id, "customer_id": customer["customer_id"]})
    if not result.fetchone():
        raise HTTPException(status_code=404, detail="Board not found")
    
    # Build update
    updates = []
    params = {"id": board_id}
    
    if data.board_name is not None:
        updates.append("board_name = :board_name")
        params["board_name"] = data.board_name
    if data.event_date is not None:
        updates.append("event_date = :event_date")
        params["event_date"] = data.event_date
    if data.event_type is not None:
        updates.append("event_type = :event_type")
        params["event_type"] = data.event_type
    if data.rental_start_date is not None:
        updates.append("rental_start_date = :rental_start_date")
        params["rental_start_date"] = data.rental_start_date
    if data.rental_end_date is not None:
        updates.append("rental_end_date = :rental_end_date")
        params["rental_end_date"] = data.rental_end_date
    if data.notes is not None:
        updates.append("notes = :notes")
        params["notes"] = data.notes
    if data.budget is not None:
        updates.append("budget = :budget")
        params["budget"] = data.budget
    if data.status is not None:
        updates.append("status = :status")
        params["status"] = data.status
    if data.cover_image is not None:
        updates.append("cover_image = :cover_image")
        params["cover_image"] = data.cover_image
    if data.canvas_layout is not None:
        updates.append("canvas_layout = :canvas_layout")
        params["canvas_layout"] = json.dumps(data.canvas_layout)
    
    # Перерахувати rental_days якщо оновлені дати
    if data.rental_start_date is not None or data.rental_end_date is not None:
        updates.append("rental_days = DATEDIFF(COALESCE(:rental_end_date, rental_end_date), COALESCE(:rental_start_date, rental_start_date)) + 1")
    
    if updates:
        sql = f"UPDATE event_boards SET {', '.join(updates)}, updated_at = NOW() WHERE id = :id"
        db.execute(text(sql), params)
        db.commit()
    
    return await get_board(board_id, db=db, token=token)

@router.delete("/boards/{board_id}")
async def delete_board(
    board_id: str,
    db: Session = Depends(get_rh_db),
    token: str = Depends(get_token_from_header)
):
    """Видалити мудборд"""
    customer = get_current_customer(token, db)
    
    result = db.execute(text("""
        DELETE FROM event_boards WHERE id = :id AND customer_id = :customer_id
    """), {"id": board_id, "customer_id": customer["customer_id"]})
    db.commit()
    
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Board not found")
    
    logger.info(f"✅ Event board deleted: {board_id}")
    return {"message": "Board deleted"}

# ============================================================================
# BOARD ITEMS ENDPOINTS
# ============================================================================

@router.post("/boards/{board_id}/items")
async def add_item_to_board(
    board_id: str,
    data: EventBoardItemCreate,
    db: Session = Depends(get_rh_db),
    token: str = Depends(get_token_from_header)
):
    """Додати товар до мудборду"""
    customer = get_current_customer(token, db)
    
    # Перевірити права на board
    board_result = db.execute(text("""
        SELECT id, rental_start_date, rental_end_date, rental_days 
        FROM event_boards WHERE id = :id AND customer_id = :customer_id
    """), {"id": board_id, "customer_id": customer["customer_id"]})
    board = board_result.fetchone()
    
    if not board:
        raise HTTPException(status_code=404, detail="Board not found")
    
    # Перевірити товар
    product_result = db.execute(text("""
        SELECT product_id, rental_price FROM products WHERE product_id = :id
    """), {"id": data.product_id})
    product = product_result.fetchone()
    
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    # Перевірити чи вже є в борді
    existing = db.execute(text("""
        SELECT id, quantity FROM event_board_items WHERE board_id = :board_id AND product_id = :product_id
    """), {"board_id": board_id, "product_id": data.product_id})
    existing_item = existing.fetchone()
    
    if existing_item:
        # Оновити кількість
        new_qty = existing_item[1] + data.quantity
        db.execute(text("""
            UPDATE event_board_items SET quantity = :qty, notes = COALESCE(:notes, notes)
            WHERE id = :id
        """), {"id": existing_item[0], "qty": new_qty, "notes": data.notes})
        item_id = existing_item[0]
    else:
        # Створити новий item
        item_id = str(uuid.uuid4())
        db.execute(text("""
            INSERT INTO event_board_items (id, board_id, product_id, quantity, notes, section)
            VALUES (:id, :board_id, :product_id, :quantity, :notes, :section)
        """), {
            "id": item_id,
            "board_id": board_id,
            "product_id": data.product_id,
            "quantity": data.quantity,
            "notes": data.notes,
            "section": data.section
        })
    
    # Оновити estimated_total
    if product[1] and board[3]:
        db.execute(text("""
            UPDATE event_boards 
            SET estimated_total = (
                SELECT COALESCE(SUM(ebi.quantity * p.rental_price * :days), 0)
                FROM event_board_items ebi
                JOIN products p ON ebi.product_id = p.product_id
                WHERE ebi.board_id = :board_id
            )
            WHERE id = :board_id
        """), {"board_id": board_id, "days": board[3]})
    
    # Створити soft reservation якщо є дати
    if board[1] and board[2]:
        expires_at = datetime.utcnow() + timedelta(minutes=30)
        db.execute(text("""
            INSERT INTO event_soft_reservations (id, board_id, product_id, quantity, reserved_from, reserved_until, expires_at, customer_id, status)
            VALUES (:id, :board_id, :product_id, :quantity, :reserved_from, :reserved_until, :expires_at, :customer_id, 'active')
            ON DUPLICATE KEY UPDATE quantity = :quantity, expires_at = :expires_at
        """), {
            "id": str(uuid.uuid4()),
            "board_id": board_id,
            "product_id": data.product_id,
            "quantity": data.quantity,
            "reserved_from": board[1],
            "reserved_until": board[2],
            "expires_at": expires_at,
            "customer_id": customer["customer_id"]
        })
    
    db.commit()
    
    logger.info(f"✅ Item added to board: {board_id}, product: {data.product_id}")
    
    return {"id": item_id, "product_id": data.product_id, "quantity": data.quantity}

@router.patch("/boards/{board_id}/items/{item_id}")
async def update_board_item(
    board_id: str,
    item_id: str,
    data: EventBoardItemUpdate,
    db: Session = Depends(get_rh_db),
    token: str = Depends(get_token_from_header)
):
    """Оновити товар в мудборді"""
    customer = get_current_customer(token, db)
    
    # Перевірити права
    board_result = db.execute(text("""
        SELECT eb.id FROM event_boards eb
        JOIN event_board_items ebi ON eb.id = ebi.board_id
        WHERE eb.id = :board_id AND eb.customer_id = :customer_id AND ebi.id = :item_id
    """), {"board_id": board_id, "customer_id": customer["customer_id"], "item_id": item_id})
    
    if not board_result.fetchone():
        raise HTTPException(status_code=404, detail="Item not found")
    
    updates = []
    params = {"id": item_id}
    
    if data.quantity is not None:
        updates.append("quantity = :quantity")
        params["quantity"] = data.quantity
    if data.notes is not None:
        updates.append("notes = :notes")
        params["notes"] = data.notes
    if data.section is not None:
        updates.append("section = :section")
        params["section"] = data.section
    
    if updates:
        sql = f"UPDATE event_board_items SET {', '.join(updates)} WHERE id = :id"
        db.execute(text(sql), params)
        db.commit()
    
    return {"id": item_id, "updated": True}

@router.delete("/boards/{board_id}/items/{item_id}")
async def delete_board_item(
    board_id: str,
    item_id: str,
    db: Session = Depends(get_rh_db),
    token: str = Depends(get_token_from_header)
):
    """Видалити товар з мудборду"""
    customer = get_current_customer(token, db)
    
    # Отримати product_id перед видаленням
    item_result = db.execute(text("""
        SELECT ebi.product_id FROM event_board_items ebi
        JOIN event_boards eb ON ebi.board_id = eb.id
        WHERE ebi.id = :item_id AND eb.id = :board_id AND eb.customer_id = :customer_id
    """), {"item_id": item_id, "board_id": board_id, "customer_id": customer["customer_id"]})
    item = item_result.fetchone()
    
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    
    # Видалити soft reservation
    db.execute(text("""
        DELETE FROM event_soft_reservations WHERE board_id = :board_id AND product_id = :product_id
    """), {"board_id": board_id, "product_id": item[0]})
    
    # Видалити item
    db.execute(text("DELETE FROM event_board_items WHERE id = :id"), {"id": item_id})
    db.commit()
    
    logger.info(f"✅ Item deleted from board: {board_id}")
    return {"message": "Item deleted"}

# ============================================================================
# CONVERT TO ORDER
# ============================================================================

@router.post("/boards/{board_id}/convert-to-order")
async def convert_to_order(
    board_id: str,
    data: OrderCreate,
    db: Session = Depends(get_rh_db),
    token: str = Depends(get_token_from_header)
):
    """
    Конвертувати мудборд у замовлення RentalHub
    
    Використовує нову архітектуру client_users/payer_profiles:
    - Створює/знаходить client_user по email
    - Прив'язує замовлення до client_user_id
    - payer_profile_id = NULL або pending (менеджер вибере пізніше)
    
    Замовлення з Ivent-tool мають префікс #IT-XXXX для розрізнення від:
    - #OC-XXXX - замовлення з OpenCart (старий сайт)
    - #ORD-XXXX - замовлення створені вручну в RentalHub
    """
    import traceback
    
    try:
        customer = get_current_customer(token, db)
        logger.info(f"[convert-to-order] Customer: {customer.get('customer_id')}, Board: {board_id}")
        
        # Отримати board - використовуємо правильні імена колонок з таблиці event_boards
        board_result = db.execute(text("""
            SELECT id, customer_id, board_name, notes, event_date, 
                   rental_start_date, rental_end_date, rental_days,
                   status, created_at, updated_at, converted_to_order_id,
                   event_type
            FROM event_boards 
            WHERE id = :id AND customer_id = :customer_id
        """), {"id": board_id, "customer_id": customer["customer_id"]})
        board_row = board_result.fetchone()
        
        if not board_row:
            logger.warning(f"[convert-to-order] Board not found: {board_id}")
            raise HTTPException(status_code=404, detail="Board not found")
        
        # Конвертуємо в dict для зручності
        board = {
            "id": board_row[0],
            "customer_id": board_row[1],
            "name": board_row[2],  # board_name - назва події/мудборду
            "notes": board_row[3],  # нотатки мудборду
            "event_date": board_row[4],
            "rental_start_date": board_row[5],
            "rental_end_date": board_row[6],
            "rental_days": board_row[7],
            "status": board_row[8],
            "converted_to_order_id": board_row[11],
            "event_type": board_row[12]  # тип події з мудборду
        }
        
        # ========================================
        # АВТОМАТИЧНЕ ЗАПОВНЕННЯ ДАНИХ
        # ========================================
        
        # Email: завжди з профілю (авторизований користувач)
        email = customer.get("email", "")
        email_normalized = email.lower().strip() if email else ""
        
        # Ім'я клієнта: з запиту або з профілю event_customer
        customer_name = data.customer_name
        if not customer_name:
            firstname = customer.get("firstname", "")
            lastname = customer.get("lastname", "")
            customer_name = f"{firstname} {lastname}".strip() or "Клієнт EventTool"
        
        # Телефон: з запиту або з профілю
        phone = data.phone or customer.get("telephone", "")
        
        # ========================================
        # RESOLVE/CREATE client_user
        # ========================================
        client_user_id = None
        if email_normalized:
            # Шукаємо існуючого клієнта
            client_check = db.execute(text("""
                SELECT id FROM client_users WHERE email_normalized = :email
            """), {"email": email_normalized}).fetchone()
            
            if client_check:
                client_user_id = client_check[0]
                logger.info(f"[convert-to-order] Found existing client_user: {client_user_id}")
            else:
                # Створюємо нового клієнта
                db.execute(text("""
                    INSERT INTO client_users (email, email_normalized, full_name, phone, source)
                    VALUES (:email, :email_norm, :name, :phone, 'events')
                """), {
                    "email": email,
                    "email_norm": email_normalized,
                    "name": customer_name,
                    "phone": phone
                })
                db.commit()
                
                client_user_id = db.execute(text("""
                    SELECT id FROM client_users WHERE email_normalized = :email
                """), {"email": email_normalized}).fetchone()[0]
                
                logger.info(f"[convert-to-order] Created new client_user: {client_user_id}")
        
        # Назва події: з мудборду (board_name)
        event_name = board["name"]
        
        # Дата події: з мудборду
        event_date = board["event_date"]
        
        logger.info(f"[convert-to-order] Auto-filled: name={customer_name}, phone={phone}, event={event_name}")
        
        # ====== Перевірка наявності підписаного річного договору ======
        if client_user_id and not _has_valid_signed_agreement(db, client_user_id):
            logger.warning(f"[convert-to-order] No signed agreement for client_user {client_user_id}")
            raise HTTPException(
                status_code=412,
                detail={
                    "code": "AGREEMENT_REQUIRED",
                    "message": "Перед оформленням замовлення підпишіть річний договір у кабінеті (вкладка «Договір»).",
                },
            )

        if board["converted_to_order_id"]:
            raise HTTPException(status_code=400, detail="Board already converted to order")
        
        if not board["rental_start_date"] or not board["rental_end_date"]:
            raise HTTPException(status_code=400, detail="Rental dates required. Please set rental period first.")
    
        # Отримати items (з повним полем застави)
        items_result = db.execute(text("""
            SELECT ebi.product_id, ebi.quantity, p.rental_price, p.name, p.image_url, p.sku,
                   COALESCE(p.deposit, p.price, 0) AS deposit_each
            FROM event_board_items ebi
            JOIN products p ON ebi.product_id = p.product_id
            WHERE ebi.board_id = :board_id
        """), {"board_id": board_id})
        items = items_result.fetchall()
        
        if not items:
            raise HTTPException(status_code=400, detail="Board has no items")
        
        # Розрахувати rental_days за правилами Farfor (єдине джерело правди)
        rental_days = _calc_days(board["rental_start_date"], board["rental_end_date"]) or 1
        total_price = sum(float(item[2] or 0) * item[1] * rental_days for item in items)
        # Застава = сума deposit товарів (як у RentalHub)
        deposit_amount = sum(float(item[6] or 0) * item[1] for item in items)
        
        # Генерувати order_number з префіксом IT- для Ivent-tool
        # Починаємо з 10000 для IT замовлень
        max_it_result = db.execute(text("""
            SELECT MAX(CAST(SUBSTRING(order_number, 4) AS UNSIGNED)) 
            FROM orders 
            WHERE order_number LIKE 'IT-%'
        """))
        max_it_num = max_it_result.fetchone()[0] or 9999
        new_it_number = max(max_it_num + 1, 10000)
        
        # Отримуємо MAX order_id для нового запису
        max_id_result = db.execute(text("SELECT MAX(order_id) FROM orders"))
        max_id = max_id_result.fetchone()[0] or 0
        new_order_id = max_id + 1
        
        order_number = f"IT-{new_it_number}"  # IT = Ivent-Tool
        
        logger.info(f"[convert-to-order] Creating order {order_number} (id={new_order_id}, client_user_id={client_user_id})")
        
        # Підготувати notes - простий формат
        notes_parts = []
        
        # Джерело та мудборд
        notes_parts.append("[Джерело: Ivent-tool]")
        notes_parts.append(f"Мудборд: {board['name']}")
        
        # Тип платника (поки в notes, payer_profile_id буде вибрано менеджером)
        payer_labels = {
            'individual': 'Фізична особа',
            'fop': 'ФОП',
            'company': 'Юридична особа'
        }
        notes_parts.append(f"Тип платника (вказано клієнтом): {payer_labels.get(data.payer_type, data.payer_type)}")
        
        # Нотатки з мудборду
        if board.get("notes"):
            notes_parts.append(f"---\nНотатки мудборду: {board['notes']}")
        
        # Коментар клієнта в кінці
        if data.customer_comment:
            notes_parts.append(f"---\nКоментар клієнта: {data.customer_comment}")
        
        notes_text = "\n".join(notes_parts) if notes_parts else None
        
        # Створити order в RentalHub — динамічний INSERT тільки з колонок що існують
        # (різні версії БД можуть мати різний набір колонок)
        order_cols_rows = db.execute(text("SHOW COLUMNS FROM orders")).fetchall()
        order_cols = {r[0] for r in order_cols_rows}

        # Кандидати: ключ_колонки -> значення
        candidate_values = {
            "order_id": new_order_id,
            "order_number": order_number,
            "status": "awaiting_customer",
            "rental_start_date": board["rental_start_date"],
            "rental_end_date": board["rental_end_date"],
            "rental_days": rental_days,
            "event_date": event_date,
            "event_location": event_name,
            "total_price": total_price,
            "total_amount": total_price,  # альтернативна назва
            "deposit_amount": deposit_amount,
            "customer_name": customer_name,
            "customer_phone": phone,
            "customer_email": email,
            "notes": notes_text,
            "source": "event_tool",
            "event_board_id": board_id,
            "client_user_id": client_user_id,
            "pickup_time_slot": data.pickup_time_slot,
            "return_time": data.return_time or "17:00",
        }

        # Залишаємо тільки ті ключі, для яких реально існує колонка в БД
        use_cols = [c for c in candidate_values if c in order_cols]
        params = {c: candidate_values[c] for c in use_cols}

        col_list_sql = ", ".join(use_cols + (["created_at"] if "created_at" in order_cols else []))
        val_list_sql = ", ".join(f":{c}" for c in use_cols) + (", NOW()" if "created_at" in order_cols else "")

        insert_sql = f"INSERT INTO orders ({col_list_sql}) VALUES ({val_list_sql})"
        logger.info(f"[convert-to-order] Dynamic INSERT cols: {use_cols}")
        db.execute(text(insert_sql), params)
        
        # Створити order_items
        for item in items:
            db.execute(text("""
                INSERT INTO order_items (order_id, product_id, product_name, quantity, price, total_rental, image_url)
                VALUES (:order_id, :product_id, :name, :quantity, :price, :total, :image_url)
            """), {
                "order_id": new_order_id,
                "product_id": item[0],
                "name": item[3],
                "quantity": item[1],
                "price": float(item[2] or 0),
                "total": float(item[2] or 0) * item[1] * rental_days,
                "image_url": item[4]
            })
        
        # Записати в order_internal_notes якщо є коментар клієнта (як в sync з OpenCart)
        if data.customer_comment:
            try:
                db.execute(text("""
                    INSERT INTO order_internal_notes 
                    (order_id, user_id, user_name, message, created_at)
                    VALUES (:order_id, NULL, :user_name, :message, NOW())
                """), {
                    "order_id": new_order_id,
                    "user_name": "💬 Коментар клієнта (Ivent-tool)",
                    "message": data.customer_comment
                })
            except Exception as e:
                logger.warning(f"Could not save internal note: {e}")
        
        # Записати в order_lifecycle
        try:
            db.execute(text("""
                INSERT INTO order_lifecycle (order_id, stage, notes, created_by, created_at)
                VALUES (:order_id, 'created', :notes, :created_by, NOW())
            """), {
                "order_id": new_order_id,
                "notes": f"Замовлення створено з Ivent-tool (мудборд: {board['name']})",
                "created_by": f"{customer['firstname']} {customer.get('lastname', '')} (декоратор)"
            })
        except Exception as e:
            logger.warning(f"Could not save lifecycle: {e}")
        
        # Видалити soft reservations
        db.execute(text("DELETE FROM event_soft_reservations WHERE board_id = :board_id"), {"board_id": board_id})
        
        # Оновити board
        db.execute(text("""
            UPDATE event_boards SET converted_to_order_id = :order_id, status = 'converted', updated_at = NOW()
            WHERE id = :board_id
        """), {"order_id": new_order_id, "board_id": board_id})
        
        db.commit()
        
        logger.info(f"✅ Board {board_id} converted to order {order_number} (Ivent-tool)")
        
        return {
            "order_id": new_order_id,
            "order_number": order_number,
            "total_price": total_price,
            "deposit_amount": deposit_amount,
            "rental_days": rental_days,
            "items_count": len(items),
            "status": "awaiting_customer",
            "source": "event_tool",
            "message": f"Замовлення {order_number} успішно створено!"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        trace_id = f"ERR-{board_id[:8]}-{datetime.now().strftime('%H%M%S')}"
        # Витягуємо найглибший рядок traceback з нашого файлу — для зручної діагностики
        tb_lines = traceback.format_exc().splitlines()
        our_file_lines = [ln for ln in tb_lines if 'event_tool.py' in ln]
        last_our_line = our_file_lines[-1].strip() if our_file_lines else ''
        logger.error(f"[convert-to-order] {trace_id}: {str(e)}\nLast app line: {last_our_line}\n{traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "convert_failed",
                "trace_id": trace_id,
                "message": f"Помилка: {str(e)[:150]}",
                "details": f"{str(e)} | {last_our_line}",
            }
        )

# ============================================================================
# КАБІНЕТ КЛІЄНТА — список замовлень
# ============================================================================

@router.get("/orders")
async def get_my_orders(
    db: Session = Depends(get_rh_db),
    token: str = Depends(get_token_from_header)
):
    """Список замовлень поточного авторизованого клієнта Event Tool"""
    try:
        customer = get_current_customer(token, db)
        email = (customer.get("email") or "").lower().strip()
        if not email:
            return []

        # Знайти client_user_id за email
        cu = db.execute(
            text("SELECT id FROM client_users WHERE email_normalized = :e LIMIT 1"),
            {"e": email}
        ).fetchone()
        if not cu:
            return []
        client_user_id = cu[0]

        # Визначаємо які колонки реально існують у orders
        cols_rows = db.execute(text("SHOW COLUMNS FROM orders")).fetchall()
        existing_cols = {r[0] for r in cols_rows}

        def col(name, default="NULL"):
            return name if name in existing_cols else default

        select_sql = f"""
            SELECT
                order_id,
                {col('order_number', "''")} AS order_number,
                {col('status', "''")} AS status,
                {col('rental_start_date')} AS rental_start_date,
                {col('rental_end_date')} AS rental_end_date,
                {col('rental_days', '0')} AS rental_days,
                {col('event_date')} AS event_date,
                {col('event_location', "''")} AS event_location,
                {col('total_price', col('total_amount', '0'))} AS total_price,
                {col('deposit_amount', '0')} AS deposit_amount,
                {col('payment_status', "''")} AS payment_status,
                {col('source', "''")} AS source,
                {col('created_at')} AS created_at,
                {col('notes', "''")} AS notes,
                {col('customer_name', "''")} AS customer_name,
                {col('updated_at')} AS updated_at,
                {col('issue_date')} AS issue_date,
                {col('return_date')} AS return_date,
                {col('service_fee', '0')} AS service_fee,
                {col('discount_amount', '0')} AS discount_amount,
                {col('manager_comment', "''")} AS manager_comment
            FROM orders
            WHERE {col('client_user_id', 'NULL')} = :cuid
               OR ({col('customer_email', "''")} = :email AND :email <> '')
            ORDER BY created_at DESC
            LIMIT 100
        """

        rows = db.execute(text(select_sql), {"cuid": client_user_id, "email": email}).fetchall()

        result = []
        for r in rows:
            order_id = r[0]
            try:
                items_count = db.execute(
                    text("SELECT COUNT(*) FROM order_items WHERE order_id = :oid"),
                    {"oid": order_id}
                ).scalar() or 0
            except Exception:
                items_count = 0

            # ✅ Прогрес комплектації з issue_cards
            packing_progress = 0
            try:
                ic_row = db.execute(
                    text("SELECT items FROM issue_cards WHERE order_id = :oid"),
                    {"oid": order_id}
                ).fetchone()
                if ic_row and ic_row[0]:
                    import json
                    ic_items = json.loads(ic_row[0]) if isinstance(ic_row[0], str) else ic_row[0]
                    if ic_items:
                        total_qty = sum(it.get('qty', 1) for it in ic_items)
                        picked_qty = sum(it.get('picked_qty', 0) for it in ic_items)
                        if total_qty > 0:
                            packing_progress = int((picked_qty / total_qty) * 100)
            except Exception:
                packing_progress = 0

            # ✅ Скільки клієнт сплатив (з fin_transactions)
            paid_rent = 0.0
            paid_deposit = 0.0
            try:
                pay_row = db.execute(text("""
                    SELECT
                        COALESCE(SUM(CASE WHEN tx_type IN ('rent_payment', 'additional_payment') THEN amount ELSE 0 END), 0),
                        COALESCE(SUM(CASE WHEN tx_type = 'deposit_payment' THEN amount ELSE 0 END), 0)
                    FROM fin_transactions
                    WHERE entity_type = 'order' AND entity_id = :oid
                """), {"oid": order_id}).fetchone()
                if pay_row:
                    paid_rent = float(pay_row[0] or 0)
                    paid_deposit = float(pay_row[1] or 0)
            except Exception:
                pass

            total_rental = float(r[8] or 0)
            service_fee = float(r[18] or 0)
            discount_amount = float(r[19] or 0)
            total_to_pay = round(max(0, total_rental - discount_amount) + service_fee, 2)

            result.append({
                "order_id": order_id,
                "order_number": r[1],
                "status": r[2],
                "rental_start_date": r[3].isoformat() if r[3] else None,
                "rental_end_date": r[4].isoformat() if r[4] else None,
                "rental_days": int(r[5] or 0),
                "event_date": r[6].isoformat() if r[6] else None,
                "event_location": r[7],
                "total_price": total_rental,
                "deposit_amount": float(r[9] or 0),
                "payment_status": r[10] or "",
                "source": r[11] or "",
                "created_at": r[12].isoformat() if r[12] else None,
                "notes": r[13] or "",
                "customer_name": r[14] or "",
                "items_count": items_count,
                # Нові поля для синхронізації з RentalHub
                "updated_at": r[15].isoformat() if r[15] else None,
                "issue_date": r[16].isoformat() if r[16] else None,
                "return_date": r[17].isoformat() if r[17] else None,
                "service_fee": service_fee,
                "discount_amount": discount_amount,
                "total_to_pay": total_to_pay,
                "manager_comment": r[20] or "",
                "packing_progress": packing_progress,
                "paid_rent": paid_rent,
                "paid_deposit": paid_deposit,
            })
        return result
    except Exception as e:
        # Не валимо API — повертаємо порожньо щоб UI не падав
        import traceback
        traceback.print_exc()
        print(f"[get_my_orders] Error: {e}")
        return []


@router.get("/orders/{order_id}")
async def get_my_order_details(
    order_id: int,
    db: Session = Depends(get_rh_db),
    token: str = Depends(get_token_from_header)
):
    """Деталі окремого замовлення (тільки своє)"""
    try:
        customer = get_current_customer(token, db)
        email = (customer.get("email") or "").lower().strip()

        cu = db.execute(
            text("SELECT id FROM client_users WHERE email_normalized = :e LIMIT 1"),
            {"e": email}
        ).fetchone()
        client_user_id = cu[0] if cu else None

        # Колонки orders
        cols_rows = db.execute(text("SHOW COLUMNS FROM orders")).fetchall()
        existing_cols = {r[0] for r in cols_rows}
        def col(name, default="NULL"):
            return name if name in existing_cols else default

        sql = f"""
            SELECT
                order_id,
                {col('order_number', "''")} AS order_number,
                {col('status', "''")} AS status,
                {col('rental_start_date')} AS rental_start_date,
                {col('rental_end_date')} AS rental_end_date,
                {col('rental_days', '0')} AS rental_days,
                {col('event_date')} AS event_date,
                {col('event_location', "''")} AS event_location,
                {col('total_price', col('total_amount', '0'))} AS total_price,
                {col('deposit_amount', '0')} AS deposit_amount,
                {col('payment_status', "''")} AS payment_status,
                {col('source', "''")} AS source,
                {col('created_at')} AS created_at,
                {col('notes', "''")} AS notes,
                {col('customer_name', "''")} AS customer_name,
                {col('customer_phone', "''")} AS customer_phone,
                {col('customer_email', "''")} AS customer_email,
                {col('updated_at')} AS updated_at,
                {col('issue_date')} AS issue_date,
                {col('return_date')} AS return_date,
                {col('service_fee', '0')} AS service_fee,
                {col('discount_amount', '0')} AS discount_amount,
                {col('manager_comment', "''")} AS manager_comment,
                {col('pickup_time_slot', "''")} AS pickup_time_slot,
                {col('return_time', "''")} AS return_time
            FROM orders
            WHERE order_id = :oid
              AND ({col('client_user_id', 'NULL')} = :cuid OR {col('customer_email', "''")} = :email)
        """
        order_row = db.execute(text(sql), {"oid": order_id, "cuid": client_user_id, "email": email}).fetchone()
        if not order_row:
            raise HTTPException(status_code=404, detail="Order not found")

        # Items — з джойном до products щоб дістати фото, SKU, актуальну ціну
        item_cols_rows = db.execute(text("SHOW COLUMNS FROM order_items")).fetchall()
        item_cols = {r[0] for r in item_cols_rows}
        def ic(name, default="NULL"):
            return f"oi.{name}" if name in item_cols else default

        # Знаходимо назву колонки з фото в products (image_url або image)
        prod_cols_rows = db.execute(text("SHOW COLUMNS FROM products")).fetchall()
        prod_cols = {r[0] for r in prod_cols_rows}
        p_img_col = "p.image_url" if "image_url" in prod_cols else ("p.image" if "image" in prod_cols else "''")
        p_sku_col = "p.sku" if "sku" in prod_cols else "''"
        p_name_col = "p.name" if "name" in prod_cols else "''"
        p_rental_col = "p.rental_price" if "rental_price" in prod_cols else "0"
        p_deposit_col = "p.deposit" if "deposit" in prod_cols else "0"
        p_color_col = "p.color" if "color" in prod_cols else "''"
        p_material_col = "p.material" if "material" in prod_cols else "''"

        items_sql = f"""
            SELECT
                {ic('product_id', '0')} AS product_id,
                {ic('product_name', "''")} AS product_name,
                {ic('quantity', '0')} AS quantity,
                {ic('price', '0')} AS price_per_day,
                {ic('total_rental', '0')} AS total_rental,
                {ic('total_deposit', '0')} AS total_deposit,
                {ic('image_url', "''")} AS oi_image_url,
                {p_sku_col} AS sku,
                {p_name_col} AS p_name,
                {p_img_col} AS p_image_url,
                {p_rental_col} AS p_rental_price,
                {p_deposit_col} AS p_deposit,
                {p_color_col} AS color,
                {p_material_col} AS material
            FROM order_items oi
            LEFT JOIN products p ON oi.product_id = p.product_id
            WHERE oi.order_id = :oid
        """
        items_rows = db.execute(text(items_sql), {"oid": order_id}).fetchall()

        # Нормалізуємо URL картинок — додаємо префікс /uploads/ якщо потрібно
        def normalize_image_url(url: str) -> str:
            if not url:
                return ""
            url = str(url).strip()
            if url.startswith("http://") or url.startswith("https://"):
                return url
            if url.startswith("/"):
                return url
            # Відносний шлях — додаємо /uploads/
            return f"/uploads/{url}"

        # ✅ Прогрес комплектації з issue_cards
        packing_progress = 0
        try:
            ic_row = db.execute(
                text("SELECT items FROM issue_cards WHERE order_id = :oid"),
                {"oid": order_id}
            ).fetchone()
            if ic_row and ic_row[0]:
                import json
                ic_items = json.loads(ic_row[0]) if isinstance(ic_row[0], str) else ic_row[0]
                if ic_items:
                    total_qty = sum(it.get('qty', 1) for it in ic_items)
                    picked_qty = sum(it.get('picked_qty', 0) for it in ic_items)
                    if total_qty > 0:
                        packing_progress = int((picked_qty / total_qty) * 100)
        except Exception:
            packing_progress = 0

        # ✅ Скільки клієнт сплатив
        paid_rent = 0.0
        paid_deposit = 0.0
        try:
            pay_row = db.execute(text("""
                SELECT
                    COALESCE(SUM(CASE WHEN tx_type IN ('rent_payment', 'additional_payment') THEN amount ELSE 0 END), 0),
                    COALESCE(SUM(CASE WHEN tx_type = 'deposit_payment' THEN amount ELSE 0 END), 0)
                FROM fin_transactions
                WHERE entity_type = 'order' AND entity_id = :oid
            """), {"oid": order_id}).fetchone()
            if pay_row:
                paid_rent = float(pay_row[0] or 0)
                paid_deposit = float(pay_row[1] or 0)
        except Exception:
            pass

        total_rental = float(order_row[8] or 0)
        service_fee = float(order_row[20] or 0)
        discount_amount = float(order_row[21] or 0)
        total_to_pay = round(max(0, total_rental - discount_amount) + service_fee, 2)

        # Якщо є дати — рахуємо за правилами Farfor (override застарілого rental_days з БД)
        _calc = _calc_days(order_row[3], order_row[4])
        rental_days_calc = _calc if _calc > 0 else int(order_row[5] or 0)

        return {
            "order_id": order_row[0],
            "order_number": order_row[1],
            "status": order_row[2],
            "rental_start_date": order_row[3].isoformat() if order_row[3] else None,
            "rental_end_date": order_row[4].isoformat() if order_row[4] else None,
            "rental_days": rental_days_calc,
            "event_date": order_row[6].isoformat() if order_row[6] else None,
            "event_location": order_row[7],
            "total_price": total_rental,
            "deposit_amount": float(order_row[9] or 0),
            "payment_status": order_row[10] or "",
            "source": order_row[11] or "",
            "created_at": order_row[12].isoformat() if order_row[12] else None,
            "notes": order_row[13] or "",
            "customer_name": order_row[14] or "",
            "customer_phone": order_row[15] or "",
            "customer_email": order_row[16] or "",
            # Нові поля для синхронізації з RentalHub
            "updated_at": order_row[17].isoformat() if order_row[17] else None,
            "issue_date": order_row[18].isoformat() if order_row[18] else None,
            "return_date": order_row[19].isoformat() if order_row[19] else None,
            "service_fee": service_fee,
            "discount_amount": discount_amount,
            "total_to_pay": total_to_pay,
            "manager_comment": order_row[22] or "",
            "pickup_time_slot": order_row[23] or "",
            "return_time": order_row[24] or "17:00",
            "packing_progress": packing_progress,
            "paid_rent": paid_rent,
            "paid_deposit": paid_deposit,
            "items": [
                {
                    "product_id": ir[0],
                    "product_name": ir[1] or ir[8] or '',
                    "quantity": int(ir[2] or 0),
                    "price_per_day": float(ir[3] or 0),
                    "total_rental": float(ir[4] or 0),
                    "total_deposit": float(ir[5] or 0),
                    "image_url": normalize_image_url(ir[9] or ir[6] or ''),
                    "sku": ir[7] or '',
                    "deposit_per_unit": float(ir[11] or 0),
                    "color": ir[12] or '',
                    "material": ir[13] or '',
                }
                for ir in items_rows
            ],
        }
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"[get_my_order_details] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/orders/{order_id}/timeline")
async def get_my_order_timeline(
    order_id: int,
    db: Session = Depends(get_rh_db),
    token: str = Depends(get_token_from_header)
):
    """
    Історія змін замовлення з order_lifecycle — клієнт бачить
    всі дії менеджера (статуси, коментарі) в хронологічному порядку.
    """
    try:
        customer = get_current_customer(token, db)
        email = (customer.get("email") or "").lower().strip()
        cu = db.execute(
            text("SELECT id FROM client_users WHERE email_normalized = :e LIMIT 1"),
            {"e": email}
        ).fetchone()
        client_user_id = cu[0] if cu else None

        # Перевірка приналежності замовлення клієнту
        cols_rows = db.execute(text("SHOW COLUMNS FROM orders")).fetchall()
        existing_cols = {r[0] for r in cols_rows}
        cuid_col = "client_user_id" if "client_user_id" in existing_cols else "NULL"
        email_col = "customer_email" if "customer_email" in existing_cols else "''"
        own = db.execute(text(f"""
            SELECT order_id FROM orders WHERE order_id = :oid
              AND ({cuid_col} = :cuid OR {email_col} = :email)
            LIMIT 1
        """), {"oid": order_id, "cuid": client_user_id, "email": email}).fetchone()
        if not own:
            raise HTTPException(status_code=404, detail="Order not found")

        # Читаємо timeline (за наявності таблиці)
        try:
            lc_rows = db.execute(text("""
                SELECT stage, notes, created_by, created_by_name, created_at
                FROM order_lifecycle WHERE order_id = :oid ORDER BY created_at ASC
            """), {"oid": order_id}).fetchall()
        except Exception:
            lc_rows = []

        STAGE_LABELS = {
            "created": "Замовлення створено",
            "awaiting_customer": "Очікує підтвердження клієнта",
            "confirmed": "Підтверджено клієнтом",
            "preparation": "Передано на комплектацію",
            "ready_for_issue": "Готове до видачі",
            "issued": "Видано клієнту",
            "on_rent": "На оренді",
            "returned": "Повернуто",
            "completed": "Завершено",
            "cancelled": "Скасовано",
            "cancelled_by_client": "Скасовано клієнтом",
            "cancelled_by_manager": "Скасовано менеджером",
            "estimate_created": "Сформовано кошторис",
            "contract_created": "Сформовано договір",
            "invoice_created": "Сформовано рахунок",
            "document_signed": "Документ підписано",
        }

        return [
            {
                "stage": r[0],
                "stage_label": STAGE_LABELS.get(r[0], r[0]),
                "notes": r[1] or "",
                "actor": r[3] or r[2] or "Система",
                "created_at": r[4].isoformat() if r[4] else None,
            }
            for r in lc_rows
        ]
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        logger.error(f"[get_my_order_timeline] {e}")
        raise HTTPException(status_code=500, detail=str(e))



@router.get("/orders/{order_id}/estimate.html", response_class=HTMLResponse)
async def get_order_estimate_html(
    order_id: int,
    request: Request,
    db: Session = Depends(get_rh_db),
):
    """
    Попередній HTML-кошторис для клієнта.
    Auth: або Authorization header (Bearer), або ?token=... query (для прямого посилання з email).
    Клієнт може зберегти його як PDF через Ctrl+P → "Зберегти як PDF" у браузері.
    """
    # Дістаємо токен з header АБО query
    token = None
    auth = request.headers.get("Authorization")
    if auth and auth.startswith("Bearer "):
        token = auth.replace("Bearer ", "", 1).strip()
    if not token:
        token = request.query_params.get("token")
    if not token:
        raise HTTPException(401, "Token required")

    customer = get_current_customer(token, db)
    email = (customer.get("email") or "").lower().strip()

    # Деталі замовлення (через існуючий endpoint логіку — спрощений варіант)
    cols_rows = db.execute(text("SHOW COLUMNS FROM orders")).fetchall()
    existing_cols = {r[0] for r in cols_rows}
    def col(name, default="NULL"):
        return name if name in existing_cols else default

    sql = f"""
        SELECT
            order_id,
            {col('order_number', "''")} AS order_number,
            {col('status', "''")} AS status,
            {col('rental_start_date')} AS rental_start_date,
            {col('rental_end_date')} AS rental_end_date,
            {col('rental_days', '0')} AS rental_days,
            {col('event_date')} AS event_date,
            {col('total_price', col('total_amount', '0'))} AS total_price,
            {col('deposit_amount', '0')} AS deposit_amount,
            {col('customer_name', "''")} AS customer_name,
            {col('customer_phone', "''")} AS customer_phone,
            {col('customer_email', "''")} AS customer_email,
            {col('pickup_time_slot', "''")} AS pickup_time_slot,
            {col('return_time', "''")} AS return_time,
            {col('notes', "''")} AS notes
        FROM orders
        WHERE order_id = :oid
          AND ({col('customer_email', "''")} = :email)
    """
    o = db.execute(text(sql), {"oid": order_id, "email": email}).fetchone()
    if not o:
        raise HTTPException(404, "Order not found")

    items = db.execute(text("""
        SELECT product_name, quantity, price, total_rental, image_url
        FROM order_items WHERE order_id = :oid
    """), {"oid": order_id}).fetchall()

    rental_days = _calc_days(o[3], o[4]) or int(o[5] or 1)
    total_price = float(o[7] or 0)
    deposit = float(o[8] or 0)
    total_pay = total_price + deposit

    rows_html = ""
    for it in items:
        line_total = float(it[3] or 0)
        rows_html += f"""
        <tr>
          <td>{it[0] or ''}</td>
          <td style="text-align:center">{it[1] or 0}</td>
          <td style="text-align:right">₴{float(it[2] or 0):.2f}</td>
          <td style="text-align:right">{rental_days}</td>
          <td style="text-align:right;font-weight:600">₴{line_total:.2f}</td>
        </tr>"""

    pickup_str = f"{o[3]} {o[12] or ''}".strip() if o[3] else "—"
    return_str = f"{o[4]} до {o[13] or '17:00'}".strip() if o[4] else "—"

    html = f"""<!DOCTYPE html>
<html lang="uk">
<head>
<meta charset="UTF-8">
<title>Кошторис #{o[1] or o[0]}</title>
<style>
  @page {{ size: A4; margin: 18mm; }}
  body {{ font-family: -apple-system, 'Segoe UI', Roboto, sans-serif; color: #0f172a; max-width: 800px; margin: 20px auto; padding: 0 24px; line-height: 1.5; }}
  .head {{ display: flex; justify-content: space-between; align-items: flex-start; border-bottom: 2px solid #0a3d2e; padding-bottom: 16px; margin-bottom: 24px; }}
  h1 {{ font-size: 26px; color: #0a3d2e; margin: 0 0 6px; }}
  .muted {{ color: #64748b; font-size: 13px; }}
  .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 14px 28px; margin: 18px 0 28px; padding: 18px; background: #f8fafc; border-radius: 8px; }}
  .grid .label {{ font-size: 11px; text-transform: uppercase; letter-spacing: 0.6px; color: #94a3b8; margin-bottom: 4px; }}
  .grid .value {{ font-size: 14px; font-weight: 600; }}
  table {{ width: 100%; border-collapse: collapse; margin: 16px 0; }}
  th {{ background: #0a3d2e; color: #fff; padding: 10px 12px; text-align: left; font-size: 12px; }}
  td {{ padding: 10px 12px; border-bottom: 1px solid #e5e7eb; font-size: 13px; }}
  tfoot td {{ font-weight: 700; padding-top: 14px; border-top: 2px solid #0a3d2e; }}
  .pay {{ background: linear-gradient(135deg, #0a3d2e 0%, #145a45 100%); color: #fff; padding: 18px 24px; border-radius: 10px; margin-top: 24px; }}
  .pay .total {{ font-size: 32px; font-weight: 800; }}
  .pay .sub {{ font-size: 13px; opacity: 0.9; margin-top: 4px; }}
  .actions {{ margin: 28px 0 12px; text-align: center; }}
  .btn {{ display: inline-block; padding: 12px 28px; background: #0a3d2e; color: #fff; border-radius: 8px; text-decoration: none; font-weight: 600; cursor: pointer; border: none; font-size: 14px; }}
  @media print {{ .actions {{ display: none; }} body {{ margin: 0; }} }}
  .note {{ font-size: 12px; color: #64748b; margin-top: 18px; padding: 12px; background: #fef9e7; border-left: 3px solid #b08d2e; border-radius: 4px; }}
</style>
</head>
<body>
  <div class="head">
    <div>
      <h1>Кошторис #{o[1] or o[0]}</h1>
      <div class="muted">Попередній — менеджер уточнить фінальні умови</div>
    </div>
    <div style="text-align:right">
      <div style="font-weight:700;color:#0a3d2e">Farfor Decor</div>
      <div class="muted">farforrent.com.ua</div>
    </div>
  </div>

  <div class="grid">
    <div><div class="label">Клієнт</div><div class="value">{o[9] or '—'}</div></div>
    <div><div class="label">Телефон</div><div class="value">{o[10] or '—'}</div></div>
    <div><div class="label">Дата івенту</div><div class="value">{o[6] or '—'}</div></div>
    <div><div class="label">Діб оренди</div><div class="value">{rental_days}</div></div>
    <div><div class="label">Видача</div><div class="value">{pickup_str}</div></div>
    <div><div class="label">Повернення</div><div class="value">{return_str}</div></div>
  </div>

  <table>
    <thead>
      <tr><th>Найменування</th><th style="text-align:center">К-сть</th><th style="text-align:right">Ціна/доба</th><th style="text-align:right">Діб</th><th style="text-align:right">Сума</th></tr>
    </thead>
    <tbody>{rows_html}</tbody>
    <tfoot>
      <tr><td colspan="4" style="text-align:right">Оренда:</td><td style="text-align:right">₴{total_price:.2f}</td></tr>
      <tr><td colspan="4" style="text-align:right">Застава (повертається):</td><td style="text-align:right">₴{deposit:.2f}</td></tr>
    </tfoot>
  </table>

  <div class="pay">
    <div class="sub">До сплати при отриманні</div>
    <div class="total">₴{total_pay:.2f}</div>
    <div class="sub">Оренда ₴{total_price:.2f} + застава ₴{deposit:.2f}</div>
  </div>

  <div class="note">
    📌 Це <strong>попередній</strong> кошторис. Фінальну вартість підтвердить менеджер після перевірки наявності та погодження часу видачі.
    Застава повертається у повному обсязі при здачі товару у належному стані.
  </div>

  <div class="actions">
    <button class="btn" onclick="window.print()">🖨️ Зберегти / друкувати</button>
  </div>
</body>
</html>"""
    return HTMLResponse(content=html)


_DOC_LABELS_FOR_CLIENT = {
    "estimate": "Кошторис",
    "invoice_offer": "Рахунок-оферта",
    "invoice_legal": "Рахунок (ФОП/ТОВ)",
    "invoice_additional": "Додатковий рахунок",
    "contract_rent": "Договір оренди",
    "issue_act": "Акт видачі",
    "return_act": "Акт повернення",
    "deposit_settlement_act": "Акт врегулювання застави",
    "deposit_refund_act": "Акт повернення застави",
    "service_act": "Акт послуг",
    "goods_invoice": "Товарна накладна",
}


@router.get("/cabinet/documents")
async def get_cabinet_documents(
    db: Session = Depends(get_rh_db),
    token: str = Depends(get_token_from_header),
):
    """
    Перелік документів клієнта, прив'язаних до його замовлень.
    Тягне з існуючої таблиці `documents` (entity_type='order').
    Технічні документи (defect_act, picking_list тощо) виключаються.
    """
    customer = get_current_customer(token, db)
    email = (customer.get("email") or "").lower().strip()
    cuid = customer.get("customer_id") or customer.get("id")
    client_user_id = customer.get("client_user_id") or customer.get("id")

    # Lazy column add: first_viewed_at (для бейджа "Новий")
    _ensure_documents_first_viewed_column(db)

    allowed_types = list(_DOC_LABELS_FOR_CLIENT.keys())
    placeholders = ",".join([f":t{i}" for i in range(len(allowed_types))])
    params = {f"t{i}": t for i, t in enumerate(allowed_types)}
    params.update({"email": email, "cuid": cuid, "cuser": client_user_id})

    sql = f"""
        SELECT d.id, d.doc_type, d.doc_number, d.entity_id AS order_id,
               d.status, d.version, d.created_at, d.updated_at,
               d.signed_at, o.order_number, o.event_date,
               LENGTH(d.html_content) AS has_html,
               d.first_viewed_at
        FROM documents d
        INNER JOIN orders o ON o.order_id = d.entity_id
        WHERE d.entity_type = 'order'
          AND d.doc_type IN ({placeholders})
          AND (o.customer_email = :email OR o.client_user_id = :cuser OR o.customer_id = :cuid)
        ORDER BY d.created_at DESC
        LIMIT 200
    """
    rows = db.execute(text(sql), params).fetchall()
    return {
        "documents": [
            {
                "id": r[0],
                "doc_type": r[1],
                "doc_type_label": _DOC_LABELS_FOR_CLIENT.get(r[1], r[1]),
                "doc_number": r[2],
                "order_id": r[3],
                "order_number": r[9] or str(r[3]),
                "event_date": r[10].isoformat() if r[10] else None,
                "status": r[4],
                "version": r[5],
                "created_at": r[6].isoformat() if r[6] else None,
                "updated_at": r[7].isoformat() if r[7] else None,
                "signed_at": r[8].isoformat() if r[8] else None,
                "has_html": bool(r[11]),
                "first_viewed_at": r[12].isoformat() if r[12] else None,
                "is_new": r[12] is None,
            }
            for r in rows
        ]
    }


def _ensure_documents_first_viewed_column(db: Session) -> None:
    """Ідемпотентно додає колонку first_viewed_at до documents (для бейджа 'Новий')."""
    try:
        check = db.execute(text("""
            SELECT COUNT(*) FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'documents'
              AND COLUMN_NAME = 'first_viewed_at'
        """)).fetchone()[0]
        if not check:
            db.execute(text("ALTER TABLE documents ADD COLUMN first_viewed_at TIMESTAMP NULL"))
            db.commit()
    except Exception:
        db.rollback()


@router.get("/cabinet/notifications/unread")
async def get_cabinet_unread(
    db: Session = Depends(get_rh_db),
    token: str = Depends(get_token_from_header),
):
    """Лічильник нових (непереглянутих) документів. Використовується для бейджа на вкладці 'Документи'."""
    customer = get_current_customer(token, db)
    email = (customer.get("email") or "").lower().strip()
    cuid = customer.get("customer_id") or customer.get("id")
    client_user_id = customer.get("client_user_id") or customer.get("id")

    _ensure_documents_first_viewed_column(db)

    allowed_types = list(_DOC_LABELS_FOR_CLIENT.keys())
    placeholders = ",".join([f":t{i}" for i in range(len(allowed_types))])
    params = {f"t{i}": t for i, t in enumerate(allowed_types)}
    params.update({"email": email, "cuid": cuid, "cuser": client_user_id})

    sql = f"""
        SELECT COUNT(*)
        FROM documents d
        INNER JOIN orders o ON o.order_id = d.entity_id
        WHERE d.entity_type = 'order'
          AND d.doc_type IN ({placeholders})
          AND d.first_viewed_at IS NULL
          AND (o.customer_email = :email OR o.client_user_id = :cuser OR o.customer_id = :cuid)
    """
    cnt = db.execute(text(sql), params).fetchone()[0] or 0
    return {"new_documents": int(cnt)}


@router.get("/cabinet/documents/{doc_id}/view", response_class=HTMLResponse)
async def view_cabinet_document(
    doc_id: str,
    request: Request,
    db: Session = Depends(get_rh_db),
):
    """
    Перегляд документа клієнтом (HTML). Auth через Bearer header АБО ?token=
    Безпека: перевіряємо що документ належить ордеру цього клієнта.
    """
    token = None
    auth = request.headers.get("Authorization")
    if auth and auth.startswith("Bearer "):
        token = auth.replace("Bearer ", "", 1).strip()
    if not token:
        token = request.query_params.get("token")
    if not token:
        raise HTTPException(401, "Token required")

    customer = get_current_customer(token, db)
    email = (customer.get("email") or "").lower().strip()
    cuid = customer.get("customer_id") or customer.get("id")
    client_user_id = customer.get("client_user_id") or customer.get("id")

    row = db.execute(text("""
        SELECT d.id, d.doc_type, d.doc_number, d.html_content, d.status, d.version, o.order_number
        FROM documents d
        INNER JOIN orders o ON o.order_id = d.entity_id
        WHERE d.id = :did
          AND d.entity_type = 'order'
          AND (o.customer_email = :email OR o.client_user_id = :cuser OR o.customer_id = :cuid)
        LIMIT 1
    """), {"did": doc_id, "email": email, "cuid": cuid, "cuser": client_user_id}).fetchone()

    if not row:
        raise HTTPException(404, "Документ не знайдено")

    # Позначаємо документ як переглянутий (один раз) — для бейджа "Новий"
    try:
        db.execute(text("""
            UPDATE documents
            SET first_viewed_at = NOW()
            WHERE id = :did AND first_viewed_at IS NULL
        """), {"did": doc_id})
        db.commit()
    except Exception:
        db.rollback()

    label = _DOC_LABELS_FOR_CLIENT.get(row[1], row[1])
    title = f"{label} {row[2] or ''} (v{row[5]})"
    html_body = row[3] or "<p style='padding:40px;text-align:center;color:#94a3b8'>Документ ще не сформовано. Зачекайте, доки менеджер його підготує.</p>"

    # Якщо вже повний HTML doc — повертаємо як є (зазвичай так)
    if html_body and "<html" in html_body.lower():
        return HTMLResponse(content=html_body)

    # Інакше обгортаємо у мінімальний layout
    wrapped = f"""<!DOCTYPE html><html lang="uk"><head><meta charset="UTF-8">
<title>{title}</title>
<style>body{{font-family:-apple-system,'Segoe UI',Roboto,sans-serif;max-width:900px;margin:24px auto;padding:0 24px;color:#0f172a;line-height:1.55}}
@media print{{body{{margin:0}}}}
.actions{{margin:24px 0;text-align:center}}
.btn{{padding:12px 28px;background:#0a3d2e;color:#fff;border-radius:8px;border:none;cursor:pointer;font-weight:600}}
@media print{{.actions{{display:none}}}}
</style></head><body>
<h1 style="color:#0a3d2e;border-bottom:2px solid #0a3d2e;padding-bottom:8px">{title}</h1>
{html_body}
<div class="actions"><button class="btn" onclick="window.print()">Зберегти / друкувати</button></div>
</body></html>"""
    return HTMLResponse(content=wrapped)


@router.get("/cabinet/profile")
async def get_cabinet_profile(
    db: Session = Depends(get_rh_db),
    token: str = Depends(get_token_from_header),
):
    """Профіль клієнта для редагування у кабінеті."""
    customer = get_current_customer(token, db)
    cuid = customer.get("client_user_id") or customer.get("id") or customer.get("customer_id")
    row = db.execute(text("""
        SELECT id, email, phone, full_name, payer_type, tax_id, bank_details,
               company, instagram, preferred_contact, created_at
        FROM client_users WHERE id = :cid LIMIT 1
    """), {"cid": cuid}).fetchone()
    if not row:
        raise HTTPException(404, "Профіль не знайдено")
    return {
        "id": row[0],
        "email": row[1],
        "phone": row[2] or "",
        "full_name": row[3] or "",
        "payer_type": row[4] or "individual",
        "tax_id": row[5] or "",
        "bank_details": row[6] or {},
        "company": row[7] or "",
        "instagram": row[8] or "",
        "preferred_contact": row[9] or "",
        "created_at": row[10].isoformat() if row[10] else None,
    }


@router.put("/cabinet/profile")
async def update_cabinet_profile(
    payload: dict = Body(...),
    db: Session = Depends(get_rh_db),
    token: str = Depends(get_token_from_header),
):
    """Редагування профілю клієнтом. Email — заблоковано (для зміни — підтримка)."""
    customer = get_current_customer(token, db)
    cuid = customer.get("client_user_id") or customer.get("id") or customer.get("customer_id")

    ALLOWED = {"phone", "full_name", "payer_type", "tax_id", "bank_details",
               "company", "instagram", "preferred_contact"}
    updates = {k: v for k, v in payload.items() if k in ALLOWED}
    if not updates:
        raise HTTPException(400, "Немає полів для оновлення")

    if "payer_type" in updates and updates["payer_type"] not in ("individual", "fop", "fop_simple", "tov"):
        raise HTTPException(400, "Некоректний тип платника")

    if "bank_details" in updates and isinstance(updates["bank_details"], dict):
        import json as _json
        updates["bank_details"] = _json.dumps(updates["bank_details"], ensure_ascii=False)

    set_clause = ", ".join([f"{k} = :{k}" for k in updates.keys()])
    updates["cid"] = cuid
    db.execute(text(f"UPDATE client_users SET {set_clause}, updated_at = NOW() WHERE id = :cid"), updates)
    db.commit()
    return {"success": True, "message": "Профіль оновлено"}


_PAYER_EDITABLE = {
    "payer_type", "company_name", "edrpou", "iban", "bank_name",
    "director_name", "address", "phone", "email",
    "legal_name", "signatory_name", "signatory_basis",
    "email_for_docs", "phone_for_docs", "is_vat_payer", "tax_mode",
}


@router.get("/cabinet/payers")
async def list_cabinet_payers(
    db: Session = Depends(get_rh_db),
    token: str = Depends(get_token_from_header),
):
    """Список платників клієнта."""
    customer = get_current_customer(token, db)
    cuid = customer.get("client_user_id") or customer.get("id") or customer.get("customer_id")
    rows = db.execute(text("""
        SELECT pp.id, pp.payer_type, pp.company_name, pp.edrpou, pp.iban,
               pp.bank_name, pp.director_name, pp.address, pp.phone, pp.email,
               pp.legal_name, pp.signatory_name, pp.signatory_basis,
               pp.email_for_docs, pp.phone_for_docs, pp.is_vat_payer, pp.tax_mode,
               pp.is_active, cpl.id AS link_id, cpl.is_default, cpl.label
        FROM client_payer_links cpl
        INNER JOIN payer_profiles pp ON pp.id = cpl.payer_profile_id
        WHERE cpl.client_user_id = :cid AND pp.is_active = 1
        ORDER BY cpl.is_default DESC, cpl.created_at DESC
    """), {"cid": cuid}).fetchall()
    keys = ["id", "payer_type", "company_name", "edrpou", "iban", "bank_name",
            "director_name", "address", "phone", "email", "legal_name",
            "signatory_name", "signatory_basis", "email_for_docs", "phone_for_docs",
            "is_vat_payer", "tax_mode", "is_active", "link_id", "is_default", "label"]
    return {"payers": [dict(zip(keys, r)) for r in rows]}


@router.post("/cabinet/payers")
async def create_cabinet_payer(
    payload: dict = Body(...),
    db: Session = Depends(get_rh_db),
    token: str = Depends(get_token_from_header),
):
    """Створити нового платника + прив'язати до клієнта."""
    customer = get_current_customer(token, db)
    cuid = customer.get("client_user_id") or customer.get("id") or customer.get("customer_id")
    fields = {k: v for k, v in payload.items() if k in _PAYER_EDITABLE}
    if not fields.get("company_name"):
        raise HTTPException(400, "Назва платника обов'язкова")
    fields.setdefault("payer_type", "individual")
    fields["created_by_user_id"] = cuid
    fields["is_active"] = 1
    cols = ", ".join(fields.keys())
    placeholders = ", ".join([f":{k}" for k in fields.keys()])
    result = db.execute(text(f"INSERT INTO payer_profiles ({cols}) VALUES ({placeholders})"), fields)
    db.commit()
    new_id = result.lastrowid
    db.execute(text("""
        INSERT INTO client_payer_links (client_user_id, payer_profile_id, is_default, label, created_at)
        VALUES (:cid, :pid, 0, :label, NOW())
    """), {"cid": cuid, "pid": new_id, "label": payload.get("label") or fields.get("company_name")})
    db.commit()
    return {"success": True, "payer_id": new_id}


@router.put("/cabinet/payers/{payer_id}")
async def update_cabinet_payer(
    payer_id: int,
    payload: dict = Body(...),
    db: Session = Depends(get_rh_db),
    token: str = Depends(get_token_from_header),
):
    """Редагувати платника (тільки якщо прив'язаний до цього клієнта)."""
    customer = get_current_customer(token, db)
    cuid = customer.get("client_user_id") or customer.get("id") or customer.get("customer_id")
    own = db.execute(text("SELECT id FROM client_payer_links WHERE client_user_id = :cid AND payer_profile_id = :pid"),
                     {"cid": cuid, "pid": payer_id}).fetchone()
    if not own:
        raise HTTPException(403, "Немає доступу")
    updates = {k: v for k, v in payload.items() if k in _PAYER_EDITABLE}
    if not updates:
        raise HTTPException(400, "Немає полів для оновлення")
    set_clause = ", ".join([f"{k} = :{k}" for k in updates.keys()])
    updates["pid"] = payer_id
    db.execute(text(f"UPDATE payer_profiles SET {set_clause}, updated_at = NOW() WHERE id = :pid"), updates)
    db.commit()
    return {"success": True}


@router.put("/cabinet/payers/{payer_id}/default")
async def set_default_payer(
    payer_id: int,
    db: Session = Depends(get_rh_db),
    token: str = Depends(get_token_from_header),
):
    """Зробити цього платника основним."""
    customer = get_current_customer(token, db)
    cuid = customer.get("client_user_id") or customer.get("id") or customer.get("customer_id")
    db.execute(text("UPDATE client_payer_links SET is_default = 0 WHERE client_user_id = :cid"), {"cid": cuid})
    res = db.execute(text("UPDATE client_payer_links SET is_default = 1 WHERE client_user_id = :cid AND payer_profile_id = :pid"),
                     {"cid": cuid, "pid": payer_id})
    db.commit()
    if res.rowcount == 0:
        raise HTTPException(404, "Платника не знайдено")
    return {"success": True}


@router.delete("/cabinet/payers/{payer_id}")
async def unlink_cabinet_payer(
    payer_id: int,
    db: Session = Depends(get_rh_db),
    token: str = Depends(get_token_from_header),
):
    """Відв'язати платника від клієнта (платник у БД лишається, лише link видаляється)."""
    customer = get_current_customer(token, db)
    cuid = customer.get("client_user_id") or customer.get("id") or customer.get("customer_id")
    res = db.execute(text("DELETE FROM client_payer_links WHERE client_user_id = :cid AND payer_profile_id = :pid"),
                     {"cid": cuid, "pid": payer_id})
    db.commit()
    if res.rowcount == 0:
        raise HTTPException(404, "Платника не знайдено")
    return {"success": True}


@router.get("/orders/{order_id}/documents")
async def get_my_order_documents(
    order_id: int,
    db: Session = Depends(get_rh_db),
    token: str = Depends(get_token_from_header)
):
    """Список документів конкретного замовлення (тільки якщо воно належить клієнту)"""
    try:
        customer = get_current_customer(token, db)
        email = (customer.get("email") or "").lower().strip()

        # Перевірка прав — замовлення має належати цьому клієнту
        cu = db.execute(
            text("SELECT id FROM client_users WHERE email_normalized = :e LIMIT 1"),
            {"e": email}
        ).fetchone()
        client_user_id = cu[0] if cu else None

        # Чи дійсно це замовлення цього клієнта?
        cols_rows = db.execute(text("SHOW COLUMNS FROM orders")).fetchall()
        existing_cols = {r[0] for r in cols_rows}
        cuid_col = "client_user_id" if "client_user_id" in existing_cols else "NULL"
        email_col = "customer_email" if "customer_email" in existing_cols else "''"
        check = db.execute(text(f"""
            SELECT order_id FROM orders
            WHERE order_id = :oid
              AND ({cuid_col} = :cuid OR {email_col} = :email)
            LIMIT 1
        """), {"oid": order_id, "cuid": client_user_id, "email": email}).fetchone()
        if not check:
            raise HTTPException(status_code=404, detail="Order not found")

        # Документи + статус підписання
        # ВАЖЛИВО: документи в RH можуть бути збережені з різним entity_id:
        #   - 'order' + order_id (стандарт)
        #   - 'order' + order_number (рідко, deprecated)
        #   - 'customer' + customer_id (estimate перед оформленням)
        # Шукаємо в усіх варіантах щоб не пропустити нічого.
        order_number = order_row[1] or ''

        # Дістаємо customer_id замовлення
        customer_id_row = db.execute(text(f"""
            SELECT {col('customer_id', 'NULL')} FROM orders WHERE order_id = :oid
        """), {"oid": order_id}).fetchone()
        customer_id_val = customer_id_row[0] if customer_id_row else None

        rows = db.execute(text("""
            SELECT d.id, d.doc_type, d.doc_number, d.version, d.status, d.signed_at, d.created_at,
                   (SELECT COUNT(*) FROM document_signatures ds
                    WHERE ds.document_id = d.id AND ds.signer_role = 'tenant') AS tenant_signed,
                   (SELECT COUNT(*) FROM document_signatures ds
                    WHERE ds.document_id = d.id AND ds.signer_role = 'landlord') AS landlord_signed,
                   d.entity_type, d.entity_id
            FROM documents d
            WHERE (d.entity_type = 'order' AND d.entity_id IN (:oid_str, :order_number))
               OR (d.entity_type = 'customer' AND :cust_id_str <> '' AND d.entity_id = :cust_id_str)
            ORDER BY d.created_at DESC
        """), {
            "oid_str": str(order_id),
            "order_number": str(order_number) if order_number else '___none___',
            "cust_id_str": str(customer_id_val) if customer_id_val else '',
        }).fetchall()

        logger.info(f"[get_my_order_documents] order_id={order_id}, order_number={order_number}, "
                    f"customer_id={customer_id_val}, docs_found={len(rows)}")

        DOC_TYPE_LABELS = {
            "invoice": "Рахунок",
            "invoice_legal": "Рахунок (юр.особа)",
            "invoice_offer": "Рахунок-оферта",
            "estimate": "Кошторис",
            "act_issue": "Акт видачі",
            "act_return": "Акт повернення",
            "annex": "Додаток до договору",
            "contract": "Договір оренди",
        }

        # Документи які клієнт повинен підписати
        SIGNABLE_TYPES = {"contract", "annex", "act_issue", "act_return"}

        return [
            {
                "id": r[0],
                "doc_type": r[1],
                "doc_type_label": DOC_TYPE_LABELS.get(r[1], r[1]),
                "doc_number": r[2],
                "version": r[3],
                "status": r[4],
                "signed_at": r[5].isoformat() if r[5] else None,
                "created_at": r[6].isoformat() if r[6] else None,
                "preview_url": f"/api/documents/{r[0]}/preview",
                "pdf_url": f"/api/documents/{r[0]}/pdf",
                "is_signable": r[1] in SIGNABLE_TYPES,
                "tenant_signed": bool(r[7]),
                "landlord_signed": bool(r[8]),
                "needs_client_signature": r[1] in SIGNABLE_TYPES and not bool(r[7]),
            }
            for r in rows
        ]
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"[get_my_order_documents] Error: {e}")
        return []


@router.post("/orders/{order_id}/documents/{document_id}/sign")
async def sign_document_as_client(
    order_id: int,
    document_id: str,
    payload: dict,
    db: Session = Depends(get_rh_db),
    token: str = Depends(get_token_from_header)
):
    """
    Клієнт підписує документ зі свого кабінету (роль = tenant).

    Body: {"signature_png_base64": "data:image/png;base64,...", "signer_name": "..."}

    1. Перевіряємо що документ належить замовленню цього клієнта.
    2. Не дозволяємо повторний підпис tenant'ом.
    3. Зберігаємо в document_signatures (signer_role='tenant').
    4. Якщо landlord теж підписав → orders.status = 'signed'.
    """
    try:
        customer = get_current_customer(token, db)
        email = (customer.get("email") or "").lower().strip()

        # Знайти client_user_id
        cu = db.execute(
            text("SELECT id FROM client_users WHERE email_normalized = :e LIMIT 1"),
            {"e": email}
        ).fetchone()
        client_user_id = cu[0] if cu else None

        # 1. Перевіряємо приналежність документа замовленню клієнта
        cols_rows = db.execute(text("SHOW COLUMNS FROM orders")).fetchall()
        existing_cols = {r[0] for r in cols_rows}
        cuid_col = "client_user_id" if "client_user_id" in existing_cols else "NULL"
        email_col = "customer_email" if "customer_email" in existing_cols else "''"

        check = db.execute(text(f"""
            SELECT d.id, d.doc_type, d.status
            FROM documents d
            JOIN orders o ON CAST(d.entity_id AS UNSIGNED) = o.order_id
            WHERE d.id = :doc_id
              AND d.entity_type = 'order'
              AND o.order_id = :oid
              AND ({cuid_col} = :cuid OR {email_col} = :email)
            LIMIT 1
        """), {
            "doc_id": document_id, "oid": order_id,
            "cuid": client_user_id, "email": email
        }).fetchone()

        if not check:
            raise HTTPException(status_code=404, detail="Document not found or access denied")

        # 2. Перевіряємо чи вже підписаний tenant'ом
        existing = db.execute(text("""
            SELECT id FROM document_signatures
            WHERE document_id = :doc_id AND signer_role = 'tenant'
        """), {"doc_id": document_id}).fetchone()
        if existing:
            raise HTTPException(status_code=400, detail="Document already signed")

        # 3. Підпис
        sig_b64 = payload.get("signature_png_base64", "")
        if not sig_b64:
            raise HTTPException(status_code=400, detail="signature_png_base64 required")
        if sig_b64.startswith("data:image"):
            pass  # вже data URL
        else:
            sig_b64 = f"data:image/png;base64,{sig_b64}"

        signer_name = payload.get("signer_name") or f"{customer.get('firstname','')} {customer.get('lastname','')}".strip() or email

        db.execute(text("""
            INSERT INTO document_signatures
            (document_id, signer_role, signature_image, signer_name, signed_at)
            VALUES (:doc_id, 'tenant', :sig, :name, NOW())
        """), {"doc_id": document_id, "sig": sig_b64, "name": signer_name})

        # 4. Якщо обидві сторони підписали — позначаємо документ як signed
        sig_count = db.execute(text("""
            SELECT COUNT(DISTINCT signer_role) FROM document_signatures
            WHERE document_id = :doc_id
        """), {"doc_id": document_id}).scalar() or 0

        fully_signed = sig_count >= 2
        if fully_signed:
            db.execute(text("UPDATE documents SET status = 'signed' WHERE id = :id"),
                       {"id": document_id})

        db.commit()

        return {
            "success": True,
            "document_id": document_id,
            "fully_signed": fully_signed,
            "message": "Підпис прийнято. " + ("Документ повністю підписаний." if fully_signed else "Очікуємо підпис менеджера."),
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        import traceback
        traceback.print_exc()
        logger.error(f"[sign_document_as_client] {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/orders/{order_id}/documents/{document_id}/approve")
async def approve_document_as_client(
    order_id: int,
    document_id: str,
    payload: dict = Body(default={}),
    db: Session = Depends(get_rh_db),
    token: str = Depends(get_token_from_header)
):
    """
    Inline-погодження кошторису (estimate / invoice_offer / quote) клієнтом.
    Не вимагає малювання підпису — фіксує згоду одним натиском.
    Створює запис у document_signatures з signer_role='tenant',
    signature_image='APPROVED_INLINE', signer_name=ПІБ клієнта.
    """
    try:
        customer = get_current_customer(token, db)
        email = (customer.get("email") or "").lower().strip()

        cu = db.execute(
            text("SELECT id FROM client_users WHERE email_normalized = :e LIMIT 1"),
            {"e": email}
        ).fetchone()
        client_user_id = cu[0] if cu else None

        cols_rows = db.execute(text("SHOW COLUMNS FROM orders")).fetchall()
        existing_cols = {r[0] for r in cols_rows}
        cuid_col = "client_user_id" if "client_user_id" in existing_cols else "NULL"
        email_col = "customer_email" if "customer_email" in existing_cols else "''"

        # Доступ + перевірка типу документа (тільки документи-кошториси)
        doc = db.execute(text(f"""
            SELECT d.id, d.doc_type, d.category, d.status
            FROM documents d
            JOIN orders o ON CAST(d.entity_id AS UNSIGNED) = o.order_id
            WHERE d.id = :doc_id
              AND d.entity_type = 'order'
              AND o.order_id = :oid
              AND ({cuid_col} = :cuid OR {email_col} = :email)
            LIMIT 1
        """), {
            "doc_id": document_id, "oid": order_id,
            "cuid": client_user_id, "email": email
        }).fetchone()

        if not doc:
            raise HTTPException(status_code=404, detail="Document not found or access denied")

        # Дозволяємо inline-погодження тільки для кошторисів
        allowed_doc_types = {"estimate", "invoice_offer", "quote", "preliminary_estimate"}
        allowed_categories = {"quote", "estimate"}
        if doc[1] not in allowed_doc_types and (doc[2] or "") not in allowed_categories:
            raise HTTPException(
                status_code=400,
                detail=f"Документ типу '{doc[1]}' потребує повноцінного підпису, не inline-погодження"
            )

        # Чи вже погоджений
        existing = db.execute(text("""
            SELECT id FROM document_signatures
            WHERE document_id = :doc_id AND signer_role = 'tenant'
        """), {"doc_id": document_id}).fetchone()
        if existing:
            raise HTTPException(status_code=400, detail="Документ вже погоджено")

        signer_name = (
            payload.get("signer_name")
            or f"{customer.get('firstname','')} {customer.get('lastname','')}".strip()
            or email
        )

        db.execute(text("""
            INSERT INTO document_signatures
              (document_id, signer_role, signature_image, signer_name, signed_at)
            VALUES (:doc_id, 'tenant', 'APPROVED_INLINE', :name, NOW())
        """), {"doc_id": document_id, "name": signer_name})

        # Позначаємо документ як approved
        db.execute(text("UPDATE documents SET status = 'approved' WHERE id = :id"),
                   {"id": document_id})

        # Лог в order_lifecycle
        try:
            db.execute(text("""
                INSERT INTO order_lifecycle (order_id, event_type, event_data, created_at)
                VALUES (:oid, 'estimate_approved',
                        JSON_OBJECT('document_id', :doc_id, 'approved_by', :name), NOW())
            """), {"oid": order_id, "doc_id": document_id, "name": signer_name})
        except Exception:
            pass  # таблиця може бути відсутня

        db.commit()

        # Push менеджеру? Зараз notify сповіщає клієнта; для менеджера — окремий потік (Telegram/email).
        return {
            "success": True,
            "document_id": document_id,
            "status": "approved",
            "approved_by": signer_name,
            "message": "Кошторис погоджено!"
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        import traceback; traceback.print_exc()
        logger.error(f"[approve_document_as_client] {e}")
        raise HTTPException(status_code=500, detail=str(e))




# ============================================================================
# MASTER AGREEMENT (Cabinet 2.0 — Річний договір)
# ============================================================================
# Використовуємо існуючі таблиці master_agreements + document_signatures.
# Логіка:
#  • Один активний (status='signed' + valid_until >= today) договір на client_user_id.
#  • Якщо немає → auto-create draft (executor_type='tov', 12 міс).
#  • Підпис: canvas → INSERT document_signatures (document_id='master_agreement:<id>', signer_role='tenant')
#            + UPDATE master_agreements SET status='signed', signed_at=NOW()
#            + UPDATE client_users.active_master_agreement_id = <id>
#  • CheckoutModal / convert-to-order: блокує без підписаного активного договору.

_EXECUTORS = {
    "tov": {
        "name": "ТОВ «ФАРФОР РЕНТ»",
        "short_name": "ТОВ «ФАРФОР РЕНТ»",
        "edrpou": "44651557",
        "address": "02000, м. Київ, вул. Магнітогорська, буд. 1, корп. 34",
        "bank": "АТ КБ «ПРИВАТБАНК»",
        "iban": "UA913052990000026002015020709",
        "director": "Драко В.А.",
    },
}


def _generate_ma_contract_number(db: Session, contract_date: date) -> str:
    """DDMMYYYY-N unique per day."""
    date_str = contract_date.strftime("%d%m%Y")
    seq = db.execute(text("""
        SELECT COUNT(*) FROM master_agreements WHERE DATE(valid_from) = :d
    """), {"d": contract_date}).fetchone()[0] + 1
    return f"{date_str}-{seq}"


def _get_or_create_draft_agreement(db: Session, client_user_id: int) -> dict:
    """
    Знаходить активний (signed+valid) або draft договір клієнта.
    Якщо немає — створює draft.
    Повертає dict зі станом.
    """
    # Спочатку шукаємо підписаний і ще валідний
    row = db.execute(text("""
        SELECT id, contract_number, status, valid_from, valid_until, signed_at
        FROM master_agreements
        WHERE client_user_id = :cid
          AND status = 'signed'
          AND valid_until >= CURDATE()
        ORDER BY signed_at DESC LIMIT 1
    """), {"cid": client_user_id}).fetchone()
    if row:
        return {
            "id": row[0], "contract_number": row[1], "status": row[2],
            "valid_from": row[3].isoformat() if row[3] else None,
            "valid_until": row[4].isoformat() if row[4] else None,
            "signed_at": row[5].isoformat() if row[5] else None,
            "needs_signature": False,
        }

    # Далі — draft/sent (можна підписати)
    row = db.execute(text("""
        SELECT id, contract_number, status, valid_from, valid_until, signed_at
        FROM master_agreements
        WHERE client_user_id = :cid AND status IN ('draft', 'sent')
        ORDER BY created_at DESC LIMIT 1
    """), {"cid": client_user_id}).fetchone()
    if row:
        return {
            "id": row[0], "contract_number": row[1], "status": row[2],
            "valid_from": row[3].isoformat() if row[3] else None,
            "valid_until": row[4].isoformat() if row[4] else None,
            "signed_at": row[5].isoformat() if row[5] else None,
            "needs_signature": True,
        }

    # Нічого немає → створюємо draft
    client = db.execute(text("""
        SELECT id, full_name, email, phone, payer_type, tax_id, bank_details
        FROM client_users WHERE id = :id LIMIT 1
    """), {"id": client_user_id}).fetchone()
    if not client:
        raise HTTPException(404, "Клієнтський профіль не знайдено")

    contract_date = date.today()
    valid_until = contract_date + timedelta(days=365)
    contract_number = _generate_ma_contract_number(db, contract_date)
    executor = _EXECUTORS["tov"]
    bank_details = None
    try:
        bank_details = json.loads(client[6]) if client[6] else None
    except Exception:
        bank_details = None
    snapshot = {
        "contract_number": contract_number,
        "contract_date": contract_date.isoformat(),
        "valid_from": contract_date.isoformat(),
        "valid_until": valid_until.isoformat(),
        "executor_type": "tov",
        "executor": executor,
        "generated_at": datetime.now().isoformat(),
        "client": {
            "id": client[0], "full_name": client[1], "email": client[2],
            "phone": client[3], "payer_type": client[4],
            "tax_id": client[5], "bank_details": bank_details,
        },
    }
    db.execute(text("""
        INSERT INTO master_agreements
            (client_user_id, payer_profile_id, contract_number, template_version,
             valid_from, valid_until, status, snapshot_json)
        VALUES (:cid, NULL, :num, 'tov', :vf, :vu, 'draft', :snap)
    """), {
        "cid": client_user_id, "num": contract_number,
        "vf": contract_date, "vu": valid_until,
        "snap": json.dumps(snapshot, ensure_ascii=False),
    })
    # LAST_INSERT_ID() is connection-scoped — fetch before commit on the same session
    new_id = db.execute(text("SELECT LAST_INSERT_ID()")).fetchone()[0]
    db.commit()
    return {
        "id": new_id, "contract_number": contract_number, "status": "draft",
        "valid_from": contract_date.isoformat(),
        "valid_until": valid_until.isoformat(),
        "signed_at": None,
        "needs_signature": True,
    }


def _has_valid_signed_agreement(db: Session, client_user_id: int) -> bool:
    """True якщо у клієнта є підписаний і валідний договір."""
    row = db.execute(text("""
        SELECT 1 FROM master_agreements
        WHERE client_user_id = :cid AND status = 'signed' AND valid_until >= CURDATE()
        LIMIT 1
    """), {"cid": client_user_id}).fetchone()
    return bool(row)


def _resolve_client_user_id(db: Session, customer: dict) -> int:
    """Знаходить client_users.id для поточного customer (з event_customers)."""
    cuid = customer.get("client_user_id") or customer.get("id") or customer.get("customer_id")
    return int(cuid) if cuid else 0


@router.get("/cabinet/master-agreement")
async def get_cabinet_master_agreement(
    db: Session = Depends(get_rh_db),
    token: str = Depends(get_token_from_header),
):
    """Поточний стан річного договору клієнта. Створює draft якщо немає."""
    customer = get_current_customer(token, db)
    cuid = _resolve_client_user_id(db, customer)
    if not cuid:
        raise HTTPException(401, "Не вдалось ідентифікувати клієнта")
    return _get_or_create_draft_agreement(db, cuid)


@router.get("/cabinet/master-agreement/view")
async def view_cabinet_master_agreement(
    token: str,
    db: Session = Depends(get_rh_db),
):
    """HTML-прев'ю договору. Токен у query (щоб працювало в iframe)."""
    customer = get_current_customer(token, db)
    cuid = _resolve_client_user_id(db, customer)
    if not cuid:
        raise HTTPException(401, "Не вдалось ідентифікувати клієнта")
    state = _get_or_create_draft_agreement(db, cuid)
    agreement_id = state["id"]

    # Render via existing service
    try:
        from services.pdf_generator import generate_master_agreement_html
    except Exception:
        generate_master_agreement_html = None

    ag = db.execute(text("""
        SELECT ma.id, ma.contract_number, ma.status, ma.valid_from, ma.valid_until,
               ma.signed_at, ma.snapshot_json, ma.note,
               cu.full_name, cu.email, cu.phone, cu.payer_type, cu.tax_id, cu.bank_details
        FROM master_agreements ma
        LEFT JOIN client_users cu ON cu.id = ma.client_user_id
        WHERE ma.id = :id AND ma.client_user_id = :cid
    """), {"id": agreement_id, "cid": cuid}).fetchone()
    if not ag:
        raise HTTPException(404, "Договір не знайдено")

    snap = None
    if ag[6]:
        try:
            snap = json.loads(ag[6]) if isinstance(ag[6], str) else ag[6]
        except Exception:
            snap = None
    agreement_data = {
        "contract_number": ag[1],
        "status": ag[2],
        "valid_from": ag[3].isoformat() if ag[3] else None,
        "valid_until": ag[4].isoformat() if ag[4] else None,
        "signed_at": ag[5].isoformat() if ag[5] else None,
        "signed_by": None,
        "snapshot": snap,
    }
    client_data = {
        "full_name": ag[8], "email": ag[9], "phone": ag[10],
        "payer_type": ag[11], "tax_id": ag[12], "bank_details": ag[13],
    }

    if generate_master_agreement_html:
        html = generate_master_agreement_html(agreement_data, client_data)
    else:
        # Простий fallback — на випадок недоступності сервісу
        html = f"""
        <!DOCTYPE html><html><head><meta charset="utf-8">
        <title>Договір {ag[1]}</title>
        <style>body{{font-family:Georgia,serif;max-width:800px;margin:40px auto;padding:20px;color:#0f172a;line-height:1.6}}
        h1{{font-size:20px;text-align:center}} .row{{display:flex;justify-content:space-between;margin:10px 0}}
        .label{{color:#64748b}}</style></head><body>
        <h1>РАМКОВИЙ ДОГОВІР ОРЕНДИ № {ag[1]}</h1>
        <div class="row"><span class="label">Дата:</span><span>{agreement_data['valid_from']}</span></div>
        <div class="row"><span class="label">Діє до:</span><span>{agreement_data['valid_until']}</span></div>
        <h3>Орендодавець</h3><p>{_EXECUTORS['tov']['name']}, ЄДРПОУ {_EXECUTORS['tov']['edrpou']}</p>
        <h3>Орендар (клієнт)</h3><p>{client_data['full_name'] or ''}, тел. {client_data['phone'] or ''}, email {client_data['email'] or ''}</p>
        <p>Умови оренди стандартні, повний текст договору надається офіс-менеджером.</p>
        </body></html>"""
    return HTMLResponse(content=html, media_type="text/html")


@router.post("/cabinet/master-agreement/sign")
async def sign_cabinet_master_agreement(
    payload: dict = Body(...),
    request: Request = None,
    db: Session = Depends(get_rh_db),
    token: str = Depends(get_token_from_header),
):
    """
    Клієнт підписує річний договір.
    Body: {signature_png_base64, signer_name, agreement_id?}
    """
    customer = get_current_customer(token, db)
    cuid = _resolve_client_user_id(db, customer)
    if not cuid:
        raise HTTPException(401, "Не вдалось ідентифікувати клієнта")

    sig_b64 = (payload.get("signature_png_base64") or "").strip()
    if not sig_b64:
        raise HTTPException(400, "signature_png_base64 required")
    if not sig_b64.startswith("data:image"):
        sig_b64 = f"data:image/png;base64,{sig_b64}"

    # Знаходимо договір (за id або поточний draft)
    state = _get_or_create_draft_agreement(db, cuid)
    agreement_id = int(payload.get("agreement_id") or state["id"])
    ag = db.execute(text("""
        SELECT id, status, client_user_id, contract_number
        FROM master_agreements WHERE id = :id LIMIT 1
    """), {"id": agreement_id}).fetchone()
    if not ag or int(ag[2] or 0) != cuid:
        raise HTTPException(404, "Договір не знайдено")
    if ag[1] == "signed":
        raise HTTPException(400, "Договір вже підписаний")
    if ag[1] not in ("draft", "sent"):
        raise HTTPException(400, f"Не можна підписати договір зі статусом '{ag[1]}'")

    signer_name = (payload.get("signer_name") or "").strip() or (
        f"{customer.get('firstname','')} {customer.get('lastname','')}".strip()
        or customer.get("email") or ""
    )
    ip_addr = ""
    user_agent = ""
    if request is not None:
        ip_addr = (request.client.host if request.client else "") or request.headers.get("x-forwarded-for", "")
        user_agent = request.headers.get("user-agent", "")[:500]

    doc_id = f"master_agreement:{agreement_id}"
    # Перевірка повторного підпису
    existing = db.execute(text("""
        SELECT id FROM document_signatures
        WHERE document_id = :did AND signer_role = 'tenant'
    """), {"did": doc_id}).fetchone()
    if existing:
        raise HTTPException(400, "Договір вже підписаний клієнтом")

    db.execute(text("""
        INSERT INTO document_signatures
            (document_id, signer_role, signature_image, signer_name, signed_at, ip_address, user_agent)
        VALUES (:did, 'tenant', :sig, :name, NOW(), :ip, :ua)
    """), {"did": doc_id, "sig": sig_b64, "name": signer_name,
           "ip": ip_addr or None, "ua": user_agent or None})

    db.execute(text("""
        UPDATE master_agreements
        SET status = 'signed', signed_at = NOW(),
            note = CONCAT(IFNULL(note, ''), CASE WHEN note IS NULL OR note = '' THEN '' ELSE '\n' END,
                          'Підписано клієнтом: ', :name, ' [', :ip, ']')
        WHERE id = :id
    """), {"id": agreement_id, "name": signer_name, "ip": ip_addr or "—"})

    # active_master_agreement_id (колонка може бути відсутня в старих схемах)
    try:
        db.execute(text("""
            UPDATE client_users SET active_master_agreement_id = :aid WHERE id = :cid
        """), {"aid": agreement_id, "cid": cuid})
    except Exception:
        db.rollback()
        # знову встановимо нову транзакцію в цій сесії
        db.execute(text("SELECT 1"))

    db.commit()
    return {
        "success": True,
        "agreement_id": agreement_id,
        "contract_number": ag[3],
        "message": "Договір підписано.",
    }


# ============================================================================
# FAVORITES (ОБРАНЕ)
# ============================================================================

@router.get("/favorites")
async def list_favorites(
    db: Session = Depends(get_rh_db),
    token: str = Depends(get_token_from_header)
):
    """Список ID товарів в обраному поточного користувача."""
    user = get_current_customer(token, db)
    rows = db.execute(text("""
        SELECT product_id FROM event_favorites WHERE customer_id = :cid
        ORDER BY created_at DESC
    """), {"cid": user["customer_id"]}).fetchall()
    return {"product_ids": [r[0] for r in rows]}


@router.get("/favorites/products")
async def list_favorite_products(
    db: Session = Depends(get_rh_db),
    token: str = Depends(get_token_from_header)
):
    """Повні картки товарів з обраного для сторінки 'Обране'."""
    user = get_current_customer(token, db)
    # Динамічно перевіряємо які колонки існують у products
    prod_cols = {r[0] for r in db.execute(text("SHOW COLUMNS FROM products")).fetchall()}
    def pc(col, default="NULL"):
        return f"p.{col}" if col in prod_cols else default

    rental_col = pc("rental_price", "p.price")
    deposit_col = f"COALESCE({pc('deposit', 'NULL')}, p.price, 0)"
    color_col = pc("color", "''")
    material_col = pc("material", "''")
    desc_col = pc("description", "''")
    cat_col = pc("category_id", "NULL")

    rows = db.execute(text(f"""
        SELECT p.product_id, p.name, p.sku, p.price, p.image_url, p.quantity,
               {desc_col} AS description, {cat_col} AS category_id, f.created_at,
               {rental_col} AS rental_price,
               {deposit_col} AS deposit_amount,
               {color_col} AS color, {material_col} AS material
        FROM event_favorites f
        JOIN products p ON p.product_id = f.product_id
        WHERE f.customer_id = :cid
        ORDER BY f.created_at DESC
    """), {"cid": user["customer_id"]}).fetchall()
    return {"products": [{
        "product_id": r[0], "name": r[1], "sku": r[2],
        "price": float(r[3] or 0),
        "rental_price": float(r[9] or 0),
        "deposit": float(r[10] or 0),
        "image_url": r[4], "quantity": r[5] or 0,
        "description": r[6], "category_id": r[7],
        "color": r[11] or "",
        "material": r[12] or "",
        "favorited_at": r[8].isoformat() if r[8] else None,
    } for r in rows]}


@router.post("/favorites/{product_id}")
async def add_favorite(
    product_id: int,
    db: Session = Depends(get_rh_db),
    token: str = Depends(get_token_from_header)
):
    """Додати товар в обране."""
    user = get_current_customer(token, db)
    exists = db.execute(text("""
        SELECT product_id FROM products WHERE product_id = :pid
    """), {"pid": product_id}).scalar()
    if not exists:
        raise HTTPException(status_code=404, detail="Product not found")
    db.execute(text("""
        INSERT IGNORE INTO event_favorites (customer_id, product_id)
        VALUES (:cid, :pid)
    """), {"cid": user["customer_id"], "pid": product_id})
    db.commit()
    return {"ok": True, "product_id": product_id, "favorited": True}


@router.delete("/favorites/{product_id}")
async def remove_favorite(
    product_id: int,
    db: Session = Depends(get_rh_db),
    token: str = Depends(get_token_from_header)
):
    """Видалити товар з обраного."""
    user = get_current_customer(token, db)
    db.execute(text("""
        DELETE FROM event_favorites WHERE customer_id = :cid AND product_id = :pid
    """), {"cid": user["customer_id"], "pid": product_id})
    db.commit()
    return {"ok": True, "product_id": product_id, "favorited": False}


# ============================================================================
# WEB PUSH NOTIFICATIONS
# ============================================================================

@router.get("/push/public-key")
async def push_public_key():
    """Return VAPID public key for the browser to use during subscription."""
    return {"public_key": os.environ.get("VAPID_PUBLIC_KEY", "")}


class PushSubscriptionRequest(BaseModel):
    endpoint: str
    keys: dict  # {p256dh, auth}
    user_agent: Optional[str] = None


@router.post("/push/subscribe")
async def push_subscribe(
    data: PushSubscriptionRequest,
    db: Session = Depends(get_rh_db),
    token: str = Depends(get_token_from_header)
):
    """Save (or refresh) a web-push subscription for current customer."""
    user = get_current_customer(token, db)
    p256dh = data.keys.get("p256dh", "")
    auth_secret = data.keys.get("auth", "")
    if not (data.endpoint and p256dh and auth_secret):
        raise HTTPException(status_code=400, detail="Invalid subscription payload")
    db.execute(text("""
        INSERT INTO push_subscriptions
          (customer_id, endpoint, p256dh, auth_secret, user_agent, last_used_at)
        VALUES (:cid, :ep, :p256, :auth, :ua, NOW())
        ON DUPLICATE KEY UPDATE
          customer_id = VALUES(customer_id),
          p256dh = VALUES(p256dh),
          auth_secret = VALUES(auth_secret),
          user_agent = VALUES(user_agent),
          last_used_at = NOW()
    """), {
        "cid": user["customer_id"], "ep": data.endpoint,
        "p256": p256dh, "auth": auth_secret, "ua": data.user_agent,
    })
    db.commit()
    return {"ok": True}


@router.post("/push/unsubscribe")
async def push_unsubscribe(
    data: dict,
    db: Session = Depends(get_rh_db),
    token: str = Depends(get_token_from_header)
):
    user = get_current_customer(token, db)
    endpoint = data.get("endpoint", "")
    if endpoint:
        db.execute(text("""
            DELETE FROM push_subscriptions
            WHERE customer_id = :cid AND endpoint = :ep
        """), {"cid": user["customer_id"], "ep": endpoint})
    else:
        db.execute(text("DELETE FROM push_subscriptions WHERE customer_id = :cid"),
                   {"cid": user["customer_id"]})
    db.commit()
    return {"ok": True}


@router.post("/push/test")
async def push_test(
    db: Session = Depends(get_rh_db),
    token: str = Depends(get_token_from_header)
):
    """Send a test push to current customer (useful for UI 'Test notification' button)."""
    from services.push_notifications import send_to_customer
    user = get_current_customer(token, db)
    result = send_to_customer(
        db, user["customer_id"],
        title="🎉 RentalHub: тестове сповіщення",
        body="Push сповіщення працюють. Тепер ви будете отримувати оновлення про ваші замовлення.",
        url="/profile", tag="test",
    )
    return result



# ============================================================================
# HEALTH CHECK
# ============================================================================

@router.get("/health")
async def health():
    return {"status": "ok", "service": "event-tool", "timestamp": datetime.utcnow().isoformat()}

# ============================================================================
# IMAGE PROXY (для обходу CORS)
# ============================================================================

import httpx
from fastapi.responses import StreamingResponse
import io

@router.get("/image-proxy")
async def image_proxy(url: str, response: Response):
    """
    Проксі для зображень з CORS headers
    Використовується для завантаження зображень на canvas
    """
    # Перевіряємо що URL з довіреного домену
    allowed_domains = [
        "backrentalhub.farforrent.com.ua",
        "www.farforrent.com.ua",
        "farforrent.com.ua"
    ]
    
    from urllib.parse import urlparse
    parsed = urlparse(url)
    
    if parsed.netloc not in allowed_domains:
        raise HTTPException(status_code=400, detail="Domain not allowed")
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            img_response = await client.get(url)
            
            if img_response.status_code != 200:
                raise HTTPException(status_code=404, detail="Image not found")
            
            # Визначаємо content-type
            content_type = img_response.headers.get("content-type", "image/jpeg")
            
            # Повертаємо з CORS headers
            return Response(
                content=img_response.content,
                media_type=content_type,
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, OPTIONS",
                    "Access-Control-Allow-Headers": "*",
                    "Cache-Control": "public, max-age=86400"  # Cache 24 години
                }
            )
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Image fetch timeout")
    except Exception as e:
        logger.error(f"Image proxy error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

