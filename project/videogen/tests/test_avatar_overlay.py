"""Tests for src/processing/avatar_overlay.py"""

import pytest
from pathlib import Path

try:
    from src.processing.avatar_overlay import overlay_avatar
except ImportError:
    pytest.skip("dependencies not installed", allow_module_level=True)


class TestOverlayAvatar:
    def test_overlay_image_avatar(self, sample_video, sample_image, tmp_dir):
        output = tmp_dir / "with_avatar.mp4"
        result = overlay_avatar(
            input_video=sample_video,
            avatar_source=sample_image,
            output_video=output,
            position="bottom-right",
            scale=0.15,
            margin=20,
        )
        assert result.exists()
        assert result.stat().st_size > 0

    def test_positions(self, sample_video, sample_image, tmp_dir):
        for pos in ["top-left", "top-right", "bottom-left", "bottom-right"]:
            output = tmp_dir / f"avatar_{pos}.mp4"
            result = overlay_avatar(
                input_video=sample_video,
                avatar_source=sample_image,
                output_video=output,
                position=pos,
                scale=0.1,
            )
            assert result.exists(), f"Failed for position {pos}"

    def test_nonexistent_video_raises(self, sample_image, tmp_dir):
        with pytest.raises(Exception):
            overlay_avatar(
                input_video=tmp_dir / "nope.mp4",
                avatar_source=sample_image,
                output_video=tmp_dir / "out.mp4",
            )
