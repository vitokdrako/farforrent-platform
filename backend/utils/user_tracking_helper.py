"""
User Tracking Helper
Utility functions for integrating user tracking into existing endpoints
"""
import jwt
import os
from typing import Optional, Dict
from fastapi import Header

# JWT Secret
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"

def get_current_user_from_header(authorization: Optional[str] = None) -> Dict:
    """
    Extract current user from JWT token in Authorization header
    Returns a dict with user info or a default system user
    """
    if not authorization:
        # Return system user
        return {
            "id": None,
            "user_id": None,
            "email": "system",
            "name": "System",
            "role": "system"
        }
    
    try:
        # Remove 'Bearer ' prefix
        token = authorization.replace("Bearer ", "").strip()
        
        # Decode JWT
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        
        firstname = payload.get("firstname", "")
        lastname = payload.get("lastname", "")
        full_name = f"{firstname} {lastname}".strip()
        
        return {
            "id": payload.get("user_id"),
            "user_id": payload.get("user_id"),
            "email": payload.get("email"),
            "name": full_name or payload.get("username") or "User",
            "firstname": firstname,
            "lastname": lastname,
            "role": payload.get("role", "user")
        }
    except Exception as e:
        print(f"[UserTracking] Auth error: {e}")
        # Return system user
        return {
            "id": None,
            "user_id": None,
            "email": "system",
            "name": "System",
            "role": "system"
        }

async def get_current_user_dependency(authorization: Optional[str] = Header(None)) -> Dict:
    """
    FastAPI dependency for getting current user
    Can be used with Depends(get_current_user_dependency)
    """
    return get_current_user_from_header(authorization)
