"""
Pipeline orchestration module - High-level workflows for video generation.

Modules:
- screenshot_handler: Media ingestion (images, videos, PPT, PDF)
- veo_pipeline: Veo 3.1 animation pipeline orchestration
- video_assembler: Final video assembly and output
"""

from .screenshot_handler import (
    get_media_files,
    get_video_duration,
    extract_pptx_slides,
    get_image_files,
    validate_media_files,
    MediaFile,
    MediaType
)
from .veo_pipeline import create_marketing_video_veo, create_marketing_video_static
from .video_assembler import assemble_video, SceneConfig, get_recommended_size

__all__ = [
    # screenshot_handler
    'get_media_files',
    'get_video_duration',
    'extract_pptx_slides',
    'get_image_files',
    'validate_media_files',
    'MediaFile',
    'MediaType',
    # veo_pipeline
    'create_marketing_video_veo',
    'create_marketing_video_static',
    # video_assembler
    'assemble_video',
    'SceneConfig',
    'get_recommended_size',
]
