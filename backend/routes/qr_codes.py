from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
import uuid
import qrcode
import os
from datetime import datetime

from database import get_db
from models_sqlalchemy import DecorQRCode, OpenCartProduct

router = APIRouter(prefix="/api/qr-codes", tags=["qr-codes"])

# Використовуємо папку uploads в межах проекту
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QR_DIR = os.path.join(BASE_DIR, "uploads", "qr")
os.makedirs(QR_DIR, exist_ok=True)

@router.get("/generate/{sku}")
async def generate_qr_code(sku: str, db: Session = Depends(get_db)):
    existing = db.query(DecorQRCode).filter(DecorQRCode.sku == sku).first()
    
    if existing:
        return {
            "id": existing.id,
            "sku": existing.sku,
            "qr_code_url": f"/api/qr-codes/image/{existing.id}",
            "qr_data": existing.qr_code_data
        }
    
    product = db.query(OpenCartProduct).filter(OpenCartProduct.model == sku).first()
    
    qr_id = f"QR-{str(uuid.uuid4())[:8].upper()}"
    qr_data = f"SKU:{sku}"
    
    qr = qrcode.QRCode(version=1, box_size=10, border=2)
    qr.add_data(qr_data)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    qr_image_path = os.path.join(QR_DIR, f"{qr_id}.png")
    img.save(qr_image_path)
    
    new_qr = DecorQRCode(
        id=qr_id,
        sku=sku,
        product_id=product.product_id if product else None,
        qr_code_data=qr_data,
        qr_image_path=qr_image_path,
        generated_at=datetime.now()
    )
    
    db.add(new_qr)
    db.commit()
    
    return {
        "id": qr_id,
        "sku": sku,
        "qr_code_url": f"/api/qr-codes/image/{qr_id}",
        "qr_data": qr_data
    }

@router.post("/scan")
async def scan_qr_code(qr_data: dict, db: Session = Depends(get_db)):
    data = qr_data.get('data', '')
    
    if data.startswith('SKU:'):
        sku = data.replace('SKU:', '')
        
        qr_record = db.query(DecorQRCode).filter(DecorQRCode.sku == sku).first()
        if qr_record:
            qr_record.times_scanned += 1
            qr_record.last_scanned_at = datetime.now()
            db.commit()
        
        product = db.query(OpenCartProduct).filter(OpenCartProduct.model == sku).first()
        
        return {
            "sku": sku,
            "product_id": product.product_id if product else None,
            "name": product.oc_product_description[0].name if product and product.oc_product_description else ""
        }
    
    raise HTTPException(status_code=400, detail="Invalid QR code data")

@router.get("/image/{qr_id}")
async def get_qr_image(qr_id: str, db: Session = Depends(get_db)):
    from fastapi.responses import FileResponse
    
    qr = db.query(DecorQRCode).filter(DecorQRCode.id == qr_id).first()
    
    if not qr or not os.path.exists(qr.qr_image_path):
        raise HTTPException(status_code=404, detail="QR code not found")
    
    return FileResponse(qr.qr_image_path, media_type="image/png")