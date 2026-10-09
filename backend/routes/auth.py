"""
Authentication routes for Warehouse Frontend
"""
from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from sqlalchemy import text
import hashlib
import bcrypt
from datetime import datetime, timedelta
import jwt
import os

from database import get_db
from database_rentalhub import get_rh_db

router = APIRouter(prefix="/api/auth", tags=["auth"])

# JWT Secret (у продакшн треба зберігати в .env)
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1440  # 24 години

# ============================================================
# PYDANTIC MODELS
# ============================================================

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    user: dict

class UserResponse(BaseModel):
    user_id: int
    username: str
    email: str
    firstname: str
    lastname: str
    role: str  # 'admin', 'manager', 'requisitioner'

# ============================================================
# HELPERS
# ============================================================

def verify_opencart_password(password: str, salt: str, hashed: str) -> bool:
    """Verify password using OpenCart's hashing method (SHA1 + salt)"""
    computed_hash = hashlib.sha1((salt + hashlib.sha1((salt + hashlib.sha1(password.encode()).hexdigest()).encode()).hexdigest()).encode()).hexdigest()
    return computed_hash == hashed

def create_access_token(data: dict, expires_delta: timedelta = None):
    """Create JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def determine_user_role(email: str, user_group_id: int) -> str:
    """Determine user role based on email and group"""
    email_lower = email.lower()
    
    # Admin/Directors - повний доступ
    if any(admin_email in email_lower for admin_email in ['vitokdrako@gmail.com', 'huktania3@gmail.com']):
        return 'admin'
    
    # Managers - менеджерський кабінет
    if any(manager_email in email_lower for manager_email in ['rfarfordecor@gmail.com', 'aleksandra.arsalani@icloud.com']):
        return 'manager'
    
    # Requisitioners - реквізиторський кабінет
    # Альбіна, Катя, Діана, Андрій, Ярослав, Женя
    return 'requisitioner'

# ============================================================
# API ENDPOINTS
# ============================================================

@router.post("/login", response_model=LoginResponse)
async def login(
    credentials: LoginRequest, 
    db: Session = Depends(get_db),
    rh_db: Session = Depends(get_rh_db)
):
    """
    Login endpoint - спробує спочатку нову users таблицю, потім OpenCart
    """
    # Спочатку пробуємо нову users таблицю (RentalHub)
    try:
        query_rh = text("""
            SELECT user_id, username, email, password_hash, firstname, lastname, 
                   role, is_active, last_login
            FROM users 
            WHERE email = :email AND is_active = 1
        """)
        
        result_rh = rh_db.execute(query_rh, {"email": credentials.email})
        user_rh = result_rh.fetchone()
        
        if user_rh:
            # Перевіряємо пароль через bcrypt
            if bcrypt.checkpw(credentials.password.encode('utf-8'), user_rh[3].encode('utf-8')):
                # Оновлюємо last_login
                update_query = text("UPDATE users SET last_login = NOW() WHERE user_id = :user_id")
                rh_db.execute(update_query, {"user_id": user_rh[0]})
                rh_db.commit()
                
                # Створюємо токен з повним ім'ям користувача
                access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
                access_token = create_access_token(
                    data={
                        "sub": user_rh[2],  # email
                        "email": user_rh[2],
                        "username": user_rh[1],
                        "user_id": user_rh[0],
                        "firstname": user_rh[4] or "",
                        "lastname": user_rh[5] or "",
                        "role": user_rh[6]
                    },
                    expires_delta=access_token_expires
                )
                
                return LoginResponse(
                    access_token=access_token,
                    token_type="bearer",
                    user={
                        "user_id": user_rh[0],
                        "username": user_rh[1],
                        "email": user_rh[2],
                        "firstname": user_rh[4] or "",
                        "lastname": user_rh[5] or "",
                        "role": user_rh[6]
                    }
                )
    except Exception as e:
        print(f"RentalHub auth error: {e}")
    
    # Якщо не знайшли в новій таблиці, пробуємо OpenCart (fallback)
    try:
        # Find user by email
        query = text("""
            SELECT user_id, username, password, salt, firstname, lastname, email, 
                   user_group_id, status
            FROM oc_user 
            WHERE email = :email AND status = 1
        """)
        
        result = db.execute(query, {"email": credentials.email})
        user = result.fetchone()
        
        if not user:
            raise HTTPException(status_code=401, detail="Невірний email або пароль")
        
        # Verify password
        if not verify_opencart_password(credentials.password, user.salt, user.password):
            raise HTTPException(status_code=401, detail="Невірний email або пароль")
        
        # Determine role
        role = determine_user_role(user.email, user.user_group_id)
        
        # Create access token
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={
                "sub": user.email,
                "user_id": user.user_id,
                "role": role
            },
            expires_delta=access_token_expires
        )
        
        # Return response
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "user_id": user.user_id,
                "username": user.username,
                "email": user.email,
                "firstname": user.firstname,
                "lastname": user.lastname,
                "role": role
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Login error: {e}")
        raise HTTPException(status_code=500, detail="Помилка авторизації")

@router.get("/me", response_model=UserResponse)
async def get_current_user(token: str, db: Session = Depends(get_db)):
    """Get current user info from token"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        role = payload.get("role")
        
        if email is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        query = text("""
            SELECT user_id, username, email, firstname, lastname
            FROM oc_user 
            WHERE email = :email AND status = 1
        """)
        
        result = db.execute(query, {"email": email})
        user = result.fetchone()
        
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        
        return {
            "user_id": user.user_id,
            "username": user.username,
            "email": user.email,
            "firstname": user.firstname,
            "lastname": user.lastname,
            "role": role
        }
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

@router.post("/refresh")
async def refresh_token(authorization: str = Header(None), db: Session = Depends(get_rh_db)):
    """
    Оновити access token.
    ✅ Можна викликати навіть з протухлим токеном (до 7 днів)
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header required")
    
    try:
        token = authorization.replace("Bearer ", "")
        
        # Декодуємо без перевірки терміну дії
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM], options={"verify_exp": False})
        except jwt.JWTError:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        # Перевіряємо що токен не старший 7 днів
        exp = payload.get("exp")
        if exp:
            token_expired_at = datetime.utcfromtimestamp(exp)
            max_refresh_time = token_expired_at + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
            if datetime.utcnow() > max_refresh_time:
                raise HTTPException(status_code=401, detail="Token too old to refresh, please login again")
        
        email = payload.get("sub")
        if not email:
            raise HTTPException(status_code=401, detail="Invalid token payload")
        
        # Знаходимо користувача
        result = db.execute(text("""
            SELECT user_id, username, email, firstname, lastname, user_group_id
            FROM users WHERE email = :email AND is_active = 1
        """), {"email": email})
        user_row = result.fetchone()
        
        if not user_row:
            raise HTTPException(status_code=401, detail="User not found")
        
        role = determine_user_role(user_row[2], user_row[5])
        
        # Створюємо новий токен
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        new_token = create_access_token(
            data={
                "sub": user_row[2],
                "user_id": user_row[0],
                "role": role,
                "firstname": user_row[3],
                "lastname": user_row[4]
            },
            expires_delta=access_token_expires
        )
        
        return {
            "access_token": new_token,
            "token_type": "bearer",
            "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,  # в секундах
            "user": {
                "id": user_row[0],
                "email": user_row[2],
                "name": f"{user_row[3]} {user_row[4]}".strip(),
                "role": role
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/logout")
async def logout():
    """Logout endpoint (client should delete token)"""
    return {"message": "Successfully logged out"}
