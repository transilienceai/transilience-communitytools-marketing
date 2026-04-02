# Veo Generator — `src/ai/veo_generator.py`

## Description

Google Veo 3.1 video generation from text prompts or images.

## Functions

### `generate_video_veo(prompt, output_path, image_path=None, last_image_path=None, duration=8, aspect_ratio="16:9", resolution="1080p", model="veo-3.1-generate-preview", api_key=None, enable_audio=True) -> Path`
Generates video using Veo 3.1 REST API. Supports text-to-video or image-to-video (with optional last frame for transitions). Polls for completion (max 10 minutes).

### `generate_video_from_images_veo(images, output_path, prompt="smooth cinematic transition between scenes", api_key=None, resolution="1080p") -> Path`
Generates video from multiple images. Uses first image as animation base.

### `animate_image_veo(image_path, output_path, motion_prompt="subtle natural motion, cinematic quality", duration=8, api_key=None) -> Path`
Animates a static image using Veo 3.1.

### `list_veo_models() -> dict`
Lists available Veo models with capabilities (resolutions, aspect ratios, features).

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
