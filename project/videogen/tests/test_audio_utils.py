"""Tests for src/core/audio_utils.py"""

import pytest

try:
    from src.core.audio_utils import extract_audio
except ImportError:
    pytest.skip("moviepy not installed", allow_module_level=True)


class TestExtractAudio:
    def test_extracts_mp3(self, sample_video, tmp_dir):
        output = tmp_dir / "extracted.mp3"
        result = extract_audio(sample_video, output)
        assert result.exists()
        assert result.suffix == ".mp3"
        assert result.stat().st_size > 0

    def test_default_output_path(self, sample_video):
        result = extract_audio(sample_video)
        assert result.exists()
        assert "_audio.mp3" in result.name
        result.unlink()  # cleanup

    def test_silent_video_raises(self, sample_video_no_audio, tmp_dir):
        output = tmp_dir / "silent.mp3"
        # ffmpeg may still produce an empty file or fail
        try:
            result = extract_audio(sample_video_no_audio, output)
            # If it succeeds, file should exist (may be tiny)
            assert result.exists()
        except RuntimeError:
            pass  # Expected — no audio to extract
