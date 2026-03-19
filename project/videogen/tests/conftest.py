"""Shared fixtures for all tests."""

import os
import sys
import types
import tempfile
import subprocess
from pathlib import Path

import pytest

# Ensure project root is on path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Stub out src and src.core __init__ to prevent eager imports that need PIL/moviepy.
# Tests import specific submodules directly (e.g. src.core.video_utils).
for mod_name in ["src", "src.core", "src.ai", "src.pipeline", "src.processing", "src.generators"]:
    if mod_name not in sys.modules:
        m = types.ModuleType(mod_name)
        m.__path__ = [str(PROJECT_ROOT / mod_name.replace(".", "/"))]
        m.__package__ = mod_name
        sys.modules[mod_name] = m


@pytest.fixture
def tmp_dir():
    """Provide a temporary directory, cleaned up after test."""
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


@pytest.fixture
def sample_image(tmp_dir):
    """Create a small test PNG image."""
    img_path = tmp_dir / "test_image.png"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=red:s=10x10:d=1",
         "-frames:v", "1", str(img_path)],
        capture_output=True, timeout=10,
    )
    if img_path.exists():
        return img_path
    pytest.skip("ffmpeg not available")


@pytest.fixture
def sample_video(tmp_dir):
    """Create a 2-second test video with audio."""
    vid_path = tmp_dir / "test_video.mp4"
    subprocess.run(
        ["ffmpeg", "-y",
         "-f", "lavfi", "-i", "color=c=blue:s=320x240:d=2:r=30",
         "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
         "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
         "-c:a", "aac", "-b:a", "64k",
         "-shortest", str(vid_path)],
        capture_output=True, timeout=15,
    )
    if vid_path.exists():
        return vid_path
    pytest.skip("ffmpeg not available")


@pytest.fixture
def sample_video_no_audio(tmp_dir):
    """Create a 2-second test video without audio."""
    vid_path = tmp_dir / "test_silent.mp4"
    subprocess.run(
        ["ffmpeg", "-y",
         "-f", "lavfi", "-i", "color=c=green:s=320x240:d=2:r=30",
         "-c:v", "libx264", "-preset", "ultrafast", "-an",
         str(vid_path)],
        capture_output=True, timeout=15,
    )
    if vid_path.exists():
        return vid_path
    pytest.skip("ffmpeg not available")


@pytest.fixture
def sample_audio(tmp_dir):
    """Create a 2-second test audio file."""
    audio_path = tmp_dir / "test_audio.mp3"
    subprocess.run(
        ["ffmpeg", "-y",
         "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
         "-c:a", "libmp3lame", "-b:a", "64k",
         str(audio_path)],
        capture_output=True, timeout=10,
    )
    if audio_path.exists():
        return audio_path
    pytest.skip("ffmpeg not available")


@pytest.fixture
def mock_env(monkeypatch):
    """Set dummy API keys so modules don't fail on import."""
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test-key")
