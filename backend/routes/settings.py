"""
Settings API for Rental Hub Universal Tool
Handles configuration management, database connection testing, and auto-detection
"""
from fastapi import APIRouter, HTTPException, status
from models import (
    AppConfig, AppConfigUpdate, ConnectionTestRequest, ConnectionTestResponse,
    DetectTablesRequest, DetectTablesResponse
)
from config_manager import config_manager
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/settings", tags=["settings"])



@router.get("", response_model=AppConfig)
async def get_settings():
    """
    Get current application configuration
    
    Returns decrypted configuration (password is decrypted for editing)
    """
    try:
        config = config_manager.load_config()
        return config
    except Exception as e:
        logger.error(f"Error loading settings: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load settings: {str(e)}"
        )



@router.post("", response_model=Dict[str, Any])
async def save_settings(config_update: AppConfigUpdate):
    """
    Save application configuration
    
    Password will be encrypted before saving to file
    """
    try:
        # Load current config
        current_config = config_manager.load_config()
        
        # Update with new values
        if config_update.database:
            current_config['database'] = config_update.database.dict()
        
        if config_update.mapping:
            current_config['mapping'] = config_update.mapping.dict()
        
        if config_update.company:
            current_config['company'] = config_update.company.dict()
        
        # Save (password will be encrypted)
        success = config_manager.save_config(current_config)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to save configuration"
            )
        
        return {
            "success": True,
            "message": "Configuration saved successfully",
            "config": current_config
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving settings: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save settings: {str(e)}"
        )



@router.post("/test-connection", response_model=ConnectionTestResponse)
async def test_connection(request: ConnectionTestRequest):
    """
    Test database connection with provided credentials
    
    Returns connection status and MySQL version if successful
    """
    try:
        db_config = request.dict()
        result = config_manager.test_connection(db_config)
        
        return ConnectionTestResponse(**result)
    except Exception as e:
        logger.error(f"Error testing connection: {e}")
        return ConnectionTestResponse(
            success=False,
            message="Connection test failed",
            error=str(e)
        )



@router.post("/detect-tables", response_model=DetectTablesResponse)
async def detect_tables(request: DetectTablesRequest):
    """
    Auto-detect OpenCart tables and suggest field mappings
    
    Analyzes database structure and returns:
    - List of all tables with specified prefix
    - Suggested mappings based on common OpenCart patterns
    - Available columns for each relevant table
    """
    try:
        db_config = request.dict()
        result = config_manager.detect_opencart_tables(db_config)
        
        return DetectTablesResponse(**result)
    except Exception as e:
        logger.error(f"Error detecting tables: {e}")
        return DetectTablesResponse(
            success=False,
            message="Table detection failed",
            error=str(e)
        )


@router.get("/database-url")
async def get_database_url():
    """
    Get current database connection URL (for debugging)
    
    Note: Password is masked in response
    """
    try:
        config = config_manager.load_config()
        db = config.get('database', {})
        
        # Mask password
        masked_url = (
            f"mysql+pymysql://{db.get('user')}:***@"
            f"{db.get('host')}:{db.get('port')}/{db.get('database')}"
        )
        
        return {
            "success": True,
            "url": masked_url,
            "config": {
                "host": db.get('host'),
                "port": db.get('port'),
                "database": db.get('database'),
                "user": db.get('user'),
                "prefix": db.get('prefix')
            }
        }
    except Exception as e:
        logger.error(f"Error getting database URL: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get database URL: {str(e)}"
        )


@router.post("/reset-to-defaults")
async def reset_to_defaults():
    """
    Reset configuration to default values
    
    WARNING: This will overwrite current configuration
    """
    try:
        default_config = config_manager.get_default_config()
        success = config_manager.save_config(default_config)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to reset configuration"
            )
        
        return {
            "success": True,
            "message": "Configuration reset to defaults",
            "config": default_config
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resetting configuration: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reset configuration: {str(e)}"
        )

