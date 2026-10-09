"""
Product Images Upload API
Керування зображеннями товарів
"""
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from sqlalchemy import text
from database_rentalhub import get_rh_db_sync
from PIL import Image
import os
import logging
import shutil
from pathlib import Path
from typing import List

router = APIRouter(prefix="/api/products", tags=["product-images"])
logger = logging.getLogger(__name__)

# Production path
UPLOAD_DIR = "/home/farforre/farforrent.com.ua/rentalhub/backend/uploads/products"
# Local preview path (fallback)
LOCAL_UPLOAD_DIR = "/app/backend/uploads/products"

# Use production path if exists, otherwise local
PRODUCTS_DIR = UPLOAD_DIR if os.path.exists(os.path.dirname(UPLOAD_DIR)) else LOCAL_UPLOAD_DIR

# Create directories if they don't exist
os.makedirs(PRODUCTS_DIR, exist_ok=True)
os.makedirs(os.path.join(PRODUCTS_DIR, "thumbnails"), exist_ok=True)
os.makedirs(os.path.join(PRODUCTS_DIR, "medium"), exist_ok=True)

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


def create_thumbnail(image_path: str, size: tuple) -> str:
    """Створити thumbnail зображення"""
    try:
        img = Image.open(image_path)
        
        # Convert RGBA to RGB if needed
        if img.mode in ('RGBA', 'LA', 'P'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
            img = background
        
        # Resize keeping aspect ratio
        img.thumbnail(size, Image.Resampling.LANCZOS)
        
        # Save thumbnail
        filename = os.path.basename(image_path)
        name, ext = os.path.splitext(filename)
        
        if size == (300, 300):
            thumb_path = os.path.join(PRODUCTS_DIR, "thumbnails", f"{name}_thumb{ext}")
        else:
            thumb_path = os.path.join(PRODUCTS_DIR, "medium", f"{name}_medium{ext}")
        
        img.save(thumb_path, quality=85, optimize=True)
        logger.info(f"Created thumbnail: {thumb_path}")
        return thumb_path
        
    except Exception as e:
        logger.error(f"Error creating thumbnail: {str(e)}")
        return None


@router.post("/{sku}/upload-image")
async def upload_product_image(
    sku: str,
    file: UploadFile = File(...),
    db = Depends(get_rh_db_sync)
):
    """
    Завантажити зображення для товару
    """
    try:
        # Validate file extension
        file_ext = os.path.splitext(file.filename)[1].lower()
        if file_ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Недопустимий формат файлу. Дозволені: {', '.join(ALLOWED_EXTENSIONS)}"
            )
        
        # Check file size
        file.file.seek(0, 2)
        file_size = file.file.tell()
        file.file.seek(0)
        
        if file_size > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"Файл завеликий. Максимум: {MAX_FILE_SIZE / 1024 / 1024}MB"
            )
        
        # Check if product exists
        query = text("SELECT product_id, name FROM products WHERE sku = :sku")
        result = db.execute(query, {"sku": sku}).fetchone()
        
        if not result:
            raise HTTPException(status_code=404, detail=f"Товар з SKU {sku} не знайдено")
        
        product_id, product_name = result
        
        # Generate safe filename: SKU_timestamp.ext
        import time
        safe_sku = sku.replace("/", "_").replace("\\", "_").replace(" ", "_")
        timestamp = int(time.time())
        filename = f"{safe_sku}_{timestamp}{file_ext}"
        file_path = os.path.join(PRODUCTS_DIR, filename)
        
        # Save original file
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        logger.info(f"Saved image: {file_path}")
        
        # Create thumbnails
        thumbnail_path = create_thumbnail(file_path, (300, 300))
        medium_path = create_thumbnail(file_path, (800, 800))
        
        # Update database with new image path
        # Store relative path from uploads root
        relative_path = f"uploads/products/{filename}"
        
        update_query = text("""
            UPDATE products 
            SET image_url = :image_url
            WHERE sku = :sku
        """)
        db.execute(update_query, {"image_url": relative_path, "sku": sku})
        db.commit()
        
        logger.info(f"Updated image URL for SKU {sku}: {relative_path}")
        
        return {
            "success": True,
            "message": f"Зображення завантажено для {product_name}",
            "sku": sku,
            "image_url": relative_path,
            "original": filename,
            "thumbnail": os.path.basename(thumbnail_path) if thumbnail_path else None,
            "medium": os.path.basename(medium_path) if medium_path else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading image for SKU {sku}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Помилка завантаження: {str(e)}")
    finally:
        db.close()


@router.post("/bulk-upload-images")
async def bulk_upload_images(
    files: List[UploadFile] = File(...),
    db = Depends(get_rh_db_sync)
):
    """
    Масове завантаження зображень
    Ім'я файлу має містити SKU товару
    """
    results = {
        "success": [],
        "failed": []
    }
    
    for file in files:
        try:
            # Extract SKU from filename (before first underscore or dot)
            filename = file.filename
            sku = filename.split('_')[0].split('.')[0]
            
            # Validate file extension
            file_ext = os.path.splitext(filename)[1].lower()
            if file_ext not in ALLOWED_EXTENSIONS:
                results["failed"].append({
                    "filename": filename,
                    "error": f"Недопустимий формат: {file_ext}"
                })
                continue
            
            # Check if product exists
            query = text("SELECT product_id, name FROM products WHERE sku = :sku")
            result = db.execute(query, {"sku": sku}).fetchone()
            
            if not result:
                results["failed"].append({
                    "filename": filename,
                    "sku": sku,
                    "error": "Товар не знайдено"
                })
                continue
            
            product_id, product_name = result
            
            # Generate safe filename
            import time
            safe_sku = sku.replace("/", "_").replace("\\", "_").replace(" ", "_")
            timestamp = int(time.time())
            new_filename = f"{safe_sku}_{timestamp}{file_ext}"
            file_path = os.path.join(PRODUCTS_DIR, new_filename)
            
            # Save file
            file.file.seek(0)
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            
            # Create thumbnails
            create_thumbnail(file_path, (300, 300))
            create_thumbnail(file_path, (800, 800))
            
            # Update database
            relative_path = f"uploads/products/{new_filename}"
            update_query = text("""
                UPDATE products 
                SET image_url = :image_url
                WHERE sku = :sku
            """)
            db.execute(update_query, {"image_url": relative_path, "sku": sku})
            db.commit()
            
            results["success"].append({
                "filename": filename,
                "sku": sku,
                "product_name": product_name,
                "image_url": relative_path
            })
            
        except Exception as e:
            results["failed"].append({
                "filename": file.filename,
                "error": str(e)
            })
    
    db.close()
    
    return {
        "total": len(files),
        "success_count": len(results["success"]),
        "failed_count": len(results["failed"]),
        "results": results
    }


@router.get("/{sku}/image-info")
async def get_product_image_info(sku: str, db = Depends(get_rh_db_sync)):
    """
    Отримати інформацію про зображення товару
    """
    try:
        query = text("""
            SELECT name, image_url, sku 
            FROM products 
            WHERE sku = :sku
        """)
        result = db.execute(query, {"sku": sku}).fetchone()
        
        if not result:
            raise HTTPException(status_code=404, detail="Товар не знайдено")
        
        product_name, image_url, sku = result
        
        # Check if image exists on disk
        has_image = False
        image_exists_on_disk = False
        
        if image_url:
            has_image = True
            if image_url.startswith("uploads/"):
                full_path = os.path.join(PRODUCTS_DIR, os.path.basename(image_url))
                image_exists_on_disk = os.path.exists(full_path)
        
        db.close()
        
        return {
            "sku": sku,
            "product_name": product_name,
            "image_url": image_url,
            "has_image": has_image,
            "image_exists_on_disk": image_exists_on_disk
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting image info for {sku}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()
