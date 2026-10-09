"""
Test Orders Route - використовує in-memory тестову БД
"""
from fastapi import APIRouter
from typing import Optional, List
from datetime import datetime
import json

router = APIRouter(prefix="/api/test-orders", tags=["test-orders"])

@router.get("")
async def get_test_orders(
    status: Optional[str] = None,
    limit: int = 100
):
    """
    Отримати тестові замовлення
    
    Query params:
    - status: pending, on_rent, returned
    - limit: максимальна кількість
    """
    from test_database import get_test_session, TestOrder, TestOrderSimpleFields
    
    session = get_test_session()
    
    try:
        # Query з JOIN
        query = session.query(TestOrder, TestOrderSimpleFields).join(
            TestOrderSimpleFields,
            TestOrder.order_id == TestOrderSimpleFields.order_id
        )
        
        # Фільтр за статусом
        if status:
            status_map = {
                "pending": 19,
                "on_rent": 24,
                "returned": 25
            }
            if status in status_map:
                query = query.filter(TestOrder.order_status_id == status_map[status])
        else:
            # За замовчуванням: тільки активні (pending або on_rent)
            query = query.filter(TestOrder.order_status_id.in_([19, 24]))
        
        # Limit
        query = query.limit(limit)
        
        results = query.all()
        
        # Формуємо відповідь
        orders = []
        for order, simple_fields in results:
            # Розраховуємо totals
            items = json.loads(order.items_json) if order.items_json else []
            total_rental = sum(item.get('price', 0) * item.get('quantity', 0) for item in items)
            total_deposit = sum(item.get('deposit', 0) * item.get('quantity', 0) for item in items)
            
            # Маппінг статусу
            status_map = {
                19: "pending",
                24: "on_rent",
                25: "returned"
            }
            
            order_data = {
                "id": str(order.order_id),
                "order_number": order.order_number,
                "client_id": order.customer_id,
                "client_name": order.customer_name,
                "client_email": order.email,
                "client_phone": order.telephone,
                "status": status_map.get(order.order_status_id, "unknown"),
                "created_at": order.date_added.isoformat() if order.date_added else None,
                "issue_date": simple_fields.rent_issue_date,
                "return_date": simple_fields.rent_return_date,
                "total_rental": total_rental,
                "deposit_held": total_deposit,
                "total_deposit": total_deposit,
                "items": items,
                "items_count": len(items),
                "test_mode": True  # Маркер що це тестові дані
            }
            
            orders.append(order_data)
        
        return orders
        
    finally:
        session.close()

@router.get("/summary")
async def get_test_summary():
    """Статистика по тестовим замовленням"""
    from test_database import get_test_session, TestOrder
    
    session = get_test_session()
    
    try:
        today = datetime.now().strftime('%Y-%m-%d')
        
        # Всього замовлень
        total = session.query(TestOrder).count()
        
        # За статусами
        pending = session.query(TestOrder).filter(TestOrder.order_status_id == 19).count()
        on_rent = session.query(TestOrder).filter(TestOrder.order_status_id == 24).count()
        
        # Створені сьогодні
        created_today = session.query(TestOrder).filter(
            TestOrder.date_added >= datetime.now().date()
        ).count()
        
        return {
            "test_mode": True,
            "today": today,
            "total_orders": total,
            "by_status": {
                "pending": pending,
                "on_rent": on_rent
            },
            "created_today": created_today
        }
        
    finally:
        session.close()
