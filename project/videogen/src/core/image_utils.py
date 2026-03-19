"""
Image Utilities
Image processing, encoding, and dimension utilities.
Consolidates image-related functions from multiple modules.
"""

import base64
from io import BytesIO
from pathlib import Path
from typing import Tuple
from PIL import Image


def image_to_base64(image_path: Path) -> str:
    """
    Convert image file to base64 string for API calls.

    Args:
        image_path: Path to image file

    Returns:
        Base64-encoded string
    """
    with open(image_path, "rb") as f:
        return base64.standard_b64encode(f.read()).decode("utf-8")


def pil_image_to_base64(img: Image.Image, format: str = "PNG") -> str:
    """
    Convert PIL Image to base64 string.

    Args:
        img: PIL Image object
        format: Image format (PNG, JPEG, etc.)

    Returns:
        Base64-encoded string
    """
    buffer = BytesIO()
    img.save(buffer, format=format)
    return base64.standard_b64encode(buffer.getvalue()).decode("utf-8")


def get_mime_type(image_path: Path) -> str:
    """
    Get MIME type for image based on file extension.

    Args:
        image_path: Path to image file

    Returns:
        MIME type string (e.g., 'image/png', 'image/jpeg')
    """
    ext = image_path.suffix.lower()
    media_types = {
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.webp': 'image/webp',
        '.gif': 'image/gif',
        '.bmp': 'image/bmp',
    }
    return media_types.get(ext, 'image/png')


def get_image_media_type(image_path: Path) -> str:
    """
    Legacy alias for get_mime_type.
    Get media type for image based on extension.
    """
    return get_mime_type(image_path)


def resize_image_for_api(image_path: Path, max_size: int = 1568) -> Tuple[str, str]:
    """
    Resize image if needed for API (Claude has size limits).

    Args:
        image_path: Path to image file
        max_size: Maximum dimension (width or height)

    Returns:
        Tuple of (base64_data, media_type)
    """
    img = Image.open(image_path)

    # Resize if larger than max_size on any dimension
    if max(img.size) > max_size:
        ratio = max_size / max(img.size)
        new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
        img = img.resize(new_size, Image.Resampling.LANCZOS)

        # Save to bytes
        buffer = BytesIO()
        img_format = 'PNG' if image_path.suffix.lower() == '.png' else 'JPEG'
        img.save(buffer, format=img_format)
        base64_data = base64.standard_b64encode(buffer.getvalue()).decode("utf-8")
        media_type = 'image/png' if img_format == 'PNG' else 'image/jpeg'
    else:
        base64_data = image_to_base64(image_path)
        media_type = get_mime_type(image_path)

    return base64_data, media_type


def resize_pil_image_for_api(img: Image.Image, max_size: int = 1568) -> Tuple[str, str]:
    """
    Resize PIL Image if needed for API.

    Args:
        img: PIL Image object
        max_size: Maximum dimension (width or height)

    Returns:
        Tuple of (base64_data, media_type)
    """
    if max(img.size) > max_size:
        ratio = max_size / max(img.size)
        new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
        img = img.resize(new_size, Image.Resampling.LANCZOS)

    buffer = BytesIO()
    img.save(buffer, format='JPEG')
    base64_data = base64.standard_b64encode(buffer.getvalue()).decode("utf-8")
    return base64_data, 'image/jpeg'


def get_image_dimensions(image_path: Path) -> Tuple[int, int]:
    """
    Get image dimensions (width, height).

    Args:
        image_path: Path to image file

    Returns:
        Tuple of (width, height)
    """
    with Image.open(image_path) as img:
        return img.size
