# Video Cleaner — `src/processing/video_cleaner.py`

## Description

Motion detection and still frame removal utilities.

## Functions

### `clean_video(video_path, output_path=None) -> Tuple[Path, List[Tuple[float, float]]]`
Main function. Removes still/repetitive frames by detecting stillness periods. Uses FFmpeg concat demuxer to extract and stitch movement segments.
- Returns `(cleaned_video_path, movement_segments)`
- `movement_segments`: list of `(start, end)` time ranges kept

### `analyze_motion(video_path) -> Tuple[float, float, List[Tuple[float, float]]]`
Analyzes frame-to-frame motion using OpenCV. Downscales (0.1x) and blurs for efficiency. Samples every 6 frames.
- Returns `(fps, duration, motion_data)`
- `motion_data`: list of `(timestamp, motion_percentage)` tuples

### `find_stillness_periods(motion, threshold=0.005, min_duration=1.5) -> List[Tuple[float, float, float]]`
Finds periods where motion is below threshold.
- Returns list of `(start, end, duration)` tuples for still periods

## Dependencies
- `cv2` (OpenCV), `numpy`, `subprocess` (FFmpeg), `tempfile`

## Usage
```python
from src.processing.video_cleaner import clean_video

# Remove still frames from recording
cleaned_path, segments = clean_video(Path("recording.mp4"))
print(f"Kept {len(segments)} movement segments")
```
