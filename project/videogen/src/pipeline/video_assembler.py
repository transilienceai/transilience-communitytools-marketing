"""
Video Assembler
Stitches images, adds captions, syncs audio, and overlays music.
"""

import os
from pathlib import Path
from typing import List, Optional, Tuple
from dataclasses import dataclass
from moviepy import (
    ImageClip, VideoFileClip, AudioFileClip, CompositeVideoClip,
    concatenate_videoclips, TextClip, ColorClip
)
from moviepy.video.fx import FadeIn, FadeOut
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from ..core.audio_utils import add_background_music

console = Console()

# Media type constants
IMAGE_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp')
VIDEO_EXTENSIONS = ('.mp4', '.mov', '.avi', '.mkv', '.webm', '.m4v')
PPTX_EXTENSIONS = ('.pptx', '.ppt')  # PowerPoint files (converted to images)


@dataclass
class SceneConfig:
    """Configuration for a single scene in the video."""
    media_path: Path  # Can be image or video
    audio_path: Optional[Path]
    caption: str
    duration: float  # For images: display time. For videos: ignored (uses video duration)
    is_video: bool = False  # True if media_path is a video file

    # Legacy alias for backward compatibility
    @property
    def image_path(self) -> Path:
        return self.media_path


def create_caption_clip(
    text: str,
    duration: float,
    video_size: Tuple[int, int],
    font_size: int = 40,
    font_color: str = "white",
    bg_color: str = "black",
    position: str = "bottom"
) -> CompositeVideoClip:
    """
    Create a caption clip with background.
    """
    width, height = video_size

    # Create text clip (use None for default system font)
    txt_clip = TextClip(
        text=text,
        font_size=font_size,
        color=font_color,
        font=None,
        method="caption",
        size=(width - 100, None),
        text_align="center"
    ).with_duration(duration)

    # Create semi-transparent background
    txt_width, txt_height = txt_clip.size
    padding = 20
    bg_clip = ColorClip(
        size=(txt_width + padding * 2, txt_height + padding),
        color=(0, 0, 0)
    ).with_opacity(0.7).with_duration(duration)

    # Position based on preference
    if position == "bottom":
        y_pos = height - txt_height - 80
    elif position == "top":
        y_pos = 50
    else:  # center
        y_pos = (height - txt_height) // 2

    x_pos = (width - txt_width) // 2

    # Composite background and text
    caption = CompositeVideoClip([
        bg_clip.with_position((x_pos - padding, y_pos - padding // 2)),
        txt_clip.with_position((x_pos, y_pos))
    ], size=video_size).with_duration(duration)

    return caption


def create_scene_clip(
    config: SceneConfig,
    video_size: Tuple[int, int],
    show_captions: bool = True,
    caption_position: str = "bottom"
) -> CompositeVideoClip:
    """
    Create a video clip for a single scene with image/video, audio, and caption.
    Supports both static images and video clips.
    """
    # Check if this is a video or image
    ext = config.media_path.suffix.lower()
    is_video = ext in VIDEO_EXTENSIONS or config.is_video

    if is_video:
        # Load video clip
        base_clip = VideoFileClip(str(config.media_path))
        duration = base_clip.duration

        # Resize video to target size if needed
        if base_clip.size != video_size:
            base_clip = base_clip.resized(video_size)

        # Strip original video audio and use voiceover only
        if config.audio_path and config.audio_path.exists():
            voiceover = AudioFileClip(str(config.audio_path))
            voiceover = voiceover.with_volume_scaled(5.0)
            base_clip = base_clip.with_audio(voiceover)
        else:
            # No voiceover available — remove original audio
            base_clip = base_clip.without_audio()
    else:
        # Load image and set duration
        base_clip = ImageClip(str(config.media_path))

        # Resize image to target size if needed
        if base_clip.size != video_size:
            base_clip = base_clip.resized(video_size)

        # Determine actual duration (audio length or specified duration)
        duration = config.duration
        if config.audio_path and config.audio_path.exists():
            audio = AudioFileClip(str(config.audio_path))
            # Boost voiceover volume significantly (5x)
            audio = audio.with_volume_scaled(5.0)
            duration = max(duration, audio.duration + 0.5)  # Add small buffer
            base_clip = base_clip.with_duration(duration)
            base_clip = base_clip.with_audio(audio)
        else:
            base_clip = base_clip.with_duration(duration)

    # Add caption if enabled
    if show_captions and config.caption:
        caption_clip = create_caption_clip(
            config.caption,
            duration,
            video_size,
            position=caption_position
        )
        scene = CompositeVideoClip([base_clip, caption_clip])
    else:
        scene = base_clip

    # Add subtle fade transitions
    scene = scene.with_effects([FadeIn(0.3), FadeOut(0.3)])

    return scene


def assemble_video(
    scenes: List[SceneConfig],
    output_path: Path,
    video_size: Tuple[int, int] = (1920, 1080),
    fps: int = 30,
    music_path: Optional[Path] = None,
    music_volume: float = 0.03,  # Very low volume so voice is prominent
    show_captions: bool = True,
    caption_position: str = "bottom"
) -> Path:
    """
    Assemble all scenes into final video with music.

    Args:
        scenes: List of SceneConfig for each scene
        output_path: Where to save the final video
        video_size: (width, height) of output video
        fps: Frames per second
        music_path: Optional path to background music
        music_volume: Volume of background music (0.0 - 1.0)
        show_captions: Whether to show captions on screen
        caption_position: "bottom", "top", or "center"

    Returns:
        Path to the created video file
    """
    console.print(f"\n[bold blue]Assembling video with {len(scenes)} scenes...[/bold blue]")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        console=console
    ) as progress:
        # Create scene clips
        task = progress.add_task("Creating scene clips...", total=len(scenes))
        clips = []

        for config in scenes:
            try:
                clip = create_scene_clip(
                    config,
                    video_size,
                    show_captions=show_captions,
                    caption_position=caption_position
                )
                if clip is not None:
                    clips.append(clip)
            except Exception as e:
                console.print(f"[yellow]Warning: Could not create clip for {config.media_path}: {e}[/yellow]")
            progress.update(task, advance=1)

        # Check if we have any clips
        if not clips:
            raise ValueError("No clips were created. Check that your media files are valid.")

        # Concatenate all clips
        progress.update(task, description="Concatenating clips...")
        final_video = concatenate_videoclips(clips, method="compose")

        # Add background music
        if music_path:
            progress.update(task, description="Adding background music...")
            final_video = add_background_music(final_video, music_path, music_volume)

        # Write output file
        progress.update(task, description="Rendering video (this may take a while)...")

        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        final_video.write_videofile(
            str(output_path),
            fps=fps,
            codec="libx264",
            audio_codec="aac",
            temp_audiofile="temp-audio.m4a",
            remove_temp=True,
            logger=None  # Suppress moviepy's verbose output
        )

        # Clean up
        final_video.close()
        for clip in clips:
            clip.close()

    console.print(f"\n[bold green]✓ Video saved to: {output_path}[/bold green]")
    return output_path


def get_recommended_size(media_path: Path) -> Tuple[int, int]:
    """Get recommended video size based on first media file (image or video)."""
    ext = media_path.suffix.lower()

    if ext in VIDEO_EXTENSIONS:
        # Get size from video
        clip = VideoFileClip(str(media_path))
        width, height = clip.size
        clip.close()
    else:
        # Get size from image
        from PIL import Image
        with Image.open(media_path) as img:
            width, height = img.size

    # Common aspect ratios
    if width / height > 1.5:  # Wide (16:9 or similar)
        return (1920, 1080)
    elif width / height < 0.7:  # Tall (9:16, mobile)
        return (1080, 1920)
    else:  # Square-ish (1:1 or 4:3)
        return (1080, 1080)
