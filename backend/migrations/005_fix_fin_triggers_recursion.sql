-- ============================================================================
-- Migration 005: Fix recursive trigger error 1442 in fin_payments/fin_transactions
-- ============================================================================
-- Problem: fin_payments_after_insert had `UPDATE fin_payments SET tx_id` inside
--   its own AFTER INSERT trigger → MySQL error 1442.
-- Also: fin_transactions_after_insert mirrored back into fin_payments without
--   guarding against rows just produced by fin_payments_after_insert → potential
--   double-mirror.
--
-- Fix:
--   1) Drop recursive UPDATE inside fin_payments_after_insert (tx_id linkage
--      becomes optional; finance UI uses v_order_finance view).
--   2) In fin_transactions_after_insert, skip rows whose note starts with
--      "[from fp #" (those are produced by fin_payments → fin_transactions
--      mirror trigger).
-- ============================================================================

DROP TRIGGER IF EXISTS fin_payments_after_insert;

DELIMITER $$
CREATE TRIGGER fin_payments_after_insert
AFTER INSERT ON fin_payments
FOR EACH ROW
BEGIN
    IF NEW.payment_type != 'discount'
       AND NEW.tx_id IS NULL
       AND (NEW.status IS NULL OR NEW.status NOT IN ('voided','cancelled')) THEN

        INSERT INTO fin_transactions
          (tx_type, status, currency, amount, occurred_at, note,
           entity_type, entity_id, created_at, accepted_by_id, accepted_by_name)
        VALUES (
          CASE NEW.payment_type
            WHEN 'rent' THEN 'rent_payment'
            WHEN 'deposit' THEN 'deposit_payment'
            WHEN 'deposit_refund' THEN 'deposit_refund'
            WHEN 'damage' THEN 'damage_payment'
            WHEN 'additional' THEN 'additional_payment'
            WHEN 'loss' THEN 'damage_deduction'
            WHEN 'late' THEN 'late_payment'
            ELSE 'rent_payment'
          END,
          IFNULL(NEW.status, 'posted'),
          IFNULL(NEW.currency, 'UAH'),
          NEW.amount,
          IFNULL(NEW.occurred_at, NOW()),
          CONCAT('[from fp #', NEW.id, '] ', IFNULL(NEW.note, '')),
          CASE WHEN NEW.order_id IS NOT NULL THEN 'order'
               WHEN NEW.damage_case_id IS NOT NULL THEN 'damage_case'
               ELSE 'unknown' END,
          COALESCE(NEW.order_id, NEW.damage_case_id, 0),
          NOW(),
          NEW.accepted_by_id,
          NEW.accepted_by_name
        );
    END IF;
END$$
DELIMITER ;


DROP TRIGGER IF EXISTS fin_transactions_after_insert;

DELIMITER $$
CREATE TRIGGER fin_transactions_after_insert
AFTER INSERT ON fin_transactions
FOR EACH ROW
BEGIN
    -- Skip rows already produced by fin_payments_after_insert (avoid recursion)
    IF NEW.tx_type IN ('rent_payment','deposit_payment','deposit_refund',
                       'damage_payment','additional_payment','damage_deduction','late_payment')
       AND NEW.voided_at IS NULL
       AND NEW.entity_type IN ('order','damage_case')
       AND (NEW.note IS NULL OR NEW.note NOT LIKE '[from fp #%')
       AND NOT EXISTS (SELECT 1 FROM fin_payments WHERE tx_id = NEW.id) THEN

        INSERT INTO fin_payments
          (payment_type, method, amount, currency, occurred_at,
           order_id, damage_case_id, tx_id, status, note,
           accepted_by_id, accepted_by_name, created_at)
        VALUES (
          CASE NEW.tx_type
            WHEN 'rent_payment' THEN 'rent'
            WHEN 'deposit_payment' THEN 'deposit'
            WHEN 'deposit_refund' THEN 'deposit_refund'
            WHEN 'damage_payment' THEN 'damage'
            WHEN 'additional_payment' THEN 'additional'
            WHEN 'damage_deduction' THEN 'loss'
            WHEN 'late_payment' THEN 'late'
          END,
          'cash',
          NEW.amount,
          IFNULL(NEW.currency, 'UAH'),
          NEW.occurred_at,
          CASE WHEN NEW.entity_type = 'order' THEN NEW.entity_id END,
          CASE WHEN NEW.entity_type = 'damage_case' THEN NEW.entity_id END,
          NEW.id,
          IFNULL(NEW.status, 'posted'),
          CONCAT('[from tx #', NEW.id, '] ', IFNULL(NEW.note, '')),
          NEW.accepted_by_id, NEW.accepted_by_name, NOW()
        );
    END IF;
END$$
DELIMITER ;
