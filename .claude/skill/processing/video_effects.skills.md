# Video Effects — `src/processing/video_effects.py`

## Description

Cinematic effects including zoom, pan, color grading, transitions using FFmpeg.

## Functions

| Function | Description |
|----------|-------------|
| `apply_cinematic_effects()` | Applies single-pass cinematic effects via FFmpeg filter chains: zoom pulses every 12s, smooth black dips, alternating zoom+dip pattern, vertical sine wave drift, brightness/saturation color grading, vignette, and fade in/out. Returns path to output video (or original path if effects fail). |

## Dependencies
- `subprocess` (FFmpeg), `shutil`
- `src.core.video_utils` (get_duration, get_video_dimensions)

## Usage
```python
from src.processing.video_effects import apply_cinematic_effects

# Apply effects after cleaning
result = apply_cinematic_effects(
    Path("cleaned.mp4"),
    [(0, 5.2), (8.1, 15.0), (18.3, 25.0)],  # movement segments
    Path("cinematic.mp4")
)
```
