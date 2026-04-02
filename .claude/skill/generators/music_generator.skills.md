# Music Generator — `src/generators/music_generator.py`

## Description

AI background music generation with multiple engine support.

## Main Entry Point

| Function | Description |
|----------|-------------|
| `generate_music()` | Generate background music. Auto-detects available engine by checking API keys: ElevenLabs > Replicate > Suno > simple (local). |

## Engine Functions

| Function | Description |
|----------|-------------|
| `generate_music_elevenlabs()` | ElevenLabs Music API (10-300s, paid) with automatic fallback to Sound Effects API (0.5-30s) if subscription insufficient. |
| `generate_music_suno()` | Suno AI via self-hosted suno-api service or direct cookie-based access. Polls for completion (max 5 min). |
| `generate_music_replicate()` | Replicate's MusicGen model (stereo-large, max 30s). |
| `generate_music_huggingface()` | Falls back to enhanced local generation (MusicGen requires paid Inference Endpoints). |
| `generate_enhanced_local_music()` | Local synthesis with chord progressions, harmonics, bass, LFO modulation. Analyzes prompt for style (upbeat/ambient/corporate/neutral). |
| `generate_simple_tone()` | Basic synthesis — ambient pads or rhythmic patterns. No API required. |

## Utilities

| Function | Description |
|----------|-------------|
| `get_music_prompt_for_tone()` | Maps tone keywords to suitable music prompts. Keys: professional, friendly, exciting, calm, tech, playful. |

## Dependencies
- `requests`, `numpy`, `scipy.io.wavfile`, `rich`
- Optional: `replicate` SDK
- FFmpeg (for WAV→MP3 conversion)
- API keys: `ELEVENLABS_API_KEY`, `REPLICATE_API_TOKEN`, `SUNO_API_URL`/`SUNO_COOKIE`, `HUGGINGFACE_API_TOKEN`

## Usage
```python
from src.generators.music_generator import generate_music, get_music_prompt_for_tone

# Auto-detect best engine
path = generate_music("upbeat corporate", Path("music.mp3"), duration=30)

# Specific engine
path = generate_music("calm piano", Path("bg.mp3"), engine="elevenlabs")

# Get prompt from tone
prompt = get_music_prompt_for_tone("exciting")  # "energetic electronic..."
```
