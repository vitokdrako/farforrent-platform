"""
🖼️ Image proxy - ЄДИНЕ ДЖЕРЕЛО ПРАВДИ для зображень
Тільки uploads/products/ - найвища якість

Використовується тільки для preview середовища
В production - прямий доступ до uploads через nginx
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
import logging
from pathlib import Path

router = APIRouter(prefix="/api/image-proxy", tags=["image-proxy"])
logger = logging.getLogger(__name__)

# Локальна директорія uploads
LOCAL_UPLOADS = Path("/app/backend/uploads")

@router.get("/{path:path}")
async def proxy_image(path: str):
    """
    Віддає зображення тільки з uploads/
    Якщо немає - повертає placeholder
    """
    try:
        # Тільки uploads/ - єдине джерело правди
        if path.startswith('uploads/'):
            local_path = LOCAL_UPLOADS / path.replace('uploads/', '')
            if local_path.exists() and local_path.is_file():
                logger.info(f"✅ Serving from uploads: {local_path}")
                return FileResponse(local_path)
            else:
                logger.warning(f"⚠️ Image not found in uploads: {path}")
                # Повертаємо placeholder
                return StreamingResponse(
                    iter([generate_placeholder_svg(path)]),
                    media_type="image/svg+xml",
                    headers={
                        "Cache-Control": "public, max-age=3600",
                        "Access-Control-Allow-Origin": "*"
                    }
                )
        else:
            # Якщо шлях не починається з uploads/ - це помилка
            logger.error(f"❌ Invalid image path (should start with 'uploads/'): {path}")
            raise HTTPException(status_code=400, detail="Image path must start with 'uploads/'")
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving image {path}: {type(e).__name__} - {str(e)}")
        return StreamingResponse(
            iter([generate_placeholder_svg(path)]),
            media_type="image/svg+xml"
        )


def generate_placeholder_svg(path: str) -> bytes:
    """
    Генерує placeholder SVG зображення для випадків коли справжнє зображення недоступне
    """
    # Отримати ім'я файлу з шляху
    filename = path.split('/')[-1] if '/' in path else path
    filename = filename[:20] + '...' if len(filename) > 20 else filename
    
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="400" height="400" viewBox="0 0 400 400">
  <rect width="400" height="400" fill="#f1f5f9"/>
  <text x="50%" y="45%" dominant-baseline="middle" text-anchor="middle" 
        font-family="Arial, sans-serif" font-size="16" fill="#64748b" font-weight="bold">
    Зображення недоступне
  </text>
  <text x="50%" y="55%" dominant-baseline="middle" text-anchor="middle" 
        font-family="Arial, sans-serif" font-size="12" fill="#94a3b8">
    {filename}
  </text>
  <circle cx="200" cy="170" r="30" fill="none" stroke="#cbd5e1" stroke-width="3"/>
  <circle cx="200" cy="170" r="8" fill="#cbd5e1"/>
  <path d="M 180 190 L 200 170 L 220 190" stroke="#cbd5e1" stroke-width="3" 
        fill="none" stroke-linecap="round" stroke-linejoin="round"/>
</svg>'''
    return svg.encode('utf-8')
