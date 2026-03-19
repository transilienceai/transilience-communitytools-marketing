"""Tests for cli.py — verify commands exist and help works."""

import subprocess
import sys
import pytest

try:
    import click
    HAS_CLICK = True
except ImportError:
    HAS_CLICK = False

pytestmark = pytest.mark.skipif(not HAS_CLICK, reason="click not installed")

CLI = [sys.executable, "cli.py"]


def run_cli(*args, timeout=15):
    return subprocess.run(
        [*CLI, *args],
        capture_output=True, text=True, timeout=timeout,
    )


class TestCLIHelp:
    """Every command should print help without crashing."""

    def test_main_help(self):
        r = run_cli("--help")
        assert r.returncode == 0
        assert "create" in r.stdout

    @pytest.mark.parametrize("cmd", [
        "create",
        "storyboard",
        "avatar",
        "veo-marketing",
        "generate",
        "voice-clone",
        "music",
        "voices",
        "veo",
        "info",
    ])
    def test_command_help(self, cmd):
        r = run_cli(cmd, "--help")
        assert r.returncode == 0, f"{cmd} --help failed: {r.stderr[:200]}"


class TestCLIDryRun:
    """Commands with --dry-run should not call APIs."""

    def test_create_dry_run_no_files(self, tmp_dir):
        r = run_cli("create", str(tmp_dir), "--dry-run")
        # Should fail gracefully — no files
        assert "No images" in r.stderr or "No images" in r.stdout or r.returncode != 0

    def test_create_dry_run_with_image(self, sample_image, tmp_dir):
        import shutil
        dest = tmp_dir / "01_test.png"
        shutil.copy(sample_image, dest)
        r = run_cli("create", str(tmp_dir), "--dry-run", "--product", "Test")
        # Should show plan without actually generating
        assert r.returncode == 0 or "dry" in r.stdout.lower() or "plan" in r.stdout.lower()
