-- Міграція: Додавання трекінгу користувачів
-- Дата: 2025-12-05
-- Призначення: Відстежувати хто і коли працював з кожним замовленням

-- ============================================
-- 1. ORDERS - хто створив, підтвердив, оновив
-- ============================================

ALTER TABLE orders 
ADD COLUMN created_by_id INT DEFAULT NULL COMMENT 'Менеджер що створив замовлення',
ADD COLUMN confirmed_by_id INT DEFAULT NULL COMMENT 'Менеджер що підтвердив',
ADD COLUMN updated_by_id INT DEFAULT NULL COMMENT 'Хто останній редагував',
ADD COLUMN confirmed_at TIMESTAMP NULL COMMENT 'Коли підтверджено';

-- ============================================
-- 2. ISSUE CARDS - хто створив, підготував, видав
-- ============================================

ALTER TABLE issue_cards
ADD COLUMN created_by_id INT DEFAULT NULL COMMENT 'Менеджер що створив картку',
ADD COLUMN prepared_by_id INT DEFAULT NULL COMMENT 'Реквізитор що підготував',
ADD COLUMN issued_by_id INT DEFAULT NULL COMMENT 'Реквізитор що видав клієнту',
ADD COLUMN prepared_at TIMESTAMP NULL COMMENT 'Коли підготовлено',
ADD COLUMN issued_at TIMESTAMP NULL COMMENT 'Коли видано клієнту';

-- ============================================
-- 3. КОМПЛЕКТАЦІЯ - хто що пакував (КІЛЬКА реквізиторів)
-- ============================================

CREATE TABLE IF NOT EXISTS order_item_packing (
    id VARCHAR(36) PRIMARY KEY,
    order_id INT NOT NULL,
    item_id VARCHAR(100) NOT NULL COMMENT 'ID товару в замовленні',
    product_id INT NOT NULL,
    sku VARCHAR(50) NOT NULL,
    product_name VARCHAR(255),
    quantity INT NOT NULL COMMENT 'Кількість що запакував',
    packed_by_id INT NOT NULL COMMENT 'Реквізитор що запакував',
    packed_by_name VARCHAR(100) COMMENT 'Імʼя реквізитора',
    packed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT 'Коли запаковано',
    location VARCHAR(100) COMMENT 'Локація звідки взято (zone-aisle-shelf)',
    notes TEXT COMMENT 'Примітки (якщо є)',
    
    INDEX idx_order_id (order_id),
    INDEX idx_packed_by (packed_by_id),
    INDEX idx_sku (sku),
    FOREIGN KEY (order_id) REFERENCES orders(order_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 4. RETURN CARDS - хто прийняв, перевірив (якщо є окрема таблиця)
-- ============================================

-- Якщо є окрема таблиця return_cards
-- ALTER TABLE return_cards
-- ADD COLUMN received_by_id INT DEFAULT NULL COMMENT 'Реквізитор що прийняв',
-- ADD COLUMN checked_by_id INT DEFAULT NULL COMMENT 'Хто перевірив стан',
-- ADD COLUMN received_at TIMESTAMP NULL COMMENT 'Коли прийнято';

-- Поки що зберігаємо в issue_cards
ALTER TABLE issue_cards
ADD COLUMN received_by_id INT DEFAULT NULL COMMENT 'Реквізитор що прийняв повернення',
ADD COLUMN checked_by_id INT DEFAULT NULL COMMENT 'Хто перевірив стан товару',
ADD COLUMN received_at TIMESTAMP NULL COMMENT 'Коли прийнято повернення';

-- ============================================
-- 5. DAMAGE HISTORY - хто зафіксував (вже є created_by як текст, додаємо ID)
-- ============================================

ALTER TABLE product_damage_history
ADD COLUMN created_by_id INT DEFAULT NULL COMMENT 'ID користувача що зафіксував пошкодження';

-- Оновити existing records якщо можливо зіставити
-- UPDATE product_damage_history pdh
-- JOIN users u ON pdh.created_by = u.email OR pdh.created_by = u.name
-- SET pdh.created_by_id = u.id
-- WHERE pdh.created_by_id IS NULL;

-- ============================================
-- 6. FINANCE TRANSACTIONS - хто створив
-- ============================================

ALTER TABLE finance_transactions
ADD COLUMN created_by_id INT DEFAULT NULL COMMENT 'Хто нарахував/прийняв оплату';

-- ============================================
-- 7. ІНДЕКСИ для швидкого пошуку
-- ============================================

ALTER TABLE orders ADD INDEX idx_created_by (created_by_id);
ALTER TABLE orders ADD INDEX idx_confirmed_by (confirmed_by_id);

ALTER TABLE issue_cards ADD INDEX idx_created_by (created_by_id);
ALTER TABLE issue_cards ADD INDEX idx_prepared_by (prepared_by_id);
ALTER TABLE issue_cards ADD INDEX idx_issued_by (issued_by_id);

ALTER TABLE product_damage_history ADD INDEX idx_created_by_id (created_by_id);
ALTER TABLE finance_transactions ADD INDEX idx_created_by_id (created_by_id);

-- ============================================
-- 8. VIEW для зручного перегляду історії
-- ============================================

CREATE OR REPLACE VIEW order_action_history AS
SELECT 
    o.order_id,
    o.order_number,
    'created' as action_type,
    o.created_by_id as user_id,
    NULL as user_name,
    o.created_at as action_at
FROM orders o
WHERE o.created_by_id IS NOT NULL

UNION ALL

SELECT 
    o.order_id,
    o.order_number,
    'confirmed' as action_type,
    o.confirmed_by_id as user_id,
    NULL as user_name,
    o.confirmed_at as action_at
FROM orders o
WHERE o.confirmed_by_id IS NOT NULL

UNION ALL

SELECT 
    ic.order_id,
    ic.order_number,
    'prepared' as action_type,
    ic.prepared_by_id as user_id,
    NULL as user_name,
    ic.prepared_at as action_at
FROM issue_cards ic
WHERE ic.prepared_by_id IS NOT NULL

UNION ALL

SELECT 
    ic.order_id,
    ic.order_number,
    'issued' as action_type,
    ic.issued_by_id as user_id,
    NULL as user_name,
    ic.issued_at as action_at
FROM issue_cards ic
WHERE ic.issued_by_id IS NOT NULL

UNION ALL

SELECT 
    ic.order_id,
    ic.order_number,
    'returned' as action_type,
    ic.received_by_id as user_id,
    NULL as user_name,
    ic.received_at as action_at
FROM issue_cards ic
WHERE ic.received_by_id IS NOT NULL

ORDER BY action_at DESC;

-- ============================================
-- ГОТОВО!
-- ============================================

-- Перевірка:
-- SELECT * FROM order_item_packing LIMIT 5;
-- SELECT * FROM order_action_history WHERE order_id = 7040;
