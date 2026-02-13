"""Tests for the cross-platform utility module."""

import sys
from unittest.mock import patch

import pytest

from wired_part.utils.platform import (
    FONT_FAMILIES,
    get_font_family,
    get_platform,
    get_primary_font_name,
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

    def test_linux_variant(self):
        with patch.object(sys, "platform", "linux2"):
            assert get_platform() == "linux"

    def test_unknown(self):
        with patch.object(sys, "platform", "freebsd13"):
            assert get_platform() == "unknown"


class TestGetPrimaryFontName:
    def test_windows_segoe(self):
        with patch.object(sys, "platform", "win32"):
            assert get_primary_font_name() == "Segoe UI"

    def test_macos_system_font(self):
        with patch.object(sys, "platform", "darwin"):
            assert get_primary_font_name() == ".AppleSystemUIFont"

    def test_linux_ubuntu(self):
        with patch.object(sys, "platform", "linux"):
            assert get_primary_font_name() == "Ubuntu"

    def test_unknown_fallback(self):
        with patch.object(sys, "platform", "freebsd13"):
            assert get_primary_font_name() == "sans-serif"


class TestGetFontFamily:
    def test_windows_has_segoe(self):
        with patch.object(sys, "platform", "win32"):
            family = get_font_family()
            assert "Segoe UI" in family
            assert "sans-serif" in family

    def test_macos_has_apple_font(self):
        with patch.object(sys, "platform", "darwin"):
            family = get_font_family()
            assert "AppleSystemUIFont" in family
            assert "Helvetica" in family

    def test_linux_has_ubuntu(self):
        with patch.object(sys, "platform", "linux"):
            family = get_font_family()
            assert "Ubuntu" in family
            assert "Noto Sans" in family

    def test_returns_comma_separated(self):
        with patch.object(sys, "platform", "win32"):
            family = get_font_family()
            assert "," in family

    def test_unknown_returns_sans_serif(self):
        with patch.object(sys, "platform", "freebsd13"):
            family = get_font_family()
            assert "sans-serif" in family


class TestFontFamiliesDict:
    def test_has_all_platforms(self):
        assert "win32" in FONT_FAMILIES
        assert "darwin" in FONT_FAMILIES
        assert "linux" in FONT_FAMILIES

    def test_each_has_fallback(self):
        for platform, fonts in FONT_FAMILIES.items():
            assert fonts[-1] == "sans-serif", (
                f"{platform} font stack missing sans-serif fallback"
            )
