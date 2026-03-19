"""
AI Music Generator
Generates background music using various AI services.

Supported engines:
- elevenlabs: ElevenLabs Music API (high quality, commercial use)
- huggingface: Free! Uses Hugging Face Inference API with MusicGen
- replicate: Paid, uses Replicate's MusicGen model
- suno: Suno AI API (free tier available)
- simple: Free, local synthesis (no AI, basic tones)
"""

import os
import io
import time
import requests
from pathlib import Path
from typing import Optional
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()


def generate_music_elevenlabs(
    prompt: str,
    output_path: Path,
    duration: int = 30,
    api_key: Optional[str] = None,
    use_music_api: bool = True
) -> Path:
    """
    Generate music using ElevenLabs API.

    Supports both:
    - Eleven Music API: Full music generation (10s-5min, paid users only)
    - Sound Effects API: Sound effects and short loops (up to 30s)

    Args:
        prompt: Description of the music to generate
        output_path: Where to save the audio file
        duration: Length in seconds (10-300 for music, 0.5-30 for SFX)
        api_key: ElevenLabs API key (or set ELEVENLABS_API_KEY env var)
        use_music_api: True for Eleven Music, False for Sound Effects

    Returns:
        Path to the generated audio file
    """
    api_key = api_key or os.getenv("ELEVENLABS_API_KEY") or os.getenv("XI_API_KEY")
    if not api_key:
        raise ValueError(
            "ElevenLabs API key not set.\n"
            "Get your key at: https://elevenlabs.io/app/settings/api-keys\n"
            "Then set: export ELEVENLABS_API_KEY=your_key"
        )

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        if use_music_api:
            try:
                return _generate_elevenlabs_music(prompt, output_path, duration, api_key, progress)
            except ValueError as e:
                if "403" in str(e) or "paid" in str(e).lower() or "subscription" in str(e).lower():
                    console.print("[yellow]Music API requires paid plan — falling back to Sound Effects API[/yellow]")
                    return _generate_elevenlabs_sfx(prompt, output_path, min(duration, 30), api_key, progress)
                raise
        else:
            return _generate_elevenlabs_sfx(prompt, output_path, duration, api_key, progress)


def _generate_elevenlabs_music(
    prompt: str,
    output_path: Path,
    duration: int,
    api_key: str,
    progress
) -> Path:
    """Generate music using ElevenLabs Music API."""

    task = progress.add_task("Generating music with ElevenLabs Music API...", total=None)

    # Eleven Music API endpoint
    url = "https://api.elevenlabs.io/v1/music"

    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json"
    }

    # Clamp duration to Music API limits (10-300 seconds)
    music_duration = max(10, min(duration, 300))

    payload = {
        "prompt": prompt,
        "duration_seconds": music_duration,
        "instrumental": True  # Background music should be instrumental
    }

    response = requests.post(url, headers=headers, json=payload, timeout=120)

    if response.status_code == 401:
        raise ValueError(
            "ElevenLabs API authentication failed.\n"
            "Please verify your API key is correct."
        )
    elif response.status_code == 403:
        raise ValueError(
            "ElevenLabs Music API requires a paid subscription.\n"
            "Falling back to Sound Effects API for shorter clips,\n"
            "or upgrade at: https://elevenlabs.io/pricing"
        )
    elif response.status_code != 200:
        raise ValueError(f"ElevenLabs API error ({response.status_code}): {response.text[:300]}")

    # Response is the audio file directly
    progress.update(task, description="Saving generated music...")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(response.content)

    console.print(f"[green]✓ Music generated with ElevenLabs: {output_path}[/green]")
    return output_path


def _generate_elevenlabs_sfx(
    prompt: str,
    output_path: Path,
    duration: int,
    api_key: str,
    progress
) -> Path:
    """Generate sound effects using ElevenLabs Sound Effects API."""

    task = progress.add_task("Generating audio with ElevenLabs Sound Effects...", total=None)

    # Sound Effects API endpoint
    url = "https://api.elevenlabs.io/v1/sound-generation"

    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json"
    }

    # Clamp duration to SFX API limits (0.5-30 seconds)
    sfx_duration = max(0.5, min(duration, 30))

    payload = {
        "text": prompt,
        "duration_seconds": sfx_duration
    }

    response = requests.post(url, headers=headers, json=payload, timeout=60)

    if response.status_code == 401:
        raise ValueError(
            "ElevenLabs API authentication failed.\n"
            "Please verify your API key is correct."
        )
    elif response.status_code != 200:
        raise ValueError(f"ElevenLabs API error ({response.status_code}): {response.text[:300]}")

    # Response is the audio file directly
    progress.update(task, description="Saving generated audio...")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(response.content)

    console.print(f"[green]✓ Audio generated with ElevenLabs: {output_path}[/green]")
    return output_path


def generate_music_huggingface(
    prompt: str,
    output_path: Path,
    duration: int = 30,
    api_key: Optional[str] = None,
    model: str = "facebook/musicgen-small"
) -> Path:
    """
    Generate music using Hugging Face Inference API.

    Note: MusicGen requires custom inference endpoints (paid).
    This function uses the text-to-audio pipeline with supported models.

    FREE to use! Get your token at https://huggingface.co/settings/tokens
    """
    import subprocess

    api_key = api_key or os.getenv("HUGGINGFACE_API_TOKEN") or os.getenv("HF_TOKEN")
    if not api_key:
        raise ValueError(
            "Hugging Face API token not set.\n"
            "Get your FREE token at: https://huggingface.co/settings/tokens\n"
            "Then set: export HUGGINGFACE_API_TOKEN=your_token"
        )

    # MusicGen is not available on free serverless inference API
    # It requires custom Inference Endpoints (paid)
    # Fallback to local generation with enhanced quality
    console.print("[yellow]Note: MusicGen requires paid Inference Endpoints on Hugging Face.[/yellow]")
    console.print("[yellow]Generating enhanced local music instead...[/yellow]")

    # Use enhanced local generation
    return generate_enhanced_local_music(prompt, output_path, duration)


def generate_enhanced_local_music(
    prompt: str,
    output_path: Path,
    duration: float = 30.0
) -> Path:
    """
    Generate enhanced background music locally using synthesis.
    Creates more musical output than simple tones.
    """
    import numpy as np
    from scipy.io import wavfile
    import subprocess

    sample_rate = 44100
    t = np.linspace(0, duration, int(sample_rate * duration), False)

    # Analyze prompt for style
    prompt_lower = prompt.lower()

    if any(word in prompt_lower for word in ["upbeat", "energetic", "happy", "exciting", "dynamic"]):
        # Upbeat major key progression
        chord_freqs = [
            (261.63, 329.63, 392.00),  # C major
            (293.66, 369.99, 440.00),  # D major
            (329.63, 415.30, 493.88),  # E major
            (349.23, 440.00, 523.25),  # F major
        ]
        tempo = 120
        style = "upbeat"
    elif any(word in prompt_lower for word in ["calm", "relaxing", "ambient", "peaceful", "gentle", "soft"]):
        # Calm ambient pads
        chord_freqs = [
            (220.00, 277.18, 329.63),  # A minor
            (196.00, 246.94, 293.66),  # G major
            (174.61, 220.00, 261.63),  # F major
            (164.81, 207.65, 246.94),  # E minor
        ]
        tempo = 60
        style = "ambient"
    elif any(word in prompt_lower for word in ["corporate", "professional", "business", "inspiring"]):
        # Professional/corporate sound
        chord_freqs = [
            (261.63, 329.63, 392.00),  # C major
            (220.00, 277.18, 329.63),  # A minor
            (174.61, 220.00, 261.63),  # F major
            (196.00, 246.94, 293.66),  # G major
        ]
        tempo = 100
        style = "corporate"
    else:
        # Default neutral
        chord_freqs = [
            (261.63, 329.63, 392.00),  # C major
            (220.00, 277.18, 329.63),  # A minor
            (174.61, 220.00, 261.63),  # F major
            (196.00, 246.94, 293.66),  # G major
        ]
        tempo = 90
        style = "neutral"

    # Generate the music
    wave = np.zeros(len(t))
    beat_duration = 60.0 / tempo
    samples_per_beat = int(sample_rate * beat_duration)
    beats_per_chord = 4

    for i, sample_idx in enumerate(range(0, len(t), samples_per_beat * beats_per_chord)):
        chord_idx = (i // 1) % len(chord_freqs)
        freqs = chord_freqs[chord_idx]

        end_idx = min(sample_idx + samples_per_beat * beats_per_chord, len(t))
        segment_t = t[sample_idx:end_idx] - t[sample_idx]

        # Create chord with harmonics
        segment = np.zeros(len(segment_t))
        for freq in freqs:
            # Fundamental
            segment += 0.3 * np.sin(2 * np.pi * freq * segment_t)
            # Soft harmonics
            segment += 0.1 * np.sin(2 * np.pi * freq * 2 * segment_t)
            segment += 0.05 * np.sin(2 * np.pi * freq * 3 * segment_t)

        # Add subtle low bass
        bass_freq = freqs[0] / 2
        segment += 0.2 * np.sin(2 * np.pi * bass_freq * segment_t)

        # Apply envelope for smooth transitions
        attack = int(0.1 * len(segment))
        release = int(0.2 * len(segment))
        envelope = np.ones(len(segment))
        envelope[:attack] = np.linspace(0, 1, attack)
        envelope[-release:] = np.linspace(1, 0, release)
        segment *= envelope

        wave[sample_idx:end_idx] += segment

    # Add subtle modulation for movement
    lfo = 0.1 * np.sin(2 * np.pi * 0.2 * t)  # Slow LFO
    wave = wave * (1 + lfo)

    # Normalize
    wave = wave / (np.max(np.abs(wave)) + 0.001)
    wave *= 0.8  # Leave headroom

    # Fade in/out
    fade_samples = int(sample_rate * 2)
    wave[:fade_samples] *= np.linspace(0, 1, fade_samples)
    wave[-fade_samples:] *= np.linspace(1, 0, fade_samples)

    # Convert to 16-bit
    audio = (wave * 32767).astype(np.int16)

    # Save as WAV
    wav_path = output_path.with_suffix('.wav')
    wavfile.write(str(wav_path), sample_rate, audio)

    # Convert to MP3
    if output_path.suffix.lower() == '.mp3':
        subprocess.run([
            'ffmpeg', '-y', '-i', str(wav_path),
            '-codec:a', 'libmp3lame', '-qscale:a', '2',
            str(output_path)
        ], capture_output=True)
        wav_path.unlink()
    else:
        wav_path.rename(output_path)

    console.print(f"[green]✓ Generated {style} background music: {output_path}[/green]")
    return output_path




def generate_music_suno(
    prompt: str,
    output_path: Path,
    duration: int = 30,
    api_key: Optional[str] = None
) -> Path:
    """
    Generate music using Suno AI API (via suno-api service).

    Requires either:
    - SUNO_API_URL: URL to your self-hosted suno-api instance
    - SUNO_COOKIE: Your Suno session cookie (for direct API access)

    Setup options:
    1. Use suno-api (recommended): https://github.com/gcui-art/suno-api
       - Deploy it, then set SUNO_API_URL=http://localhost:3000
    2. Get cookie from suno.com (browser dev tools) and set SUNO_COOKIE
    """
    import subprocess

    api_url = os.getenv("SUNO_API_URL")
    cookie = api_key or os.getenv("SUNO_COOKIE")

    if not api_url and not cookie:
        raise ValueError(
            "Suno API not configured.\n\n"
            "Option 1 - Use suno-api (recommended):\n"
            "  1. Deploy: https://github.com/gcui-art/suno-api\n"
            "  2. Set: export SUNO_API_URL=http://localhost:3000\n\n"
            "Option 2 - Use Suno cookie:\n"
            "  1. Login to suno.com\n"
            "  2. Open DevTools > Application > Cookies\n"
            "  3. Copy the cookie value\n"
            "  4. Set: export SUNO_COOKIE=your_cookie_here"
        )

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task("Generating music with Suno AI...", total=None)

        if api_url:
            # Use suno-api service
            response = requests.post(
                f"{api_url.rstrip('/')}/api/generate",
                json={
                    "prompt": prompt,
                    "make_instrumental": True,
                    "wait_audio": True
                },
                timeout=300
            )

            if response.status_code != 200:
                raise ValueError(f"Suno API error ({response.status_code}): {response.text[:200]}")

            data = response.json()

            # Get the audio URL from response
            if isinstance(data, list) and len(data) > 0:
                audio_url = data[0].get("audio_url")
            elif isinstance(data, dict):
                audio_url = data.get("audio_url")
            else:
                raise ValueError(f"Unexpected Suno API response: {data}")

            if not audio_url:
                raise ValueError("No audio URL in Suno response")

            progress.update(task, description="Downloading generated music...")

            # Download the audio
            audio_response = requests.get(audio_url, timeout=120)
            audio_response.raise_for_status()
            audio_data = audio_response.content

        else:
            # Direct Suno API (using cookie)
            headers = {
                "Cookie": cookie,
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0"
            }

            # Create generation request
            response = requests.post(
                "https://studio-api.suno.ai/api/generate/v2/",
                headers=headers,
                json={
                    "prompt": prompt,
                    "make_instrumental": True,
                    "mv": "chirp-v3-5"
                },
                timeout=60
            )

            if response.status_code != 200:
                raise ValueError(
                    f"Suno API error ({response.status_code}): {response.text[:200]}\n"
                    "Your cookie may have expired. Get a new one from suno.com"
                )

            data = response.json()
            clip_ids = [clip["id"] for clip in data.get("clips", [])]

            if not clip_ids:
                raise ValueError("No clips generated")

            # Poll for completion
            progress.update(task, description="Waiting for Suno to generate music...")
            audio_url = None

            for _ in range(60):  # Max 5 minutes
                time.sleep(5)

                status_response = requests.get(
                    f"https://studio-api.suno.ai/api/feed/?ids={clip_ids[0]}",
                    headers=headers,
                    timeout=30
                )

                if status_response.status_code == 200:
                    status_data = status_response.json()
                    if status_data and len(status_data) > 0:
                        clip = status_data[0]
                        if clip.get("audio_url"):
                            audio_url = clip["audio_url"]
                            break
                        status = clip.get("status", "unknown")
                        progress.update(task, description=f"Suno status: {status}...")

            if not audio_url:
                raise ValueError("Suno generation timed out")

            progress.update(task, description="Downloading generated music...")
            audio_response = requests.get(audio_url, timeout=120)
            audio_response.raise_for_status()
            audio_data = audio_response.content

        # Save the audio
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Suno returns MP3
        temp_path = output_path.with_suffix('.mp3')
        with open(temp_path, 'wb') as f:
            f.write(audio_data)

        # Convert if needed
        if output_path.suffix.lower() != '.mp3':
            result = subprocess.run([
                'ffmpeg', '-y', '-i', str(temp_path),
                str(output_path)
            ], capture_output=True)
            temp_path.unlink()
            if result.returncode != 0:
                raise ValueError(f"FFmpeg conversion failed: {result.stderr.decode()}")
        else:
            if temp_path != output_path:
                temp_path.rename(output_path)

    console.print(f"[green]✓ Music generated with Suno AI: {output_path}[/green]")
    return output_path


def generate_music_replicate(
    prompt: str,
    output_path: Path,
    duration: int = 30,
    api_key: Optional[str] = None
) -> Path:
    """
    Generate music using Replicate's MusicGen model.
    Requires REPLICATE_API_TOKEN environment variable.
    """
    import replicate

    api_key = api_key or os.getenv("REPLICATE_API_TOKEN")
    if not api_key:
        raise ValueError("REPLICATE_API_TOKEN not set. Get one at https://replicate.com")

    os.environ["REPLICATE_API_TOKEN"] = api_key

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task("Generating music with AI...", total=None)

        # Use MusicGen model
        output = replicate.run(
            "meta/musicgen:671ac645ce5e552cc63a54a2bbff63fcf798043055d2dac5fc9e36a837eedcfb",
            input={
                "prompt": prompt,
                "duration": min(duration, 30),  # MusicGen max is 30s
                "model_version": "stereo-large",
                "output_format": "mp3",
                "normalization_strategy": "peak"
            }
        )

        progress.update(task, description="Downloading generated music...")

        # Download the generated audio
        response = requests.get(output, timeout=60)
        response.raise_for_status()

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'wb') as f:
            f.write(response.content)

    console.print(f"[green]✓ Music generated: {output_path}[/green]")
    return output_path


def generate_simple_tone(
    output_path: Path,
    duration: float = 30.0,
    frequency: float = 440.0,
    style: str = "ambient"
) -> Path:
    """
    Generate a simple background tone/music using synthesis.
    No API required - uses local generation.
    """
    import numpy as np
    from scipy.io import wavfile
    import subprocess

    sample_rate = 44100
    t = np.linspace(0, duration, int(sample_rate * duration), False)

    if style == "ambient":
        # Create ambient pad with multiple harmonics
        freq1, freq2, freq3 = 220, 277.18, 329.63  # A minor chord
        wave = (
            0.3 * np.sin(2 * np.pi * freq1 * t) +
            0.2 * np.sin(2 * np.pi * freq2 * t) +
            0.2 * np.sin(2 * np.pi * freq3 * t) +
            0.1 * np.sin(2 * np.pi * freq1 * 2 * t)
        )
        # Add slow modulation
        modulation = 0.5 + 0.5 * np.sin(2 * np.pi * 0.1 * t)
        wave = wave * modulation
    elif style == "upbeat":
        # Simple rhythmic pattern
        freq = 329.63  # E4
        beat_freq = 2  # 120 BPM
        wave = np.sin(2 * np.pi * freq * t)
        # Add rhythmic envelope
        envelope = 0.5 + 0.5 * np.abs(np.sin(2 * np.pi * beat_freq * t))
        wave = wave * envelope
    else:
        # Default sine wave
        wave = np.sin(2 * np.pi * frequency * t)

    # Normalize and fade in/out
    wave = wave / np.max(np.abs(wave))
    fade_samples = int(sample_rate * 2)  # 2 second fade
    fade_in = np.linspace(0, 1, fade_samples)
    fade_out = np.linspace(1, 0, fade_samples)
    wave[:fade_samples] *= fade_in
    wave[-fade_samples:] *= fade_out

    # Convert to 16-bit audio
    audio = (wave * 32767).astype(np.int16)

    # Save as WAV first
    wav_path = output_path.with_suffix('.wav')
    wavfile.write(str(wav_path), sample_rate, audio)

    # Convert to MP3 using ffmpeg
    if output_path.suffix.lower() == '.mp3':
        subprocess.run([
            'ffmpeg', '-y', '-i', str(wav_path),
            '-codec:a', 'libmp3lame', '-qscale:a', '2',
            str(output_path)
        ], capture_output=True)
        wav_path.unlink()  # Remove temp WAV
    else:
        wav_path.rename(output_path)

    console.print(f"[green]✓ Generated {style} background music: {output_path}[/green]")
    return output_path


def generate_music(
    prompt: str = "upbeat corporate background music",
    output_path: Path = None,
    duration: int = 30,
    engine: str = "auto"
) -> Path:
    """
    Generate background music using available AI services.

    Args:
        prompt: Description of the music to generate
        output_path: Where to save the music file
        duration: Length in seconds
        engine: "huggingface", "replicate", "simple", or "auto"

    Returns:
        Path to the generated music file
    """
    if output_path is None:
        output_path = Path("generated_music.mp3")

    # Auto-detect available engine (prefer ElevenLabs first)
    if engine == "auto":
        if os.getenv("ELEVENLABS_API_KEY") or os.getenv("XI_API_KEY"):
            engine = "elevenlabs"
            console.print("[cyan]Using ElevenLabs[/cyan]")
        elif os.getenv("REPLICATE_API_TOKEN"):
            engine = "replicate"
            console.print("[cyan]Using Replicate MusicGen[/cyan]")
        elif os.getenv("SUNO_API_URL") or os.getenv("SUNO_COOKIE"):
            engine = "suno"
            console.print("[cyan]Using Suno AI[/cyan]")
        else:
            console.print("[yellow]No AI music API configured. Using enhanced local generator.[/yellow]")
            console.print("[dim]For best quality, set ELEVENLABS_API_KEY[/dim]")
            engine = "simple"

    if engine == "elevenlabs" or engine == "11labs":
        return generate_music_elevenlabs(prompt, output_path, duration)
    elif engine == "elevenlabs-sfx" or engine == "11labs-sfx":
        return generate_music_elevenlabs(prompt, output_path, duration, use_music_api=False)
    elif engine == "suno":
        return generate_music_suno(prompt, output_path, duration)
    elif engine == "huggingface" or engine == "hf":
        return generate_music_huggingface(prompt, output_path, duration)
    elif engine == "replicate":
        return generate_music_replicate(prompt, output_path, duration)
    elif engine == "simple":
        style = "upbeat" if "upbeat" in prompt.lower() else "ambient"
        return generate_simple_tone(output_path, float(duration), style=style)
    else:
        raise ValueError(f"Unknown music engine: {engine}")


# Music prompt suggestions based on video tone
MUSIC_PROMPTS = {
    "professional": "corporate background music, inspiring, motivational, clean",
    "friendly": "upbeat acoustic background music, warm, welcoming, positive",
    "exciting": "energetic electronic background music, dynamic, powerful, modern",
    "calm": "ambient relaxing background music, peaceful, soft, gentle",
    "tech": "modern technology background music, digital, futuristic, innovative",
    "playful": "fun cheerful background music, light, bouncy, happy",
}


def get_music_prompt_for_tone(tone: str) -> str:
    """Get a suitable music prompt based on video tone."""
    tone_lower = tone.lower()
    for key, prompt in MUSIC_PROMPTS.items():
        if key in tone_lower:
            return prompt
    return MUSIC_PROMPTS["professional"]  # Default
