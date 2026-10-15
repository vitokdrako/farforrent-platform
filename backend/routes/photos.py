from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from fastapi.responses import Response
from typing import Optional
from sqlalchemy.orm import Session
import uuid
from datetime import datetime

from database import get_db
from models_sqlalchemy import DecorPhoto
from utils.object_storage import (
    put_object,
    get_object,
    build_storage_path,
    build_public_url,
    new_filename,
)

router = APIRouter(prefix="/api/photos", tags=["photos"])


@router.post("/upload")
async def upload_photo(
    entity_type: str,
    entity_id: str,
    photo_type: str = "general",
    sku: Optional[str] = None,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Завантажити фото в object storage, DecorPhoto.filepath зберігає storage_path."""
    photo_id = f"PHOTO-{str(uuid.uuid4())[:12].upper()}"

    filename = new_filename(file.filename, default_ext="jpg")
    storage_path = build_storage_path("photos", filename)

    contents = await file.read()
    upload_result = put_object(
        storage_path, contents, file.content_type or "application/octet-stream"
    )
    stored_path = upload_result["path"]
    file_size = upload_result.get("size", len(contents))

    new_photo = DecorPhoto(
        id=photo_id,
        entity_type=entity_type,
        entity_id=entity_id,
        sku=sku,
        photo_type=photo_type,
        filename=filename,
        filepath=stored_path,
        file_size=file_size,
        mime_type=file.content_type,
        uploaded_at=datetime.now(),
    )

    db.add(new_photo)
    db.commit()

    return {
        "id": photo_id,
        "filename": filename,
        "url": build_public_url(stored_path),
        "size": file_size,
    }


@router.get("/{photo_id}")
async def get_photo(photo_id: str, db: Session = Depends(get_db)):
    photo = db.query(DecorPhoto).filter(DecorPhoto.id == photo_id).first()
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")

    try:
        data, content_type = get_object(photo.filepath)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Photo not found: {e}")

    return Response(content=data, media_type=photo.mime_type or content_type)


@router.get("/by-entity/{entity_type}/{entity_id}")
async def get_photos_by_entity(
    entity_type: str,
    entity_id: str,
    db: Session = Depends(get_db),
):
    photos = db.query(DecorPhoto).filter(
        DecorPhoto.entity_type == entity_type,
        DecorPhoto.entity_id == entity_id,
    ).all()

    return [
        {
            "id": photo.id,
            "url": build_public_url(photo.filepath) if photo.filepath else "",
            "type": photo.photo_type,
            "sku": photo.sku,
            "uploaded_at": photo.uploaded_at.isoformat(),
        }
        for photo in photos
    ]


@router.delete("/{photo_id}")
async def delete_photo(photo_id: str, db: Session = Depends(get_db)):
    """
    Soft-delete: видаляємо запис з БД. Object storage не має delete API,
    тож файл залишається осиротілим — це нормальна поведінка для цього сховища.
    """
    photo = db.query(DecorPhoto).filter(DecorPhoto.id == photo_id).first()
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")

    db.delete(photo)
    db.commit()
    return {"message": "Photo deleted successfully"}
