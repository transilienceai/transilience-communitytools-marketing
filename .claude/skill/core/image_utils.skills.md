# Image Utils — `src/core/image_utils.py`

## Description

Image processing, encoding, and dimension utilities for API integration.

## Functions

### `image_to_base64(image_path) -> str`
Converts image file to base64 string for API calls.

### `pil_image_to_base64(img, format="PNG") -> str`
Converts PIL Image to base64 string.

### `get_mime_type(image_path) -> str`
Gets MIME type for image based on extension (e.g., `image/png`).

### `get_image_media_type(image_path) -> str`
Legacy alias for `get_mime_type`.

### `resize_image_for_api(image_path, max_size=1568) -> Tuple[str, str]`
Resizes image if needed for API (Claude size limits). Returns `(base64_data, media_type)`.

### `resize_pil_image_for_api(img, max_size=1568) -> Tuple[str, str]`
Resizes PIL Image if needed for API. Returns `(base64_data, media_type)`.

### `get_image_dimensions(image_path) -> Tuple[int, int]`
Gets image dimensions. Returns `(width, height)`.

## Dependencies
- `PIL Image`, `base64`, `io.BytesIO`

## Usage
```python
from src.core.image_utils import image_to_base64, resize_image_for_api, get_image_dimensions

# Encode for API
b64 = image_to_base64(Path("screenshot.png"))

# Resize for Claude Vision
data, media_type = resize_image_for_api(Path("large_image.png"))

# Get dimensions
w, h = get_image_dimensions(Path("image.jpg"))
```
