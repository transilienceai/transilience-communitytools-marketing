# Screenshot Handler — `src/pipeline/screenshot_handler.py`

## Description

Media file loading, sorting, and PowerPoint slide extraction.

## Classes

### `MediaType` (Enum)
- `IMAGE`, `VIDEO`, `POWERPOINT`

### `MediaFile`
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

### `get_media_files(input_path) -> List[MediaFile]`
Main entry point. Gets sorted list of media files from directory or single file. Expands PowerPoint files into individual slides.

### `extract_pptx_slides(pptx_path, output_dir=None) -> List[Path]`
Extracts PowerPoint slides as images. Converts via PDF (LibreOffice) for best quality. Falls back to python-pptx rendering.

### `expand_pptx_to_media_files(pptx_path) -> List[MediaFile]`
Expands PowerPoint file into `MediaFile` objects for each slide.

### `get_video_duration(video_path) -> float`
Gets duration of video file in seconds.

### `get_video_thumbnail(video_path, time=0.5) -> Image.Image`
Extracts thumbnail frame from video for AI analysis.

### `extract_video_frames(video_path, num_frames=3) -> List[Image.Image]`
Extracts multiple frames at evenly spaced intervals.

### `get_image_files(input_path, extensions=IMAGE_EXTENSIONS) -> List[Path]`
Legacy function. Gets image files from directory or single file.

### `load_image(image_path) -> Image.Image`
Loads image file and returns PIL Image.

### `get_media_dimensions(media_file) -> Tuple[int, int]`
Gets dimensions for any media file (image, video, or PPTX slide). Returns `(width, height)`.

### `validate_media_files(media_files) -> bool`
Validates all media files can be loaded.

### `validate_images(image_paths) -> bool`
Legacy function. Validates images.

### `render_slide_pdf2image(pptx_path, slide_index, width, height) -> Image.Image`
Renders single slide using LibreOffice + pdf2image.

### `render_slide_simple(slide, width, height) -> Image.Image`
Simple slide renderer using python-pptx (background, images, text).

### `create_placeholder_slide(width, height, title, subtitle="") -> Image.Image`
Creates placeholder image for slides that couldn't be rendered.

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
