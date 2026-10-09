"""
Email Service - Відправка email через SMTP
"""
import os
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import Optional, List
import logging

logger = logging.getLogger(__name__)

# SMTP Configuration from environment
SMTP_HOST = os.getenv("SMTP_HOST", "mail.adm.tools")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_USE_SSL = os.getenv("SMTP_USE_SSL", "True").lower() == "true"
SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL", "info@farforrent.com.ua")
SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", "FarforRent")


def send_email(
    to_email: str,
    subject: str,
    html_content: str,
    plain_content: Optional[str] = None,
    attachments: Optional[List[dict]] = None,
    reply_to: Optional[str] = None
) -> dict:
    """
    Відправити email
    
    Args:
        to_email: Email отримувача
        subject: Тема листа
        html_content: HTML вміст листа
        plain_content: Текстовий вміст (опціонально)
        attachments: Список вкладень [{"filename": "doc.pdf", "content": bytes, "content_type": "application/pdf"}]
        reply_to: Email для відповіді
    
    Returns:
        {"success": True/False, "message": "..."}
    """
    if not SMTP_USERNAME or not SMTP_PASSWORD:
        logger.error("SMTP credentials not configured")
        return {"success": False, "message": "SMTP не налаштовано"}
    
    try:
        # Створюємо повідомлення
        # Використовуємо "mixed" якщо є вкладення, інакше "alternative"
        if attachments:
            msg = MIMEMultipart("mixed")
            # Створюємо внутрішню частину для тексту
            msg_alt = MIMEMultipart("alternative")
        else:
            msg = MIMEMultipart("alternative")
            msg_alt = msg
            
        msg["Subject"] = subject
        msg["From"] = f"{SMTP_FROM_NAME} <{SMTP_FROM_EMAIL}>"
        msg["To"] = to_email
        
        if reply_to:
            msg["Reply-To"] = reply_to
        
        # Додаємо текстову версію
        if plain_content:
            part1 = MIMEText(plain_content, "plain", "utf-8")
            msg_alt.attach(part1)
        
        # Додаємо HTML версію
        part2 = MIMEText(html_content, "html", "utf-8")
        msg_alt.attach(part2)
        
        # Якщо є вкладення - додаємо текстову частину до основного повідомлення
        if attachments:
            msg.attach(msg_alt)
        
        # Додаємо вкладення
        if attachments:
            for attachment in attachments:
                content_type = attachment.get("content_type", "application/octet-stream")
                maintype, subtype = content_type.split("/", 1) if "/" in content_type else ("application", "octet-stream")
                
                part = MIMEBase(maintype, subtype)
                part.set_payload(attachment["content"])
                encoders.encode_base64(part)
                part.add_header(
                    "Content-Disposition",
                    "attachment",
                    filename=attachment['filename']
                )
                msg.attach(part)
        
        # Відправляємо
        context = ssl.create_default_context()
        
        if SMTP_USE_SSL:
            # SSL з'єднання (порт 465)
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=context) as server:
                server.login(SMTP_USERNAME, SMTP_PASSWORD)
                server.sendmail(SMTP_FROM_EMAIL, to_email, msg.as_string())
        else:
            # TLS з'єднання (порт 587)
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
                server.starttls(context=context)
                server.login(SMTP_USERNAME, SMTP_PASSWORD)
                server.sendmail(SMTP_FROM_EMAIL, to_email, msg.as_string())
        
        logger.info(f"Email sent successfully to {to_email}")
        return {"success": True, "message": f"Email відправлено на {to_email}"}
        
    except smtplib.SMTPAuthenticationError as e:
        logger.error(f"SMTP authentication failed: {e}")
        return {"success": False, "message": "Помилка автентифікації SMTP"}
    except smtplib.SMTPException as e:
        logger.error(f"SMTP error: {e}")
        return {"success": False, "message": f"Помилка SMTP: {str(e)}"}
    except Exception as e:
        logger.error(f"Email send error: {e}")
        return {"success": False, "message": f"Помилка відправки: {str(e)}"}


def send_document_email(
    to_email: str,
    document_type: str,
    document_html: str,
    order_number: str,
    customer_name: Optional[str] = None
) -> dict:
    """
    Відправити документ клієнту
    Документ відправляється як є - з тим самим дизайном що й в адмінці
    
    Args:
        to_email: Email клієнта
        document_type: Тип документа (invoice_offer, contract_rent, etc.)
        document_html: HTML вміст документа
        order_number: Номер замовлення
        customer_name: Ім'я клієнта
    """
    # Назви документів українською
    doc_names = {
        "estimate": "Кошторис",
        "invoice_offer": "Рахунок-оферта",
        "contract_rent": "Договір оренди",
        "issue_act": "Акт передачі",
        "return_act": "Акт повернення",
        "damage_invoice": "Рахунок за пошкодження",
        "deposit_refund_act": "Акт повернення застави",
        "picking_list": "Лист комплектації",
        "issue_checklist": "Чеклист видачі",
    }
    
    doc_name = doc_names.get(document_type, document_type)
    subject = f"{doc_name} - Замовлення {order_number} | FarforRent"
    
    # Відправляємо документ як є - той самий дизайн що в адмінці
    # Просто додаємо базову обгортку для email клієнтів
    html_content = document_html
    
    # Текстова версія для email клієнтів без HTML підтримки
    plain_content = f"""
{doc_name} - Замовлення {order_number}

Цей лист містить документ у форматі HTML.
Якщо ви не бачите документ, відкрийте лист в браузері або увімкніть відображення HTML.

З повагою,
Команда FarforRent
info@farforrent.com.ua
    """
    
    return send_email(
        to_email=to_email,
        subject=subject,
        html_content=html_content,
        plain_content=plain_content
    )


async def send_email_with_attachment(
    to_email: str,
    subject: str,
    body: str,
    attachment: bytes,
    attachment_filename: str,
    content_type: str = "application/pdf"
) -> dict:
    """
    Відправити email з вкладенням (async версія для FastAPI)
    
    Args:
        to_email: Email отримувача
        subject: Тема листа
        body: HTML тіло листа
        attachment: Байти вкладення
        attachment_filename: Назва файлу
        content_type: MIME тип вкладення
    """
    return send_email(
        to_email=to_email,
        subject=subject,
        html_content=body,
        attachments=[{
            "filename": attachment_filename,
            "content": attachment,
            "content_type": content_type
        }]
    )
