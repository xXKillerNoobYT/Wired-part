"""Tests for the cross-platform GPS module."""

import sys
from unittest.mock import MagicMock, patch

import pytest

from wired_part.utils.gps import (
    GPSError,
    GPSTimeoutError,
    GPSUnavailableError,
    fetch_gps,
    get_gps_instructions,
    get_platform,
    is_gps_available,
)


class TestGetPlatform:
    def test_windows(self):
        with patch.object(sys, "platform", "win32"):
            assert get_platform() == "windows"

    def test_macos(self):
        with patch.object(sys, "platform", "darwin"):
            assert get_platform() == "macos"

    def test_linux(self):
        with patch.object(sys, "platform", "linux"):
            assert get_platform() == "linux"

    def test_unknown(self):
        with patch.object(sys, "platform", "freebsd12"):
            assert get_platform() == "unknown"


class TestIsGpsAvailable:
    def test_windows_always_available(self):
        with patch("wired_part.utils.gps.get_platform", return_value="windows"):
            assert is_gps_available() is True

    def test_unknown_platform_not_available(self):
        with patch("wired_part.utils.gps.get_platform", return_value="unknown"):
            assert is_gps_available() is False

    def test_macos_without_corelocation(self):
        with patch("wired_part.utils.gps.get_platform", return_value="macos"):
            with patch(
                "wired_part.utils.gps._macos_corelocation_available",
                return_value=False,
            ):
                assert is_gps_available() is False

    def test_macos_with_corelocation(self):
        with patch("wired_part.utils.gps.get_platform", return_value="macos"):
            with patch(
                "wired_part.utils.gps._macos_corelocation_available",
                return_value=True,
            ):
                assert is_gps_available() is True


class TestGetGpsInstructions:
    def test_windows_mentions_settings(self):
        with patch("wired_part.utils.gps.get_platform", return_value="windows"):
            instructions = get_gps_instructions()
            assert "Windows Settings" in instructions

    def test_macos_mentions_system_settings(self):
        with patch("wired_part.utils.gps.get_platform", return_value="macos"):
            instructions = get_gps_instructions()
            assert "System Settings" in instructions

    def test_linux_mentions_geoclue(self):
        with patch("wired_part.utils.gps.get_platform", return_value="linux"):
            instructions = get_gps_instructions()
            assert "geoclue" in instructions

    def test_unknown_platform(self):
        with patch("wired_part.utils.gps.get_platform", return_value="unknown"):
            instructions = get_gps_instructions()
            assert "not available" in instructions


class TestFetchGpsWindows:
    @patch("wired_part.utils.gps.get_platform", return_value="windows")
    @patch("subprocess.run")
    def test_successful_fetch(self, mock_run, _):
        mock_run.return_value = MagicMock(
            stdout="40.712800,-74.006000\n", returncode=0
        )
        lat, lon = fetch_gps()
        assert abs(lat - 40.7128) < 0.0001
        assert abs(lon - (-74.006)) < 0.0001

    @patch("wired_part.utils.gps.get_platform", return_value="windows")
    @patch("subprocess.run")
    def test_strips_ansi_codes(self, mock_run, _):
        # Simulate VS Code terminal escape sequences in output
        mock_run.return_value = MagicMock(
            stdout="\x1b]633;some_code\x0740.7128,-74.0060\n",
            returncode=0,
        )
        lat, lon = fetch_gps()
        assert abs(lat - 40.7128) < 0.0001

    @patch("wired_part.utils.gps.get_platform", return_value="windows")
    @patch("subprocess.run")
    def test_failed_returns_error(self, mock_run, _):
        mock_run.return_value = MagicMock(
            stdout="FAILED\n", returncode=0
        )
        with pytest.raises(GPSUnavailableError):
            fetch_gps()

    @patch("wired_part.utils.gps.get_platform", return_value="windows")
    @patch("subprocess.run")
    def test_timeout_raises_error(self, mock_run, _):
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired(
            cmd="powershell", timeout=15
        )
        with pytest.raises(GPSTimeoutError):
            fetch_gps()


class TestFetchGpsUnsupportedPlatform:
    @patch("wired_part.utils.gps.get_platform", return_value="unknown")
    def test_unsupported_raises_error(self, _):
        with pytest.raises(GPSUnavailableError, match="not supported"):
            fetch_gps()


class TestGpsExceptionHierarchy:
    def test_gps_unavailable_is_gps_error(self):
        assert issubclass(GPSUnavailableError, GPSError)

    def test_gps_timeout_is_gps_error(self):
        assert issubclass(GPSTimeoutError, GPSError)

    def test_gps_error_is_exception(self):
        assert issubclass(GPSError, Exception)
