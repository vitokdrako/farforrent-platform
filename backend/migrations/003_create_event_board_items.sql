-- Міграція 003: Створення таблиці event_board_items
-- Товари в event board

CREATE TABLE IF NOT EXISTS event_board_items (
    item_id INT PRIMARY KEY AUTO_INCREMENT,
    board_id INT NOT NULL COMMENT 'ID event board',
    product_id INT NOT NULL COMMENT 'ID товару з таблиці products',
    quantity INT NOT NULL DEFAULT 1 COMMENT 'Кількість товару',
    notes TEXT NULL COMMENT 'Примітки до товару в цьому board',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    FOREIGN KEY (board_id) REFERENCES event_boards(board_id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products(product_id),
    
    INDEX idx_board (board_id),
    INDEX idx_product (product_id),
    
    UNIQUE KEY unique_board_product (board_id, product_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Товари в event boards';

SELECT '✅ Migration 003 completed successfully' AS status;
