"""
Text Animation Module
Creates engaging animations that sync with voiceover:
- Cursor movement pointing to text
- Text highlighting effects
- Zoom/pan effects on text regions

Uses AI vision to detect text regions and sync with narration timing.
"""

import os
import json
from pathlib import Path
from typing import List, Tuple, Optional, Dict
from dataclasses import dataclass
from rich.console import Console

console = Console()


@dataclass
class TextRegion:
    """A detected text region in an image."""
    text: str
    x: int  # top-left x
    y: int  # top-left y
    width: int
    height: int
    center_x: int
    center_y: int


@dataclass
class AnimationKeyframe:
    """A keyframe for cursor/highlight animation."""
    time: float  # seconds from start
    x: int
    y: int
    text: str
    highlight: bool = True
    zoom: float = 1.0  # 1.0 = normal, 1.2 = 20% zoom


def analyze_image_for_text_regions(
    image_path: Path,
    script_text: str,
    api_key: Optional[str] = None
) -> List[TextRegion]:
    """
    Use Claude Vision to analyze image and find text regions.
    Returns list of text regions with their coordinates.
    """
    from ..ai.gemini_client import generate_with_images

    api_key = api_key or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        console.print("[yellow]Warning: GOOGLE_API_KEY not set, using estimated regions[/yellow]")
        return _estimate_text_regions(image_path, script_text)

    # Read image bytes
    with open(image_path, "rb") as f:
        image_bytes = f.read()

    ext = image_path.suffix.lower()
    media_type = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".gif": "image/gif"
    }.get(ext, "image/png")

    prompt = f"""Analyze this image and identify all visible text regions.

For each text element you can see, provide:
1. The exact text content
2. Approximate position as percentage of image dimensions (x%, y% for top-left corner)
3. Approximate size as percentage (width%, height%)

The script mentions these topics: {script_text[:500]}

Return a JSON array of text regions found:
[
  {{"text": "exact text seen", "x_percent": 10, "y_percent": 20, "width_percent": 30, "height_percent": 5}},
  ...
]

Only return the JSON array, nothing else. If no text is visible, return []."""

    try:
        response_text = generate_with_images(
            prompt=prompt,
            images=[(image_bytes, media_type)],
            max_output_tokens=2000,
            api_key=api_key,
        )

        # Extract JSON from response
        if response_text.startswith("["):
            regions_data = json.loads(response_text)
        else:
            # Try to find JSON in response
            import re
            json_match = re.search(r'\[.*\]', response_text, re.DOTALL)
            if json_match:
                regions_data = json.loads(json_match.group())
            else:
                return _estimate_text_regions(image_path, script_text)

        # Get image dimensions
        from PIL import Image
        with Image.open(image_path) as img:
            img_width, img_height = img.size

        # Convert percentages to pixels
        regions = []
        for r in regions_data:
            x = int(r.get("x_percent", 50) * img_width / 100)
            y = int(r.get("y_percent", 50) * img_height / 100)
            width = int(r.get("width_percent", 20) * img_width / 100)
            height = int(r.get("height_percent", 5) * img_height / 100)

            regions.append(TextRegion(
                text=r.get("text", ""),
                x=x,
                y=y,
                width=width,
                height=height,
                center_x=x + width // 2,
                center_y=y + height // 2
            ))

        return regions

    except Exception as e:
        console.print(f"[yellow]Vision analysis failed: {e}, using estimates[/yellow]")
        return _estimate_text_regions(image_path, script_text)


def _estimate_text_regions(image_path: Path, script_text: str) -> List[TextRegion]:
    """Fallback: estimate text regions based on common UI patterns."""
    from PIL import Image

    with Image.open(image_path) as img:
        img_width, img_height = img.size

    # Common text positions in screenshots/presentations
    regions = [
        # Title area (top center)
        TextRegion("title", int(img_width * 0.1), int(img_height * 0.05),
                   int(img_width * 0.8), int(img_height * 0.1),
                   img_width // 2, int(img_height * 0.1)),
        # Main content (center)
        TextRegion("content", int(img_width * 0.1), int(img_height * 0.2),
                   int(img_width * 0.8), int(img_height * 0.5),
                   img_width // 2, img_height // 2),
        # Bottom area
        TextRegion("footer", int(img_width * 0.1), int(img_height * 0.8),
                   int(img_width * 0.8), int(img_height * 0.1),
                   img_width // 2, int(img_height * 0.85)),
    ]

    return regions


def create_animation_keyframes(
    regions: List[TextRegion],
    audio_duration: float,
    script_text: str
) -> List[AnimationKeyframe]:
    """
    Create animation keyframes that sync cursor/highlight with audio.
    Distributes attention across detected text regions over the audio duration.
    """
    if not regions:
        return []

    keyframes = []
    time_per_region = audio_duration / len(regions)

    for i, region in enumerate(regions):
        start_time = i * time_per_region

        # Add keyframe for this region
        keyframes.append(AnimationKeyframe(
            time=start_time,
            x=region.center_x,
            y=region.center_y,
            text=region.text,
            highlight=True,
            zoom=1.15  # Subtle zoom
        ))

        # Add intermediate keyframe (cursor settles)
        keyframes.append(AnimationKeyframe(
            time=start_time + 0.3,
            x=region.center_x,
            y=region.center_y,
            text=region.text,
            highlight=True,
            zoom=1.2
        ))

    return keyframes


def create_cursor_image(size: int = 32) -> Path:
    """Create a cursor pointer image."""
    from PIL import Image, ImageDraw

    # Create cursor image with transparency
    cursor = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(cursor)

    # Draw arrow cursor shape
    points = [
        (0, 0),
        (0, size * 0.8),
        (size * 0.25, size * 0.6),
        (size * 0.4, size),
        (size * 0.55, size * 0.95),
        (size * 0.4, size * 0.55),
        (size * 0.6, size * 0.55),
    ]
    points = [(int(x), int(y)) for x, y in points]

    # White fill with black outline
    draw.polygon(points, fill=(255, 255, 255, 255), outline=(0, 0, 0, 255))

    # Save to temp file
    cursor_path = Path("/tmp/cursor_pointer.png")
    cursor.save(cursor_path)

    return cursor_path


def create_highlight_overlay(
    width: int,
    height: int,
    color: Tuple[int, int, int] = (255, 255, 0),
    opacity: int = 80
) -> Path:
    """Create a highlight overlay image."""
    from PIL import Image

    # Create semi-transparent highlight
    highlight = Image.new('RGBA', (width, height), (*color, opacity))

    highlight_path = Path("/tmp/highlight_overlay.png")
    highlight.save(highlight_path)

    return highlight_path


def apply_text_animation(
    image_path: Path,
    output_path: Path,
    keyframes: List[AnimationKeyframe],
    duration: float,
    video_size: Tuple[int, int] = (1920, 1080),
    fps: int = 30
):
    """
    Apply cursor, highlight, and zoom animations to create an engaging video.
    """
    from moviepy import ImageClip, VideoClip, CompositeVideoClip
    from PIL import Image
    import numpy as np

    # Load base image
    base_img = Image.open(image_path).convert('RGBA')
    base_img = base_img.resize(video_size, Image.Resampling.LANCZOS)
    base_array = np.array(base_img)

    # Create cursor
    cursor_path = create_cursor_image(40)
    cursor_img = Image.open(cursor_path).convert('RGBA')
    cursor_array = np.array(cursor_img)

    # Create highlight
    highlight_size = (200, 50)  # Default highlight size
    highlight_path = create_highlight_overlay(*highlight_size)
    highlight_img = Image.open(highlight_path).convert('RGBA')

    def make_frame(t):
        """Generate frame at time t with animations."""
        # Find current keyframe
        current_kf = keyframes[0] if keyframes else None
        next_kf = None

        for i, kf in enumerate(keyframes):
            if kf.time <= t:
                current_kf = kf
                if i + 1 < len(keyframes):
                    next_kf = keyframes[i + 1]

        if not current_kf:
            return base_array[:, :, :3]

        # Interpolate position if between keyframes
        if next_kf and next_kf.time > current_kf.time:
            progress = (t - current_kf.time) / (next_kf.time - current_kf.time)
            progress = min(1.0, max(0.0, progress))
            # Ease-out interpolation
            progress = 1 - (1 - progress) ** 2

            cursor_x = int(current_kf.x + (next_kf.x - current_kf.x) * progress)
            cursor_y = int(current_kf.y + (next_kf.y - current_kf.y) * progress)
            zoom = current_kf.zoom + (next_kf.zoom - current_kf.zoom) * progress
        else:
            cursor_x = current_kf.x
            cursor_y = current_kf.y
            zoom = current_kf.zoom

        # Scale coordinates to video size
        scale_x = video_size[0] / base_img.width if hasattr(base_img, 'width') else 1
        scale_y = video_size[1] / base_img.height if hasattr(base_img, 'height') else 1
        cursor_x = int(cursor_x * scale_x)
        cursor_y = int(cursor_y * scale_y)

        # Create frame with zoom effect
        frame = base_array.copy()

        if zoom > 1.0:
            # Apply zoom by cropping and resizing
            zoom_factor = zoom
            new_w = int(video_size[0] / zoom_factor)
            new_h = int(video_size[1] / zoom_factor)

            # Center zoom on cursor position
            left = max(0, min(cursor_x - new_w // 2, video_size[0] - new_w))
            top = max(0, min(cursor_y - new_h // 2, video_size[1] - new_h))

            # Crop and resize
            cropped = frame[top:top + new_h, left:left + new_w]
            from PIL import Image as PILImage
            cropped_pil = PILImage.fromarray(cropped)
            zoomed_pil = cropped_pil.resize(video_size, PILImage.Resampling.LANCZOS)
            frame = np.array(zoomed_pil)

            # Adjust cursor position for zoom
            cursor_x = int((cursor_x - left) * zoom_factor)
            cursor_y = int((cursor_y - top) * zoom_factor)

        # Add highlight effect (glowing rectangle around text)
        if current_kf.highlight:
            highlight_w, highlight_h = 250, 60
            hl_x = max(0, min(cursor_x - highlight_w // 2, video_size[0] - highlight_w))
            hl_y = max(0, min(cursor_y - highlight_h // 2, video_size[1] - highlight_h))

            # Create pulsing highlight
            pulse = 0.7 + 0.3 * np.sin(t * 4)  # Pulsing effect
            alpha = int(60 * pulse)

            # Blend highlight
            for dy in range(highlight_h):
                for dx in range(highlight_w):
                    if hl_y + dy < video_size[1] and hl_x + dx < video_size[0]:
                        # Yellow highlight with gradient edges
                        edge_fade = min(dx, highlight_w - dx, dy, highlight_h - dy) / 10
                        edge_fade = min(1.0, edge_fade)
                        blend = alpha * edge_fade / 255

                        frame[hl_y + dy, hl_x + dx, 0] = int(frame[hl_y + dy, hl_x + dx, 0] * (1 - blend) + 255 * blend)
                        frame[hl_y + dy, hl_x + dx, 1] = int(frame[hl_y + dy, hl_x + dx, 1] * (1 - blend) + 255 * blend)

        # Add cursor
        cursor_w, cursor_h = cursor_array.shape[1], cursor_array.shape[0]
        for cy in range(cursor_h):
            for cx in range(cursor_w):
                px, py = cursor_x + cx, cursor_y + cy
                if 0 <= px < video_size[0] and 0 <= py < video_size[1]:
                    alpha = cursor_array[cy, cx, 3] / 255
                    if alpha > 0:
                        frame[py, px, :3] = (
                            frame[py, px, :3] * (1 - alpha) +
                            cursor_array[cy, cx, :3] * alpha
                        ).astype(np.uint8)

        return frame[:, :, :3]

    # Create video clip
    video = VideoClip(make_frame, duration=duration)
    video = video.with_fps(fps)

    # Write output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    video.write_videofile(
        str(output_path),
        fps=fps,
        codec='libx264',
        audio=False,
        preset='medium',
        threads=4
    )

    return output_path


def create_animated_scene(
    image_path: Path,
    script_text: str,
    audio_path: Optional[Path],
    output_path: Path,
    video_size: Tuple[int, int] = (1920, 1080),
    fps: int = 30
) -> Path:
    """
    Create an animated scene with cursor, highlights, and zoom synced to audio.

    Args:
        image_path: Source image
        script_text: Narration script (used to identify important regions)
        audio_path: Voiceover audio file
        output_path: Where to save the animated video
        video_size: Output video dimensions
        fps: Frames per second

    Returns:
        Path to the animated video
    """
    from moviepy import AudioFileClip, VideoFileClip

    console.print(f"[cyan]Creating animated scene for: {image_path.name}[/cyan]")

    # Get audio duration
    if audio_path and audio_path.exists():
        audio = AudioFileClip(str(audio_path))
        duration = audio.duration
        audio.close()
    else:
        duration = 5.0  # Default duration

    # Analyze image for text regions
    console.print("  Analyzing image for text regions...")
    regions = analyze_image_for_text_regions(image_path, script_text)
    console.print(f"  Found {len(regions)} text regions")

    # Create animation keyframes
    keyframes = create_animation_keyframes(regions, duration, script_text)
    console.print(f"  Created {len(keyframes)} animation keyframes")

    # Generate animated video
    console.print("  Rendering animation...")
    temp_video = output_path.parent / f"temp_{output_path.name}"
    apply_text_animation(
        image_path=image_path,
        output_path=temp_video,
        keyframes=keyframes,
        duration=duration,
        video_size=video_size,
        fps=fps
    )

    # Add audio if provided
    if audio_path and audio_path.exists():
        console.print("  Adding voiceover...")
        video = VideoFileClip(str(temp_video))
        audio = AudioFileClip(str(audio_path))
        final = video.with_audio(audio)
        final.write_videofile(
            str(output_path),
            fps=fps,
            codec='libx264',
            audio_codec='aac',
            preset='medium',
            threads=4
        )
        video.close()
        audio.close()
        temp_video.unlink()  # Clean up temp file
    else:
        temp_video.rename(output_path)

    console.print(f"[green]  ✓ Animated scene created: {output_path}[/green]")
    return output_path
