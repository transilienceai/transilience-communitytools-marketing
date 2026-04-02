# Veo Generator — `src/ai/veo_generator.py`

## Description

Google Veo 3.1 video generation from text prompts or images.

## Functions

| Function | Description |
|----------|-------------|
| `generate_video_veo()` | Generate video from text prompt or image using Veo 3.1. Supports image-to-video with optional last frame for transitions. |
| `generate_video_from_images_veo()` | Generate video from multiple images. Uses first image as animation base. |
| `animate_image_veo()` | Animate a static image with cinematic motion using Veo 3.1. |
| `list_veo_models()` | List available Veo models with capabilities. |

## Models
- `veo-3.1-generate-preview` — Full quality
- `veo-3.1-fast-generate-preview` — Faster, lower quality

## Dependencies
- `requests`, `PIL Image`, `dotenv`
- API base: `https://generativelanguage.googleapis.com/v1beta`
- Requires `GOOGLE_API_KEY` env var

## Usage
```python
from src.ai.veo_generator import generate_video_veo, animate_image_veo

# Text-to-video
generate_video_veo("A sunrise over mountains", Path("sunrise.mp4"))

# Image-to-video
generate_video_veo(
    "gentle zoom with cinematic motion",
    Path("animated.mp4"),
    image_path=Path("screenshot.png"),
    resolution="1080p"
)

# Simple image animation
animate_image_veo(Path("image.png"), Path("output.mp4"))
```
