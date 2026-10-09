"""
PDF Export routes - Generate PDF documents
"""
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from database import get_db
from sqlalchemy.orm import Session
from models_sqlalchemy import (
    OpenCartOrder, OpenCartOrderSimpleFields, OpenCartOrderProduct,
    DecorDamage, DecorDamageItem
)
from pdf_generator import pick_list_generator, invoice_generator, damage_report_generator
from config_manager import config_manager
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/pdf", tags=["pdf"])


@router.get("/pick-list/{order_id}")
async def generate_pick_list(order_id: int, db: Session = Depends(get_db)):
    """
    Generate pick-list PDF for order
    
    Used for warehouse staff to prepare order for delivery
    """
    try:
        # Get order data
        order = db.query(OpenCartOrder).filter(
            OpenCartOrder.order_id == order_id
        ).first()
        
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        
        # Get simple fields (dates)
        simple_fields = db.query(OpenCartOrderSimpleFields).filter(
            OpenCartOrderSimpleFields.order_id == order_id
        ).first()
        
        # Get order products
        products = db.query(OpenCartOrderProduct).filter(
            OpenCartOrderProduct.order_id == order_id
        ).all()
        
        # Prepare data for PDF
        order_data = {
            'order_number': str(order.order_id),
            'client_name': f"{order.firstname} {order.lastname}",
            'client_phone': order.telephone,
            'client_email': order.email,
            'issue_date': simple_fields.rent_issue_date if simple_fields else 'N/A',
            'return_date': simple_fields.rent_return_date if simple_fields else 'N/A',
            'items': [
                {
                    'article': p.model,
                    'name': p.name,
                    'quantity': p.quantity
                }
                for p in products
            ]
        }
        
        # Get company info from config
        config = config_manager.load_config()
        company_info = config.get('company', {})
        
        # Generate PDF
        pdf_buffer = pick_list_generator.generate(order_data, company_info)
        
        # Return as streaming response
        return StreamingResponse(
            pdf_buffer,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=picklist_{order_id}.pdf"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating pick-list: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate pick-list: {str(e)}"
        )


@router.get("/invoice/{order_id}")
async def generate_invoice(order_id: int, db: Session = Depends(get_db)):
    """
    Generate invoice PDF for order
    
    Includes rental costs, deposit, and totals
    """
    try:
        # Get order data
        order = db.query(OpenCartOrder).filter(
            OpenCartOrder.order_id == order_id
        ).first()
        
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        
        # Get simple fields
        simple_fields = db.query(OpenCartOrderSimpleFields).filter(
            OpenCartOrderSimpleFields.order_id == order_id
        ).first()
        
        # Get products
        products = db.query(OpenCartOrderProduct).filter(
            OpenCartOrderProduct.order_id == order_id
        ).all()
        
        # Calculate rental days
        rental_days = 1  # Default
        if simple_fields and simple_fields.rent_issue_date and simple_fields.rent_return_date:
            from datetime import datetime
            try:
                issue = datetime.strptime(simple_fields.rent_issue_date, '%Y-%m-%d')
                return_date = datetime.strptime(simple_fields.rent_return_date, '%Y-%m-%d')
                rental_days = max((return_date - issue).days, 1)
            except:
                pass
        
        # Calculate totals
        total_rental = sum(float(p.price) * int(p.quantity) * rental_days for p in products)
        total_deposit = total_rental * 0.20  # 20% deposit
        
        # Prepare data
        order_data = {
            'order_number': str(order.order_id),
            'client_name': f"{order.firstname} {order.lastname}",
            'client_phone': order.telephone,
            'client_email': order.email,
            'rental_days': rental_days,
            'total_rental': total_rental,
            'total_deposit': total_deposit,
            'items': [
                {
                    'name': p.name,
                    'quantity': p.quantity,
                    'price_per_day': float(p.price)
                }
                for p in products
            ]
        }
        
        # Get company info
        config = config_manager.load_config()
        company_info = config.get('company', {})
        
        # Generate PDF
        pdf_buffer = invoice_generator.generate(order_data, company_info)
        
        return StreamingResponse(
            pdf_buffer,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=invoice_{order_id}.pdf"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating invoice: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate invoice: {str(e)}"
        )


@router.get("/damage-report/{damage_id}")
async def generate_damage_report(damage_id: str, db: Session = Depends(get_db)):
    """
    Generate damage report PDF
    
    Includes damaged items, costs, and financial summary
    """
    try:
        # Get damage case
        damage_case = db.query(DecorDamage).filter(
            DecorDamage.id == damage_id
        ).first()
        
        if not damage_case:
            raise HTTPException(status_code=404, detail="Damage case not found")
        
        # Get damage items
        items = db.query(DecorDamageItem).filter(
            DecorDamageItem.damage_id == damage_id
        ).all()
        
        # Prepare data
        damage_data = {
            'id': damage_case.id,
            'order_number': damage_case.order_number,
            'customer_name': damage_case.customer_name,
            'customer_phone': damage_case.customer_phone,
            'case_status': damage_case.case_status,
            'deposit_available': float(damage_case.deposit_available or 0),
            'notes': damage_case.notes,
            'items': [
                {
                    'name': item.name,
                    'item_ref': item.item_ref,
                    'damage_type': item.damage_type,
                    'qty': item.qty,
                    'estimate_value': float(item.estimate_value or 0)
                }
                for item in items
            ]
        }
        
        # Get company info
        config = config_manager.load_config()
        company_info = config.get('company', {})
        
        # Generate PDF
        pdf_buffer = damage_report_generator.generate(damage_data, company_info)
        
        return StreamingResponse(
            pdf_buffer,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=damage_report_{damage_id[:8]}.pdf"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating damage report: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate damage report: {str(e)}"
        )
