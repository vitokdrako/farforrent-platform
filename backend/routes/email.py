"""
Email service for sending order confirmations
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os

from database import get_db
from models_sqlalchemy import OpenCartOrder

router = APIRouter(prefix="/api/email", tags=["email"])

class EmailConfirmation(BaseModel):
    order_id: int
    client_comment: str
    discount_percent: Optional[float] = 0
    rental_days: Optional[int] = None
    
@router.post("/send-confirmation")
async def send_order_confirmation(
    email_data: EmailConfirmation,
    db: Session = Depends(get_db)
):
    """
    Відправити підтвердження замовлення клієнту на email
    """
    try:
        # Отримати замовлення
        order = db.query(OpenCartOrder).filter(
            OpenCartOrder.order_id == email_data.order_id
        ).first()
        
        if not order:
            raise HTTPException(status_code=404, detail="Замовлення не знайдено")
        
        # Згенерувати токен підтвердження
        import uuid
        confirmation_token = str(uuid.uuid4())
        
        # Створити HTML email
        confirmation_url = f"https://backrentalhub.farforrent.com.ua/api/email/confirm/{confirmation_token}"
        
        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2>Підтвердження змін у замовленні #{order.order_id}</h2>
            
            <p>Шановний(а) {order.firstname} {order.lastname},</p>
            
            <p>Ми внесли зміни до вашого замовлення. Будь ласка, перевірте деталі:</p>
            
            <div style="background: #f5f5f5; padding: 15px; border-radius: 8px; margin: 20px 0;">
                <p><strong>Коментар менеджера:</strong></p>
                <p>{email_data.client_comment}</p>
                
                {f'<p><strong>Знижка:</strong> {email_data.discount_percent}%</p>' if email_data.discount_percent else ''}
                {f'<p><strong>Кількість днів оренди:</strong> {email_data.rental_days} діб</p>' if email_data.rental_days else ''}
            </div>
            
            <p>Якщо ви згодні з цими змінами, будь ласка, натисніть кнопку нижче:</p>
            
            <div style="text-align: center; margin: 30px 0;">
                <a href="{confirmation_url}" 
                   style="background: #4CAF50; color: white; padding: 12px 30px; text-decoration: none; border-radius: 6px; display: inline-block;">
                    ✓ Підтверджую зміни
                </a>
            </div>
            
            <p style="color: #666; font-size: 12px;">
                Якщо у вас є питання, зв'яжіться з нами за телефоном або email.
            </p>
            
            <hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;">
            <p style="color: #999; font-size: 11px;">
                RentalHub © 2025. Це автоматичний email, будь ласка не відповідайте на нього.
            </p>
        </body>
        </html>
        """
        
        # Відправити email (mock для тестування)
        # В production треба використати SMTP
        print(f"[EMAIL] Sending to {order.email}")
        print(f"[EMAIL] Subject: Підтвердження змін у замовленні #{order.order_id}")
        print(f"[EMAIL] Token: {confirmation_token}")
        
        # TODO: Зберегти токен в базі для верифікації
        # TODO: Налаштувати SMTP для реальної відправки
        
        return {
            "success": True,
            "message": "Email відправлено",
            "email": order.email,
            "confirmation_token": confirmation_token,
            "mock": True  # Видалити коли буде реальний SMTP
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Помилка відправки email: {str(e)}"
        )

@router.get("/confirm/{token}")
async def confirm_order_changes(token: str):
    """
    Підтвердження змін клієнтом через email link
    """
    # TODO: Перевірити токен в базі
    # TODO: Оновити статус замовлення
    
    return {
        "success": True,
        "message": "Дякуємо! Ваше підтвердження отримано.",
        "token": token
    }


# ==================== ВІДПРАВКА ДОКУМЕНТІВ ====================

class SendDocumentRequest(BaseModel):
    to_email: str
    document_type: str
    document_html: str
    order_number: str
    customer_name: Optional[str] = None


class SendDocumentByTypeRequest(BaseModel):
    """Запит для відправки документа по типу - автоматично генерує документ"""
    doc_type: str
    entity_id: str
    entity_type: Optional[str] = "order"
    recipient_email: str
    recipient_name: Optional[str] = None
    order_number: Optional[str] = None


@router.post("/send-document")
async def send_document_to_client(request: SendDocumentRequest):
    """
    Відправити документ клієнту на email (з готовим HTML)
    
    - document_type: invoice_offer, contract_rent, issue_act, return_act, etc.
    - document_html: HTML вміст документа
    - order_number: Номер замовлення
    - customer_name: Ім'я клієнта (опціонально)
    """
    from services.email_service import send_document_email
    
    if not request.to_email:
        raise HTTPException(status_code=400, detail="Email не вказано")
    
    if not request.document_html:
        raise HTTPException(status_code=400, detail="Документ порожній")
    
    result = send_document_email(
        to_email=request.to_email,
        document_type=request.document_type,
        document_html=request.document_html,
        order_number=request.order_number,
        customer_name=request.customer_name
    )
    
    if not result["success"]:
        raise HTTPException(status_code=500, detail=result["message"])
    
    return result


@router.post("/send-document-by-type")
async def send_document_by_type(request: SendDocumentByTypeRequest):
    """
    Автоматично генерує документ і відправляє на email.
    
    - doc_type: invoice_offer, contract_rent, issue_act, return_act, damage_breakdown, etc.
    - entity_id: ID замовлення або картки
    - entity_type: 'order' або 'issue'
    - recipient_email: Email отримувача
    """
    from services.email_service import send_document_email
    from services.doc_engine.data_builders import build_document_data
    from services.doc_engine.generator import generate_document_html
    from database_rentalhub import get_rh_db_sync
    
    if not request.recipient_email:
        raise HTTPException(status_code=400, detail="Email не вказано")
    
    try:
        db = get_rh_db_sync()
        
        # Генеруємо документ
        doc_data = build_document_data(db, request.doc_type, request.entity_id, {})
        html_content = generate_document_html(request.doc_type, doc_data)
        
        # Визначаємо номер замовлення
        order_number = request.order_number
        if not order_number and doc_data:
            order_number = doc_data.get('order', {}).get('order_number', request.entity_id)
        
        # Відправляємо email
        result = send_document_email(
            to_email=request.recipient_email,
            document_type=request.doc_type,
            document_html=html_content,
            order_number=order_number or request.entity_id,
            customer_name=request.recipient_name
        )
        
        db.close()
        
        if not result["success"]:
            raise HTTPException(status_code=500, detail=result["message"])
        
        return {
            "success": True,
            "message": f"Документ відправлено на {request.recipient_email}"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Помилка: {str(e)}")


@router.post("/test-smtp")
async def test_smtp_connection():
    """
    Тест SMTP з'єднання
    """
    from services.email_service import send_email, SMTP_HOST, SMTP_PORT, SMTP_FROM_EMAIL
    
    result = send_email(
        to_email=SMTP_FROM_EMAIL,  # Відправляємо самому собі
        subject="🧪 Тест SMTP - FarforRent",
        html_content="<h1>SMTP працює!</h1><p>Це тестовий лист.</p>",
        plain_content="SMTP працює! Це тестовий лист."
    )
    
    return {
        **result,
        "smtp_host": SMTP_HOST,
        "smtp_port": SMTP_PORT,
        "from_email": SMTP_FROM_EMAIL
    }
