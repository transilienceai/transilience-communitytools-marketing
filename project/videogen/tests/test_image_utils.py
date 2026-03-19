"""Tests for src/core/image_utils.py"""

import base64
import pytest
from pathlib import Path

try:
    from src.core.image_utils import (
        image_to_base64,
        get_mime_type,
        get_image_media_type,
        resize_image_for_api,
        get_image_dimensions,
    )
except ImportError:
    pytest.skip("PIL not installed", allow_module_level=True)


class TestImageToBase64:
    def test_returns_valid_base64(self, sample_image):
        b64 = image_to_base64(sample_image)
        assert isinstance(b64, str)
        # Should be decodable
        decoded = base64.b64decode(b64)
        assert len(decoded) > 0

    def test_nonexistent_raises(self, tmp_dir):
        with pytest.raises(FileNotFoundError):
            image_to_base64(tmp_dir / "nope.png")


class TestGetMimeType:
    @pytest.mark.parametrize("ext,expected", [
        (".png", "image/png"),
        (".jpg", "image/jpeg"),
        (".jpeg", "image/jpeg"),
        (".webp", "image/webp"),
        (".gif", "image/gif"),
        (".bmp", "image/bmp"),
        (".xyz", "image/png"),  # Unknown defaults to png
    ])
    def test_mime_types(self, ext, expected):
        assert get_mime_type(Path(f"test{ext}")) == expected

    def test_legacy_alias(self):
        assert get_image_media_type(Path("test.jpg")) == "image/jpeg"


class TestResizeImageForApi:
    def test_returns_tuple(self, sample_image):
        b64, mime = resize_image_for_api(sample_image)
        assert isinstance(b64, str)
        assert mime in ("image/png", "image/jpeg")

    def test_small_image_not_resized(self, sample_image):
        b64, _ = resize_image_for_api(sample_image, max_size=1568)
        original_b64 = image_to_base64(sample_image)
        assert b64 == original_b64


class TestGetImageDimensions:
    def test_returns_dimensions(self, sample_image):
        w, h = get_image_dimensions(sample_image)
        assert w == 10
        assert h == 10
