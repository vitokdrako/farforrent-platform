"""
Tasks routes
✅ MIGRATED: Using RentalHub DB
✅ UPDATED: Підтримка assigned_to_id (user_id) замість текстового поля
"""
from fastapi import APIRouter, HTTPException, Depends, Header
from typing import List, Optional
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime
import uuid
import jwt
import os

from database_rentalhub import get_rh_db

router = APIRouter(prefix="/api/tasks", tags=["tasks"])

# JWT config
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"

# ============================================================
# HELPER: Get current user from token
# ============================================================

def get_current_user_from_token(authorization: str = Header(None)):
    """Extract user from JWT token"""
    if not authorization:
        return None
    try:
        token = authorization.replace("Bearer ", "")
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return {
            'id': payload.get('user_id'),
            'email': payload.get('sub'),
            'role': payload.get('role')
        }
    except:
        return None

# ============================================================
# PYDANTIC MODELS
# ============================================================

class TaskCreate(BaseModel):
    order_id: Optional[int] = None
    order_number: Optional[str] = None
    damage_id: Optional[str] = None
    title: str
    description: Optional[str] = None
    task_type: str = "general"
    status: str = "todo"
    priority: str = "medium"
    assigned_to_id: Optional[int] = None  # ✅ user_id
    assigned_to: Optional[str] = None  # legacy text field (для зворотної сумісності)
    due_date: Optional[datetime] = None

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    task_type: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    assigned_to_id: Optional[int] = None  # ✅ user_id
    assigned_to: Optional[str] = None  # legacy
    due_date: Optional[datetime] = None
    completed_at: Optional[datetime] = None

# ============================================================
# API ENDPOINTS
# ============================================================

@router.get("/staff")
async def get_staff_for_assignment(db: Session = Depends(get_rh_db)):
    """
    Отримати список працівників для призначення тасків
    """
    result = db.execute(text("""
        SELECT user_id, username, firstname, lastname, role
        FROM users
        WHERE is_active = 1
        ORDER BY role, firstname
    """))
    
    staff = []
    for row in result:
        full_name = f"{row[2] or ''} {row[3] or ''}".strip() or row[1]
        staff.append({
            "id": row[0],
            "user_id": row[0],
            "username": row[1],
            "full_name": full_name,
            "role": row[4]
        })
    
    return staff

@router.get("")
async def get_tasks(
    status: Optional[str] = None,
    task_type: Optional[str] = None,
    order_id: Optional[int] = None,
    assigned_to_id: Optional[int] = None,  # ✅ Фільтр по user_id
    my_tasks: Optional[bool] = None,  # ✅ Фільтр "мої завдання"
    authorization: str = Header(None),
    db: Session = Depends(get_rh_db)
):
    """
    Get all tasks
    ✅ UPDATED: Підтримка assigned_to_id та фільтру "мої завдання"
    """
    current_user = get_current_user_from_token(authorization)
    
    sql_query = """
        SELECT 
            t.id, t.order_id, t.order_number, t.damage_id, t.title, t.description,
            t.task_type, t.status, t.priority, t.assigned_to, t.due_date,
            t.completed_at, t.created_by, t.created_at, t.updated_at,
            t.assigned_to_id, t.created_by_id,
            NULL as damage_case_number,
            u.firstname as assignee_firstname, u.lastname as assignee_lastname,
            creator.firstname as creator_firstname, creator.lastname as creator_lastname
        FROM tasks t
        LEFT JOIN users u ON t.assigned_to_id = u.user_id
        LEFT JOIN users creator ON t.created_by_id = creator.user_id
        WHERE 1=1
    """
    params = {}
    
    if status:
        sql_query += " AND t.status = :status"
        params['status'] = status
    if task_type:
        sql_query += " AND t.task_type = :task_type"
        params['task_type'] = task_type
    if order_id:
        sql_query += " AND t.order_id = :order_id"
        params['order_id'] = order_id
    if assigned_to_id:
        sql_query += " AND t.assigned_to_id = :assigned_to_id"
        params['assigned_to_id'] = assigned_to_id
    
    # ✅ Фільтр "мої завдання"
    if my_tasks and current_user and current_user.get('id'):
        sql_query += " AND t.assigned_to_id = :my_user_id"
        params['my_user_id'] = current_user['id']
    
    sql_query += " ORDER BY FIELD(t.priority, 'high', 'medium', 'low'), t.created_at DESC"
    
    result = db.execute(text(sql_query), params)
    
    tasks = []
    for row in result:
        # Формуємо ім'я виконавця
        assignee_name = None
        if row[18] or row[19]:  # assignee_firstname, assignee_lastname
            assignee_name = f"{row[18] or ''} {row[19] or ''}".strip()
        elif row[9]:  # legacy assigned_to text
            assignee_name = row[9]
        
        # Формуємо ім'я створювача
        creator_name = None
        if row[20] or row[21]:
            creator_name = f"{row[20] or ''} {row[21] or ''}".strip()
        elif row[12]:
            creator_name = row[12]
        
        tasks.append({
            "id": row[0],
            "order_id": row[1],
            "order_number": row[2],
            "damage_id": row[3],
            "title": row[4],
            "description": row[5],
            "task_type": row[6],
            "status": row[7],
            "priority": row[8],
            "assigned_to": assignee_name,  # Для зворотної сумісності
            "assigned_to_id": row[15],  # ✅ user_id
            "assignee_name": assignee_name,  # ✅ Повне ім'я
            "due_date": row[10].isoformat() if row[10] else None,
            "completed_at": row[11].isoformat() if row[11] else None,
            "created_by": creator_name,
            "created_by_id": row[16],
            "created_at": row[13].isoformat() if row[13] else None,
            "updated_at": row[14].isoformat() if row[14] else None,
            "damage_case_number": row[17]
        })
    
    return tasks

@router.post("")
async def create_task(
    task: TaskCreate,
    authorization: str = Header(None),
    db: Session = Depends(get_rh_db)
):
    """
    Create new task
    ✅ UPDATED: Підтримка assigned_to_id та created_by_id
    """
    current_user = get_current_user_from_token(authorization)
    task_id = str(uuid.uuid4())
    
    # Визначаємо created_by_id
    created_by_id = current_user.get('id') if current_user else None
    created_by = current_user.get('email') if current_user else 'System'
    
    db.execute(text("""
        INSERT INTO tasks (
            id, order_id, order_number, damage_id, title, description,
            task_type, status, priority, assigned_to, assigned_to_id, due_date,
            created_by, created_by_id, created_at, updated_at
        )
        VALUES (
            :id, :order_id, :order_number, :damage_id, :title, :description,
            :task_type, :status, :priority, :assigned_to, :assigned_to_id, :due_date,
            :created_by, :created_by_id, NOW(), NOW()
        )
    """), {
        "id": task_id,
        "order_id": task.order_id,
        "order_number": task.order_number,
        "damage_id": task.damage_id,
        "title": task.title,
        "description": task.description,
        "task_type": task.task_type,
        "status": task.status,
        "priority": task.priority,
        "assigned_to": task.assigned_to,  # legacy
        "assigned_to_id": task.assigned_to_id,  # ✅ user_id
        "due_date": task.due_date,
        "created_by": created_by,
        "created_by_id": created_by_id
    })
    
    db.commit()
    
    # === Task-Chat Integration: notify in chat ===
    try:
        from routes.team_chat import notify_task_in_chat
        assignee_name = ""
        if task.assigned_to_id:
            arow = db.execute(text("SELECT firstname, lastname FROM users WHERE user_id = :uid"), {"uid": task.assigned_to_id}).fetchone()
            if arow:
                assignee_name = f"{arow[0] or ''} {arow[1] or ''}".strip()
        notify_task_in_chat(
            db=db, user_id=created_by_id or 1, user_name=created_by,
            task_title=task.title, task_id=task_id,
            assignee_name=assignee_name,
            priority=task.priority or "",
            due_date=str(task.due_date) if task.due_date else "",
        )
    except Exception as e:
        print(f"[Task-Chat] Notification failed: {e}")
    
    return {
        "id": task_id,
        "message": "Task created successfully",
        "assigned_to_id": task.assigned_to_id
    }

@router.get("/{task_id}")
async def get_task(
    task_id: str,
    db: Session = Depends(get_rh_db)
):
    """Get single task by ID"""
    result = db.execute(text("""
        SELECT 
            t.id, t.order_id, t.order_number, t.damage_id, t.title, t.description,
            t.task_type, t.status, t.priority, t.assigned_to, t.due_date,
            t.completed_at, t.created_by, t.created_at, t.updated_at,
            t.assigned_to_id, t.created_by_id,
            u.firstname as assignee_firstname, u.lastname as assignee_lastname
        FROM tasks t
        LEFT JOIN users u ON t.assigned_to_id = u.user_id
        WHERE t.id = :task_id
    """), {"task_id": task_id})
    
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Task not found")
    
    assignee_name = None
    if len(row) > 17 and (row[17] or row[18]):
        assignee_name = f"{row[17] or ''} {row[18] or ''}".strip()
    elif row[9]:
        assignee_name = row[9]
    
    return {
        "id": row[0],
        "order_id": row[1],
        "order_number": row[2],
        "damage_id": row[3],
        "title": row[4],
        "description": row[5],
        "task_type": row[6],
        "status": row[7],
        "priority": row[8],
        "assigned_to": assignee_name,
        "assigned_to_id": row[15] if len(row) > 15 else None,
        "assignee_name": assignee_name,
        "due_date": row[10].isoformat() if row[10] else None,
        "completed_at": row[11].isoformat() if row[11] else None,
        "created_by": row[12],
        "created_by_id": row[16] if len(row) > 16 else None,
        "created_at": row[13].isoformat() if row[13] else None,
        "updated_at": row[14].isoformat() if row[14] else None,
        "damage_case_number": None
    }

@router.put("/{task_id}")
async def update_task(
    task_id: str,
    task: TaskUpdate,
    db: Session = Depends(get_rh_db)
):
    """
    Update task
    ✅ UPDATED: Підтримка assigned_to_id
    """
    # Build dynamic update
    set_clauses = []
    params = {"task_id": task_id}
    
    if task.title is not None:
        set_clauses.append("title = :title")
        params["title"] = task.title
    if task.description is not None:
        set_clauses.append("description = :description")
        params["description"] = task.description
    if task.task_type is not None:
        set_clauses.append("task_type = :task_type")
        params["task_type"] = task.task_type
    if task.status is not None:
        set_clauses.append("status = :status")
        params["status"] = task.status
        # Якщо статус done - встановити completed_at
        if task.status == "done":
            set_clauses.append("completed_at = NOW()")
    if task.priority is not None:
        set_clauses.append("priority = :priority")
        params["priority"] = task.priority
    if task.assigned_to_id is not None:
        set_clauses.append("assigned_to_id = :assigned_to_id")
        params["assigned_to_id"] = task.assigned_to_id
    if task.assigned_to is not None:
        set_clauses.append("assigned_to = :assigned_to")
        params["assigned_to"] = task.assigned_to
    if task.due_date is not None:
        set_clauses.append("due_date = :due_date")
        params["due_date"] = task.due_date
    if task.completed_at is not None:
        set_clauses.append("completed_at = :completed_at")
        params["completed_at"] = task.completed_at
    
    if not set_clauses:
        raise HTTPException(status_code=400, detail="No fields to update")
    
    set_clauses.append("updated_at = NOW()")
    
    sql = f"UPDATE tasks SET {', '.join(set_clauses)} WHERE id = :task_id"
    db.execute(text(sql), params)
    db.commit()
    
    # === Task-Chat Integration: notify status change ===
    if task.status is not None:
        try:
            from routes.team_chat import notify_task_status_change
            # Get user_id from authorization header if available
            notify_task_status_change(db=db, user_id=1, task_id=task_id, new_status=task.status)
        except Exception as e:
            print(f"[Task-Chat] Status notification failed: {e}")
    
    # Return updated task
    return await get_task(task_id, db)

@router.delete("/{task_id}")
async def delete_task(
    task_id: str,
    db: Session = Depends(get_rh_db)
):
    """Delete task"""
    result = db.execute(text("SELECT id FROM tasks WHERE id = :task_id"), {"task_id": task_id})
    if not result.fetchone():
        raise HTTPException(status_code=404, detail="Task not found")
    
    db.execute(text("DELETE FROM tasks WHERE id = :task_id"), {"task_id": task_id})
    db.commit()
    
    return {"message": "Task deleted successfully", "id": task_id}

# ============================================================
# STATISTICS ENDPOINT
# ============================================================

@router.get("/stats/by-user")
async def get_tasks_stats_by_user(db: Session = Depends(get_rh_db)):
    """
    Статистика завдань по користувачах
    """
    result = db.execute(text("""
        SELECT 
            u.user_id,
            CONCAT(u.firstname, ' ', u.lastname) as full_name,
            u.role,
            COUNT(t.id) as total_tasks,
            SUM(CASE WHEN t.status = 'todo' THEN 1 ELSE 0 END) as todo_count,
            SUM(CASE WHEN t.status = 'in_progress' THEN 1 ELSE 0 END) as in_progress_count,
            SUM(CASE WHEN t.status = 'done' THEN 1 ELSE 0 END) as done_count
        FROM users u
        LEFT JOIN tasks t ON u.user_id = t.assigned_to_id
        WHERE u.is_active = 1
        GROUP BY u.user_id
        ORDER BY total_tasks DESC
    """))
    
    stats = []
    for row in result:
        stats.append({
            "user_id": row[0],
            "full_name": row[1],
            "role": row[2],
            "total_tasks": row[3] or 0,
            "todo": row[4] or 0,
            "in_progress": row[5] or 0,
            "done": row[6] or 0
        })
    
    return stats
