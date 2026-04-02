# Video Effects — `src/processing/video_effects.py`

## Description

Cinematic effects including zoom, pan, color grading, transitions using FFmpeg.

## Functions

### `apply_cinematic_effects(video_path, movement_segments, output_path) -> Path`
Applies single-pass cinematic effects via FFmpeg filter chains:

- **Zoom pulses** — `scale eval=frame` every 12 seconds
- **Smooth black dips** — Gaussian curves every 12 seconds
- **Alternating pattern** — Zoom + dip at even flashes, dip-only at odd
- **Vertical drift** — Sine wave (0.3 rad/s, ~21s period)
- **Color grading** — Brightness +0.02, saturation x1.08
- **Vignette** — Subtle vignette effect
- **Fade in/out** — 0.6s fade in, 0.8s fade out

Returns path to output video with effects (or original path if effects fail).

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
