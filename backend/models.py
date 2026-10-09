from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional
from datetime import datetime
import uuid

# Inventory Models
class InventoryItem(BaseModel):
    id: str
    name: str
    article: str
    category: str
    price_per_day: float
    replacement_price: Optional[float] = None  # Full replacement cost
    deposit: float  # Deposit amount (typically 50% of replacement)
    deposit_tier: str = "standard"  # standard, high, special
    quantity_available: int
    quantity_total: int
    is_serial: bool = False  # Track individual units with serial numbers
    images: List[str] = []
    description: Optional[str] = None
    notes: Optional[str] = None

class InventoryUnit(BaseModel):
    """Individual tracked unit (for serial inventory)"""
    id: str
    inventory_id: str  # Reference to InventoryItem
    serial_number: str
    barcode: str
    status: str  # available, reserved, picked, on_rent, return_qc, repair, lost, written_off
    current_order_id: Optional[str] = None
    last_movement: Optional[datetime] = None
    condition_notes: Optional[str] = None

class Movement(BaseModel):
    """Audit trail for inventory movements"""
    id: str
    unit_id: Optional[str] = None  # For serial items
    inventory_id: str
    order_id: Optional[str] = None
    type: str  # reserve, unreserve, pick, issue, return, repair, write_off
    quantity: int = 1
    from_status: str
    to_status: str
    scanned_by: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    notes: Optional[str] = None

class InventoryItemCreate(BaseModel):
    name: str
    article: str
    category: str
    description: Optional[str] = None
    price_per_day: float
    deposit: float
    quantity_total: int
    image_url: Optional[str] = None

class InventoryItemUpdate(BaseModel):
    name: Optional[str] = None
    article: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    price_per_day: Optional[float] = None
    deposit: Optional[float] = None
    quantity_available: Optional[int] = None
    quantity_total: Optional[int] = None
    status: Optional[str] = None

# Client Models
class Client(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    phone: str
    email: Optional[EmailStr] = None
    status: str = "new"  # new, regular, vip
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    total_orders: int = 0
    total_spent: float = 0.0

class ClientCreate(BaseModel):
    name: str
    phone: str
    email: Optional[EmailStr] = None
    status: str = "new"
    notes: Optional[str] = None

# Order Models
class OrderItem(BaseModel):
    inventory_id: str
    name: str
    article: str
    quantity: int
    price_per_day: float
    deposit: float
    total_rental: float
    total_deposit: float

class Order(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    order_number: str
    
    # Order lifecycle status
    status: str = "new"  # new, reserved, picked, issued, on_rent, partially_returned, returned, awaiting_payment, closed, canceled
    
    # Financial status (separate tracking)
    finance_status: str = "quote"  # quote, awaiting_prepayment, paid_rent, awaiting_settlement, invoiced, partially_paid, withheld, refunded, closed
    
    # Client info
    client_id: str
    client_name: str
    client_phone: str
    client_email: Optional[str] = None
    
    # Dates
    issue_date: str
    return_date: str
    rental_days: int
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Items
    items: List[OrderItem]
    
    # Financial breakdown
    rent_subtotal: float = 0.0  # Base rental before fees
    discount: float = 0.0
    discount_percent: float = 0.0
    total_rental: float = 0.0  # After discount
    
    # Fees
    min_order_fee: float = 0.0  # To reach 2000 UAH minimum
    rush_fee: float = 0.0  # +30% for orders within 24h
    out_of_hours_fee: float = 0.0  # +1500 UAH for weekend/after hours
    
    # Services
    delivery_fee: float = 0.0
    setup_fee: float = 0.0
    services_total: float = 0.0
    
    # Penalties
    late_fees: float = 0.0
    cleaning_fees: float = 0.0
    repair_fees: float = 0.0
    penalties_total: float = 0.0
    
    # Deposit
    total_deposit: float = 0.0
    deposit_held: float = 0.0
    deposit_withheld: float = 0.0
    deposit_released: float = 0.0
    
    # Payments
    prepaid: float = 0.0
    paid_total: float = 0.0
    to_pay: float = 0.0
    
    # Comments
    client_comment: Optional[str] = None
    manager_comment: Optional[str] = None
    
    # Tracking
    created_by: str = "Manager"
    assigned_to: Optional[str] = None
    
    # Flags
    is_partial_issue: bool = False
    is_partial_return: bool = False
    is_rush_order: bool = False  # Within 24h
    requires_out_of_hours: bool = False  # Weekend or after 17:00
    
    # Timestamps for lifecycle
    reserved_at: Optional[datetime] = None
    picked_at: Optional[datetime] = None
    issued_at: Optional[datetime] = None
    returned_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None

class OrderCreate(BaseModel):
    client_id: Optional[str] = None
    client_name: str
    client_phone: str
    client_email: Optional[str] = None
    issue_date: str
    return_date: str
    items: List[OrderItem]
    discount_percent: float = 0.0
    client_comment: Optional[str] = None
    manager_comment: Optional[str] = None

class OrderUpdate(BaseModel):
    status: Optional[str] = None
    prepaid: Optional[float] = None
    manager_comment: Optional[str] = None
    finance_status: Optional[str] = None

# Finance Models
class Payment(BaseModel):
    id: str
    order_id: str
    order_number: str
    customer_id: Optional[str] = None
    type: str  # rent, service, deposit_hold, deposit_withhold, deposit_release, late_fee, cleaning, repair, invoice_payment, refund
    method: str  # cash, card, bank_transfer, internal, invoice
    amount: float
    status: str = "paid"  # pending, paid, failed, refunded
    note: Optional[str] = None
    created_by: str = "Manager"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    meta: Optional[dict] = None

class Deposit(BaseModel):
    id: str
    order_id: str
    order_number: str
    hold_amount: float  # Total deposit held
    withheld_amount: float = 0.0  # Amount withheld for damages
    released_amount: float = 0.0  # Amount released back to customer
    available_amount: float = 0.0  # Available for withholding
    hold_status: str = "on_hold"  # on_hold, withheld, released, converted
    auto_release_at: Optional[datetime] = None
    withhold_reason: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class Invoice(BaseModel):
    id: str
    order_id: str
    order_number: str
    customer_id: str
    customer_name: str
    customer_phone: str
    customer_email: Optional[str] = None
    amount: float
    status: str = "draft"  # draft, sent, paid, void, overdue
    due_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    paid_at: Optional[datetime] = None
    pdf_url: Optional[str] = None
    items: List[dict] = []  # {kind, title, qty, price, total}
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class FinanceSummary(BaseModel):
    # Revenue
    total_revenue: float = 0.0
    rent_revenue: float = 0.0
    services_revenue: float = 0.0
    penalties_revenue: float = 0.0
    
    # Deposits
    deposits_held: float = 0.0
    deposits_released: float = 0.0
    deposits_withheld: float = 0.0
    deposits_on_hold: float = 0.0
    
    # Additional charges
    late_fees: float = 0.0
    cleaning_fees: float = 0.0
    repair_fees: float = 0.0
    min_order_fees: float = 0.0
    rush_fees: float = 0.0
    out_of_hours_fees: float = 0.0
    
    # Invoices
    unpaid_invoices_count: int = 0
    unpaid_invoices_amount: float = 0.0
    overdue_invoices_count: int = 0
    overdue_invoices_amount: float = 0.0

# Damage Management Models
class DamageItem(BaseModel):
    id: int
    barcode: str
    name: str
    image: str = ""
    category: str  # Меблі, Столики, Вази, etc.
    item_ref: Optional[str] = None  # Reference to order item or inventory
    type: str  # dirty, chipped, broken, lost, wet, burn, scratch
    qty: int
    baseValue: float
    estimateValue: float
    resolution: Optional[str] = None  # cleaning, repair, replacement, write_off, penalty
    comment: str = ""
    photos: List[str] = []

class DamageCase(BaseModel):
    id: str
    order_number: str
    order_id: Optional[str] = None
    customer_id: Optional[str] = None
    client: dict
    
    # Main status workflow
    case_status: str = "draft"  # draft, triage, estimating, estimated, awaiting_approval, approved, in_progress, qa_check, resolved, closed, canceled
    
    # Financial sub-status
    finance_status: str = "none"  # none, awaiting_withhold, withheld, invoiced, partially_paid, paid, refunded, writeoff_pending, written_off
    
    # Fulfillment sub-status
    fulfillment_status: str = "none"  # none, cleaning_queue, cleaning, cleaned, repair_queue, repair, repaired, replacement_ordered, replacement_received, write_off
    
    items: List[DamageItem]
    
    # Financial tracking
    claimed_total: float = 0.0  # Total amount claimed
    paid_total: float = 0.0  # Amount already paid
    withheld_total: float = 0.0  # Amount withheld from deposit
    deposit_available: float = 0.0  # Available deposit amount
    
    notes: str = ""
    internal_notes: str = ""
    
    # Assignment and tracking
    created_by: str = "System"
    assigned_to: Optional[str] = None
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    approved_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    
    # SLA tracking
    awaiting_approval_since: Optional[datetime] = None
    in_repair_since: Optional[datetime] = None
    
    # Policy
    payment_policy: str = "withhold_first"  # withhold_first, invoice_first
    manager_comment: Optional[str] = None


# Settings Models for Universal Tool
class DatabaseConfig(BaseModel):
    """Database connection configuration"""
    host: str
    port: int = 3306
    user: str
    password: str
    database: str
    prefix: str = "oc_"

class FieldMapping(BaseModel):
    """Field mapping configuration for different OpenCart installations"""
    orders_table: str = "oc_order"
    order_products_table: str = "oc_order_product"
    order_dates_table: str = "oc_order_simple_fields"
    products_table: str = "oc_product"
    product_descriptions_table: str = "oc_product_description"
    customers_table: str = "oc_customer"
    status_field: str = "order_status_id"
    
    # Статуси життєвого циклу
    pending_statuses: List[int] = [2]        # В обробці (нові)
    confirmed_statuses: List[int] = [19]     # Опрацьовано (підтверджені)
    on_rent_statuses: List[int] = [24]       # Видано (в оренді)
    returned_statuses: List[int] = [25]      # Повернуто (перевірка)
    completed_statuses: List[int] = [13]     # Завершено (архів)
    
    # Поля дат
    issue_date_field: str = "rent_issue_date"
    return_date_field: str = "rent_return_date"
    
    # Поля товарів
    product_article_field: str = "model"
    product_ean_field: str = "ean"

class CompanySettings(BaseModel):
    """Company information for invoices and documents"""
    name: str = "Rental Hub"
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    currency: str = "UAH"
    tax_rate: float = 0.0

class AppConfig(BaseModel):
    """Complete application configuration"""
    version: str = "1.0"
    created_at: str
    updated_at: str
    database: DatabaseConfig
    mapping: FieldMapping
    company: CompanySettings

class AppConfigUpdate(BaseModel):
    """Configuration update (all fields optional)"""
    database: Optional[DatabaseConfig] = None
    mapping: Optional[FieldMapping] = None
    company: Optional[CompanySettings] = None

class ConnectionTestRequest(BaseModel):
    """Request to test database connection"""
    host: str
    port: int = 3306
    user: str
    password: str
    database: str

class ConnectionTestResponse(BaseModel):
    """Response from connection test"""
    success: bool
    message: str
    version: Optional[str] = None
    error: Optional[str] = None

class DetectTablesRequest(BaseModel):
    """Request to detect OpenCart tables"""
    host: str
    port: int = 3306
    user: str
    password: str
    database: str
    prefix: str = "oc_"

class DetectTablesResponse(BaseModel):
    """Response from table detection"""
    success: bool
    detected: Optional[dict] = None
    message: Optional[str] = None
    error: Optional[str] = None
