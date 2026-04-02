# Screenshot Handler — `src/pipeline/screenshot_handler.py`

## Description

Media file loading, sorting, and PowerPoint slide extraction.

## Classes

| Class | Description |
|-------|-------------|
| `MediaType` | Enum: `IMAGE`, `VIDEO`, `POWERPOINT`. |
| `MediaFile` | Dataclass for a loaded media file. |

**MediaFile fields:**
- `path` — Path to media file
- `media_type` — `MediaType` enum
- `duration` — Duration (for videos)
- `slide_index` — Slide number (for PPTX)
- `original_pptx` — Original PPTX path (for extracted slides)

## Constants
- `IMAGE_EXTENSIONS`: `.png`, `.jpg`, `.jpeg`, `.webp`, `.gif`, `.bmp`
- `VIDEO_EXTENSIONS`: `.mp4`, `.mov`, `.avi`, `.mkv`, `.webm`, `.m4v`
- `PPTX_EXTENSIONS`: `.pptx`, `.ppt`

## Functions

| Function | Description |
|----------|-------------|
| `get_media_files()` | Main entry point. Gets sorted list of media files from directory or single file. Expands PowerPoint files into individual slides. |
| `extract_pptx_slides()` | Extracts PowerPoint slides as images. Converts via PDF (LibreOffice) for best quality. Falls back to python-pptx rendering. |
| `expand_pptx_to_media_files()` | Expands PowerPoint file into `MediaFile` objects for each slide. |
| `get_video_duration()` | Gets duration of video file in seconds. |
| `get_video_thumbnail()` | Extracts thumbnail frame from video for AI analysis. |
| `extract_video_frames()` | Extracts multiple frames at evenly spaced intervals. |
| `get_image_files()` | Legacy function. Gets image files from directory or single file. |
| `load_image()` | Loads image file and returns PIL Image. |
| `get_media_dimensions()` | Gets dimensions for any media file (image, video, or PPTX slide). Returns `(width, height)`. |
| `validate_media_files()` | Validates all media files can be loaded. |
| `validate_images()` | Legacy function. Validates images. |
| `render_slide_pdf2image()` | Renders single slide using LibreOffice + pdf2image. |
| `render_slide_simple()` | Simple slide renderer using python-pptx (background, images, text). |
| `create_placeholder_slide()` | Creates placeholder image for slides that couldn't be rendered. |

## Dependencies
- `PIL Image`, `pptx`, `pdf2image`, `subprocess` (LibreOffice), `moviepy`

## Usage
```python
from src.pipeline.screenshot_handler import get_media_files, extract_pptx_slides

# Load all media from folder
media = get_media_files("./content/")
for m in media:
    print(f"{m.path.name} — {m.media_type}")

# Extract slides from PowerPoint
slides = extract_pptx_slides(Path("presentation.pptx"))
```
