# Veo Pipeline — `src/pipeline/veo_pipeline.py`

## Description

Main orchestrator. Complete marketing video pipeline using Google Veo 3.1 for high-quality video generation with Claude Vision analysis, TTS voiceover, and background music.

## Classes

### `SceneData`
- `image_path` — Source image path
- `script` — Voiceover script
- `extracted_text` — OCR text from image
- `text_regions` — Detected text region bounding boxes
- `video_path` — Generated video path
- `audio_path` — Generated audio path
- `duration` — Scene duration
- `is_video` — Whether source is video

## Analysis Functions

### `analyze_image_for_script_and_text(image_path, context="", tone="professional and engaging", api_key=None) -> Tuple[str, str]`
Analyzes image with Claude Vision. Returns `(voiceover_script, extracted_text)`.

### `analyze_image_for_script(image_path, context="", tone="professional and engaging", api_key=None) -> str`
Legacy function. Returns voiceover script only.

### `detect_text_regions_with_ai(image_path, api_key=None) -> List[dict]`
Uses Claude Vision to detect text regions with bounding boxes. Returns list of dicts with `text`, `x`, `y`, `width`, `height` (percentages).

### `polish_transcript(raw_transcript, context="", tone="professional and engaging", api_key=None) -> str`
Polishes raw transcript using Claude. Removes filler, fixes grammar, preserves all points and original order.

## Generation Functions

### `generate_motion_prompt(image_path, script) -> str`
Generates motion prompt for Veo based on image and script content (dashboard, button, team, product cues).

### `generate_veo_video(image_path, output_path, motion_prompt, script_text="", api_key=None, last_image_path=None) -> Path`
Generates video from image using Veo 3.1. Duration estimated from script length. Supports `last_image_path` for transitions.

### `generate_voiceover(script, output_path, engine="elevenlabs", voice="Smritika", api_key=None, speed=1.0) -> Tuple[Path, float]`
Generates voiceover for script. Returns `(audio_path, duration)`.

## Composition Functions

### `combine_video_with_audio(video_path, audio_path, output_path, audio_volume=5.0, original_audio_volume=0.3) -> Path`
Combines video with voiceover. Adjusts video speed to match audio duration. Mixes original audio (quiet) with voiceover (loud).

### `add_background_music_to_file(video_path, music_path, output_path, music_volume=0.03) -> Path`
Adds background music to video file. Loops music if shorter than video.

### `overlay_original_text_on_video(video_path, original_image_path, text_regions, output_path) -> Path`
Overlays original image's text regions onto Veo video. Uses heavy feathering.

### `_extract_final_audio(video_path, audio_output_path) -> Path`
Extracts audio from final video as high-quality MP3 (44.1kHz stereo, 192kbps).

## Utility Functions

### `estimate_speech_duration(text, words_per_minute=150) -> float`
Estimates spoken duration of text (clamped 5-8s for Veo).

### `estimate_script_duration(text, words_per_minute=150) -> float`
Estimates unclamped spoken duration for logging.

## Pipeline Functions

### `_generate_veo_scene(scene, index, temp_dir, semaphore, next_image_path=None, next_extracted_text="")` (async)
Generates a single Veo scene respecting concurrency semaphore. Passes next scene's image for smooth transitions.

### `_generate_veo_scenes_parallel(scenes, temp_dir, max_concurrent=3)` (async)
Generates all Veo scenes in parallel with concurrency cap.

### `create_marketing_video_veo(input_path, output_path, tts_engine="elevenlabs", voice="Smritika", music_path=None, music_volume=0.03, voice_volume=5.0, context="", tone="professional and engaging", resolution="1080p", max_concurrent_veo=3, voice_speed=1.0) -> Path`
**Main pipeline function.** Complete flow:
1. Scan & sort media files
2. Analyze with Claude Vision (script + OCR)
3. Generate Veo videos (parallel)
4. Generate voiceovers (TTS)
5. Combine video + audio per scene
6. Normalize resolution
7. Concatenate all scenes
8. Add background music
9. Extract audio as separate MP3

**Output:** `output.mp4` (video) + `output.mp3` (audio)

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
