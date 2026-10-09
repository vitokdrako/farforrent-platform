"""
Email Provider Abstraction Layer
Supports: SMTP, Resend, SendGrid, Dummy (for testing)

Usage:
    provider = get_email_provider()
    result = await provider.send(to, subject, html, attachments)

Environment Variables:
    EMAIL_PROVIDER=smtp|resend|sendgrid|dummy (auto-detect if not set)
    
    # SMTP (recommended for own domain)
    SMTP_HOST=mail.adm.tools
    SMTP_PORT=465
    SMTP_USERNAME=info@example.com
    SMTP_PASSWORD=secret
    SMTP_USE_SSL=True
    SMTP_FROM_EMAIL=info@example.com
    SMTP_FROM_NAME=Company Name
    
    # Resend
    RESEND_API_KEY=re_...
    
    # SendGrid
    SENDGRID_API_KEY=SG....
"""
import os
import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel

logger = logging.getLogger(__name__)


# ============================================================
# DATA MODELS
# ============================================================

class EmailAttachment(BaseModel):
    filename: str
    content: str  # base64 encoded
    content_type: str = "application/pdf"


class EmailResult(BaseModel):
    success: bool
    provider: str
    email_id: Optional[str] = None
    error: Optional[str] = None
    sent_at: str = None
    
    def __init__(self, **data):
        if "sent_at" not in data:
            data["sent_at"] = datetime.now().isoformat()
        super().__init__(**data)


# ============================================================
# ABSTRACT EMAIL PROVIDER
# ============================================================

class EmailProvider(ABC):
    """Abstract base class for email providers"""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name for logging"""
        pass
    
    @abstractmethod
    async def send(
        self,
        to: str,
        subject: str,
        html: str,
        from_email: Optional[str] = None,
        attachments: Optional[List[EmailAttachment]] = None,
        cc: Optional[str] = None,
        bcc: Optional[str] = None
    ) -> EmailResult:
        """Send an email"""
        pass
    
    @abstractmethod
    def is_configured(self) -> bool:
        """Check if provider is properly configured"""
        pass


# ============================================================
# DUMMY PROVIDER (for development/testing)
# ============================================================

class DummyEmailProvider(EmailProvider):
    """
    Dummy provider that logs emails without sending.
    Use for development and testing.
    """
    
    @property
    def name(self) -> str:
        return "dummy"
    
    def is_configured(self) -> bool:
        return True
    
    async def send(
        self,
        to: str,
        subject: str,
        html: str,
        from_email: Optional[str] = None,
        attachments: Optional[List[EmailAttachment]] = None,
        cc: Optional[str] = None,
        bcc: Optional[str] = None
    ) -> EmailResult:
        """Log email details without actually sending"""
        
        logger.info(f"[DUMMY EMAIL] To: {to}")
        logger.info(f"[DUMMY EMAIL] Subject: {subject}")
        logger.info(f"[DUMMY EMAIL] From: {from_email or 'default'}")
        logger.info(f"[DUMMY EMAIL] HTML length: {len(html)} chars")
        if attachments:
            logger.info(f"[DUMMY EMAIL] Attachments: {[a.filename for a in attachments]}")
        
        # Simulate a slight delay
        await asyncio.sleep(0.1)
        
        return EmailResult(
            success=True,
            provider="dummy",
            email_id=f"dummy_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            error=None
        )


# ============================================================
# RESEND PROVIDER
# ============================================================

class ResendEmailProvider(EmailProvider):
    """
    Resend email provider.
    https://resend.com/docs
    """
    
    def __init__(self):
        self.api_key = os.environ.get("RESEND_API_KEY")
        self.default_from = os.environ.get("EMAIL_FROM", "onboarding@resend.dev")
    
    @property
    def name(self) -> str:
        return "resend"
    
    def is_configured(self) -> bool:
        return bool(self.api_key and self.api_key.startswith("re_"))
    
    async def send(
        self,
        to: str,
        subject: str,
        html: str,
        from_email: Optional[str] = None,
        attachments: Optional[List[EmailAttachment]] = None,
        cc: Optional[str] = None,
        bcc: Optional[str] = None
    ) -> EmailResult:
        """Send email via Resend API"""
        
        if not self.is_configured():
            return EmailResult(
                success=False,
                provider="resend",
                error="Resend API key not configured"
            )
        
        try:
            import resend
            resend.api_key = self.api_key
            
            params: Dict[str, Any] = {
                "from": from_email or self.default_from,
                "to": [to],
                "subject": subject,
                "html": html
            }
            
            if cc:
                params["cc"] = [cc]
            if bcc:
                params["bcc"] = [bcc]
            
            if attachments:
                params["attachments"] = [
                    {
                        "filename": att.filename,
                        "content": att.content,
                        "content_type": att.content_type
                    }
                    for att in attachments
                ]
            
            # Run sync SDK in thread for non-blocking
            email = await asyncio.to_thread(resend.Emails.send, params)
            
            logger.info(f"[RESEND] Email sent to {to}, id: {email.get('id')}")
            
            return EmailResult(
                success=True,
                provider="resend",
                email_id=email.get("id")
            )
            
        except Exception as e:
            logger.error(f"[RESEND] Failed to send email: {str(e)}")
            return EmailResult(
                success=False,
                provider="resend",
                error=str(e)
            )


# ============================================================
# SENDGRID PROVIDER
# ============================================================

class SendGridEmailProvider(EmailProvider):
    """
    SendGrid email provider.
    https://docs.sendgrid.com/
    """
    
    def __init__(self):
        self.api_key = os.environ.get("SENDGRID_API_KEY")
        self.default_from = os.environ.get("EMAIL_FROM", "noreply@example.com")
    
    @property
    def name(self) -> str:
        return "sendgrid"
    
    def is_configured(self) -> bool:
        return bool(self.api_key and self.api_key.startswith("SG."))
    
    async def send(
        self,
        to: str,
        subject: str,
        html: str,
        from_email: Optional[str] = None,
        attachments: Optional[List[EmailAttachment]] = None,
        cc: Optional[str] = None,
        bcc: Optional[str] = None
    ) -> EmailResult:
        """Send email via SendGrid API"""
        
        if not self.is_configured():
            return EmailResult(
                success=False,
                provider="sendgrid",
                error="SendGrid API key not configured"
            )
        
        try:
            from sendgrid import SendGridAPIClient
            from sendgrid.helpers.mail import (
                Mail, Attachment, FileContent, FileName, 
                FileType, Disposition, Cc, Bcc
            )
            
            message = Mail(
                from_email=from_email or self.default_from,
                to_emails=to,
                subject=subject,
                html_content=html
            )
            
            if cc:
                message.add_cc(Cc(cc))
            if bcc:
                message.add_bcc(Bcc(bcc))
            
            if attachments:
                for att in attachments:
                    attachment = Attachment(
                        FileContent(att.content),
                        FileName(att.filename),
                        FileType(att.content_type),
                        Disposition("attachment")
                    )
                    message.add_attachment(attachment)
            
            sg = SendGridAPIClient(self.api_key)
            response = await asyncio.to_thread(sg.send, message)
            
            logger.info(f"[SENDGRID] Email sent to {to}, status: {response.status_code}")
            
            return EmailResult(
                success=response.status_code in [200, 201, 202],
                provider="sendgrid",
                email_id=response.headers.get("X-Message-Id")
            )
            
        except Exception as e:
            logger.error(f"[SENDGRID] Failed to send email: {str(e)}")
            return EmailResult(
                success=False,
                provider="sendgrid",
                error=str(e)
            )


# ============================================================
# SMTP PROVIDER (Direct SMTP connection)
# ============================================================

class SMTPEmailProvider(EmailProvider):
    """
    Direct SMTP email provider.
    Uses standard SMTP protocol with SSL/TLS support.
    
    Environment Variables:
        SMTP_HOST=mail.example.com
        SMTP_PORT=465 (SSL) or 587 (TLS)
        SMTP_USERNAME=user@example.com
        SMTP_PASSWORD=password
        SMTP_USE_SSL=True|False
        SMTP_FROM_EMAIL=noreply@example.com
        SMTP_FROM_NAME=Company Name
    """
    
    def __init__(self):
        self.host = os.environ.get("SMTP_HOST")
        self.port = int(os.environ.get("SMTP_PORT", 465))
        self.username = os.environ.get("SMTP_USERNAME")
        self.password = os.environ.get("SMTP_PASSWORD")
        self.use_ssl = os.environ.get("SMTP_USE_SSL", "True").lower() == "true"
        self.from_email = os.environ.get("SMTP_FROM_EMAIL", self.username)
        self.from_name = os.environ.get("SMTP_FROM_NAME", "FarforDecorRent")
    
    @property
    def name(self) -> str:
        return "smtp"
    
    def is_configured(self) -> bool:
        return bool(self.host and self.username and self.password)
    
    async def send(
        self,
        to: str,
        subject: str,
        html: str,
        from_email: Optional[str] = None,
        attachments: Optional[List[EmailAttachment]] = None,
        cc: Optional[str] = None,
        bcc: Optional[str] = None
    ) -> EmailResult:
        """Send email via SMTP"""
        
        if not self.is_configured():
            return EmailResult(
                success=False,
                provider="smtp",
                error="SMTP not configured. Set SMTP_HOST, SMTP_USERNAME, SMTP_PASSWORD"
            )
        
        try:
            import smtplib
            from email.mime.multipart import MIMEMultipart
            from email.mime.text import MIMEText
            from email.mime.base import MIMEBase
            from email import encoders
            import base64
            import uuid
            
            # Build email message
            msg = MIMEMultipart('alternative')
            
            # From header with name
            sender = from_email or self.from_email
            if self.from_name:
                msg['From'] = f"{self.from_name} <{sender}>"
            else:
                msg['From'] = sender
            
            msg['To'] = to
            msg['Subject'] = subject
            
            if cc:
                msg['Cc'] = cc
            
            # Add HTML body
            msg.attach(MIMEText(html, 'html', 'utf-8'))
            
            # Add attachments
            if attachments:
                for att in attachments:
                    try:
                        part = MIMEBase('application', 'octet-stream')
                        part.set_payload(base64.b64decode(att.content))
                        encoders.encode_base64(part)
                        part.add_header(
                            'Content-Disposition',
                            f'attachment; filename="{att.filename}"'
                        )
                        msg.attach(part)
                    except Exception as att_err:
                        logger.warning(f"[SMTP] Failed to attach {att.filename}: {att_err}")
            
            # Build recipient list
            recipients = [to]
            if cc:
                recipients.append(cc)
            if bcc:
                recipients.append(bcc)
            
            # Send email (run sync SMTP in thread)
            def send_smtp():
                if self.use_ssl:
                    server = smtplib.SMTP_SSL(self.host, self.port, timeout=30)
                else:
                    server = smtplib.SMTP(self.host, self.port, timeout=30)
                    server.starttls()
                
                server.login(self.username, self.password)
                server.sendmail(sender, recipients, msg.as_string())
                server.quit()
                return True
            
            await asyncio.to_thread(send_smtp)
            
            email_id = f"smtp_{uuid.uuid4().hex[:12]}"
            logger.info(f"[SMTP] Email sent to {to} via {self.host}, id: {email_id}")
            
            return EmailResult(
                success=True,
                provider="smtp",
                email_id=email_id
            )
            
        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"[SMTP] Authentication failed: {str(e)}")
            return EmailResult(
                success=False,
                provider="smtp",
                error=f"SMTP authentication failed: {str(e)}"
            )
        except smtplib.SMTPException as e:
            logger.error(f"[SMTP] SMTP error: {str(e)}")
            return EmailResult(
                success=False,
                provider="smtp",
                error=f"SMTP error: {str(e)}"
            )
        except Exception as e:
            logger.error(f"[SMTP] Failed to send email: {str(e)}")
            return EmailResult(
                success=False,
                provider="smtp",
                error=str(e)
            )


# ============================================================
# PROVIDER FACTORY
# ============================================================

_provider_instance: Optional[EmailProvider] = None

def get_email_provider() -> EmailProvider:
    """
    Get configured email provider based on EMAIL_PROVIDER env var.
    Uses singleton pattern for efficiency.
    
    Priority:
    1. If EMAIL_PROVIDER is set explicitly, use that
    2. If SMTP_HOST is configured, use SMTP
    3. Fall back to dummy
    """
    global _provider_instance
    
    if _provider_instance is not None:
        return _provider_instance
    
    provider_name = os.environ.get("EMAIL_PROVIDER", "").lower()
    
    # Explicit provider selection
    if provider_name == "smtp":
        provider = SMTPEmailProvider()
        if not provider.is_configured():
            logger.warning("SMTP not configured, falling back to dummy provider")
            provider = DummyEmailProvider()
    elif provider_name == "resend":
        provider = ResendEmailProvider()
        if not provider.is_configured():
            logger.warning("Resend not configured, falling back to dummy provider")
            provider = DummyEmailProvider()
    elif provider_name == "sendgrid":
        provider = SendGridEmailProvider()
        if not provider.is_configured():
            logger.warning("SendGrid not configured, falling back to dummy provider")
            provider = DummyEmailProvider()
    elif provider_name == "dummy":
        provider = DummyEmailProvider()
    else:
        # Auto-detect: check if SMTP is configured
        smtp_provider = SMTPEmailProvider()
        if smtp_provider.is_configured():
            provider = smtp_provider
            logger.info("Auto-detected SMTP configuration, using SMTP provider")
        else:
            provider = DummyEmailProvider()
    
    _provider_instance = provider
    logger.info(f"Email provider initialized: {provider.name}")
    
    return provider


def reset_provider():
    """Reset provider instance (useful for testing)"""
    global _provider_instance
    _provider_instance = None
