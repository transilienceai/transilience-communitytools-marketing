"""
Caption renderer — generates ASS subtitles with per-word color highlighting.

Shows ~7 words at a time, currently spoken word in orange, rest in white.
Burns captions via single FFmpeg pass (fast).
"""
from __future__ import annotations

import subprocess
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from rich.console import Console

console = Console()

# Config
NARRATION_OFFSET = 0.3
FONT_SIZE = 40
MAX_WORDS_PER_GROUP = 7


@dataclass
class CaptionWord:
    text: str
    start: float
    end: float


@dataclass
class CaptionSentence:
    words: List[CaptionWord]

    @property
    def start(self) -> float:
        return self.words[0].start if self.words else 0.0

    @property
    def end(self) -> float:
        return self.words[-1].end if self.words else 0.0


def _group_into_chunks(words: List[CaptionWord]) -> List[CaptionSentence]:
    """Group words into phrases — max 7 words, split on punctuation or pause."""
    if not words:
        return []

    chunks: List[CaptionSentence] = []
    current: List[CaptionWord] = [words[0]]

    for i in range(1, len(words)):
        prev_text = words[i - 1].text.rstrip()
        gap = words[i].start - words[i - 1].end

        has_punct = prev_text and prev_text[-1] in ".!?;:,"
        has_pause = gap > 0.2
        at_max = len(current) >= MAX_WORDS_PER_GROUP

        if has_punct or has_pause or at_max:
            chunks.append(CaptionSentence(words=current))
            current = [words[i]]
        else:
            current.append(words[i])

    if current:
        chunks.append(CaptionSentence(words=current))

    return chunks


def _format_ass_time(seconds: float) -> str:
    """Convert seconds to ASS timestamp: H:MM:SS.cc"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def _generate_ass(
    groups: List[CaptionSentence],
    video_width: int, video_height: int,
) -> str:
    """Generate ASS subtitle with karaoke word highlighting (orange active, white rest)."""
    # ASS colors: &HBBGGRR& (BGR not RGB)
    white = "&H00FFFFFF"
    orange = "&H0000A5FF"
    outline = "&H00000000"

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {video_width}
PlayResY: {video_height}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,{FONT_SIZE},{white},{orange},{outline},&H00000000,-1,0,0,0,100,100,0,0,1,3,0,2,40,40,60,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    events = []
    for group in groups:
        start = max(0, group.start - NARRATION_OFFSET)
        end = group.end - NARRATION_OFFSET
        if end <= start:
            continue

        # Build karaoke text — each word gets a \kf tag with duration in centiseconds
        # \kf fills the word with SecondaryColour (orange) over the duration
        parts = []
        for word in group.words:
            dur_cs = max(1, int((word.end - word.start) * 100))
            parts.append(f"{{\\kf{dur_cs}}}{word.text}")

        text = " ".join(parts)
        events.append(
            f"Dialogue: 0,{_format_ass_time(start)},{_format_ass_time(end)},Default,,0,0,0,karaoke,{text}"
        )

    return header + "\n".join(events) + "\n"


def burn_captions_onto_video(
    video_path: Path,
    words: List[dict],
    output_path: Path,
    fps: float = 30.0,
    caption_style: str = "word",
) -> Path:
    """Burn captions onto video using FFmpeg ASS subtitles (fast, single pass)."""
    console.print("[cyan]Burning captions...[/cyan]")

    caption_words = [
        CaptionWord(
            text=w.get("text", getattr(w, "text", "")) if isinstance(w, dict) else w.text,
            start=w.get("start", getattr(w, "start", 0.0)) if isinstance(w, dict) else w.start,
            end=w.get("end", getattr(w, "end", 0.0)) if isinstance(w, dict) else w.end,
        )
        for w in words
    ]

    groups = _group_into_chunks(caption_words)

    if not groups:
        console.print("[yellow]No caption words, skipping[/yellow]")
        shutil.copy2(str(video_path), str(output_path))
        return output_path

    # Get video dimensions
    probe_cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height",
        "-of", "csv=p=0",
        str(video_path),
    ]
    probe = subprocess.run(probe_cmd, capture_output=True, text=True)
    try:
        w, h = probe.stdout.strip().split(",")
        video_w, video_h = int(w), int(h)
    except ValueError:
        video_w, video_h = 1920, 1080

    console.print(f"  {len(caption_words)} words, {len(groups)} groups")

    # Generate ASS file
    ass_content = _generate_ass(groups, video_w, video_h)
    ass_path = Path(tempfile.mktemp(suffix=".ass"))
    ass_path.write_text(ass_content)

    # Burn with FFmpeg — single pass
    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-vf", f"ass={ass_path}",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18",
        "-c:a", "copy",
        str(output_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    ass_path.unlink(missing_ok=True)

    if result.returncode != 0:
        console.print(f"  [yellow]Caption burn failed, copying original[/yellow]")
        shutil.copy2(str(video_path), str(output_path))
    else:
        console.print("  [green]Captions burned[/green]")

    return output_path
