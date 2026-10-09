-- Міграція 004: Створення таблиці soft_reservations
-- Тимчасові резервації товарів поки клієнт працює з board

CREATE TABLE IF NOT EXISTS soft_reservations (
    reservation_id INT PRIMARY KEY AUTO_INCREMENT,
    board_id INT NOT NULL COMMENT 'ID event board',
    product_id INT NOT NULL COMMENT 'ID товару',
    quantity INT NOT NULL DEFAULT 1 COMMENT 'Зарезервована кількість',
    reserved_until DATETIME NOT NULL COMMENT 'Резервація діє до цієї дати',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (board_id) REFERENCES event_boards(board_id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products(product_id),
    
    INDEX idx_board (board_id),
    INDEX idx_product (product_id),
    INDEX idx_expiry (reserved_until),
    INDEX idx_product_expiry (product_id, reserved_until)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Тимчасові м''які резервації товарів для event boards';

-- Створити event для автоматичного очищення застарілих резервацій
DROP EVENT IF EXISTS cleanup_expired_soft_reservations;

CREATE EVENT cleanup_expired_soft_reservations
ON SCHEDULE EVERY 1 HOUR
DO
  DELETE FROM soft_reservations WHERE reserved_until < NOW();

SELECT '✅ Migration 004 completed successfully' AS status;
