"""
Web Push notifications service for Event Tool clients.
- Sends browser push via pywebpush + VAPID auth.
- Stores subscriptions in `push_subscriptions` table.
- Trigger on order status change, document signed, etc.
"""
import os
import json
import base64
import logging
from typing import Optional
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger("push")

VAPID_PUBLIC_KEY = os.environ.get("VAPID_PUBLIC_KEY", "")
VAPID_SUBJECT = os.environ.get("VAPID_SUBJECT", "mailto:info@farforrent.com.ua")
_priv_b64 = os.environ.get("VAPID_PRIVATE_PEM_BASE64", "")
VAPID_PRIVATE_PEM = base64.b64decode(_priv_b64).decode() if _priv_b64 else ""


def is_configured() -> bool:
    return bool(VAPID_PUBLIC_KEY and VAPID_PRIVATE_PEM)


def send_to_customer(db: Session, customer_id: int, title: str, body: str,
                     url: str = "/profile", icon: Optional[str] = None,
                     tag: Optional[str] = None) -> dict:
    """
    Send push to all subscriptions of a customer. Returns {sent, failed, removed}.
    Removes 410 (Gone) subscriptions automatically.
    """
    if not is_configured():
        logger.warning("VAPID keys not configured — push skipped")
        return {"sent": 0, "failed": 0, "removed": 0, "skipped": True}

    try:
        from pywebpush import webpush, WebPushException
    except ImportError:
        logger.error("pywebpush not installed")
        return {"sent": 0, "failed": 0, "removed": 0, "error": "library missing"}

    rows = db.execute(text("""
        SELECT id, endpoint, p256dh, auth_secret
        FROM push_subscriptions WHERE customer_id = :cid
    """), {"cid": customer_id}).fetchall()

    if not rows:
        return {"sent": 0, "failed": 0, "removed": 0}

    payload = json.dumps({
        "title": title, "body": body, "url": url,
        "icon": icon or "/favicon.ico", "tag": tag or "rentalhub",
    }, ensure_ascii=False)

    sent = failed = removed = 0
    removed_ids = []
    for row in rows:
        sub = {"endpoint": row[1], "keys": {"p256dh": row[2], "auth": row[3]}}
        try:
            webpush(
                subscription_info=sub,
                data=payload,
                vapid_private_key=VAPID_PRIVATE_PEM,
                vapid_claims={"sub": VAPID_SUBJECT},
                ttl=24 * 3600,
            )
            sent += 1
        except WebPushException as e:
            status = getattr(e.response, "status_code", None)
            if status in (404, 410):
                removed_ids.append(row[0])
                removed += 1
            else:
                logger.warning(f"push to {row[1][:60]} failed: {status} {e}")
                failed += 1
        except Exception as e:
            logger.warning(f"push unexpected error: {e}")
            failed += 1

    if removed_ids:
        db.execute(text("DELETE FROM push_subscriptions WHERE id IN :ids").bindparams(),
                   {"ids": tuple(removed_ids)})
        db.commit()

    if sent:
        db.execute(text("""
            UPDATE push_subscriptions SET last_used_at = NOW()
            WHERE customer_id = :cid
        """), {"cid": customer_id})
        db.commit()

    return {"sent": sent, "failed": failed, "removed": removed}


def notify_order_status_change(db: Session, order_id: int, new_status: str,
                                old_status: Optional[str] = None) -> dict:
    """Send push when order status changes."""
    if not is_configured():
        return {"skipped": True}
    row = db.execute(text("""
        SELECT o.order_number, o.event_tool_customer_id, c.firstname
        FROM orders o
        LEFT JOIN event_customers c ON c.customer_id = o.event_tool_customer_id
        WHERE o.order_id = :oid
    """), {"oid": order_id}).fetchone()
    if not row or not row[1]:
        return {"skipped": True, "reason": "no customer linked"}

    status_labels = {
        "draft": "Чернетка", "awaiting_customer": "Очікує підтвердження",
        "confirmed": "Підтверджено", "processing": "В обробці",
        "issued": "Видано", "returned": "Повернено",
        "completed": "Завершено", "cancelled": "Скасовано",
    }
    label = status_labels.get(new_status, new_status)
    title = f"Замовлення {row[0]}"
    body = f"Статус оновлено: {label}"
    return send_to_customer(db, row[1], title, body, url="/profile",
                            tag=f"order-{order_id}-status")


def notify_document_ready(db: Session, order_id: int, doc_type: str,
                          doc_number: Optional[str] = None) -> dict:
    """Send push when a new document is ready to sign/view."""
    if not is_configured():
        return {"skipped": True}
    row = db.execute(text("""
        SELECT o.order_number, o.event_tool_customer_id
        FROM orders o WHERE o.order_id = :oid
    """), {"oid": order_id}).fetchone()
    if not row or not row[1]:
        return {"skipped": True}

    doc_labels = {
        "rental_agreement": "Договір оренди", "invoice_legal": "Рахунок",
        "estimate": "Кошторис", "return_act": "Акт повернення",
        "issue_act": "Акт видачі", "service_act": "Акт виконаних робіт",
    }
    label = doc_labels.get(doc_type, "Документ")
    title = f"📄 Новий документ {label}"
    body = f"Замовлення {row[0]} — натисніть, щоб переглянути та підписати"
    return send_to_customer(db, row[1], title, body, url="/profile",
                            tag=f"order-{order_id}-doc-{doc_type}")
