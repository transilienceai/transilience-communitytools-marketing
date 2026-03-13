# TTS Engine — `src/ai/tts_engine.py`

Text-to-Speech and Speech-to-Text engine supporting Edge TTS (free), OpenAI TTS, and ElevenLabs with voice cloning and transcription.

## Classes

### `AudioSegment`
- `audio_path` — Path to generated audio
- `duration` — Audio duration (seconds)
- `text` — Source text

### `TranscriptWord`
- `text` — Word text
- `start` — Start time (seconds)
- `end` — End time (seconds)
- `confidence` — Confidence score

### `Transcript`
- `text` — Full transcription text
- `words` — List of `TranscriptWord`
- `language` — Detected language
- `duration` — Total duration

## TTS Functions

### `generate_tts_edge(text, output_path, voice="en-US-AriaNeural", speed=1.0) -> float` (async)
Free TTS using Microsoft Edge voices. Returns audio duration.

### `generate_tts_openai(text, output_path, voice="alloy", api_key=None, speed=1.0) -> float`
TTS using OpenAI API. Returns audio duration.

### `generate_tts_elevenlabs(text, output_path, voice="Rachel", api_key=None, model="eleven_multilingual_v2", speed=1.0) -> float`
Premium TTS using ElevenLabs. Supports speed adjustment via ffmpeg atempo. Returns audio duration.

### `generate_audio_segments(scripts, output_dir, engine="edge", voice=None, speed=1.0) -> List[AudioSegment]`
Generates audio for all script segments. Returns list of `AudioSegment`.

## Voice Functions

### `get_elevenlabs_voice_id(voice, api_key) -> str`
Converts voice name to voice_id. Returns id as-is if already an id.

### `list_elevenlabs_voices(api_key=None) -> list`
Lists all available ElevenLabs voices (including cloned). Returns list of dicts with `voice_id`, `name`, `category`, `description`.

### `clone_voice_elevenlabs(name, audio_files, api_key=None, description="", accent="", gender="", age="") -> str`
Clones voice using ElevenLabs. Returns `voice_id` of cloned voice.

### `list_available_voices(engine="edge", api_key=None) -> dict`
Returns available voices for specified engine.

## Transcription Functions

### `transcribe_elevenlabs(input_path, api_key=None, language_code="en", model_id="scribe_v1") -> Transcript`
Transcribes audio/video using ElevenLabs Scribe with word-level timestamps. Auto-extracts audio from video files.

### `transcribe_video(video_path, api_key=None, language_code="en") -> str`
Convenience function: transcribes video and returns just the text.

### `extract_audio_from_video(video_path, output_path=None) -> Path`
Extracts audio from video as MP3 using ffmpeg.

## Dependencies
- `edge_tts`, `openai`, `requests`, `moviepy`, `subprocess` (ffmpeg)

## Usage
```python
from src.ai.tts_engine import generate_tts_elevenlabs, clone_voice_elevenlabs

# Clone a voice
voice_id = clone_voice_elevenlabs("Aman", [Path("recording.mp3")], accent="Indian", gender="male")

# Generate TTS
duration = generate_tts_elevenlabs("Hello world", Path("output.mp3"), voice="Aman")

# Transcribe video
from src.ai.tts_engine import transcribe_video
text = transcribe_video(Path("demo.mp4"))
```
