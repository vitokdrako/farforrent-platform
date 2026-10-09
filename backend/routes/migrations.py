"""
Database migrations API endpoint
Safe way to run database schema changes
"""
from fastapi import APIRouter, HTTPException
from sqlalchemy import text
from database_rentalhub import get_rh_db_sync
import logging

router = APIRouter(prefix="/api/migrations", tags=["migrations"])

# ============================================================
# CLIENT-BASED MASTER AGREEMENTS MIGRATION
# ============================================================

@router.post("/client-ma-structure")
async def migrate_client_ma_structure():
    """
    Migrate to client-based Master Agreement structure:
    1. Add payer_type to client_users
    2. Add active_master_agreement_id to client_users
    3. Add client_user_id to master_agreements
    """
    try:
        db = get_rh_db_sync()
        changes = []
        
        # 1. Add payer_type to client_users
        check = db.execute(text("""
            SELECT COUNT(*) FROM information_schema.COLUMNS 
            WHERE TABLE_SCHEMA = DATABASE()
            AND TABLE_NAME = 'client_users' 
            AND COLUMN_NAME = 'payer_type'
        """)).fetchone()[0]
        
        if check == 0:
            db.execute(text("""
                ALTER TABLE client_users 
                ADD COLUMN payer_type ENUM('individual', 'fop', 'fop_simple', 'tov') 
                DEFAULT 'individual' AFTER phone
            """))
            db.commit()
            changes.append("Added payer_type to client_users")
        
        # 2. Add active_master_agreement_id to client_users
        check = db.execute(text("""
            SELECT COUNT(*) FROM information_schema.COLUMNS 
            WHERE TABLE_SCHEMA = DATABASE()
            AND TABLE_NAME = 'client_users' 
            AND COLUMN_NAME = 'active_master_agreement_id'
        """)).fetchone()[0]
        
        if check == 0:
            db.execute(text("""
                ALTER TABLE client_users 
                ADD COLUMN active_master_agreement_id INT NULL AFTER payer_type
            """))
            db.commit()
            changes.append("Added active_master_agreement_id to client_users")
        
        # 3. Add client_user_id to master_agreements
        check = db.execute(text("""
            SELECT COUNT(*) FROM information_schema.COLUMNS 
            WHERE TABLE_SCHEMA = DATABASE()
            AND TABLE_NAME = 'master_agreements' 
            AND COLUMN_NAME = 'client_user_id'
        """)).fetchone()[0]
        
        if check == 0:
            db.execute(text("""
                ALTER TABLE master_agreements 
                ADD COLUMN client_user_id INT NULL AFTER payer_profile_id
            """))
            db.commit()
            changes.append("Added client_user_id to master_agreements")
        
        # 4. Add tax_id (ЄДРПОУ/ІПН) to client_users
        check = db.execute(text("""
            SELECT COUNT(*) FROM information_schema.COLUMNS 
            WHERE TABLE_SCHEMA = DATABASE()
            AND TABLE_NAME = 'client_users' 
            AND COLUMN_NAME = 'tax_id'
        """)).fetchone()[0]
        
        if check == 0:
            db.execute(text("""
                ALTER TABLE client_users 
                ADD COLUMN tax_id VARCHAR(20) NULL AFTER payer_type
            """))
            db.commit()
            changes.append("Added tax_id to client_users")
        
        # 5. Add bank_details (JSON) to client_users
        check = db.execute(text("""
            SELECT COUNT(*) FROM information_schema.COLUMNS 
            WHERE TABLE_SCHEMA = DATABASE()
            AND TABLE_NAME = 'client_users' 
            AND COLUMN_NAME = 'bank_details'
        """)).fetchone()[0]
        
        if check == 0:
            db.execute(text("""
                ALTER TABLE client_users 
                ADD COLUMN bank_details JSON NULL AFTER tax_id
            """))
            db.commit()
            changes.append("Added bank_details to client_users")
        
        db.close()
        
        return {
            "success": True,
            "migration": "client-ma-structure",
            "changes": changes if changes else ["All columns already exist"]
        }
        
    except Exception as e:
        logger.error(f"Migration failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


logger = logging.getLogger(__name__)


@router.post("/add-manager-fields")
async def add_manager_fields_to_orders():
    """
    Add manager_comment and damage_fee columns to orders table
    Safe to run multiple times - checks if columns exist first
    """
    try:
        db = get_rh_db_sync()
        
        # Check if columns already exist
        check_query = text("""
            SELECT COUNT(*) as count
            FROM information_schema.COLUMNS 
            WHERE TABLE_SCHEMA = DATABASE()
            AND TABLE_NAME = 'orders' 
            AND COLUMN_NAME IN ('manager_comment', 'damage_fee')
        """)
        
        result = db.execute(check_query).fetchone()
        existing_columns = result[0] if result else 0
        
        if existing_columns == 2:
            logger.info("Columns manager_comment and damage_fee already exist")
            db.close()
            return {
                "success": True,
                "message": "Колонки вже існують",
                "columns_added": 0
            }
        
        # Add columns if they don't exist
        columns_added = []
        
        # Add manager_comment if not exists
        if existing_columns == 0 or existing_columns == 1:
            try:
                check_manager = text("""
                    SELECT COUNT(*) 
                    FROM information_schema.COLUMNS 
                    WHERE TABLE_SCHEMA = DATABASE()
                    AND TABLE_NAME = 'orders' 
                    AND COLUMN_NAME = 'manager_comment'
                """)
                has_manager = db.execute(check_manager).fetchone()[0]
                
                if not has_manager:
                    alter_manager = text("ALTER TABLE orders ADD COLUMN manager_comment TEXT")
                    db.execute(alter_manager)
                    db.commit()
                    columns_added.append('manager_comment')
                    logger.info("Added column: manager_comment")
            except Exception as e:
                logger.error(f"Error adding manager_comment: {str(e)}")
                db.rollback()
                raise
        
        # Add damage_fee if not exists
        if existing_columns == 0 or existing_columns == 1:
            try:
                check_fee = text("""
                    SELECT COUNT(*) 
                    FROM information_schema.COLUMNS 
                    WHERE TABLE_SCHEMA = DATABASE()
                    AND TABLE_NAME = 'orders' 
                    AND COLUMN_NAME = 'damage_fee'
                """)
                has_fee = db.execute(check_fee).fetchone()[0]
                
                if not has_fee:
                    alter_fee = text("ALTER TABLE orders ADD COLUMN damage_fee DECIMAL(10, 2) DEFAULT 0.00")
                    db.execute(alter_fee)
                    db.commit()
                    columns_added.append('damage_fee')
                    logger.info("Added column: damage_fee")
            except Exception as e:
                logger.error(f"Error adding damage_fee: {str(e)}")
                db.rollback()
                raise
        
        db.close()
        
        return {
            "success": True,
            "message": f"Міграція успішна! Додано колонок: {len(columns_added)}",
            "columns_added": columns_added
        }
        
    except Exception as e:
        logger.error(f"Migration failed: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Помилка міграції: {str(e)}"
        )


@router.get("/check-schema")
async def check_orders_schema():
    """
    Check current schema of orders table
    """
    try:
        db = get_rh_db_sync()
        
        query = text("""
            SELECT COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE, COLUMN_DEFAULT
            FROM information_schema.COLUMNS 
            WHERE TABLE_SCHEMA = DATABASE()
            AND TABLE_NAME = 'orders'
            ORDER BY ORDINAL_POSITION
        """)
        
        result = db.execute(query).fetchall()
        
        columns = [
            {
                "name": row[0],
                "type": row[1],
                "nullable": row[2],
                "default": row[3]
            }
            for row in result
        ]
        
        db.close()
        
        return {
            "table": "orders",
            "total_columns": len(columns),
            "columns": columns
        }
        
    except Exception as e:
        logger.error(f"Schema check failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Помилка перевірки схеми: {str(e)}"
        )


@router.post("/finance-hub-v2")
async def migrate_finance_hub_v2():
    """
    Finance Hub 2.0 - Міграція для підтримки:
    - deal_mode в orders (rent/sale)
    - Розширення fin_payments для advance/discount
    - Оптимізовані індекси
    
    Safe to run multiple times.
    """
    try:
        db = get_rh_db_sync()
        results = []
        
        # === 1. ADD deal_mode TO orders ===
        try:
            check = db.execute(text("""
                SELECT COUNT(*) FROM information_schema.COLUMNS 
                WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'orders' 
                AND COLUMN_NAME = 'deal_mode'
            """)).scalar()
            
            if not check:
                db.execute(text("""
                    ALTER TABLE orders 
                    ADD COLUMN deal_mode VARCHAR(20) DEFAULT 'rent' 
                    COMMENT 'rent=оренда, sale=продаж'
                """))
                db.commit()
                results.append("deal_mode: added to orders")
            else:
                results.append("deal_mode: already exists")
        except Exception as e:
            results.append(f"deal_mode: error - {str(e)}")
            db.rollback()
        
        # === 2. ADD INDEX on fin_payments (order_id, payment_type) ===
        try:
            check = db.execute(text("""
                SELECT COUNT(*) FROM information_schema.STATISTICS 
                WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'fin_payments' 
                AND INDEX_NAME = 'idx_payments_order_type'
            """)).scalar()
            
            if not check:
                db.execute(text("""
                    CREATE INDEX idx_payments_order_type 
                    ON fin_payments(order_id, payment_type)
                """))
                db.commit()
                results.append("idx_payments_order_type: created")
            else:
                results.append("idx_payments_order_type: already exists")
        except Exception as e:
            results.append(f"idx_payments_order_type: error - {str(e)}")
            db.rollback()
        
        # === 3. ADD INDEX on fin_payments (payment_type, method, status) for stats ===
        try:
            check = db.execute(text("""
                SELECT COUNT(*) FROM information_schema.STATISTICS 
                WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'fin_payments' 
                AND INDEX_NAME = 'idx_payments_stats'
            """)).scalar()
            
            if not check:
                db.execute(text("""
                    CREATE INDEX idx_payments_stats 
                    ON fin_payments(payment_type, method, status)
                """))
                db.commit()
                results.append("idx_payments_stats: created")
            else:
                results.append("idx_payments_stats: already exists")
        except Exception as e:
            results.append(f"idx_payments_stats: error - {str(e)}")
            db.rollback()
        
        # === 4. ADD INDEX on fin_expenses for category aggregation ===
        try:
            check = db.execute(text("""
                SELECT COUNT(*) FROM information_schema.STATISTICS 
                WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'fin_expenses' 
                AND INDEX_NAME = 'idx_expenses_category_method'
            """)).scalar()
            
            if not check:
                db.execute(text("""
                    CREATE INDEX idx_expenses_category_method 
                    ON fin_expenses(category_id, method)
                """))
                db.commit()
                results.append("idx_expenses_category_method: created")
            else:
                results.append("idx_expenses_category_method: already exists")
        except Exception as e:
            results.append(f"idx_expenses_category_method: error - {str(e)}")
            db.rollback()
        
        # === 5. Ensure 'advance' payment type works ===
        # fin_payments.payment_type is VARCHAR, no enum migration needed
        results.append("payment_type 'advance': VARCHAR field supports it")
        
        db.close()
        
        return {
            "success": True,
            "migration": "finance-hub-v2",
            "results": results
        }
        
    except Exception as e:
        logger.error(f"Finance Hub V2 migration failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Помилка міграції: {str(e)}"
        )


@router.post("/documents-engine-v3")
async def migrate_documents_engine_v3():
    """
    Phase 3: Documents Engine Migration
    
    Creates:
    - master_agreements table (рамкові договори)
    - order_annexes table (додатки до замовлень)
    - Updates documents table (snapshot_json, is_legal, etc.)
    - Updates orders table (active_annex_id)
    
    Safe to run multiple times.
    """
    try:
        db = get_rh_db_sync()
        results = []
        
        # === 1. CREATE master_agreements TABLE ===
        try:
            check = db.execute(text("""
                SELECT COUNT(*) FROM information_schema.TABLES 
                WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'master_agreements'
            """)).scalar()
            
            if not check:
                db.execute(text("""
                    CREATE TABLE master_agreements (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        payer_profile_id INT NOT NULL,
                        contract_number VARCHAR(50) NOT NULL UNIQUE,
                        template_version VARCHAR(20) DEFAULT 'v1',
                        signed_at DATETIME NULL,
                        valid_from DATE NOT NULL,
                        valid_until DATE NOT NULL,
                        status ENUM('draft', 'sent', 'signed', 'expired', 'cancelled') DEFAULT 'draft',
                        snapshot_json JSON,
                        pdf_path VARCHAR(500),
                        note TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                        
                        INDEX idx_ma_payer (payer_profile_id),
                        INDEX idx_ma_status (status),
                        INDEX idx_ma_valid (valid_until),
                        
                        CONSTRAINT fk_ma_payer FOREIGN KEY (payer_profile_id) 
                            REFERENCES payer_profiles(id) ON DELETE RESTRICT
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 
                    COMMENT='Рамкові договори (Phase 3)'
                """))
                db.commit()
                results.append("master_agreements: created")
            else:
                results.append("master_agreements: already exists")
        except Exception as e:
            results.append(f"master_agreements: error - {str(e)}")
            db.rollback()
        
        # === 2. CREATE order_annexes TABLE ===
        try:
            check = db.execute(text("""
                SELECT COUNT(*) FROM information_schema.TABLES 
                WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'order_annexes'
            """)).scalar()
            
            if not check:
                db.execute(text("""
                    CREATE TABLE order_annexes (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        order_id INT NOT NULL,
                        master_agreement_id INT NOT NULL,
                        annex_number VARCHAR(50) NOT NULL,
                        version INT DEFAULT 1,
                        snapshot_json JSON,
                        pdf_path VARCHAR(500),
                        status ENUM('draft', 'generated', 'signed') DEFAULT 'draft',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                        
                        INDEX idx_annex_order (order_id),
                        INDEX idx_annex_agreement (master_agreement_id),
                        UNIQUE KEY uk_annex_order_version (order_id, version),
                        
                        CONSTRAINT fk_annex_order FOREIGN KEY (order_id) 
                            REFERENCES orders(order_id) ON DELETE CASCADE,
                        CONSTRAINT fk_annex_agreement FOREIGN KEY (master_agreement_id) 
                            REFERENCES master_agreements(id) ON DELETE RESTRICT
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 
                    COMMENT='Додатки до договорів (Phase 3)'
                """))
                db.commit()
                results.append("order_annexes: created")
            else:
                results.append("order_annexes: already exists")
        except Exception as e:
            results.append(f"order_annexes: error - {str(e)}")
            db.rollback()
        
        # === 3. ADD active_annex_id TO orders ===
        try:
            check = db.execute(text("""
                SELECT COUNT(*) FROM information_schema.COLUMNS 
                WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'orders' 
                AND COLUMN_NAME = 'active_annex_id'
            """)).scalar()
            
            if not check:
                db.execute(text("""
                    ALTER TABLE orders 
                    ADD COLUMN active_annex_id INT NULL 
                    COMMENT 'Активний додаток до договору'
                """))
                db.commit()
                results.append("orders.active_annex_id: added")
            else:
                results.append("orders.active_annex_id: already exists")
        except Exception as e:
            results.append(f"orders.active_annex_id: error - {str(e)}")
            db.rollback()
        
        # === 4. ADD snapshot_json TO documents ===
        try:
            check = db.execute(text("""
                SELECT COUNT(*) FROM information_schema.COLUMNS 
                WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'documents' 
                AND COLUMN_NAME = 'snapshot_json'
            """)).scalar()
            
            if not check:
                db.execute(text("""
                    ALTER TABLE documents 
                    ADD COLUMN snapshot_json JSON COMMENT 'Immutable snapshot of document data'
                """))
                db.commit()
                results.append("documents.snapshot_json: added")
            else:
                results.append("documents.snapshot_json: already exists")
        except Exception as e:
            results.append(f"documents.snapshot_json: error - {str(e)}")
            db.rollback()
        
        # === 5. ADD is_legal TO documents ===
        try:
            check = db.execute(text("""
                SELECT COUNT(*) FROM information_schema.COLUMNS 
                WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'documents' 
                AND COLUMN_NAME = 'is_legal'
            """)).scalar()
            
            if not check:
                db.execute(text("""
                    ALTER TABLE documents 
                    ADD COLUMN is_legal BOOLEAN DEFAULT FALSE 
                    COMMENT 'TRUE = юридичний документ'
                """))
                db.commit()
                results.append("documents.is_legal: added")
            else:
                results.append("documents.is_legal: already exists")
        except Exception as e:
            results.append(f"documents.is_legal: error - {str(e)}")
            db.rollback()
        
        # === 6. ADD category TO documents ===
        try:
            check = db.execute(text("""
                SELECT COUNT(*) FROM information_schema.COLUMNS 
                WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'documents' 
                AND COLUMN_NAME = 'category'
            """)).scalar()
            
            if not check:
                db.execute(text("""
                    ALTER TABLE documents 
                    ADD COLUMN category VARCHAR(50) DEFAULT 'quote' 
                    COMMENT 'quote|contract|annex|act|finance|operations'
                """))
                db.commit()
                results.append("documents.category: added")
            else:
                results.append("documents.category: already exists")
        except Exception as e:
            results.append(f"documents.category: error - {str(e)}")
            db.rollback()
        
        # === 7. ADD master_agreement_id TO documents ===
        try:
            check = db.execute(text("""
                SELECT COUNT(*) FROM information_schema.COLUMNS 
                WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'documents' 
                AND COLUMN_NAME = 'master_agreement_id'
            """)).scalar()
            
            if not check:
                db.execute(text("""
                    ALTER TABLE documents 
                    ADD COLUMN master_agreement_id INT NULL 
                    COMMENT 'Reference to master agreement'
                """))
                db.commit()
                results.append("documents.master_agreement_id: added")
            else:
                results.append("documents.master_agreement_id: already exists")
        except Exception as e:
            results.append(f"documents.master_agreement_id: error - {str(e)}")
            db.rollback()
        
        db.close()
        
        return {
            "success": True,
            "migration": "documents-engine-v3",
            "results": results
        }
        
    except Exception as e:
        logger.error(f"Documents Engine V3 migration failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Помилка міграції: {str(e)}"
        )


# Видалено дубльовану міграцію document-workflow-v2 
# (структура вже існує через documents-engine-v3)

        
        return {
            "success": True,
            "migration": "documents-engine-v3",
            "results": results
        }
        
    except Exception as e:
        logger.error(f"Documents Engine V3 migration failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Помилка міграції: {str(e)}"
        )


@router.post("/products-extended-attributes")
async def migrate_products_extended_attributes():
    """
    Розширення таблиці products новими атрибутами:
    - Розміри окремими колонками (height, width, depth, diameter)
    - Категорія/підкатегорія (редаговані)
    - Форма виробу (shape)
    - Хештеги (hashtags) для фільтрації
    
    Safe to run multiple times.
    """
    try:
        db = get_rh_db_sync()
        results = []
        
        # === 1. ADD height, width, depth, diameter columns ===
        dimension_cols = [
            ("height_cm", "DECIMAL(10,2)", "Висота в см"),
            ("width_cm", "DECIMAL(10,2)", "Ширина в см"),
            ("depth_cm", "DECIMAL(10,2)", "Глибина в см"),
            ("diameter_cm", "DECIMAL(10,2)", "Діаметр в см"),
        ]
        
        for col_name, col_type, col_desc in dimension_cols:
            try:
                check = db.execute(text(f"""
                    SELECT COUNT(*) FROM information_schema.COLUMNS 
                    WHERE TABLE_SCHEMA = DATABASE() 
                    AND TABLE_NAME = 'products' 
                    AND COLUMN_NAME = '{col_name}'
                """)).scalar()
                
                if not check:
                    db.execute(text(f"""
                        ALTER TABLE products ADD COLUMN {col_name} {col_type} DEFAULT NULL
                        COMMENT '{col_desc}'
                    """))
                    db.commit()
                    results.append(f"{col_name}: created")
                else:
                    results.append(f"{col_name}: already exists")
            except Exception as e:
                results.append(f"{col_name}: error - {str(e)}")
                db.rollback()
        
        # === 2. ADD shape column (форма виробу) ===
        try:
            check = db.execute(text("""
                SELECT COUNT(*) FROM information_schema.COLUMNS 
                WHERE TABLE_SCHEMA = DATABASE() 
                AND TABLE_NAME = 'products' 
                AND COLUMN_NAME = 'shape'
            """)).scalar()
            
            if not check:
                db.execute(text("""
                    ALTER TABLE products ADD COLUMN shape VARCHAR(100) DEFAULT NULL
                    COMMENT 'Форма виробу (круглий, квадратний, овальний...)'
                """))
                db.commit()
                results.append("shape: created")
            else:
                results.append("shape: already exists")
        except Exception as e:
            results.append(f"shape: error - {str(e)}")
            db.rollback()
        
        # === 3. ADD hashtags column (JSON array) ===
        try:
            check = db.execute(text("""
                SELECT COUNT(*) FROM information_schema.COLUMNS 
                WHERE TABLE_SCHEMA = DATABASE() 
                AND TABLE_NAME = 'products' 
                AND COLUMN_NAME = 'hashtags'
            """)).scalar()
            
            if not check:
                db.execute(text("""
                    ALTER TABLE products ADD COLUMN hashtags JSON DEFAULT NULL
                    COMMENT 'Масив хештегів для фільтрації ["весілля", "вінтаж", "золото"]'
                """))
                db.commit()
                results.append("hashtags: created")
            else:
                results.append("hashtags: already exists")
        except Exception as e:
            results.append(f"hashtags: error - {str(e)}")
            db.rollback()
        
        # === 4. Ensure category_name and subcategory_name are editable ===
        # (They should already exist from OpenCart sync, but let's make sure)
        cat_cols = [
            ("category_name", "VARCHAR(255)", "Назва категорії"),
            ("subcategory_name", "VARCHAR(255)", "Назва підкатегорії"),
        ]
        
        for col_name, col_type, col_desc in cat_cols:
            try:
                check = db.execute(text(f"""
                    SELECT COUNT(*) FROM information_schema.COLUMNS 
                    WHERE TABLE_SCHEMA = DATABASE() 
                    AND TABLE_NAME = 'products' 
                    AND COLUMN_NAME = '{col_name}'
                """)).scalar()
                
                if not check:
                    db.execute(text(f"""
                        ALTER TABLE products ADD COLUMN {col_name} {col_type} DEFAULT NULL
                        COMMENT '{col_desc}'
                    """))
                    db.commit()
                    results.append(f"{col_name}: created")
                else:
                    results.append(f"{col_name}: already exists")
            except Exception as e:
                results.append(f"{col_name}: error - {str(e)}")
                db.rollback()
        
        # === 5. CREATE hashtags dictionary table ===
        try:
            check = db.execute(text("""
                SELECT COUNT(*) FROM information_schema.TABLES 
                WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'product_hashtags_dict'
            """)).scalar()
            
            if not check:
                db.execute(text("""
                    CREATE TABLE product_hashtags_dict (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        tag VARCHAR(100) NOT NULL UNIQUE,
                        display_name VARCHAR(100),
                        category VARCHAR(50) DEFAULT 'general',
                        usage_count INT DEFAULT 0,
                        is_active BOOLEAN DEFAULT TRUE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        INDEX idx_tag (tag),
                        INDEX idx_category (category)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                    COMMENT='Словник хештегів для фільтрації товарів'
                """))
                db.commit()
                results.append("product_hashtags_dict: created")
                
                # Додати базові хештеги
                base_tags = [
                    ('весілля', 'Весілля', 'event'),
                    ('корпоратив', 'Корпоратив', 'event'),
                    ('день_народження', 'День народження', 'event'),
                    ('вінтаж', 'Вінтаж', 'style'),
                    ('модерн', 'Модерн', 'style'),
                    ('класика', 'Класика', 'style'),
                    ('бохо', 'Бохо', 'style'),
                    ('мінімалізм', 'Мінімалізм', 'style'),
                    ('золото', 'Золото', 'color'),
                    ('срібло', 'Срібло', 'color'),
                    ('білий', 'Білий', 'color'),
                    ('чорний', 'Чорний', 'color'),
                    ('скло', 'Скло', 'material'),
                    ('метал', 'Метал', 'material'),
                    ('дерево', 'Дерево', 'material'),
                    ('тканина', 'Тканина', 'material'),
                    ('преміум', 'Преміум', 'tier'),
                    ('стандарт', 'Стандарт', 'tier'),
                    ('економ', 'Економ', 'tier'),
                ]
                
                for tag, display, cat in base_tags:
                    try:
                        db.execute(text("""
                            INSERT INTO product_hashtags_dict (tag, display_name, category)
                            VALUES (:tag, :display, :cat)
                        """), {"tag": tag, "display": display, "cat": cat})
                    except:
                        pass
                db.commit()
                results.append("product_hashtags_dict: populated with base tags")
            else:
                results.append("product_hashtags_dict: already exists")
        except Exception as e:
            results.append(f"product_hashtags_dict: error - {str(e)}")
            db.rollback()
        
        # === 6. Migrate existing size data to separate columns ===
        try:
            # Парсимо існуючі size (формат "50x50x50") в окремі колонки
            db.execute(text("""
                UPDATE products 
                SET 
                    height_cm = CAST(SUBSTRING_INDEX(size, 'x', 1) AS DECIMAL(10,2)),
                    width_cm = CAST(SUBSTRING_INDEX(SUBSTRING_INDEX(size, 'x', 2), 'x', -1) AS DECIMAL(10,2)),
                    depth_cm = CAST(SUBSTRING_INDEX(size, 'x', -1) AS DECIMAL(10,2))
                WHERE size IS NOT NULL 
                AND size != ''
                AND size LIKE '%x%x%'
                AND height_cm IS NULL
            """))
            migrated = db.execute(text("SELECT ROW_COUNT()")).scalar()
            db.commit()
            results.append(f"size migration: {migrated} products updated")
        except Exception as e:
            results.append(f"size migration: error - {str(e)}")
            db.rollback()
        
        db.close()
        
        return {
            "success": True,
            "migration": "products-extended-attributes",
            "results": results
        }
        
    except Exception as e:
        logger.error(f"Products extended attributes migration failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Помилка міграції: {str(e)}"
        )

        try:
            check = db.execute(text("""
                SELECT COUNT(*) FROM information_schema.COLUMNS 
                WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'documents' 
                AND COLUMN_NAME = 'annex_id'
            """)).scalar()
            
            if not check:
                db.execute(text("""
                    ALTER TABLE documents 
                    ADD COLUMN annex_id INT NULL 
                    COMMENT 'Reference to order annex'
                """))
                db.commit()
                results.append("documents.annex_id: added")
            else:
                results.append("documents.annex_id: already exists")
        except Exception as e:
            results.append(f"documents.annex_id: error - {str(e)}")
            db.rollback()
        
        # === 9. CREATE document_emails TABLE ===
        try:
            check = db.execute(text("""
                SELECT COUNT(*) FROM information_schema.TABLES 
                WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'document_emails'
            """)).scalar()
            
            if not check:
                db.execute(text("""
                    CREATE TABLE document_emails (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        document_id VARCHAR(100) NOT NULL,
                        sent_to VARCHAR(255) NOT NULL,
                        sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        status ENUM('sent', 'failed', 'opened') DEFAULT 'sent',
                        error_message TEXT,
                        
                        INDEX idx_de_document (document_id),
                        INDEX idx_de_sent_at (sent_at)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 
                    COMMENT='Email log for documents'
                """))
                db.commit()
                results.append("document_emails: created")
            else:
                results.append("document_emails: already exists")
        except Exception as e:
            results.append(f"document_emails: error - {str(e)}")
            db.rollback()
        
        # === 10. CREATE document_signatures TABLE (for future) ===
        try:
            check = db.execute(text("""
                SELECT COUNT(*) FROM information_schema.TABLES 
                WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'document_signatures'
            """)).scalar()
            
            if not check:
                db.execute(text("""
                    CREATE TABLE document_signatures (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        document_id VARCHAR(100) NOT NULL,
                        signature_image MEDIUMTEXT COMMENT 'Base64 signature',
                        signer_name VARCHAR(255),
                        signer_role VARCHAR(100),
                        signed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        ip_address VARCHAR(50),
                        user_agent TEXT,
                        
                        INDEX idx_ds_document (document_id)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 
                    COMMENT='Digital signatures for documents'
                """))
                db.commit()
                results.append("document_signatures: created")
            else:
                results.append("document_signatures: already exists")
        except Exception as e:
            results.append(f"document_signatures: error - {str(e)}")
            db.rollback()
        
        db.close()
        
        return {
            "success": True,
            "migration": "documents-engine-v3",
            "results": results
        }
        
    except Exception as e:
        logger.error(f"Documents Engine V3 migration failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Помилка міграції: {str(e)}"
        )


@router.post("/payment-annex-linking")
async def migrate_payment_annex_linking():
    """
    Phase 3.2: Add annex_id to fin_payments for legal linking
    
    - Adds annex_id column to fin_payments
    - Creates index for efficient lookups
    """
    try:
        from database_rentalhub import get_rh_db_sync
        db = get_rh_db_sync()
        results = []
        
        # === 1. ADD annex_id TO fin_payments ===
        try:
            check = db.execute(text("""
                SELECT 1 FROM information_schema.COLUMNS 
                WHERE TABLE_SCHEMA = DATABASE() 
                AND TABLE_NAME = 'fin_payments'
                AND COLUMN_NAME = 'annex_id'
            """)).fetchone()
            
            if not check:
                db.execute(text("""
                    ALTER TABLE fin_payments 
                    ADD COLUMN annex_id INT NULL 
                    COMMENT 'Link to order_annexes for legal documents',
                    ADD INDEX idx_payments_annex (annex_id)
                """))
                db.commit()
                results.append("fin_payments.annex_id: added")
            else:
                results.append("fin_payments.annex_id: already exists")
        except Exception as e:
            results.append(f"fin_payments.annex_id: error - {str(e)}")
            db.rollback()
        
        # === 2. ADD document_version TO document_emails ===
        try:
            check = db.execute(text("""
                SELECT 1 FROM information_schema.COLUMNS 
                WHERE TABLE_SCHEMA = DATABASE() 
                AND TABLE_NAME = 'document_emails'
                AND COLUMN_NAME = 'document_version'
            """)).fetchone()
            
            if not check:
                db.execute(text("""
                    ALTER TABLE document_emails 
                    ADD COLUMN document_version INT DEFAULT 1,
                    ADD COLUMN sent_by_user_id INT NULL,
                    ADD COLUMN sent_by_user_name VARCHAR(255)
                """))
                db.commit()
                results.append("document_emails: added version/user columns")
            else:
                results.append("document_emails: columns already exist")
        except Exception as e:
            results.append(f"document_emails: error - {str(e)}")
            db.rollback()
        
        # === 3. ADD subject/message TO document_emails ===
        try:
            check = db.execute(text("""
                SELECT 1 FROM information_schema.COLUMNS 
                WHERE TABLE_SCHEMA = DATABASE() 
                AND TABLE_NAME = 'document_emails'
                AND COLUMN_NAME = 'subject'
            """)).fetchone()
            
            if not check:
                db.execute(text("""
                    ALTER TABLE document_emails 
                    ADD COLUMN subject VARCHAR(500),
                    ADD COLUMN message TEXT
                """))
                db.commit()
                results.append("document_emails: added subject/message columns")
            else:
                results.append("document_emails: subject/message columns already exist")
        except Exception as e:
            results.append(f"document_emails subject/message: error - {str(e)}")
            db.rollback()
        
        # === 4. ADD provider columns TO document_emails ===
        try:
            check = db.execute(text("""
                SELECT 1 FROM information_schema.COLUMNS 
                WHERE TABLE_SCHEMA = DATABASE() 
                AND TABLE_NAME = 'document_emails'
                AND COLUMN_NAME = 'provider'
            """)).fetchone()
            
            if not check:
                db.execute(text("""
                    ALTER TABLE document_emails 
                    ADD COLUMN provider VARCHAR(50) DEFAULT 'dummy',
                    ADD COLUMN provider_email_id VARCHAR(255)
                """))
                db.commit()
                results.append("document_emails: added provider columns")
            else:
                results.append("document_emails: provider columns already exist")
        except Exception as e:
            results.append(f"document_emails provider: error - {str(e)}")
            db.rollback()
        
        db.close()
        
        return {
            "success": True,
            "migration": "payment-annex-linking",
            "results": results
        }
        
    except Exception as e:
        logger.error(f"Payment-Annex Linking migration failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Помилка міграції: {str(e)}"
        )


@router.post("/event-tool-orders")
async def migrate_event_tool_orders():
    """
    EventTool Integration: Add source and event_board_id columns to orders table.
    Also ensures IT- order numbering starts from 10000.
    """
    try:
        from database_rentalhub import get_rh_db_sync
        db = get_rh_db_sync()
        results = []
        
        # === 1. ADD source TO orders ===
        try:
            check = db.execute(text("""
                SELECT 1 FROM information_schema.COLUMNS 
                WHERE TABLE_SCHEMA = DATABASE() 
                AND TABLE_NAME = 'orders'
                AND COLUMN_NAME = 'source'
            """)).fetchone()
            
            if not check:
                db.execute(text("""
                    ALTER TABLE orders 
                    ADD COLUMN source VARCHAR(50) DEFAULT 'opencart'
                    COMMENT 'Order source: opencart, event_tool, manual'
                """))
                db.commit()
                results.append("orders.source: added")
            else:
                results.append("orders.source: already exists")
        except Exception as e:
            results.append(f"orders.source: error - {str(e)}")
            db.rollback()
        
        # === 2. ADD event_board_id TO orders ===
        try:
            check = db.execute(text("""
                SELECT 1 FROM information_schema.COLUMNS 
                WHERE TABLE_SCHEMA = DATABASE() 
                AND TABLE_NAME = 'orders'
                AND COLUMN_NAME = 'event_board_id'
            """)).fetchone()
            
            if not check:
                db.execute(text("""
                    ALTER TABLE orders 
                    ADD COLUMN event_board_id VARCHAR(36) NULL
                    COMMENT 'UUID of EventTool board if source=event_tool',
                    ADD INDEX idx_orders_event_board (event_board_id)
                """))
                db.commit()
                results.append("orders.event_board_id: added")
            else:
                results.append("orders.event_board_id: already exists")
        except Exception as e:
            results.append(f"orders.event_board_id: error - {str(e)}")
            db.rollback()
        
        db.close()
        
        return {
            "success": True,
            "migration": "event-tool-orders",
            "results": results
        }
        
    except Exception as e:
        logger.error(f"EventTool Orders migration failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Помилка міграції: {str(e)}"
        )



@router.post("/client-payer-architecture")
async def migrate_client_payer_architecture():
    """
    ФАЗА 1: Архітектура Client/Payer для Finance Cabinet
    
    Створює:
    - client_users: контакти/клієнти (один email = один клієнт)
    - payer_profiles: платники (5 типів з реквізитами)
    - client_payer_links: зв'язка клієнт ↔ платники
    - Додає client_user_id та payer_profile_id в orders
    
    Safe to run multiple times.
    """
    try:
        db = get_rh_db_sync()
        results = []
        
        # === 1. CREATE client_users TABLE ===
        try:
            check = db.execute(text("""
                SELECT COUNT(*) FROM information_schema.TABLES 
                WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'client_users'
            """)).scalar()
            
            if not check:
                db.execute(text("""
                    CREATE TABLE client_users (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        email VARCHAR(255) NOT NULL COMMENT 'Original email',
                        email_normalized VARCHAR(255) NOT NULL COMMENT 'Lowercase trimmed email',
                        phone VARCHAR(50) NULL,
                        full_name VARCHAR(255) NULL,
                        company_hint VARCHAR(255) NULL COMMENT 'Підказка компанії від клієнта',
                        source VARCHAR(50) DEFAULT 'rentalhub' COMMENT 'rentalhub/events/import/opencart',
                        notes TEXT NULL COMMENT 'Нотатки менеджера',
                        preferred_contact VARCHAR(50) NULL COMMENT 'telegram/viber/whatsapp/email/phone',
                        is_active BOOLEAN DEFAULT TRUE,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                        UNIQUE KEY uk_client_email (email_normalized),
                        INDEX idx_client_phone (phone),
                        INDEX idx_client_source (source)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                    COMMENT='Клієнти/контакти - один email = один клієнт'
                """))
                db.commit()
                results.append("client_users: TABLE CREATED")
            else:
                results.append("client_users: already exists")
        except Exception as e:
            results.append(f"client_users: error - {str(e)}")
            db.rollback()
        
        # === 2. CREATE payer_profiles TABLE ===
        try:
            check = db.execute(text("""
                SELECT COUNT(*) FROM information_schema.TABLES 
                WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'payer_profiles'
            """)).scalar()
            
            if not check:
                db.execute(text("""
                    CREATE TABLE payer_profiles (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        
                        -- Основні поля
                        type VARCHAR(50) NOT NULL DEFAULT 'individual' 
                            COMMENT 'individual/fop/company/foreign/pending',
                        display_name VARCHAR(255) NOT NULL COMMENT 'Як показувати в UI',
                        tax_mode VARCHAR(50) NULL COMMENT 'none/simplified/general/vat',
                        
                        -- Реквізити (структурований JSON для гнучкості)
                        details_json JSON NULL COMMENT 'Всі реквізити платника',
                        
                        -- Окремі поля для швидкого пошуку/фільтрації
                        legal_name VARCHAR(255) NULL COMMENT 'Юридична назва',
                        edrpou VARCHAR(20) NULL COMMENT 'ЄДРПОУ/ІПН',
                        iban VARCHAR(50) NULL COMMENT 'IBAN рахунок',
                        
                        -- Контакти для документів
                        email_for_docs VARCHAR(255) NULL,
                        phone_for_docs VARCHAR(50) NULL,
                        
                        -- Підписант
                        signatory_name VARCHAR(255) NULL COMMENT 'ПІБ підписанта',
                        signatory_basis VARCHAR(255) NULL COMMENT 'На підставі чого діє',
                        
                        -- Службові
                        is_active BOOLEAN DEFAULT TRUE,
                        created_by_user_id INT NULL COMMENT 'Хто створив (менеджер)',
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                        
                        INDEX idx_payer_type (type),
                        INDEX idx_payer_edrpou (edrpou),
                        INDEX idx_payer_display (display_name)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                    COMMENT='Профілі платників - 5 типів з реквізитами'
                """))
                db.commit()
                results.append("payer_profiles: TABLE CREATED")
            else:
                results.append("payer_profiles: already exists")
        except Exception as e:
            results.append(f"payer_profiles: error - {str(e)}")
            db.rollback()
        
        # === 3. CREATE client_payer_links TABLE ===
        try:
            check = db.execute(text("""
                SELECT COUNT(*) FROM information_schema.TABLES 
                WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'client_payer_links'
            """)).scalar()
            
            if not check:
                db.execute(text("""
                    CREATE TABLE client_payer_links (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        client_user_id INT NOT NULL,
                        payer_profile_id INT NOT NULL,
                        is_default BOOLEAN DEFAULT FALSE COMMENT 'Платник за замовчуванням',
                        label VARCHAR(100) NULL COMMENT 'Мітка: "Для проєкту X"',
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        
                        UNIQUE KEY uk_client_payer (client_user_id, payer_profile_id),
                        INDEX idx_link_client (client_user_id),
                        INDEX idx_link_payer (payer_profile_id),
                        
                        CONSTRAINT fk_link_client FOREIGN KEY (client_user_id) 
                            REFERENCES client_users(id) ON DELETE CASCADE,
                        CONSTRAINT fk_link_payer FOREIGN KEY (payer_profile_id) 
                            REFERENCES payer_profiles(id) ON DELETE CASCADE
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                    COMMENT='Зв язок клієнт ↔ платники (один клієнт може мати багато платників)'
                """))
                db.commit()
                results.append("client_payer_links: TABLE CREATED")
            else:
                results.append("client_payer_links: already exists")
        except Exception as e:
            results.append(f"client_payer_links: error - {str(e)}")
            db.rollback()
        
        # === 4. ADD client_user_id TO orders ===
        try:
            check = db.execute(text("""
                SELECT COUNT(*) FROM information_schema.COLUMNS 
                WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'orders' 
                AND COLUMN_NAME = 'client_user_id'
            """)).scalar()
            
            if not check:
                db.execute(text("""
                    ALTER TABLE orders 
                    ADD COLUMN client_user_id INT NULL 
                    COMMENT 'FK to client_users - контакт/замовник',
                    ADD INDEX idx_orders_client (client_user_id)
                """))
                db.commit()
                results.append("orders.client_user_id: ADDED")
            else:
                results.append("orders.client_user_id: already exists")
        except Exception as e:
            results.append(f"orders.client_user_id: error - {str(e)}")
            db.rollback()
        
        # === 5. ADD payer_profile_id TO orders ===
        try:
            check = db.execute(text("""
                SELECT COUNT(*) FROM information_schema.COLUMNS 
                WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'orders' 
                AND COLUMN_NAME = 'payer_profile_id'
            """)).scalar()
            
            if not check:
                db.execute(text("""
                    ALTER TABLE orders 
                    ADD COLUMN payer_profile_id INT NULL 
                    COMMENT 'FK to payer_profiles - платник замовлення',
                    ADD INDEX idx_orders_payer (payer_profile_id)
                """))
                db.commit()
                results.append("orders.payer_profile_id: ADDED")
            else:
                results.append("orders.payer_profile_id: already exists")
        except Exception as e:
            results.append(f"orders.payer_profile_id: error - {str(e)}")
            db.rollback()
        
        # === 6. ADD payer_snapshot_json TO orders ===
        try:
            check = db.execute(text("""
                SELECT COUNT(*) FROM information_schema.COLUMNS 
                WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'orders' 
                AND COLUMN_NAME = 'payer_snapshot_json'
            """)).scalar()
            
            if not check:
                db.execute(text("""
                    ALTER TABLE orders 
                    ADD COLUMN payer_snapshot_json JSON NULL 
                    COMMENT 'Зліпок реквізитів платника на момент документів'
                """))
                db.commit()
                results.append("orders.payer_snapshot_json: ADDED")
            else:
                results.append("orders.payer_snapshot_json: already exists")
        except Exception as e:
            results.append(f"orders.payer_snapshot_json: error - {str(e)}")
            db.rollback()
        
        # === 7. ADD source TO orders (if not exists from previous migration) ===
        try:
            check = db.execute(text("""
                SELECT COUNT(*) FROM information_schema.COLUMNS 
                WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'orders' 
                AND COLUMN_NAME = 'source'
            """)).scalar()
            
            if not check:
                db.execute(text("""
                    ALTER TABLE orders 
                    ADD COLUMN source VARCHAR(50) NULL 
                    COMMENT 'Джерело: rentalhub/event_tool/opencart'
                """))
                db.commit()
                results.append("orders.source: ADDED")
            else:
                results.append("orders.source: already exists")
        except Exception as e:
            results.append(f"orders.source: error - {str(e)}")
            db.rollback()
        
        # === 8. ADD event_board_id TO orders ===
        try:
            check = db.execute(text("""
                SELECT COUNT(*) FROM information_schema.COLUMNS 
                WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'orders' 
                AND COLUMN_NAME = 'event_board_id'
            """)).scalar()
            
            if not check:
                db.execute(text("""
                    ALTER TABLE orders 
                    ADD COLUMN event_board_id VARCHAR(36) NULL 
                    COMMENT 'UUID мудборду з EventTool'
                """))
                db.commit()
                results.append("orders.event_board_id: ADDED")
            else:
                results.append("orders.event_board_id: already exists")
        except Exception as e:
            results.append(f"orders.event_board_id: error - {str(e)}")
            db.rollback()
        
        db.close()
        
        return {
            "success": True,
            "migration": "client-payer-architecture",
            "description": "Архітектура Client/Payer для Finance Cabinet",
            "tables_created": ["client_users", "payer_profiles", "client_payer_links"],
            "orders_columns": ["client_user_id", "payer_profile_id", "payer_snapshot_json", "source", "event_board_id"],
            "results": results
        }
        
    except Exception as e:
        logger.error(f"Client/Payer migration failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Помилка міграції: {str(e)}"
        )


@router.post("/migrate-existing-clients")
async def migrate_existing_clients_to_client_users():
    """
    Міграція існуючих клієнтів з orders в client_users.
    Об'єднує записи по email (один email = один client_user).
    
    Safe to run multiple times - перевіряє чи клієнт вже існує.
    """
    try:
        db = get_rh_db_sync()
        results = {
            "created": 0,
            "skipped": 0,
            "linked": 0,
            "errors": []
        }
        
        # Отримати унікальні email з orders
        emails_query = db.execute(text("""
            SELECT DISTINCT 
                LOWER(TRIM(customer_email)) as email_norm,
                customer_email,
                customer_name,
                customer_phone,
                source
            FROM orders 
            WHERE customer_email IS NOT NULL 
            AND customer_email != ''
            ORDER BY created_at DESC
        """))
        
        for row in emails_query:
            email_norm = row[0]
            email_orig = row[1]
            name = row[2]
            phone = row[3]
            source = row[4] or 'rentalhub'
            
            if not email_norm:
                continue
            
            try:
                # Перевірити чи вже існує
                existing = db.execute(text("""
                    SELECT id FROM client_users WHERE email_normalized = :email
                """), {"email": email_norm}).fetchone()
                
                if existing:
                    client_id = existing[0]
                    results["skipped"] += 1
                else:
                    # Створити нового клієнта
                    db.execute(text("""
                        INSERT INTO client_users (email, email_normalized, full_name, phone, source)
                        VALUES (:email, :email_norm, :name, :phone, :source)
                    """), {
                        "email": email_orig,
                        "email_norm": email_norm,
                        "name": name,
                        "phone": phone,
                        "source": source
                    })
                    db.commit()
                    
                    # Отримати ID
                    client_id = db.execute(text("""
                        SELECT id FROM client_users WHERE email_normalized = :email
                    """), {"email": email_norm}).fetchone()[0]
                    
                    results["created"] += 1
                
                # Оновити orders з цим email
                updated = db.execute(text("""
                    UPDATE orders 
                    SET client_user_id = :client_id 
                    WHERE LOWER(TRIM(customer_email)) = :email 
                    AND (client_user_id IS NULL OR client_user_id != :client_id)
                """), {"client_id": client_id, "email": email_norm})
                db.commit()
                
                results["linked"] += updated.rowcount
                
            except Exception as e:
                results["errors"].append(f"{email_norm}: {str(e)}")
                db.rollback()
        
        db.close()
        
        return {
            "success": True,
            "migration": "migrate-existing-clients",
            "results": results
        }
        
    except Exception as e:
        logger.error(f"Client migration failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Помилка міграції: {str(e)}"
        )
