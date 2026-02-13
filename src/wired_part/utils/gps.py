"""Cross-platform GPS location detection.

Provides a unified interface for fetching device GPS coordinates
across Windows, macOS, and Linux. Falls back to manual entry when
automatic detection is unavailable.

Platform support:
- Windows: System.Device.Location via PowerShell
- macOS: CoreLocation via pyobjc (optional) or manual fallback
- Linux: GeoClue2 via D-Bus (optional) or manual fallback
"""

import re
import subprocess
import sys


def get_platform() -> str:
    """Return a normalized platform identifier.

    Returns one of: 'windows', 'macos', 'linux', 'unknown'
    """
    if sys.platform == "win32":
        return "windows"
    elif sys.platform == "darwin":
        return "macos"
    elif sys.platform.startswith("linux"):
        return "linux"
    return "unknown"


def is_gps_available() -> bool:
    """Check whether automatic GPS detection is supported on this platform."""
    platform = get_platform()
    if platform == "windows":
        return True  # PowerShell + System.Device always available
    if platform == "macos":
        return _macos_corelocation_available()
    if platform == "linux":
        return _linux_geoclue_available()
    return False


def get_gps_instructions() -> str:
    """Return platform-specific instructions for enabling GPS."""
    platform = get_platform()
    if platform == "windows":
        return (
            "Enable Location Services in "
            "Windows Settings > Privacy & Security > Location."
        )
    if platform == "macos":
        return (
            "Enable Location Services in "
            "System Settings > Privacy & Security > Location Services."
        )
    if platform == "linux":
        return (
            "Install geoclue2 and ensure location services are enabled. "
            "On most distros: sudo apt install geoclue-2.0"
        )
    return "GPS auto-detection is not available on this platform."


def fetch_gps() -> tuple[float, float]:
    """Attempt to fetch GPS coordinates from the device.

    Returns:
        Tuple of (latitude, longitude).

    Raises:
        GPSUnavailableError: If GPS detection fails or is unsupported.
        GPSTimeoutError: If GPS detection times out.
    """
    platform = get_platform()
    if platform == "windows":
        return _fetch_gps_windows()
    if platform == "macos":
        return _fetch_gps_macos()
    if platform == "linux":
        return _fetch_gps_linux()
    raise GPSUnavailableError(
        "GPS auto-detection is not supported on this platform. "
        "Please enter coordinates manually."
    )


class GPSError(Exception):
    """Base exception for GPS errors."""


class GPSUnavailableError(GPSError):
    """GPS hardware or service is not available."""


class GPSTimeoutError(GPSError):
    """GPS detection timed out."""


# ── Windows ────────────────────────────────────────────────────

def _fetch_gps_windows() -> tuple[float, float]:
    """Fetch GPS via Windows Location API (PowerShell)."""
    ps_script = (
        "Add-Type -AssemblyName System.Device; "
        "$w = New-Object System.Device.Location.GeoCoordinateWatcher; "
        "$w.Start(); "
        "$timeout = 10; $elapsed = 0; "
        "while ($w.Status -ne 'Ready' -and $elapsed -lt $timeout) "
        "{ Start-Sleep -Milliseconds 500; $elapsed += 0.5 }; "
        "if ($w.Status -eq 'Ready') { "
        "$c = $w.Position.Location; "
        "Write-Output \"$($c.Latitude),$($c.Longitude)\" } "
        "else { Write-Output 'FAILED' }; "
        "$w.Stop()"
    )
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            capture_output=True, text=True, timeout=15,
        )
        # Strip ANSI / VS Code terminal escape sequences
        raw = result.stdout
        output = re.sub(
            r"\x1b\].*?\x07"
            r"|\x1b\[[0-9;]*[A-Za-z]"
            r"|\x1b[^[\]].?",
            "", raw,
        ).strip()
        if output and output != "FAILED" and "," in output:
            parts = output.split(",")
            return float(parts[0]), float(parts[1])
        raise GPSUnavailableError(
            f"Location unavailable. {get_gps_instructions()}"
        )
    except subprocess.TimeoutExpired:
        raise GPSTimeoutError(
            f"Location request timed out. {get_gps_instructions()}"
        )
    except (ValueError, IndexError) as e:
        raise GPSUnavailableError(f"Could not parse GPS output: {e}")


# ── macOS ──────────────────────────────────────────────────────

def _macos_corelocation_available() -> bool:
    """Check if pyobjc CoreLocation is available."""
    try:
        import CoreLocation  # noqa: F401
        return True
    except ImportError:
        return False


def _fetch_gps_macos() -> tuple[float, float]:
    """Fetch GPS via macOS CoreLocation (requires pyobjc)."""
    try:
        import CoreLocation
        import objc  # noqa: F401

        manager = CoreLocation.CLLocationManager.alloc().init()
        manager.startUpdatingLocation()

        # CoreLocation is async — we poll briefly
        import time
        for _ in range(20):  # Up to 10 seconds
            location = manager.location()
            if location is not None:
                coord = location.coordinate()
                manager.stopUpdatingLocation()
                return coord.latitude, coord.longitude
            time.sleep(0.5)

        manager.stopUpdatingLocation()
        raise GPSTimeoutError(
            f"Location request timed out. {get_gps_instructions()}"
        )
    except ImportError:
        raise GPSUnavailableError(
            "CoreLocation not available. Install pyobjc-framework-CoreLocation "
            "for automatic GPS, or enter coordinates manually from Maps."
        )
    except Exception as e:
        raise GPSUnavailableError(
            f"Could not get location: {e}\n"
            "You can enter coordinates manually from Maps."
        )


# ── Linux ──────────────────────────────────────────────────────

def _linux_geoclue_available() -> bool:
    """Check if GeoClue2 D-Bus service is available."""
    try:
        result = subprocess.run(
            ["gdbus", "introspect", "--system",
             "--dest", "org.freedesktop.GeoClue2",
             "--object-path", "/org/freedesktop/GeoClue2/Manager"],
            capture_output=True, text=True, timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _fetch_gps_linux() -> tuple[float, float]:
    """Fetch GPS via GeoClue2 D-Bus API."""
    try:
        # Use the where-am-i tool from geoclue2 if available
        result = subprocess.run(
            ["where-am-i", "-t", "10"],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode == 0:
            lat = lon = None
            for line in result.stdout.splitlines():
                line = line.strip()
                if line.startswith("Latitude:"):
                    lat = float(line.split(":")[1].strip().rstrip("°"))
                elif line.startswith("Longitude:"):
                    lon = float(line.split(":")[1].strip().rstrip("°"))
            if lat is not None and lon is not None:
                return lat, lon

        raise GPSUnavailableError(
            f"GeoClue2 could not determine location. "
            f"{get_gps_instructions()}"
        )
    except FileNotFoundError:
        raise GPSUnavailableError(
            "GeoClue2 'where-am-i' tool not found. "
            "Install geoclue-2.0 for automatic GPS, "
            "or enter coordinates manually from Maps."
        )
    except subprocess.TimeoutExpired:
        raise GPSTimeoutError(
            f"Location request timed out. {get_gps_instructions()}"
        )
    except ValueError as e:
        raise GPSUnavailableError(f"Could not parse GeoClue output: {e}")
