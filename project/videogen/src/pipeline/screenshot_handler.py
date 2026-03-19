"""
Screenshot/Image/Video/PowerPoint Input Handler
Handles loading images, video clips, and PowerPoint slides from files.
"""

import os
import tempfile
from pathlib import Path
from typing import List, Tuple, Union
from dataclasses import dataclass
from enum import Enum
from PIL import Image
from rich.console import Console
from ..core.image_utils import (
    image_to_base64,
    pil_image_to_base64,
    get_mime_type,
    get_image_media_type,
    resize_image_for_api,
    resize_pil_image_for_api,
    get_image_dimensions,
)
from ..core.video_utils import get_duration

console = Console()


class MediaType(Enum):
    IMAGE = "image"
    VIDEO = "video"
    POWERPOINT = "pptx"  # PowerPoint slides (converted to images)


@dataclass
class MediaFile:
    """Represents an input media file (image, video, or pptx slide)."""
    path: Path
    media_type: MediaType
    duration: float = 0.0  # For videos, actual duration; for images/slides, 0
    slide_index: int = -1  # For pptx slides, the slide number (0-indexed)
    original_pptx: Path = None  # For pptx slides, path to original file


# Supported formats
IMAGE_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp')
VIDEO_EXTENSIONS = ('.mp4', '.mov', '.avi', '.mkv', '.webm', '.m4v')
PPTX_EXTENSIONS = ('.pptx', '.ppt')
ALL_EXTENSIONS = IMAGE_EXTENSIONS + VIDEO_EXTENSIONS + PPTX_EXTENSIONS


def extract_pptx_slides(pptx_path: Path, output_dir: Path = None) -> List[Path]:
    """
    Extract slides from a PowerPoint file as images.
    Returns list of paths to extracted slide images.
    """
    from pptx import Presentation
    from pptx.util import Inches
    import io

    if output_dir is None:
        output_dir = Path(tempfile.mkdtemp(prefix="pptx_slides_"))

    output_dir.mkdir(parents=True, exist_ok=True)

    prs = Presentation(str(pptx_path))
    slide_paths = []
    num_slides = len(prs.slides)

    # Get slide dimensions
    slide_width = prs.slide_width
    slide_height = prs.slide_height

    # Calculate pixel dimensions (assuming 96 DPI)
    dpi = 96
    width_px = int(slide_width.inches * dpi * 2)  # 2x for better quality
    height_px = int(slide_height.inches * dpi * 2)

    # Method 1: Convert PPTX to PDF once, then extract all pages (best quality)
    pdf_images = _convert_pptx_via_pdf(pptx_path, num_slides, width_px, height_px)

    for i, slide in enumerate(prs.slides):
        slide_path = output_dir / f"{pptx_path.stem}_slide_{i+1:03d}.png"

        if pdf_images and i < len(pdf_images):
            pdf_images[i].save(str(slide_path), 'PNG')
            slide_paths.append(slide_path)
            continue

        try:
            # Method 2: Use python-pptx to extract shapes and render
            slide_img = render_slide_simple(slide, width_px, height_px)
            slide_img.save(str(slide_path), 'PNG')
            slide_paths.append(slide_path)
        except Exception as e:
            console.print(f"[yellow]Warning: Could not render slide {i+1}: {e}[/yellow]")
            # Create a placeholder image
            slide_img = create_placeholder_slide(
                width_px, height_px,
                f"Slide {i+1}",
                pptx_path.stem
            )
            slide_img.save(str(slide_path), 'PNG')
            slide_paths.append(slide_path)

    return slide_paths


def _convert_pptx_via_pdf(pptx_path: Path, num_slides: int, width: int, height: int) -> List[Image.Image]:
    """Convert PPTX to PDF once via LibreOffice, then extract all pages as images."""
    import subprocess
    import tempfile

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run([
                'soffice', '--headless', '--convert-to', 'pdf',
                '--outdir', tmpdir, str(pptx_path)
            ], capture_output=True, timeout=120)

            if result.returncode != 0:
                return []

            pdf_path = Path(tmpdir) / f"{pptx_path.stem}.pdf"
            if not pdf_path.exists():
                return []

            from pdf2image import convert_from_path
            images = convert_from_path(str(pdf_path), dpi=200)
            return [img.resize((width, height), Image.Resampling.LANCZOS) for img in images]
    except Exception:
        return []


def render_slide_pdf2image(pptx_path: Path, slide_index: int, width: int, height: int) -> Image.Image:
    """Try to render slide using LibreOffice + pdf2image (best quality)."""
    import subprocess
    import tempfile

    # This requires LibreOffice to be installed
    # Convert PPTX to PDF first
    with tempfile.TemporaryDirectory() as tmpdir:
        # Convert to PDF using LibreOffice
        result = subprocess.run([
            'soffice', '--headless', '--convert-to', 'pdf',
            '--outdir', tmpdir, str(pptx_path)
        ], capture_output=True, timeout=60)

        if result.returncode != 0:
            return None

        pdf_path = Path(tmpdir) / f"{pptx_path.stem}.pdf"
        if not pdf_path.exists():
            return None

        # Convert PDF page to image
        from pdf2image import convert_from_path
        images = convert_from_path(str(pdf_path), first_page=slide_index+1, last_page=slide_index+1)
        if images:
            return images[0].resize((width, height), Image.Resampling.LANCZOS)

    return None


def render_slide_simple(slide, width: int, height: int) -> Image.Image:
    """
    Simple slide renderer using python-pptx.
    Extracts background, images, and text from shapes.
    """
    from pptx.util import Emu
    from pptx.dml.color import RGBColor
    from PIL import ImageDraw, ImageFont
    import io

    # Slide dimensions in EMUs (for coordinate mapping)
    slide_width_emu = slide.slide_layout.slide_master.slide_width if hasattr(slide.slide_layout.slide_master, 'slide_width') else 9144000
    slide_height_emu = slide.slide_layout.slide_master.slide_height if hasattr(slide.slide_layout.slide_master, 'slide_height') else 6858000

    # Create base image with white background
    img = Image.new('RGB', (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(img)

    # Try to get background color
    try:
        if slide.background.fill.solid():
            bg_color = slide.background.fill.fore_color.rgb
            img = Image.new('RGB', (width, height), (bg_color.red, bg_color.green, bg_color.blue))
            draw = ImageDraw.Draw(img)
    except Exception:
        pass

    # Try to get background image
    try:
        bg = slide.background
        if bg.fill.type is not None and hasattr(bg.fill, 'background') and bg.fill.type == 6:  # Picture fill
            bg_image_blob = bg.fill.background.image.blob
            bg_img = Image.open(io.BytesIO(bg_image_blob)).convert('RGB')
            bg_img = bg_img.resize((width, height), Image.Resampling.LANCZOS)
            img.paste(bg_img, (0, 0))
            draw = ImageDraw.Draw(img)
    except Exception:
        pass

    # Render all shapes (images first, then text on top)
    for shape in slide.shapes:
        # Extract embedded images
        if shape.shape_type == 13:  # Picture
            try:
                image_blob = shape.image.blob
                shape_img = Image.open(io.BytesIO(image_blob)).convert('RGBA')

                # Map shape position from EMUs to pixels
                x = int(shape.left / slide_width_emu * width)
                y = int(shape.top / slide_height_emu * height)
                w = int(shape.width / slide_width_emu * width)
                h = int(shape.height / slide_height_emu * height)

                shape_img = shape_img.resize((w, h), Image.Resampling.LANCZOS)
                img.paste(shape_img, (x, y), shape_img)
                draw = ImageDraw.Draw(img)
            except Exception:
                pass

    # Render text on top of images
    y_offset = height * 0.1
    for shape in slide.shapes:
        if shape.has_text_frame:
            for paragraph in shape.text_frame.paragraphs:
                text = paragraph.text.strip()
                if text:
                    # Determine font size based on shape position
                    try:
                        font_size = max(20, min(60, int(height * 0.05)))
                        # Check if this is a title
                        if hasattr(shape, 'is_placeholder') and shape.is_placeholder:
                            if shape.placeholder_format.type == 1:  # Title
                                font_size = int(height * 0.08)
                    except Exception:
                        font_size = 30

                    # Draw text
                    try:
                        draw.text((width * 0.1, y_offset), text, fill=(0, 0, 0), font_size=font_size)
                    except Exception:
                        draw.text((width * 0.1, y_offset), text, fill=(0, 0, 0))

                    y_offset += font_size + 20

    return img


def create_placeholder_slide(width: int, height: int, title: str, subtitle: str = "") -> Image.Image:
    """Create a placeholder image for slides that couldn't be rendered."""
    from PIL import ImageDraw

    img = Image.new('RGB', (width, height), (240, 240, 240))
    draw = ImageDraw.Draw(img)

    # Draw title
    draw.text((width // 2, height // 3), title, fill=(100, 100, 100), anchor="mm", font_size=60)

    # Draw subtitle
    if subtitle:
        draw.text((width // 2, height // 2), subtitle, fill=(150, 150, 150), anchor="mm", font_size=30)

    # Draw border
    draw.rectangle([10, 10, width-10, height-10], outline=(200, 200, 200), width=2)

    return img


def get_media_files(input_path: str) -> List[MediaFile]:
    """
    Get list of media files (images, videos, and pptx slides) from a directory or single file.
    Returns sorted list of MediaFile objects.
    PowerPoint files are expanded into individual slides.
    """
    path = Path(input_path)

    if path.is_file():
        ext = path.suffix.lower()
        if ext in IMAGE_EXTENSIONS:
            return [MediaFile(path=path, media_type=MediaType.IMAGE)]
        elif ext in VIDEO_EXTENSIONS:
            duration = get_video_duration(path)
            return [MediaFile(path=path, media_type=MediaType.VIDEO, duration=duration)]
        elif ext in PPTX_EXTENSIONS:
            return expand_pptx_to_media_files(path)
        else:
            raise ValueError(f"File {path} is not a supported format. Supported: {ALL_EXTENSIONS}")

    if path.is_dir():
        media_files = []

        # Collect all supported files
        all_files = []
        for ext in ALL_EXTENSIONS:
            all_files.extend(path.glob(f"*{ext}"))
            all_files.extend(path.glob(f"*{ext.upper()}"))

        # Remove duplicates and sort
        all_files = sorted(set(all_files), key=lambda x: x.name)

        for file_path in all_files:
            ext = file_path.suffix.lower()
            if ext in IMAGE_EXTENSIONS:
                media_files.append(MediaFile(path=file_path, media_type=MediaType.IMAGE))
            elif ext in VIDEO_EXTENSIONS:
                duration = get_video_duration(file_path)
                media_files.append(MediaFile(path=file_path, media_type=MediaType.VIDEO, duration=duration))
            elif ext in PPTX_EXTENSIONS:
                # Expand PowerPoint to individual slides
                pptx_media_files = expand_pptx_to_media_files(file_path)
                media_files.extend(pptx_media_files)

        if not media_files:
            raise ValueError(f"No media files found in {path}. Supported formats: {ALL_EXTENSIONS}")

        return media_files

    raise ValueError(f"Path {input_path} does not exist")


def expand_pptx_to_media_files(pptx_path: Path) -> List[MediaFile]:
    """
    Expand a PowerPoint file into individual MediaFile objects for each slide.
    """
    console.print(f"  [cyan]Extracting slides from {pptx_path.name}...[/cyan]")

    # Create temp directory for extracted slides
    temp_dir = Path(tempfile.mkdtemp(prefix="pptx_"))
    slide_paths = extract_pptx_slides(pptx_path, temp_dir)

    media_files = []
    for i, slide_path in enumerate(slide_paths):
        media_files.append(MediaFile(
            path=slide_path,
            media_type=MediaType.POWERPOINT,
            slide_index=i,
            original_pptx=pptx_path
        ))

    console.print(f"  [green]✓[/green] Extracted {len(media_files)} slides from {pptx_path.name}")
    return media_files


def get_video_duration(video_path: Path) -> float:
    """Get duration of a video file in seconds."""
    try:
        return get_duration(video_path)
    except Exception as e:
        console.print(f"[yellow]Warning: {e}[/yellow]")
        return 5.0  # Default duration


def get_video_thumbnail(video_path: Path, time: float = 0.5) -> Image.Image:
    """Extract a thumbnail frame from a video for AI analysis."""
    from moviepy import VideoFileClip

    clip = VideoFileClip(str(video_path))
    # Get frame at specified time (or middle if time > duration)
    frame_time = min(time, clip.duration / 2)
    frame = clip.get_frame(frame_time)
    clip.close()

    # Convert numpy array to PIL Image
    return Image.fromarray(frame.astype('uint8'))


def extract_video_frames(video_path: Path, num_frames: int = 3) -> List[Image.Image]:
    """Extract multiple frames from a video for better AI analysis."""
    from moviepy import VideoFileClip

    clip = VideoFileClip(str(video_path))
    frames = []

    # Get frames at evenly spaced intervals
    for i in range(num_frames):
        time = (i + 0.5) * clip.duration / num_frames
        frame = clip.get_frame(time)
        frames.append(Image.fromarray(frame.astype('uint8')))

    clip.close()
    return frames


# Legacy function for backward compatibility
def get_image_files(input_path: str, extensions: Tuple[str, ...] = IMAGE_EXTENSIONS) -> List[Path]:
    """
    Get list of image files from a directory or single file.
    Returns sorted list of image paths.
    """
    media_files = get_media_files(input_path)
    return [mf.path for mf in media_files if mf.media_type == MediaType.IMAGE]


def load_image(image_path: Path) -> Image.Image:
    """Load an image file and return PIL Image."""
    return Image.open(image_path)


def get_media_dimensions(media_file: MediaFile) -> Tuple[int, int]:
    """Get dimensions for any media file (image, video, or pptx slide)."""
    if media_file.media_type in (MediaType.IMAGE, MediaType.POWERPOINT):
        return get_image_dimensions(media_file.path)
    else:
        from moviepy import VideoFileClip
        clip = VideoFileClip(str(media_file.path))
        size = clip.size
        clip.close()
        return tuple(size)


def validate_media_files(media_files: List[MediaFile]) -> bool:
    """Validate that all media files can be loaded."""
    if not media_files:
        return False

    dimensions = set()
    for mf in media_files:
        try:
            dims = get_media_dimensions(mf)
            dimensions.add(dims)

            # Format display based on type
            if mf.media_type == MediaType.POWERPOINT:
                type_str = f"slide {mf.slide_index + 1}"
            else:
                type_str = mf.media_type.value

            console.print(f"  [green]✓[/green] {mf.path.name} ({type_str}, {dims[0]}x{dims[1]})")
        except Exception as e:
            console.print(f"[red]Error loading {mf.path}: {e}[/red]")
            return False

    if len(dimensions) > 1:
        console.print(f"[yellow]Warning: Media files have different dimensions: {dimensions}[/yellow]")
        console.print("[yellow]Video will resize all to match the first file's dimensions.[/yellow]")

    return True


# Legacy function
def validate_images(image_paths: List[Path]) -> bool:
    """Validate that all images can be loaded and have consistent dimensions."""
    media_files = [MediaFile(path=p, media_type=MediaType.IMAGE) for p in image_paths]
    return validate_media_files(media_files)
