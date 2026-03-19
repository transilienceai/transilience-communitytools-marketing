"""Tests for src/pipeline/screenshot_handler.py"""

import pytest
from pathlib import Path

try:
    from src.pipeline.screenshot_handler import (
        IMAGE_EXTENSIONS,
        VIDEO_EXTENSIONS,
        PPTX_EXTENSIONS,
        ALL_EXTENSIONS,
        get_image_files,
        validate_images,
        MediaFile,
        MediaType,
    )
except ImportError:
    pytest.skip("PIL not installed", allow_module_level=True)


class TestConstants:
    def test_image_extensions(self):
        assert ".png" in IMAGE_EXTENSIONS
        assert ".jpg" in IMAGE_EXTENSIONS
        assert ".jpeg" in IMAGE_EXTENSIONS
        assert ".webp" in IMAGE_EXTENSIONS

    def test_video_extensions(self):
        assert ".mp4" in VIDEO_EXTENSIONS
        assert ".mov" in VIDEO_EXTENSIONS
        assert ".webm" in VIDEO_EXTENSIONS

    def test_pptx_extensions(self):
        assert ".pptx" in PPTX_EXTENSIONS

    def test_all_extensions_includes_all(self):
        for ext in IMAGE_EXTENSIONS:
            assert ext in ALL_EXTENSIONS
        for ext in VIDEO_EXTENSIONS:
            assert ext in ALL_EXTENSIONS


class TestMediaFile:
    def test_create_image_mediafile(self, sample_image):
        mf = MediaFile(path=sample_image, media_type=MediaType.IMAGE)
        assert mf.path == sample_image
        assert mf.media_type == MediaType.IMAGE

    def test_create_video_mediafile(self, sample_video):
        mf = MediaFile(path=sample_video, media_type=MediaType.VIDEO)
        assert mf.media_type == MediaType.VIDEO


class TestGetImageFiles:
    def test_finds_images(self, tmp_dir, sample_image):
        # Copy sample to tmp_dir with known name
        import shutil
        dest = tmp_dir / "photo.png"
        shutil.copy(sample_image, dest)
        files = get_image_files(str(tmp_dir))
        assert len(files) >= 1
        assert any(f.name == "photo.png" for f in files)

    def test_empty_dir(self, tmp_dir):
        files = get_image_files(str(tmp_dir))
        assert len(files) == 0

    def test_ignores_non_images(self, tmp_dir):
        (tmp_dir / "readme.txt").write_text("hello")
        files = get_image_files(str(tmp_dir))
        assert len(files) == 0


class TestValidateImages:
    def test_valid_images(self, sample_image):
        assert validate_images([sample_image]) is True

    def test_empty_list(self):
        assert validate_images([]) is False

    def test_nonexistent_files(self, tmp_dir):
        assert validate_images([tmp_dir / "nope.png"]) is False
