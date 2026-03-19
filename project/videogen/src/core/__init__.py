"""
Core utilities module - Low-level utilities with minimal dependencies.

Modules:
- video_utils: FFprobe-based video metadata (duration, dimensions, fps)
- image_utils: Image processing (base64 encoding, resizing, MIME types)
- audio_utils: Audio extraction and music overlay
"""

from .video_utils import get_duration, get_video_dimensions, get_video_fps, probe_video
from .image_utils import (
    image_to_base64,
    pil_image_to_base64,
    get_mime_type,
    resize_image_for_api,
    resize_pil_image_for_api,
    get_image_dimensions
)
from .audio_utils import extract_audio, add_background_music

__all__ = [
    # video_utils
    'get_duration',
    'get_video_dimensions',
    'get_video_fps',
    'probe_video',
    # image_utils
    'image_to_base64',
    'pil_image_to_base64',
    'get_mime_type',
    'resize_image_for_api',
    'resize_pil_image_for_api',
    'get_image_dimensions',
    # audio_utils
    'extract_audio',
    'add_background_music',
]
