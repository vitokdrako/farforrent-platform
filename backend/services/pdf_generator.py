"""
PDF Generator Service - генерація PDF документів
Використовує WeasyPrint та Jinja2 (якщо доступні)
"""
import os
import json
from datetime import datetime
from typing import Optional, Dict, Any
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
import logging

logger = logging.getLogger(__name__)

# WeasyPrint is optional - wrap in try-except to allow server to start without it
WEASYPRINT_AVAILABLE = False
HTML = None
CSS = None
FontConfiguration = None

try:
    from weasyprint import HTML as _HTML, CSS as _CSS
    from weasyprint.text.fonts import FontConfiguration as _FontConfiguration
    HTML = _HTML
    CSS = _CSS
    FontConfiguration = _FontConfiguration
    WEASYPRINT_AVAILABLE = True
except (ImportError, OSError) as e:
    logger.warning(f"WeasyPrint not available: {e}. PDF generation will be disabled.")

logger = logging.getLogger(__name__)

# Base paths
TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
PDF_OUTPUT_DIR = Path(__file__).parent.parent / "generated_pdfs"

# Ensure output directory exists
PDF_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Jinja2 environment with DB override
from services.template_loader import DBOverrideLoader
_file_loader_pdf = FileSystemLoader(str(TEMPLATES_DIR))
jinja_env = Environment(
    loader=DBOverrideLoader(_file_loader_pdf),
    autoescape=True
)

# Executor (company) default data - fallback if not in snapshot
EXECUTORS = {
    "tov": {
        "name": "ТОВ «ФАРФОР РЕНТ»",
        "short_name": "ТОВ «ФАРФОР РЕНТ»",
        "edrpou": "44651557",
        "address": "02000, м. Київ, вул. Магнітогорська, буд. 1, корп. 34",
        "bank": "АТ КБ «ПРИВАТБАНК»",
        "iban": "UA913052990000026002015020709",
        "director": "Драко В.А.",
        "tax_status": "платник податку на прибуток на загальних умовах"
    },
    "fop": {
        "name": "ФОП Николенко Наталя Станіславівна",
        "short_name": "ФОП Николенко Н.С.",
        "edrpou": "3606801844",
        "address": "02000, м. Київ, вул. Магнітогорська, буд. 1, корп. 34",
        "bank": "АТ «УНІВЕРСАЛ БАНК»",
        "iban": "UA043220010000026003340091618",
        "mfo": "322001",
        "director": None,
        "tax_status": "платник єдиного податку"
    }
}


def format_date_ua(date_str: str) -> str:
    """Format ISO date to Ukrainian format: DD.MM.YYYY"""
    if not date_str:
        return "—"
    try:
        if isinstance(date_str, str):
            dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        else:
            dt = date_str
        return dt.strftime("%d.%m.%Y")
    except:
        return date_str


def format_date_ua_long(date_str: str) -> str:
    """Format ISO date to Ukrainian long format: DD місяця YYYY"""
    if not date_str:
        return "—"
    try:
        if isinstance(date_str, str):
            dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        else:
            dt = date_str
        months = [
            'січня', 'лютого', 'березня', 'квітня', 'травня', 'червня',
            'липня', 'серпня', 'вересня', 'жовтня', 'листопада', 'грудня'
        ]
        return f"{dt.day} {months[dt.month - 1]} {dt.year}"
    except:
        return date_str


def generate_master_agreement_pdf(
    agreement_data: Dict[str, Any],
    client_data: Dict[str, Any],
    output_filename: Optional[str] = None
) -> Dict[str, Any]:
    """
    Generate PDF for Master Agreement
    
    Args:
        agreement_data: Agreement data from database (including snapshot_json)
        client_data: Client data from database
        output_filename: Optional custom filename
    
    Returns:
        {"success": True, "pdf_path": "...", "pdf_bytes": bytes}
    """
    try:
        # Get executor from snapshot or use default
        snapshot = agreement_data.get("snapshot") or {}
        executor_type = snapshot.get("executor_type") or agreement_data.get("template_version") or "tov"
        executor = snapshot.get("executor") or EXECUTORS.get(executor_type, EXECUTORS["tov"])
        
        # Get client from snapshot or use provided data
        snapshot_client = snapshot.get("client") or {}
        client = {
            "full_name": client_data.get("full_name") or snapshot_client.get("full_name") or "—",
            "email": client_data.get("email") or snapshot_client.get("email") or "—",
            "phone": client_data.get("phone") or snapshot_client.get("phone"),
            "payer_type": client_data.get("payer_type") or snapshot_client.get("payer_type") or "individual",
            "tax_id": client_data.get("tax_id") or snapshot_client.get("tax_id"),
            "company_name": client_data.get("company_name") or snapshot_client.get("company_name"),
            "director_name": client_data.get("director_name") or snapshot_client.get("director_name"),
            "bank_details": None
        }
        
        # Parse bank_details
        bank_details = client_data.get("bank_details") or snapshot_client.get("bank_details")
        if bank_details:
            if isinstance(bank_details, str):
                try:
                    client["bank_details"] = json.loads(bank_details)
                except:
                    client["bank_details"] = None
            else:
                client["bank_details"] = bank_details
        
        # Prepare template data
        template_data = {
            "contract_number": agreement_data.get("contract_number", "—"),
            "contract_date": format_date_ua(snapshot.get("contract_date") or agreement_data.get("valid_from")),
            "valid_from": format_date_ua(agreement_data.get("valid_from")),
            "valid_until": format_date_ua_long(agreement_data.get("valid_until")),
            "status": agreement_data.get("status", "draft"),
            "signed_at": format_date_ua(agreement_data.get("signed_at")) if agreement_data.get("signed_at") else None,
            "signed_by": agreement_data.get("signed_by"),
            "executor": executor,
            "client": client,
            "generated_at": datetime.now().strftime("%d.%m.%Y %H:%M")
        }
        
        # Load and render template
        template = jinja_env.get_template("legal/master_agreement.html")
        html_content = template.render(**template_data)
        
        # Generate PDF
        font_config = FontConfiguration()
        html = HTML(string=html_content, base_url=str(TEMPLATES_DIR))
        
        css = CSS(string='''
            @page {
                size: A4;
                margin: 15mm;
            }
            body {
                font-family: "DejaVu Sans", Arial, sans-serif;
            }
        ''', font_config=font_config)
        
        pdf_bytes = html.write_pdf(stylesheets=[css], font_config=font_config)
        
        # Save to file
        if not output_filename:
            contract_num_safe = agreement_data.get('contract_number', 'unknown').replace('-', '_').replace('/', '_')
            output_filename = f"Dogovir_{contract_num_safe}.pdf"
        
        pdf_path = PDF_OUTPUT_DIR / output_filename
        with open(pdf_path, 'wb') as f:
            f.write(pdf_bytes)
        
        logger.info(f"PDF generated: {pdf_path}")
        
        return {
            "success": True,
            "pdf_path": str(pdf_path),
            "pdf_filename": output_filename,
            "pdf_bytes": pdf_bytes
        }
        
    except Exception as e:
        logger.error(f"PDF generation error: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": str(e)
        }


def generate_master_agreement_html(
    agreement_data: Dict[str, Any],
    client_data: Dict[str, Any]
) -> str:
    """
    Generate HTML for Master Agreement (for preview)
    """
    try:
        # Get executor from snapshot or use default
        snapshot = agreement_data.get("snapshot") or {}
        executor_type = snapshot.get("executor_type") or agreement_data.get("template_version") or "tov"
        executor = snapshot.get("executor") or EXECUTORS.get(executor_type, EXECUTORS["tov"])
        
        # Get client from snapshot or use provided data
        snapshot_client = snapshot.get("client") or {}
        client = {
            "full_name": client_data.get("full_name") or snapshot_client.get("full_name") or "—",
            "email": client_data.get("email") or snapshot_client.get("email") or "—",
            "phone": client_data.get("phone") or snapshot_client.get("phone"),
            "payer_type": client_data.get("payer_type") or snapshot_client.get("payer_type") or "individual",
            "tax_id": client_data.get("tax_id") or snapshot_client.get("tax_id"),
            "company_name": client_data.get("company_name") or snapshot_client.get("company_name"),
            "director_name": client_data.get("director_name") or snapshot_client.get("director_name"),
            "bank_details": None
        }
        
        # Parse bank_details
        bank_details = client_data.get("bank_details") or snapshot_client.get("bank_details")
        if bank_details:
            if isinstance(bank_details, str):
                try:
                    client["bank_details"] = json.loads(bank_details)
                except:
                    client["bank_details"] = None
            else:
                client["bank_details"] = bank_details
        
        template_data = {
            "contract_number": agreement_data.get("contract_number", "—"),
            "contract_date": format_date_ua(snapshot.get("contract_date") or agreement_data.get("valid_from")),
            "valid_from": format_date_ua(agreement_data.get("valid_from")),
            "valid_until": format_date_ua_long(agreement_data.get("valid_until")),
            "status": agreement_data.get("status", "draft"),
            "signed_at": format_date_ua(agreement_data.get("signed_at")) if agreement_data.get("signed_at") else None,
            "signed_by": agreement_data.get("signed_by"),
            "executor": executor,
            "client": client,
            "generated_at": datetime.now().strftime("%d.%m.%Y %H:%M")
        }
        
        # Provide "agreement" wrapper for templates that use {{ agreement.xxx }}
        template_data["agreement"] = {
            **agreement_data,
            "contract_number": agreement_data.get("contract_number", "—"),
            "contract_date": format_date_ua(snapshot.get("contract_date") or agreement_data.get("valid_from")),
            "valid_from": format_date_ua(agreement_data.get("valid_from")),
            "valid_until": format_date_ua_long(agreement_data.get("valid_until")),
            "signed_at": format_date_ua(agreement_data.get("signed_at")) if agreement_data.get("signed_at") else None,
            "executor": executor,
            "client": client,
        }
        
        # Provide "landlord" mapping for DB templates
        template_data["landlord"] = {
            "name": executor.get("name", ""),
            "tax_id": executor.get("edrpou", executor.get("tax_id", "")),
            "iban": executor.get("iban", ""),
            "address": executor.get("address", ""),
        }
        
        # Provide "tenant" mapping for DB templates
        payer_type = client.get("payer_type", "individual")
        payer_type_labels = {
            "individual": "фізична особа",
            "fop": "фізична особа-підприємець",
            "tov": "юридична особа (ТОВ)",
            "pp": "приватне підприємство",
        }
        template_data["tenant"] = {
            "legal_name": client.get("company_name") or client.get("full_name", ""),
            "signer_name": client.get("director_name") or client.get("full_name", ""),
            "address": "",
            "iban": "",
            "type": payer_type,
            "type_label": payer_type_labels.get(payer_type, payer_type or ""),
            "tax_id": client.get("tax_id", ""),
            "phone": client.get("phone", ""),
            "email": client.get("email", ""),
            "full_name": client.get("full_name", ""),
        }
        if client.get("bank_details") and isinstance(client["bank_details"], dict):
            template_data["tenant"]["iban"] = client["bank_details"].get("iban", "")
            template_data["tenant"]["address"] = client["bank_details"].get("address", "")
        
        # Provide "meta" for DB templates (date parts + watermark)
        contract_date_raw = snapshot.get("contract_date") or agreement_data.get("valid_from")
        meta_day, meta_month, meta_year = "", "", ""
        if contract_date_raw:
            try:
                from datetime import date as dt_date
                if isinstance(contract_date_raw, str):
                    d = datetime.fromisoformat(contract_date_raw).date() if 'T' in contract_date_raw else datetime.strptime(contract_date_raw, "%Y-%m-%d").date()
                elif isinstance(contract_date_raw, dt_date):
                    d = contract_date_raw
                else:
                    d = None
                if d:
                    months_ua = ["січня","лютого","березня","квітня","травня","червня",
                                "липня","серпня","вересня","жовтня","листопада","грудня"]
                    meta_day = str(d.day)
                    meta_month = months_ua[d.month - 1]
                    meta_year = str(d.year)
            except:
                pass
        template_data["meta"] = {
            "watermark_text": "" if agreement_data.get("status") == "signed" else "ЧЕРНЕТКА",
            "contract_day": meta_day,
            "contract_month": meta_month,
            "contract_year": meta_year,
        }
        
        template = jinja_env.get_template("legal/master_agreement.html")
        return template.render(**template_data)
        
    except Exception as e:
        logger.error(f"HTML generation error: {e}")
        import traceback
        traceback.print_exc()
        return f"<html><body><h1>Помилка генерації</h1><p>{str(e)}</p></body></html>"
