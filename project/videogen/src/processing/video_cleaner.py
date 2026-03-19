"""
Video Cleaner
Motion detection and still frame removal utilities.
"""

import subprocess
import tempfile
import shutil
from pathlib import Path
from typing import List, Tuple, Optional
import cv2
import numpy as np
from rich.console import Console

console = Console()


def analyze_motion(video_path: Path) -> Tuple[float, float, List[Tuple[float, float]]]:
    """
    Analyze frame-to-frame motion in a video using OpenCV.

    Args:
        video_path: Path to video file

    Returns:
        Tuple of (fps, duration, motion_data)
        motion_data: List of (timestamp, motion_percentage) tuples
    """
    cap = cv2.VideoCapture(str(video_path))
    fps = cap.get(cv2.CAP_PROP_FPS)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total / fps if fps > 0 else 0

    ret, prev = cap.read()
    if not ret:
        cap.release()
        return fps, duration, []

    scale = 0.1
    prev_g = cv2.GaussianBlur(
        cv2.cvtColor(cv2.resize(prev, None, fx=scale, fy=scale), cv2.COLOR_BGR2GRAY),
        (7, 7), 0
    )

    motion = []
    idx = 1
    sample_every = 6

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if idx % sample_every != 0:
            idx += 1
            continue

        g = cv2.GaussianBlur(
            cv2.cvtColor(cv2.resize(frame, None, fx=scale, fy=scale), cv2.COLOR_BGR2GRAY),
            (7, 7), 0
        )
        diff = cv2.absdiff(prev_g, g)
        _, thresh = cv2.threshold(diff, 10, 255, cv2.THRESH_BINARY)
        pct = (np.count_nonzero(thresh) / thresh.size) * 100
        motion.append((idx / fps, pct))
        prev_g = g
        idx += 1

    cap.release()
    return fps, duration, motion


def find_stillness_periods(
    motion: List[Tuple[float, float]],
    threshold: float = 0.005,
    min_duration: float = 1.5
) -> List[Tuple[float, float, float]]:
    """
    Find periods where motion is below threshold.

    Args:
        motion: List of (timestamp, motion_percentage) tuples
        threshold: Motion threshold (below = still)
        min_duration: Minimum duration to consider a stillness period (seconds)

    Returns:
        List of (start, end, duration) tuples for still periods
    """
    periods = []
    in_still = False
    start = 0.0

    for t, m in motion:
        if m < threshold:
            if not in_still:
                in_still = True
                start = t
        else:
            if in_still:
                dur = t - start
                if dur >= min_duration:
                    periods.append((start, t, dur))
                in_still = False

    if in_still and motion:
        dur = motion[-1][0] - start
        if dur >= min_duration:
            periods.append((start, motion[-1][0], dur))

    return periods


def clean_video(
    video_path: Path,
    output_path: Optional[Path] = None
) -> Tuple[Path, List[Tuple[float, float]]]:
    """
    Remove still/repetitive frames from video by detecting and removing stillness periods.

    Args:
        video_path: Path to input video
        output_path: Optional output path (defaults to {video_stem}_cleaned.mp4)

    Returns:
        Tuple of (cleaned_video_path, movement_segments)
        movement_segments: List of (start, end) time ranges kept in the video
    """
    if output_path is None:
        output_path = video_path.parent / f"{video_path.stem}_cleaned.mp4"

    console.print("[dim]Analyzing motion...[/dim]")
    fps, duration, motion = analyze_motion(video_path)

    stillness = find_stillness_periods(motion)
    total_still = sum(d for _, _, d in stillness)

    console.print(f"  Found {len(stillness)} still periods ({total_still:.1f}s of {duration:.1f}s)")

    # Build movement segments (inverse of stillness)
    segments = []
    cursor = 0.0
    for start, end, _ in stillness:
        if start > cursor + 0.2:
            segments.append((cursor, start))
        cursor = end
    if cursor < duration - 0.2:
        segments.append((cursor, duration))

    if not segments:
        console.print("[yellow]No movement detected — keeping original video[/yellow]")
        return video_path, [(0.0, duration)]

    total_kept = sum(e - s for s, e in segments)
    console.print(f"  Keeping {len(segments)} segments ({total_kept:.1f}s, {total_kept/duration*100:.0f}%)")

    # Extract and concatenate movement segments
    temp_dir = Path(tempfile.mkdtemp())
    temp_clips = []

    for i, (start, end) in enumerate(segments):
        temp = temp_dir / f"seg_{i:03d}.mp4"
        cmd = [
            "ffmpeg", "-y", "-ss", f"{start:.3f}", "-i", str(video_path),
            "-t", f"{end - start:.3f}",
            "-c", "copy",
            "-avoid_negative_ts", "make_zero",
            str(temp)
        ]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode == 0:
            temp_clips.append(temp)

    # Concatenate
    concat_file = temp_dir / "concat.txt"
    concat_file.write_text("\n".join(f"file '{c}'" for c in temp_clips))

    cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file),
        "-c", "copy",
        str(output_path)
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)

    # Cleanup temp
    shutil.rmtree(temp_dir, ignore_errors=True)

    if r.returncode != 0:
        console.print(f"[red]Cleaning failed — using original[/red]")
        return video_path, [(0.0, duration)]

    console.print(f"[green]✓ Cleaned video:[/green] {output_path.name} ({total_kept:.1f}s)")
    return output_path, segments
