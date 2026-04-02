# Text Animator — `src/generators/text_animator.py`

## Description

Creates engaging animations with cursor movement, text highlighting, and zoom effects synced to voiceover audio. Uses Gemini Vision to detect text regions.

## Data Classes

| Class | Description |
|-------|-------------|
| `TextRegion` | Detected text region: `text`, `x`, `y`, `width`, `height`, `center_x`, `center_y`. |
| `AnimationKeyframe` | Animation keyframe: `time` (seconds), `x`, `y`, `text`, `highlight` (bool), `zoom` (float). |

## Functions

| Function | Description |
|----------|-------------|
| `create_animated_scene()` | Main entry point. Analyzes image for text regions, creates keyframes synced to audio duration, renders animated video with cursor/highlight/zoom, then combines with audio. |
| `analyze_image_for_text_regions()` | Uses Gemini Vision to find text regions in an image. Returns coordinates as pixel positions. Falls back to `_estimate_text_regions()` on failure. |
| `create_animation_keyframes()` | Distributes attention across text regions over audio duration. Creates entry + settle keyframes per region with subtle zoom (1.15-1.2x). |
| `apply_text_animation()` | Renders frame-by-frame video with ease-out cursor interpolation, pulsing yellow highlight, and zoom-to-cursor effects. Uses MoviePy VideoClip. |
| `create_cursor_image()` | Generates a white arrow cursor PNG with black outline. |
| `create_highlight_overlay()` | Generates a semi-transparent highlight rectangle PNG. |

## Dependencies
- `moviepy`, `PIL`, `numpy`, Gemini Vision (via `gemini_client`)

## Usage
```python
from src.generators.text_animator import create_animated_scene

create_animated_scene(
    image_path=Path("screenshot.png"),
    script_text="Check out our powerful dashboard...",
    audio_path=Path("voiceover.mp3"),
    output_path=Path("animated.mp4"),
)
```
