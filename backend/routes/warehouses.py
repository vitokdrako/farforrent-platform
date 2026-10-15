"""
Warehouses API — CRUD складів + stock per warehouse.
Phase 1: лише читання/запис, без логістичних transfers (Phase 2).
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional, List
from pydantic import BaseModel, Field

from database_rentalhub import get_rh_db
from utils.user_tracking_helper import get_current_user_dependency

router = APIRouter(prefix="/api/admin/warehouses", tags=["warehouses"])


# ============================================================================
# Pydantic schemas
# ============================================================================
class WarehouseIn(BaseModel):
    code: str = Field(..., min_length=1, max_length=16)
    name: str = Field(..., min_length=1, max_length=255)
    country: str = Field(..., min_length=2, max_length=2)
    city: Optional[str] = None
    address: Optional[str] = None
    currency: str = Field(default="UAH", min_length=3, max_length=3)
    timezone: Optional[str] = "Europe/Kyiv"
    phone: Optional[str] = None
    email: Optional[str] = None
    is_default: bool = False
    is_active: bool = True


class WarehouseUpdate(BaseModel):
    name: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None
    address: Optional[str] = None
    currency: Optional[str] = None
    timezone: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    is_default: Optional[bool] = None
    is_active: Optional[bool] = None


class WarehouseStockIn(BaseModel):
    quantity: Optional[int] = None
    reserved_qty: Optional[int] = None
    min_quantity: Optional[int] = None
    price_override: Optional[float] = None
    cost_override: Optional[float] = None
    is_available: Optional[bool] = None


# ============================================================================
# Helpers
# ============================================================================
def _warehouse_to_dict(row) -> dict:
    return {
        "id": row[0],
        "code": row[1],
        "name": row[2],
        "country": row[3],
        "city": row[4],
        "address": row[5],
        "currency": row[6],
        "timezone": row[7],
        "phone": row[8],
        "email": row[9],
        "is_default": bool(row[10]),
        "is_active": bool(row[11]),
    }


def _get_user_warehouse_ids(user_id: int, db: Session) -> List[int]:
    rows = db.execute(
        text("SELECT warehouse_id FROM user_warehouses WHERE user_id = :uid"),
        {"uid": user_id},
    ).fetchall()
    return [r[0] for r in rows]


def _is_super_admin(user_id: int, db: Session) -> bool:
    if not user_id:
        return False
    row = db.execute(
        text("SELECT is_super_admin FROM users WHERE user_id = :uid"),
        {"uid": user_id},
    ).fetchone()
    return bool(row[0]) if row else False


def _require_auth(user: dict) -> int:
    """Повертає user_id якщо залогінений, інакше кидає 401."""
    uid = user.get("user_id") or user.get("id")
    if not uid:
        raise HTTPException(401, "Not authenticated")
    return uid


# ============================================================================
# Warehouses CRUD
# ============================================================================
@router.get("")
async def list_warehouses(
    include_inactive: bool = Query(False),
    db: Session = Depends(get_rh_db),
    user: Optional[dict] = Depends(get_current_user_dependency),
):
    """
    Список складів. Якщо юзер не super_admin — повертаємо лише ті, до яких має доступ.
    Якщо юзер взагалі не залогінений — повертаємо активні (щоб publicly було видно у вітрині).
    """
    where_clauses = []
    params: dict = {}

    if not include_inactive:
        where_clauses.append("w.is_active = 1")

    uid = user.get("user_id") or user.get("id") if user else None
    if uid and not _is_super_admin(uid, db):
        where_clauses.append(
            "w.id IN (SELECT warehouse_id FROM user_warehouses WHERE user_id = :uid)"
        )
        params["uid"] = uid

    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
    rows = db.execute(
        text(f"""
            SELECT w.id, w.code, w.name, w.country, w.city, w.address, w.currency,
                   w.timezone, w.phone, w.email, w.is_default, w.is_active
            FROM warehouses w
            {where_sql}
            ORDER BY w.is_default DESC, w.code
        """),
        params,
    ).fetchall()

    result = []
    for row in rows:
        d = _warehouse_to_dict(row)
        # Статистика
        stats_row = db.execute(
            text("""
                SELECT
                    (SELECT COUNT(*) FROM product_warehouses WHERE warehouse_id = :wid AND quantity > 0) AS products,
                    (SELECT COUNT(*) FROM orders WHERE warehouse_id = :wid AND is_archived = 0) AS orders,
                    (SELECT COUNT(*) FROM client_users WHERE warehouse_id = :wid) AS clients
            """),
            {"wid": d["id"]},
        ).fetchone()
        d["stats"] = {
            "products": int(stats_row[0] or 0),
            "orders": int(stats_row[1] or 0),
            "clients": int(stats_row[2] or 0),
        }
        result.append(d)
    return result


@router.get("/{warehouse_id}")
async def get_warehouse(warehouse_id: int, db: Session = Depends(get_rh_db)):
    row = db.execute(
        text("""
            SELECT id, code, name, country, city, address, currency, timezone,
                   phone, email, is_default, is_active
            FROM warehouses WHERE id = :id
        """),
        {"id": warehouse_id},
    ).fetchone()
    if not row:
        raise HTTPException(404, "Warehouse not found")
    return _warehouse_to_dict(row)


@router.post("", status_code=201)
async def create_warehouse(
    payload: WarehouseIn,
    db: Session = Depends(get_rh_db),
    user: dict = Depends(get_current_user_dependency),
):
    if not _is_super_admin(_require_auth(user), db):
        raise HTTPException(403, "Only super_admin can create warehouses")

    # Якщо позначено is_default=TRUE — спочатку знімаємо з усіх
    if payload.is_default:
        db.execute(text("UPDATE warehouses SET is_default = FALSE"))

    try:
        res = db.execute(
            text("""
                INSERT INTO warehouses
                    (code, name, country, city, address, currency, timezone,
                     phone, email, is_default, is_active)
                VALUES
                    (:code, :name, :country, :city, :address, :currency, :timezone,
                     :phone, :email, :is_default, :is_active)
            """),
            payload.dict(),
        )
        db.commit()
    except Exception as e:
        db.rollback()
        if "Duplicate" in str(e) or "1062" in str(e):
            raise HTTPException(409, f"Warehouse with code '{payload.code}' already exists")
        raise HTTPException(500, f"Could not create warehouse: {e}")

    new_id = res.lastrowid
    return await get_warehouse(new_id, db)


@router.put("/{warehouse_id}")
async def update_warehouse(
    warehouse_id: int,
    payload: WarehouseUpdate,
    db: Session = Depends(get_rh_db),
    user: dict = Depends(get_current_user_dependency),
):
    if not _is_super_admin(_require_auth(user), db):
        raise HTTPException(403, "Only super_admin can edit warehouses")

    data = {k: v for k, v in payload.dict().items() if v is not None}
    if not data:
        return await get_warehouse(warehouse_id, db)

    if data.get("is_default"):
        db.execute(
            text("UPDATE warehouses SET is_default = FALSE WHERE id != :id"),
            {"id": warehouse_id},
        )

    set_clause = ", ".join(f"{k} = :{k}" for k in data.keys())
    data["id"] = warehouse_id
    db.execute(text(f"UPDATE warehouses SET {set_clause} WHERE id = :id"), data)
    db.commit()
    return await get_warehouse(warehouse_id, db)


@router.delete("/{warehouse_id}")
async def archive_warehouse(
    warehouse_id: int,
    db: Session = Depends(get_rh_db),
    user: dict = Depends(get_current_user_dependency),
):
    """М'яке видалення — просто is_active=FALSE. Повністю видалити не можна."""
    if not _is_super_admin(_require_auth(user), db):
        raise HTTPException(403, "Only super_admin can archive warehouses")
    row = db.execute(
        text("SELECT is_default FROM warehouses WHERE id = :id"),
        {"id": warehouse_id},
    ).fetchone()
    if not row:
        raise HTTPException(404, "Warehouse not found")
    if row[0]:
        raise HTTPException(400, "Cannot archive default warehouse. Set another one as default first.")
    db.execute(
        text("UPDATE warehouses SET is_active = FALSE WHERE id = :id"),
        {"id": warehouse_id},
    )
    db.commit()
    return {"ok": True}


# ============================================================================
# Current user's accessible warehouses
# ============================================================================
@router.get("/_me/accessible")
async def my_warehouses(
    db: Session = Depends(get_rh_db),
    user: dict = Depends(get_current_user_dependency),
):
    """
    Повертає склади, до яких має доступ поточний юзер.
    Використовується в WarehouseSwitcher.
    """
    uid = _require_auth(user)

    if _is_super_admin(uid, db):
        # Super admin — всі активні
        rows = db.execute(text("""
            SELECT id, code, name, country, city, currency, is_default
            FROM warehouses WHERE is_active = TRUE
            ORDER BY is_default DESC, code
        """)).fetchall()
    else:
        rows = db.execute(text("""
            SELECT w.id, w.code, w.name, w.country, w.city, w.currency, w.is_default
            FROM warehouses w
            JOIN user_warehouses uw ON uw.warehouse_id = w.id
            WHERE uw.user_id = :uid AND w.is_active = TRUE
            ORDER BY w.is_default DESC, w.code
        """), {"uid": uid}).fetchall()

    return [
        {
            "id": r[0], "code": r[1], "name": r[2], "country": r[3],
            "city": r[4], "currency": r[5], "is_default": bool(r[6]),
        }
        for r in rows
    ]
