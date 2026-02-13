"""Cross-platform utilities for font selection, DPI scaling, and
platform detection.
"""

import sys

# Cross-platform font stack — each platform uses its native system font
# with appropriate fallbacks.
FONT_FAMILIES = {
    "win32": ("Segoe UI", "Tahoma", "Arial", "sans-serif"),
    "darwin": (".AppleSystemUIFont", "Helvetica Neue", "Helvetica",
               "sans-serif"),
    "linux": ("Ubuntu", "Noto Sans", "Liberation Sans",
              "DejaVu Sans", "sans-serif"),
}


def get_font_family() -> str:
    """Return a CSS-safe font-family string for the current platform."""
    for key, fonts in FONT_FAMILIES.items():
        if sys.platform.startswith(key):
            return ", ".join(f'"{f}"' if " " in f else f
                             for f in fonts)
    # Fallback for unknown platforms
    return '"sans-serif"'


def get_primary_font_name() -> str:
    """Return the preferred font name for QFont on this platform."""
    for key, fonts in FONT_FAMILIES.items():
        if sys.platform.startswith(key):
            return fonts[0]
    return "sans-serif"


def get_platform() -> str:
    """Return a normalized platform identifier."""
    if sys.platform == "win32":
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    if sys.platform.startswith("linux"):
        return "linux"
    return "unknown"
