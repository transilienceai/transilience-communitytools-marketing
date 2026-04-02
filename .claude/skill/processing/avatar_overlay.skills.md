# Avatar Overlay — `src/processing/avatar_overlay.py`

## Description

FFmpeg-based avatar compositing — overlays an image or video avatar on a corner of a video.

## Functions

### `overlay_avatar(input_video, avatar_source, output_video, position="bottom-right", scale=0.15, margin=20, opacity=1.0, border_radius=0, fps=30) -> Path`
Composite an avatar onto a video using FFmpeg's overlay filter.

- **Image avatars** (.png/.jpg): Scaled to `scale * video_width`, supports opacity via `colorchannelmixer`
- **Video avatars** (.mp4/.mov): Scaled and looped to match main video duration, uses `shortest=1`
- **Positions**: top-left, top-right, bottom-left, bottom-right
- Uses ffprobe to get main video dimensions
- Output: H.264, AAC 192kbps, configurable FPS

## CLI Command
```bash
python cli.py avatar video.mp4 avatar.png -o output.mp4 \
    --position bottom-right --scale 0.15 --opacity 1.0 --margin 20
```

## Web UI Endpoint
`POST /avatar` — Receives video + avatar file via multipart form, returns base64 video.

## Dependencies
- FFmpeg, ffprobe (subprocess)

## Usage
```python
from src.processing.avatar_overlay import overlay_avatar

overlay_avatar(
    input_video=Path("video.mp4"),
    avatar_source=Path("avatar.png"),
    output_video=Path("video_with_avatar.mp4"),
    position="bottom-right",
    scale=0.15,
    opacity=0.9,
)
```
