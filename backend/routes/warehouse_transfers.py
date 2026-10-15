"""
Warehouse Transfers API — Переміщення товарів між складами (Phase 2).

Статуси:
  draft      — чернетка, можна редагувати склад позицій, нічого не списано
  in_transit — товар відвантажено з from_warehouse (списано зі stock), їде в to_warehouse
  received   — товар прийнято, зараховано в stock to_warehouse
  cancelled  — скасовано (можливо лише з draft)

Переходи дозволені:
  draft      -> in_transit  (POST /{id}/ship)       — списує з from_warehouse
  in_transit -> received    (POST /{id}/receive)    — зараховує на to_warehouse
  draft      -> cancelled   (POST /{id}/cancel)
"""
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from database_rentalhub import get_rh_db
from utils.user_tracking_helper import get_current_user_dependency

router = APIRouter(prefix="/api/admin/warehouse-transfers", tags=["warehouse-transfers"])


# ============================================================================
# Pydantic schemas
# ============================================================================
class TransferItemIn(BaseModel):
    product_id: int
    quantity: int = Field(..., gt=0)
    note: Optional[str] = None


class TransferIn(BaseModel):
    from_warehouse_id: int
    to_warehouse_id: int
    note: Optional[str] = None
    items: List[TransferItemIn] = Field(default_factory=list)


class TransferUpdate(BaseModel):
    note: Optional[str] = None
    items: Optional[List[TransferItemIn]] = None


# ============================================================================
# Helpers
# ============================================================================
def _require_auth(user: Optional[dict]) -> int:
    uid = (user or {}).get("user_id") or (user or {}).get("id")
    if not uid:
        raise HTTPException(401, "Not authenticated")
    return uid


def _generate_transfer_number(db: Session) -> str:
    """WT-YYYY-NNN, counter resets each year."""
    year = datetime.now().year
    row = db.execute(
        text("""
            SELECT COUNT(*) + 1
            FROM warehouse_transfers
            WHERE YEAR(created_at) = :year
        """),
        {"year": year},
    ).scalar()
    return f"WT-{year}-{int(row or 1):04d}"


def _transfer_row_to_dict(row) -> dict:
    return {
        "id": row[0],
        "transfer_number": row[1],
        "from_warehouse_id": row[2],
        "to_warehouse_id": row[3],
        "status": row[4],
        "note": row[5],
        "created_by": row[6],
        "shipped_by": row[7],
        "received_by": row[8],
        "created_at": row[9].isoformat() if row[9] else None,
        "shipped_at": row[10].isoformat() if row[10] else None,
        "received_at": row[11].isoformat() if row[11] else None,
        "cancelled_at": row[12].isoformat() if row[12] else None,
        "from_warehouse": {"id": row[13], "code": row[14], "name": row[15]},
        "to_warehouse": {"id": row[16], "code": row[17], "name": row[18]},
    }


_SELECT_SQL = """
    SELECT t.id, t.transfer_number, t.from_warehouse_id, t.to_warehouse_id,
           t.status, t.note, t.created_by, t.shipped_by, t.received_by,
           t.created_at, t.shipped_at, t.received_at, t.cancelled_at,
           wf.id, wf.code, wf.name,
           wt.id, wt.code, wt.name
    FROM warehouse_transfers t
    JOIN warehouses wf ON wf.id = t.from_warehouse_id
    JOIN warehouses wt ON wt.id = t.to_warehouse_id
"""


def _load_items(db: Session, transfer_id: int) -> list[dict]:
    rows = db.execute(
        text("""
            SELECT i.id, i.product_id, i.quantity, i.note,
                   p.sku, p.name, p.image_url
            FROM warehouse_transfer_items i
            LEFT JOIN products p ON p.product_id = i.product_id
            WHERE i.transfer_id = :tid
            ORDER BY i.id
        """),
        {"tid": transfer_id},
    ).fetchall()
    return [
        {
            "id": r[0],
            "product_id": r[1],
            "quantity": r[2],
            "note": r[3],
            "sku": r[4],
            "name": r[5],
            "image_url": r[6],
        }
        for r in rows
    ]


# ============================================================================
# Routes
# ============================================================================
@router.get("")
async def list_transfers(
    status: Optional[str] = Query(None),
    warehouse_id: Optional[int] = Query(None, description="Фільтр: or_from=warehouse_id OR to=warehouse_id"),
    limit: int = Query(100, le=500),
    db: Session = Depends(get_rh_db),
):
    """Список переміщень. warehouse_id — показати лише ті, де цей склад або from, або to."""
    where = []
    params: dict = {}
    if status:
        where.append("t.status = :status")
        params["status"] = status
    if warehouse_id is not None:
        where.append("(t.from_warehouse_id = :wid OR t.to_warehouse_id = :wid)")
        params["wid"] = warehouse_id
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""

    rows = db.execute(
        text(f"""
            {_SELECT_SQL}
            {where_sql}
            ORDER BY t.created_at DESC
            LIMIT :limit
        """),
        {**params, "limit": limit},
    ).fetchall()

    result = []
    for row in rows:
        d = _transfer_row_to_dict(row)
        # Add brief item count
        cnt = db.execute(
            text("""
                SELECT COUNT(*), COALESCE(SUM(quantity), 0)
                FROM warehouse_transfer_items WHERE transfer_id = :tid
            """),
            {"tid": d["id"]},
        ).fetchone()
        d["item_count"] = int(cnt[0] or 0)
        d["total_quantity"] = int(cnt[1] or 0)
        result.append(d)
    return result


@router.get("/{transfer_id}")
async def get_transfer(transfer_id: int, db: Session = Depends(get_rh_db)):
    row = db.execute(
        text(f"{_SELECT_SQL} WHERE t.id = :id"),
        {"id": transfer_id},
    ).fetchone()
    if not row:
        raise HTTPException(404, "Transfer not found")
    d = _transfer_row_to_dict(row)
    d["items"] = _load_items(db, transfer_id)
    return d


@router.post("", status_code=201)
async def create_transfer(
    payload: TransferIn,
    db: Session = Depends(get_rh_db),
    user: dict = Depends(get_current_user_dependency),
):
    """Створити переміщення (статус = draft)."""
    uid = _require_auth(user)

    if payload.from_warehouse_id == payload.to_warehouse_id:
        raise HTTPException(400, "from_warehouse_id і to_warehouse_id мають відрізнятися")

    # Validate warehouses exist
    row = db.execute(
        text(
            "SELECT COUNT(*) FROM warehouses WHERE id IN (:a, :b) AND is_active = 1"
        ),
        {"a": payload.from_warehouse_id, "b": payload.to_warehouse_id},
    ).scalar()
    if int(row or 0) != 2:
        raise HTTPException(400, "Один зі складів не знайдено або неактивний")

    try:
        transfer_number = _generate_transfer_number(db)
        res = db.execute(
            text("""
                INSERT INTO warehouse_transfers
                    (transfer_number, from_warehouse_id, to_warehouse_id, status, note, created_by)
                VALUES
                    (:tn, :from_id, :to_id, 'draft', :note, :uid)
            """),
            {
                "tn": transfer_number,
                "from_id": payload.from_warehouse_id,
                "to_id": payload.to_warehouse_id,
                "note": payload.note,
                "uid": uid,
            },
        )
        transfer_id = res.lastrowid

        for item in payload.items:
            db.execute(
                text("""
                    INSERT INTO warehouse_transfer_items
                        (transfer_id, product_id, quantity, note)
                    VALUES (:tid, :pid, :qty, :note)
                """),
                {
                    "tid": transfer_id,
                    "pid": item.product_id,
                    "qty": item.quantity,
                    "note": item.note,
                },
            )
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Could not create transfer: {e}")

    return await get_transfer(transfer_id, db)


@router.put("/{transfer_id}")
async def update_transfer(
    transfer_id: int,
    payload: TransferUpdate,
    db: Session = Depends(get_rh_db),
    user: dict = Depends(get_current_user_dependency),
):
    """Редагувати draft — note та список позицій. Інші статуси — заборонено."""
    _require_auth(user)

    status_row = db.execute(
        text("SELECT status FROM warehouse_transfers WHERE id = :id"),
        {"id": transfer_id},
    ).fetchone()
    if not status_row:
        raise HTTPException(404, "Transfer not found")
    if status_row[0] != "draft":
        raise HTTPException(400, f"Можна редагувати лише чернетку (поточний статус: {status_row[0]})")

    try:
        if payload.note is not None:
            db.execute(
                text("UPDATE warehouse_transfers SET note = :note WHERE id = :id"),
                {"note": payload.note, "id": transfer_id},
            )

        if payload.items is not None:
            db.execute(
                text("DELETE FROM warehouse_transfer_items WHERE transfer_id = :id"),
                {"id": transfer_id},
            )
            for item in payload.items:
                db.execute(
                    text("""
                        INSERT INTO warehouse_transfer_items
                            (transfer_id, product_id, quantity, note)
                        VALUES (:tid, :pid, :qty, :note)
                    """),
                    {
                        "tid": transfer_id,
                        "pid": item.product_id,
                        "qty": item.quantity,
                        "note": item.note,
                    },
                )
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Could not update transfer: {e}")

    return await get_transfer(transfer_id, db)


@router.post("/{transfer_id}/ship")
async def ship_transfer(
    transfer_id: int,
    db: Session = Depends(get_rh_db),
    user: dict = Depends(get_current_user_dependency),
):
    """draft -> in_transit. Атомарно списує stock з from_warehouse."""
    uid = _require_auth(user)

    row = db.execute(
        text("""
            SELECT status, from_warehouse_id FROM warehouse_transfers WHERE id = :id
        """),
        {"id": transfer_id},
    ).fetchone()
    if not row:
        raise HTTPException(404, "Transfer not found")
    if row[0] != "draft":
        raise HTTPException(400, f"Відвантажити можна лише з draft (поточний: {row[0]})")
    from_wid = row[1]

    items = db.execute(
        text("""
            SELECT product_id, quantity FROM warehouse_transfer_items WHERE transfer_id = :id
        """),
        {"id": transfer_id},
    ).fetchall()
    if not items:
        raise HTTPException(400, "Переміщення без позицій — додайте товари перед відвантаженням")

    # Pre-flight: перевіримо достатність залишків
    for pid, qty in items:
        stock = db.execute(
            text("""
                SELECT COALESCE(quantity, 0) - COALESCE(reserved_qty, 0)
                FROM product_warehouses WHERE product_id = :pid AND warehouse_id = :wid
            """),
            {"pid": pid, "wid": from_wid},
        ).scalar()
        if stock is None or int(stock) < qty:
            raise HTTPException(
                400,
                f"Недостатньо товару product_id={pid} на складі: доступно {stock or 0}, потрібно {qty}",
            )

    try:
        # Списуємо з from_warehouse
        for pid, qty in items:
            db.execute(
                text("""
                    UPDATE product_warehouses
                    SET quantity = quantity - :qty
                    WHERE product_id = :pid AND warehouse_id = :wid
                """),
                {"qty": qty, "pid": pid, "wid": from_wid},
            )

        db.execute(
            text("""
                UPDATE warehouse_transfers
                SET status = 'in_transit', shipped_at = NOW(), shipped_by = :uid
                WHERE id = :id
            """),
            {"uid": uid, "id": transfer_id},
        )
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Could not ship transfer: {e}")

    return await get_transfer(transfer_id, db)


@router.post("/{transfer_id}/receive")
async def receive_transfer(
    transfer_id: int,
    db: Session = Depends(get_rh_db),
    user: dict = Depends(get_current_user_dependency),
):
    """in_transit -> received. Атомарно зараховує stock на to_warehouse."""
    uid = _require_auth(user)

    row = db.execute(
        text("""
            SELECT status, to_warehouse_id FROM warehouse_transfers WHERE id = :id
        """),
        {"id": transfer_id},
    ).fetchone()
    if not row:
        raise HTTPException(404, "Transfer not found")
    if row[0] != "in_transit":
        raise HTTPException(400, f"Прийняти можна лише з in_transit (поточний: {row[0]})")
    to_wid = row[1]

    items = db.execute(
        text("SELECT product_id, quantity FROM warehouse_transfer_items WHERE transfer_id = :id"),
        {"id": transfer_id},
    ).fetchall()

    try:
        for pid, qty in items:
            # UPSERT: якщо запису немає — створюємо
            db.execute(
                text("""
                    INSERT INTO product_warehouses (product_id, warehouse_id, quantity, is_available)
                    VALUES (:pid, :wid, :qty, 1)
                    ON DUPLICATE KEY UPDATE quantity = quantity + :qty
                """),
                {"pid": pid, "wid": to_wid, "qty": qty},
            )
        db.execute(
            text("""
                UPDATE warehouse_transfers
                SET status = 'received', received_at = NOW(), received_by = :uid
                WHERE id = :id
            """),
            {"uid": uid, "id": transfer_id},
        )
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Could not receive transfer: {e}")

    return await get_transfer(transfer_id, db)


@router.post("/{transfer_id}/cancel")
async def cancel_transfer(
    transfer_id: int,
    db: Session = Depends(get_rh_db),
    user: dict = Depends(get_current_user_dependency),
):
    """draft -> cancelled. Нічого списувати не треба."""
    _require_auth(user)
    row = db.execute(
        text("SELECT status FROM warehouse_transfers WHERE id = :id"),
        {"id": transfer_id},
    ).fetchone()
    if not row:
        raise HTTPException(404, "Transfer not found")
    if row[0] != "draft":
        raise HTTPException(400, f"Скасувати можна лише чернетку (поточний: {row[0]})")

    db.execute(
        text("""
            UPDATE warehouse_transfers
            SET status = 'cancelled', cancelled_at = NOW()
            WHERE id = :id
        """),
        {"id": transfer_id},
    )
    db.commit()
    return await get_transfer(transfer_id, db)


@router.delete("/{transfer_id}")
async def delete_transfer(
    transfer_id: int,
    db: Session = Depends(get_rh_db),
    user: dict = Depends(get_current_user_dependency),
):
    """Повне видалення — лише для draft."""
    _require_auth(user)
    row = db.execute(
        text("SELECT status FROM warehouse_transfers WHERE id = :id"),
        {"id": transfer_id},
    ).fetchone()
    if not row:
        raise HTTPException(404, "Transfer not found")
    if row[0] != "draft":
        raise HTTPException(400, "Видалити можна лише чернетку. Активні переміщення — через cancel.")
    db.execute(text("DELETE FROM warehouse_transfers WHERE id = :id"), {"id": transfer_id})
    db.commit()
    return {"ok": True}
