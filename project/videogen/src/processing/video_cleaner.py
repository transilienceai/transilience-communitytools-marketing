"""
Video Cleaner
Motion detection and still frame removal utilities.
Splits large videos into 3-minute chunks, cleans in parallel, then merges.
"""

import subprocess
import tempfile
import shutil
import math
from pathlib import Path
from typing import List, Tuple, Optional
from concurrent.futures import ProcessPoolExecutor, as_completed
import cv2
import numpy as np
from rich.console import Console

console = Console()

CHUNK_SECONDS = 180  # 3 minutes


def _get_video_duration(video_path: Path) -> float:
    cmd = [
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(video_path)
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    return float(r.stdout.strip()) if r.returncode == 0 else 0.0


def _split_video(video_path: Path, chunk_dir: Path, chunk_secs: int = CHUNK_SECONDS) -> List[Path]:
    duration = _get_video_duration(video_path)
    if duration <= 0:
        return []
    num_chunks = math.ceil(duration / chunk_secs)
    chunks = []
    for i in range(num_chunks):
        start = i * chunk_secs
        out = chunk_dir / f"chunk_{i:03d}.mp4"
        cmd = [
            "ffmpeg", "-y", "-ss", str(start), "-i", str(video_path),
            "-t", str(chunk_secs), "-c", "copy",
            "-avoid_negative_ts", "make_zero",
            str(out)
        ]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode == 0 and out.exists():
            chunks.append(out)
    return chunks


def analyze_motion(video_path: Path) -> Tuple[float, float, List[Tuple[float, float]]]:
    """
    Analyze frame-to-frame motion in a video using OpenCV.

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


def detect_shaky_periods(
    video_path: Path,
    window: float = 1.0,
    shake_threshold: float = 3.0,
    min_duration: float = 0.5,
) -> List[Tuple[float, float, float]]:
    """
    Detect shaky sections using optical flow variance.

    Shaky frames have rapid, erratic global motion — high variance in
    frame-to-frame displacement vectors over a short window.

    Args:
        video_path: Path to video
        window: Sliding window size in seconds to measure shake
        shake_threshold: Std-dev of displacement above which = shaky (pixels at analysis scale)
        min_duration: Minimum shaky period length to report (seconds)

    Returns:
        List of (start, end, avg_shake_intensity) tuples
    """
    cap = cv2.VideoCapture(str(video_path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total / fps if fps > 0 else 0

    ret, prev = cap.read()
    if not ret:
        cap.release()
        return []

    scale = 0.25
    prev_g = cv2.cvtColor(cv2.resize(prev, None, fx=scale, fy=scale), cv2.COLOR_BGR2GRAY)

    # Collect per-frame global displacement using phase correlation
    displacements: List[Tuple[float, float, float]] = []  # (timestamp, dx, dy)
    idx = 1
    sample_every = 2  # finer sampling for shake detection

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if idx % sample_every != 0:
            idx += 1
            continue

        g = cv2.cvtColor(cv2.resize(frame, None, fx=scale, fy=scale), cv2.COLOR_BGR2GRAY)

        # Phase correlation gives sub-pixel global shift between frames
        shift, _response = cv2.phaseCorrelate(
            prev_g.astype(np.float64),
            g.astype(np.float64),
        )
        dx, dy = shift
        displacements.append((idx / fps, dx, dy))
        prev_g = g
        idx += 1

    cap.release()

    if len(displacements) < 3:
        return []

    # Sliding window: compute std-dev of displacement within each window
    window_samples = max(int(window * fps / sample_every), 3)
    shake_data: List[Tuple[float, float]] = []  # (timestamp, shake_intensity)

    for i in range(len(displacements) - window_samples + 1):
        win = displacements[i : i + window_samples]
        dxs = [d[1] for d in win]
        dys = [d[2] for d in win]
        # Shake = std dev of displacement vectors (high = erratic motion)
        intensity = (np.std(dxs) ** 2 + np.std(dys) ** 2) ** 0.5
        mid_t = win[len(win) // 2][0]
        shake_data.append((mid_t, intensity))

    # Find contiguous shaky periods
    periods: List[Tuple[float, float, float]] = []
    in_shake = False
    start = 0.0
    intensities: List[float] = []

    for t, intensity in shake_data:
        if intensity >= shake_threshold:
            if not in_shake:
                in_shake = True
                start = t
                intensities = []
            intensities.append(intensity)
        else:
            if in_shake:
                dur = t - start
                if dur >= min_duration:
                    avg_i = sum(intensities) / len(intensities)
                    periods.append((start, t, avg_i))
                in_shake = False
                intensities = []

    if in_shake and shake_data:
        dur = shake_data[-1][0] - start
        if dur >= min_duration:
            avg_i = sum(intensities) / len(intensities)
            periods.append((start, shake_data[-1][0], avg_i))

    return periods


def find_stillness_periods(
    motion: List[Tuple[float, float]],
    threshold: float = 10.0,
    min_duration: float = 1.5
) -> List[Tuple[float, float, float]]:
    """
    Find periods where motion is below threshold.

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


def _clean_chunk(
    chunk_path: Path,
    output_path: Path,
    threshold: float = 10.0,
    remove_shaky: bool = False,
    shake_threshold: float = 3.0,
) -> Tuple[Path, List[Tuple[float, float]], List[Tuple[float, float, float]]]:
    """Clean a single chunk — meant to run in a separate process.

    Returns:
        (output_path, kept_segments, shaky_periods)
    """
    fps, duration, motion = analyze_motion(chunk_path)
    stillness = find_stillness_periods(motion, threshold=threshold)

    # Detect shaky periods
    shaky_periods: List[Tuple[float, float, float]] = []
    if remove_shaky:
        shaky_periods = detect_shaky_periods(chunk_path, shake_threshold=shake_threshold)

    # Merge stillness + shaky into one "bad periods" list
    bad_periods = [(s, e) for s, e, _ in stillness]
    bad_periods += [(s, e) for s, e, _ in shaky_periods]
    # Sort and merge overlapping intervals
    bad_periods.sort()
    merged_bad: List[Tuple[float, float]] = []
    for s, e in bad_periods:
        if merged_bad and s <= merged_bad[-1][1]:
            merged_bad[-1] = (merged_bad[-1][0], max(merged_bad[-1][1], e))
        else:
            merged_bad.append((s, e))

    # Build keep segments (inverse of bad periods)
    segments = []
    cursor = 0.0
    for start, end in merged_bad:
        if start > cursor + 0.2:
            segments.append((cursor, start))
        cursor = end
    if cursor < duration - 0.2:
        segments.append((cursor, duration))

    if not segments:
        # Entire chunk is bad — keep a 2s representative sample from the start
        segments = [(0.0, min(2.0, duration))]

    temp_dir = Path(tempfile.mkdtemp())
    temp_clips = []

    for i, (start, end) in enumerate(segments):
        temp = temp_dir / f"seg_{i:03d}.mp4"
        cmd = [
            "ffmpeg", "-y", "-ss", f"{start:.3f}", "-i", str(chunk_path),
            "-t", f"{end - start:.3f}",
            "-c", "copy",
            "-avoid_negative_ts", "make_zero",
            str(temp)
        ]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode == 0 and temp.exists():
            temp_clips.append(temp)

    if not temp_clips:
        shutil.rmtree(temp_dir, ignore_errors=True)
        return chunk_path, [(0.0, duration)], shaky_periods

    concat_file = temp_dir / "concat.txt"
    concat_file.write_text("\n".join(f"file '{c.resolve()}'" for c in temp_clips))

    cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file),
        "-c", "copy",
        str(output_path)
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)

    shutil.rmtree(temp_dir, ignore_errors=True)

    if r.returncode != 0 or not output_path.exists():
        return chunk_path, [(0.0, duration)], shaky_periods

    return output_path, segments, shaky_periods


def clean_video(
    video_path: Path,
    output_path: Optional[Path] = None,
    threshold: float = 10.0,
    remove_shaky: bool = False,
    shake_threshold: float = 3.0,
) -> Tuple[Path, List[Tuple[float, float]]]:
    """
    Remove still/repetitive frames and optionally shaky frames from video.
    Splits into 3-min chunks, cleans in parallel, then merges.

    Args:
        threshold: Motion % below which frames are considered still (0-100).
                   10 = only near-identical, 50 = removes 50%+ similar frames.
        remove_shaky: Also detect and remove shaky/jittery sections.
        shake_threshold: Displacement std-dev above which = shaky (default 3.0).
    """
    video_path = video_path.resolve()
    if output_path is None:
        output_path = video_path.parent / f"{video_path.stem}_cleaned.mp4"
    output_path = output_path.resolve()

    duration = _get_video_duration(video_path)

    # Get fps for frame count reporting
    cap = cv2.VideoCapture(str(video_path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    cap.release()
    original_frames = int(duration * fps)

    # Short video — clean directly, no splitting
    if duration <= CHUNK_SECONDS:
        console.print(f"[dim]Analyzing motion ({duration:.0f}s, {original_frames} frames, threshold={threshold}%, remove_shaky={remove_shaky})...[/dim]")
        result_path, segments, shaky = _clean_chunk(
            video_path, output_path, threshold=threshold,
            remove_shaky=remove_shaky, shake_threshold=shake_threshold,
        )
        total_kept = sum(e - s for s, e in segments)
        kept_frames = int(total_kept * fps)
        removed_frames = original_frames - kept_frames
        shaky_duration = sum(e - s for s, e, _ in shaky)
        if result_path == output_path:
            msg = (
                f"[green]✓ Cleaned video:[/green] {output_path.name}\n"
                f"  Original: {duration:.1f}s ({original_frames} frames)\n"
                f"  Cleaned:  {total_kept:.1f}s ({kept_frames} frames)\n"
                f"  Removed:  {duration - total_kept:.1f}s ({removed_frames} frames, {removed_frames/max(original_frames,1)*100:.0f}%)"
            )
            if shaky:
                msg += f"\n  Shaky:    {len(shaky)} sections ({shaky_duration:.1f}s removed)"
            console.print(msg)
        else:
            console.print("[yellow]No still/shaky frames found — keeping original[/yellow]")
        return result_path, segments

    # Large video — split → parallel clean → merge
    temp_dir = Path(tempfile.mkdtemp())
    chunk_dir = temp_dir / "chunks"
    cleaned_dir = temp_dir / "cleaned"
    chunk_dir.mkdir()
    cleaned_dir.mkdir()

    num_chunks = math.ceil(duration / CHUNK_SECONDS)
    console.print(f"[dim]Splitting {duration:.0f}s video into {num_chunks} chunks (3 min each)...[/dim]")
    chunks = _split_video(video_path, chunk_dir)

    if not chunks:
        console.print("[yellow]Split failed — cleaning original directly[/yellow]")
        shutil.rmtree(temp_dir, ignore_errors=True)
        result_path, segments, _ = _clean_chunk(video_path, output_path, threshold=threshold, remove_shaky=remove_shaky, shake_threshold=shake_threshold)
        return result_path, segments

    console.print(f"[dim]Cleaning {len(chunks)} chunks in parallel (threshold={threshold}%, remove_shaky={remove_shaky})...[/dim]")

    # Clean chunks in parallel (one process per chunk, cap at 4 workers)
    max_workers = min(4, len(chunks))
    cleaned_chunks: List[Tuple[int, Path]] = []
    all_segments: List[Tuple[float, float]] = []
    all_shaky: List[Tuple[float, float, float]] = []

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {}
        for i, chunk in enumerate(chunks):
            cleaned_out = cleaned_dir / f"cleaned_{i:03d}.mp4"
            fut = executor.submit(_clean_chunk, chunk, cleaned_out, threshold, remove_shaky, shake_threshold)
            futures[fut] = i

        for fut in as_completed(futures):
            idx = futures[fut]
            try:
                result_path, segs, shaky = fut.result()
                cleaned_chunks.append((idx, result_path))
                all_segments.extend(segs)
                all_shaky.extend(shaky)
                shaky_info = f" ({len(shaky)} shaky sections)" if shaky else ""
                console.print(f"  [green]✓[/green] Chunk {idx + 1}/{len(chunks)} cleaned{shaky_info}")
            except Exception as e:
                console.print(f"  [yellow]⚠[/yellow] Chunk {idx + 1} failed: {e}, using original")
                cleaned_chunks.append((idx, chunks[idx]))

    # Sort by original order
    cleaned_chunks.sort(key=lambda x: x[0])

    # Merge cleaned chunks
    console.print(f"[dim]Merging {len(cleaned_chunks)} cleaned chunks...[/dim]")
    concat_file = temp_dir / "final_concat.txt"
    concat_file.write_text("\n".join(f"file '{p.resolve()}'" for _, p in cleaned_chunks))

    cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file),
        "-c", "copy",
        str(output_path)
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)

    if r.returncode != 0 or not output_path.exists():
        # Fallback: re-encode merge
        cmd = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file),
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18",
            "-c:a", "aac", "-b:a", "192k",
            str(output_path)
        ]
        r = subprocess.run(cmd, capture_output=True, text=True)

    shutil.rmtree(temp_dir, ignore_errors=True)

    if not output_path.exists():
        console.print("[red]Merge failed — using original[/red]")
        return video_path, [(0.0, duration)]

    cleaned_duration = _get_video_duration(output_path)
    removed_duration = duration - cleaned_duration
    kept_frames = int(cleaned_duration * fps)
    removed_frames = original_frames - kept_frames
    shaky_duration = sum(e - s for s, e, _ in all_shaky)
    msg = (
        f"[green]✓ Cleaned video:[/green] {output_path.name}\n"
        f"  Original: {duration:.1f}s ({original_frames} frames)\n"
        f"  Cleaned:  {cleaned_duration:.1f}s ({kept_frames} frames)\n"
        f"  Removed:  {removed_duration:.1f}s ({removed_frames} frames, {removed_frames/max(original_frames,1)*100:.0f}%)"
    )
    if all_shaky:
        msg += f"\n  Shaky:    {len(all_shaky)} sections ({shaky_duration:.1f}s removed)"
    console.print(msg)
    return output_path, all_segments
