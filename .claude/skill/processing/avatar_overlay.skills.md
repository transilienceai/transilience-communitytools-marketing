# Avatar Overlay — `src/processing/avatar_overlay.py`

## Description

FFmpeg-based avatar compositing — overlays an image or video avatar on a corner of a video.

## Functions

| Function | Description |
|----------|-------------|
| `overlay_avatar()` | Composite an avatar onto a video using FFmpeg's overlay filter. Image avatars (.png/.jpg) scaled to `scale * video_width`, supports opacity via `colorchannelmixer`. Video avatars (.mp4/.mov) scaled and looped to match main video duration. Positions: top-left, top-right, bottom-left, bottom-right. Output: H.264, AAC 192kbps. |

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
