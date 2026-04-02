# Blend Handler — `src/pipeline/blend_handler.py`

## Description

Scans folders recursively, optionally follows a sequence file, or uses Gemini Vision to determine optimal order, then outputs a numbered folder ready for `create`.

## Functions

| Function | Description |
|----------|-------------|
| `blend_content()` | Main orchestrator: scan input recursively, deduplicate size variants, apply sequence file or AI ordering, round-robin interleave files from different source folders, add bookend images, copy to output dir with `{i:02d}-{stem}{ext}` naming. |
| `scan_recursive()` | Recursively find all image/video files. Deduplicates case-insensitive matches. |
| `parse_sequence_source()` | Parse media file references from a single markdown file or directory of markdown files. Handles numbered lists, bullet lists, and any line containing a recognized media extension. |
| `fuzzy_match()` | Match a reference string to a file. Strategy: exact basename, then stem-contains, then difflib ratio >= 0.6. |

## Dependencies
- `screenshot_handler` (IMAGE_EXTENSIONS, VIDEO_EXTENSIONS)
- `veo_pipeline.reorder_items_with_vision` (for AI ordering)
- `rich` (summary table)

## Usage
```python
from src.pipeline.blend_handler import blend_content

files = blend_content(
    input_path=Path("storyboard_output/"),
    output_dir=Path("blended/"),
    ai_order=True,
    storyline="AI transforms compliance",
)
# Ready for: python cli.py create blended/ -o video.mp4
```
