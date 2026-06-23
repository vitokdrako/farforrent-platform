"""
Product Images Multi - Підтримка кількох фото на товар
Використовує нову таблицю product_images
"""
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from sqlalchemy import text
from database_rentalhub import get_rh_db_sync
from PIL import Image
import os
import logging
import shutil
import time
import re
from pathlib import Path
from typing import List
from pydantic import BaseModel

router = APIRouter(prefix="/api/products", tags=["product-images-multi"])
logger = logging.getLogger(__name__)

# Production path (на VPS)
PROD_DIR = "/var/www/farforrent/backend/uploads/products"
# Legacy production path (старий хостинг)
LEGACY_DIR = "/home/farforre/farforrent.com.ua/rentalhub/backend/uploads/products"
# Local fallback
LOCAL_DIR = "/app/backend/uploads/products"

# Auto-detect
if os.path.exists(os.path.dirname(PROD_DIR)):
    PRODUCTS_DIR = PROD_DIR
elif os.path.exists(os.path.dirname(LEGACY_DIR)):
    PRODUCTS_DIR = LEGACY_DIR
else:
    PRODUCTS_DIR = LOCAL_DIR

os.makedirs(PRODUCTS_DIR, exist_ok=True)
os.makedirs(os.path.join(PRODUCTS_DIR, "thumbnails"), exist_ok=True)
os.makedirs(os.path.join(PRODUCTS_DIR, "medium"), exist_ok=True)

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


def _make_thumb(image_path: str, size: tuple, subdir: str) -> str | None:
    """Створює thumbnail заданого розміру, повертає шлях"""
    try:
        img = Image.open(image_path)
        if img.mode in ("RGBA", "LA", "P"):
            bg = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode == "P":
                img = img.convert("RGBA")
            bg.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
            img = bg
        img.thumbnail(size, Image.Resampling.LANCZOS)

        filename = os.path.basename(image_path)
        out_path = os.path.join(PRODUCTS_DIR, subdir, filename)
        img.save(out_path, quality=85, optimize=True)
        return out_path
    except Exception as e:
        logger.error(f"Thumbnail error: {e}")
        return None


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
    """Завантажити кілька фото одночасно для товара"""
    try:
        product_id = _resolve_product_id(db, product_id)
        # Перевірка товара + дістати SKU
        prod = db.execute(text(
            "SELECT product_id, COALESCE(sku, 'no-sku') FROM products WHERE product_id = :pid"
        ), {"pid": product_id}).fetchone()
        if not prod:
            raise HTTPException(404, "Товар не знайдено")

        sku = _sanitize_sku(prod[1] or f"id{product_id}")

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

                # Розмір
                f.file.seek(0, 2)
                size = f.file.tell()
                f.file.seek(0)
                if size > MAX_FILE_SIZE:
                    results["failed"].append({"filename": f.filename, "error": "Файл завеликий (>10MB)"})
                    continue

                # Зберігаємо
                ts = int(time.time() * 1000)
                filename = f"{sku}_{ts}_{next_order}{ext}"
                file_path = os.path.join(PRODUCTS_DIR, filename)
                with open(file_path, "wb") as buf:
                    shutil.copyfileobj(f.file, buf)

                # Thumbnails
                _make_thumb(file_path, (300, 300), "thumbnails")
                _make_thumb(file_path, (800, 800), "medium")

                relative_url = f"uploads/products/{filename}"
                is_primary = 1 if (not has_primary and not results["uploaded"]) else 0

                # INSERT
                db.execute(text("""
                    INSERT INTO product_images
                    (product_id, image_url, sort_order, is_primary, source)
                    VALUES (:pid, :url, :sort, :prim, 'manual')
                """), {"pid": product_id, "url": relative_url, "sort": next_order, "prim": is_primary})

                # Якщо це первинне фото — оновимо також products.image_url
                if is_primary == 1:
                    db.execute(text(
                        "UPDATE products SET image_url = :url WHERE product_id = :pid"
                    ), {"url": relative_url, "pid": product_id})
                    has_primary = True

                results["uploaded"].append({
                    "filename": filename,
                    "url": relative_url,
                    "sort_order": next_order,
                    "is_primary": bool(is_primary),
                })
                next_order += 1
            except Exception as e:
                logger.error(f"Upload failed for {f.filename}: {e}")
                results["failed"].append({"filename": f.filename, "error": str(e)})

        db.commit()
        return {"success": True, **results}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Multi upload error: {e}")
        raise HTTPException(500, f"Помилка завантаження: {e}")
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────────
# DELETE /api/product-images/{image_id}
# ─────────────────────────────────────────────────────────────────
delete_router = APIRouter(prefix="/api", tags=["product-images-multi"])


@delete_router.delete("/product-images/{image_id}")
async def delete_product_image(image_id: int, db=Depends(get_rh_db_sync)):
    try:
        row = db.execute(text(
            "SELECT product_id, image_url, is_primary FROM product_images WHERE id = :id"
        ), {"id": image_id}).fetchone()
        if not row:
            raise HTTPException(404, "Фото не знайдено")

        product_id, image_url, was_primary = row[0], row[1], bool(row[2])

        # Видаляємо файл
        try:
            full = os.path.join("/var/www/farforrent/backend", image_url) if not os.path.isabs(image_url) else image_url
            if os.path.exists(full):
                os.remove(full)
                # thumbnails
                base = os.path.basename(image_url)
                for sub in ("thumbnails", "medium"):
                    t = os.path.join(PRODUCTS_DIR, sub, base)
                    if os.path.exists(t):
                        os.remove(t)
        except Exception as e:
            logger.warning(f"File delete warning: {e}")

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
