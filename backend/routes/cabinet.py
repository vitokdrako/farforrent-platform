"""
Personal Cabinet API — Особистий кабінет працівника
Профіль, мої задачі, статистика, дашборд
"""
from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime, date

from database_rentalhub import get_rh_db
from utils.user_tracking_helper import get_current_user_dependency

router = APIRouter(prefix="/api/cabinet", tags=["cabinet"])


def require_auth(current_user: dict = Depends(get_current_user_dependency)):
    uid = current_user.get("user_id") or current_user.get("id")
    if not uid or current_user.get("name") == "System":
        raise HTTPException(status_code=401, detail="Авторизуйтесь")
    return current_user


class ProfileUpdate(BaseModel):
    firstname: Optional[str] = None
    lastname: Optional[str] = None
    phone: Optional[str] = None
    telegram: Optional[str] = None


# === Profile ===

@router.get("/profile")
async def get_my_profile(
    user: dict = Depends(require_auth),
    db: Session = Depends(get_rh_db)
):
    uid = user.get("user_id") or user.get("id")
    row = db.execute(text("""
        SELECT user_id, username, email, firstname, lastname, role,
               is_active, created_at, last_login
        FROM users WHERE user_id = :uid
    """), {"uid": uid}).fetchone()

    if not row:
        raise HTTPException(404, "Користувач не знайдений")

    return {
        "user_id": row[0],
        "username": row[1],
        "email": row[2],
        "firstname": row[3] or "",
        "lastname": row[4] or "",
        "full_name": f"{row[3] or ''} {row[4] or ''}".strip(),
        "role": row[5],
        "is_active": bool(row[6]),
        "created_at": row[7].isoformat() if row[7] else None,
        "last_login": row[8].isoformat() if row[8] else None,
    }


@router.put("/profile")
async def update_my_profile(
    data: ProfileUpdate,
    user: dict = Depends(require_auth),
    db: Session = Depends(get_rh_db)
):
    uid = user.get("user_id") or user.get("id")
    sets = []
    params = {"uid": uid}
    if data.firstname is not None:
        sets.append("firstname = :fn")
        params["fn"] = data.firstname
    if data.lastname is not None:
        sets.append("lastname = :ln")
        params["ln"] = data.lastname
    if not sets:
        raise HTTPException(400, "Немає даних для оновлення")

    db.execute(text(f"UPDATE users SET {', '.join(sets)} WHERE user_id = :uid"), params)
    db.commit()
    return await get_my_profile(user, db)


# === My Tasks ===

def _format_task(r):
    return {
        "id": r[0], "order_id": r[1], "order_number": r[2],
        "title": r[3], "description": r[4],
        "task_type": r[5], "status": r[6], "priority": r[7],
        "due_date": r[8].isoformat() if r[8] else None,
        "completed_at": r[9].isoformat() if r[9] else None,
        "created_at": r[10].isoformat() if r[10] else None,
        "created_by": f"{r[11] or ''} {r[12] or ''}".strip() if r[11] else None,
        "assigned_to_id": r[13] if len(r) > 13 else None,
        "assignee_name": f"{r[14] or ''} {r[15] or ''}".strip() if len(r) > 14 and r[14] else None,
    }

_TASK_SELECT = """
    SELECT t.id, t.order_id, t.order_number, t.title, t.description,
           t.task_type, t.status, t.priority, t.due_date,
           t.completed_at, t.created_at,
           creator.firstname, creator.lastname,
           t.assigned_to_id,
           assignee.firstname, assignee.lastname
    FROM tasks t
    LEFT JOIN users creator ON t.created_by_id = creator.user_id
    LEFT JOIN users assignee ON t.assigned_to_id = assignee.user_id
"""


@router.get("/my-tasks")
async def get_my_tasks(
    status: Optional[str] = None,
    scope: Optional[str] = None,
    user: dict = Depends(require_auth),
    db: Session = Depends(get_rh_db)
):
    uid = user.get("user_id") or user.get("id")

    if scope == "all":
        where = "1=1"
        params = {}
    else:
        where = "t.assigned_to_id = :uid"
        params = {"uid": uid}

    if status:
        where += " AND t.status = :status"
        params["status"] = status

    rows = db.execute(text(f"""
        {_TASK_SELECT}
        WHERE {where}
        ORDER BY FIELD(t.priority, 'high', 'medium', 'low'),
                 FIELD(t.status, 'in_progress', 'todo', 'done'),
                 t.created_at DESC
    """), params).fetchall()

    return [_format_task(r) for r in rows]


# === Focus: tasks due today + overdue ===

@router.get("/focus")
async def get_daily_focus(
    user: dict = Depends(require_auth),
    db: Session = Depends(get_rh_db)
):
    uid = user.get("user_id") or user.get("id")
    today = date.today().isoformat()

    overdue = db.execute(text(f"""
        {_TASK_SELECT}
        WHERE t.assigned_to_id = :uid AND t.status != 'done'
          AND t.due_date IS NOT NULL AND DATE(t.due_date) < :today
        ORDER BY t.due_date ASC
    """), {"uid": uid, "today": today}).fetchall()

    due_today = db.execute(text(f"""
        {_TASK_SELECT}
        WHERE t.assigned_to_id = :uid AND t.status != 'done'
          AND DATE(t.due_date) = :today
        ORDER BY FIELD(t.priority, 'high', 'medium', 'low')
    """), {"uid": uid, "today": today}).fetchall()

    in_progress = db.execute(text(f"""
        {_TASK_SELECT}
        WHERE t.assigned_to_id = :uid AND t.status = 'in_progress'
        ORDER BY FIELD(t.priority, 'high', 'medium', 'low')
    """), {"uid": uid}).fetchall()

    # Week calendar: tasks per day for next 7 days
    week_start = date.today()
    week_data = []
    for i in range(7):
        d = week_start + __import__('datetime').timedelta(days=i)
        cnt = db.execute(text("""
            SELECT COUNT(*) FROM tasks
            WHERE assigned_to_id = :uid AND status != 'done'
              AND DATE(due_date) = :d
        """), {"uid": uid, "d": d.isoformat()}).scalar()
        week_data.append({"date": d.isoformat(), "day_name": d.strftime("%a"), "count": cnt or 0})

    return {
        "overdue": [_format_task(r) for r in overdue],
        "due_today": [_format_task(r) for r in due_today],
        "in_progress": [_format_task(r) for r in in_progress],
        "week": week_data,
    }


# === My Stats ===

@router.get("/stats")
async def get_my_stats(
    user: dict = Depends(require_auth),
    db: Session = Depends(get_rh_db)
):
    uid = user.get("user_id") or user.get("id")
    today = date.today().isoformat()

    # Task stats
    task_stats = db.execute(text("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN status = 'todo' THEN 1 ELSE 0 END) as todo,
            SUM(CASE WHEN status = 'in_progress' THEN 1 ELSE 0 END) as in_progress,
            SUM(CASE WHEN status = 'done' THEN 1 ELSE 0 END) as done,
            SUM(CASE WHEN due_date IS NOT NULL AND due_date < NOW() AND status != 'done' THEN 1 ELSE 0 END) as overdue
        FROM tasks
        WHERE assigned_to_id = :uid
    """), {"uid": uid}).fetchone()

    # Tasks completed today
    today_done = db.execute(text("""
        SELECT COUNT(*) FROM tasks
        WHERE assigned_to_id = :uid AND status = 'done'
          AND DATE(completed_at) = :today
    """), {"uid": uid, "today": today}).scalar()

    # Orders stats (from order_internal_notes as activity indicator)
    notes_today = db.execute(text("""
        SELECT COUNT(*) FROM order_internal_notes
        WHERE user_id = :uid AND DATE(created_at) = :today
    """), {"uid": uid, "today": today}).scalar()

    # Chat messages today
    msgs_today = db.execute(text("""
        SELECT COUNT(*) FROM chat_messages
        WHERE user_id = :uid AND DATE(created_at) = :today
    """), {"uid": uid, "today": today}).scalar()

    return {
        "tasks": {
            "total": task_stats[0] or 0,
            "todo": task_stats[1] or 0,
            "in_progress": task_stats[2] or 0,
            "done": task_stats[3] or 0,
            "overdue": task_stats[4] or 0,
        },
        "today": {
            "tasks_completed": today_done or 0,
            "notes_written": notes_today or 0,
            "messages_sent": msgs_today or 0,
        },
    }


# === Team Overview ===

@router.get("/team")
async def get_team_overview(
    user: dict = Depends(require_auth),
    db: Session = Depends(get_rh_db)
):
    rows = db.execute(text("""
        SELECT u.user_id, u.username, u.firstname, u.lastname, u.role,
               u.last_login,
               (SELECT COUNT(*) FROM tasks t WHERE t.assigned_to_id = u.user_id AND t.status != 'done') as active_tasks,
               (SELECT COUNT(*) FROM tasks t WHERE t.assigned_to_id = u.user_id AND t.status = 'done'
                AND DATE(t.completed_at) = CURDATE()) as done_today
        FROM users u
        WHERE u.is_active = 1
        ORDER BY u.role, u.firstname
    """)).fetchall()

    return [{
        "user_id": r[0], "username": r[1],
        "name": f"{r[2] or ''} {r[3] or ''}".strip(),
        "role": r[4],
        "last_login": r[5].isoformat() if r[5] else None,
        "active_tasks": r[6] or 0,
        "done_today": r[7] or 0,
    } for r in rows]



# === Order Chats ===

@router.get("/order-chats")
async def get_order_chats(
    mode: Optional[str] = "active",
    search: Optional[str] = None,
    user: dict = Depends(require_auth),
    db: Session = Depends(get_rh_db)
):
    """
    Get orders with internal notes count for Order Chats tab.
    mode: active (default), all, with_notes
    """
    status_filter = ""
    params = {}

    if mode == "active":
        status_filter = "AND o.status IN ('awaiting_customer','processing','ready_for_issue','issued','on_rent','partial_return','returned')"
    elif mode == "with_notes":
        status_filter = ""
    # 'all' = no filter

    search_filter = ""
    if search and search.strip():
        search_filter = "AND (o.order_number LIKE :search OR o.customer_name LIKE :search)"
        params["search"] = f"%{search.strip()}%"

    rows = db.execute(text(f"""
        SELECT o.order_id, o.order_number, o.customer_name, o.customer_phone,
               o.status, o.issue_date, o.return_date, o.created_at,
               COALESCE(n.notes_count, 0) as notes_count,
               n.last_note_at, n.last_note_user, n.last_note_text
        FROM orders o
        LEFT JOIN (
            SELECT order_id,
                   COUNT(*) as notes_count,
                   MAX(created_at) as last_note_at,
                   SUBSTRING_INDEX(GROUP_CONCAT(user_name ORDER BY created_at DESC SEPARATOR '|||'), '|||', 1) as last_note_user,
                   SUBSTRING_INDEX(GROUP_CONCAT(LEFT(message, 80) ORDER BY created_at DESC SEPARATOR '|||'), '|||', 1) as last_note_text
            FROM order_internal_notes
            GROUP BY order_id
        ) n ON CAST(n.order_id AS UNSIGNED) = o.order_id
        WHERE 1=1 {status_filter} {search_filter}
        {"HAVING notes_count > 0" if mode == "with_notes" else ""}
        ORDER BY
            CASE WHEN n.last_note_at IS NOT NULL THEN 0 ELSE 1 END,
            n.last_note_at DESC,
            o.order_id DESC
        LIMIT 100
    """), params).fetchall()

    return [{
        "order_id": r[0],
        "order_number": r[1],
        "customer_name": r[2] or "",
        "customer_phone": r[3] or "",
        "status": r[4] or "",
        "issue_date": r[5].isoformat() if r[5] else None,
        "return_date": r[6].isoformat() if r[6] else None,
        "created_at": r[7].isoformat() if r[7] else None,
        "notes_count": r[8] or 0,
        "last_note_at": r[9].isoformat() if r[9] else None,
        "last_note_user": r[10] or "",
        "last_note_text": r[11] or "",
    } for r in rows]



@router.get("/order-notes-new")
async def get_order_notes_new_count(
    user: dict = Depends(require_auth),
    db: Session = Depends(get_rh_db)
):
    """Count order notes from the last 24h not written by current user."""
    uid = str(user.get("user_id") or user.get("id"))
    count = db.execute(text("""
        SELECT COUNT(*) FROM order_internal_notes
        WHERE created_at >= NOW() - INTERVAL 24 HOUR
          AND (user_id IS NULL OR user_id != :uid)
    """), {"uid": uid}).scalar()
    return {"count": count or 0}
