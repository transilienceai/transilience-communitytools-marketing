"""
Marketing Video CLI - AI-powered marketing video generator

Features:
- AI-powered script generation (Claude Vision)
- Video generation backend (Veo 3.1)
- Text-to-speech (ElevenLabs, Edge TTS, OpenAI)
- Text animations with cursor, highlights, zoom
- Background music support
"""

# Core utilities (low-level, no dependencies on other src modules)
from .core.video_utils import get_duration, get_video_dimensions, get_video_fps, probe_video
from .core.image_utils import (
    image_to_base64,
    pil_image_to_base64,
    get_mime_type,
    get_image_media_type,
    resize_image_for_api,
    resize_pil_image_for_api,
    get_image_dimensions,
)
from .core.audio_utils import extract_audio, add_background_music

# Video processing & effects
from .processing.video_cleaner import analyze_motion, find_stillness_periods, clean_video
from .processing.video_effects import apply_cinematic_effects
from .processing.video_extractors import extract_keyframes, extract_last_frame, extract_frame_at_time

# AI/ML services
from .ai.ai_analyzer import analyze_screenshots, VideoScript, SceneScript
from .ai.veo_generator import generate_video_veo, animate_image_veo, list_veo_models
from .ai.tts_engine import (
    generate_audio_segments,
    list_available_voices,
    transcribe_elevenlabs,
    transcribe_video,
    extract_audio_from_video,
    Transcript,
    TranscriptWord,
    AudioSegment,
)

# Content generators
from .generators.text_animator import create_animated_scene, analyze_image_for_text_regions

# Pipeline orchestration
from .pipeline.screenshot_handler import (
    get_image_files,
    get_media_files,
    validate_images,
    validate_media_files,
    MediaFile,
    MediaType,
    get_video_thumbnail,
    extract_video_frames,
    IMAGE_EXTENSIONS,
    VIDEO_EXTENSIONS,
    PPTX_EXTENSIONS,
)
from .pipeline.video_assembler import assemble_video, SceneConfig, get_recommended_size
from .pipeline.veo_pipeline import create_marketing_video_veo

__all__ = [
    # Video utilities
    "get_duration",
    "get_video_dimensions",
    "get_video_fps",
    "probe_video",
    # Image utilities
    "image_to_base64",
    "pil_image_to_base64",
    "get_mime_type",
    "get_image_media_type",
    "resize_image_for_api",
    "resize_pil_image_for_api",
    "get_image_dimensions",
    # Audio utilities
    "extract_audio",
    "add_background_music",
    # Video processing
    "analyze_motion",
    "find_stillness_periods",
    "clean_video",
    "apply_cinematic_effects",
    "extract_keyframes",
    "extract_last_frame",
    "extract_frame_at_time",
    # Screenshot handling
    "get_image_files",
    "get_media_files",
    "validate_images",
    "validate_media_files",
    "MediaFile",
    "MediaType",
    "get_video_thumbnail",
    "extract_video_frames",
    "IMAGE_EXTENSIONS",
    "VIDEO_EXTENSIONS",
    "PPTX_EXTENSIONS",
    # AI analysis
    "analyze_screenshots",
    "VideoScript",
    "SceneScript",
    # TTS & STT
    "generate_audio_segments",
    "list_available_voices",
    "transcribe_elevenlabs",
    "transcribe_video",
    "extract_audio_from_video",
    "Transcript",
    "TranscriptWord",
    "AudioSegment",
    # Video assembly
    "assemble_video",
    "SceneConfig",
    "get_recommended_size",
    # Veo 3.1
    "generate_video_veo",
    "animate_image_veo",
    "list_veo_models",
    "create_marketing_video_veo",
    # Text animation
    "create_animated_scene",
    "analyze_image_for_text_regions",
]
