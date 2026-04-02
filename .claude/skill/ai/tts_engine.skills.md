# TTS Engine — `src/ai/tts_engine.py`

## Description

Text-to-Speech and Speech-to-Text engine supporting Edge TTS (free), OpenAI TTS, and ElevenLabs with voice cloning and transcription.

## Classes

| Class | Description |
|-------|-------------|
| `AudioSegment` | Dataclass for a generated audio segment. |
| `TranscriptWord` | Dataclass for a single transcribed word with timestamps. |
| `Transcript` | Dataclass for a full transcription result. |

**AudioSegment fields:**
- `audio_path` — Path to generated audio
- `duration` — Audio duration (seconds)
- `text` — Source text

**TranscriptWord fields:**
- `text` — Word text
- `start` — Start time (seconds)
- `end` — End time (seconds)
- `confidence` — Confidence score

**Transcript fields:**
- `text` — Full transcription text
- `words` — List of `TranscriptWord`
- `language` — Detected language
- `duration` — Total duration

## TTS Functions

| Function | Description |
|----------|-------------|
| `generate_tts_edge()` | Free TTS using Microsoft Edge voices. Returns audio duration. (async) |
| `generate_tts_openai()` | TTS using OpenAI API. Returns audio duration. |
| `generate_tts_elevenlabs()` | Premium TTS using ElevenLabs. Supports speed adjustment via ffmpeg atempo. Returns audio duration. |
| `generate_audio_segments()` | Generates audio for all script segments. Returns list of `AudioSegment`. |

## Voice Functions

| Function | Description |
|----------|-------------|
| `get_elevenlabs_voice_id()` | Converts voice name to voice_id. Returns id as-is if already an id. |
| `list_elevenlabs_voices()` | Lists all available ElevenLabs voices (including cloned). Returns list of dicts with `voice_id`, `name`, `category`, `description`. |
| `clone_voice_elevenlabs()` | Clones voice using ElevenLabs. Returns `voice_id` of cloned voice. |
| `list_available_voices()` | Returns available voices for specified engine. |

## Transcription Functions

| Function | Description |
|----------|-------------|
| `transcribe_elevenlabs()` | Transcribes audio/video using ElevenLabs Scribe with word-level timestamps. Auto-extracts audio from video files. |
| `transcribe_video()` | Convenience function: transcribes video and returns just the text. |
| `extract_audio_from_video()` | Extracts audio from video as MP3 using ffmpeg. |

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
