"""Tests for src/pipeline/veo_pipeline.py — unit tests for helpers (no API calls)."""

import pytest
from pathlib import Path
from unittest.mock import patch

try:
    from src.pipeline.veo_pipeline import (
        SceneData,
        combine_video_with_audio,
        add_background_music_to_file,
        enhance_script_for_tts,
    )
    HAS_DEPS = True
except ImportError:
    HAS_DEPS = False

pytestmark = pytest.mark.skipif(not HAS_DEPS, reason="rich/moviepy not installed")


class TestSceneData:
    def test_create_scene(self):
        scene = SceneData(image_path=Path("test.png"), script="Hello world")
        assert scene.script == "Hello world"
        assert scene.is_video is False
        assert scene.preserve_audio is False
        assert scene.duration == 8.0

    def test_preserve_audio_flag(self):
        scene = SceneData(image_path=Path("test.png"), script="test", preserve_audio=True)
        assert scene.preserve_audio is True

    def test_video_scene(self):
        scene = SceneData(
            image_path=Path("thumb.png"),
            script="narration",
            video_path=Path("demo.mp4"),
            is_video=True,
        )
        assert scene.is_video is True
        assert scene.video_path == Path("demo.mp4")

    def test_no_voiceover_scene(self):
        scene = SceneData(
            image_path=Path("test.png"),
            script="",
            video_path=Path("screen.webm"),
            is_video=True,
            preserve_audio=True,
        )
        assert scene.script == ""
        assert scene.preserve_audio is True


class TestCombineVideoWithAudio:
    def test_combines_video_and_audio(self, sample_video, sample_audio, tmp_dir):
        output = tmp_dir / "combined.mp4"
        result = combine_video_with_audio(sample_video, sample_audio, output)
        assert result.exists()
        assert result.stat().st_size > 0

    def test_no_speed_adjust(self, sample_video, sample_audio, tmp_dir):
        output = tmp_dir / "combined_nospeed.mp4"
        result = combine_video_with_audio(sample_video, sample_audio, output, no_speed_adjust=True)
        assert result.exists()

    def test_preserve_audio_uses_ducking(self, sample_video, sample_audio, tmp_dir):
        output = tmp_dir / "ducked.mp4"
        result = combine_video_with_audio(sample_video, sample_audio, output, original_audio_volume=1.0)
        assert result.exists()


class TestAddBackgroundMusic:
    def test_adds_music(self, sample_video, sample_audio, tmp_dir):
        import shutil
        src = tmp_dir / "source.mp4"
        shutil.copy(sample_video, src)
        output = tmp_dir / "with_music.mp4"
        add_background_music_to_file(src, sample_audio, output, music_volume=0.03)
        assert output.exists()


class TestEnhanceScriptForTts:
    def test_returns_string(self):
        with patch("src.pipeline.veo_pipeline.generate_text") as mock_gen:
            mock_gen.return_value = "ENHANCED script with — pauses..."
            result = enhance_script_for_tts("Basic script about a product")
            assert isinstance(result, str)
            assert len(result) > 0

    def test_fallback_on_error(self):
        with patch("src.pipeline.veo_pipeline.generate_text", side_effect=Exception("API down")):
            result = enhance_script_for_tts("Fallback test script")
            assert "Fallback test script" in result
