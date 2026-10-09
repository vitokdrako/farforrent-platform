"""
Team Chat API — внутрішній месенджер для команди (MySQL)
Канали (загальний, тематичні) + особисті повідомлення + threads + фото
"""
from fastapi import APIRouter, Depends, HTTPException, Header, UploadFile, File, Form
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import text
import os, uuid, shutil

from database_rentalhub import get_rh_db
from utils.user_tracking_helper import get_current_user_dependency

router = APIRouter(prefix="/api/chat", tags=["chat"])

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads", "chat")
os.makedirs(UPLOAD_DIR, exist_ok=True)


def require_auth(current_user: dict = Depends(get_current_user_dependency)):
    uid = current_user.get("user_id") or current_user.get("id")
    if not uid or current_user.get("name") == "System":
        raise HTTPException(status_code=401, detail="Авторизуйтесь")
    return current_user


# === Models ===

class ChannelCreate(BaseModel):
    name: str
    description: Optional[str] = ""
    type: str = "topic"


class MessageCreate(BaseModel):
    message: str
    reply_to: Optional[int] = None


# === Channels ===

@router.get("/channels")
async def list_channels(
    user: dict = Depends(require_auth),
    db: Session = Depends(get_rh_db)
):
    uid = user.get("user_id") or user.get("id")

    # All public channels + DMs where user is a member
    rows = db.execute(text("""
        SELECT DISTINCT c.id, c.name, c.type, c.description, c.pinned, c.created_at, c.updated_at
        FROM chat_channels c
        LEFT JOIN chat_channel_members m ON c.id = m.channel_id
        WHERE c.type IN ('general', 'topic')
           OR (c.type = 'dm' AND m.user_id = :uid)
        ORDER BY c.pinned DESC, c.updated_at DESC
    """), {"uid": uid}).fetchall()

    result = []
    for r in rows:
        ch_id = r[0]

        # Unread count
        read_row = db.execute(text("""
            SELECT last_read_at FROM chat_read_status
            WHERE user_id = :uid AND channel_id = :ch_id
        """), {"uid": uid, "ch_id": ch_id}).fetchone()
        last_read = read_row[0] if read_row else "2000-01-01"

        unread = db.execute(text("""
            SELECT COUNT(*) FROM chat_messages
            WHERE channel_id = :ch_id AND created_at > :lr AND user_id != :uid
        """), {"ch_id": ch_id, "lr": last_read, "uid": uid}).scalar()

        # Last message
        last_msg = db.execute(text("""
            SELECT cm.message, u.firstname, u.lastname, cm.created_at
            FROM chat_messages cm
            JOIN users u ON cm.user_id = u.user_id
            WHERE cm.channel_id = :ch_id
            ORDER BY cm.created_at DESC LIMIT 1
        """), {"ch_id": ch_id}).fetchone()

        # Members for DM display name
        members = []
        if r[2] == "dm":
            mem_rows = db.execute(text("""
                SELECT m.user_id, u.firstname, u.lastname
                FROM chat_channel_members m
                JOIN users u ON m.user_id = u.user_id
                WHERE m.channel_id = :ch_id
            """), {"ch_id": ch_id}).fetchall()
            members = [{"id": mr[0], "name": f"{mr[1] or ''} {mr[2] or ''}".strip()} for mr in mem_rows]

        result.append({
            "id": ch_id,
            "name": r[1],
            "type": r[2],
            "description": r[3] or "",
            "pinned": bool(r[4]),
            "members": members,
            "unread": unread or 0,
            "last_message": {
                "text": last_msg[0][:60] if last_msg else None,
                "user_name": f"{last_msg[1] or ''} {last_msg[2] or ''}".strip() if last_msg else None,
                "created_at": last_msg[3].isoformat() if last_msg else None,
            } if last_msg else None,
            "updated_at": r[6].isoformat() if r[6] else r[5].isoformat() if r[5] else None,
        })

    return result


@router.post("/channels")
async def create_channel(
    data: ChannelCreate,
    user: dict = Depends(require_auth),
    db: Session = Depends(get_rh_db)
):
    uid = user.get("user_id") or user.get("id")

    if data.type == "general":
        existing = db.execute(text("SELECT id FROM chat_channels WHERE type = 'general'")).fetchone()
        if existing:
            raise HTTPException(400, "Загальний канал вже існує")

    db.execute(text("""
        INSERT INTO chat_channels (name, type, description, pinned, created_by)
        VALUES (:name, :type, :desc, :pinned, :uid)
    """), {
        "name": data.name, "type": data.type,
        "desc": data.description or "",
        "pinned": 1 if data.type == "general" else 0,
        "uid": uid,
    })
    
    # Get the last insert ID BEFORE commit to ensure we're on same connection
    ch_id = db.execute(text("SELECT LAST_INSERT_ID()")).scalar()
    db.commit()

    ch = db.execute(text("SELECT id, name, type, description, pinned, created_at FROM chat_channels WHERE id = :id"), {"id": ch_id}).fetchone()
    return {
        "id": ch[0], "name": ch[1], "type": ch[2],
        "description": ch[3], "pinned": bool(ch[4]),
        "created_at": ch[5].isoformat() if ch[5] else None,
    }


@router.delete("/channels/{channel_id}")
async def delete_channel(
    channel_id: int,
    user: dict = Depends(require_auth),
    db: Session = Depends(get_rh_db)
):
    ch = db.execute(text("SELECT type FROM chat_channels WHERE id = :id"), {"id": channel_id}).fetchone()
    if not ch:
        raise HTTPException(404, "Канал не знайдено")
    if ch[0] == "general":
        raise HTTPException(400, "Не можна видалити загальний канал")
    db.execute(text("DELETE FROM chat_channels WHERE id = :id"), {"id": channel_id})
    db.commit()
    return {"message": "Канал видалено"}


# === DMs ===

@router.post("/dm/{target_user_id}")
async def get_or_create_dm(
    target_user_id: int,
    user: dict = Depends(require_auth),
    db: Session = Depends(get_rh_db)
):
    uid = user.get("user_id") or user.get("id")
    if uid == target_user_id:
        raise HTTPException(400, "Не можна створити чат з собою")

    # Check if DM already exists between these two users
    existing = db.execute(text("""
        SELECT c.id, c.name FROM chat_channels c
        JOIN chat_channel_members m1 ON c.id = m1.channel_id AND m1.user_id = :uid
        JOIN chat_channel_members m2 ON c.id = m2.channel_id AND m2.user_id = :tid
        WHERE c.type = 'dm'
    """), {"uid": uid, "tid": target_user_id}).fetchone()

    if existing:
        return {"id": existing[0], "name": existing[1], "type": "dm"}

    # Get target user name
    target = db.execute(text("SELECT firstname, lastname FROM users WHERE user_id = :id"), {"id": target_user_id}).fetchone()
    target_name = f"{target[0] or ''} {target[1] or ''}".strip() if target else f"User #{target_user_id}"
    my_name = user.get("name", "User")

    # Create DM channel
    db.execute(text("""
        INSERT INTO chat_channels (name, type, description, pinned, created_by)
        VALUES (:name, 'dm', '', 0, :uid)
    """), {"name": f"{my_name} & {target_name}", "uid": uid})

    ch_id = db.execute(text("SELECT LAST_INSERT_ID()")).scalar()

    # Add both users as members
    db.execute(text("INSERT INTO chat_channel_members (channel_id, user_id) VALUES (:ch, :u1), (:ch, :u2)"),
               {"ch": ch_id, "u1": uid, "u2": target_user_id})
    db.commit()

    return {"id": ch_id, "name": f"{my_name} & {target_name}", "type": "dm"}


# === Messages ===

@router.get("/channels/{channel_id}/messages")
async def get_messages(
    channel_id: int,
    limit: int = 50,
    before_id: Optional[int] = None,
    user: dict = Depends(require_auth),
    db: Session = Depends(get_rh_db)
):
    uid = user.get("user_id") or user.get("id")

    params = {"ch_id": channel_id, "limit": limit}
    where = "cm.channel_id = :ch_id AND cm.reply_to IS NULL"
    if before_id:
        where += " AND cm.id < :before_id"
        params["before_id"] = before_id

    rows = db.execute(text(f"""
        SELECT cm.id, cm.channel_id, cm.user_id, u.firstname, u.lastname, u.role,
               cm.message, cm.reply_to, cm.created_at,
               (SELECT COUNT(*) FROM chat_messages r WHERE r.reply_to = cm.id) as thread_count,
               cm.attachment_url, cm.attachment_type, cm.is_closed, cm.task_id
        FROM chat_messages cm
        JOIN users u ON cm.user_id = u.user_id
        WHERE {where}
        ORDER BY cm.created_at DESC
        LIMIT :limit
    """), params).fetchall()

    rows = list(reversed(rows))

    # Mark as read
    db.execute(text("""
        INSERT INTO chat_read_status (user_id, channel_id, last_read_at)
        VALUES (:uid, :ch_id, NOW())
        ON DUPLICATE KEY UPDATE last_read_at = NOW()
    """), {"uid": uid, "ch_id": channel_id})
    db.commit()

    return [{
        "id": r[0], "channel_id": r[1], "user_id": r[2],
        "user_name": f"{r[3] or ''} {r[4] or ''}".strip(),
        "user_role": r[5] or "",
        "message": r[6], "reply_to": r[7],
        "thread_count": r[9],
        "attachment_url": r[10], "attachment_type": r[11],
        "is_closed": bool(r[12]), "task_id": r[13],
        "created_at": r[8].isoformat() if r[8] else None,
    } for r in rows]


@router.get("/messages/{message_id}/thread")
async def get_thread(
    message_id: int,
    user: dict = Depends(require_auth),
    db: Session = Depends(get_rh_db)
):
    # Parent message
    parent = db.execute(text("""
        SELECT cm.id, cm.channel_id, cm.user_id, u.firstname, u.lastname, u.role,
               cm.message, cm.reply_to, cm.created_at,
               cm.attachment_url, cm.attachment_type, cm.is_closed, cm.task_id
        FROM chat_messages cm
        JOIN users u ON cm.user_id = u.user_id
        WHERE cm.id = :mid
    """), {"mid": message_id}).fetchone()

    if not parent:
        raise HTTPException(404, "Повідомлення не знайдено")

    # Thread replies
    replies = db.execute(text("""
        SELECT cm.id, cm.channel_id, cm.user_id, u.firstname, u.lastname, u.role,
               cm.message, cm.reply_to, cm.created_at,
               cm.attachment_url, cm.attachment_type, cm.is_closed, cm.task_id
        FROM chat_messages cm
        JOIN users u ON cm.user_id = u.user_id
        WHERE cm.reply_to = :mid
        ORDER BY cm.created_at ASC
    """), {"mid": message_id}).fetchall()

    all_msgs = [parent] + list(replies)
    return [{
        "id": r[0], "channel_id": r[1], "user_id": r[2],
        "user_name": f"{r[3] or ''} {r[4] or ''}".strip(),
        "user_role": r[5] or "", "message": r[6],
        "reply_to": r[7], "is_parent": r[0] == message_id,
        "attachment_url": r[9], "attachment_type": r[10],
        "is_closed": bool(r[11]), "task_id": r[12],
        "created_at": r[8].isoformat() if r[8] else None,
    } for r in all_msgs]


@router.post("/channels/{channel_id}/messages")
async def send_message(
    channel_id: int,
    data: MessageCreate,
    user: dict = Depends(require_auth),
    db: Session = Depends(get_rh_db)
):
    uid = user.get("user_id") or user.get("id")
    if not data.message.strip():
        raise HTTPException(400, "Повідомлення порожнє")

    ch = db.execute(text("SELECT id FROM chat_channels WHERE id = :id"), {"id": channel_id}).fetchone()
    if not ch:
        raise HTTPException(404, "Канал не знайдено")

    # Check if replying to a closed thread
    if data.reply_to:
        parent = db.execute(text("SELECT is_closed FROM chat_messages WHERE id = :id"), {"id": data.reply_to}).fetchone()
        if parent and parent[0]:
            raise HTTPException(400, "Цей тред закрито")

    db.execute(text("""
        INSERT INTO chat_messages (channel_id, user_id, message, reply_to)
        VALUES (:ch_id, :uid, :msg, :reply)
    """), {"ch_id": channel_id, "uid": uid, "msg": data.message.strip(), "reply": data.reply_to})

    msg_id = db.execute(text("SELECT LAST_INSERT_ID()")).scalar()

    db.execute(text("UPDATE chat_channels SET updated_at = NOW() WHERE id = :ch_id"), {"ch_id": channel_id})
    db.execute(text("""
        INSERT INTO chat_read_status (user_id, channel_id, last_read_at)
        VALUES (:uid, :ch_id, NOW())
        ON DUPLICATE KEY UPDATE last_read_at = NOW()
    """), {"uid": uid, "ch_id": channel_id})
    db.commit()

    return {
        "id": msg_id, "channel_id": channel_id, "user_id": uid,
        "user_name": user.get("name", ""),
        "user_role": user.get("role", ""),
        "message": data.message.strip(),
        "reply_to": data.reply_to,
        "created_at": None,
    }


# === Upload Photo ===

@router.post("/upload")
async def upload_chat_file(
    channel_id: int = Form(...),
    message: str = Form(""),
    reply_to: Optional[int] = Form(None),
    file: UploadFile = File(...),
    user: dict = Depends(require_auth),
    db: Session = Depends(get_rh_db)
):
    uid = user.get("user_id") or user.get("id")

    # Check closed thread
    if reply_to:
        parent = db.execute(text("SELECT is_closed FROM chat_messages WHERE id = :id"), {"id": reply_to}).fetchone()
        if parent and parent[0]:
            raise HTTPException(400, "Цей тред закрито")

    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.heic'):
        raise HTTPException(400, "Підтримуються лише зображення (jpg, png, gif, webp)")

    filename = f"{uuid.uuid4().hex}{ext}"
    filepath = os.path.join(UPLOAD_DIR, filename)
    with open(filepath, "wb") as f:
        shutil.copyfileobj(file.file, f)

    attachment_url = f"/api/uploads/chat/{filename}"
    attachment_type = "image"

    db.execute(text("""
        INSERT INTO chat_messages (channel_id, user_id, message, reply_to, attachment_url, attachment_type)
        VALUES (:ch_id, :uid, :msg, :reply, :url, :atype)
    """), {
        "ch_id": channel_id, "uid": uid, "msg": message.strip() or "",
        "reply": reply_to, "url": attachment_url, "atype": attachment_type,
    })

    msg_id = db.execute(text("SELECT LAST_INSERT_ID()")).scalar()
    db.execute(text("UPDATE chat_channels SET updated_at = NOW() WHERE id = :ch_id"), {"ch_id": channel_id})
    db.execute(text("""
        INSERT INTO chat_read_status (user_id, channel_id, last_read_at)
        VALUES (:uid, :ch_id, NOW())
        ON DUPLICATE KEY UPDATE last_read_at = NOW()
    """), {"uid": uid, "ch_id": channel_id})
    db.commit()

    return {
        "id": msg_id, "channel_id": channel_id, "user_id": uid,
        "user_name": user.get("name", ""),
        "message": message.strip(), "reply_to": reply_to,
        "attachment_url": attachment_url, "attachment_type": attachment_type,
    }


# === Close / Reopen Thread ===

@router.put("/messages/{message_id}/close")
async def close_thread(
    message_id: int,
    user: dict = Depends(require_auth),
    db: Session = Depends(get_rh_db)
):
    msg = db.execute(text("SELECT id, reply_to FROM chat_messages WHERE id = :id"), {"id": message_id}).fetchone()
    if not msg:
        raise HTTPException(404, "Повідомлення не знайдено")
    if msg[1] is not None:
        raise HTTPException(400, "Закрити можна лише кореневе повідомлення треду")
    db.execute(text("UPDATE chat_messages SET is_closed = 1 WHERE id = :id"), {"id": message_id})
    db.commit()
    return {"message": "Тред закрито", "is_closed": True}


@router.put("/messages/{message_id}/reopen")
async def reopen_thread(
    message_id: int,
    user: dict = Depends(require_auth),
    db: Session = Depends(get_rh_db)
):
    db.execute(text("UPDATE chat_messages SET is_closed = 0 WHERE id = :id"), {"id": message_id})
    db.commit()
    return {"message": "Тред відкрито", "is_closed": False}


# === Task-Chat: send task notification to general channel ===

def notify_task_in_chat(db: Session, user_id: int, user_name: str, task_title: str, task_id: str, assignee_name: str = "", priority: str = "", due_date: str = ""):
    """Create message in Загальний channel when task is created"""
    general = db.execute(text("SELECT id FROM chat_channels WHERE type = 'general' LIMIT 1")).fetchone()
    if not general:
        return None

    parts = [f"Нова задача: {task_title}"]
    if assignee_name:
        parts.append(f"Виконавець: {assignee_name}")
    if priority:
        p_labels = {"high": "Високий", "medium": "Середній", "low": "Низький"}
        parts.append(f"Пріоритет: {p_labels.get(priority, priority)}")
    if due_date:
        parts.append(f"Дедлайн: {due_date[:10]}")

    msg_text = "\n".join(parts)

    db.execute(text("""
        INSERT INTO chat_messages (channel_id, user_id, message, task_id)
        VALUES (:ch_id, :uid, :msg, :tid)
    """), {"ch_id": general[0], "uid": user_id, "msg": msg_text, "tid": task_id})

    msg_id = db.execute(text("SELECT LAST_INSERT_ID()")).scalar()
    db.execute(text("UPDATE chat_channels SET updated_at = NOW() WHERE id = :ch_id"), {"ch_id": general[0]})
    db.commit()
    return msg_id


def notify_task_status_change(db: Session, user_id: int, task_id: str, new_status: str):
    """Add a thread reply to the task message when status changes"""
    # Find the original task message
    orig = db.execute(text("""
        SELECT id, channel_id FROM chat_messages WHERE task_id = :tid AND reply_to IS NULL LIMIT 1
    """), {"tid": task_id}).fetchone()
    if not orig:
        return

    status_labels = {"todo": "До виконання", "in_progress": "В роботі", "done": "Виконано"}
    status_text = status_labels.get(new_status, new_status)

    # Get user name
    u = db.execute(text("SELECT firstname, lastname FROM users WHERE user_id = :uid"), {"uid": user_id}).fetchone()
    name = f"{u[0] or ''} {u[1] or ''}".strip() if u else "System"

    msg_text = f"Статус змінено: {status_text}"

    db.execute(text("""
        INSERT INTO chat_messages (channel_id, user_id, message, reply_to, task_id)
        VALUES (:ch_id, :uid, :msg, :parent, :tid)
    """), {"ch_id": orig[1], "uid": user_id, "msg": msg_text, "parent": orig[0], "tid": task_id})

    db.execute(text("UPDATE chat_channels SET updated_at = NOW() WHERE id = :ch_id"), {"ch_id": orig[1]})
    db.commit()


# === Team Members ===

@router.get("/team")
async def get_team_members(
    user: dict = Depends(require_auth),
    db: Session = Depends(get_rh_db)
):
    rows = db.execute(text("""
        SELECT user_id, username, email, firstname, lastname, role, is_active, last_login
        FROM users WHERE is_active = 1
        ORDER BY firstname, lastname
    """)).fetchall()

    return [{
        "id": r[0], "username": r[1], "email": r[2],
        "name": f"{r[3] or ''} {r[4] or ''}".strip(),
        "role": r[5], "is_active": bool(r[6]),
        "last_login": r[7].isoformat() if r[7] else None,
    } for r in rows]


# === Unread Count ===

@router.get("/unread")
async def get_total_unread(
    user: dict = Depends(require_auth),
    db: Session = Depends(get_rh_db)
):
    uid = user.get("user_id") or user.get("id")

    total = db.execute(text("""
        SELECT COALESCE(SUM(unread), 0) FROM (
            SELECT COUNT(*) as unread
            FROM chat_channels c
            LEFT JOIN chat_channel_members m ON c.id = m.channel_id
            JOIN chat_messages cm ON cm.channel_id = c.id
            LEFT JOIN chat_read_status rs ON rs.user_id = :uid AND rs.channel_id = c.id
            WHERE (c.type IN ('general', 'topic') OR (c.type = 'dm' AND m.user_id = :uid))
              AND cm.user_id != :uid
              AND cm.created_at > COALESCE(rs.last_read_at, '2000-01-01')
        ) t
    """), {"uid": uid}).scalar()

    return {"unread": total or 0}


# === Init default channels ===

@router.post("/init")
async def init_default_channels(
    user: dict = Depends(require_auth),
    db: Session = Depends(get_rh_db)
):
    uid = user.get("user_id") or user.get("id")
    defaults = [
        ("Загальний", "general", "Загальний чат команди", 1),
        ("Склад", "topic", "Питання по складу та інвентарю", 0),
        ("Доставка", "topic", "Координація доставок", 0),
        ("Термінове", "topic", "Термінові питання", 0),
    ]
    created = []
    for name, ch_type, desc, pinned in defaults:
        exists = db.execute(text("SELECT id FROM chat_channels WHERE name = :n AND type = :t"),
                            {"n": name, "t": ch_type}).fetchone()
        if not exists:
            db.execute(text("""
                INSERT INTO chat_channels (name, type, description, pinned, created_by)
                VALUES (:n, :t, :d, :p, :uid)
            """), {"n": name, "t": ch_type, "d": desc, "p": pinned, "uid": uid})
            created.append(name)
    db.commit()
    return {"created": created, "message": f"Створено {len(created)} каналів" if created else "Канали вже існують"}
