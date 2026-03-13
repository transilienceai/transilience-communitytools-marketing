# Video Utils — `src/core/video_utils.py`

Core video metadata and probing utilities using ffprobe/ffmpeg.

## Functions

### `get_duration(file_path) -> float`
Gets duration of video or audio file in seconds. Tries format duration, then stream duration, then frame count fallback.

### `get_video_dimensions(video_path) -> Tuple[int, int]`
Gets video width and height, rounded to even numbers for encoding compatibility. Returns `(width, height)`.

### `get_video_fps(video_path) -> float`
Gets video frame rate using ffprobe. Returns fps (default 30.0).

### `probe_video(video_path, entries) -> str`
Generic ffprobe wrapper for extracting video metadata. Returns raw ffprobe output.

## Dependencies
- `subprocess` (ffprobe/ffmpeg)

## Usage
```python
from src.core.video_utils import get_duration, get_video_dimensions, get_video_fps

duration = get_duration(Path("video.mp4"))       # 45.2
w, h = get_video_dimensions(Path("video.mp4"))   # (1920, 1080)
fps = get_video_fps(Path("video.mp4"))            # 30.0
```
