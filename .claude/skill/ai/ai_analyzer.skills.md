# AI Analyzer — `src/ai/ai_analyzer.py`

## Description

AI Vision analysis and marketing script generation using Claude.

## Classes

### `SceneScript`
Dataclass for a single scene's script.
- `media_path` — Path to source media
- `description` — Scene description
- `voiceover` — Voiceover script text
- `caption` — On-screen caption
- `duration` — Scene duration (seconds)
- `is_video` — Whether source is video

### `VideoScript`
Dataclass for complete video script.
- `title` — Video title
- `scenes` — List of `SceneScript`
- `tone` — Script tone
- `target_audience` — Target audience

## Functions

### `analyze_media_files(media_files, product_name="", tone="professional and engaging", target_audience="general audience", additional_context="") -> VideoScript`
Analyzes all media files (images + videos) and generates a cohesive marketing script.

### `analyze_screenshots(image_paths, product_name="", tone="professional and engaging", target_audience="general audience", additional_context="") -> VideoScript`
Legacy function. Analyzes screenshots and generates marketing script.

### `regenerate_scene_script(scene, feedback="", tone="professional and engaging") -> SceneScript`
Regenerates script for a single scene with optional feedback.

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
