"""
CallBell Webhooks Handler
Приймає події від CallBell в реальному часі
"""
from fastapi import APIRouter, Request, HTTPException, Header
from typing import Optional
import hashlib
import hmac
import json
import logging

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])
logger = logging.getLogger(__name__)

# Webhook secret для верифікації (отримаєте від CallBell)
WEBHOOK_SECRET = "your_webhook_secret_here"  # Треба отримати з CallBell dashboard


def verify_webhook_signature(payload: bytes, signature: str) -> bool:
    """
    Перевірка підпису webhook для безпеки
    CallBell надсилає HMAC-SHA256 підпис в заголовку
    """
    if not WEBHOOK_SECRET or not signature:
        logger.warning("Webhook secret or signature missing")
        return False
    
    expected_signature = hmac.new(
        WEBHOOK_SECRET.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(signature, expected_signature)


@router.post("/callbell")
async def handle_callbell_webhook(
    request: Request,
    x_callbell_signature: Optional[str] = Header(None)
):
    """
    Головний endpoint для прийому всіх CallBell webhooks
    
    CallBell надсилає POST запит з JSON body:
    {
        "event": "message.created",
        "data": {...}
    }
    """
    try:
        # Отримати raw body для верифікації підпису
        body = await request.body()
        
        # Верифікація підпису (рекомендується для production)
        # if not verify_webhook_signature(body, x_callbell_signature or ""):
        #     logger.error("Invalid webhook signature")
        #     raise HTTPException(status_code=401, detail="Invalid signature")
        
        # Парсинг JSON
        payload = json.loads(body)
        event_type = payload.get("event")
        data = payload.get("data", {})
        
        logger.info(f"📩 Webhook received: {event_type}")
        
        # Обробка різних типів подій
        if event_type == "message.created":
            await handle_message_created(data)
        
        elif event_type == "message.updated":
            await handle_message_updated(data)
        
        elif event_type == "contact.created":
            await handle_contact_created(data)
        
        elif event_type == "contact.updated":
            await handle_contact_updated(data)
        
        else:
            logger.warning(f"Unknown event type: {event_type}")
        
        # Завжди повертаємо 200 OK щоб CallBell знав що отримали
        return {"status": "success", "event": event_type}
    
    except json.JSONDecodeError:
        logger.error("Invalid JSON in webhook")
        raise HTTPException(status_code=400, detail="Invalid JSON")
    
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal error")


async def handle_message_created(data: dict):
    """
    Обробка нового повідомлення від клієнта
    
    Приклад data:
    {
        "message": {
            "uuid": "msg_123",
            "content": {"text": "Коли моє замовлення буде готове?"},
            "direction": "incoming",
            "status": "received",
            "createdAt": "2025-11-26T12:00:00Z"
        },
        "contact": {
            "uuid": "contact_456",
            "name": "Марія Іваненко",
            "phoneNumber": "+380123456789"
        }
    }
    """
    message = data.get("message", {})
    contact = data.get("contact", {})
    
    message_text = message.get("content", {}).get("text", "")
    contact_name = contact.get("name", "Unknown")
    contact_phone = contact.get("phoneNumber", "")
    
    logger.info(f"💬 Нове повідомлення від {contact_name} ({contact_phone}): {message_text}")
    
    # ТУТ МОЖНА ДОДАТИ ВАШУ ЛОГІКУ:
    # 1. Зберегти повідомлення в БД
    # 2. Відправити нотифікацію менеджеру
    # 3. Автоматично відповісти якщо це FAQ
    # 4. Оновити статус замовлення
    
    # Приклад: автоматична відповідь на певні питання
    if "замовлення" in message_text.lower() and "статус" in message_text.lower():
        # Можна автоматично відповісти або створити задачу для менеджера
        logger.info(f"🤖 Виявлено питання про статус замовлення")
        # await send_auto_reply(contact_phone, "Перевіряємо статус вашого замовлення...")


async def handle_message_updated(data: dict):
    """
    Обробка зміни статусу повідомлення
    
    Статуси: sent, delivered, read, failed
    """
    message = data.get("message", {})
    message_uuid = message.get("uuid")
    status = message.get("status")
    
    logger.info(f"📬 Статус повідомлення {message_uuid}: {status}")
    
    # Можна оновити статус в БД
    # await update_message_status_in_db(message_uuid, status)


async def handle_contact_created(data: dict):
    """
    Обробка створення нового контакту
    """
    contact = data.get("contact", {})
    contact_name = contact.get("name")
    contact_phone = contact.get("phoneNumber")
    
    logger.info(f"👤 Новий контакт: {contact_name} ({contact_phone})")
    
    # Можна синхронізувати з вашою БД клієнтів


async def handle_contact_updated(data: dict):
    """
    Обробка оновлення контакту
    """
    contact = data.get("contact", {})
    contact_uuid = contact.get("uuid")
    
    logger.info(f"🔄 Контакт оновлено: {contact_uuid}")
    
    # Можна синхронізувати зміни з вашою БД


# Тестовий endpoint для перевірки що webhook працює
@router.get("/callbell/test")
async def test_webhook():
    """Тестовий endpoint для перевірки"""
    return {
        "status": "ok",
        "message": "Webhook endpoint is ready",
        "url": "POST /api/webhooks/callbell"
    }
