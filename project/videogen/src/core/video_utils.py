"""
Video Utilities
Core video metadata and probing utilities using ffprobe/ffmpeg.
"""

import subprocess
from pathlib import Path
from typing import Tuple


def get_duration(file_path: Path) -> float:
    """
    Get duration of a video or audio file in seconds using ffprobe.

    Args:
        file_path: Path to video or audio file

    Returns:
        Duration in seconds (float)
    """
    # Try format=duration first
    for entries in ["format=duration", "stream=duration"]:
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", entries,
            "-of", "csv=p=0",
            str(file_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            val = result.stdout.strip().split("\n")[0].strip()
            try:
                return float(val)
            except (ValueError, TypeError):
                continue

    # Fallback: count frames × fps
    cmd = [
        "ffprobe", "-v", "error",
        "-count_frames", "-select_streams", "v:0",
        "-show_entries", "stream=nb_read_frames,r_frame_rate",
        "-of", "csv=p=0",
        str(file_path)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        try:
            parts = result.stdout.strip().split(",")
            fps_str = parts[0]
            num, den = fps_str.split("/")
            fps = int(num) / int(den)
            frames = int(parts[1])
            return frames / fps if fps > 0 else 0.0
        except Exception:
            pass

    return 0.0


def get_video_dimensions(video_path: Path) -> Tuple[int, int]:
    """
    Get video width and height, rounded to even numbers for encoding.

    Args:
        video_path: Path to video file

    Returns:
        Tuple of (width, height) as even integers
    """
    cmd = [
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height", "-of", "csv=p=0",
        str(video_path)
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    parts = r.stdout.strip().split(",")
    w, h = int(parts[0]), int(parts[1])
    return w - (w % 2), h - (h % 2)


def get_video_fps(video_path: Path) -> float:
    """
    Get video frame rate using ffprobe.

    Args:
        video_path: Path to video file

    Returns:
        Frame rate as float (e.g., 30.0, 29.97)
    """
    cmd = [
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=r_frame_rate", "-of", "csv=p=0",
        str(video_path)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        fps_str = result.stdout.strip()
        try:
            num, den = fps_str.split("/")
            return int(num) / int(den)
        except Exception:
            pass
    return 30.0  # Default fallback


def probe_video(video_path: Path, entries: str) -> str:
    """
    Generic ffprobe wrapper for extracting video metadata.

    Args:
        video_path: Path to video file
        entries: ffprobe entries to show (e.g., "stream=duration,width,height")

    Returns:
        Raw ffprobe output as string
    """
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", entries,
        "-of", "csv=p=0",
        str(video_path)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout.strip()
