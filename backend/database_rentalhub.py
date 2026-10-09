"""
RentalHub Database Connection
Separate connection for the new optimized database
"""
import os
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import pymysql

# Load environment
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# RentalHub MySQL connection
RH_HOST = os.environ.get('RH_DB_HOST', 'farforre.mysql.tools')
RH_PORT = int(os.environ.get('RH_DB_PORT', 3306))
RH_USER = os.environ.get('RH_DB_USERNAME', 'farforre_rentalhub')
RH_PASSWORD = os.environ.get('RH_DB_PASSWORD', '-nu+3Gp54L')
RH_DATABASE = os.environ.get('RH_DB_DATABASE', 'farforre_rentalhub')

# RentalHub connection string
RH_MYSQL_URL = f"mysql+pymysql://{RH_USER}:{RH_PASSWORD}@{RH_HOST}:{RH_PORT}/{RH_DATABASE}?charset=utf8mb4"

# SQLAlchemy setup for RentalHub
rh_engine = create_engine(
    RH_MYSQL_URL,
    pool_pre_ping=True,
    pool_recycle=180,
    pool_size=10,
    max_overflow=20,
    pool_timeout=60,
    connect_args={
        'connect_timeout': 30,
        'read_timeout': 60,
        'write_timeout': 60
    },
    echo=False
)

RHSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=rh_engine)
RHBase = declarative_base()

# Dependency for FastAPI routes
def get_rh_db():
    """Get RentalHub database session"""
    db = RHSessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_rh_db_sync():
    """Get RentalHub database session (synchronous, for use in non-async contexts)"""
    return RHSessionLocal()

# Test connection
def test_connection():
    """Test RentalHub DB connection"""
    try:
        from sqlalchemy import text
        db = RHSessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        return True
    except Exception as e:
        print(f"RentalHub DB connection error: {e}")
        return False

if __name__ == "__main__":
    print("Testing RentalHub DB connection...")
    if test_connection():
        print("✅ RentalHub DB connected successfully!")
    else:
        print("❌ RentalHub DB connection failed")
