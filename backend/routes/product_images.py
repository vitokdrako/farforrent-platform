"""
Product Images Upload API
Керування зображеннями товарів (Emergent object storage).
"""
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from sqlalchemy import text
from database_rentalhub import get_rh_db_sync
import os
import logging
from typing import List

from utils.object_storage import (
    put_object,
    build_storage_path,
    build_public_url,
    new_filename,
)

router = APIRouter(prefix="/api/products", tags=["product-images"])
logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


def _ext_from_name(name: str) -> str:
    return os.path.splitext(name or "")[1].lower()


@router.post("/{sku}/upload-image")
async def upload_product_image(
    sku: str,
    file: UploadFile = File(...),
    db=Depends(get_rh_db_sync),
):
    """
    Завантажити зображення для товару (object storage).
    """
    try:
        file_ext = _ext_from_name(file.filename)
        if file_ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Недопустимий формат файлу. Дозволені: {', '.join(ALLOWED_EXTENSIONS)}",
            )

        contents = await file.read()
        if len(contents) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"Файл завеликий. Максимум: {MAX_FILE_SIZE / 1024 / 1024}MB",
            )

        # Check if product exists
        query = text("SELECT product_id, name FROM products WHERE sku = :sku")
        result = db.execute(query, {"sku": sku}).fetchone()
        if not result:
            raise HTTPException(status_code=404, detail=f"Товар з SKU {sku} не знайдено")
        product_id, product_name = result

        # Upload to object storage
        filename = new_filename(file.filename, default_ext="jpg")
        storage_path = build_storage_path("products", filename)
        upload_result = put_object(
            storage_path, contents, file.content_type or "image/jpeg"
        )
        public_url = build_public_url(upload_result["path"])

        # Save url in DB
        db.execute(
            text("UPDATE products SET image_url = :image_url WHERE sku = :sku"),
            {"image_url": public_url, "sku": sku},
        )
        db.commit()

        logger.info("Uploaded product image for SKU %s -> %s", sku, public_url)

        return {
            "success": True,
            "message": f"Зображення завантажено для {product_name}",
            "sku": sku,
            "image_url": public_url,
            "original": filename,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error uploading image for SKU %s: %s", sku, str(e))
        raise HTTPException(status_code=500, detail=f"Помилка завантаження: {str(e)}")
    finally:
        db.close()


@router.post("/bulk-upload-images")
async def bulk_upload_images(
    files: List[UploadFile] = File(...),
    db=Depends(get_rh_db_sync),
):
    """
    Масове завантаження зображень (object storage).
    Ім'я файлу має містити SKU товару.
    """
    results = {"success": [], "failed": []}

    for file in files:
        try:
            filename = file.filename or ""
            sku = filename.split("_")[0].split(".")[0]

            file_ext = _ext_from_name(filename)
            if file_ext not in ALLOWED_EXTENSIONS:
                results["failed"].append(
                    {"filename": filename, "error": f"Недопустимий формат: {file_ext}"}
                )
                continue

            query = text("SELECT product_id, name FROM products WHERE sku = :sku")
            row = db.execute(query, {"sku": sku}).fetchone()
            if not row:
                results["failed"].append(
                    {"filename": filename, "sku": sku, "error": "Товар не знайдено"}
                )
                continue
            product_id, product_name = row

            contents = await file.read()
            if len(contents) > MAX_FILE_SIZE:
                results["failed"].append(
                    {"filename": filename, "sku": sku, "error": "Файл завеликий (>10MB)"}
                )
                continue

            new_name = new_filename(filename, default_ext="jpg")
            storage_path = build_storage_path("products", new_name)
            upload_result = put_object(
                storage_path, contents, file.content_type or "image/jpeg"
            )
            public_url = build_public_url(upload_result["path"])

            db.execute(
                text("UPDATE products SET image_url = :image_url WHERE sku = :sku"),
                {"image_url": public_url, "sku": sku},
            )
            db.commit()

            results["success"].append(
                {
                    "filename": filename,
                    "sku": sku,
                    "product_name": product_name,
                    "image_url": public_url,
                }
            )

        except Exception as e:
            results["failed"].append({"filename": file.filename, "error": str(e)})

    db.close()

    return {
        "total": len(files),
        "success_count": len(results["success"]),
        "failed_count": len(results["failed"]),
        "results": results,
    }


@router.get("/{sku}/image-info")
async def get_product_image_info(sku: str, db=Depends(get_rh_db_sync)):
    """Отримати інформацію про зображення товару."""
    try:
        query = text(
            """
            SELECT name, image_url, sku
            FROM products
            WHERE sku = :sku
        """
        )
        result = db.execute(query, {"sku": sku}).fetchone()

        if not result:
            raise HTTPException(status_code=404, detail="Товар не знайдено")

        product_name, image_url, sku = result

        return {
            "sku": sku,
            "product_name": product_name,
            "image_url": image_url,
            "has_image": bool(image_url),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error getting image info for %s: %s", sku, str(e))
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()
