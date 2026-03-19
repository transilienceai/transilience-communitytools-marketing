"""
Video Effects
Cinematic effects (zoom, pan, color grading, transitions) using ffmpeg.
"""

import subprocess
import shutil
from pathlib import Path
from typing import List, Tuple
from rich.console import Console
from ..core.video_utils import get_duration, get_video_dimensions

console = Console()


def apply_cinematic_effects(
    video_path: Path,
    movement_segments: List[Tuple[float, float]],
    output_path: Path
) -> Path:
    """
    Single-pass cinematic effects — all effects enabled:

    - Zoom pulses (scale eval=frame) every 12s
    - Smooth black dips every 6s via eq brightness Gaussian curves
    - Alternating: zoom+dip at even flashes, dip-only at odd flashes
    - Smooth up/down vertical drift via sine wave
    - Subtle color grading + vignette
    - Fade in at start, fade out at end

    Args:
        video_path: Path to input video
        movement_segments: List of (start, end) movement segments (not used, but kept for API compatibility)
        output_path: Path for output video with effects

    Returns:
        Path to the output video (or original if effects fail)
    """
    total_dur = get_duration(video_path)
    if total_dur <= 0:
        shutil.copy2(video_path, output_path)
        return output_path

    W, H = get_video_dimensions(video_path)

    flash_interval = 12.0  # black dip every 12 seconds

    # Build flash timestamps
    flash_times = []
    t = flash_interval
    while t < total_dur - 1.0:
        flash_times.append(t)
        t += flash_interval

    # Build zoom expression
    # Every other flash gets a zoom pulse (alternating: zoom+flash, flash-only)
    zoom_times = [ft for i, ft in enumerate(flash_times) if i % 2 == 0]

    if zoom_times:
        S = 15
        ss = S * S
        pulse_terms = []
        for zt in zoom_times:
            pulse_terms.append(
                f"exp(-(t-{zt:.3f})*(t-{zt:.3f})*{ss})"
            )
        zoom_sum = "+".join(pulse_terms)
        zoom_expr = f"1.03+0.07*({zoom_sum})"
    else:
        zoom_expr = "1.03"

    # Build smooth black dip expression
    # Instead of hard drawbox on/off, use eq brightness with Gaussian dips
    # Each dip smoothly fades to black and back over ~0.3s
    # Sharpness=50 → half-width ~0.14s each side → ~0.3s total dip
    dip_sharpness = 50
    if flash_times:
        dip_terms = []
        for ft in flash_times:
            dip_terms.append(
                f"exp(-(t-{ft:.3f})*(t-{ft:.3f})*{dip_sharpness})"
            )
        dip_sum = "+".join(dip_terms)
        # Normal brightness 0.02, dip to -1.0 (black) at each flash
        brightness_expr = f"0.02-1.02*({dip_sum})"
    else:
        brightness_expr = "0.02"

    # Vertical drift: smooth up-and-down oscillation via sine wave
    # sin(t*0.3) has ~21s period — gentle, not seasick
    # 0.5+0.5*sin(...) maps to 0..1 range (top..bottom)
    drift_expr = "0.5+0.5*sin(t*0.3)"

    fade_out_start = max(0, total_dur - 0.8)

    vf_parts = [
        # Scale with zoom pulses (eval=frame for dynamic zoom)
        f"scale='trunc(iw*({zoom_expr})/2)*2'"
        f":'trunc(ih*({zoom_expr})/2)*2'"
        f":eval=frame",
        # Crop with vertical drift
        f"crop={W}:{H}:(iw-{W})/2:(ih-{H})*{drift_expr}",
        # Color grade + smooth black dips (eval=frame for dynamic brightness)
        f"eq=brightness='{brightness_expr}':saturation=1.08:eval=frame",
        # Vignette
        "vignette=PI/5",
    ]

    # Fade in at start, fade out at end
    vf_parts.append("fade=t=in:d=0.6")
    vf_parts.append(f"fade=t=out:st={fade_out_start:.2f}:d=0.8")

    vf = ",".join(vf_parts)

    cmd = [
        "ffmpeg", "-y", "-i", str(video_path),
        "-vf", vf,
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
        "-c:a", "aac", "-b:a", "192k",
        str(output_path)
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)

    if r.returncode != 0 or not output_path.exists():
        console.print(f"[yellow]Cinematic effects failed — using original video[/yellow]")
        console.print(f"[dim]{r.stderr[-200:] if r.stderr else ''}[/dim]")
        shutil.copy2(video_path, output_path)
    else:
        flash_count = len(flash_times)
        zoom_count = len(zoom_times)
        console.print(
            f"[green]✓ Cinematic effects applied:[/green] "
            f"{flash_count} smooth black dips ({zoom_count} with zoom) + drift + color grade + vignette"
        )

    return output_path
