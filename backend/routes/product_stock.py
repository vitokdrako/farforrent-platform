"""
Product Stock API — залишки товарів по складах.
Повертає/оновлює product_warehouses записи.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
from typing import Optional

from database_rentalhub import get_rh_db
from utils.user_tracking_helper import get_current_user_dependency

router = APIRouter(prefix="/api/admin/products", tags=["product-stock"])


class StockIn(BaseModel):
    quantity: Optional[int] = None
    reserved_qty: Optional[int] = None
    min_quantity: Optional[int] = None
    price_override: Optional[float] = None
    cost_override: Optional[float] = None
    is_available: Optional[bool] = None


@router.get("/{product_id}/stock")
async def get_product_stock(
    product_id: int,
    db: Session = Depends(get_rh_db),
):
    """
    Повертає залишки товару по всіх складах.
    Якщо товар ще не на складі — не з'являється у відповіді (admin може додати через PUT).
    """
    product_row = db.execute(
        text("""
            SELECT product_id, name, sku, price, quantity
            FROM products WHERE product_id = :pid
        """),
        {"pid": product_id},
    ).fetchone()
    if not product_row:
        raise HTTPException(404, "Product not found")

    rows = db.execute(
        text("""
            SELECT pw.warehouse_id, w.code, w.name, w.city, w.currency,
                   pw.quantity, pw.reserved_qty, pw.min_quantity,
                   pw.price_override, pw.cost_override, pw.is_available,
                   w.is_active
            FROM product_warehouses pw
            JOIN warehouses w ON w.id = pw.warehouse_id
            WHERE pw.product_id = :pid
            ORDER BY w.is_default DESC, w.code
        """),
        {"pid": product_id},
    ).fetchall()

    warehouses = [
        {
            "warehouse_id": r[0],
            "code": r[1],
            "name": r[2],
            "city": r[3],
            "currency": r[4],
            "quantity": int(r[5] or 0),
            "reserved_qty": int(r[6] or 0),
            "min_quantity": int(r[7] or 0),
            "price_override": float(r[8]) if r[8] is not None else None,
            "cost_override": float(r[9]) if r[9] is not None else None,
            "is_available": bool(r[10]),
            "is_active": bool(r[11]),
        }
        for r in rows
    ]

    total_stock = sum(w["quantity"] for w in warehouses)
    available_stock = sum(
        max(0, w["quantity"] - w["reserved_qty"])
        for w in warehouses
        if w["is_available"]
    )

    return {
        "product_id": product_row[0],
        "name": product_row[1],
        "sku": product_row[2],
        "base_price": float(product_row[3] or 0),
        "legacy_quantity": int(product_row[4] or 0),
        "warehouses": warehouses,
        "total_stock": total_stock,
        "available_stock": available_stock,
    }


@router.put("/{product_id}/stock/{warehouse_id}")
async def set_product_stock(
    product_id: int,
    warehouse_id: int,
    payload: StockIn,
    db: Session = Depends(get_rh_db),
    user: dict = Depends(get_current_user_dependency),
):
    """
    Створити/оновити запис про залишок товару на складі (upsert).
    Будь-яке None поле — залишає як є (або 0 на insert).
    """
    uid = user.get("user_id") or user.get("id")
    if not uid:
        raise HTTPException(401, "Not authenticated")

    # Перевірити що product і warehouse існують
    p = db.execute(text("SELECT product_id FROM products WHERE product_id = :pid"),
                   {"pid": product_id}).fetchone()
    if not p:
        raise HTTPException(404, "Product not found")
    w = db.execute(text("SELECT id FROM warehouses WHERE id = :wid"),
                   {"wid": warehouse_id}).fetchone()
    if not w:
        raise HTTPException(404, "Warehouse not found")

    data = payload.dict(exclude_none=True)

    # Check existence
    existing = db.execute(
        text("""
            SELECT quantity, reserved_qty, min_quantity, price_override,
                   cost_override, is_available
            FROM product_warehouses WHERE product_id = :pid AND warehouse_id = :wid
        """),
        {"pid": product_id, "wid": warehouse_id},
    ).fetchone()

    if existing:
        # UPDATE лише переданих полів
        if not data:
            return await get_product_stock(product_id, db)
        set_clause = ", ".join(f"{k} = :{k}" for k in data.keys())
        data.update({"pid": product_id, "wid": warehouse_id})
        db.execute(
            text(f"""
                UPDATE product_warehouses SET {set_clause}
                WHERE product_id = :pid AND warehouse_id = :wid
            """),
            data,
        )
    else:
        # INSERT з дефолтами
        insert_data = {
            "pid": product_id, "wid": warehouse_id,
            "quantity": data.get("quantity", 0),
            "reserved_qty": data.get("reserved_qty", 0),
            "min_quantity": data.get("min_quantity", 0),
            "price_override": data.get("price_override"),
            "cost_override": data.get("cost_override"),
            "is_available": data.get("is_available", True),
        }
        db.execute(
            text("""
                INSERT INTO product_warehouses
                    (product_id, warehouse_id, quantity, reserved_qty,
                     min_quantity, price_override, cost_override, is_available)
                VALUES
                    (:pid, :wid, :quantity, :reserved_qty,
                     :min_quantity, :price_override, :cost_override, :is_available)
            """),
            insert_data,
        )
    db.commit()
    return await get_product_stock(product_id, db)


@router.delete("/{product_id}/stock/{warehouse_id}")
async def remove_product_from_warehouse(
    product_id: int,
    warehouse_id: int,
    db: Session = Depends(get_rh_db),
    user: dict = Depends(get_current_user_dependency),
):
    """Прибрати товар зі складу (напр. якщо випадково додали)."""
    uid = user.get("user_id") or user.get("id")
    if not uid:
        raise HTTPException(401, "Not authenticated")
    db.execute(
        text("""
            DELETE FROM product_warehouses
            WHERE product_id = :pid AND warehouse_id = :wid
        """),
        {"pid": product_id, "wid": warehouse_id},
    )
    db.commit()
    return {"ok": True}
