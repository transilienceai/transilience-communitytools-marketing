"""
Instagram Shorts Pipeline — Extract highlights from a long video into a 40-50s short.

Flow:
1. Transcribe video with word-level timestamps (ElevenLabs Scribe)
2. AI picks the most impactful sentences (Gemini)
3. Extract those video segments via FFmpeg
4. Normalize + concat into a 40-50 second short
"""
from __future__ import annotations

import json
import subprocess
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

from rich.console import Console
from rich.panel import Panel

console = Console()


def _log(msg: str):
    """Print via raw stdout for reliable Modal log capture."""
    import sys
    sys.stdout.write(msg + "\n")
    sys.stdout.flush()

PADDING = 0.0    # no padding — fades handle transitions


@dataclass
class Highlight:
    """A selected segment from the source video."""
    text: str
    start: float   # seconds
    end: float      # seconds
    reason: str = ""


def _get_video_duration(video_path: Path) -> float:
    """Get video duration via ffprobe."""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(video_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return float(result.stdout.strip() or "0")


def _transcribe_with_timestamps(video_path: Path) -> Tuple[str, list]:
    """Transcribe video, return (full_text, word_list)."""
    from ..ai.tts_engine import transcribe_elevenlabs

    _log("Step 1: Transcribing video...")
    transcript = transcribe_elevenlabs(video_path)
    _log(f"  Transcribed {len(transcript.words)} words, {transcript.duration:.1f}s")

    words = [
        {"text": w.text, "start": w.start, "end": w.end}
        for w in transcript.words
    ]
    return transcript.text, words


def _group_words_to_sentences(words: list) -> list:
    """Group words into sentences based on timing gaps and punctuation."""
    if not words:
        return []

    sentences = []
    current_words = [words[0]]

    for i in range(1, len(words)):
        gap = words[i]["start"] - words[i - 1]["end"]
        prev_text = words[i - 1]["text"].strip()
        # Split on gaps > 0.5s or sentence-ending punctuation
        if gap > 0.5 or prev_text.endswith((".", "!", "?", ":", ";")):
            text = " ".join(w["text"] for w in current_words).strip()
            if text:
                sentences.append({
                    "text": text,
                    "start": current_words[0]["start"],
                    "end": current_words[-1]["end"],
                    "duration": current_words[-1]["end"] - current_words[0]["start"],
                })
            current_words = [words[i]]
        else:
            current_words.append(words[i])

    # Last sentence
    if current_words:
        text = " ".join(w["text"] for w in current_words).strip()
        if text:
            sentences.append({
                "text": text,
                "start": current_words[0]["start"],
                "end": current_words[-1]["end"],
                "duration": current_words[-1]["end"] - current_words[0]["start"],
            })

    return sentences


def _pick_highlights(full_text: str, sentences: list, target_duration: float = 45) -> List[Highlight]:
    """Use Gemini to pick the most impactful sentences for a short."""
    from ..ai.gemini_client import generate_text

    _log("Step 2: AI selecting best moments...")

    target_min = max(10, target_duration - 5)
    target_max = target_duration

    sentences_json = json.dumps(
        [{"idx": i, "text": s["text"], "start": round(s["start"], 2), "end": round(s["end"], 2), "duration": round(s["duration"], 2)}
         for i, s in enumerate(sentences)],
        indent=2,
    )

    prompt = f"""You are an expert short-form video editor for Instagram Reels/Shorts.

Given a transcript broken into sentences with timestamps, select the BEST sentences to create a {target_duration}-second highlight reel.

CRITICAL RULES:
- Total duration of selected segments must be between {target_min} and {target_max} seconds
- EVERY selected sentence MUST be a COMPLETE, SELF-CONTAINED statement — it must make sense on its own without context from the previous sentence
- NEVER select a sentence that starts mid-thought, with "and", "but", "so", "because", "which", "that", or any continuation word
- Each selected sentence should feel like a FRESH START — as if the speaker just began talking
- DO NOT select consecutive sentences — skip between different parts of the video so each clip feels like a new scene
- Start with a strong hook — the first sentence should grab attention instantly
- Prefer punchy, quotable, declarative statements ("We built X", "This does Y", "The result is Z")
- Avoid filler, intros, "um"s, repetition, or boring segments
- REORDER the segments for maximum impact — do NOT keep chronological order
- Start with the most attention-grabbing moment as the hook
- Build momentum: hook → context → value → payoff
- End with the most memorable or shareable moment
- Return segments in your RECOMMENDED playback order (not source order)

SENTENCES:
{sentences_json}

Return ONLY a JSON array of selected sentence indices and a reason for each:
[{{"idx": 0, "reason": "strong hook"}}, {{"idx": 5, "reason": "key insight"}}, ...]"""

    response = generate_text(prompt, json_output=True)

    try:
        selections = json.loads(response)
    except json.JSONDecodeError:
        # Try to extract JSON from response
        import re
        match = re.search(r'\[.*\]', response, re.DOTALL)
        if match:
            selections = json.loads(match.group())
        else:
            raise ValueError(f"AI returned invalid JSON: {response[:200]}")

    highlights = []
    total = 0.0
    for sel in selections:
        idx = sel["idx"]
        if idx < 0 or idx >= len(sentences):
            continue
        s = sentences[idx]
        dur = s["duration"]
        if total + dur > target_max + 2:  # small overflow tolerance
            break
        highlights.append(Highlight(
            text=s["text"],
            start=s["start"],
            end=s["end"],
            reason=sel.get("reason", ""),
        ))
        total += dur

    # Merge consecutive/overlapping highlights into single segments
    highlights = _merge_consecutive(highlights)

    total = sum(h.end - h.start for h in highlights)
    _log(f"  Selected {len(highlights)} segments, total {total:.1f}s")
    for i, h in enumerate(highlights):
        _log(f"    {i+1}. [{h.start:.1f}s-{h.end:.1f}s] ({h.end - h.start:.1f}s)")

    return highlights


def _merge_consecutive(highlights: List[Highlight], gap_threshold: float = 1.0) -> List[Highlight]:
    """Merge highlights that are consecutive or within gap_threshold seconds of each other."""
    if not highlights:
        return []

    merged: List[Highlight] = [Highlight(
        text=highlights[0].text,
        start=highlights[0].start,
        end=highlights[0].end,
        reason=highlights[0].reason,
    )]

    for h in highlights[1:]:
        prev = merged[-1]
        # If this segment starts within gap_threshold of previous end, merge
        if h.start <= prev.end + gap_threshold:
            prev.end = max(prev.end, h.end)
            prev.text = f"{prev.text} {h.text}"
        else:
            merged.append(Highlight(
                text=h.text, start=h.start, end=h.end, reason=h.reason,
            ))

    return merged


# ---------------------------------------------------------------------------
# Step 3.5 — AI Scene Enhancement (Imagen + Veo visual scenes)
# ---------------------------------------------------------------------------

@dataclass
class ScenePlan:
    """Plan for enhancing a single segment with AI-generated visuals."""
    index: int
    mode: str          # "split", "replace", or "keep"
    prompt: str = ""   # Imagen/Veo scene description
    image_path: Optional[Path] = None
    video_path: Optional[Path] = None


def _plan_scene_enhancements(highlights: List[Highlight], full_text: str = "") -> List[ScenePlan]:
    """Ask Gemini to decide which segments should get AI visual scenes."""
    from ..ai.gemini_client import generate_text

    _log("Step 3.5a: Planning scene enhancements...")

    segments_json = json.dumps([
        {"idx": i, "text": h.text, "duration": round(h.end - h.start, 1)}
        for i, h in enumerate(highlights)
    ], indent=2)

    context_section = ""
    if full_text:
        context_section = f"""
FULL TRANSCRIPT (for context — understand the product, features, and brand being discussed):
\"\"\"{full_text[:1500]}\"\"\"
"""

    prompt = f"""You are a video illustrator creating helpful visuals for a speaker video. Your scenes should feel like natural B-roll footage that supports what the speaker is saying — like a professional LinkedIn or product explainer video.
{context_section}
For each segment, choose ONE mode:
- "split": Split-screen — speaker on one side, illustration on the other. Use when the speaker describes something that benefits from a visual (a product, a workflow, a team, a result).
- "replace": Full-screen — replace the speaker with the scene, keep their audio. Use sparingly for key moments where the visual IS the story.
- "keep": No change — keep the original speaker footage. Use for introductions, personal moments, or when the speaker's face is important.

SCENE PROMPT RULES:
- Match EXACTLY what the speaker says. If they say "our team reviews alerts", show a team at screens reviewing alerts. Not a futuristic hologram.
- REALISTIC and GROUNDED. Real people, real offices, real screens. No sci-fi, no glowing, no floating elements.
- Think stock footage / B-roll quality. Clean, simple, one clear subject per scene.
- Warm natural lighting, shallow depth of field, professional but approachable.
- NO text in images.
- 30-50 words per prompt.
- The first segment should usually be "keep" (establish the speaker).
- Mix of "split" and "keep" — not everything needs a scene.

GOOD: "A person at a desk looking at a laptop showing a clean dashboard with green checkmarks, modern office, natural window light"
BAD: "Holographic 3D visualization with glowing nodes and particle effects floating in dark space, 8K cinematic"

SEGMENTS:
{segments_json}

Return ONLY a JSON array:
[{{"idx": 0, "mode": "keep", "prompt": ""}}, {{"idx": 1, "mode": "split", "prompt": "A person at a desk reviewing security alerts on a monitor..."}}, ...]"""

    response = generate_text(prompt, json_output=True)

    try:
        plans_raw = json.loads(response)
    except json.JSONDecodeError:
        import re
        match = re.search(r'\[.*\]', response, re.DOTALL)
        if match:
            plans_raw = json.loads(match.group())
        else:
            _log("  Scene planning failed — keeping all segments as-is")
            return [ScenePlan(index=i, mode="keep") for i in range(len(highlights))]

    plans = []
    for p in plans_raw:
        idx = p.get("idx", -1)
        if idx < 0 or idx >= len(highlights):
            continue
        mode = p.get("mode", "keep")
        if mode not in ("split", "replace", "keep"):
            mode = "keep"
        plans.append(ScenePlan(
            index=idx,
            mode=mode,
            prompt=p.get("prompt", ""),
        ))

    # Ensure all segments have a plan
    planned_indices = {p.index for p in plans}
    for i in range(len(highlights)):
        if i not in planned_indices:
            plans.append(ScenePlan(index=i, mode="keep"))
    plans.sort(key=lambda p: p.index)

    enhanced = sum(1 for p in plans if p.mode != "keep")
    _log(f"  Planned {enhanced}/{len(plans)} segments for scene enhancement")
    for p in plans:
        if p.mode != "keep":
            _log(f"    Segment {p.index + 1}: {p.mode} — {p.prompt[:60]}...")

    return plans


def _generate_scene_visuals(
    plans: List[ScenePlan],
    highlights: List[Highlight],
    work_dir: Path,
    resolution: str = "1080p",
) -> List[ScenePlan]:
    """Generate Imagen images and Veo videos for planned scenes."""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from ..ai.imagen_generator import generate_image
    from ..ai.veo_generator import generate_video_veo

    active_plans = [p for p in plans if p.mode in ("split", "replace")]
    if not active_plans:
        return plans

    # --- Phase 1: Generate Imagen images in parallel ---
    _log(f"Step 3.5b: Generating {len(active_plans)} scene images (Imagen)...")

    def _gen_image(plan: ScenePlan) -> ScenePlan:
        aspect = "16:9" if plan.mode == "replace" else "1:1"
        out = work_dir / f"scene_img_{plan.index:03d}.png"
        try:
            generate_image(
                prompt=plan.prompt,
                output_path=out,
                aspect_ratio=aspect,
            )
            plan.image_path = out
            _log(f"    Scene {plan.index + 1} image generated")
        except Exception as e:
            _log(f"    Scene {plan.index + 1} image failed: {e}")
            plan.mode = "keep"  # fallback
        return plan

    with ThreadPoolExecutor(max_workers=min(len(active_plans), 3)) as ex:
        futures = {ex.submit(_gen_image, p): p for p in active_plans}
        for f in as_completed(futures):
            f.result()

    # --- Phase 2: Generate Veo videos from images ---
    active_plans = [p for p in plans if p.mode in ("split", "replace") and p.image_path]
    if not active_plans:
        return plans

    _log(f"Step 3.5c: Animating {len(active_plans)} scenes (Veo 3.1)...")

    def _gen_video(plan: ScenePlan) -> ScenePlan:
        seg_duration = highlights[plan.index].end - highlights[plan.index].start
        out = work_dir / f"scene_vid_{plan.index:03d}.mp4"
        try:
            generate_video_veo(
                prompt=f"{plan.prompt}. Natural realistic footage. Gentle subtle camera movement. Warm lighting, shallow depth of field. No text overlays.",
                output_path=out,
                image_path=plan.image_path,
                duration=8,
                aspect_ratio="16:9",
                resolution=resolution,
                enable_audio=False,
            )
            # Speed-adjust to match segment duration if needed
            if out.exists() and seg_duration < 7.5:
                adjusted = work_dir / f"scene_adj_{plan.index:03d}.mp4"
                speed = 8.0 / seg_duration
                vf = f"setpts={1/speed}*PTS"
                cmd = [
                    "ffmpeg", "-y", "-i", str(out),
                    "-vf", vf, "-an",
                    "-c:v", "libx264", "-preset", "fast", "-crf", "18",
                    str(adjusted),
                ]
                r = subprocess.run(cmd, capture_output=True, text=True)
                if r.returncode == 0 and adjusted.exists():
                    out.unlink(missing_ok=True)
                    out = adjusted
            plan.video_path = out
            _log(f"    Scene {plan.index + 1} video generated")
        except Exception as e:
            _log(f"    Scene {plan.index + 1} video failed: {e}")
            plan.mode = "keep"
        return plan

    with ThreadPoolExecutor(max_workers=min(len(active_plans), 3)) as ex:
        futures = {ex.submit(_gen_video, p): p for p in active_plans}
        for f in as_completed(futures):
            f.result()

    return plans


def _composite_segment(
    segment_path: Path,
    scene_video_path: Path,
    mode: str,
    output_path: Path,
    resolution: str = "1080p",
) -> Path:
    """Composite a scene video with the original segment using FFmpeg.

    split: speaker left, scene right (hstack)
    replace: scene video replaces speaker, keep original audio
    """
    target_size = {"720p": (1280, 720), "1080p": (1920, 1080), "4k": (3840, 2160)}.get(resolution, (1920, 1080))
    w, h = target_size

    if mode == "split":
        half_w = w // 2
        # Scale both to half width, full height, then hstack
        filter_complex = (
            f"[0:v]scale={half_w}:{h}:force_original_aspect_ratio=decrease,"
            f"pad={half_w}:{h}:(ow-iw)/2:(oh-ih)/2:black[left];"
            f"[1:v]scale={half_w}:{h}:force_original_aspect_ratio=decrease,"
            f"pad={half_w}:{h}:(ow-iw)/2:(oh-ih)/2:black[right];"
            f"[left][right]hstack=inputs=2[out]"
        )
        cmd = [
            "ffmpeg", "-y",
            "-i", str(segment_path),
            "-i", str(scene_video_path),
            "-filter_complex", filter_complex,
            "-map", "[out]", "-map", "0:a?",
            "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-c:a", "aac", "-b:a", "192k",
            "-shortest",
            str(output_path),
        ]
    else:  # replace
        # Use scene video with original segment's audio
        filter_complex = (
            f"[1:v]scale={w}:{h}:force_original_aspect_ratio=decrease,"
            f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black[scene]"
        )
        cmd = [
            "ffmpeg", "-y",
            "-i", str(segment_path),
            "-i", str(scene_video_path),
            "-filter_complex", filter_complex,
            "-map", "[scene]", "-map", "0:a?",
            "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-c:a", "aac", "-b:a", "192k",
            "-shortest",
            str(output_path),
        ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        _log(f"  Composite failed: {result.stderr[-200:]}")
        # Fallback: return original segment unchanged
        shutil.copy2(str(segment_path), str(output_path))

    return output_path


def _enhance_segments(
    segments: List[Path],
    highlights: List[Highlight],
    work_dir: Path,
    resolution: str = "1080p",
    full_text: str = "",
) -> List[Path]:
    """Full scene enhancement pipeline: plan → generate → composite."""
    plans = _plan_scene_enhancements(highlights, full_text)

    # Check if any enhancement is planned
    if not any(p.mode != "keep" for p in plans):
        _log("  No scene enhancements planned — keeping original footage")
        return segments

    plans = _generate_scene_visuals(plans, highlights, work_dir, resolution)

    # Composite enhanced segments
    _log("Step 3.5d: Compositing enhanced segments...")
    enhanced_segments = []
    for i, seg in enumerate(segments):
        plan = next((p for p in plans if p.index == i), None)
        if plan and plan.mode != "keep" and plan.video_path and plan.video_path.exists():
            out = work_dir / f"enhanced_{i:03d}.mp4"
            _composite_segment(seg, plan.video_path, plan.mode, out, resolution)
            if out.exists():
                enhanced_segments.append(out)
                _log(f"    Segment {i + 1}: {plan.mode} composite done")
            else:
                enhanced_segments.append(seg)
        else:
            enhanced_segments.append(seg)

    return enhanced_segments


def _extract_segments(video_path: Path, highlights: List[Highlight], work_dir: Path) -> List[Path]:
    """Extract all segments in parallel with fast seeking."""
    _log("Step 3: Extracting video segments...")

    from concurrent.futures import ThreadPoolExecutor, as_completed

    def _extract_one(i: int, h: Highlight) -> Tuple[int, Optional[Path]]:
        out = work_dir / f"segment_{i:03d}.mp4"
        # -ss before -i for fast seek, re-encode for precise cut point
        cmd = [
            "ffmpeg", "-y",
            "-ss", str(max(0, h.start - 0.1)),  # seek slightly before
            "-i", str(video_path),
            "-ss", "0.1",  # skip the 0.1s we seeked early
            "-t", str(h.end - h.start),
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18",
            "-c:a", "aac", "-b:a", "192k",
            str(out),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0 and out.exists():
            return i, out
        return i, None

    # Run all extractions in parallel
    results: dict[int, Optional[Path]] = {}
    with ThreadPoolExecutor(max_workers=min(len(highlights), 4)) as executor:
        futures = {executor.submit(_extract_one, i, h): i for i, h in enumerate(highlights)}
        for future in as_completed(futures):
            idx, path = future.result()
            results[idx] = path
            h = highlights[idx]
            if path:
                _log(f"  Segment {idx+1}: {h.start:.1f}s-{h.end:.1f}s")
            else:
                _log(f"  Segment {idx+1} failed")

    # Return in order
    segments = []
    for i in range(len(highlights)):
        if results.get(i):
            segments.append(results[i])

    return segments


FADE_DURATION = 0.3  # seconds — fade out at end / fade in at start of each segment


def _normalize_and_concat(segments: List[Path], output_path: Path, resolution: str = "1080p") -> Path:
    """Normalize all segments with fade in/out transitions, then concat."""
    _log("Step 4: Normalizing and concatenating...")

    target_size = {"720p": (1280, 720), "1080p": (1920, 1080), "4k": (3840, 2160)}.get(resolution, (1920, 1080))
    target_w, target_h = target_size

    work_dir = segments[0].parent
    normalized = []

    for i, seg in enumerate(segments):
        norm = work_dir / f"norm_{i:03d}.mp4"

        # Get segment duration for fade-out timing
        seg_dur = _get_video_duration(seg)
        fade_out_start = max(0, seg_dur - FADE_DURATION)

        # Video: scale + pad + fade in at start + fade out at end
        vf = (
            f"scale={target_w}:{target_h}:force_original_aspect_ratio=decrease,"
            f"pad={target_w}:{target_h}:(ow-iw)/2:(oh-ih)/2:black,"
            f"fade=t=in:st=0:d={FADE_DURATION},"
            f"fade=t=out:st={fade_out_start}:d={FADE_DURATION}"
        )

        # Audio: fade in + fade out
        af = (
            f"afade=t=in:st=0:d={FADE_DURATION},"
            f"afade=t=out:st={fade_out_start}:d={FADE_DURATION}"
        )

        cmd = [
            "ffmpeg", "-y", "-i", str(seg),
            "-vf", vf,
            "-af", af,
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18",
            "-r", "30",
            "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2",
            "-shortest",
            str(norm),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0 and norm.exists():
            normalized.append(norm)
        else:
            _log(f"  Normalize failed for segment {i+1}")

    if not normalized:
        raise ValueError("No segments could be normalized")

    # Concat
    concat_list = work_dir / "concat_list.txt"
    with open(concat_list, "w") as f:
        for p in normalized:
            f.write(f"file '{p.resolve()}'\n")

    cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(concat_list),
        "-c", "copy",
        str(output_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        cmd = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", str(concat_list),
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18",
            "-c:a", "aac", "-b:a", "192k",
            str(output_path),
        ]
        subprocess.run(cmd, capture_output=True, text=True, check=True)

    duration = _get_video_duration(output_path)
    _log(f"  Concatenated {len(normalized)} segments -> {duration:.1f}s")

    return output_path


def _add_bookends(
    video_path: Path,
    intro_path: Optional[Path],
    outro_path: Optional[Path],
    work_dir: Path,
    resolution: str = "1080p",
):
    """Prepend intro and/or append outro to the video using FFmpeg concat."""
    target_size = {"720p": (1280, 720), "1080p": (1920, 1080), "4k": (3840, 2160)}.get(resolution, (1920, 1080))
    w, h = target_size

    parts = []

    def _normalize_bookend(src: Path, label: str) -> Optional[Path]:
        norm = work_dir / f"{label}_norm.mp4"
        cmd = [
            "ffmpeg", "-y", "-i", str(src),
            "-vf", f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black",
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18",
            "-r", "30",
            "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2",
            "-shortest",
            str(norm),
        ]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode == 0 and norm.exists():
            dur = _get_video_duration(norm)
            _log(f"  {label.title()} added ({dur:.1f}s)")
            return norm
        _log(f"  {label.title()} normalize failed")
        return None

    if intro_path and intro_path.exists():
        norm = _normalize_bookend(intro_path, "intro")
        if norm:
            parts.append(norm)

    # Main video in the middle
    parts.append(video_path)

    if outro_path and outro_path.exists():
        norm = _normalize_bookend(outro_path, "outro")
        if norm:
            parts.append(norm)

    if len(parts) <= 1:
        return  # nothing to add

    # Concat all parts
    concat_list = work_dir / "bookend_concat.txt"
    with open(concat_list, "w") as f:
        for p in parts:
            f.write(f"file '{p.resolve()}'\n")

    merged = work_dir / "with_bookends.mp4"
    cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(concat_list),
        "-c", "copy",
        str(merged),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        # Fallback: re-encode
        cmd = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", str(concat_list),
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18",
            "-c:a", "aac", "-b:a", "192k",
            str(merged),
        ]
        subprocess.run(cmd, capture_output=True, text=True, check=True)

    if merged.exists():
        shutil.move(str(merged), str(video_path))
        _log(f"  Final with bookends: {_get_video_duration(video_path):.1f}s")


def create_instagram_short(
    input_video: Path,
    output_path: Path,
    resolution: str = "1080p",
    captions: bool = False,
    target_duration: float = 45,
    generate_music: bool = True,
    music_prompt: str = "",
    music_volume: float = 0.15,
    video_speed: float = 1.0,
    enhance_scenes: bool = True,
    intro_video: Optional[Path] = None,
    outro_video: Optional[Path] = None,
) -> Path:
    """
    Create an Instagram Short from a longer video.

    1. Transcribe with word-level timestamps
    2. AI picks the most impactful moments
    3. Extract video segments
    3.5. (Optional) AI scene enhancement — Imagen + Veo visuals
    4. Normalize + concat
    4.5. (Optional) Prepend intro / append outro
    5. Generate & mix background music
    6. (Optional) Burn karaoke captions

    Args:
        input_video: Source video file
        output_path: Where to save the final short
        resolution: Target resolution
        captions: Whether to burn karaoke captions
        target_duration: Target duration in seconds (default 45)
        generate_music: Whether to generate background music
        music_prompt: Custom music prompt (auto-generated if empty)
        music_volume: Background music volume (0.0-1.0, default 0.15)
        enhance_scenes: Whether to generate AI visual scenes (Imagen + Veo)
        intro_video: Optional intro video to prepend
        outro_video: Optional outro video to append

    Returns:
        Path to final short video
    """
    input_video = Path(input_video).resolve()
    output_path = Path(output_path).resolve()

    if not input_video.exists():
        raise FileNotFoundError(f"Input video not found: {input_video}")

    target_min = max(10, target_duration - 5)
    target_max = target_duration

    source_duration = _get_video_duration(input_video)
    _log(f"Instagram Shorts Pipeline")
    _log(f"  Source: {input_video.name} ({source_duration:.1f}s)")
    _log(f"  Target: {target_min}-{target_max}s | Resolution: {resolution}")
    _log(f"  Music: {'Yes' if generate_music else 'No'} | Captions: {'Yes' if captions else 'No'}")
    _log(f"  Scene Enhancement: {'Yes' if enhance_scenes else 'No'}")

    work_dir = Path(tempfile.mkdtemp())

    try:
        # Step 1: Transcribe
        full_text, words = _transcribe_with_timestamps(input_video)

        # Step 1.5: Group into sentences
        sentences = _group_words_to_sentences(words)
        _log(f"  Grouped into {len(sentences)} sentences")

        if not sentences:
            raise ValueError("No sentences found in transcription")

        # Step 2: AI picks highlights
        highlights = _pick_highlights(full_text, sentences, target_duration)

        if not highlights:
            raise ValueError("AI could not select any highlights")

        # Step 3: Extract segments
        segments = _extract_segments(input_video, highlights, work_dir)

        if not segments:
            raise ValueError("No segments could be extracted")

        # Step 3.5: AI scene enhancement (Imagen + Veo)
        if enhance_scenes:
            try:
                segments = _enhance_segments(segments, highlights, work_dir, resolution, full_text)
            except Exception as e:
                _log(f"  Scene enhancement failed, continuing with original: {e}")

        # Step 4: Normalize + concat
        output_path.parent.mkdir(parents=True, exist_ok=True)
        _normalize_and_concat(segments, output_path, resolution)

        # Step 4.5: Prepend intro / append outro
        if intro_video or outro_video:
            _log("Step 4.5: Adding intro/outro...")
            try:
                _add_bookends(output_path, intro_video, outro_video, work_dir, resolution)
            except Exception as e:
                _log(f"  Intro/outro failed, continuing without: {e}")

        # Step 5: Generate & mix background music
        if generate_music and output_path.exists():
            _log("Step 5: Generating background music...")
            try:
                from ..generators.music_generator import generate_music as gen_music
                from ..pipeline.veo_pipeline import add_background_music_to_file

                short_duration = int(_get_video_duration(output_path)) + 1

                # Auto-generate music prompt from content if not provided
                if not music_prompt:
                    from ..ai.gemini_client import generate_text
                    music_prompt = generate_text(
                        f"Write a short music prompt (1 sentence) for background music in an Instagram Reel. "
                        f"The video content is: {full_text[:300]}. "
                        f"Return ONLY the music prompt, no explanation. Make it energetic and trendy.",
                    ).strip().strip('"')
                    _log(f"  Music prompt: {music_prompt}")

                music_path = work_dir / "bg_music.mp3"
                gen_music(
                    prompt=music_prompt,
                    output_path=music_path,
                    duration=min(short_duration, 30),
                )

                if music_path.exists():
                    with_music = work_dir / "with_music.mp4"
                    add_background_music_to_file(
                        output_path, music_path, with_music,
                        music_volume=music_volume,
                    )
                    if with_music.exists():
                        shutil.move(str(with_music), str(output_path))
                        _log("  Background music added")
            except Exception as e:
                _log(f"  Music generation failed: {e}")

        # Step 6: Captions (optional)
        if captions and output_path.exists():
            _log("Step 6: Burning karaoke captions...")
            try:
                from ..ai.tts_engine import transcribe_elevenlabs
                from ..processing.caption_renderer import burn_captions_onto_video

                transcript = transcribe_elevenlabs(output_path)
                if transcript.words:
                    word_dicts = [
                        {"text": w.text, "start": w.start, "end": w.end}
                        for w in transcript.words
                    ]
                    captioned = work_dir / "captioned.mp4"
                    burn_captions_onto_video(output_path, word_dicts, captioned)
                    if captioned.exists():
                        shutil.move(str(captioned), str(output_path))
                        _log("  Captions burned")
            except Exception as e:
                _log(f"  Caption burn failed: {e}")

        final_duration = _get_video_duration(output_path)
        _log(f"Instagram Short created!")
        _log(f"  Output: {output_path.absolute()}")
        _log(f"  Duration: {source_duration:.1f}s -> {final_duration:.1f}s")
        _log(f"  Segments: {len(highlights)} | Music: {'Yes' if generate_music else 'No'} | Captions: {'Yes' if captions else 'No'}")

        return output_path

    finally:
        shutil.rmtree(str(work_dir), ignore_errors=True)
