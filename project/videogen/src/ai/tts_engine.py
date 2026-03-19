"""
Text-to-Speech & Speech-to-Text Engine
Converts script text to audio using edge-tts (free), OpenAI TTS, or ElevenLabs.
Transcribes audio/video to text using ElevenLabs Scribe.

Supported TTS engines:
- edge: Free Microsoft Edge voices (good quality)
- openai: OpenAI TTS API (high quality)
- elevenlabs: ElevenLabs API (premium quality, voice cloning support)

Supported STT engines:
- elevenlabs: ElevenLabs Scribe (high accuracy, word-level timestamps)
"""

import os
import asyncio
import subprocess
import tempfile
import requests
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass, field
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

console = Console()


@dataclass
class AudioSegment:
    """Generated audio segment for a scene."""
    audio_path: Path
    duration: float  # actual duration in seconds
    text: str


@dataclass
class TranscriptWord:
    """A single transcribed word with timing."""
    text: str
    start: float  # seconds
    end: float    # seconds
    confidence: float = 1.0


@dataclass
class Transcript:
    """Full transcription result from speech-to-text."""
    text: str
    words: List[TranscriptWord] = field(default_factory=list)
    language: str = "en"
    duration: float = 0.0


async def generate_tts_edge(
    text: str,
    output_path: Path,
    voice: str = "en-US-AriaNeural",
    speed: float = 1.0
) -> float:
    """
    Generate TTS using edge-tts (free, Microsoft Edge voices).
    Returns actual audio duration.

    Args:
        speed: Speech rate multiplier (1.0 = normal, 1.2 = 20% faster, 0.8 = 20% slower)
    """
    import edge_tts

    # Convert speed multiplier to edge-tts rate string (e.g. 1.2 → "+20%")
    rate_pct = int((speed - 1) * 100)
    rate_str = f"{rate_pct:+d}%"

    communicate = edge_tts.Communicate(text, voice, rate=rate_str)
    await communicate.save(str(output_path))

    # Get actual duration using moviepy
    from moviepy import AudioFileClip
    audio = AudioFileClip(str(output_path))
    duration = audio.duration
    audio.close()
    return duration


def generate_tts_openai(
    text: str,
    output_path: Path,
    voice: str = "alloy",
    api_key: Optional[str] = None,
    speed: float = 1.0
) -> float:
    """
    Generate TTS using OpenAI API.
    Returns actual audio duration.

    Args:
        speed: Speech rate multiplier (0.25 to 4.0, 1.0 = normal)
    """
    from openai import OpenAI

    client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))

    response = client.audio.speech.create(
        model="tts-1",
        voice=voice,
        input=text,
        speed=speed
    )

    response.stream_to_file(str(output_path))

    # Get actual duration
    from moviepy import AudioFileClip
    audio = AudioFileClip(str(output_path))
    duration = audio.duration
    audio.close()
    return duration


def generate_tts_elevenlabs(
    text: str,
    output_path: Path,
    voice: str = "Rachel",
    api_key: Optional[str] = None,
    model: str = "eleven_multilingual_v2",
    speed: float = 1.0
) -> float:
    """
    Generate TTS using ElevenLabs API.
    Returns actual audio duration.

    Args:
        text: Text to convert to speech
        output_path: Where to save the audio
        voice: Voice name or voice_id (use list_elevenlabs_voices() to see options)
        api_key: ElevenLabs API key
        model: TTS model (eleven_multilingual_v2, eleven_monolingual_v1, etc.)
        speed: Speech rate multiplier (1.0 = normal). Applied via ffmpeg atempo post-processing.
    """
    api_key = api_key or os.getenv("ELEVENLABS_API_KEY") or os.getenv("XI_API_KEY")
    if not api_key:
        raise ValueError(
            "ElevenLabs API key not set.\n"
            "Get your key at: https://elevenlabs.io/app/settings/api-keys\n"
            "Then set: export ELEVENLABS_API_KEY=your_key"
        )

    # Get voice_id from voice name
    voice_id = get_elevenlabs_voice_id(voice, api_key)

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"

    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json"
    }

    payload = {
        "text": text,
        "model_id": model,
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75
        }
    }

    response = requests.post(url, headers=headers, json=payload, timeout=60)

    if response.status_code == 401:
        raise ValueError(f"ElevenLabs API authentication failed. Check your API key. Response: {response.text[:200]}")
    elif response.status_code != 200:
        raise ValueError(f"ElevenLabs API error ({response.status_code}): {response.text[:200]}")

    # Save audio (to final path or temp path if speed adjustment needed)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if speed != 1.0:
        # Save to temp, then speed up with ffmpeg atempo
        temp_path = output_path.parent / f"_raw_{output_path.name}"
        with open(temp_path, "wb") as f:
            f.write(response.content)

        # ffmpeg atempo range is 0.5-2.0; chain filters for values outside that
        atempo_filters = []
        remaining = speed
        while remaining > 2.0:
            atempo_filters.append("atempo=2.0")
            remaining /= 2.0
        while remaining < 0.5:
            atempo_filters.append("atempo=0.5")
            remaining /= 0.5
        atempo_filters.append(f"atempo={remaining:.4f}")
        filter_str = ",".join(atempo_filters)

        cmd = [
            "ffmpeg", "-y", "-i", str(temp_path),
            "-filter:a", filter_str,
            str(output_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            console.print(f"[yellow]Speed adjustment failed, using original speed[/yellow]")
            temp_path.rename(output_path)
        else:
            temp_path.unlink()
    else:
        with open(output_path, "wb") as f:
            f.write(response.content)

    # Get actual duration
    from moviepy import AudioFileClip
    audio = AudioFileClip(str(output_path))
    duration = audio.duration
    audio.close()
    return duration


def get_elevenlabs_voice_id(voice: str, api_key: str) -> str:
    """
    Get voice_id from voice name. If voice is already an ID, return it.
    """
    # If it looks like a voice_id (21 chars, alphanumeric), return as-is
    if len(voice) == 21 and voice.isalnum():
        return voice

    # Otherwise, look up by name
    voices = list_elevenlabs_voices(api_key)

    # Check exact match first
    for v in voices:
        if v["name"].lower() == voice.lower():
            return v["voice_id"]

    # Check partial match
    for v in voices:
        if voice.lower() in v["name"].lower():
            return v["voice_id"]

    # If not found, assume it's a voice_id
    return voice


def list_elevenlabs_voices(api_key: Optional[str] = None) -> list:
    """
    List all available ElevenLabs voices (including cloned voices).
    Returns list of dicts with voice_id, name, and category.
    """
    api_key = api_key or os.getenv("ELEVENLABS_API_KEY") or os.getenv("XI_API_KEY")
    if not api_key:
        return []

    url = "https://api.elevenlabs.io/v1/voices"
    headers = {"xi-api-key": api_key}

    try:
        response = requests.get(url, headers=headers, timeout=30)
        if response.status_code == 200:
            data = response.json()
            voices = []
            for v in data.get("voices", []):
                voices.append({
                    "voice_id": v.get("voice_id"),
                    "name": v.get("name"),
                    "category": v.get("category", "unknown"),
                    "description": v.get("labels", {}).get("description", "")
                })
            return voices
    except Exception:
        pass

    return []


def clone_voice_elevenlabs(
    name: str,
    audio_files: List[Path],
    api_key: Optional[str] = None,
    description: str = "",
    accent: str = "",
    gender: str = "",
    age: str = ""
) -> str:
    """
    Clone a voice using ElevenLabs Voice Cloning.

    Args:
        name: Name for the cloned voice (e.g., "Smritika")
        audio_files: List of audio file paths (mp3, wav) for voice samples
        api_key: ElevenLabs API key
        description: Optional description of the voice
        accent: Accent label (e.g., "British", "Indian", "American")
        gender: Gender label (e.g., "male", "female")
        age: Age label (e.g., "young", "middle_aged", "old")

    Returns:
        voice_id of the cloned voice
    """
    api_key = api_key or os.getenv("ELEVENLABS_API_KEY") or os.getenv("XI_API_KEY")
    if not api_key:
        raise ValueError(
            "ElevenLabs API key not set.\n"
            "Get your key at: https://elevenlabs.io/app/settings/api-keys\n"
            "Then set: export ELEVENLABS_API_KEY=your_key"
        )

    url = "https://api.elevenlabs.io/v1/voices/add"

    headers = {
        "xi-api-key": api_key
    }

    # Prepare files for upload
    files = []
    for audio_file in audio_files:
        audio_path = Path(audio_file)
        if audio_path.exists():
            files.append(("files", (audio_path.name, open(audio_path, "rb"), "audio/mpeg")))

    if not files:
        raise ValueError("No valid audio files provided for voice cloning")

    # Build labels for accent, gender, age
    import json as _json
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

    if labels:
        data["labels"] = _json.dumps(labels)

    try:
        response = requests.post(url, headers=headers, data=data, files=files, timeout=120)

        # Close file handles
        for _, (_, f, _) in files:
            f.close()

        if response.status_code == 200:
            result = response.json()
            voice_id = result.get("voice_id")
            console.print(f"[green]✓ Voice '{name}' cloned successfully! Voice ID: {voice_id}[/green]")
            return voice_id
        else:
            raise ValueError(f"ElevenLabs voice cloning failed ({response.status_code}): {response.text[:300]}")

    except Exception as e:
        # Close file handles on error
        for _, (_, f, _) in files:
            try:
                f.close()
            except:
                pass
        raise e


def generate_audio_segments(
    scripts: List[str],
    output_dir: Path,
    engine: str = "edge",
    voice: Optional[str] = None,
    speed: float = 1.0
) -> List[AudioSegment]:
    """
    Generate audio for all script segments.

    Args:
        scripts: List of text scripts to convert
        output_dir: Directory to save audio files
        engine: "edge" (free), "openai", or "elevenlabs"
        voice: Voice to use (engine-specific)
        speed: Speech rate multiplier (1.0 = normal, 1.2 = 20% faster)

    Returns:
        List of AudioSegment with paths and durations
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    segments = []

    # Set default voices
    if voice is None:
        if engine == "edge":
            voice = "en-US-AriaNeural"
        elif engine == "openai":
            voice = "alloy"
        elif engine == "elevenlabs":
            voice = "Rachel"

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        console=console
    ) as progress:
        task = progress.add_task(f"Generating voiceover ({engine})...", total=len(scripts))

        for i, text in enumerate(scripts):
            output_path = output_dir / f"voiceover_{i:03d}.mp3"

            if engine == "edge":
                # Run async edge-tts
                duration = asyncio.run(generate_tts_edge(text, output_path, voice, speed=speed))
            elif engine == "openai":
                duration = generate_tts_openai(text, output_path, voice, speed=speed)
            elif engine == "elevenlabs":
                duration = generate_tts_elevenlabs(text, output_path, voice, speed=speed)
            else:
                raise ValueError(f"Unknown TTS engine: {engine}")

            segments.append(AudioSegment(
                audio_path=output_path,
                duration=duration,
                text=text
            ))

            progress.update(task, advance=1)

    return segments


def extract_audio_from_video(video_path: Path, output_path: Optional[Path] = None) -> Path:
    """
    Extract audio from a video file as MP3 using ffmpeg.

    Args:
        video_path: Path to the video file
        output_path: Where to save the audio (defaults to temp file)

    Returns:
        Path to the extracted audio file
    """
    video_path = Path(video_path)
    if not video_path.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    if output_path is None:
        output_path = Path(tempfile.mktemp(suffix=".mp3"))

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-vn",
        "-acodec", "libmp3lame",
        "-ar", "16000",
        "-ac", "1",
        "-b:a", "64k",
        str(output_path)
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Failed to extract audio: {result.stderr[-300:]}")

    if not output_path.exists() or output_path.stat().st_size == 0:
        raise RuntimeError("Audio extraction produced empty file — video may have no audio track")

    return output_path


def transcribe_elevenlabs(
    input_path: Path,
    api_key: Optional[str] = None,
    language_code: str = "en",
    model_id: str = "scribe_v1"
) -> Transcript:
    """
    Transcribe an audio or video file using ElevenLabs Scribe.

    Accepts video files (audio is extracted automatically) or audio files directly.
    Returns a Transcript with full text and word-level timestamps.

    Args:
        input_path: Path to audio or video file
        api_key: ElevenLabs API key (falls back to ELEVENLABS_API_KEY env var)
        language_code: Language code for transcription (default: "en")
        model_id: Scribe model to use (default: "scribe_v1")

    Returns:
        Transcript with text, word-level timestamps, and metadata
    """
    api_key = api_key or os.getenv("ELEVENLABS_API_KEY") or os.getenv("XI_API_KEY")
    if not api_key:
        raise ValueError(
            "ElevenLabs API key not set.\n"
            "Get your key at: https://elevenlabs.io/app/settings/api-keys\n"
            "Then set: export ELEVENLABS_API_KEY=your_key"
        )

    input_path = Path(input_path)
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    # Determine if we need to extract audio from video
    video_extensions = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".flv", ".wmv", ".m4v"}
    audio_path = input_path
    temp_audio = None

    if input_path.suffix.lower() in video_extensions:
        console.print(f"[dim]Extracting audio from video...[/dim]")
        temp_audio = Path(tempfile.mktemp(suffix=".mp3"))
        audio_path = extract_audio_from_video(input_path, temp_audio)

    try:
        console.print(f"[dim]Transcribing with ElevenLabs Scribe...[/dim]")

        url = "https://api.elevenlabs.io/v1/speech-to-text"
        headers = {"xi-api-key": api_key}

        with open(audio_path, "rb") as f:
            files = {"file": (audio_path.name, f, "audio/mpeg")}
            data = {
                "model_id": model_id,
                "language_code": language_code,
            }

            response = requests.post(url, headers=headers, files=files, data=data, timeout=120)

        if response.status_code == 401:
            raise ValueError("ElevenLabs API authentication failed. Check your API key.")
        elif response.status_code != 200:
            raise ValueError(
                f"ElevenLabs STT error ({response.status_code}): {response.text[:300]}"
            )

        result = response.json()

        # Parse word-level timestamps
        words = []
        if "words" in result:
            for w in result["words"]:
                words.append(TranscriptWord(
                    text=w.get("text", ""),
                    start=w.get("start", 0.0),
                    end=w.get("end", 0.0),
                    confidence=w.get("confidence", 1.0),
                ))

        # Get audio duration
        duration = 0.0
        try:
            from moviepy import AudioFileClip
            audio = AudioFileClip(str(audio_path))
            duration = audio.duration
            audio.close()
        except Exception:
            if words:
                duration = words[-1].end

        transcript = Transcript(
            text=result.get("text", ""),
            words=words,
            language=result.get("language_code", language_code),
            duration=duration,
        )

        console.print(f"[green]✓ Transcribed {duration:.1f}s of audio ({len(words)} words)[/green]")
        return transcript

    finally:
        # Cleanup temp audio if we extracted it
        if temp_audio and temp_audio.exists():
            temp_audio.unlink()


def transcribe_video(
    video_path: Path,
    api_key: Optional[str] = None,
    language_code: str = "en"
) -> str:
    """
    Convenience function: transcribe a video and return just the text.

    Args:
        video_path: Path to the video file
        api_key: ElevenLabs API key
        language_code: Language code (default: "en")

    Returns:
        Transcribed text as a string
    """
    transcript = transcribe_elevenlabs(video_path, api_key=api_key, language_code=language_code)
    return transcript.text


# Available voices for reference
EDGE_VOICES = {
    "en-US-AriaNeural": "Female, conversational",
    "en-US-GuyNeural": "Male, conversational",
    "en-US-JennyNeural": "Female, friendly",
    "en-US-EricNeural": "Male, professional",
    "en-GB-SoniaNeural": "Female, British",
    "en-GB-RyanNeural": "Male, British",
    "en-AU-NatashaNeural": "Female, Australian",
}

OPENAI_VOICES = {
    "alloy": "Neutral, balanced",
    "echo": "Male, warm",
    "fable": "Male, British accent",
    "onyx": "Male, deep",
    "nova": "Female, friendly",
    "shimmer": "Female, expressive",
}

# Default ElevenLabs voices (more available via API)
ELEVENLABS_DEFAULT_VOICES = {
    "Rachel": "Female, calm, narrative",
    "Domi": "Female, confident, strong",
    "Bella": "Female, soft, warm",
    "Antoni": "Male, well-rounded, calm",
    "Elli": "Female, young, emotional",
    "Josh": "Male, deep, narrative",
    "Arnold": "Male, confident, energetic",
    "Adam": "Male, clear, middle-aged",
    "Sam": "Male, raspy, dynamic",
}


def list_available_voices(engine: str = "edge", api_key: Optional[str] = None) -> dict:
    """Return available voices for the specified engine."""
    if engine == "edge":
        return EDGE_VOICES
    elif engine == "openai":
        return OPENAI_VOICES
    elif engine == "elevenlabs":
        # Try to fetch actual voices from API (includes cloned voices)
        voices = list_elevenlabs_voices(api_key)
        if voices:
            return {v["name"]: f"{v['category']}" for v in voices}
        return ELEVENLABS_DEFAULT_VOICES
    else:
        return {}
