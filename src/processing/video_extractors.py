"""
Video Extractors
Frame and keyframe extraction utilities using ffmpeg.
"""

import subprocess
from pathlib import Path
from typing import List
from rich.console import Console
from ..core.video_utils import get_duration

console = Console()


def extract_keyframes(
    video_path: Path,
    output_dir: Path,
    max_frames: int = 5
) -> List[Path]:
    """
    Extract evenly-spaced keyframes from video using ffmpeg.

    Args:
        video_path: Path to video file
        output_dir: Directory to save keyframes
        max_frames: Maximum number of frames to extract

    Returns:
        List of paths to extracted keyframe images
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Get video duration
    dur = get_duration(video_path)
    if dur <= 0:
        return []

    # Extract evenly-spaced frames
    frames = []
    interval = dur / (max_frames + 1)
    for i in range(max_frames):
        t = interval * (i + 1)
        frame_path = output_dir / f"keyframe_{i:03d}.jpg"
        cmd = [
            "ffmpeg", "-y", "-ss", f"{t:.3f}",
            "-i", str(video_path),
            "-frames:v", "1", "-q:v", "2",
            str(frame_path)
        ]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode == 0 and frame_path.exists():
            frames.append(frame_path)

    return frames


def extract_last_frame(video_path: Path, output_path: Path) -> Path:
    """
    Extract the last frame of a video as a JPEG image.
    Used to chain Veo scenes: last frame of scene N → input image for scene N+1.

    Args:
        video_path: Path to video file
        output_path: Path to save extracted frame

    Returns:
        Path to extracted frame image

    Raises:
        RuntimeError: If frame extraction fails
    """
    # Get duration first
    dur = get_duration(video_path)
    if dur <= 0:
        raise RuntimeError(f"Cannot get duration of {video_path}")

    # Seek to near the end and grab the last frame
    # Use -sseof to seek from end (more reliable for last frame)
    cmd = [
        "ffmpeg", "-y",
        "-sseof", "-0.1",
        "-i", str(video_path),
        "-frames:v", "1", "-q:v", "2",
        "-update", "1",
        str(output_path)
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)

    if r.returncode != 0 or not output_path.exists():
        # Fallback: seek to duration - 0.1s from start
        cmd = [
            "ffmpeg", "-y",
            "-ss", f"{max(0, dur - 0.1):.3f}",
            "-i", str(video_path),
            "-frames:v", "1", "-q:v", "2",
            str(output_path)
        ]
        r = subprocess.run(cmd, capture_output=True, text=True)

    if r.returncode != 0 or not output_path.exists():
        raise RuntimeError(f"Failed to extract last frame from {video_path}")

    return output_path


def extract_frame_at_time(
    video_path: Path,
    timestamp: float,
    output_path: Path
) -> Path:
    """
    Extract a single frame at a specific timestamp.

    Args:
        video_path: Path to video file
        timestamp: Time in seconds where to extract frame
        output_path: Path to save extracted frame

    Returns:
        Path to extracted frame image

    Raises:
        RuntimeError: If frame extraction fails
    """
    cmd = [
        "ffmpeg", "-y",
        "-ss", f"{timestamp:.3f}",
        "-i", str(video_path),
        "-frames:v", "1", "-q:v", "2",
        str(output_path)
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)

    if r.returncode != 0 or not output_path.exists():
        raise RuntimeError(f"Failed to extract frame at {timestamp}s from {video_path}")

    return output_path
