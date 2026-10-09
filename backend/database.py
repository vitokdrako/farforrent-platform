"""
Database connection manager for MySQL (OpenCart)
"""
import os
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import pymysql

# Load environment variables FIRST
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MySQL OpenCart connection from environment
# Priority: OC_DB_ variables first, then MYSQL_ variables
MYSQL_HOST = os.environ.get('OC_DB_HOST') or os.environ.get('MYSQL_HOST', 'localhost')
MYSQL_PORT = int(os.environ.get('OC_DB_PORT') or os.environ.get('MYSQL_PORT', 3306))
MYSQL_USER = os.environ.get('OC_DB_USERNAME') or os.environ.get('MYSQL_USER', 'root')
MYSQL_PASSWORD = os.environ.get('OC_DB_PASSWORD') or os.environ.get('MYSQL_PASSWORD', '')
MYSQL_DATABASE = os.environ.get('OC_DB_DATABASE') or os.environ.get('MYSQL_DATABASE', 'opencart')

# MySQL connection string
MYSQL_URL = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}?charset=utf8mb4"

# SQLAlchemy setup
engine = create_engine(
    MYSQL_URL,
    pool_pre_ping=True,      # Test connection before using
    pool_recycle=180,        # Recycle connections every 3 minutes
    pool_size=10,            # Increased connection pool size
    max_overflow=20,         # Increased max overflow connections
    pool_timeout=30,         # Increased connection timeout
    connect_args={
        'connect_timeout': 30,  # Increased MySQL connection timeout
        'read_timeout': 60,     # Increased MySQL read timeout
        'write_timeout': 60     # Increased MySQL write timeout
    },
    echo=False               # Set to True for SQL debugging
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Dependency for FastAPI routes
def get_db():
    """Get SQLAlchemy database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_mysql_connection():
    """Get raw PyMySQL connection for complex queries"""
    return pymysql.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DATABASE,
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )

# Export for use in routes
__all__ = ['get_db', 'get_mysql_connection', 'Base', 'engine']
