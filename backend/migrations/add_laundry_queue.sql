-- Таблиця черги хімчистки
CREATE TABLE IF NOT EXISTS laundry_queue (
    id VARCHAR(50) PRIMARY KEY,
    batch_id VARCHAR(50) DEFAULT NULL,
    damage_id VARCHAR(50),
    order_id INT,
    order_number VARCHAR(100),
    product_id INT,
    product_name VARCHAR(255) NOT NULL,
    sku VARCHAR(100) NOT NULL,
    category VARCHAR(100) DEFAULT 'textile',
    quantity INT DEFAULT 1,
    `condition` VARCHAR(50) DEFAULT 'dirty',
    notes TEXT,
    source VARCHAR(50) DEFAULT 'damage_cabinet',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100),
    FOREIGN KEY (batch_id) REFERENCES laundry_batches(id) ON DELETE SET NULL
);

-- Індекси
CREATE INDEX idx_laundry_queue_batch ON laundry_queue(batch_id);
CREATE INDEX idx_laundry_queue_damage ON laundry_queue(damage_id);
CREATE INDEX idx_laundry_queue_order ON laundry_queue(order_id);
