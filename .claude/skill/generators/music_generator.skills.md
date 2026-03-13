# Music Generator — `src/generators/music_generator.py`

AI background music generation with multiple engine support.

## Main Entry Point

### `generate_music(prompt="upbeat corporate background music", output_path=None, duration=30, engine="auto") -> Path`
Generate background music. Auto-detects available engine by checking API keys: ElevenLabs > Replicate > Suno > simple (local).

## Engine Functions

### `generate_music_elevenlabs(prompt, output_path, duration=30, api_key=None, use_music_api=True) -> Path`
ElevenLabs Music API (10-300s, paid) with automatic fallback to Sound Effects API (0.5-30s) if subscription insufficient.

### `generate_music_suno(prompt, output_path, duration=30, api_key=None) -> Path`
Suno AI via self-hosted suno-api service or direct cookie-based access. Polls for completion (max 5 min).

### `generate_music_replicate(prompt, output_path, duration=30, api_key=None) -> Path`
Replicate's MusicGen model (stereo-large, max 30s).

### `generate_music_huggingface(prompt, output_path, duration=30, api_key=None) -> Path`
Falls back to enhanced local generation (MusicGen requires paid Inference Endpoints).

### `generate_enhanced_local_music(prompt, output_path, duration=30.0) -> Path`
Local synthesis with chord progressions, harmonics, bass, LFO modulation. Analyzes prompt for style (upbeat/ambient/corporate/neutral).

### `generate_simple_tone(output_path, duration=30.0, frequency=440.0, style="ambient") -> Path`
Basic synthesis — ambient pads or rhythmic patterns. No API required.

## Utilities

### `get_music_prompt_for_tone(tone) -> str`
Maps tone keywords to suitable music prompts. Keys: professional, friendly, exciting, calm, tech, playful.

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
