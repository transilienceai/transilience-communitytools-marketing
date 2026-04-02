# Video Assembler — `src/pipeline/video_assembler.py`

## Description

Stitches images/videos, adds captions, syncs audio, and overlays music into a final video.

## Classes

| Class | Description |
|-------|-------------|
| `SceneConfig` | Dataclass for a single scene configuration. |

**SceneConfig fields:**
- `media_path` — Path to image or video
- `audio_path` — Path to voiceover audio
- `caption` — On-screen caption text
- `duration` — Scene duration (seconds)
- `is_video` — Whether source is video

## Functions

| Function | Description |
|----------|-------------|
| `assemble_video()` | Main function. Assembles all scenes into final video. Concatenates clips with `method="compose"`, adds background music with fade-out, exports H.264 + AAC format. |
| `create_scene_clip()` | Creates video clip for a single scene. Supports static images and video clips. Resizes to target resolution. Adds 0.3s fade transitions. |
| `create_caption_clip()` | Creates caption clip with semi-transparent background. Positions: `bottom`, `top`, `center`. |
| `get_recommended_size()` | Gets recommended video size based on first media file's aspect ratio. Landscape: `(1920, 1080)`, Portrait: `(1080, 1920)`, Square: `(1080, 1080)`. |

## Dependencies
- `moviepy`, `PIL Image`, `src.core.audio_utils`

## Usage
```python
from src.pipeline.video_assembler import assemble_video, SceneConfig

scenes = [
    SceneConfig(Path("01.png"), Path("01.mp3"), "Introduction", 8.0, False),
    SceneConfig(Path("02.png"), Path("02.mp3"), "Features", 10.0, False),
]

assemble_video(scenes, Path("output.mp4"), music_path=Path("bg.mp3"))
```
