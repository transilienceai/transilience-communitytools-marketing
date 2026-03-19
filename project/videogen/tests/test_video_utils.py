"""Tests for src/core/video_utils.py"""

import pytest
from src.core.video_utils import get_duration, get_video_dimensions, get_video_fps, probe_video


class TestGetDuration:
    def test_returns_float(self, sample_video):
        dur = get_duration(sample_video)
        assert isinstance(dur, float)

    def test_approximately_correct(self, sample_video):
        dur = get_duration(sample_video)
        assert 1.5 <= dur <= 2.5, f"Expected ~2s, got {dur}s"

    def test_nonexistent_file_returns_zero(self, tmp_dir):
        dur = get_duration(tmp_dir / "nonexistent.mp4")
        assert dur == 0.0

    def test_audio_file_duration(self, sample_audio):
        dur = get_duration(sample_audio)
        assert 1.5 <= dur <= 2.5


class TestGetVideoDimensions:
    def test_returns_tuple(self, sample_video):
        w, h = get_video_dimensions(sample_video)
        assert isinstance(w, int)
        assert isinstance(h, int)

    def test_correct_dimensions(self, sample_video):
        w, h = get_video_dimensions(sample_video)
        assert w == 320
        assert h == 240

    def test_even_numbers(self, sample_video):
        w, h = get_video_dimensions(sample_video)
        assert w % 2 == 0
        assert h % 2 == 0


class TestGetVideoFps:
    def test_returns_float(self, sample_video):
        fps = get_video_fps(sample_video)
        assert isinstance(fps, float)

    def test_correct_fps(self, sample_video):
        fps = get_video_fps(sample_video)
        assert 29 <= fps <= 31, f"Expected ~30fps, got {fps}"

    def test_nonexistent_returns_default(self, tmp_dir):
        fps = get_video_fps(tmp_dir / "nonexistent.mp4")
        assert fps == 30.0


class TestProbeVideo:
    def test_returns_string(self, sample_video):
        result = probe_video(sample_video, "stream=width,height")
        assert isinstance(result, str)
        assert "320" in result
