# AI Analyzer — `src/ai/ai_analyzer.py`

## Description

AI Vision analysis and marketing script generation using Claude.

## Classes

| Class | Description |
|-------|-------------|
| `SceneScript` | Dataclass for a single scene's script. |
| `VideoScript` | Dataclass for complete video script. |

**SceneScript fields:**
- `media_path` — Path to source media
- `description` — Scene description
- `voiceover` — Voiceover script text
- `caption` — On-screen caption
- `duration` — Scene duration (seconds)
- `is_video` — Whether source is video

**VideoScript fields:**
- `title` — Video title
- `scenes` — List of `SceneScript`
- `tone` — Script tone
- `target_audience` — Target audience

## Functions

| Function | Description |
|----------|-------------|
| `analyze_media_files()` | Analyzes all media files (images + videos) and generates a cohesive marketing script. |
| `analyze_screenshots()` | Legacy function. Analyzes screenshots and generates marketing script. |
| `regenerate_scene_script()` | Regenerates script for a single scene with optional feedback. |

## Dependencies
- `anthropic` (Claude API — model: `claude-sonnet-4-20250514`)
- `rich`, `PIL Image`

## Usage
```python
from src.ai.ai_analyzer import analyze_media_files
from src.pipeline.screenshot_handler import get_media_files

media = get_media_files("./content/")
script = analyze_media_files(media, product_name="My App", tone="energetic")

for scene in script.scenes:
    print(scene.voiceover)
```
