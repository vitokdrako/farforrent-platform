"""
Centralized image URL helper for backend
All product image URLs should be processed through this helper
"""

def normalize_image_url(image_path: str | None) -> str | None:
    """
    Convert image path from database to proper URL
    
    Args:
        image_path: Image path from database (can be relative or full URL)
        
    Returns:
        Full image URL or None
        
    Examples:
        - "static/images/products/image.jpg" -> "static/images/products/image.jpg"
        - "catalog/product/image.jpg" -> "static/images/catalog/product/image.jpg"
        - "https://example.com/image.jpg" -> "https://example.com/image.jpg"
        - None -> None
    """
    if not image_path:
        return None
    
    # Already a full URL or starts with static/, uploads/ or /
    if (image_path.startswith('http://') or 
        image_path.startswith('https://') or 
        image_path.startswith('static/') or
        image_path.startswith('uploads/') or  # ✅ Додано uploads/
        image_path.startswith('/')):
        return image_path
    
    # Relative path from old OpenCart structure - convert to new static path
    # Example: "catalog/product/image.jpg" -> "static/images/catalog/product/image.jpg"
    return f"static/images/{image_path}"


# ─── Serializers (single mapper layer) ────────────────────────────────
# Use these instead of calling normalize_image_url() inline at every row.
# Reasoning: prevents accidental shadowing (the "double /uploads/" bug
# was caused by a local def normalize_image_url that shadowed this import),
# guarantees frontend-friendly "" instead of None, and centralises future
# image rules (lazy thumbnails, CDN switches, fallbacks).

def serialize_product_image(image_path: str | None) -> str:
    """
    Canonical serializer for any single product/board/cart image field.
    Returns "" (never None) so JSON consumers can use a falsy check uniformly.
    """
    return normalize_image_url(image_path) or ""


def serialize_order_item_image(item_image: str | None,
                               product_fallback_image: str | None) -> str:
    """
    Order items have a per-row override (order_items.image_url) and a
    fallback to the product's current image. Prefer the per-row value.
    """
    return normalize_image_url(item_image or product_fallback_image) or ""
