from fastapi import FastAPI, APIRouter, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, Response
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
import os
import logging
from pathlib import Path

# Load environment variables FIRST
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Import route modules AFTER loading env
from routes import inventory, clients, orders, tasks, damages, finance, test_orders, settings, pdf, users, issue_cards, return_cards, photos, qr_codes, email, catalog, archive, warehouse, extended_catalog, audit, products, auth, image_proxy, price_sync, damage_cases, admin, product_damage_history, product_reservations, inventory_adjustments, sync, product_cleaning, migrations, product_images, product_images_multi, event_tool_integration, user_tracking, laundry, documents, analytics, product_sets, expense_management, export, template_admin, order_modifications, order_internal_notes, order_sync, partial_returns, uploads, payer_profiles, dashboard_overview, calendar_events, return_versions, event_tool, master_agreements, order_annexes, document_policy, document_render, document_signatures, document_pdf, document_manual_fields, document_email, team_chat, cabinet, picking_list, admin_orders, bulk_products, admin_finance

# Create the main app
app = FastAPI(title="Rental Hub API")

# Налаштувати статичні файли для завантажених зображень
UPLOAD_ROOT = ROOT_DIR / "uploads"
UPLOAD_ROOT.mkdir(exist_ok=True)
(UPLOAD_ROOT / "products").mkdir(exist_ok=True)
(UPLOAD_ROOT / "photos").mkdir(exist_ok=True)
(UPLOAD_ROOT / "qr").mkdir(exist_ok=True)
(UPLOAD_ROOT / "damage_photos").mkdir(exist_ok=True)
(UPLOAD_ROOT / "chat").mkdir(exist_ok=True)
app.mount("/api/uploads", StaticFiles(directory=str(UPLOAD_ROOT)), name="api_uploads")
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_ROOT)), name="uploads")

# Налаштувати статичні файли для мігрованих зображень товарів
STATIC_ROOT = ROOT_DIR / "static"
STATIC_ROOT.mkdir(exist_ok=True)
(STATIC_ROOT / "images").mkdir(exist_ok=True)
(STATIC_ROOT / "images" / "products").mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_ROOT)), name="static")

# Add CORS middleware (MUST be before routers)
cors_origins = os.environ.get('CORS_ORIGINS', '')

# Default allowed origins for FarForRent
default_origins = [
    "https://rentalhub.farforrent.com.ua",
    "https://www.rentalhub.farforrent.com.ua",
    "https://events.farforrent.com.ua",
    "https://backrentalhub.farforrent.com.ua",
    "http://173.242.49.48",          # VPS Event Tool (клієнти)
    "http://173.242.49.48:8080",     # VPS RentalHub адмінка
    "http://localhost:3000",
    "http://localhost:3001",
    "https://item-photos.preview.emergentagent.com",  # Emergent preview
]

if cors_origins == '*':
    cors_origins_list = ["*"]
    allow_cred = False  # Cannot use credentials with wildcard origin
elif cors_origins:
    cors_origins_list = [o.strip() for o in cors_origins.split(',')]
    allow_cred = True
else:
    # Use default origins if not specified
    cors_origins_list = default_origins
    allow_cred = True

# Log CORS config for debugging
print(f"[CORS] Origins: {cors_origins_list}")
print(f"[CORS] Credentials: {allow_cred}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins_list,
    allow_credentials=allow_cred,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=600,
)

# Include routers
app.include_router(inventory.router)
app.include_router(clients.router)
app.include_router(orders.router)
app.include_router(orders.decor_router)  # ✅ Додано для сумісності з /api/decor-orders
app.include_router(test_orders.router)
app.include_router(auth.router)
app.include_router(tasks.router)
app.include_router(damages.router)
app.include_router(finance.router)
app.include_router(finance.manager_router)  # /api/manager/finance/* для ManagerDashboard
app.include_router(settings.router)
app.include_router(pdf.router)
app.include_router(users.router)
app.include_router(issue_cards.router)
app.include_router(return_cards.router)
app.include_router(photos.router)
app.include_router(qr_codes.router)
app.include_router(email.router)
app.include_router(catalog.router)
app.include_router(archive.router)
app.include_router(warehouse.router)
app.include_router(extended_catalog.router)
app.include_router(audit.router)
app.include_router(products.router)
app.include_router(image_proxy.router)
app.include_router(price_sync.router)
app.include_router(damage_cases.router)
app.include_router(admin.router)
app.include_router(product_damage_history.router)
app.include_router(product_reservations.router)
app.include_router(inventory_adjustments.router)
app.include_router(sync.router)
app.include_router(product_cleaning.router)
app.include_router(migrations.router)
app.include_router(product_images.router)
app.include_router(product_images_multi.router)
app.include_router(product_images_multi.delete_router)
app.include_router(event_tool_integration.router)
app.include_router(event_tool.router, prefix="/api")  # Full Event Tool API for decorators
app.include_router(user_tracking.router)
app.include_router(laundry.router)
# Phase 3.2: Manual Fields & Email - MUST be before documents.router to avoid route conflicts
app.include_router(document_manual_fields.router)
app.include_router(document_email.router)
app.include_router(documents.router)
app.include_router(analytics.router)
app.include_router(product_sets.router)
app.include_router(expense_management.router)
app.include_router(export.router)
app.include_router(template_admin.router)
app.include_router(order_modifications.router)
app.include_router(order_internal_notes.router)
app.include_router(order_sync.router)
app.include_router(partial_returns.router)
app.include_router(return_versions.router)  # Нова система версій повернення
app.include_router(uploads.router)
app.include_router(payer_profiles.router)
app.include_router(dashboard_overview.router)
app.include_router(picking_list.router)
app.include_router(admin_orders.router)
app.include_router(bulk_products.router)
app.include_router(admin_finance.router)
app.include_router(calendar_events.router)
# Phase 3: Documents Engine
app.include_router(master_agreements.router)
app.include_router(order_annexes.router)
app.include_router(document_policy.router)
# Phase 3.1: Document Rendering & Signatures
app.include_router(document_render.router)
app.include_router(document_signatures.router)
app.include_router(document_pdf.router)
app.include_router(team_chat.router)
app.include_router(cabinet.router)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Health check
@app.get("/api/")
async def root():
    return {"message": "Rental Hub API is running", "status": "ok"}

@app.get("/api/health")
async def health():
    return {"status": "healthy", "database": "mysql"}


# OPTIONS preflight requests are now handled automatically by CORSMiddleware
