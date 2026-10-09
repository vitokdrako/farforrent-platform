"""
Users/Managers routes - for getting OpenCart users
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import List
from sqlalchemy.orm import Session
from database import get_db
from models_sqlalchemy import OpenCartUser

router = APIRouter(prefix="/api/users", tags=["users"])

@router.get("")
async def get_users(
    active_only: bool = True,
    db: Session = Depends(get_db)
):
    """
    Get all users/managers from OpenCart
    
    Query params:
    - active_only: bool (default True) - return only active users
    """
    try:
        query = db.query(OpenCartUser)
        
        if active_only:
            query = query.filter(OpenCartUser.status == 1)
        
        users = query.order_by(OpenCartUser.firstname).all()
        
        return [
            {
                "id": user.user_id,
                "username": user.username,
                "firstname": user.firstname,
                "lastname": user.lastname,
                "full_name": f"{user.firstname} {user.lastname}",
                "email": user.email,
                "telephone": user.telephone,
                "telegram_id": user.telegram_id,
                "image": user.image,
                "status": user.status,
                "user_group_id": user.user_group_id,
                "date_added": user.date_added.isoformat() if user.date_added else None
            }
            for user in users
        ]
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching users: {str(e)}"
        )

@router.get("/{user_id}")
async def get_user(user_id: int, db: Session = Depends(get_db)):
    """Get single user by ID"""
    user = db.query(OpenCartUser).filter(OpenCartUser.user_id == user_id).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {
        "id": user.user_id,
        "username": user.username,
        "firstname": user.firstname,
        "lastname": user.lastname,
        "full_name": f"{user.firstname} {user.lastname}",
        "email": user.email,
        "telephone": user.telephone,
        "telegram_id": user.telegram_id,
        "image": user.image,
        "status": user.status,
        "user_group_id": user.user_group_id,
        "date_added": user.date_added.isoformat() if user.date_added else None
    }
