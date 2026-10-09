"""
PDF Generation utilities for Rental Hub
Generates pick-lists, invoices, and damage reports
"""
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from io import BytesIO
from datetime import datetime
from typing import Dict, List, Any


class PDFGenerator:
    """Base class for PDF generation"""
    
    def __init__(self):
        self.width, self.height = A4
        self.styles = getSampleStyleSheet()
        self._add_custom_styles()
    
    def _add_custom_styles(self):
        """Add custom paragraph styles"""
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=18,
            textColor=colors.HexColor('#1a1a1a'),
            spaceAfter=12,
            alignment=TA_CENTER
        ))
        
        self.styles.add(ParagraphStyle(
            name='CustomHeading',
            parent=self.styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#333333'),
            spaceAfter=10,
            spaceBefore=10
        ))
        
        self.styles.add(ParagraphStyle(
            name='CustomBody',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#4a4a4a')
        ))
    
    def create_header(self, company_info: Dict[str, str]) -> List:
        """Create PDF header with company info"""
        elements = []
        
        # Company name
        title = Paragraph(
            f"<b>{company_info.get('name', 'Rental Hub')}</b>",
            self.styles['CustomTitle']
        )
        elements.append(title)
        
        # Company details
        details = []
        if company_info.get('address'):
            details.append(company_info['address'])
        if company_info.get('phone'):
            details.append(f"Тел: {company_info['phone']}")
        if company_info.get('email'):
            details.append(f"Email: {company_info['email']}")
        
        if details:
            details_text = Paragraph(
                ' | '.join(details),
                self.styles['CustomBody']
            )
            elements.append(details_text)
        
        elements.append(Spacer(1, 10*mm))
        
        return elements


class PickListGenerator(PDFGenerator):
    """Generate pick-list for order fulfillment"""
    
    def generate(self, order: Dict[str, Any], company_info: Dict[str, str]) -> BytesIO:
        """Generate pick-list PDF"""
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        elements = []
        
        # Header
        elements.extend(self.create_header(company_info))
        
        # Title
        title = Paragraph(
            f"<b>PICK-LIST #{order.get('order_number', 'N/A')}</b>",
            self.styles['CustomTitle']
        )
        elements.append(title)
        elements.append(Spacer(1, 5*mm))
        
        # Order info
        order_info = [
            ['Клієнт:', order.get('client_name', 'N/A')],
            ['Телефон:', order.get('client_phone', 'N/A')],
            ['Дата видачі:', order.get('issue_date', 'N/A')],
            ['Дата повернення:', order.get('return_date', 'N/A')],
            ['Створено:', datetime.now().strftime('%d.%m.%Y %H:%M')]
        ]
        
        info_table = Table(order_info, colWidths=[40*mm, 120*mm])
        info_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#666666')),
            ('TEXTCOLOR', (1, 0), (1, -1), colors.HexColor('#1a1a1a')),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        
        elements.append(info_table)
        elements.append(Spacer(1, 10*mm))
        
        # Items table
        items_header = Paragraph('<b>ТОВАРИ ДО ВИДАЧІ</b>', self.styles['CustomHeading'])
        elements.append(items_header)
        elements.append(Spacer(1, 3*mm))
        
        # Table data
        data = [['№', 'Артикул', 'Назва товару', 'Кіл-ть', '☐ OK']]
        
        for idx, item in enumerate(order.get('items', []), 1):
            data.append([
                str(idx),
                item.get('article', 'N/A'),
                item.get('name', 'N/A')[:40],  # Truncate long names
                str(item.get('quantity', 0)),
                ''  # Checkbox for marking
            ])
        
        items_table = Table(data, colWidths=[10*mm, 25*mm, 85*mm, 20*mm, 20*mm])
        items_table.setStyle(TableStyle([
            # Header
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f0f0f0')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#1a1a1a')),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            
            # Body
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('ALIGN', (0, 1), (0, -1), 'CENTER'),  # №
            ('ALIGN', (3, 1), (3, -1), 'CENTER'),  # Кількість
            ('ALIGN', (4, 1), (4, -1), 'CENTER'),  # Checkbox
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            
            # Grid
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9f9f9')])
        ]))
        
        elements.append(items_table)
        elements.append(Spacer(1, 10*mm))
        
        # Footer notes
        notes = Paragraph(
            '<b>Примітки:</b><br/>'
            '☐ Всі товари перевірені та укомплектовані<br/>'
            '☐ Товари упаковані<br/>'
            '☐ Документи підготовлені',
            self.styles['CustomBody']
        )
        elements.append(notes)
        
        elements.append(Spacer(1, 15*mm))
        
        # Signatures
        sig_data = [
            ['Склав:', '_' * 30, 'Дата:', '_' * 20],
            ['', '', '', ''],
            ['Видав:', '_' * 30, 'Дата:', '_' * 20]
        ]
        
        sig_table = Table(sig_data, colWidths=[25*mm, 65*mm, 20*mm, 50*mm])
        sig_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        
        elements.append(sig_table)
        
        # Build PDF
        doc.build(elements)
        buffer.seek(0)
        return buffer


class InvoiceGenerator(PDFGenerator):
    """Generate invoice for order"""
    
    def generate(self, order: Dict[str, Any], company_info: Dict[str, str]) -> BytesIO:
        """Generate invoice PDF"""
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        elements = []
        
        # Header
        elements.extend(self.create_header(company_info))
        
        # Title
        title = Paragraph(
            f"<b>РАХУНОК #{order.get('order_number', 'N/A')}</b>",
            self.styles['CustomTitle']
        )
        elements.append(title)
        elements.append(Spacer(1, 5*mm))
        
        # Invoice info
        invoice_info = [
            ['Дата рахунку:', datetime.now().strftime('%d.%m.%Y')],
            ['Замовлення:', f"#{order.get('order_number', 'N/A')}"],
            ['', ''],
            ['<b>Клієнт:</b>', ''],
            ['Ім\'я:', order.get('client_name', 'N/A')],
            ['Телефон:', order.get('client_phone', 'N/A')],
            ['Email:', order.get('client_email', 'N/A')],
        ]
        
        info_table = Table(invoice_info, colWidths=[40*mm, 120*mm])
        info_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#666666')),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        
        elements.append(info_table)
        elements.append(Spacer(1, 10*mm))
        
        # Items table
        data = [['№', 'Назва', 'Кіл-ть', 'Ціна/день', 'Дні', 'Сума']]
        
        total = 0
        for idx, item in enumerate(order.get('items', []), 1):
            price = float(item.get('price_per_day', 0))
            qty = int(item.get('quantity', 0))
            days = int(order.get('rental_days', 1))
            subtotal = price * qty * days
            total += subtotal
            
            data.append([
                str(idx),
                item.get('name', 'N/A')[:35],
                str(qty),
                f"{price:.2f}",
                str(days),
                f"{subtotal:.2f}"
            ])
        
        items_table = Table(data, colWidths=[10*mm, 70*mm, 20*mm, 25*mm, 15*mm, 25*mm])
        items_table.setStyle(TableStyle([
            # Header
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f0f0f0')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#1a1a1a')),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            
            # Body
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('ALIGN', (2, 1), (-1, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            
            # Grid
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9f9f9')])
        ]))
        
        elements.append(items_table)
        elements.append(Spacer(1, 5*mm))
        
        # Totals
        deposit = float(order.get('total_deposit', 0))
        currency = company_info.get('currency', 'UAH')
        
        totals_data = [
            ['', '', '', '', 'Оренда:', f"{total:.2f} {currency}"],
            ['', '', '', '', 'Застава:', f"{deposit:.2f} {currency}"],
            ['', '', '', '', '<b>ВСЬОГО:</b>', f"<b>{total + deposit:.2f} {currency}</b>"]
        ]
        
        totals_table = Table(totals_data, colWidths=[10*mm, 70*mm, 20*mm, 25*mm, 25*mm, 25*mm])
        totals_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('ALIGN', (4, 0), (-1, -1), 'RIGHT'),
            ('TEXTCOLOR', (4, 2), (-1, 2), colors.HexColor('#1a1a1a')),
            ('LINEABOVE', (4, 2), (-1, 2), 1, colors.HexColor('#333333')),
        ]))
        
        elements.append(totals_table)
        elements.append(Spacer(1, 15*mm))
        
        # Payment terms
        terms = Paragraph(
            '<b>Умови оплати:</b><br/>'
            'Оплата здійснюється готівкою або банківським переказом при отриманні товару.<br/>'
            'Застава повертається після повернення товару у належному стані.',
            self.styles['CustomBody']
        )
        elements.append(terms)
        
        # Build PDF
        doc.build(elements)
        buffer.seek(0)
        return buffer


class DamageReportGenerator(PDFGenerator):
    """Generate damage report"""
    
    def generate(self, damage_case: Dict[str, Any], company_info: Dict[str, str]) -> BytesIO:
        """Generate damage report PDF"""
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        elements = []
        
        # Header
        elements.extend(self.create_header(company_info))
        
        # Title
        title = Paragraph(
            f"<b>АКТ ПОШКОДЖЕНЬ #{damage_case.get('id', 'N/A')[:8]}</b>",
            self.styles['CustomTitle']
        )
        elements.append(title)
        elements.append(Spacer(1, 5*mm))
        
        # Case info
        case_info = [
            ['Замовлення:', f"#{damage_case.get('order_number', 'N/A')}"],
            ['Клієнт:', damage_case.get('customer_name', 'N/A')],
            ['Телефон:', damage_case.get('customer_phone', 'N/A')],
            ['Дата створення:', datetime.now().strftime('%d.%m.%Y %H:%M')],
            ['Статус:', damage_case.get('case_status', 'N/A').upper()],
        ]
        
        info_table = Table(case_info, colWidths=[40*mm, 120*mm])
        info_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#666666')),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        
        elements.append(info_table)
        elements.append(Spacer(1, 10*mm))
        
        # Damaged items
        items_header = Paragraph('<b>ПОШКОДЖЕНІ ТОВАРИ</b>', self.styles['CustomHeading'])
        elements.append(items_header)
        elements.append(Spacer(1, 3*mm))
        
        data = [['№', 'Товар', 'Артикул', 'Тип пошкодження', 'Кіл-ть', 'Оцінка']]
        
        total_cost = 0
        for idx, item in enumerate(damage_case.get('items', []), 1):
            cost = float(item.get('estimate_value', 0))
            qty = int(item.get('qty', 1))
            total_cost += cost * qty
            
            data.append([
                str(idx),
                item.get('name', 'N/A')[:30],
                item.get('item_ref', 'N/A'),
                item.get('damage_type', 'N/A')[:25],
                str(qty),
                f"{cost * qty:.2f}"
            ])
        
        items_table = Table(data, colWidths=[10*mm, 50*mm, 25*mm, 40*mm, 15*mm, 25*mm])
        items_table.setStyle(TableStyle([
            # Header
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f0f0f0')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#1a1a1a')),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 8),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            
            # Body
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('ALIGN', (4, 1), (-1, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            
            # Grid
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#fff3f3')])
        ]))
        
        elements.append(items_table)
        elements.append(Spacer(1, 5*mm))
        
        # Financial summary
        currency = company_info.get('currency', 'UAH')
        deposit_available = float(damage_case.get('deposit_available', 0))
        
        summary_data = [
            ['Загальна вартість пошкоджень:', f"{total_cost:.2f} {currency}"],
            ['Доступна застава:', f"{deposit_available:.2f} {currency}"],
            ['Утримано із застави:', f"{min(total_cost, deposit_available):.2f} {currency}"],
            ['Додатковий платіж:', f"{max(total_cost - deposit_available, 0):.2f} {currency}"]
        ]
        
        summary_table = Table(summary_data, colWidths=[120*mm, 40*mm])
        summary_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('LINEABOVE', (0, 3), (-1, 3), 1, colors.HexColor('#333333')),
            ('TEXTCOLOR', (0, 3), (-1, 3), colors.HexColor('#c41e3a')),
        ]))
        
        elements.append(summary_table)
        elements.append(Spacer(1, 10*mm))
        
        # Notes
        if damage_case.get('notes'):
            notes = Paragraph(
                f"<b>Примітки:</b><br/>{damage_case.get('notes')}",
                self.styles['CustomBody']
            )
            elements.append(notes)
            elements.append(Spacer(1, 10*mm))
        
        # Signatures
        sig_data = [
            ['Менеджер:', '_' * 30, 'Дата:', '_' * 20],
            ['', '', '', ''],
            ['Клієнт:', '_' * 30, 'Дата:', '_' * 20]
        ]
        
        sig_table = Table(sig_data, colWidths=[25*mm, 65*mm, 20*mm, 50*mm])
        sig_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        
        elements.append(sig_table)
        
        # Build PDF
        doc.build(elements)
        buffer.seek(0)
        return buffer


# Singletons
pick_list_generator = PickListGenerator()
invoice_generator = InvoiceGenerator()
damage_report_generator = DamageReportGenerator()



def finance_report_generator(order_data: Dict[str, Any], transactions: List[Dict[str, Any]], company_info: Dict[str, str] = None) -> BytesIO:
    """
    Generate finance report PDF for an order
    
    Args:
        order_data: Order information (order_id, client_name, client_email, etc.)
        transactions: List of financial transactions
        company_info: Company details for header
    
    Returns:
        BytesIO: PDF file buffer
    """
    if company_info is None:
        company_info = {
            'name': 'Rental Hub',
            'address': 'Київ, Україна',
            'phone': '+380 XX XXX XXXX',
            'email': 'info@rentalhub.com',
            'currency': 'UAH'
        }
    
    buffer = BytesIO()
    generator = PDFGenerator()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=15*mm, bottomMargin=15*mm)
    elements = []
    
    # Header
    elements.extend(generator.create_header(company_info))
    
    # Document title
    title = Paragraph(
        f"<b>Фінансовий звіт</b><br/>Замовлення #{order_data.get('order_id', 'N/A')}",
        generator.styles['CustomTitle']
    )
    elements.append(title)
    elements.append(Spacer(1, 5*mm))
    
    # Client info
    client_info = [
        ['Клієнт:', order_data.get('client_name', 'N/A')],
        ['Email:', order_data.get('client_email', 'N/A')],
        ['Телефон:', order_data.get('client_phone', 'N/A')],
        ['Дата звіту:', datetime.now().strftime('%d.%m.%Y %H:%M')]
    ]
    
    client_table = Table(client_info, colWidths=[40*mm, 120*mm])
    client_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    
    elements.append(client_table)
    elements.append(Spacer(1, 10*mm))
    
    # Financial summary
    total_accrued = sum([t.get('debit', 0) for t in transactions])
    total_paid = sum([t.get('credit', 0) for t in transactions])
    deposit_held = sum([t.get('credit', 0) for t in transactions if t.get('type') == 'deposit_hold'])
    balance = total_accrued - total_paid
    
    summary_title = Paragraph("<b>Фінансовий підсумок</b>", generator.styles['CustomHeading'])
    elements.append(summary_title)
    
    summary_data = [
        ['Нараховано:', f"₴ {total_accrued:,.2f}"],
        ['Оплачено:', f"₴ {total_paid:,.2f}"],
        ['Застава (холд):', f"₴ {deposit_held:,.2f}"],
        ['До сплати:', f"₴ {balance:,.2f}"]
    ]
    
    summary_table = Table(summary_data, colWidths=[100*mm, 60*mm])
    summary_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8f9fa')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dee2e6')),
        ('TEXTCOLOR', (0, 3), (1, 3), colors.HexColor('#dc3545') if balance > 0 else colors.HexColor('#28a745')),
        ('LINEABOVE', (0, 3), (-1, 3), 1.5, colors.HexColor('#333333')),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    
    elements.append(summary_table)
    elements.append(Spacer(1, 10*mm))
    
    # Transactions table
    trans_title = Paragraph("<b>Історія транзакцій</b>", generator.styles['CustomHeading'])
    elements.append(trans_title)
    
    trans_headers = ['Дата', 'Тип', 'Опис', 'Дебет', 'Кредит', 'Статус']
    trans_data = [trans_headers]
    
    type_labels = {
        'prepayment': 'Передплата',
        'payment': 'Оплата',
        'rent_accrual': 'Оренда',
        'rent': 'Оренда',
        'deposit_hold': 'Застава',
        'deposit_release': 'Повернення',
        'deposit_writeoff': 'Списання',
        'damage': 'Збитки',
        'balance_due': 'Борг'
    }
    
    status_labels = {
        'paid': 'Оплачено',
        'held': 'Холд',
        'unpaid': 'Не оплачено',
        'accrued': 'Нараховано',
        'completed': 'Завершено'
    }
    
    for t in transactions:
        trans_data.append([
            t.get('date', '')[:10] if t.get('date') else '',
            type_labels.get(t.get('type', ''), t.get('type', '')),
            t.get('title', '')[:40],
            f"₴ {t.get('debit', 0):,.2f}" if t.get('debit', 0) > 0 else '—',
            f"₴ {t.get('credit', 0):,.2f}" if t.get('credit', 0) > 0 else '—',
            status_labels.get(t.get('status', ''), t.get('status', ''))
        ])
    
    trans_table = Table(trans_data, colWidths=[22*mm, 25*mm, 55*mm, 25*mm, 25*mm, 25*mm])
    trans_table.setStyle(TableStyle([
        # Header
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#343a40')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 0), (-1, 0), 8),
        
        # Body
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('ALIGN', (3, 1), (4, -1), 'RIGHT'),
        ('ALIGN', (0, 1), (2, -1), 'LEFT'),
        ('ALIGN', (5, 1), (5, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 1), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 5),
        
        # Grid
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dee2e6')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')])
    ]))
    
    elements.append(trans_table)
    elements.append(Spacer(1, 15*mm))
    
    # Footer note
    footer_note = Paragraph(
        "<i>Цей документ згенеровано автоматично системою Rental Hub.<br/>"
        "Для питань звертайтеся за контактами вище.</i>",
        generator.styles['CustomBody']
    )
    elements.append(footer_note)
    
    # Build PDF
    doc.build(elements)
    buffer.seek(0)
    
    return buffer

