# Post Processor — `src/processing/post_processor.py`

## Description

Video post-processing: speed adjustment, volume control, and audio remixing via FFmpeg.

## Functions

| Function | Description |
|----------|-------------|
| `adjust_video()` | Main entry point. Two modes: **Remix mode** (voice_audio provided) strips existing audio and mixes voice + music at specified volumes; **Simple mode** adjusts overall audio volume and/or video speed. Uses `-c:v copy` when only audio changes needed. Optionally extracts MP3 alongside output. |
| `build_atempo_chain()` | Build chained atempo filters for FFmpeg. Each filter limited to 0.5-2.0 range, so extreme speeds are chained (e.g., 4x = `atempo=2.0,atempo=2.0`). |
| `load_manifest()` | Load a pipeline manifest JSON file. |

## Internal Functions
- `_speed_only()` — Re-encode video + audio with setpts/atempo
- `_volume_only()` — Adjust volume with `-c:v copy` (no video re-encode)
- `_speed_and_volume()` — Both speed and volume (requires re-encode)
- `_remix_video()` — Strip audio, mix voice + music with volume control, optional speed
- `_extract_audio()` — Extract MP3 (44.1kHz stereo 192kbps)

## Dependencies
- FFmpeg (subprocess)
- `rich` (console output)

## Usage
```python
from src.processing.post_processor import adjust_video

# Simple volume adjustment (no re-encode)
adjust_video(Path("input.mp4"), Path("output.mp4"), overall_volume=2.0)

# Speed up 1.5x
adjust_video(Path("input.mp4"), Path("output.mp4"), video_speed=1.5)

# Remix voice + music
adjust_video(
    Path("input.mp4"), Path("output.mp4"),
    voice_audio=Path("voice.mp3"),
    music_audio=Path("music.mp3"),
    voice_volume=5.0,
    music_volume=0.03,
)
```
