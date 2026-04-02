# Veo Pipeline — `src/pipeline/veo_pipeline.py`

## Description

Main orchestrator. Complete marketing video pipeline using Google Veo 3.1 for high-quality video generation with Claude Vision analysis, TTS voiceover, and background music.

## Classes

| Class | Description |
|-------|-------------|
| `SceneData` | Dataclass for a single scene in the pipeline. |

**SceneData fields:**
- `image_path` — Source image path
- `script` — Voiceover script
- `extracted_text` — OCR text from image
- `text_regions` — Detected text region bounding boxes
- `video_path` — Generated video path
- `audio_path` — Generated audio path
- `duration` — Scene duration
- `is_video` — Whether source is video

## Analysis Functions

| Function | Description |
|----------|-------------|
| `analyze_image_for_script_and_text()` | Analyzes image with Claude Vision. Returns `(voiceover_script, extracted_text)`. |
| `analyze_image_for_script()` | Legacy function. Returns voiceover script only. |
| `detect_text_regions_with_ai()` | Uses Claude Vision to detect text regions with bounding boxes. Returns list of dicts with `text`, `x`, `y`, `width`, `height` (percentages). |
| `polish_transcript()` | Polishes raw transcript using Claude. Removes filler, fixes grammar, preserves all points and original order. |

## Generation Functions

| Function | Description |
|----------|-------------|
| `generate_motion_prompt()` | Generates motion prompt for Veo based on image and script content (dashboard, button, team, product cues). |
| `generate_veo_video()` | Generates video from image using Veo 3.1. Duration estimated from script length. Supports `last_image_path` for transitions. |
| `generate_voiceover()` | Generates voiceover for script. Returns `(audio_path, duration)`. |

## Composition Functions

| Function | Description |
|----------|-------------|
| `combine_video_with_audio()` | Combines video with voiceover. Adjusts video speed to match audio duration. Mixes original audio (quiet) with voiceover (loud). |
| `add_background_music_to_file()` | Adds background music to video file. Loops music if shorter than video. |
| `overlay_original_text_on_video()` | Overlays original image's text regions onto Veo video. Uses heavy feathering. |
| `_extract_final_audio()` | Extracts audio from final video as high-quality MP3 (44.1kHz stereo, 192kbps). |

## Utility Functions

| Function | Description |
|----------|-------------|
| `estimate_speech_duration()` | Estimates spoken duration of text (clamped 5-8s for Veo). |
| `estimate_script_duration()` | Estimates unclamped spoken duration for logging. |

## Pipeline Functions

| Function | Description |
|----------|-------------|
| `_generate_veo_scene()` | Generates a single Veo scene respecting concurrency semaphore. Passes next scene's image for smooth transitions. (async) |
| `_generate_veo_scenes_parallel()` | Generates all Veo scenes in parallel with concurrency cap. (async) |
| `create_marketing_video_veo()` | **Main pipeline function.** Complete flow: scan media, analyze with Claude Vision, generate Veo videos (parallel), generate voiceovers, combine video + audio, normalize resolution, concatenate, add music, extract audio MP3. |

## Dependencies
- `anthropic`, `moviepy`, `subprocess` (FFmpeg), `asyncio`
- `src.ai.veo_generator`, `src.ai.tts_engine`, `src.pipeline.screenshot_handler`

## Usage
```python
from src.pipeline.veo_pipeline import create_marketing_video_veo

# Full pipeline
output = create_marketing_video_veo(
    Path("./content/"),
    Path("output.mp4"),
    voice="Aman",
    music_path=Path("bg.mp3"),
    resolution="1080p",
    max_concurrent_veo=5
)
# Produces: output.mp4 + output.mp3
```
