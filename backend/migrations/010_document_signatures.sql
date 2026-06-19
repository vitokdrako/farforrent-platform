-- ============================================================================
-- Migration 010: document_signatures table (signatures + inline approvals)
-- Was referenced by code but never explicitly created.
-- ============================================================================
CREATE TABLE IF NOT EXISTS document_signatures (
    id INT AUTO_INCREMENT PRIMARY KEY,
    document_id VARCHAR(100) NOT NULL,
    signer_role ENUM('landlord','tenant') NOT NULL,
    signature_image LONGTEXT NOT NULL,
    signer_name VARCHAR(255) DEFAULT NULL,
    ip_address VARCHAR(64) DEFAULT NULL,
    user_agent VARCHAR(512) DEFAULT NULL,
    signed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uniq_doc_role (document_id, signer_role),
    INDEX idx_sig_doc (document_id),
    INDEX idx_sig_role (signer_role)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
