# Video Extractors — `src/processing/video_extractors.py`

## Description

Frame and keyframe extraction utilities using FFmpeg.

## Functions

### `extract_keyframes(video_path, output_dir, max_frames=5) -> List[Path]`
Extracts evenly-spaced keyframes from video. Quality: `-q:v 2` (high quality JPEG). Returns list of keyframe image paths.

### `extract_last_frame(video_path, output_path) -> Path`
Extracts last frame of video as JPEG image. Used to chain Veo scenes: last frame of scene N becomes input for scene N+1. Uses `-sseof` for reliable end-seeking with fallback.

### `extract_frame_at_time(video_path, timestamp, output_path) -> Path`
Extracts single frame at specific timestamp. Raises `RuntimeError` if extraction fails.

## Dependencies
- `subprocess` (FFmpeg)
- `src.core.video_utils` (get_duration)

## Usage
```python
from src.processing.video_extractors import extract_keyframes, extract_last_frame

# Get keyframes for analysis
frames = extract_keyframes(Path("video.mp4"), Path("./frames/"), max_frames=5)

# Get last frame for Veo scene chaining
last = extract_last_frame(Path("scene_01.mp4"), Path("last_frame.jpg"))
```
