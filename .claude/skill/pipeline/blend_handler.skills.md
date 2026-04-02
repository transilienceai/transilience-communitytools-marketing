# Blend Handler — `src/pipeline/blend_handler.py`

## Description

Scans folders recursively, optionally follows a sequence file, or uses Gemini Vision to determine optimal order, then outputs a numbered folder ready for `create`.

## Functions

### `blend_content(input_path, output_dir, sequence_path=None, bookend_path=None, include_unsequenced=True, ai_order=True, context="", tone="", storyline="", dry_run=False) -> List[Path]`
Main orchestrator:
1. Scan input recursively for media files
2. Deduplicate size variants (e.g., `home.png` vs `home-1920x1080.png` — keeps largest)
3. If sequence file: parse markdown, fuzzy-match references to files
4. AI-order unsequenced files via `reorder_items_with_vision()` (or filename sort)
5. Round-robin interleave files from different source folders
6. Add bookend images as first/last frames
7. Copy to output dir with `{i:02d}-{stem}{ext}` naming

### `scan_recursive(input_path) -> List[Path]`
Recursively find all image/video files. Deduplicates case-insensitive matches.

### `parse_sequence_source(sequence_path) -> List[str]`
Parse media file references from a single markdown file or directory of markdown files. Handles numbered lists, bullet lists, and any line containing a recognized media extension.

### `fuzzy_match(reference, all_files) -> Optional[Path]`
Match a reference string to a file. Strategy: exact basename → stem-contains → difflib ratio >= 0.6.

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
