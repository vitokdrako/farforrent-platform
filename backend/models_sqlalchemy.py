"""
SQLAlchemy models for MySQL database
- OpenCart tables (read-only)
- Decor Manager tables (read-write)
"""
from sqlalchemy import Column, Integer, String, DECIMAL, DateTime, Text, ForeignKey, Index, func
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime

# ============================================================
# OPENCART MODELS (READ-ONLY)
# ============================================================

class OpenCartOrder(Base):
    """OpenCart orders table (read-only)"""
    __tablename__ = 'oc_order'
    __table_args__ = {'extend_existing': True}
    
    order_id = Column(Integer, primary_key=True)
    customer_id = Column(Integer)
    firstname = Column(String(32))
    lastname = Column(String(32))
    email = Column(String(96))
    telephone = Column(String(32))
    total = Column(DECIMAL(15, 4))
    order_status_id = Column(Integer)
    date_added = Column(DateTime)
    date_modified = Column(DateTime)

class OpenCartOrderProduct(Base):
    """OpenCart order products (read-only)"""
    __tablename__ = 'oc_order_product'
    __table_args__ = {'extend_existing': True}
    
    order_product_id = Column(Integer, primary_key=True)
    order_id = Column(Integer)
    product_id = Column(Integer)
    name = Column(String(255))
    model = Column(String(64))
    quantity = Column(Integer)
    price = Column(DECIMAL(15, 4))
    total = Column(DECIMAL(15, 4))

class OpenCartProduct(Base):
    """OpenCart products (read-only)"""
    __tablename__ = 'oc_product'
    __table_args__ = {'extend_existing': True}
    
    product_id = Column(Integer, primary_key=True)
    model = Column(String(64))
    sku = Column(String(64))
    ean = Column(String(14))  # Збиток (вартість втрати декору)
    price = Column(DECIMAL(15, 4))
    quantity = Column(Integer)
    image = Column(String(255))
    status = Column(Integer)
    date_added = Column(DateTime)
    date_modified = Column(DateTime)

class OpenCartProductDescription(Base):
    """OpenCart product descriptions (read-only)"""
    __tablename__ = 'oc_product_description'
    __table_args__ = {'extend_existing': True}
    
    product_id = Column(Integer, primary_key=True)
    language_id = Column(Integer, primary_key=True)
    name = Column(String(255))
    description = Column(Text)


class OpenCartProductImage(Base):
    """OpenCart product images (read-only)"""
    __tablename__ = 'oc_product_image'
    __table_args__ = {'extend_existing': True}
    
    product_image_id = Column(Integer, primary_key=True)
    product_id = Column(Integer)
    image = Column(String(255))
    sort_order = Column(Integer, default=0)

class OpenCartCategory(Base):
    """OpenCart categories (read-only)"""
    __tablename__ = 'oc_category'
    __table_args__ = {'extend_existing': True}
    
    category_id = Column(Integer, primary_key=True)
    image = Column(String(255))
    parent_id = Column(Integer, default=0)
    top = Column(Integer, default=0)
    column = Column(Integer, default=1)
    sort_order = Column(Integer, default=0)
    status = Column(Integer, default=1)
    date_added = Column(DateTime)
    date_modified = Column(DateTime)

class OpenCartCategoryDescription(Base):
    """OpenCart category descriptions (read-only)"""
    __tablename__ = 'oc_category_description'
    __table_args__ = {'extend_existing': True}
    
    category_id = Column(Integer, primary_key=True)
    language_id = Column(Integer, primary_key=True)
    name = Column(String(255))
    description = Column(Text)
    meta_title = Column(String(255))
    meta_description = Column(String(255))
    meta_keyword = Column(String(255))

class OpenCartProductToCategory(Base):
    """OpenCart product to category mapping (read-only)"""
    __tablename__ = 'oc_product_to_category'
    __table_args__ = {'extend_existing': True}
    
    product_id = Column(Integer, primary_key=True)
    category_id = Column(Integer, primary_key=True)

class OpenCartCustomer(Base):
    """OpenCart customers (read-only)"""
    __tablename__ = 'oc_customer'
    __table_args__ = {'extend_existing': True}
    
    customer_id = Column(Integer, primary_key=True)
    firstname = Column(String(32))
    lastname = Column(String(32))
    email = Column(String(96))
    telephone = Column(String(32))
    status = Column(Integer)


class OpenCartUser(Base):
    """OpenCart users/managers (read-only)"""
    __tablename__ = 'oc_user'
    __table_args__ = {'extend_existing': True}
    
    user_id = Column(Integer, primary_key=True)
    user_group_id = Column(Integer)
    username = Column(String(20))
    password = Column(String(40))
    salt = Column(String(9))
    firstname = Column(String(32))
    lastname = Column(String(32))
    email = Column(String(96))
    telephone = Column(String(32))
    telegram_id = Column(Text)
    image = Column(String(255))
    status = Column(Integer)
    date_added = Column(DateTime)

class OpenCartOrderSimpleFields(Base):
    """OpenCart order simple fields with rental dates (read-only)"""
    __tablename__ = 'oc_order_simple_fields'
    __table_args__ = {'extend_existing': True}
    
    order_id = Column(Integer, primary_key=True)
    rent_issue = Column(Text)  # Text поле, з якого тригер створює rent_issue_date
    rent_return = Column(Text)  # Text поле, з якого тригер створює rent_return_date
    rent_issue_date = Column(String(255))  # Дата видачі (computed by trigger)
    rent_return_date = Column(String(255))  # Дата повернення (computed by trigger)

# ============================================================
# DECOR MANAGER MODELS (READ-WRITE)
# ============================================================

class DecorDamage(Base):
    """Damage cases"""
    __tablename__ = 'decor_damages'
    
    id = Column(String(36), primary_key=True)
    order_id = Column(Integer, index=True)
    order_number = Column(String(50))
    customer_id = Column(Integer, index=True)
    customer_name = Column(String(255))
    customer_phone = Column(String(32))
    customer_email = Column(String(96))
    event_name = Column(String(255))
    return_date = Column(DateTime)
    
    case_status = Column(String(50), default='draft', index=True)
    severity = Column(String(20), default='medium')
    source = Column(String(20), default='other')
    from_reaudit_item_id = Column(String(50))
    finance_status = Column(String(50), default='none')
    fulfillment_status = Column(String(50), default='none')
    
    claimed_total = Column(DECIMAL(10, 2), default=0.00)
    paid_total = Column(DECIMAL(10, 2), default=0.00)
    withheld_total = Column(DECIMAL(10, 2), default=0.00)
    deposit_available = Column(DECIMAL(10, 2), default=0.00)
    
    notes = Column(Text)
    payment_policy = Column(String(50), default='withhold_first')
    
    created_by = Column(String(100), default='Manager')
    assigned_to = Column(String(100))
    manager_comment = Column(Text)
    
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship
    items = relationship("DecorDamageItem", back_populates="damage", cascade="all, delete-orphan")

class DecorDamageItem(Base):
    """Items in damage cases"""
    __tablename__ = 'decor_damage_items'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    damage_id = Column(String(36), ForeignKey('decor_damages.id'), nullable=False, index=True)
    product_id = Column(Integer, index=True)
    from_reaudit_item_id = Column(String(50))
    
    barcode = Column(String(100))
    name = Column(String(255))
    image = Column(String(255))
    category = Column(String(100))
    item_ref = Column(String(100))
    
    damage_type = Column(String(100))
    qty = Column(Integer, default=1)
    
    base_value = Column(DECIMAL(10, 2), default=0.00)
    estimate_value = Column(DECIMAL(10, 2), default=0.00)
    
    resolution = Column(String(50))
    comment = Column(Text)
    photos = Column(Text)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship
    damage = relationship("DecorDamage", back_populates="items")

class DecorTask(Base):
    """Tasks"""
    __tablename__ = 'decor_tasks'
    
    id = Column(String(36), primary_key=True)
    order_id = Column(Integer, index=True)
    order_number = Column(String(50))
    damage_id = Column(String(36), index=True)
    
    title = Column(String(255), nullable=False)
    description = Column(Text)
    task_type = Column(String(50), default='general')
    
    status = Column(String(50), default='todo', index=True)
    priority = Column(String(20), default='medium')
    
    assigned_to = Column(String(100))
    due_date = Column(DateTime, index=True)
    completed_at = Column(DateTime)
    
    created_by = Column(String(100), default='System')
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class DecorInvoice(Base):
    """Invoices"""
    __tablename__ = 'decor_invoices'
    
    id = Column(String(36), primary_key=True)
    order_id = Column(Integer, index=True)
    order_number = Column(String(50))
    customer_id = Column(Integer, index=True)
    customer_name = Column(String(255))
    customer_phone = Column(String(32))
    customer_email = Column(String(96))
    
    amount = Column(DECIMAL(10, 2), nullable=False)
    status = Column(String(50), default='draft', index=True)
    
    invoice_items = Column(Text)
    
    due_at = Column(DateTime)
    sent_at = Column(DateTime)
    paid_at = Column(DateTime)
    
    pdf_url = Column(String(255))
    
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class DecorPayment(Base):
    """Payments"""
    __tablename__ = 'decor_payments'
    
    id = Column(String(36), primary_key=True)
    order_id = Column(Integer, index=True)
    invoice_id = Column(String(36), index=True)
    
    amount = Column(DECIMAL(10, 2), nullable=False)
    payment_type = Column(String(50), index=True)
    payment_method = Column(String(50))
    
    status = Column(String(50), default='pending')
    
    reference = Column(String(100))
    notes = Column(Text)
    
    paid_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

class DecorDeposit(Base):
    """Deposits"""
    __tablename__ = 'decor_deposits'
    
    id = Column(String(36), primary_key=True)
    order_id = Column(Integer, index=True)
    customer_id = Column(Integer, index=True)
    
    amount = Column(DECIMAL(10, 2), nullable=False)
    status = Column(String(50), default='held', index=True)
    
    held_amount = Column(DECIMAL(10, 2), default=0.00)
    released_amount = Column(DECIMAL(10, 2), default=0.00)
    withheld_amount = Column(DECIMAL(10, 2), default=0.00)
    
    held_at = Column(DateTime)
    released_at = Column(DateTime)
    
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

class DecorOrderLifecycle(Base):
    """Order lifecycle tracking"""
    __tablename__ = 'decor_order_lifecycle'
    
    order_id = Column(Integer, primary_key=True)
    order_number = Column(String(50), index=True)
    
    issue_date = Column(DateTime, index=True)
    return_date = Column(DateTime, index=True)
    
    issued_at = Column(DateTime)
    returned_at = Column(DateTime)
    
    lifecycle_status = Column(String(50), default='draft', index=True)
    
    manager_comment = Column(Text)
    warehouse_notes = Column(Text)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class DecorInventoryExtended(Base):
    """Extended inventory information"""
    __tablename__ = 'decor_inventory_extended'
    
    product_id = Column(Integer, primary_key=True)
    
    damage_category = Column(String(100))
    replacement_price = Column(DECIMAL(10, 2))
    
    notes = Column(Text)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
"""
Additional models for Issue Cards, Return Cards, and Photos
"""
from sqlalchemy import Column, Integer, String, Text, DECIMAL, DateTime, Date, Boolean, ForeignKey, JSON
from sqlalchemy.sql import func
from database import Base


class DecorProductCatalog(Base):
    """Extended catalog information for products - location, cleaning state, audit"""
    __tablename__ = 'decor_product_catalog'
    
    product_id = Column(Integer, primary_key=True)
    
    # Location
    location_zone = Column(String(10))  # A, B, C
    location_aisle = Column(String(10))  # A1, B2
    location_shelf = Column(String(20))  # S1, S2
    location_bin = Column(String(20))  # B01, B02
    
    # Cleaning state
    cleaning_status = Column(String(20), default='clean')  # clean, wash, dry, repair
    cleaning_last_updated = Column(DateTime, default=datetime.utcnow)
    
    # Product state
    product_state = Column(String(20), default='ok')  # ok, fragile, damaged
    
    # Audit information
    last_audit_date = Column(Date)
    last_audit_by = Column(String(100))
    next_audit_date = Column(Date)
    
    created_at = Column(DateTime, default=datetime.utcnow)


# ============================================================
# EXTENDED CATALOG MODELS (NEW)
# ============================================================

class DecorProductExtended(Base):
    """Розширені атрибути товарів: колір, матеріал, розмір, теги"""
    __tablename__ = 'decor_product_extended'
    __table_args__ = {'extend_existing': True}
    
    product_id = Column(Integer, primary_key=True)
    subcategory = Column(String(100))
    color = Column(String(100))
    material = Column(String(200))
    size = Column(String(100))
    tags = Column(JSON)  # ['лофт', 'бежевий', 'меблі']
    care_notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DecorInventoryItem(Base):
    """Унікальні інвентарні одиниці з індивідуальними кодами"""
    __tablename__ = 'decor_inventory_items'
    __table_args__ = {'extend_existing': True}
    
    id = Column(String(50), primary_key=True)
    product_id = Column(Integer, nullable=False, index=True)
    inventory_code = Column(String(100), unique=True, nullable=False)
    status = Column(String(20), default='available', index=True)
    # available, reserved, on_rent, washing, repair, lost
    location = Column(String(255))
    last_order_id = Column(Integer)
    last_movement_at = Column(DateTime)
    notes = Column(Text)
    # Audit fields
    last_audit_date = Column(Date)
    last_audit_by = Column(String(100))
    next_audit_date = Column(Date)
    audit_status = Column(String(20), default='ok')  # ok, minor, critical, lost
    audit_notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DecorProductHistory(Base):
    """Історія всіх операцій з товарами"""
    __tablename__ = 'decor_product_history'
    __table_args__ = {'extend_existing': True}
    
    id = Column(String(50), primary_key=True)
    product_id = Column(Integer, nullable=False, index=True)
    inventory_item_id = Column(String(50))
    event_type = Column(String(50), nullable=False, index=True)
    # created, edited, moved, rent_out, returned, damage_opened, damage_closed, cleaned, reserved
    actor = Column(String(100))
    order_id = Column(Integer)
    notes = Column(Text)
    photo_url = Column(String(500))  # URL для фото пошкоджень
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class DecorProductLifecycle(Base):
    """Lifecycle метрики товарів - оренди, пошкодження, прибуток"""
    __tablename__ = 'decor_product_lifecycle'
    __table_args__ = {'extend_existing': True}
    
    product_id = Column(Integer, primary_key=True)
    rentals_count = Column(Integer, default=0)
    damages_count = Column(Integer, default=0)
    total_profit = Column(DECIMAL(15, 4), default=0)
    last_rental_order_id = Column(Integer)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ============================================================
# DECOR ORDERS (OUR TABLES - READ/WRITE)
# ============================================================

class DecorOrder(Base):
    """Our orders table - imported from OpenCart"""
    __tablename__ = 'decor_orders'
    __table_args__ = {'extend_existing': True}
    
    id = Column(Integer, primary_key=True)
    opencart_order_id = Column(Integer, nullable=False, index=True)
    order_number = Column(String(50))
    client_name = Column(String(255))
    client_phone = Column(String(100))
    client_email = Column(String(255))
    telegram_chat_id = Column(String(255))
    status = Column(String(50), default='processing', index=True)
    rent_date = Column(DateTime, index=True)
    rent_return_date = Column(DateTime)
    rental_days = Column(Integer, default=1)
    total_rental = Column(DECIMAL(15, 4), default=0)
    total_deposit = Column(DECIMAL(15, 4), default=0)
    discount = Column(DECIMAL(10, 2), default=0)
    notes = Column(Text)
    manager_notes = Column(Text)
    client_confirmed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship
    items = relationship("DecorOrderItem", back_populates="order", cascade="all, delete-orphan")


class DecorOrderItem(Base):
    """Order items in our system"""
    __tablename__ = 'decor_order_items'
    __table_args__ = {'extend_existing': True}
    
    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey('decor_orders.id', ondelete='CASCADE'), nullable=False, index=True)
    product_id = Column(Integer, nullable=False, index=True)
    sku = Column(String(100))
    name = Column(String(255))
    quantity = Column(Integer, default=1)
    price_per_day = Column(DECIMAL(15, 4), default=0)
    damage_cost = Column(DECIMAL(15, 4), default=0)
    total_rental = Column(DECIMAL(15, 4), default=0)
    deposit = Column(DECIMAL(15, 4), default=0)
    image = Column(String(500))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship
    order = relationship("DecorOrder", back_populates="items")

    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ProductReservation(Base):
    """Резервації товарів (заморожування на період оренди)"""
    __tablename__ = 'product_reservations'
    __table_args__ = {'extend_existing': True}
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Товар
    product_id = Column(Integer, nullable=False, index=True)
    sku = Column(String(100), index=True)
    product_name = Column(String(255))
    
    # Кількість зарезервована
    quantity_reserved = Column(Integer, default=1)
    
    # Замовлення
    order_id = Column(Integer, nullable=False, index=True)
    order_number = Column(String(50))
    
    # Клієнт
    client_name = Column(String(255))
    client_phone = Column(String(100))
    
    # Період резервації (дати оренди)
    reserved_from = Column(DateTime, nullable=False, index=True)
    reserved_to = Column(DateTime, nullable=False, index=True)
    
    # Статус резервації
    status = Column(String(20), default='active', index=True)  # active, issued, returned, cancelled
    
    # Додаткова інформація
    issue_card_id = Column(String(50))
    return_card_id = Column(String(50))
    notes = Column(Text)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    issued_at = Column(DateTime)
    returned_at = Column(DateTime)


class DecorIssueCard(Base):
    """Картка видачі замовлення"""
    __tablename__ = 'decor_issue_cards'
    
    id = Column(String(50), primary_key=True)
    order_id = Column(Integer, nullable=False, index=True)
    order_number = Column(String(50), nullable=False)
    
    # Статус картки
    status = Column(String(20), default='preparation')  # preparation, ready, issued, archived
    
    # Відповідальні особи
    prepared_by = Column(String(100))
    issued_by = Column(String(100))
    
    # Позиції (JSON)
    items = Column(JSON)  # [{sku, name, quantity, status: prepared/ready/issued, photos: []}]
    
    # Коментарі
    preparation_notes = Column(Text)
    issue_notes = Column(Text)
    
    # Дати
    prepared_at = Column(DateTime)
    issued_at = Column(DateTime)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class DecorReturnCard(Base):
    """Картка повернення замовлення"""
    __tablename__ = 'decor_return_cards'
    
    id = Column(String(50), primary_key=True)
    order_id = Column(Integer, nullable=False, index=True)
    order_number = Column(String(50), nullable=False)
    issue_card_id = Column(String(50))  # Зв'язок з карткою видачі
    
    # Статус картки
    status = Column(String(20), default='pending')  # pending, active, checking, resolved, closed
    
    # Відповідальні особи
    received_by = Column(String(100))
    checked_by = Column(String(100))
    
    # Позиції (JSON)
    items_expected = Column(JSON)  # [{sku, name, quantity, photos_before: []}]
    items_returned = Column(JSON)  # [{sku, name, quantity_returned, condition, photos_after: [], notes}]
    
    # Статистика
    total_items_expected = Column(Integer, default=0)
    total_items_returned = Column(Integer, default=0)
    items_ok = Column(Integer, default=0)
    items_dirty = Column(Integer, default=0)
    items_damaged = Column(Integer, default=0)
    items_missing = Column(Integer, default=0)
    
    # Додаткові витрати
    cleaning_fee = Column(DECIMAL(10, 2), default=0.00)
    late_fee = Column(DECIMAL(10, 2), default=0.00)
    
    # Коментарі
    return_notes = Column(Text)
    
    # Дати
    returned_at = Column(DateTime)
    checked_at = Column(DateTime)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class DecorPhoto(Base):
    """Фото для замовлень, карток, товарів"""
    __tablename__ = 'decor_photos'
    
    id = Column(String(50), primary_key=True)
    
    # Прив'язка до об'єкту
    entity_type = Column(String(50), nullable=False)  # order, issue_card, return_card, damage_case, product
    entity_id = Column(String(50), nullable=False, index=True)
    
    # SKU товару (якщо фото товару)
    sku = Column(String(100))
    
    # Тип фото
    photo_type = Column(String(50))  # before, after, damage, general
    
    # Файл
    filename = Column(String(255), nullable=False)
    filepath = Column(String(500), nullable=False)
    file_size = Column(Integer)  # в байтах
    mime_type = Column(String(50))
    
    # Мета-дані
    caption = Column(Text)
    uploaded_by = Column(String(100))
    
    # Дати
    uploaded_at = Column(DateTime, server_default=func.now())
    created_at = Column(DateTime, server_default=func.now())


class DecorQRCode(Base):
    """QR коди для товарів"""
    __tablename__ = 'decor_qr_codes'
    
    id = Column(String(50), primary_key=True)
    
    # SKU товару
    sku = Column(String(100), nullable=False, unique=True, index=True)
    product_id = Column(Integer)
    
    # QR код
    qr_code_data = Column(Text, nullable=False)  # Дані що кодуються в QR
    qr_image_path = Column(String(500))  # Шлях до зображення QR
    
    # Мета-дані
    generated_by = Column(String(100))
    times_scanned = Column(Integer, default=0)
    last_scanned_at = Column(DateTime)
    
    # Дати
    generated_at = Column(DateTime, server_default=func.now())



# ============================================================
# FINANCE TRANSACTIONS MODEL
# ============================================================

class FinanceTransaction(Base):
    """Фінансові транзакції - облік всіх грошових рухів"""
    __tablename__ = 'finance_transactions'
    
    id = Column(String(50), primary_key=True)  # L-xxxx
    
    # Зв'язок з замовленням (опціонально)
    order_id = Column(Integer, index=True)
    order_number = Column(String(50))
    
    # Тип транзакції
    type = Column(String(50), nullable=False, index=True)  
    # Типи: 'prepayment', 'rent_accrual', 'deposit_hold', 'deposit_return', 
    #       'balance_due', 'damage_charge', 'cleaning_fee', 'late_fee',
    #       'expense', 'salary', 'regular_payment', 'refund'
    
    # Метод оплати
    payment_method = Column(String(50))  
    # cash, fop_transfer, wayforpay, card, bank_transfer
    
    # Опис
    title = Column(String(255), nullable=False)
    description = Column(Text)
    
    # Суми
    debit = Column(DECIMAL(10, 2), default=0.00)   # Нарахування (борг клієнта)
    credit = Column(DECIMAL(10, 2), default=0.00)  # Оплата (надходження)
    
    # Валюта та курс
    currency = Column(String(3), default='UAH')  # UAH, USD, EUR
    exchange_rate = Column(DECIMAL(10, 4), default=1.0000)
    amount_uah = Column(DECIMAL(10, 2))  # Сума в гривнях
    
    # Статус
    status = Column(String(50), default='pending', index=True)
    # pending, paid, held, released, cancelled, accrued, unpaid
    
    # Контрагент
    counterparty = Column(String(255))  # Ім'я клієнта або постачальника
    
    # Теги для фільтрації
    tag = Column(String(50), index=True)  # prepay, rent, deposit, expense, salary, etc
    
    # Категорія витрат (для внутрішніх витрат)
    expense_category = Column(String(100))  # office, salary, marketing, utilities, etc
    
    # Дата транзакції
    transaction_date = Column(DateTime, default=datetime.now, index=True)
    
    # Дати
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


# ============================================================
# REGULAR PAYMENTS (Нагадування регулярних платежів)
# ============================================================

class RegularPayment(Base):
    """Регулярні платежі компанії (оренда офісу, комунальні, тощо)"""
    __tablename__ = 'regular_payments'
    
    id = Column(String(50), primary_key=True)
    
    # Опис
    title = Column(String(255), nullable=False)
    description = Column(Text)
    category = Column(String(100))  # rent, utilities, subscription, salary, etc
    
    # Сума
    amount = Column(DECIMAL(10, 2), nullable=False)
    currency = Column(String(3), default='UAH')
    
    # Періодичність
    frequency = Column(String(50), nullable=False)  # monthly, quarterly, yearly, weekly
    day_of_period = Column(Integer)  # День місяця/тижня для оплати
    
    # Контрагент
    payee = Column(String(255))  # Кому платимо
    payment_method = Column(String(50))  # Як платимо
    
    # Наступна дата платежу
    next_due_date = Column(DateTime, index=True)
    
    # Статус
    is_active = Column(Integer, default=1)
    
    # Дати
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
