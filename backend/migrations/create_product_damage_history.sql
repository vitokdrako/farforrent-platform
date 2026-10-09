-- Таблиця для історії пошкоджень товарів
-- Використовується для фіксації пошкоджень до видачі та при поверненні

CREATE TABLE IF NOT EXISTS product_damage_history (
    id VARCHAR(36) PRIMARY KEY,
    product_id INT NOT NULL,
    sku VARCHAR(255),
    product_name VARCHAR(500),
    category VARCHAR(255),
    
    -- Контекст пошкодження
    order_id INT,
    order_number VARCHAR(50),
    stage ENUM('pre_issue', 'return') NOT NULL COMMENT 'Етап: до видачі або при поверненні',
    
    -- Деталі пошкодження
    damage_type VARCHAR(255) NOT NULL,
    damage_code VARCHAR(100),
    severity ENUM('low', 'medium', 'high', 'critical') DEFAULT 'low',
    fee DECIMAL(10,2) DEFAULT 0.00,
    
    -- Документація
    photo_url VARCHAR(500),
    note TEXT,
    
    -- Метадані
    created_by VARCHAR(255),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_product_id (product_id),
    INDEX idx_sku (sku),
    INDEX idx_order_id (order_id),
    INDEX idx_stage (stage),
    INDEX idx_created_at (created_at),
    
    FOREIGN KEY (product_id) REFERENCES products(product_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
