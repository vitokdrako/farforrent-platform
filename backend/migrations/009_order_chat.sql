-- ============================================================================
-- Migration 009: Order chat (manager ↔ client per order)
-- ============================================================================
CREATE TABLE IF NOT EXISTS order_chat_messages (
    id INT AUTO_INCREMENT PRIMARY KEY,
    order_id INT NOT NULL,
    sender_type ENUM('client','manager','system') NOT NULL,
    sender_id INT DEFAULT NULL,
    sender_name VARCHAR(255) DEFAULT NULL,
    message TEXT NOT NULL,
    attachment_url VARCHAR(500) DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    read_by_client_at TIMESTAMP NULL DEFAULT NULL,
    read_by_manager_at TIMESTAMP NULL DEFAULT NULL,
    INDEX idx_chat_order (order_id, created_at),
    INDEX idx_chat_unread_client (order_id, read_by_client_at),
    INDEX idx_chat_unread_manager (order_id, read_by_manager_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
