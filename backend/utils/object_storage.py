"""
Emergent Object Storage client.

Replaces ephemeral pod-local file writes (`uploads/...`) with persistent object storage
that survives deploys / pod restarts and is accessible from the deployed environment.

Usage:
    from utils.object_storage import put_object, get_object, build_public_url

    # In an upload endpoint:
    data = await file.read()
    path = build_storage_path("products", f"{uuid.uuid4().hex}.jpg")
    put_object(path, data, file.content_type or "image/jpeg")
    url = build_public_url(path)   # -> "/api/files/<app>/products/<uuid>.jpg"
    # Save `url` into DB; frontend hits GET /api/files/{path:path} to render it.
"""
from __future__ import annotations

import os
import logging
import threading
import uuid
from typing import Tuple

import requests

logger = logging.getLogger(__name__)

# ───────────────────────── Config ─────────────────────────
_STORAGE_BASE = (os.environ.get("INTEGRATION_PROXY_URL") or "").strip() or "https://integrations.emergentagent.com"
STORAGE_URL = _STORAGE_BASE.rstrip("/") + "/objstore/api/v1/storage"
EMERGENT_KEY = os.environ.get("EMERGENT_LLM_KEY")

# All stored paths are prefixed with the app name to isolate the bucket per deployment.
APP_NAME = os.environ.get("OBJECT_STORAGE_APP_NAME", "rentalhub")

# Module-level cached storage key; populated by `init_storage()`.
_storage_key: str | None = None
_init_lock = threading.Lock()


def init_storage() -> str:
    """
    Lazily authenticates with the Emergent object-storage proxy and caches
    the session-scoped storage key.

    Idempotent and safe to call from any request path (double-checked locking).
    """
    global _storage_key
    if _storage_key:
        return _storage_key

    with _init_lock:
        if _storage_key:  # someone else beat us to it
            return _storage_key
        if not EMERGENT_KEY:
            raise RuntimeError(
                "EMERGENT_LLM_KEY is not set in backend/.env — object storage cannot init"
            )
        resp = requests.post(
            f"{STORAGE_URL}/init",
            json={"emergent_key": EMERGENT_KEY},
            timeout=30,
        )
        resp.raise_for_status()
        _storage_key = resp.json()["storage_key"]
        logger.info("Object storage initialized")
        return _storage_key


def put_object(path: str, data: bytes, content_type: str) -> dict:
    """Upload a byte payload. Returns {"path": "...", "size": N, "etag": "..."}."""
    key = init_storage()
    resp = requests.put(
        f"{STORAGE_URL}/objects/{path}",
        headers={"X-Storage-Key": key, "Content-Type": content_type},
        data=data,
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()


def get_object(path: str) -> Tuple[bytes, str]:
    """Download an object. Returns (bytes, content-type)."""
    key = init_storage()
    resp = requests.get(
        f"{STORAGE_URL}/objects/{path}",
        headers={"X-Storage-Key": key},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.content, resp.headers.get("Content-Type", "application/octet-stream")


# ───────────────────────── Helpers ─────────────────────────
def build_storage_path(folder: str, filename: str) -> str:
    """
    Build the canonical object-storage path.

    Example:
        build_storage_path("products", "ab12cd.jpg")
        -> "rentalhub/products/ab12cd.jpg"
    """
    folder = folder.strip("/")
    filename = filename.lstrip("/")
    return f"{APP_NAME}/{folder}/{filename}"


def build_public_url(storage_path: str) -> str:
    """
    Build the URL the frontend uses to render / download the file.

    Example:
        build_public_url("rentalhub/products/ab12.jpg")
        -> "/api/files/rentalhub/products/ab12.jpg"
    """
    return f"/api/files/{storage_path.lstrip('/')}"


def new_filename(original_filename: str | None, default_ext: str = "bin") -> str:
    """Generate a collision-free filename, preserving the original extension when possible."""
    ext = default_ext
    if original_filename and "." in original_filename:
        ext = original_filename.rsplit(".", 1)[-1].lower() or default_ext
    return f"{uuid.uuid4().hex}.{ext}"
