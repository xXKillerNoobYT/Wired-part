# Cross-Platform Support

Wired-Part is designed to run on Windows, macOS, and Linux with a consistent experience. This document covers platform-specific details.

## GPS Location Detection

GPS auto-detection uses platform-native APIs via `src/wired_part/utils/gps.py`:

| Platform | Method | Dependency | Fallback |
|----------|--------|------------|----------|
| Windows | PowerShell + System.Device.Location | Built-in | Manual entry |
| macOS | CoreLocation framework | pyobjc-framework-CoreLocation (optional) | Manual entry |
| Linux | GeoClue2 via `where-am-i` CLI | geoclue-2.0 package (optional) | Manual entry |

### Installing optional GPS dependencies

**macOS:**
```bash
pip install pyobjc-framework-CoreLocation
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt install geoclue-2.0
```

### Manual GPS Entry
All platforms support manual coordinate entry. Users can paste coordinates from Google Maps or any mapping app. The GPS auto-detect button shows platform-specific instructions when detection fails.

## Fonts

The application uses platform-native system fonts for optimal readability:

| Platform | Primary Font | Fallbacks |
|----------|-------------|-----------|
| Windows | Segoe UI | Tahoma, Arial |
| macOS | .AppleSystemUIFont | Helvetica Neue, Helvetica |
| Linux | Ubuntu | Noto Sans, Liberation Sans, DejaVu Sans |

Font selection is handled by `src/wired_part/utils/platform.py`. The QSS stylesheet uses a `{{FONT_FAMILY}}` placeholder that gets replaced at runtime with the correct font stack.

## DPI Scaling

- Dialogs use `setMinimumSize()` instead of `setFixedSize()` to allow scaling on high-DPI displays
- QSS uses `pt` (points) for font sizes, which scale with system DPI settings
- Widget-level fixed sizes (avatars, color previews) remain fixed since they represent specific visual elements

## Path Handling

All file paths use `pathlib.Path` for cross-platform compatibility. No Windows-specific path separators (`\\`) are used in the codebase.

## Future: Mobile Support

Mobile devices (iPhone, iPad) will be supported through a separate application that syncs via the cloud sync system (Phase 3). The desktop app uses PySide6 which is desktop-only; mobile will require a separate framework.
