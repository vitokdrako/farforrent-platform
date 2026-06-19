-- ============================================================================
-- Migration 007: Event Tool Favorites (Обране)
-- ============================================================================
CREATE TABLE IF NOT EXISTS event_favorites (
    id INT AUTO_INCREMENT PRIMARY KEY,
    customer_id INT NOT NULL,
    product_id INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uniq_customer_product (customer_id, product_id),
    INDEX idx_favorites_customer (customer_id),
    INDEX idx_favorites_product (product_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
