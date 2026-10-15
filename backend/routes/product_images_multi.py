"""
Product Images Multi - Підтримка кількох фото на товар (Emergent object storage).
Використовує таблицю product_images.
"""
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from sqlalchemy import text
from database_rentalhub import get_rh_db_sync
import os
import logging
import re
from typing import List
from pydantic import BaseModel

from utils.object_storage import (
    put_object,
    build_storage_path,
    build_public_url,
    new_filename,
)

router = APIRouter(prefix="/api/products", tags=["product-images-multi"])
logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


def _sanitize_sku(sku: str) -> str:
    return re.sub(r"[^A-Za-z0-9_\-]", "_", sku)


def _resolve_product_id(db, product_id_or_sku: str) -> int:
    """Перетворює SKU або числовий product_id у числовий product_id."""
    try:
        return int(product_id_or_sku)
    except (ValueError, TypeError):
        pass
    row = db.execute(
        text("SELECT product_id FROM products WHERE sku = :sku LIMIT 1"),
        {"sku": product_id_or_sku},
    ).fetchone()
    if not row:
        raise HTTPException(404, f"Товар з SKU/ID '{product_id_or_sku}' не знайдено")
    return int(row[0])


# ─────────────────────────────────────────────────────────────────
# GET /api/products/{product_id}/images
# ─────────────────────────────────────────────────────────────────
@router.get("/{product_id}/images")
async def list_product_images(product_id: str, db=Depends(get_rh_db_sync)):
    """Повертає всі фото товару, відсортовані по sort_order"""
    try:
        product_id = _resolve_product_id(db, product_id)
        rows = db.execute(text("""
            SELECT id, product_id, image_url, sort_order, is_primary, source, created_at
            FROM product_images
            WHERE product_id = :pid
            ORDER BY is_primary DESC, sort_order ASC, id ASC
        """), {"pid": product_id}).fetchall()

        # Якщо в таблиці нічого немає — fallback на products.image_url (legacy)
        if not rows:
            legacy = db.execute(text(
                "SELECT image_url FROM products WHERE product_id = :pid"
            ), {"pid": product_id}).fetchone()
            if legacy and legacy[0]:
                return {
                    "images": [{
                        "id": 0,
                        "product_id": product_id,
                        "image_url": legacy[0],
                        "sort_order": 0,
                        "is_primary": True,
                        "source": "legacy",
                        "created_at": None,
                    }]
                }
            return {"images": []}

        return {
            "images": [
                {
                    "id": r[0],
                    "product_id": r[1],
                    "image_url": r[2],
                    "sort_order": r[3] or 0,
                    "is_primary": bool(r[4]),
                    "source": r[5] or "manual",
                    "created_at": r[6].isoformat() if r[6] else None,
                }
                for r in rows
            ]
        }
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────────
# POST /api/products/{product_id}/images  (multi-upload)
# ─────────────────────────────────────────────────────────────────
@router.post("/{product_id}/images")
async def upload_product_images(
    product_id: str,
    files: List[UploadFile] = File(...),
    db=Depends(get_rh_db_sync),
):
    """Завантажити кілька фото одночасно (object storage)."""
    try:
        product_id = _resolve_product_id(db, product_id)
        # Перевірка товара + дістати SKU
        prod = db.execute(text(
            "SELECT product_id, COALESCE(sku, 'no-sku') FROM products WHERE product_id = :pid"
        ), {"pid": product_id}).fetchone()
        if not prod:
            raise HTTPException(404, "Товар не знайдено")

        _sanitize_sku(prod[1] or f"id{product_id}")  # kept for backward-compat / future folder naming

        # Поточна максимальна sort_order
        max_order = db.execute(text(
            "SELECT COALESCE(MAX(sort_order), -1) FROM product_images WHERE product_id = :pid"
        ), {"pid": product_id}).scalar()

        # Чи вже є primary
        has_primary = db.execute(text(
            "SELECT COUNT(*) FROM product_images WHERE product_id = :pid AND is_primary = 1"
        ), {"pid": product_id}).scalar() > 0

        results = {"uploaded": [], "failed": []}
        next_order = (max_order or -1) + 1

        for f in files:
            try:
                ext = os.path.splitext(f.filename or "")[1].lower()
                if ext not in ALLOWED_EXTENSIONS:
                    results["failed"].append({"filename": f.filename, "error": f"Формат {ext} не підтримується"})
                    continue

                contents = await f.read()
                if len(contents) > MAX_FILE_SIZE:
                    results["failed"].append({"filename": f.filename, "error": "Файл завеликий (>10MB)"})
                    continue

                filename = new_filename(f.filename, default_ext="jpg")
                storage_path = build_storage_path("products", filename)
                upload_result = put_object(
                    storage_path, contents, f.content_type or "image/jpeg"
                )
                public_url = build_public_url(upload_result["path"])

                is_primary = 1 if (not has_primary and not results["uploaded"]) else 0

                # INSERT
                db.execute(text("""
                    INSERT INTO product_images
                    (product_id, image_url, sort_order, is_primary, source)
                    VALUES (:pid, :url, :sort, :prim, 'manual')
                """), {"pid": product_id, "url": public_url, "sort": next_order, "prim": is_primary})

                # Якщо це первинне фото — оновимо також products.image_url
                if is_primary == 1:
                    db.execute(text(
                        "UPDATE products SET image_url = :url WHERE product_id = :pid"
                    ), {"url": public_url, "pid": product_id})
                    has_primary = True

                results["uploaded"].append({
                    "filename": filename,
                    "url": public_url,
                    "sort_order": next_order,
                    "is_primary": bool(is_primary),
                })
                next_order += 1
            except Exception as e:
                logger.error("Upload failed for %s: %s", f.filename, e)
                results["failed"].append({"filename": f.filename, "error": str(e)})

        db.commit()
        return {"success": True, **results}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error("Multi upload error: %s", e)
        raise HTTPException(500, f"Помилка завантаження: {e}")
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────────
# DELETE /api/product-images/{image_id}
# ─────────────────────────────────────────────────────────────────
delete_router = APIRouter(prefix="/api", tags=["product-images-multi"])


@delete_router.delete("/product-images/{image_id}")
async def delete_product_image(image_id: int, db=Depends(get_rh_db_sync)):
    """
    Видалення запису про фото. Файл в object storage залишається осиротілим
    (у storage немає API видалення — див. playbook), це нормально.
    """
    try:
        row = db.execute(text(
            "SELECT product_id, image_url, is_primary FROM product_images WHERE id = :id"
        ), {"id": image_id}).fetchone()
        if not row:
            raise HTTPException(404, "Фото не знайдено")

        product_id, _image_url, was_primary = row[0], row[1], bool(row[2])

        db.execute(text("DELETE FROM product_images WHERE id = :id"), {"id": image_id})

        # Якщо видалили primary — призначимо нове primary
        if was_primary:
            next_primary = db.execute(text("""
                SELECT id, image_url FROM product_images
                WHERE product_id = :pid
                ORDER BY sort_order ASC, id ASC LIMIT 1
            """), {"pid": product_id}).fetchone()
            if next_primary:
                db.execute(text(
                    "UPDATE product_images SET is_primary = 1 WHERE id = :id"
                ), {"id": next_primary[0]})
                db.execute(text(
                    "UPDATE products SET image_url = :url WHERE product_id = :pid"
                ), {"url": next_primary[1], "pid": product_id})
            else:
                db.execute(text(
                    "UPDATE products SET image_url = NULL WHERE product_id = :pid"
                ), {"pid": product_id})

        db.commit()
        return {"success": True, "deleted_id": image_id}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Помилка видалення: {e}")
    finally:
        db.close()


@delete_router.put("/product-images/{image_id}/primary")
async def set_primary_image(image_id: int, db=Depends(get_rh_db_sync)):
    """Зробити фото головним"""
    try:
        row = db.execute(text(
            "SELECT product_id, image_url FROM product_images WHERE id = :id"
        ), {"id": image_id}).fetchone()
        if not row:
            raise HTTPException(404, "Фото не знайдено")

        product_id, image_url = row[0], row[1]

        # Скидаємо primary для всіх фото товара
        db.execute(text(
            "UPDATE product_images SET is_primary = 0 WHERE product_id = :pid"
        ), {"pid": product_id})

        # Встановлюємо primary для цього фото
        db.execute(text(
            "UPDATE product_images SET is_primary = 1 WHERE id = :id"
        ), {"id": image_id})

        # Оновлюємо products.image_url
        db.execute(text(
            "UPDATE products SET image_url = :url WHERE product_id = :pid"
        ), {"url": image_url, "pid": product_id})

        db.commit()
        return {"success": True, "image_id": image_id, "product_id": product_id}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Помилка: {e}")
    finally:
        db.close()


class ReorderItem(BaseModel):
    id: int
    sort_order: int


class ReorderRequest(BaseModel):
    items: List[ReorderItem]


@router.put("/{product_id}/images/reorder")
async def reorder_images(product_id: str, payload: ReorderRequest, db=Depends(get_rh_db_sync)):
    """Зміна порядку фото (drag&drop)"""
    try:
        product_id = _resolve_product_id(db, product_id)
        for item in payload.items:
            db.execute(text("""
                UPDATE product_images
                SET sort_order = :so
                WHERE id = :id AND product_id = :pid
            """), {"so": item.sort_order, "id": item.id, "pid": product_id})
        db.commit()
        return {"success": True, "updated": len(payload.items)}
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Помилка: {e}")
    finally:
        db.close()
