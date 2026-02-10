"""Application configuration — loads .env, then overrides from settings.json."""

import json
import os
from pathlib import Path

from dotenv import load_dotenv

# Find the project root (where .env lives)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(_PROJECT_ROOT / ".env")

# Runtime settings file for in-app configuration
_SETTINGS_FILE = _PROJECT_ROOT / "data" / "settings.json"


def _load_settings() -> dict:
    """Load saved runtime settings from JSON file."""
    if _SETTINGS_FILE.exists():
        try:
            return json.loads(_SETTINGS_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save_settings(settings: dict):
    """Persist runtime settings to JSON file."""
    _SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _SETTINGS_FILE.write_text(
        json.dumps(settings, indent=2), encoding="utf-8"
    )


# Load saved settings once at import time
_runtime = _load_settings()


class Config:
    """Central configuration: .env defaults, settings.json overrides."""

    # Paths
    PROJECT_ROOT: Path = _PROJECT_ROOT
    DATABASE_PATH: Path = Path(
        os.getenv("DATABASE_PATH", str(_PROJECT_ROOT / "data" / "wired_part.db"))
    )
    BACKUP_PATH: Path = Path(
        os.getenv("DATABASE_BACKUP_PATH", str(_PROJECT_ROOT / "data" / "backups"))
    )

    # LM Studio (settings.json overrides .env)
    LM_STUDIO_BASE_URL: str = _runtime.get(
        "lm_studio_base_url",
        os.getenv("LM_STUDIO_BASE_URL", "http://localhost:1234/v1"),
    )
    LM_STUDIO_API_KEY: str = _runtime.get(
        "lm_studio_api_key",
        os.getenv("LM_STUDIO_API_KEY", "lm-studio"),
    )
    LM_STUDIO_MODEL: str = _runtime.get(
        "lm_studio_model",
        os.getenv("LM_STUDIO_MODEL", "local-model"),
    )
    LM_STUDIO_TIMEOUT: int = int(_runtime.get(
        "lm_studio_timeout",
        os.getenv("LM_STUDIO_TIMEOUT", "60"),
    ))

    # UI
    APP_THEME: str = _runtime.get(
        "app_theme",
        os.getenv("APP_THEME", "dark"),
    )
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    @classmethod
    def update_llm_settings(cls, base_url: str, api_key: str,
                            model: str, timeout: int):
        """Update LLM settings at runtime and persist to disk."""
        cls.LM_STUDIO_BASE_URL = base_url
        cls.LM_STUDIO_API_KEY = api_key
        cls.LM_STUDIO_MODEL = model
        cls.LM_STUDIO_TIMEOUT = timeout

        settings = _load_settings()
        settings["lm_studio_base_url"] = base_url
        settings["lm_studio_api_key"] = api_key
        settings["lm_studio_model"] = model
        settings["lm_studio_timeout"] = timeout
        _save_settings(settings)

    @classmethod
    def update_theme(cls, theme: str):
        """Update theme at runtime and persist to disk."""
        cls.APP_THEME = theme
        settings = _load_settings()
        settings["app_theme"] = theme
        _save_settings(settings)
