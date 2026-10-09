-- Міграція 001: Модифікація таблиці customers для Event Tool
-- Додаємо поля для authentication клієнтів

-- Перевірка існування колонок перед додаванням
SET @dbname = DATABASE();
SET @tablename = 'customers';

-- Додати password_hash якщо не існує
SET @col_exists = (
    SELECT COUNT(*) 
    FROM INFORMATION_SCHEMA.COLUMNS 
    WHERE TABLE_SCHEMA = @dbname 
    AND TABLE_NAME = @tablename 
    AND COLUMN_NAME = 'password_hash'
);

SET @sql = IF(@col_exists = 0,
    'ALTER TABLE customers ADD COLUMN password_hash VARCHAR(255) NULL COMMENT "Bcrypt хеш паролю для Event Tool клієнтів"',
    'SELECT "Column password_hash already exists" AS msg'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Додати is_active якщо не існує
SET @col_exists = (
    SELECT COUNT(*) 
    FROM INFORMATION_SCHEMA.COLUMNS 
    WHERE TABLE_SCHEMA = @dbname 
    AND TABLE_NAME = @tablename 
    AND COLUMN_NAME = 'is_active'
);

SET @sql = IF(@col_exists = 0,
    'ALTER TABLE customers ADD COLUMN is_active BOOLEAN DEFAULT TRUE COMMENT "Чи активний акаунт"',
    'SELECT "Column is_active already exists" AS msg'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Додати email_verified якщо не існує
SET @col_exists = (
    SELECT COUNT(*) 
    FROM INFORMATION_SCHEMA.COLUMNS 
    WHERE TABLE_SCHEMA = @dbname 
    AND TABLE_NAME = @tablename 
    AND COLUMN_NAME = 'email_verified'
);

SET @sql = IF(@col_exists = 0,
    'ALTER TABLE customers ADD COLUMN email_verified BOOLEAN DEFAULT FALSE COMMENT "Чи підтверджена email адреса"',
    'SELECT "Column email_verified already exists" AS msg'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Додати last_login якщо не існує
SET @col_exists = (
    SELECT COUNT(*) 
    FROM INFORMATION_SCHEMA.COLUMNS 
    WHERE TABLE_SCHEMA = @dbname 
    AND TABLE_NAME = @tablename 
    AND COLUMN_NAME = 'last_login'
);

SET @sql = IF(@col_exists = 0,
    'ALTER TABLE customers ADD COLUMN last_login DATETIME NULL COMMENT "Остання дата входу"',
    'SELECT "Column last_login already exists" AS msg'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Створити індекс для швидкого пошуку по email
SET @index_exists = (
    SELECT COUNT(*)
    FROM INFORMATION_SCHEMA.STATISTICS
    WHERE TABLE_SCHEMA = @dbname
    AND TABLE_NAME = @tablename
    AND INDEX_NAME = 'idx_customers_email'
);

SET @sql = IF(@index_exists = 0,
    'CREATE INDEX idx_customers_email ON customers(email)',
    'SELECT "Index idx_customers_email already exists" AS msg'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SELECT '✅ Migration 001 completed successfully' AS status;
