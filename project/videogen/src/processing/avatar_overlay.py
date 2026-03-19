"""
Avatar overlay — composites an image or video avatar in a corner of a video.
"""
import subprocess
from pathlib import Path


def overlay_avatar(
    input_video: Path,
    avatar_source: Path,
    output_video: Path,
    position: str = "bottom-right",
    scale: float = 0.15,
    margin: int = 20,
    opacity: float = 1.0,
    border_radius: int = 0,
    fps: int = 30,
) -> Path:
    """
    Overlay an avatar (image or video) on a corner of the main video.

    Args:
        input_video: Path to the main video file.
        avatar_source: Path to avatar image (.png/.jpg) or video (.mp4/.mov).
        output_video: Path for the output video.
        position: Corner position — top-left, top-right, bottom-left, bottom-right.
        scale: Avatar size as fraction of video width (0.1 = 10%, 0.2 = 20%).
        margin: Pixel margin from edges.
        opacity: Avatar opacity (0.0–1.0). Only for image avatars.
        border_radius: Round the avatar corners (0 = square). Requires image avatar.
        fps: Output FPS.

    Returns:
        Path to the output video.
    """
    input_video = Path(input_video)
    avatar_source = Path(avatar_source)
    output_video = Path(output_video)

    # Get main video dimensions
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height",
         "-of", "csv=p=0", str(input_video)],
        capture_output=True, text=True,
    )
    w, h = [int(x) for x in probe.stdout.strip().split(",")]

    avatar_w = int(w * scale)

    # Calculate overlay position
    positions = {
        "top-left": (margin, margin),
        "top-right": (f"W-w-{margin}", margin),
        "bottom-left": (margin, f"H-h-{margin}"),
        "bottom-right": (f"W-w-{margin}", f"H-h-{margin}"),
    }
    pos = positions.get(position, positions["bottom-right"])
    ox, oy = pos

    ext = avatar_source.suffix.lower()
    is_video_avatar = ext in (".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v")

    if is_video_avatar:
        # Video avatar: loop to match main video duration, scale, overlay
        filter_complex = (
            f"[1:v]scale={avatar_w}:-1,loop=-1:size=32767[avatar];"
            f"[0:v][avatar]overlay={ox}:{oy}:shortest=1[out]"
        )
        cmd = [
            "ffmpeg", "-y",
            "-i", str(input_video),
            "-i", str(avatar_source),
            "-filter_complex", filter_complex,
            "-map", "[out]", "-map", "0:a?",
            "-c:v", "libx264", "-preset", "fast",
            "-c:a", "aac", "-b:a", "192k",
            "-r", str(fps),
            str(output_video),
        ]
    else:
        # Image avatar: scale and overlay
        if opacity < 1.0:
            alpha_filter = f",format=rgba,colorchannelmixer=aa={opacity}"
        else:
            alpha_filter = ""

        filter_complex = (
            f"[1:v]scale={avatar_w}:-1{alpha_filter}[avatar];"
            f"[0:v][avatar]overlay={ox}:{oy}[out]"
        )
        cmd = [
            "ffmpeg", "-y",
            "-i", str(input_video),
            "-i", str(avatar_source),
            "-filter_complex", filter_complex,
            "-map", "[out]", "-map", "0:a?",
            "-c:v", "libx264", "-preset", "fast",
            "-c:a", "aac", "-b:a", "192k",
            "-r", str(fps),
            str(output_video),
        ]

    print(f"Overlaying avatar ({position}, {int(scale*100)}% width)...")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg overlay failed: {result.stderr[-500:]}")

    print(f"Avatar overlay complete → {output_video}")
    return output_video
