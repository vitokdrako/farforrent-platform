"""
Public file-serving route backed by Emergent object storage.

Everything uploaded via object storage lives behind this endpoint. The URL
pattern (`/api/files/<storage_path>`) is embedded directly in `products.image_url`,
`chat_messages.attachment_url`, damage photo records, etc., so that
`<img src="...">` works without any client-side signing.

Images are not sensitive today (same as the previous `/uploads/*` static mount
exposed every uploaded photo), so this route stays public to preserve the
existing frontend behaviour. If auth is later required, add the usual
Bearer / `?auth=` pattern — the playbook's download example covers it.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
import requests

from utils.object_storage import get_object

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/files", tags=["files"])


@router.get("/{path:path}")
async def download_file(path: str):
    """Stream an object out of the Emergent storage proxy."""
    try:
        data, content_type = get_object(path)
    except requests.HTTPError as e:
        status = e.response.status_code if e.response is not None else 500
        if status == 404:
            raise HTTPException(status_code=404, detail="File not found") from e
        logger.error("Object storage download failed (%s): %s", status, path)
        raise HTTPException(status_code=502, detail="Storage backend error") from e
    except Exception as e:
        logger.exception("Unexpected error downloading %s", path)
        raise HTTPException(status_code=500, detail=str(e)) from e

    # Cache aggressively — storage paths are content-addressed (UUID per upload),
    # so there is no cache invalidation concern.
    return Response(
        content=data,
        media_type=content_type,
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )
