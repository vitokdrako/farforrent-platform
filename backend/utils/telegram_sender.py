"""
Telegram sender utility for sending order confirmations
"""
import os
import requests
from typing import Optional, Dict, Any


def send_order_confirmation_telegram(
    chat_id: str,
    order_data: Dict[str, Any]
) -> bool:
    """
    Відправити повідомлення про замовлення в Telegram
    
    Args:
        chat_id: Telegram chat ID клієнта
        order_data: Дані замовлення
        
    Returns:
        bool: True якщо успішно
    """
    bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
    
    if not bot_token:
        print("[TELEGRAM] ⚠️ BOT_TOKEN не налаштований")
        return False
    
    if not chat_id:
        print("[TELEGRAM] ⚠️ chat_id не вказаний")
        return False
    
    try:
        # Формуємо повідомлення
        message = f"""
🎉 <b>Замовлення підтверджено!</b>

📋 Номер: <b>#{order_data.get('order_number')}</b>
👤 Клієнт: {order_data.get('client_name')}

📅 Дата видачі: <b>{order_data.get('issue_date')}</b>
📅 Дата повернення: <b>{order_data.get('return_date')}</b>
⏱ Кількість діб: <b>{order_data.get('rental_days')}</b>

📦 <b>Товари:</b>
"""
        
        # Додати список товарів (макс 5)
        items = order_data.get('items', [])
        for i, item in enumerate(items[:5]):
            message += f"{i+1}. {item.get('name')} x{item.get('quantity')}\n"
        
        if len(items) > 5:
            message += f"... і ще {len(items) - 5} товарів\n"
        
        message += f"""
💰 <b>Вартість оренди:</b> {order_data.get('total_rental')} грн
🛡 <b>Застава:</b> {order_data.get('total_deposit')} грн
💵 <b>Передоплата (50%):</b> {order_data.get('prepayment')} грн
"""
        
        # Додати зміни якщо є
        changes = order_data.get('changes', [])
        if changes:
            message += "\n⚠️ <b>Внесені зміни:</b>\n"
            for change in changes[:3]:
                message += f"• {change}\n"
        
        message += "\n📧 Детальний лист відправлено на email"
        
        # Інлайн кнопка "Підтвердити"
        keyboard = {
            "inline_keyboard": [
                [
                    {
                        "text": "✅ Підтвердити замовлення",
                        "callback_data": f"confirm_order_{order_data.get('order_id')}"
                    }
                ]
            ]
        }
        
        # Відправити через Telegram Bot API
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML",
            "reply_markup": keyboard
        }
        
        response = requests.post(url, json=payload, timeout=10)
        
        if response.status_code == 200:
            print(f"[TELEGRAM] ✅ Повідомлення відправлено в chat_id={chat_id}")
            return True
        else:
            print(f"[TELEGRAM] ❌ Помилка: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"[TELEGRAM] ❌ Exception: {str(e)}")
        return False
