"""
Post-processing module for adjusting video speed, voice volume, and music volume.

Operates on already-rendered videos using pure FFmpeg for speed.
Supports two modes:
- Simple mode: adjust overall audio volume + video speed on a mixed track
- Remix mode: re-mix separate voice/music tracks at new volumes + adjust video speed
"""

import json
import subprocess
from pathlib import Path
from typing import Optional
from rich.console import Console

console = Console()


def build_atempo_chain(speed: float) -> str:
    """Build chained atempo filters for FFmpeg (each filter limited to 0.5-2.0 range).

    FFmpeg's atempo filter only accepts values in [0.5, 2.0]. For speeds outside
    this range, we chain multiple atempo filters together.

    Args:
        speed: Playback speed multiplier (e.g., 1.5 = 50% faster)

    Returns:
        Comma-separated atempo filter string (e.g., "atempo=2.0,atempo=1.5")
    """
    filters = []
    remaining = speed
    while remaining > 2.0:
        filters.append("atempo=2.0")
        remaining /= 2.0
    while remaining < 0.5:
        filters.append("atempo=0.5")
        remaining *= 2.0
    filters.append(f"atempo={remaining:.4f}")
    return ",".join(filters)


def load_manifest(manifest_path: Path) -> Optional[dict]:
    """Load a pipeline manifest JSON file.

    Args:
        manifest_path: Path to the manifest JSON file

    Returns:
        Parsed manifest dict, or None if not found/invalid
    """
    if not manifest_path.exists():
        return None
    try:
        with open(manifest_path) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        console.print(f"[yellow]Warning: Could not read manifest {manifest_path}: {e}[/yellow]")
        return None


def adjust_video(
    input_video: Path,
    output_video: Path,
    video_speed: float = 1.0,
    overall_volume: Optional[float] = None,
    voice_audio: Optional[Path] = None,
    music_audio: Optional[Path] = None,
    voice_volume: float = 5.0,
    music_volume: float = 0.03,
    extract_audio: bool = True,
) -> Path:
    """Adjust video speed, audio volume, or remix voice/music tracks.

    Operates in one of two modes:
    - Remix mode (voice_audio provided): Strip existing audio, mix voice + music
      at specified volumes, optionally adjust speed
    - Simple mode: Adjust overall audio volume and/or video speed on the mixed track

    Uses `-c:v copy` when only audio changes are needed (no re-encode).

    Args:
        input_video: Source video file
        output_video: Destination video file
        video_speed: Playback speed multiplier (1.0 = normal)
        overall_volume: Overall audio volume multiplier (simple mode)
        voice_audio: Path to voice-only audio for remixing
        music_audio: Path to music audio for remixing
        voice_volume: Voice volume multiplier (remix mode)
        music_volume: Music volume multiplier (remix mode)
        extract_audio: Whether to extract MP3 alongside output

    Returns:
        Path to the output video file
    """
    output_video.parent.mkdir(parents=True, exist_ok=True)

    has_speed_change = abs(video_speed - 1.0) > 0.01
    has_remix = voice_audio is not None
    has_volume_change = overall_volume is not None and abs(overall_volume - 1.0) > 0.01

    if has_remix:
        _remix_video(input_video, output_video, video_speed, voice_audio,
                     music_audio, voice_volume, music_volume, has_speed_change)
    elif has_speed_change and has_volume_change:
        _speed_and_volume(input_video, output_video, video_speed, overall_volume)
    elif has_speed_change:
        _speed_only(input_video, output_video, video_speed)
    elif has_volume_change:
        _volume_only(input_video, output_video, overall_volume)
    else:
        console.print("[yellow]No adjustments requested — copying input to output[/yellow]")
        import shutil
        shutil.copy2(input_video, output_video)

    # Extract audio as MP3
    if extract_audio:
        audio_output = output_video.with_suffix(".mp3")
        try:
            _extract_audio(output_video, audio_output)
        except Exception as e:
            console.print(f"[yellow]Warning: Audio extraction failed: {e}[/yellow]")

    return output_video


def _run_ffmpeg(cmd: list, description: str = "FFmpeg"):
    """Run an FFmpeg command and handle errors."""
    console.print(f"[dim]Running {description}...[/dim]")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"{description} failed: {result.stderr[-500:]}")


def _speed_only(input_video: Path, output_video: Path, speed: float):
    """Adjust video speed with re-encode (video + audio)."""
    pts_factor = 1.0 / speed
    atempo = build_atempo_chain(speed)

    cmd = [
        "ffmpeg", "-y", "-i", str(input_video),
        "-filter:v", f"setpts={pts_factor:.6f}*PTS",
        "-filter:a", atempo,
        "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-r", "30",
        "-c:a", "aac", "-b:a", "192k",
        str(output_video)
    ]
    _run_ffmpeg(cmd, f"Speed adjustment ({speed:.2f}x)")


def _volume_only(input_video: Path, output_video: Path, volume: float):
    """Adjust audio volume without re-encoding video (-c:v copy)."""
    cmd = [
        "ffmpeg", "-y", "-i", str(input_video),
        "-c:v", "copy",
        "-filter:a", f"volume={volume:.4f}",
        "-c:a", "aac", "-b:a", "192k",
        str(output_video)
    ]
    _run_ffmpeg(cmd, f"Volume adjustment ({volume:.2f}x, no video re-encode)")


def _speed_and_volume(input_video: Path, output_video: Path, speed: float, volume: float):
    """Adjust both speed and volume (requires video re-encode)."""
    pts_factor = 1.0 / speed
    atempo = build_atempo_chain(speed)

    cmd = [
        "ffmpeg", "-y", "-i", str(input_video),
        "-filter:v", f"setpts={pts_factor:.6f}*PTS",
        "-filter:a", f"{atempo},volume={volume:.4f}",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-r", "30",
        "-c:a", "aac", "-b:a", "192k",
        str(output_video)
    ]
    _run_ffmpeg(cmd, f"Speed ({speed:.2f}x) + volume ({volume:.2f}x)")


def _remix_video(
    input_video: Path,
    output_video: Path,
    speed: float,
    voice_audio: Path,
    music_audio: Optional[Path],
    voice_volume: float,
    music_volume: float,
    has_speed_change: bool,
):
    """Strip audio from video, remix voice + music at specified volumes."""
    has_music = music_audio is not None and music_audio.exists()

    # Build video filter
    video_filter = f"setpts={1.0/speed:.6f}*PTS" if has_speed_change else None

    # Build audio filter_complex
    # Voice is input 1, music (if present) is input 2
    inputs = ["-i", str(input_video), "-i", str(voice_audio)]
    if has_music:
        inputs.extend(["-i", str(music_audio)])

    filter_parts = []

    # Voice processing: volume + speed adjustment
    voice_filters = f"volume={voice_volume:.4f}"
    if has_speed_change:
        voice_filters += f",{build_atempo_chain(speed)}"
    filter_parts.append(f"[1:a]{voice_filters}[voice]")

    if has_music:
        # Music processing: volume + loop + trim to match video duration
        # We use aloop to loop music, then trim to video length
        music_filters = f"volume={music_volume:.4f}"
        if has_speed_change:
            music_filters += f",{build_atempo_chain(speed)}"
        filter_parts.append(f"[2:a]aloop=loop=-1:size=2e+09,{music_filters}[music]")
        filter_parts.append("[voice][music]amix=inputs=2:duration=shortest:dropout_transition=3[aout]")
        audio_map = "[aout]"
    else:
        audio_map = "[voice]"

    filter_complex = ";".join(filter_parts)

    cmd = ["ffmpeg", "-y"] + inputs

    if video_filter:
        # Need full filter_complex with video
        full_filter = f"[0:v]{video_filter}[vout];{filter_complex}"
        cmd.extend([
            "-filter_complex", full_filter,
            "-map", "[vout]", "-map", audio_map,
            "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-r", "30",
        ])
    else:
        # No video re-encode needed
        cmd.extend([
            "-filter_complex", filter_complex,
            "-map", "0:v", "-map", audio_map,
            "-c:v", "copy",
        ])

    cmd.extend(["-c:a", "aac", "-b:a", "192k", "-shortest", str(output_video)])

    remix_desc = "Remix (voice"
    if has_music:
        remix_desc += " + music"
    if has_speed_change:
        remix_desc += f" + {speed:.2f}x speed"
    remix_desc += ")"
    _run_ffmpeg(cmd, remix_desc)


def _extract_audio(video_path: Path, audio_output_path: Path) -> Path:
    """Extract audio from video as high-quality MP3."""
    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-vn", "-acodec", "libmp3lame",
        "-ar", "44100", "-ac", "2", "-b:a", "192k",
        str(audio_output_path)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Audio extraction failed: {result.stderr[-300:]}")
    console.print(f"[green]Extracted audio:[/green] {audio_output_path.name}")
    return audio_output_path
