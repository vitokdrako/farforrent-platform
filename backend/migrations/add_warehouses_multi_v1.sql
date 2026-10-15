-- ============================================================================
-- Migration: Multi-Warehouse Phase 1
-- Purpose: Додає підтримку кількох складів без ламання існуючих флоу.
-- Safe to re-run: усі ALTER/CREATE з IF NOT EXISTS, INSERT з ON DUPLICATE.
-- ============================================================================

-- 1. Таблиця складів
CREATE TABLE IF NOT EXISTS warehouses (
  id INT PRIMARY KEY AUTO_INCREMENT,
  code VARCHAR(16) UNIQUE NOT NULL,
  name VARCHAR(255) NOT NULL,
  country VARCHAR(2) NOT NULL,
  city VARCHAR(100),
  address TEXT,
  currency VARCHAR(3) NOT NULL DEFAULT 'UAH',
  timezone VARCHAR(50) DEFAULT 'Europe/Kyiv',
  phone VARCHAR(50),
  email VARCHAR(255),
  is_default BOOLEAN DEFAULT FALSE,
  is_active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_warehouses_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 2. Товар на складі (M2M з кількістю і ціною)
CREATE TABLE IF NOT EXISTS product_warehouses (
  product_id INT NOT NULL,
  warehouse_id INT NOT NULL,
  quantity INT DEFAULT 0,
  reserved_qty INT DEFAULT 0,
  min_quantity INT DEFAULT 0,
  price_override DECIMAL(10,2) NULL,
  cost_override DECIMAL(10,2) NULL,
  is_available BOOLEAN DEFAULT TRUE,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (product_id, warehouse_id),
  INDEX idx_pw_warehouse (warehouse_id),
  INDEX idx_pw_available (is_available)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 3. Доступ менеджера до складу
CREATE TABLE IF NOT EXISTS user_warehouses (
  user_id INT NOT NULL,
  warehouse_id INT NOT NULL,
  role VARCHAR(32) DEFAULT 'manager',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (user_id, warehouse_id),
  INDEX idx_uw_warehouse (warehouse_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 4. Денормалізована мультимовність для товарів
-- (Якщо колонка вже є — MySQL 8 підтримує IF NOT EXISTS у ALTER COLUMN)
SET @col_exists := (SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='products' AND COLUMN_NAME='name_en');
SET @sql := IF(@col_exists = 0,
  'ALTER TABLE products ADD COLUMN name_en VARCHAR(500) NULL AFTER name',
  'SELECT "name_en already exists"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @col_exists := (SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='products' AND COLUMN_NAME='name_es');
SET @sql := IF(@col_exists = 0,
  'ALTER TABLE products ADD COLUMN name_es VARCHAR(500) NULL AFTER name_en',
  'SELECT "name_es already exists"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @col_exists := (SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='products' AND COLUMN_NAME='description_en');
SET @sql := IF(@col_exists = 0,
  'ALTER TABLE products ADD COLUMN description_en TEXT NULL',
  'SELECT "description_en already exists"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @col_exists := (SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='products' AND COLUMN_NAME='description_es');
SET @sql := IF(@col_exists = 0,
  'ALTER TABLE products ADD COLUMN description_es TEXT NULL',
  'SELECT "description_es already exists"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 5. Прив'язка замовлень до складу
SET @col_exists := (SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='orders' AND COLUMN_NAME='warehouse_id');
SET @sql := IF(@col_exists = 0,
  'ALTER TABLE orders ADD COLUMN warehouse_id INT NULL AFTER order_number, ADD INDEX idx_orders_warehouse (warehouse_id)',
  'SELECT "orders.warehouse_id already exists"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 6. Прив'язка клієнтів до складу
SET @col_exists := (SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='client_users' AND COLUMN_NAME='warehouse_id');
SET @sql := IF(@col_exists = 0,
  'ALTER TABLE client_users ADD COLUMN warehouse_id INT NULL AFTER id, ADD INDEX idx_cu_warehouse (warehouse_id)',
  'SELECT "client_users.warehouse_id already exists"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 7. Super admin flag для users
SET @col_exists := (SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='users' AND COLUMN_NAME='is_super_admin');
SET @sql := IF(@col_exists = 0,
  'ALTER TABLE users ADD COLUMN is_super_admin BOOLEAN DEFAULT FALSE',
  'SELECT "is_super_admin already exists"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- =========================================================================
-- SEED: UA як дефолтний склад
-- =========================================================================
INSERT INTO warehouses (code, name, country, city, currency, timezone, is_default, is_active)
VALUES ('UA', 'Київ (основний)', 'UA', 'Київ', 'UAH', 'Europe/Kyiv', TRUE, TRUE)
ON DUPLICATE KEY UPDATE name = VALUES(name), is_default = VALUES(is_default);

-- Копіюємо залишки products.quantity → product_warehouses (ТІЛЬКИ якщо ще не копіювали)
INSERT INTO product_warehouses (product_id, warehouse_id, quantity, is_available)
SELECT p.product_id,
       (SELECT id FROM warehouses WHERE code='UA') AS warehouse_id,
       COALESCE(p.quantity, 0),
       CASE WHEN p.status = 'enabled' OR p.status = 1 THEN 1 ELSE 0 END
FROM products p
LEFT JOIN product_warehouses pw ON pw.product_id = p.product_id
  AND pw.warehouse_id = (SELECT id FROM warehouses WHERE code='UA')
WHERE pw.product_id IS NULL;

-- Існуючі замовлення → UA (NULL -> UA)
UPDATE orders
SET warehouse_id = (SELECT id FROM warehouses WHERE code='UA')
WHERE warehouse_id IS NULL;

-- Існуючі клієнти → UA
UPDATE client_users
SET warehouse_id = (SELECT id FROM warehouses WHERE code='UA')
WHERE warehouse_id IS NULL;

-- Всі admin юзери → UA з роллю manager
INSERT IGNORE INTO user_warehouses (user_id, warehouse_id, role)
SELECT u.user_id,
       (SELECT id FROM warehouses WHERE code='UA'),
       'manager'
FROM users u;

-- Головний адмін — super_admin
UPDATE users SET is_super_admin = TRUE WHERE email = 'vitokdrako@gmail.com';
