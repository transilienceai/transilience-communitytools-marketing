# Imagen Generator — `src/ai/imagen_generator.py`

## Description

Google Imagen 4.0 image generation wrapper using the google-genai SDK.

## Functions

| Function | Description |
|----------|-------------|
| `generate_image()` | Generate an image from a text prompt. Saves as PNG. Creates parent dirs automatically. Handles multiple SDK response formats (image_bytes, data, PIL). Raises `RuntimeError` on failure. |

## Dependencies
- `google-genai` SDK (via `gemini_client.get_client()`)
- Requires `GOOGLE_API_KEY` env var

## Usage
```python
from src.ai.imagen_generator import generate_image

path = generate_image(
    "Holographic dashboard floating above a clean white desk",
    Path("output/scene_001.png"),
    aspect_ratio="16:9"
)
```
