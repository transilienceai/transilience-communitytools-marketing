# Audio Utils — `src/core/audio_utils.py`

## Description

Audio extraction, music overlay, and audio processing utilities.

## Functions

### `extract_audio(video_path, output_path=None) -> Path`
Extracts audio from video as MP3 using ffmpeg.
- Default output: `{video_stem}_audio.mp3`
- Settings: 16kHz, mono, 64kbps (processing quality)

### `add_background_music(video_clip, music_path, music_volume=0.03)`
Adds background music to a MoviePy video clip.
- Loops music if shorter than video
- Applies 2-second fade-out
- Combines with existing audio if present
- Returns modified video clip

## Dependencies
- `moviepy` (AudioFileClip, concatenate_audioclips, CompositeAudioClip, AudioFadeOut)
- `subprocess` (ffmpeg)

## Usage
```python
from src.core.audio_utils import extract_audio, add_background_music
from moviepy import VideoFileClip

# Extract audio
audio_path = extract_audio(Path("video.mp4"))

# Add music to clip
clip = VideoFileClip("video.mp4")
clip_with_music = add_background_music(clip, Path("music.mp3"), music_volume=0.04)
```
