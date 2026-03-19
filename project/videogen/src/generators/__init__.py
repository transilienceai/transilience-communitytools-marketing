"""
Content generators module - Music and text animation.

Modules:
- music_generator: Background music generation (Suno, MusicGen)
- text_animator: Text overlay and animation effects
"""

from .music_generator import (
    generate_music_elevenlabs,
    generate_music_huggingface,
    generate_enhanced_local_music,
    generate_music_suno,
    generate_music_replicate,
    generate_simple_tone,
    generate_music,
    get_music_prompt_for_tone
)
from .text_animator import create_animated_scene, analyze_image_for_text_regions

__all__ = [
    # music_generator
    'generate_music_elevenlabs',
    'generate_music_huggingface',
    'generate_enhanced_local_music',
    'generate_music_suno',
    'generate_music_replicate',
    'generate_simple_tone',
    'generate_music',
    'get_music_prompt_for_tone',
    # text_animator
    'create_animated_scene',
    'analyze_image_for_text_regions',
]
