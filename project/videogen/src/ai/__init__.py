"""
AI/ML services module - Claude Vision, Veo 3.1, and TTS.

Modules:
- ai_analyzer: Claude Vision content analysis
- veo_generator: Google Veo 3.1 image-to-video animation
- tts_engine: Text-to-speech (ElevenLabs, Edge TTS)
"""

from .ai_analyzer import analyze_screenshots, analyze_media_files, regenerate_scene_script, VideoScript, SceneScript
from .veo_generator import generate_video_veo, generate_video_from_images_veo, animate_image_veo, list_veo_models
from .tts_engine import (
    AudioSegment,
    TranscriptWord,
    Transcript,
    generate_tts_openai,
    generate_tts_elevenlabs,
    get_elevenlabs_voice_id,
    list_elevenlabs_voices,
    clone_voice_elevenlabs,
    generate_audio_segments,
    extract_audio_from_video,
    transcribe_elevenlabs,
    transcribe_video,
    list_available_voices
)

__all__ = [
    # ai_analyzer
    'analyze_screenshots',
    'analyze_media_files',
    'regenerate_scene_script',
    'VideoScript',
    'SceneScript',
    # veo_generator
    'generate_video_veo',
    'generate_video_from_images_veo',
    'animate_image_veo',
    'list_veo_models',
    # tts_engine
    'AudioSegment',
    'TranscriptWord',
    'Transcript',
    'generate_tts_openai',
    'generate_tts_elevenlabs',
    'get_elevenlabs_voice_id',
    'list_elevenlabs_voices',
    'clone_voice_elevenlabs',
    'generate_audio_segments',
    'extract_audio_from_video',
    'transcribe_elevenlabs',
    'transcribe_video',
    'list_available_voices',
]
