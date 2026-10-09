"""
Email sender utility for FarforRent
Використовує SMTP для відправки email
"""

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr
from pathlib import Path
from jinja2 import Template
import logging

logger = logging.getLogger(__name__)


class EmailSender:
    """Email sender через SMTP"""
    
    def __init__(self):
        self.smtp_host = os.getenv('SMTP_HOST', 'localhost')
        self.smtp_port = int(os.getenv('SMTP_PORT', '465'))
        self.smtp_username = os.getenv('SMTP_USERNAME', '')
        self.smtp_password = os.getenv('SMTP_PASSWORD', '')
        self.smtp_use_ssl = os.getenv('SMTP_USE_SSL', 'True').lower() == 'true'
        self.from_email = os.getenv('SMTP_FROM_EMAIL', 'noreply@farforrent.com.ua')
        self.from_name = os.getenv('SMTP_FROM_NAME', 'FarforRent')
        
    def send_email(
        self,
        to_email: str,
        to_name: str,
        subject: str,
        html_content: str,
        text_content: str = None
    ) -> bool:
        """
        Відправити email
        
        Args:
            to_email: Email отримувача
            to_name: Ім'я отримувача
            subject: Тема листа
            html_content: HTML контент
            text_content: Plain text контент (fallback)
            
        Returns:
            bool: True якщо успішно
        """
        print(f"[EMAIL SENDER] Attempting to send email to {to_email}")
        print(f"[EMAIL SENDER] SMTP Config: host={self.smtp_host}, port={self.smtp_port}, use_ssl={self.smtp_use_ssl}")
        try:
            # Створити повідомлення
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = formataddr((self.from_name, self.from_email))
            msg['To'] = formataddr((to_name, to_email))
            
            # Додати text version
            if text_content:
                part1 = MIMEText(text_content, 'plain', 'utf-8')
                msg.attach(part1)
            
            # Додати HTML version
            part2 = MIMEText(html_content, 'html', 'utf-8')
            msg.attach(part2)
            
            print(f"[EMAIL SENDER] Message created, attempting SMTP connection...")
            
            # Відправити через SMTP
            if self.smtp_use_ssl:
                # SSL connection
                with smtplib.SMTP_SSL(self.smtp_host, self.smtp_port) as server:
                    if self.smtp_username and self.smtp_password:
                        server.login(self.smtp_username, self.smtp_password)
                    server.sendmail(self.from_email, to_email, msg.as_string())
            else:
                # TLS connection
                with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                    server.starttls()
                    if self.smtp_username and self.smtp_password:
                        server.login(self.smtp_username, self.smtp_password)
                    server.sendmail(self.from_email, to_email, msg.as_string())
            
            print(f"[EMAIL SENDER] ✅ Email відправлено: {to_email} - {subject}")
            logger.info(f"✅ Email відправлено: {to_email} - {subject}")
            return True
            
        except Exception as e:
            print(f"[EMAIL SENDER] ❌ Помилка відправки email до {to_email}: {str(e)}")
            logger.error(f"❌ Помилка відправки email до {to_email}: {str(e)}")
            return False
    
    def send_order_confirmation(
        self,
        to_email: str,
        to_name: str,
        order_data: dict
    ) -> bool:
        """
        Відправити email підтвердження замовлення
        
        Args:
            to_email: Email клієнта
            to_name: Ім'я клієнта
            order_data: Дані замовлення для template
            
        Returns:
            bool: True якщо успішно
        """
        print(f"[EMAIL SENDER] send_order_confirmation викликано для {to_email}")
        print(f"[EMAIL SENDER] order_data keys: {list(order_data.keys())}")
        try:
            # Завантажити template
            template_path = Path(__file__).parent.parent / 'email_templates' / 'order_confirmation_v2.html'
            print(f"[EMAIL SENDER] Template path: {template_path}")
            
            if not template_path.exists():
                logger.error(f"❌ Template не знайдено: {template_path}")
                return False
            
            with open(template_path, 'r', encoding='utf-8') as f:
                template_content = f.read()
                template = Template(template_content)
                html_content = template.render(**order_data)
            
            # Створити text version (fallback)
            text_content = f"""
Підтвердження замовлення #{order_data.get('order_number')}

Вітаємо, {to_name}!

Ви створили замовлення на оренду декору у FarforRent.
Будь ласка, підтвердіть замовлення за посиланням: {order_data.get('confirmation_link')}

Дата видачі: {order_data.get('rent_date')}
Дата повернення: {order_data.get('return_date')}
Кількість діб: {order_data.get('rental_days')}

Загальна сума: ₴ {order_data.get('total_rental')}
Застава: ₴ {order_data.get('total_deposit')}

З повагою,
Команда FarforRent
https://farforrent.com.ua
+38 (097) 123 09 93
            """
            
            subject = f"Підтвердження замовлення #{order_data.get('order_number')} — FarforRent"
            
            return self.send_email(
                to_email=to_email,
                to_name=to_name,
                subject=subject,
                html_content=html_content,
                text_content=text_content
            )
            
        except Exception as e:
            logger.error(f"❌ Помилка відправки підтвердження замовлення: {str(e)}")
            return False


# Singleton instance
_email_sender = None

def get_email_sender() -> EmailSender:
    """Отримати singleton instance EmailSender"""
    global _email_sender
    if _email_sender is None:
        _email_sender = EmailSender()
    return _email_sender
