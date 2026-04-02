"""
Video processing module - Motion detection, effects, and frame extraction.

Modules:
- video_cleaner: Motion detection and still frame removal
- video_effects: Cinematic effects (zoom, pan, color grading)
- video_extractors: Keyframe and frame extraction utilities
- post_processor: Post-processing (speed, volume, remix)
"""

from .video_cleaner import analyze_motion, find_stillness_periods, clean_video
from .video_effects import apply_cinematic_effects
from .video_extractors import extract_keyframes, extract_last_frame, extract_frame_at_time
from .post_processor import adjust_video, build_atempo_chain, load_manifest
from .caption_renderer import burn_captions_onto_video, CaptionWord

__all__ = [
    # video_cleaner
    'analyze_motion',
    'find_stillness_periods',
    'clean_video',
    # video_effects
    'apply_cinematic_effects',
    # video_extractors
    'extract_keyframes',
    'extract_last_frame',
    'extract_frame_at_time',
    # post_processor
    'adjust_video',
    'build_atempo_chain',
    'load_manifest',
    # caption_renderer
    'burn_captions_onto_video',
    'CaptionWord',
]
