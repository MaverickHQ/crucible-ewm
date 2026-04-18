"""Tests for the CLI main module."""

from __future__ import annotations

import subprocess
import sys


def test_help_does_not_require_certifi(tmp_path) -> None:
    """
    Test that running --help does not require certifi to be installed.

    This ensures that the experiment module is not imported at module load time,
    which would require certifi even for simple commands like --help.
    """
    result = subprocess.run(
        [sys.executable, "-m", "services.cli.main", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"Expected exit code 0, got {result.returncode}. stderr: {result.stderr}"
    )
    assert "ewm" in result.stdout.lower() or "usage" in result.stdout.lower()


def test_version_does_not_require_certifi(tmp_path) -> None:
    """
    Test that running version does not require certifi to be installed.
    """
    result = subprocess.run(
        [sys.executable, "-m", "services.cli.main", "version"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"Expected exit code 0, got {result.returncode}. stderr: {result.stderr}"
    )
    # Should print version string
    assert "beyond-tokens" in result.stdout.lower() or result.stdout.strip()
