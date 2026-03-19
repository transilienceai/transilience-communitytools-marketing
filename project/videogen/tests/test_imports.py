"""Test that all modules import without errors (skips if deps missing)."""

import importlib
import pytest


ALL_MODULES = [
    "src.core.video_utils",
    "src.core.audio_utils",
    "src.core.image_utils",
    "src.pipeline.screenshot_handler",
    "src.pipeline.blend_handler",
    "src.pipeline.video_assembler",
    "src.pipeline.veo_pipeline",
    "src.pipeline.storyboard_planner",
    "src.pipeline.bookend_generator",
    "src.pipeline.website_screenshotter",
    "src.processing.video_cleaner",
    "src.processing.video_effects",
    "src.processing.video_extractors",
    "src.processing.avatar_overlay",
    "src.processing.post_processor",
    "src.generators.text_animator",
    "src.generators.music_generator",
    "src.ai.gemini_client",
    "src.ai.ai_analyzer",
    "src.ai.tts_engine",
    "src.ai.veo_generator",
    "src.ai.imagen_generator",
]


@pytest.mark.parametrize("module", ALL_MODULES)
def test_module_imports(mock_env, module):
    """Each module should import or skip gracefully if deps are missing."""
    try:
        mod = importlib.import_module(module)
        assert mod is not None
    except ImportError as e:
        pytest.skip(f"Dependency missing: {e}")
