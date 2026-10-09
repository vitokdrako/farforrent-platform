"""
Configuration Manager for Rental Hub Universal Tool
Handles database configuration, field mapping, and encryption
"""
import json
import os
from typing import Dict, Any, Optional
from pathlib import Path
from cryptography.fernet import Fernet
import base64
from datetime import datetime

CONFIG_FILE = Path(__file__).parent / "rental_hub_config.json"
ENCRYPTION_KEY_FILE = Path(__file__).parent / ".encryption_key"

class ConfigManager:
    """Manage application configuration with encryption"""
    
    def __init__(self):
        self.config_file = CONFIG_FILE
        self.key_file = ENCRYPTION_KEY_FILE
        self._ensure_encryption_key()
    
    def _ensure_encryption_key(self):
        """Create encryption key if it doesn't exist"""
        if not self.key_file.exists():
            key = Fernet.generate_key()
            self.key_file.write_bytes(key)
            self.key_file.chmod(0o600)  # Read/write for owner only
    
    def _get_cipher(self) -> Fernet:
        """Get Fernet cipher instance"""
        key = self.key_file.read_bytes()
        return Fernet(key)
    
    def _encrypt_password(self, password: str) -> str:
        """Encrypt password"""
        if not password:
            return ""
        cipher = self._get_cipher()
        encrypted = cipher.encrypt(password.encode())
        return base64.b64encode(encrypted).decode()
    
    def _decrypt_password(self, encrypted_password: str) -> str:
        """Decrypt password"""
        if not encrypted_password:
            return ""
        try:
            cipher = self._get_cipher()
            decrypted = cipher.decrypt(base64.b64decode(encrypted_password))
            return decrypted.decode()
        except Exception as e:
            print(f"Decryption error: {e}")
            return ""
    
    def get_default_config(self) -> Dict[str, Any]:
        """Get default configuration"""
        return {
            "version": "1.0",
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "database": {
                "host": "farforre.mysql.tools",
                "port": 3306,
                "user": "farforre_db",
                "password": "",  # Will be encrypted
                "database": "farforre_db",
                "prefix": "oc_"
            },
            "mapping": {
                "orders_table": "oc_order",
                "order_products_table": "oc_order_product",
                "order_dates_table": "oc_order_simple_fields",
                "products_table": "oc_product",
                "product_descriptions_table": "oc_product_description",
                "customers_table": "oc_customer",
                "status_field": "order_status_id",
                "pending_statuses": [2],
                "confirmed_statuses": [19],
                "on_rent_statuses": [24],
                "returned_statuses": [25],
                "completed_statuses": [13],
                "issue_date_field": "rent_issue_date",
                "return_date_field": "rent_return_date",
                "product_article_field": "model",
                "product_ean_field": "ean"
            },
            "company": {
                "name": "Rental Hub",
                "address": "",
                "phone": "",
                "email": None,
                "currency": "UAH",
                "tax_rate": 0.0
            }
        }
    
    def load_config(self) -> Dict[str, Any]:
        """Load configuration from file"""
        if not self.config_file.exists():
            return self.get_default_config()
        
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # Decrypt password
            if config.get('database', {}).get('password'):
                config['database']['password'] = self._decrypt_password(
                    config['database']['password']
                )
            
            return config
        except Exception as e:
            print(f"Error loading config: {e}")
            return self.get_default_config()
    
    def save_config(self, config: Dict[str, Any]) -> bool:
        """Save configuration to file (encrypts password)"""
        try:
            # Make a copy to avoid modifying original
            config_to_save = json.loads(json.dumps(config))
            
            # Encrypt password before saving
            if config_to_save.get('database', {}).get('password'):
                config_to_save['database']['password'] = self._encrypt_password(
                    config_to_save['database']['password']
                )
            
            # Update timestamp
            config_to_save['updated_at'] = datetime.utcnow().isoformat()
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config_to_save, f, indent=2, ensure_ascii=False)
            
            return True
        except Exception as e:
            print(f"Error saving config: {e}")
            return False
    
    def get_database_url(self, config: Optional[Dict[str, Any]] = None) -> str:
        """Get database URL from config"""
        if config is None:
            config = self.load_config()
        
        db = config.get('database', {})
        return (
            f"mysql+pymysql://{db.get('user')}:{db.get('password')}@"
            f"{db.get('host')}:{db.get('port')}/{db.get('database')}"
            f"?charset=utf8mb4"
        )
    
    def test_connection(self, db_config: Dict[str, Any]) -> Dict[str, Any]:
        """Test database connection"""
        import pymysql
        
        try:
            connection = pymysql.connect(
                host=db_config.get('host'),
                port=db_config.get('port', 3306),
                user=db_config.get('user'),
                password=db_config.get('password'),
                database=db_config.get('database'),
                charset='utf8mb4',
                connect_timeout=5
            )
            
            with connection.cursor() as cursor:
                cursor.execute("SELECT VERSION()")
                version = cursor.fetchone()[0]
            
            connection.close()
            
            return {
                "success": True,
                "message": "Connection successful",
                "version": version
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Connection failed: {str(e)}",
                "error": str(e)
            }
    
    def detect_opencart_tables(self, db_config: Dict[str, Any]) -> Dict[str, Any]:
        """Auto-detect OpenCart tables"""
        import pymysql
        
        try:
            connection = pymysql.connect(
                host=db_config.get('host'),
                port=db_config.get('port', 3306),
                user=db_config.get('user'),
                password=db_config.get('password'),
                database=db_config.get('database'),
                charset='utf8mb4',
                cursorclass=pymysql.cursors.DictCursor
            )
            
            prefix = db_config.get('prefix', 'oc_')
            detected = {
                "tables": [],
                "suggestions": {}
            }
            
            with connection.cursor() as cursor:
                # Get all tables with prefix
                cursor.execute(f"SHOW TABLES LIKE '{prefix}%'")
                tables = [list(row.values())[0] for row in cursor.fetchall()]
                detected['tables'] = tables
                
                # Suggest mappings based on common OpenCart names
                suggestions = {}
                
                if f"{prefix}order" in tables:
                    suggestions['orders_table'] = f"{prefix}order"
                    
                    # Get columns
                    cursor.execute(f"SHOW COLUMNS FROM {prefix}order")
                    columns = [row['Field'] for row in cursor.fetchall()]
                    
                    if 'order_status_id' in columns:
                        suggestions['status_field'] = 'order_status_id'
                
                if f"{prefix}order_product" in tables:
                    suggestions['order_products_table'] = f"{prefix}order_product"
                
                if f"{prefix}product" in tables:
                    suggestions['products_table'] = f"{prefix}product"
                    
                    cursor.execute(f"SHOW COLUMNS FROM {prefix}product")
                    columns = [row['Field'] for row in cursor.fetchall()]
                    
                    if 'model' in columns:
                        suggestions['product_article_field'] = 'model'
                
                if f"{prefix}customer" in tables:
                    suggestions['customers_table'] = f"{prefix}customer"
                
                # Look for rental date fields
                for table in tables:
                    if 'order' in table.lower() and 'simple' in table.lower():
                        suggestions['order_dates_table'] = table
                        
                        cursor.execute(f"SHOW COLUMNS FROM {table}")
                        columns = [row['Field'] for row in cursor.fetchall()]
                        
                        for col in columns:
                            if 'issue' in col.lower() or 'start' in col.lower():
                                suggestions['issue_date_field'] = col
                            if 'return' in col.lower() or 'end' in col.lower():
                                suggestions['return_date_field'] = col
                
                detected['suggestions'] = suggestions
            
            connection.close()
            
            return {
                "success": True,
                "detected": detected
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Detection failed: {str(e)}",
                "error": str(e)
            }


# Global instance
config_manager = ConfigManager()
