from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from fastapi.responses import FileResponse
from typing import List, Optional
from sqlalchemy.orm import Session
import uuid
import os
from datetime import datetime
import shutil

from database import get_db
from models_sqlalchemy import DecorPhoto

router = APIRouter(prefix="/api/photos", tags=["photos"])

# Використовуємо папку uploads в межах проекту
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads", "photos")
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/upload")
async def upload_photo(
    entity_type: str,
    entity_id: str,
    photo_type: str = "general",
    sku: Optional[str] = None,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    photo_id = f"PHOTO-{str(uuid.uuid4())[:12].upper()}"
    file_ext = os.path.splitext(file.filename)[1]
    filename = f"{photo_id}{file_ext}"
    filepath = os.path.join(UPLOAD_DIR, filename)
    
    with open(filepath, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    file_size = os.path.getsize(filepath)
    
    new_photo = DecorPhoto(
        id=photo_id,
        entity_type=entity_type,
        entity_id=entity_id,
        sku=sku,
        photo_type=photo_type,
        filename=filename,
        filepath=filepath,
        file_size=file_size,
        mime_type=file.content_type,
        uploaded_at=datetime.now()
    )
    
    db.add(new_photo)
    db.commit()
    
    return {
        "id": photo_id,
        "filename": filename,
        "url": f"/api/photos/{photo_id}",
        "size": file_size
    }

@router.get("/{photo_id}")
async def get_photo(photo_id: str, db: Session = Depends(get_db)):
    photo = db.query(DecorPhoto).filter(DecorPhoto.id == photo_id).first()
    
    if not photo or not os.path.exists(photo.filepath):
        raise HTTPException(status_code=404, detail="Photo not found")
    
    return FileResponse(photo.filepath, media_type=photo.mime_type)

@router.get("/by-entity/{entity_type}/{entity_id}")
async def get_photos_by_entity(
    entity_type: str,
    entity_id: str,
    db: Session = Depends(get_db)
):
    photos = db.query(DecorPhoto).filter(
        DecorPhoto.entity_type == entity_type,
        DecorPhoto.entity_id == entity_id
    ).all()
    
    return [
        {
            "id": photo.id,
            "url": f"/api/photos/{photo.id}",
            "type": photo.photo_type,
            "sku": photo.sku,
            "uploaded_at": photo.uploaded_at.isoformat()
        }
        for photo in photos
    ]

@router.delete("/{photo_id}")
async def delete_photo(photo_id: str, db: Session = Depends(get_db)):
    photo = db.query(DecorPhoto).filter(DecorPhoto.id == photo_id).first()
    
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")
    
    if os.path.exists(photo.filepath):
        os.remove(photo.filepath)
    
    db.delete(photo)
    db.commit()
    
    return {"message": "Photo deleted successfully"}