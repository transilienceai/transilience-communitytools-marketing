"""
Audio Utilities
Audio extraction, music overlay, and audio processing.
"""

import subprocess
from pathlib import Path
from typing import Optional
from moviepy import AudioFileClip, concatenate_audioclips
from moviepy.audio.fx import AudioFadeOut
from rich.console import Console

console = Console()


def extract_audio(video_path: Path, output_path: Optional[Path] = None) -> Path:
    """
    Extract audio from video as MP3 using ffmpeg.

    Args:
        video_path: Path to video file
        output_path: Optional output path (defaults to {video_stem}_audio.mp3)

    Returns:
        Path to extracted audio file

    Raises:
        RuntimeError: If audio extraction fails
    """
    if output_path is None:
        output_path = video_path.parent / f"{video_path.stem}_audio.mp3"

    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-vn", "-acodec", "libmp3lame",
        "-ar", "16000", "-ac", "1", "-b:a", "64k",
        str(output_path)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Audio extraction failed: {result.stderr[-300:]}")

    console.print(f"[green]✓ Audio extracted:[/green] {output_path.name}")
    return output_path


def add_background_music(
    video_clip,
    music_path: Path,
    music_volume: float = 0.03
):
    """
    Add background music to video, looping if necessary.

    Args:
        video_clip: MoviePy VideoFileClip object
        music_path: Path to music file (.mp3, .wav, etc.)
        music_volume: Volume multiplier for music (0.0 - 1.0, default: 0.03)

    Returns:
        VideoFileClip with background music added
    """
    if not music_path.exists():
        console.print(f"[yellow]Music file not found: {music_path}[/yellow]")
        return video_clip

    music = AudioFileClip(str(music_path))

    # Loop music if shorter than video
    video_duration = video_clip.duration
    if music.duration < video_duration:
        # Calculate how many times to loop
        loops_needed = int(video_duration / music.duration) + 1
        music = concatenate_audioclips([music] * loops_needed)

    # Trim to video length and adjust volume
    music = music.subclipped(0, video_duration)
    music = music.with_volume_scaled(music_volume)

    # Fade out music at the end
    music = music.with_effects([AudioFadeOut(2.0)])

    # Combine with existing audio
    from moviepy import CompositeAudioClip
    if video_clip.audio:
        final_audio = CompositeAudioClip([video_clip.audio, music])
        return video_clip.with_audio(final_audio)
    else:
        return video_clip.with_audio(music)
