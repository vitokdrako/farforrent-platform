"""
Document Render - генерація HTML та PDF
"""
import os
from jinja2 import Environment, FileSystemLoader, select_autoescape
from datetime import datetime

# WeasyPrint is optional - will be imported when needed
WEASYPRINT_AVAILABLE = False
try:
    from weasyprint import HTML, CSS
    from weasyprint.text.fonts import FontConfiguration
    WEASYPRINT_AVAILABLE = True
except (ImportError, OSError):
    pass

# Шлях до шаблонів
TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), '..', 'templates', 'documents')

# Jinja2 environment with DB override
from services.template_loader import DBOverrideLoader
_file_loader = FileSystemLoader(TEMPLATES_DIR)
jinja_env = Environment(
    loader=DBOverrideLoader(_file_loader),
    autoescape=select_autoescape(['html', 'xml'])
)

# Custom filters
def format_money(value):
    """Форматує суму в гривнях"""
    try:
        return f"{float(value):,.2f}".replace(",", " ")
    except:
        return "0.00"

def format_date(value, fmt="%d.%m.%Y"):
    """Форматує дату"""
    if isinstance(value, str):
        return value
    if isinstance(value, datetime):
        return value.strftime(fmt)
    return str(value) if value else ""

jinja_env.filters['money'] = format_money
jinja_env.filters['date'] = format_date

# Custom tests
import re
def regex_search(value, pattern):
    """Jinja2 filter: regex search"""
    if not value or not pattern:
        return False
    return bool(re.search(pattern, str(value)))

jinja_env.filters['regex_search'] = regex_search
jinja_env.tests['regex_search'] = regex_search

def render_html(template_path: str, data: dict) -> str:
    """
    Рендерить HTML з шаблону та даних.
    
    Args:
        template_path: шлях до шаблону відносно templates/documents/
        data: дані для шаблону
    
    Returns:
        HTML рядок
    """
    template = jinja_env.get_template(template_path)
    return template.render(**data)

def render_pdf(html_content: str, base_url: str = None) -> bytes:
    """
    Генерує PDF з HTML.
    
    Args:
        html_content: HTML рядок
        base_url: базовий URL для відносних посилань
    
    Returns:
        PDF як bytes
    """
    if not WEASYPRINT_AVAILABLE:
        # Fallback: return HTML as bytes with print styles
        print_html = f'''<!DOCTYPE html>
<html>
<head>
<style>
@media print {{
    @page {{ size: A4; margin: 15mm; }}
    body {{ font-family: Arial, sans-serif; font-size: 10pt; }}
}}
</style>
</head>
<body>
{html_content}
<script>window.print();</script>
</body>
</html>'''
        return print_html.encode('utf-8')
    
    font_config = FontConfiguration()
    
    # CSS для друку
    css = CSS(string='''
        @page {
            size: A4;
            margin: 15mm;
        }
        body {
            font-family: "DejaVu Sans", "Arial", sans-serif;
            font-size: 10pt;
            line-height: 1.4;
        }
        table {
            width: 100%;
            border-collapse: collapse;
        }
        th, td {
            border: 1px solid #ddd;
            padding: 6px 8px;
            text-align: left;
        }
        th {
            background-color: #f5f5f5;
            font-weight: bold;
        }
        .header {
            margin-bottom: 20px;
        }
        .footer {
            margin-top: 30px;
        }
        .signature-block {
            margin-top: 40px;
            display: flex;
            justify-content: space-between;
        }
        .signature-line {
            width: 200px;
            border-bottom: 1px solid #000;
            margin-top: 30px;
        }
        .text-right { text-align: right; }
        .text-center { text-align: center; }
        .font-bold { font-weight: bold; }
        .text-sm { font-size: 9pt; }
        .text-lg { font-size: 12pt; }
        .mb-2 { margin-bottom: 8px; }
        .mb-4 { margin-bottom: 16px; }
        .mt-4 { margin-top: 16px; }
    ''', font_config=font_config)
    
    html = HTML(string=html_content, base_url=base_url)
    return html.write_pdf(stylesheets=[css], font_config=font_config)

def get_template_path(doc_type: str, version: str = "v1", lang: str = "uk") -> str:
    """
    Формує шлях до шаблону.
    
    Args:
        doc_type: тип документа
        version: версія шаблону
        lang: мова (uk/en)
    
    Returns:
        Шлях до шаблону
    """
    # Спочатку шукаємо з мовою
    lang_path = f"{doc_type}/{lang}/{version}.html"
    if os.path.exists(os.path.join(TEMPLATES_DIR, lang_path)):
        return lang_path
    
    # Fallback до дефолтного
    return f"{doc_type}/{version}.html"
