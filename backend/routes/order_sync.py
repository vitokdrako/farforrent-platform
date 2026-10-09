"""
Order Sync API - Real-time синхронізація змін в ордерах

Архітектура:
1. WebSocket Hub - тримає з'єднання всіх клієнтів
2. Версіонування по секціях (header, items, progress, comments)
3. Бродкаст подій без затирання локальної роботи
4. REST endpoints для версій (fallback для polling)

Секції ордера:
- header: дати, статус, клієнт, доставка
- items: позиції, кількості, ціни
- progress: прогрес збору (warehouse-specific)
- comments: internal notes / чат
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime
from typing import Dict, Set, Optional, List
import json
import asyncio

from database_rentalhub import get_rh_db

router = APIRouter(prefix="/api/orders", tags=["order-sync"])


# ============================================================
# WebSocket Connection Manager
# ============================================================
class OrderSyncManager:
    """Менеджер WebSocket з'єднань для синхронізації ордерів"""
    
    def __init__(self):
        # order_id -> set of WebSocket connections
        self.active_connections: Dict[int, Set[WebSocket]] = {}
        # websocket -> {user_id, user_name, order_id, role}
        self.connection_info: Dict[WebSocket, dict] = {}
        
    async def connect(self, websocket: WebSocket, order_id: int, user_id: int, user_name: str, role: str = "manager"):
        """Підключити клієнта до кімнати ордера"""
        await websocket.accept()
        
        if order_id not in self.active_connections:
            self.active_connections[order_id] = set()
        
        self.active_connections[order_id].add(websocket)
        self.connection_info[websocket] = {
            "user_id": user_id,
            "user_name": user_name,
            "role": role,
            "order_id": order_id,
            "connected_at": datetime.now().isoformat()
        }
        
        # Notify others that someone joined
        await self.broadcast(order_id, {
            "type": "user.joined",
            "user_id": user_id,
            "user_name": user_name,
            "role": role,
            "users_count": len(self.active_connections[order_id]),
            "users": self.get_active_users(order_id)
        }, exclude=websocket)
        
        # Send current users to the new connection
        await websocket.send_text(json.dumps({
            "type": "sync.connected",
            "order_id": order_id,
            "users": self.get_active_users(order_id),
            "timestamp": datetime.now().isoformat()
        }, ensure_ascii=False))
        
        print(f"[WS] {user_name} ({role}) connected to order {order_id}. Total: {len(self.active_connections[order_id])}")
    
    def disconnect(self, websocket: WebSocket):
        """Відключити клієнта"""
        info = self.connection_info.get(websocket)
        if info:
            order_id = info["order_id"]
            if order_id in self.active_connections:
                self.active_connections[order_id].discard(websocket)
                
                # Cleanup empty rooms
                if not self.active_connections[order_id]:
                    del self.active_connections[order_id]
                else:
                    # Notify others
                    asyncio.create_task(self.broadcast(order_id, {
                        "type": "user.left",
                        "user_id": info["user_id"],
                        "user_name": info["user_name"],
                        "role": info["role"],
                        "users_count": len(self.active_connections.get(order_id, set())),
                        "users": self.get_active_users(order_id)
                    }))
            
            del self.connection_info[websocket]
            print(f"[WS] {info['user_name']} disconnected from order {order_id}")
    
    async def broadcast(self, order_id: int, message: dict, exclude: Optional[WebSocket] = None):
        """Відправити повідомлення всім в кімнаті ордера"""
        if order_id not in self.active_connections:
            return
        
        message["timestamp"] = datetime.now().isoformat()
        message_json = json.dumps(message, ensure_ascii=False)
        
        disconnected = []
        for connection in self.active_connections[order_id]:
            if connection == exclude:
                continue
            try:
                await connection.send_text(message_json)
            except Exception as e:
                print(f"[WS] Failed to send message: {e}")
                disconnected.append(connection)
        
        # Cleanup disconnected
        for conn in disconnected:
            self.disconnect(conn)
    
    async def notify_section_update(self, order_id: int, section: str, 
                                     updated_by_id: int, updated_by_name: str,
                                     version: int, changes_summary: str = "",
                                     changed_fields: List[str] = None):
        """Повідомити про оновлення секції"""
        await self.broadcast(order_id, {
            "type": "order.section.updated",
            "section": section,
            "version": version,
            "updated_by_id": updated_by_id,
            "updated_by_name": updated_by_name,
            "changes_summary": changes_summary,
            "changed_fields": changed_fields or []
        })
    
    async def notify_comment_added(self, order_id: int, comment: dict, sender_id: int):
        """Повідомити про новий коментар"""
        await self.broadcast(order_id, {
            "type": "order.comment.added",
            "comment": comment,
            "sender_id": sender_id
        })
    
    def get_active_users(self, order_id: int) -> list:
        """Отримати список активних користувачів в ордері"""
        if order_id not in self.active_connections:
            return []
        
        users = []
        seen_ids = set()
        for ws in self.active_connections[order_id]:
            info = self.connection_info.get(ws)
            if info and info["user_id"] not in seen_ids:
                seen_ids.add(info["user_id"])
                users.append({
                    "user_id": info["user_id"],
                    "user_name": info["user_name"],
                    "role": info["role"],
                    "connected_at": info["connected_at"]
                })
        return users


# Global manager instance
sync_manager = OrderSyncManager()


# ============================================================
# REST API Endpoints
# ============================================================

@router.get("/{order_id}/last-modified")
async def get_order_last_modified(
    order_id: str,
    db: Session = Depends(get_rh_db)
):
    """
    Отримати timestamp останньої зміни замовлення.
    Легкий endpoint для polling - повертає тільки timestamp.
    """
    try:
        result = db.execute(text("""
            SELECT updated_at, modified_by 
            FROM orders 
            WHERE order_id = :order_id
        """), {"order_id": str(order_id)})
        
        row = result.fetchone()
        if not row:
            return {"order_id": order_id, "last_modified": None, "modified_by": None}
        
        return {
            "order_id": order_id,
            "last_modified": row[0].isoformat() if row[0] else None,
            "modified_by": row[1]
        }
        
    except Exception as e:
        return {"order_id": order_id, "last_modified": None, "modified_by": None}


@router.post("/{order_id}/touch")
async def touch_order(
    order_id: str,
    user_id: Optional[str] = None,
    user_name: Optional[str] = None,
    db: Session = Depends(get_rh_db)
):
    """Оновити timestamp (коли користувач зберігає)"""
    try:
        db.execute(text("""
            UPDATE orders 
            SET updated_at = NOW(), modified_by = :modified_by
            WHERE order_id = :order_id
        """), {
            "order_id": str(order_id),
            "modified_by": user_name or f"User {user_id}"
        })
        db.commit()
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/{order_id}/versions")
async def get_order_versions(order_id: int, db: Session = Depends(get_rh_db)):
    """Отримати поточні версії всіх секцій ордера"""
    try:
        result = db.execute(text("""
            SELECT section, version, modified_by_id, modified_by_name, modified_at
            FROM order_section_versions
            WHERE order_id = :order_id
        """), {"order_id": order_id})
        
        versions = {}
        for row in result:
            versions[row[0]] = {
                "version": row[1],
                "modified_by_id": row[2],
                "modified_by_name": row[3],
                "modified_at": row[4].isoformat() if row[4] else None
            }
    except:
        versions = {}
    
    # Додати дефолтні секції якщо немає
    for section in ["header", "items", "progress", "comments"]:
        if section not in versions:
            versions[section] = {"version": 0, "modified_by_id": None, "modified_by_name": None, "modified_at": None}
    
    return {
        "order_id": order_id,
        "versions": versions,
        "active_users": sync_manager.get_active_users(order_id)
    }


@router.post("/{order_id}/sections/{section}/update")
async def update_section_version(
    order_id: int, 
    section: str,
    client_version: int = Query(0),
    user_id: int = Query(0),
    user_name: str = Query(""),
    changes_summary: str = Query(""),
    changed_fields: str = Query(""),  # comma-separated
    db: Session = Depends(get_rh_db)
):
    """
    Оновити версію секції (викликається після збереження змін)
    Повертає 409 якщо версія застаріла
    """
    if section not in ["header", "items", "progress", "comments"]:
        raise HTTPException(status_code=400, detail=f"Invalid section: {section}")
    
    # Перевірити поточну версію
    try:
        current = db.execute(text("""
            SELECT version FROM order_section_versions 
            WHERE order_id = :order_id AND section = :section
        """), {"order_id": order_id, "section": section}).fetchone()
        
        current_version = current[0] if current else 0
    except:
        # Таблиця може не існувати
        current_version = 0
    
    # Конфлікт версій (якщо клієнт має стару версію)
    if client_version > 0 and client_version < current_version:
        return {
            "conflict": True,
            "client_version": client_version,
            "server_version": current_version,
            "message": "Дані застаріли. Хтось інший вніс зміни."
        }
    
    # Оновити версію
    new_version = current_version + 1
    
    try:
        if current:
            db.execute(text("""
                UPDATE order_section_versions 
                SET version = :version, modified_by_id = :user_id, 
                    modified_by_name = :user_name, modified_at = NOW()
                WHERE order_id = :order_id AND section = :section
            """), {
                "order_id": order_id, "section": section,
                "version": new_version, "user_id": user_id, "user_name": user_name
            })
        else:
            db.execute(text("""
                INSERT INTO order_section_versions (order_id, section, version, modified_by_id, modified_by_name, modified_at)
                VALUES (:order_id, :section, :version, :user_id, :user_name, NOW())
            """), {
                "order_id": order_id, "section": section,
                "version": new_version, "user_id": user_id, "user_name": user_name
            })
        
        db.commit()
    except Exception as e:
        print(f"[Sync] Error updating version: {e}")
        # Продовжуємо без збереження версії
    
    # Бродкаст іншим користувачам через WebSocket
    fields_list = [f.strip() for f in changed_fields.split(",") if f.strip()] if changed_fields else []
    await sync_manager.notify_section_update(
        order_id, section, user_id, user_name, new_version, changes_summary, fields_list
    )
    
    return {
        "conflict": False,
        "new_version": new_version,
        "section": section
    }


@router.get("/{order_id}/active-users")
async def get_active_users(order_id: int):
    """Отримати список активних користувачів в ордері"""
    return {
        "order_id": order_id,
        "users": sync_manager.get_active_users(order_id)
    }


# ============================================================
# WebSocket Endpoint
# ============================================================

@router.websocket("/{order_id}/ws")
async def websocket_order_sync(
    websocket: WebSocket, 
    order_id: int,
    user_id: int = 0,
    user_name: str = "Анонім",
    role: str = "manager"
):
    """
    WebSocket для real-time синхронізації ордера
    
    Клієнт отримує події:
    - sync.connected - успішне підключення + список активних юзерів
    - user.joined / user.left - хтось приєднався/вийшов
    - user.typing - хтось друкує коментар
    - order.section.updated - секція оновлена (header/items/progress/comments)
    - order.comment.added - новий коментар
    
    Клієнт може відправляти:
    - {"type": "ping"} - heartbeat
    - {"type": "typing"} - сигнал що друкує
    """
    await sync_manager.connect(websocket, order_id, user_id, user_name, role)
    
    try:
        while True:
            # Отримуємо повідомлення від клієнта
            data = await websocket.receive_text()
            
            try:
                message = json.loads(data)
                msg_type = message.get("type", "")
                
                if msg_type == "ping":
                    await websocket.send_text(json.dumps({"type": "pong", "timestamp": datetime.now().isoformat()}))
                
                elif msg_type == "typing":
                    # Хтось друкує коментар
                    await sync_manager.broadcast(order_id, {
                        "type": "user.typing",
                        "user_id": user_id,
                        "user_name": user_name
                    }, exclude=websocket)
                    
            except json.JSONDecodeError:
                pass
                
    except WebSocketDisconnect:
        sync_manager.disconnect(websocket)
    except Exception as e:
        print(f"[WS] Error: {e}")
        sync_manager.disconnect(websocket)


# ============================================================
# Helper functions для інших роутів
# ============================================================

async def broadcast_order_update(order_id: int, section: str, user_id: int, user_name: str, 
                                  changes: str = "", changed_fields: List[str] = None):
    """Хелпер для бродкасту змін з інших роутів"""
    await sync_manager.notify_section_update(order_id, section, user_id, user_name, 0, changes, changed_fields)


async def broadcast_comment(order_id: int, comment: dict, sender_id: int):
    """Хелпер для бродкасту коментаря"""
    await sync_manager.notify_comment_added(order_id, comment, sender_id)


def get_sync_manager():
    """Отримати глобальний sync manager"""
    return sync_manager
