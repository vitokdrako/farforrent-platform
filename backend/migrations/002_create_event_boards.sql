-- Міграція 002: Створення таблиці event_boards
-- Event boards для планування подій клієнтами

CREATE TABLE IF NOT EXISTS event_boards (
    board_id INT PRIMARY KEY AUTO_INCREMENT,
    customer_id INT NOT NULL COMMENT 'ID клієнта з таблиці customers',
    board_name VARCHAR(255) NOT NULL COMMENT 'Назва події',
    event_date DATE NULL COMMENT 'Дата події',
    event_location VARCHAR(500) NULL COMMENT 'Локація події',
    guest_count INT NULL COMMENT 'Кількість гостей',
    notes TEXT NULL COMMENT 'Примітки від клієнта',
    status VARCHAR(50) DEFAULT 'draft' COMMENT 'Статус: draft, active, archived',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id) ON DELETE CASCADE,
    
    INDEX idx_customer (customer_id),
    INDEX idx_status (status),
    INDEX idx_event_date (event_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Event boards для планування подій клієнтами';

SELECT '✅ Migration 002 completed successfully' AS status;
