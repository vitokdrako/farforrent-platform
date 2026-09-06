"""Нотифікації в командний чат про події задач.

Причина існування: `routes/tasks.py` викликав ці функції з
`routes/team_chat.py` (route -> route). Тепер обидва модулі залежать
від цього сервісу.

Код перенесено 1:1. Обидві функції залишаються «best-effort»: якщо
загального каналу або початкового повідомлення задачі немає, вони тихо
повертають `None` і не кидають виняток — створення чи оновлення задачі
не має падати через недоступну нотифікацію.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

#: Людські підписи пріоритетів задачі.
_PRIORITY_LABELS = {"high": "Високий", "medium": "Середній", "low": "Низький"}

#: Людські підписи статусів задачі.
_STATUS_LABELS = {"todo": "До виконання", "in_progress": "В роботі", "done": "Виконано"}


def notify_task_in_chat(
    db: Session,
    user_id: int,
    user_name: str,
    task_title: str,
    task_id: str,
    assignee_name: str = "",
    priority: str = "",
    due_date: str = "",
) -> Optional[int]:
    """Створити повідомлення в каналі «Загальний» при створенні задачі.

    Returns:
        Id створеного повідомлення або `None`, якщо загального каналу немає.
    """
    general = db.execute(
        text("SELECT id FROM chat_channels WHERE type = 'general' LIMIT 1")
    ).fetchone()
    if not general:
        return None

    parts = [f"Нова задача: {task_title}"]
    if assignee_name:
        parts.append(f"Виконавець: {assignee_name}")
    if priority:
        parts.append(f"Пріоритет: {_PRIORITY_LABELS.get(priority, priority)}")
    if due_date:
        parts.append(f"Дедлайн: {due_date[:10]}")

    msg_text = "\n".join(parts)

    db.execute(text("""
        INSERT INTO chat_messages (channel_id, user_id, message, task_id)
        VALUES (:ch_id, :uid, :msg, :tid)
    """), {"ch_id": general[0], "uid": user_id, "msg": msg_text, "tid": task_id})

    msg_id = db.execute(text("SELECT LAST_INSERT_ID()")).scalar()
    db.execute(
        text("UPDATE chat_channels SET updated_at = NOW() WHERE id = :ch_id"),
        {"ch_id": general[0]},
    )
    db.commit()
    return msg_id


def notify_task_status_change(
    db: Session,
    user_id: int,
    task_id: str,
    new_status: str,
) -> None:
    """Додати відповідь у тред задачі при зміні статусу.

    Тихо виходить, якщо початкового повідомлення задачі в чаті немає.
    """
    orig = db.execute(text("""
        SELECT id, channel_id FROM chat_messages WHERE task_id = :tid AND reply_to IS NULL LIMIT 1
    """), {"tid": task_id}).fetchone()
    if not orig:
        return

    status_text = _STATUS_LABELS.get(new_status, new_status)

    # Ім'я автора зміни лишається в БД як user_id; вибірка збережена 1:1
    # з початкової реалізації, щоб не змінювати поведінку.
    u = db.execute(
        text("SELECT firstname, lastname FROM users WHERE user_id = :uid"),
        {"uid": user_id},
    ).fetchone()
    name = f"{u[0] or ''} {u[1] or ''}".strip() if u else "System"  # noqa: F841

    msg_text = f"Статус змінено: {status_text}"

    db.execute(text("""
        INSERT INTO chat_messages (channel_id, user_id, message, reply_to, task_id)
        VALUES (:ch_id, :uid, :msg, :parent, :tid)
    """), {"ch_id": orig[1], "uid": user_id, "msg": msg_text, "parent": orig[0], "tid": task_id})

    db.execute(
        text("UPDATE chat_channels SET updated_at = NOW() WHERE id = :ch_id"),
        {"ch_id": orig[1]},
    )
    db.commit()


__all__ = ["notify_task_in_chat", "notify_task_status_change"]