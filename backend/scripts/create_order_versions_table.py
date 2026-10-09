"""
Створити таблицю order_section_versions для real-time синхронізації
"""
from sqlalchemy import text
import sys
sys.path.insert(0, '/app/backend')
from database_rentalhub import get_rh_db

def create_table():
    db = next(get_rh_db())
    try:
        # Перевірити чи таблиця вже існує
        result = db.execute(text("SHOW TABLES LIKE 'order_section_versions'"))
        if result.fetchone():
            print("✅ Таблиця order_section_versions вже існує")
            return
        
        # Створити таблицю
        db.execute(text("""
            CREATE TABLE order_section_versions (
                id INT AUTO_INCREMENT PRIMARY KEY,
                order_id INT NOT NULL,
                section VARCHAR(50) NOT NULL,
                version INT DEFAULT 1,
                modified_by_id INT NULL,
                modified_by_name VARCHAR(100) NULL,
                modified_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_order_section (order_id, section)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """))
        db.commit()
        print("✅ Таблиця order_section_versions створена успішно")
    except Exception as e:
        print(f"❌ Помилка: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    create_table()
