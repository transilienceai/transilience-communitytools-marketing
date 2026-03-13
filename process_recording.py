#!/usr/bin/env python3
"""
Screen Recording Processor

Pipeline: Find video → Extract audio → Clean video → Transcribe → AI script → TTS voiceover → Final video

Usage:
    python process_recording.py screenshot/
    python process_recording.py screenshot/ --voice "Aman" --tone "friendly"
    python process_recording.py screenshot/ --product "My SaaS App" --voice "Aman" -o screenshot/processed
"""

import os
import sys
import json
import subprocess
from pathlib import Path
from typing import List, Tuple, Optional

import requests
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

# Import refactored utilities
from src.processing.video_cleaner import analyze_motion, find_stillness_periods, clean_video
from src.processing.video_effects import apply_cinematic_effects
from src.processing.video_extractors import extract_keyframes, extract_last_frame
from src.core.video_utils import get_duration, get_video_dimensions
from src.core.audio_utils import extract_audio

load_dotenv()
console = Console()

VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"}
API_KEY = os.getenv("ELEVENLABS_API_KEY")
STT_ENDPOINT = "https://api.elevenlabs.io/v1/speech-to-text"
TTS_ENDPOINT = "https://api.elevenlabs.io/v1/text-to-speech"


# ── Step 1: Find video ──────────────────────────────────────────────────────

def find_video(folder: str) -> Path:
    """Find the first video file in the given folder."""
    folder = Path(folder)
    for f in sorted(folder.iterdir()):
        if f.suffix.lower() in VIDEO_EXTENSIONS and not f.name.startswith("."):
            return f
    raise FileNotFoundError(f"No video files found in {folder}")


# ── Step 4: Transcribe audio (ElevenLabs) ───────────────────────────────────

def transcribe_video(file_path: str, model_id: str = "scribe_v1") -> str:
    """
    Transcribe a local video or audio file using ElevenLabs Speech-to-Text.
    Returns the transcript text (string).
    """
    if not API_KEY:
        raise ValueError(
            "ELEVENLABS_API_KEY not set.\n"
            "Get your key at: https://elevenlabs.io/app/settings/api-keys"
        )

    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    with open(file_path, "rb") as f:
        file_bytes = f.read()

    headers = {
        "xi-api-key": API_KEY,
        "Accept": "application/json"
    }
    files = {
        "file": (os.path.basename(file_path), file_bytes),
    }
    data = {
        "model_id": model_id
    }

    response = requests.post(STT_ENDPOINT, headers=headers, data=data, files=files)
    response.raise_for_status()
    result = response.json()

    text = result.get("text", "")
    console.print(f"[green]✓ Transcribed:[/green] {len(text.split())} words")
    return text


# ── Step 5: Generate AI voiceover script ─────────────────────────────────────

def _parse_script_json(response_text: str) -> dict:
    """Parse JSON from Claude response (handles code blocks and raw JSON)."""
    import re
    json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', response_text)
    if json_match:
        json_str = json_match.group(1)
    else:
        json_start = response_text.find('{')
        json_end = response_text.rfind('}') + 1
        if json_start != -1 and json_end > json_start:
            json_str = response_text[json_start:json_end]
        else:
            raise ValueError("Could not parse AI response as JSON")
    return json.loads(json_str)


def generate_voiceover_script(
    transcript: str,
    movement_segments: List[Tuple[float, float]],
    product_name: str = "",
    tone: str = "professional and engaging",
    target_audience: str = "general audience"
) -> dict:
    """
    Use Claude to turn a raw transcript into a polished voiceover script
    with timing aligned to movement segments.
    """
    from src.ai.gemini_client import generate_text

    # Build segment info
    segment_info = []
    for i, (start, end) in enumerate(movement_segments):
        segment_info.append(f"  Segment {i+1}: {start:.1f}s - {end:.1f}s ({end-start:.1f}s)")

    total_duration = sum(e - s for s, e in movement_segments)

    prompt = f"""You are a professional voiceover scriptwriter. I have a screen recording that has been cleaned
to remove idle/still moments. I need you to create a polished voiceover script from the raw transcript.

## Raw transcript from the recording:
{transcript}

## Video segments (movement only, still frames removed):
{chr(10).join(segment_info)}
Total duration: {total_duration:.1f}s

## Context:
Product/Topic: {product_name or "Infer from transcript"}
Tone: {tone}
Target Audience: {target_audience}

## Instructions:
1. Rewrite the transcript into a clean, engaging voiceover script
2. Break it into segments that align with the video timing above
3. Each segment's voiceover should fit naturally within its duration (~3 words per second)
4. Remove filler words, ums, repetitions
5. Make it sound professional and polished
6. Add a compelling intro and call-to-action if appropriate

Respond in this exact JSON format:
{{
    "title": "A title for this video",
    "summary": "One-line summary of what the recording shows",
    "segments": [
        {{
            "segment_index": 1,
            "start": 0.0,
            "end": 10.0,
            "voiceover": "The polished voiceover text for this segment",
            "caption": "Short on-screen text (max 8 words)"
        }}
    ],
    "full_voiceover": "The complete voiceover script as one continuous text"
}}"""

    console.print("[dim]Generating AI voiceover script...[/dim]")

    response_text = generate_text(
        prompt=prompt,
        max_output_tokens=4096,
    )

    script = _parse_script_json(response_text)
    console.print(f"[green]✓ AI script generated:[/green] {script.get('title', 'Untitled')}")
    return script


def generate_voiceover_script_vision(
    keyframes: List[Path],
    movement_segments: List[Tuple[float, float]],
    transcript: str = "",
    product_name: str = "",
    tone: str = "professional and engaging",
    target_audience: str = "general audience"
) -> dict:
    """
    Use Claude Vision to analyze keyframes from the screen recording and
    generate a relevant voiceover script based on what's ACTUALLY visible.

    This produces much better results than transcript-only because:
    - It sees the actual UI, text, and features on screen
    - Works even when the original audio is poor/silent
    - Script directly describes what the viewer will see
    """
    from src.ai.gemini_client import generate_with_content_blocks

    # Build segment info
    segment_info = []
    for i, (start, end) in enumerate(movement_segments):
        segment_info.append(f"  Segment {i+1}: {start:.1f}s - {end:.1f}s ({end-start:.1f}s)")
    total_duration = sum(e - s for s, e in movement_segments)

    # Build content blocks for Gemini Vision
    content_blocks = []

    for i, kf in enumerate(keyframes):
        with open(kf, "rb") as f:
            image_bytes = f.read()

        ext = kf.suffix.lower()
        media_type = {
            ".png": "image/png", ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg", ".webp": "image/webp"
        }.get(ext, "image/jpeg")

        content_blocks.append(f"--- Keyframe {i+1} of {len(keyframes)} ---")
        content_blocks.append((image_bytes, media_type))

    # Add the prompt
    content_blocks.append(f"""You are a world-class product video scriptwriter. Write a voiceover script that makes viewers want to try this product IMMEDIATELY.

Above are {len(keyframes)} keyframes extracted from a screen recording. Study every detail — the UI, buttons, text, features, workflow.

## Video segments (movement only, still frames removed):
{chr(10).join(segment_info)}
Total duration: {total_duration:.1f}s

{f'## Original narration (use as CONTEXT to understand the product — but write a BETTER script):{chr(10)}{transcript}' if transcript.strip() else '## No audio transcript available — write the script based entirely on what you see in the keyframes.'}

## Context:
Product/Topic: {product_name or "Infer from the screenshots"}
Tone: {tone}
Target Audience: {target_audience}

## Script writing rules:
- HOOK in the first 3 seconds: start with a pain point, bold claim, or question that grabs attention
- Show, don't tell: "Watch this — one command, everything synced" beats "This tool helps you sync things"
- Use the original narration to understand WHAT the product does, then write something 10x more compelling
- Every sentence earns its place. If it doesn't add value, cut it.
- Build momentum: problem → solution → proof → call-to-action
- Be SPECIFIC: name the exact features, commands, UI elements visible on screen
- Write for the EAR, not the eye — this will be spoken aloud by a voice actor
- Short sentences hit harder. Use them. Then follow with a slightly longer one for rhythm.
- End with a clear, confident call-to-action
- DO NOT invent features that aren't visible in the screenshots or mentioned in the original narration
- Pace: ~3 words per second. Keep it tight.
- NO filler phrases: "In today's world", "This powerful tool", "Let me show you", "As you can see"

Respond in this exact JSON format:
{{
    "title": "A title for this video",
    "summary": "One-line summary of what the recording shows",
    "segments": [
        {{
            "segment_index": 1,
            "start": 0.0,
            "end": 10.0,
            "voiceover": "The polished voiceover text for this segment",
            "caption": "Short on-screen text (max 8 words)"
        }}
    ],
    "full_voiceover": "The complete voiceover script as one continuous text"
}}""")

    console.print(f"[dim]Generating AI voiceover script from {len(keyframes)} keyframes (Vision)...[/dim]")

    response_text = generate_with_content_blocks(
        blocks=content_blocks,
        max_output_tokens=4096,
    )

    script = _parse_script_json(response_text)
    console.print(f"[green]✓ AI script generated (Vision):[/green] {script.get('title', 'Untitled')}")
    return script


# ── Voice cloning (ElevenLabs) ────────────────────────────────────────────────

def clone_voice(
    name: str,
    audio_files: List[str],
    description: str = "",
    accent: str = "",
    gender: str = "",
    age: str = ""
) -> str:
    """
    Clone a voice using ElevenLabs.

    Args:
        name: Name for the cloned voice
        audio_files: List of audio/video file paths to use as voice samples
        description: Optional description of the voice
        accent: Accent label (e.g., "British", "Indian", "American", "Australian")
        gender: Gender label (e.g., "male", "female")
        age: Age label (e.g., "young", "middle_aged", "old")

    Returns:
        voice_id of the newly cloned voice
    """
    if not API_KEY:
        raise ValueError("ELEVENLABS_API_KEY not set.")

    url = "https://api.elevenlabs.io/v1/voices/add"
    headers = {"xi-api-key": API_KEY}

    # Prepare files — extract audio from videos if needed
    files = []
    for file_path in audio_files:
        path = Path(file_path)
        if not path.exists():
            console.print(f"[yellow]Skipping missing file: {path}[/yellow]")
            continue

        # If it's a video, extract the audio first
        if path.suffix.lower() in VIDEO_EXTENSIONS:
            console.print(f"[dim]Extracting audio from {path.name}...[/dim]")
            temp_audio = Path(tempfile.mktemp(suffix=".mp3"))
            extract_audio(path, temp_audio)
            files.append(("files", (temp_audio.name, open(temp_audio, "rb"), "audio/mpeg")))
        else:
            files.append(("files", (path.name, open(path, "rb"), "audio/mpeg")))

    if not files:
        raise ValueError("No valid audio files provided for voice cloning")

    # Build labels for accent, gender, age
    labels = {}
    if accent:
        labels["accent"] = accent
    if gender:
        labels["gender"] = gender
    if age:
        labels["age"] = age

    data = {
        "name": name,
        "description": description or f"Cloned voice: {name}"
    }

    # Add labels as JSON string
    if labels:
        data["labels"] = json.dumps(labels)
        console.print(f"[dim]Labels: {labels}[/dim]")

    try:
        console.print(f"[dim]Cloning voice '{name}' with {len(files)} sample(s)...[/dim]")
        response = requests.post(url, headers=headers, data=data, files=files, timeout=120)

        # Close file handles
        for _, (_, f, _) in files:
            f.close()

        if response.status_code == 200:
            result = response.json()
            voice_id = result.get("voice_id")
            console.print(f"[green]✓ Voice '{name}' cloned! Voice ID: {voice_id}[/green]")
            return voice_id
        else:
            raise ValueError(f"Voice cloning failed ({response.status_code}): {response.text[:300]}")

    except Exception as e:
        for _, (_, f, _) in files:
            try:
                f.close()
            except Exception:
                pass
        raise e


# ── Step 6: Generate TTS voiceover (ElevenLabs) ──────────────────────────────

def get_voice_id(voice: str) -> str:
    """Resolve voice name to voice_id. If already an ID, return as-is."""
    if len(voice) == 21 and voice.isalnum():
        return voice

    url = "https://api.elevenlabs.io/v1/voices"
    headers = {"xi-api-key": API_KEY}

    response = requests.get(url, headers=headers, timeout=30)
    if response.status_code != 200:
        console.print(f"[yellow]Could not fetch voices, using '{voice}' as ID[/yellow]")
        return voice

    voices = response.json().get("voices", [])

    # Exact match
    for v in voices:
        if v["name"].lower() == voice.lower():
            return v["voice_id"]

    # Partial match
    for v in voices:
        if voice.lower() in v["name"].lower():
            return v["voice_id"]

    console.print(f"[yellow]Voice '{voice}' not found, using as ID[/yellow]")
    return voice


def generate_tts(
    text: str,
    output_path: Path,
    voice: str = "Aman",
    model: str = "eleven_multilingual_v2",
    style: float = 0.0,
    stability: float = 0.5,
    similarity_boost: float = 0.75,
    use_speaker_boost: bool = True
) -> Path:
    """
    Generate TTS audio using ElevenLabs.

    Args:
        text: Text to speak
        output_path: Where to save the audio
        voice: Voice name or ID
        model: ElevenLabs model (eleven_multilingual_v2 recommended for accents)
        style: Style exaggeration (0.0-1.0). Higher = more expressive/accent emphasis
        stability: Voice stability (0.0-1.0). Lower = more varied/expressive
        similarity_boost: Voice clarity (0.0-1.0). Higher = closer to original voice
        use_speaker_boost: Boost speaker clarity
    """
    if not API_KEY:
        raise ValueError("ELEVENLABS_API_KEY not set.")

    voice_id = get_voice_id(voice)

    url = f"{TTS_ENDPOINT}/{voice_id}"
    headers = {
        "xi-api-key": API_KEY,
        "Content-Type": "application/json"
    }
    payload = {
        "text": text,
        "model_id": model,
        "voice_settings": {
            "stability": stability,
            "similarity_boost": similarity_boost,
            "style": style,
            "use_speaker_boost": use_speaker_boost
        }
    }

    response = requests.post(url, headers=headers, json=payload, timeout=120)

    if response.status_code == 401:
        raise ValueError("ElevenLabs API authentication failed.")
    elif response.status_code != 200:
        raise ValueError(f"ElevenLabs TTS error ({response.status_code}): {response.text[:200]}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(response.content)

    console.print(f"[green]✓ Voiceover generated:[/green] {output_path.name}")
    return output_path


# ── Step 7b: Generate video with Veo 3.1 ─────────────────────────────────────

def generate_veo_scenes(
    keyframes: List[Path],
    script: dict,
    output_dir: Path,
    product_name: str = "",
    resolution: str = "1080p",
    model: str = "veo-3.1-generate-preview"
) -> List[Path]:
    """
    Generate Veo 3.1 video clips from keyframes + script segments.

    Uses last-frame/first-frame chaining for visual continuity:
    - Scene 1: generated from the first keyframe
    - Scene 2: generated from the LAST FRAME of scene 1 (not a keyframe)
    - Scene 3: generated from the LAST FRAME of scene 2
    - ...and so on

    This ensures each scene visually starts where the previous one ended,
    creating smooth, continuous transitions throughout the video.
    """
    from src.ai.veo_generator import generate_video_veo
    from src.pipeline.veo_pipeline import generate_motion_prompt

    output_dir.mkdir(parents=True, exist_ok=True)
    segments = script.get("segments", [])
    scene_videos = []

    # The first scene uses the first keyframe; subsequent scenes use
    # the last frame of the previous scene for continuity
    current_input_image = keyframes[0] if keyframes else None

    num_scenes = len(keyframes)

    for i in range(num_scenes):
        if current_input_image is None:
            console.print(f"  [yellow]No input image for scene {i+1}, skipping[/yellow]")
            break

        # Match scene to script segment
        if i < len(segments):
            seg = segments[i]
            voiceover = seg.get("voiceover", "")
            caption = seg.get("caption", "")
        else:
            voiceover = script.get("full_voiceover", "")
            caption = ""

        # Build continuity hint for scene chaining
        if i == 0:
            continuity_hint = "This is the opening scene. "
        else:
            continuity_hint = (
                "Continue smoothly from the previous scene. "
                "The starting frame is the last frame of the previous scene — "
                "maintain visual continuity and flow naturally from where we left off. "
            )

        # Use veo_pipeline's context-aware motion prompt
        motion_cues = generate_motion_prompt(current_input_image, voiceover)

        # Build video prompt matching veo_pipeline style
        motion_prompt = f"""{continuity_hint}{voiceover}

EXACT TEXT IN IMAGE (do not change): {caption}

Create a cinematic, engaging video with:
- {motion_cues}
- Cursor movements pointing to key UI elements
- Highlight effects on important features
- Professional motion graphics feel
{f'- Showcasing: {product_name}' if product_name else ''}

Keep all text readable throughout the video."""

        scene_path = output_dir / f"veo_scene_{i:03d}.mp4"
        console.print(f"  [dim]Generating scene {i+1}/{num_scenes} (input: {current_input_image.name})...[/dim]")

        try:
            generate_video_veo(
                prompt=motion_prompt,
                output_path=scene_path,
                image_path=current_input_image,
                duration=8,
                aspect_ratio="16:9",
                resolution=resolution,
                model=model,
                enable_audio=False  # We'll use our own voiceover
            )
            if scene_path.exists():
                scene_videos.append(scene_path)
                console.print(f"  [green]✓ Scene {i+1} generated[/green]")

                # Extract last frame for the next scene's input (continuity chain)
                if i < num_scenes - 1:
                    last_frame_path = output_dir / f"last_frame_{i:03d}.jpg"
                    try:
                        extract_last_frame(scene_path, last_frame_path)
                        current_input_image = last_frame_path
                        console.print(f"  [dim]Extracted last frame → input for scene {i+2}[/dim]")
                    except Exception as e:
                        console.print(f"  [yellow]Could not extract last frame: {e}[/yellow]")
                        # Fallback: use the next keyframe if available
                        if i + 1 < len(keyframes):
                            current_input_image = keyframes[i + 1]
                            console.print(f"  [dim]Falling back to keyframe {i+2}[/dim]")
                        else:
                            current_input_image = None

        except Exception as e:
            console.print(f"  [yellow]Scene {i+1} failed: {e}[/yellow]")
            # Fallback: use a static clip from the input image
            fallback = output_dir / f"fallback_scene_{i:03d}.mp4"
            cmd = [
                "ffmpeg", "-y", "-loop", "1",
                "-i", str(current_input_image),
                "-c:v", "libx264", "-t", "8",
                "-pix_fmt", "yuv420p", "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2",
                str(fallback)
            ]
            r = subprocess.run(cmd, capture_output=True, text=True)
            if r.returncode == 0:
                scene_videos.append(fallback)

            # Try to use next keyframe for the next scene
            if i + 1 < len(keyframes):
                current_input_image = keyframes[i + 1]
            else:
                current_input_image = None

    return scene_videos


def concatenate_scenes(scene_videos: List[Path], output_path: Path) -> Path:
    """Concatenate multiple Veo scene clips into one video."""
    import shutil

    if len(scene_videos) == 1:
        shutil.copy2(scene_videos[0], output_path)
        return output_path

    output_path = Path(output_path).resolve()

    # Write concat file next to the output (not in a temp dir) using absolute paths
    concat_file = output_path.parent / "_concat_list.txt"
    concat_file.write_text(
        "\n".join(f"file '{Path(v).resolve()}'" for v in scene_videos)
    )

    cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(concat_file),
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
        str(output_path)
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)

    # Cleanup concat file
    try:
        concat_file.unlink()
    except Exception:
        pass

    if r.returncode != 0:
        raise RuntimeError(f"Scene concatenation failed: {r.stderr[-300:]}")

    return output_path


# ── Step 8: Assemble final video ─────────────────────────────────────────────

def assemble_final_video(
    video_path: Path,
    voiceover_path: Path,
    output_path: Path,
    voiceover_volume: float = 2.0,
    music_path: Optional[Path] = None,
    music_volume: float = 0.15,
    audio_speed: float = 1.0
) -> Path:
    """
    Combine cleaned video with AI voiceover audio and optional background music.
    Slow-mos the video to match the voiceover length if the audio is longer.

    Args:
        video_path: Cleaned video file
        voiceover_path: TTS voiceover audio
        output_path: Where to save the final video
        voiceover_volume: Volume multiplier for voiceover (default: 2.0 = +6dB louder)
        music_path: Optional background music file (.mp3/.wav)
        music_volume: Music volume (default: 0.15 — quiet behind voiceover)
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Speed already applied to voiceover in the pipeline (Step 6)
    video_dur = get_duration(video_path)
    audio_dur = get_duration(voiceover_path)

    # Volume only
    voice_chain = f"volume={voiceover_volume}"

    # Calculate slowdown factor if audio is longer than video
    slowdown = audio_dur / video_dur if video_dur > 0 and audio_dur > video_dur else 1.0

    if slowdown > 1.0:
        console.print(f"[dim]Slowing video {slowdown:.2f}x to match {audio_dur:.1f}s voiceover[/dim]")
        video_filter = f"[0:v]setpts={slowdown:.4f}*PTS[vout]"
    else:
        video_filter = f"[0:v]copy[vout]"

    has_music = music_path and Path(music_path).exists()

    if has_music:
        console.print(f"[dim]Adding background music: {Path(music_path).name} (volume: {music_volume})[/dim]")

        # 3 inputs: video, voiceover, music
        fade_out_start = max(0, audio_dur - 2.0)

        filter_complex = (
            f"{video_filter};"
            f"[1:a]{voice_chain}[voice];"
            f"[2:a]volume={music_volume},afade=t=in:d=2,afade=t=out:st={fade_out_start:.2f}:d=2[music];"
            f"[voice][music]amix=inputs=2:duration=first:dropout_transition=2[aout]"
        )

        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-i", str(voiceover_path),
            "-stream_loop", "-1", "-i", str(music_path),
            "-filter_complex", filter_complex,
            "-map", "[vout]",
            "-map", "[aout]",
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
            "-c:a", "aac", "-b:a", "192k",
            "-shortest",
            str(output_path)
        ]
    else:
        # No music — just video + voiceover
        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-i", str(voiceover_path),
            "-filter_complex",
            f"{video_filter};[1:a]{voice_chain}[aout]",
            "-map", "[vout]",
            "-map", "[aout]",
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
            "-c:a", "aac", "-b:a", "192k",
            "-shortest",
            str(output_path)
        ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Video assembly failed: {result.stderr[-300:]}")

    extras = []
    if slowdown > 1.0:
        extras.append(f"slowed {slowdown:.2f}x")
    if has_music:
        extras.append("+ music")

    console.print(
        f"[green]✓ Final video:[/green] {output_path.name}"
        + (f" ({', '.join(extras)})" if extras else "")
    )
    return output_path


# ── Main pipeline ────────────────────────────────────────────────────────────

def process_recording(
    folder: str,
    product_name: str = "",
    tone: str = "professional and engaging",
    target_audience: str = "general audience",
    voice: str = "Aman",
    output_dir: Optional[str] = None,
    resolution: str = "1080p",
    veo_model: str = "veo-3.1-generate-preview",
    max_scenes: int = 5,
    use_veo: bool = False,
    effects: bool = True,
    music_path: Optional[str] = None,
    music_volume: float = 0.15,
    voiceover_volume: float = 2.0,
    voice_stability: float = 0.5,
    voice_similarity: float = 0.75,
    voice_style: float = 0.0,
    speaker_boost: bool = True,
    audio_speed: float = 1.0
) -> dict:
    """
    Full pipeline: find video → extract audio → clean video → transcribe →
    extract keyframes → Vision AI script → TTS voiceover → cinematic effects → final video.

    Video modes (Step 7):
    - Default: cleaned recording + cinematic effects (zoom, pan, crossfade)
    - --no-effects: cleaned recording as-is (no effects)
    - --veo: Veo 3.1 AI-generated scenes (may hallucinate content)

    Returns dict with all outputs (paths and script data).
    """
    folder = Path(folder)
    out_dir = Path(output_dir) if output_dir else folder / "processed"
    out_dir.mkdir(parents=True, exist_ok=True)

    results = {}

    # Step 1: Find video
    console.print(Panel.fit("[bold]Step 1: Finding video[/bold]", border_style="blue"))
    video_path = find_video(folder)
    console.print(f"  Found: {video_path.name}")
    results["source_video"] = str(video_path)

    # Step 2: Extract audio
    console.print(Panel.fit("[bold]Step 2: Extracting audio[/bold]", border_style="blue"))
    audio_path = extract_audio(video_path, out_dir / f"{video_path.stem}_audio.mp3")
    results["audio"] = str(audio_path)

    # Step 3: Clean video
    console.print(Panel.fit("[bold]Step 3: Cleaning video[/bold]", border_style="blue"))
    cleaned_path, movement_segments = clean_video(
        video_path,
        out_dir / f"{video_path.stem}_cleaned.mp4"
    )
    results["cleaned_video"] = str(cleaned_path)
    results["movement_segments"] = [(s, e) for s, e in movement_segments]

    # Step 4: Transcribe audio (used as supplementary context)
    console.print(Panel.fit("[bold]Step 4: Transcribing audio[/bold]", border_style="blue"))
    transcript = transcribe_video(str(audio_path))
    results["transcript"] = transcript

    # Step 5: Extract keyframes + Generate AI voiceover script (Vision)
    console.print(Panel.fit("[bold]Step 5: Analyzing video & generating AI script (Vision)[/bold]", border_style="blue"))

    keyframes_dir = out_dir / "keyframes"
    keyframes = extract_keyframes(cleaned_path, keyframes_dir, max_frames=max_scenes)
    console.print(f"  Extracted {len(keyframes)} keyframes")
    results["keyframes"] = [str(k) for k in keyframes]

    if keyframes:
        # Use Claude Vision on keyframes for a relevant script
        script = generate_voiceover_script_vision(
            keyframes=keyframes,
            movement_segments=movement_segments,
            transcript=transcript,
            product_name=product_name,
            tone=tone,
            target_audience=target_audience
        )
    else:
        # Fallback to transcript-only if no keyframes
        console.print("[yellow]No keyframes — falling back to transcript-based script[/yellow]")
        script = generate_voiceover_script(
            transcript,
            movement_segments,
            product_name=product_name,
            tone=tone,
            target_audience=target_audience
        )
    results["script"] = script

    # Save script to file
    script_path = out_dir / "voiceover_script.json"
    with open(script_path, "w") as f:
        json.dump(script, f, indent=2)
    results["script_file"] = str(script_path)

    # Step 6: Generate TTS voiceover
    console.print(Panel.fit(f"[bold]Step 6: Generating voiceover (voice: {voice})[/bold]", border_style="blue"))
    voiceover_text = script.get("full_voiceover", "")
    if not voiceover_text:
        voiceover_text = " ".join(
            seg.get("voiceover", "") for seg in script.get("segments", [])
        )

    voiceover_path = generate_tts(
        text=voiceover_text,
        output_path=out_dir / "voiceover.mp3",
        voice=voice,
        stability=voice_stability,
        similarity_boost=voice_similarity,
        style=voice_style,
        use_speaker_boost=speaker_boost
    )

    # Apply speed change right after TTS so the saved file is the final version
    if audio_speed != 1.0:
        speed = max(0.5, min(100.0, audio_speed))
        sped_path = out_dir / "voiceover_sped.mp3"
        console.print(f"[dim]Applying voiceover speed: {speed}x[/dim]")
        speed_cmd = [
            "ffmpeg", "-y", "-i", str(voiceover_path),
            "-af", f"atempo={speed}",
            "-b:a", "192k",
            str(sped_path)
        ]
        sr = subprocess.run(speed_cmd, capture_output=True, text=True)
        if sr.returncode == 0 and sped_path.exists():
            # Overwrite original with sped-up version
            import shutil
            shutil.move(str(sped_path), str(voiceover_path))
            console.print(f"[green]✓ Voiceover saved at {speed}x speed[/green]")
        else:
            console.print(f"[yellow]Speed change failed, keeping original speed[/yellow]")

    results["voiceover"] = str(voiceover_path)

    # Step 7: Apply video effects
    if use_veo:
        # Veo 3.1 AI-generated scenes (opt-in)
        console.print(Panel.fit(f"[bold]Step 7: Generating video with Veo 3.1 ({resolution})[/bold]", border_style="blue"))

        veo_scenes_dir = out_dir / "veo_scenes"
        veo_scenes = generate_veo_scenes(
            keyframes=keyframes,
            script=script,
            output_dir=veo_scenes_dir,
            product_name=product_name,
            resolution=resolution,
            model=veo_model
        )
        results["veo_scenes"] = [str(s) for s in veo_scenes]

        if veo_scenes:
            veo_video_path = out_dir / "veo_combined.mp4"
            concatenate_scenes(veo_scenes, veo_video_path)
            console.print(f"[green]✓ Veo video generated:[/green] {len(veo_scenes)} scenes")
            video_for_assembly = veo_video_path
        else:
            console.print("[yellow]Veo generation failed — falling back to cleaned video[/yellow]")
            video_for_assembly = cleaned_path

    elif effects:
        # Cinematic effects on real footage (default)
        console.print(Panel.fit("[bold]Step 7: Applying cinematic effects (zoom, pan, transitions)[/bold]", border_style="blue"))
        fx_path = out_dir / f"{cleaned_path.stem}_cinematic.mp4"
        video_for_assembly = apply_cinematic_effects(
            video_path=cleaned_path,
            movement_segments=movement_segments,
            output_path=fx_path
        )
    else:
        # Raw cleaned recording (--no-effects)
        console.print(Panel.fit("[bold]Step 7: Using cleaned screen recording (no effects)[/bold]", border_style="blue"))
        console.print(f"  Using: {cleaned_path.name}")
        video_for_assembly = cleaned_path

    results["video_for_assembly"] = str(video_for_assembly)

    # Step 8: Assemble final video (video + TTS voiceover + optional music)
    music_label = f" + music: {Path(music_path).name}" if music_path else ""
    console.print(Panel.fit(f"[bold]Step 8: Assembling final video{music_label}[/bold]", border_style="blue"))
    final_path = assemble_final_video(
        video_path=video_for_assembly,
        voiceover_path=voiceover_path,
        output_path=out_dir / "final_video.mp4",
        voiceover_volume=voiceover_volume,
        music_path=Path(music_path) if music_path else None,
        music_volume=music_volume,
        audio_speed=audio_speed
    )
    results["final_video"] = str(final_path)

    # Display results
    console.print()
    console.print(Panel.fit("[bold green]Pipeline Complete[/bold green]", border_style="green"))

    table = Table(title=script.get("title", "Voiceover Script"))
    table.add_column("#", style="dim", width=4)
    table.add_column("Time", width=14)
    table.add_column("Voiceover", ratio=3)
    table.add_column("Caption", ratio=1)

    for seg in script.get("segments", []):
        table.add_row(
            str(seg.get("segment_index", "")),
            f"{seg.get('start', 0):.1f}s - {seg.get('end', 0):.1f}s",
            seg.get("voiceover", ""),
            seg.get("caption", "")
        )
    console.print(table)

    console.print(f"\n[bold]Full voiceover:[/bold]")
    console.print(script.get("full_voiceover", ""))

    console.print(f"\n[bold]Outputs:[/bold]")
    console.print(f"  Cleaned video:   {cleaned_path}")
    mode_label = " (Veo)" if use_veo else (" (cinematic effects)" if effects else " (original)")
    console.print(f"  Video source:    {video_for_assembly}{mode_label}")
    console.print(f"  Voiceover audio: {voiceover_path}")
    console.print(f"  Final video:     {final_path}")
    console.print(f"  Script JSON:     {script_path}")

    return results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Process screen recording into voiceover video")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # ── process (default) ──
    proc = subparsers.add_parser("process", help="Full pipeline: video → voiceover → final video")
    proc.add_argument("folder", help="Folder containing the video file")
    proc.add_argument("--product", default="", help="Product/service name")
    proc.add_argument("--tone", default="professional and engaging", help="Script tone")
    proc.add_argument("--audience", default="general audience", help="Target audience")
    proc.add_argument("--voice", default="Aman", help="ElevenLabs voice name (default: Aman)")
    proc.add_argument("--max-scenes", type=int, default=5, help="Max keyframes for Vision analysis (default: 5)")
    proc.add_argument("--no-effects", action="store_true", default=False, help="Skip cinematic effects (zoom/pan/transitions)")
    proc.add_argument("--veo", action="store_true", default=False, help="Use Veo 3.1 AI video instead of effects (may hallucinate)")
    proc.add_argument("--resolution", default="1080p", choices=["720p", "1080p", "4k"], help="Veo video resolution (default: 1080p)")
    proc.add_argument("--veo-model", default="veo-3.1-generate-preview", help="Veo model (default: veo-3.1-generate-preview)")
    proc.add_argument("--music", default=None, help="Background music file (.mp3/.wav)")
    proc.add_argument("--music-volume", type=float, default=0.15, help="Music volume (default: 0.15 — quiet behind voiceover)")
    proc.add_argument("--vo-volume", type=float, default=2.0, help="Voiceover volume multiplier (default: 2.0)")
    proc.add_argument("--audio-speed", type=float, default=1.0, help="Voiceover playback speed (default: 1.0, try 1.5 for faster)")
    proc.add_argument("--stability", type=float, default=0.5, help="Voice stability 0.0-1.0 (lower = more expressive, default: 0.5)")
    proc.add_argument("--similarity", type=float, default=0.75, help="Voice similarity 0.0-1.0 (higher = closer to original, default: 0.75)")
    proc.add_argument("--style", type=float, default=0.0, help="Voice style 0.0-1.0 (higher = more expressive/accent, default: 0.0)")
    proc.add_argument("--no-speaker-boost", action="store_true", default=False, help="Disable speaker clarity boost")
    proc.add_argument("-o", "--output", default=None, help="Output directory")

    # ── clone ──
    cln = subparsers.add_parser("clone", help="Clone a voice using ElevenLabs")
    cln.add_argument("name", help="Name for the cloned voice")
    cln.add_argument("audio_files", nargs="+", help="Audio/video files to use as voice samples")
    cln.add_argument("--description", default="", help="Description of the voice")
    cln.add_argument("--accent", default="", help="Accent label (e.g., 'British', 'Indian', 'American')")
    cln.add_argument("--gender", default="", help="Gender label (e.g., 'male', 'female')")
    cln.add_argument("--age", default="", help="Age label (e.g., 'young', 'middle_aged', 'old')")

    args = parser.parse_args()

    # Default to 'process' if no subcommand and a folder-like arg is given
    if args.command is None:
        # Fallback: treat as process command for backward compatibility
        parser.print_help()
        sys.exit(1)

    if args.command == "process":
        process_recording(
            folder=args.folder,
            product_name=args.product,
            tone=args.tone,
            target_audience=args.audience,
            voice=args.voice,
            output_dir=args.output,
            resolution=args.resolution,
            veo_model=args.veo_model,
            max_scenes=args.max_scenes,
            use_veo=args.veo,
            effects=not args.no_effects,
            music_path=args.music,
            music_volume=args.music_volume,
            voiceover_volume=args.vo_volume,
            voice_stability=args.stability,
            voice_similarity=args.similarity,
            voice_style=args.style,
            speaker_boost=not args.no_speaker_boost,
            audio_speed=args.audio_speed
        )

    elif args.command == "clone":
        try:
            voice_id = clone_voice(
                name=args.name,
                audio_files=args.audio_files,
                description=args.description,
                accent=args.accent,
                gender=args.gender,
                age=args.age
            )
            console.print(Panel.fit(
                f"[bold green]Voice cloned successfully![/bold green]\n\n"
                f"  Name:     {args.name}\n"
                f"  Voice ID: {voice_id}\n"
                + (f"  Accent:   {args.accent}\n" if args.accent else "")
                + (f"  Gender:   {args.gender}\n" if args.gender else "")
                + (f"  Age:      {args.age}\n" if args.age else "")
                + f"\nUse it in the pipeline:\n"
                f"  python process_recording.py process screenshot/ --voice \"{args.name}\"",
                border_style="green"
            ))
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            sys.exit(1)
