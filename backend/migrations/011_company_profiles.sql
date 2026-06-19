-- ============================================================================
-- Migration 011: Centralized Company Profiles
-- ============================================================================
-- Уніфіковане сховище реквізитів:
--   • Наші юр. особи (landlord/orenda) — наприклад, ФОП Николенко, ТОВ FarforDecor
--   • Клієнтські (tenant/payer) — підтягуються з payer_profiles
--
-- Тут створюється окрема таблиця company_profiles (тільки для НАШИХ компаній),
-- а payer_profiles залишається для клієнтських даних.
-- Замовлення може посилатися на company_profile_id (наша сторона) + payer_profile_id (клієнтська).
-- ============================================================================

CREATE TABLE IF NOT EXISTS company_profiles (
    id INT AUTO_INCREMENT PRIMARY KEY,
    code VARCHAR(50) NOT NULL,           -- "fop_main", "llc_decor", etc.
    display_name VARCHAR(255) NOT NULL,  -- "FarforDecor" / "ФОП Николенко"
    legal_name VARCHAR(500) NOT NULL,    -- повна юр. назва для документів
    payer_type ENUM('fop_simple','fop_general','llc_simple','llc_general','individual') NOT NULL DEFAULT 'fop_simple',
    tax_status VARCHAR(100) DEFAULT NULL,
    edrpou VARCHAR(20) DEFAULT NULL,
    iban VARCHAR(34) DEFAULT NULL,
    bank_name VARCHAR(255) DEFAULT NULL,
    address VARCHAR(500) DEFAULT NULL,
    warehouse_address VARCHAR(500) DEFAULT NULL,
    director_name VARCHAR(255) DEFAULT NULL,
    signer_name VARCHAR(255) DEFAULT NULL,
    signer_role VARCHAR(100) DEFAULT NULL,
    is_vat_payer TINYINT(1) DEFAULT 0,
    phone VARCHAR(100) DEFAULT NULL,
    email VARCHAR(255) DEFAULT NULL,
    website VARCHAR(255) DEFAULT NULL,
    logo_url VARCHAR(500) DEFAULT NULL,
    stamp_url VARCHAR(500) DEFAULT NULL,
    is_default TINYINT(1) DEFAULT 0,
    is_active TINYINT(1) DEFAULT 1,
    sort_order INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uniq_code (code),
    INDEX idx_company_default (is_default, is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Add link from orders to company_profile (наша сторона) + snapshot
ALTER TABLE orders
  ADD COLUMN company_profile_id INT DEFAULT NULL AFTER payer_profile_id;

ALTER TABLE orders
  ADD COLUMN company_snapshot_json JSON DEFAULT NULL AFTER payer_snapshot_json;

-- Seed: створюємо дефолтну компанію з system_settings якщо ще нема жодної
INSERT INTO company_profiles
    (code, display_name, legal_name, payer_type, tax_status, edrpou, iban, bank_name,
     address, warehouse_address, signer_name, phone, email, website, is_default, is_active)
SELECT
    'main',
    'FarforDecorOrenda',
    COALESCE((SELECT setting_value FROM system_settings WHERE setting_key='name'),
             'ФОП Николенко Наталя Станіславівна'),
    'fop_simple',
    COALESCE((SELECT setting_value FROM system_settings WHERE setting_key='tax_status'),
             'платник єдиного податку'),
    COALESCE((SELECT setting_value FROM system_settings WHERE setting_key='tax_id'), '3606801844'),
    COALESCE((SELECT setting_value FROM system_settings WHERE setting_key='iban'),
             'UA043220010000026003340091618'),
    COALESCE((SELECT setting_value FROM system_settings WHERE setting_key='bank_name'),
             'ПАТ "УНІВЕРСАЛ БАНК"'),
    COALESCE((SELECT setting_value FROM system_settings WHERE setting_key='address'), 'м. Київ'),
    COALESCE((SELECT setting_value FROM system_settings WHERE setting_key='warehouse_address'),
             'м. Київ, вул. Будіндустрії 4'),
    COALESCE((SELECT setting_value FROM system_settings WHERE setting_key='signer_name'),
             'Николенко Н.С.'),
    COALESCE((SELECT setting_value FROM system_settings WHERE setting_key='phone'),
             '(097) 123 09 93, (093) 375 09 40'),
    COALESCE((SELECT setting_value FROM system_settings WHERE setting_key='email'),
             'info@farforrent.com.ua'),
    COALESCE((SELECT setting_value FROM system_settings WHERE setting_key='website'),
             'https://www.farforrent.com.ua'),
    1, 1
WHERE NOT EXISTS (SELECT 1 FROM company_profiles WHERE code = 'main');
