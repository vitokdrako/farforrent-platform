-- Phase 2 — Warehouse Transfers (переміщення між складами)
-- 2026-02-26

CREATE TABLE IF NOT EXISTS warehouse_transfers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    transfer_number VARCHAR(32) NOT NULL UNIQUE,
    from_warehouse_id INT NOT NULL,
    to_warehouse_id INT NOT NULL,
    status ENUM('draft', 'in_transit', 'received', 'cancelled') NOT NULL DEFAULT 'draft',
    note TEXT NULL,
    created_by INT NULL,
    shipped_by INT NULL,
    received_by INT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    shipped_at DATETIME NULL,
    received_at DATETIME NULL,
    cancelled_at DATETIME NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    CONSTRAINT fk_wt_from FOREIGN KEY (from_warehouse_id) REFERENCES warehouses(id),
    CONSTRAINT fk_wt_to   FOREIGN KEY (to_warehouse_id)   REFERENCES warehouses(id),

    INDEX idx_wt_status (status),
    INDEX idx_wt_from (from_warehouse_id, status),
    INDEX idx_wt_to (to_warehouse_id, status),
    INDEX idx_wt_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


CREATE TABLE IF NOT EXISTS warehouse_transfer_items (
    id INT AUTO_INCREMENT PRIMARY KEY,
    transfer_id INT NOT NULL,
    product_id INT NOT NULL,
    quantity INT NOT NULL,
    note VARCHAR(255) NULL,

    CONSTRAINT fk_wti_transfer FOREIGN KEY (transfer_id) REFERENCES warehouse_transfers(id) ON DELETE CASCADE,
    INDEX idx_wti_transfer (transfer_id),
    INDEX idx_wti_product (product_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
