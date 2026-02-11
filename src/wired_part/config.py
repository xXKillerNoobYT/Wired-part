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

    # Labor settings (settings.json overrides defaults)
    GEOFENCE_RADIUS: float = float(_runtime.get(
        "geofence_radius",
        os.getenv("GEOFENCE_RADIUS", "0.5"),
    ))
    PHOTOS_DIRECTORY: str = _runtime.get(
        "photos_directory",
        os.getenv("PHOTOS_DIRECTORY", str(_PROJECT_ROOT / "data" / "photos")),
    )
    OVERTIME_THRESHOLD: float = float(_runtime.get(
        "overtime_threshold",
        os.getenv("OVERTIME_THRESHOLD", "8.0"),
    ))

    # Orders & Returns
    ORDER_NUMBER_PREFIX: str = _runtime.get(
        "order_number_prefix",
        os.getenv("ORDER_NUMBER_PREFIX", "PO"),
    )
    RA_NUMBER_PREFIX: str = _runtime.get(
        "ra_number_prefix",
        os.getenv("RA_NUMBER_PREFIX", "RA"),
    )
    AUTO_CLOSE_RECEIVED_ORDERS: bool = _runtime.get(
        "auto_close_received_orders", True
    )

    # Parts Catalog
    PDFS_DIRECTORY: str = _runtime.get(
        "pdfs_directory",
        os.getenv("PDFS_DIRECTORY", str(_PROJECT_ROOT / "data" / "pdfs")),
    )
    LOCAL_PN_PREFIX: str = _runtime.get(
        "local_pn_prefix",
        os.getenv("LOCAL_PN_PREFIX", "LP"),
    )

    # Billing
    DEFAULT_BILLING_CYCLE: str = _runtime.get(
        "default_billing_cycle",
        os.getenv("DEFAULT_BILLING_CYCLE", "monthly"),
    )
    DEFAULT_BILLING_DAY: int = int(_runtime.get(
        "default_billing_day",
        os.getenv("DEFAULT_BILLING_DAY", "1"),
    ))

    # Notebook template (settings.json overrides default sections)
    NOTEBOOK_SECTIONS_TEMPLATE: list = _runtime.get(
        "notebook_sections_template",
        None,  # None = use DEFAULT_NOTEBOOK_SECTIONS from constants
    )

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

    # Background agent intervals (minutes) — persisted in settings.json
    AUDIT_AGENT_INTERVAL: int = int(_runtime.get(
        "audit_agent_interval", "30"
    ))
    ADMIN_AGENT_INTERVAL: int = int(_runtime.get(
        "admin_agent_interval", "60"
    ))
    REMINDER_AGENT_INTERVAL: int = int(_runtime.get(
        "reminder_agent_interval", "15"
    ))

    @classmethod
    def update_theme(cls, theme: str):
        """Update theme at runtime and persist to disk."""
        cls.APP_THEME = theme
        settings = _load_settings()
        settings["app_theme"] = theme
        _save_settings(settings)

    @classmethod
    def update_agent_intervals(cls, audit: int, admin: int, reminder: int):
        """Update background agent intervals (in minutes) and persist."""
        cls.AUDIT_AGENT_INTERVAL = audit
        cls.ADMIN_AGENT_INTERVAL = admin
        cls.REMINDER_AGENT_INTERVAL = reminder

        settings = _load_settings()
        settings["audit_agent_interval"] = audit
        settings["admin_agent_interval"] = admin
        settings["reminder_agent_interval"] = reminder
        _save_settings(settings)

    @classmethod
    def update_labor_settings(cls, radius: float,
                              photos_dir: str, overtime: float):
        """Update labor-related settings and persist."""
        cls.GEOFENCE_RADIUS = radius
        cls.PHOTOS_DIRECTORY = photos_dir
        cls.OVERTIME_THRESHOLD = overtime

        settings = _load_settings()
        settings["geofence_radius"] = radius
        settings["photos_directory"] = photos_dir
        settings["overtime_threshold"] = overtime
        _save_settings(settings)

    @classmethod
    def update_billing_settings(cls, cycle: str, day: int):
        """Update billing cycle defaults and persist."""
        cls.DEFAULT_BILLING_CYCLE = cycle
        cls.DEFAULT_BILLING_DAY = day

        settings = _load_settings()
        settings["default_billing_cycle"] = cycle
        settings["default_billing_day"] = day
        _save_settings(settings)

    @classmethod
    def update_notebook_template(cls, sections: list[str]):
        """Update the default notebook sections template and persist."""
        cls.NOTEBOOK_SECTIONS_TEMPLATE = sections

        settings = _load_settings()
        settings["notebook_sections_template"] = sections
        _save_settings(settings)

    @classmethod
    def get_notebook_sections(cls) -> list[str]:
        """Get the notebook sections to use for new jobs.

        Returns the custom template if set, otherwise falls back
        to DEFAULT_NOTEBOOK_SECTIONS from constants.
        """
        if cls.NOTEBOOK_SECTIONS_TEMPLATE:
            return list(cls.NOTEBOOK_SECTIONS_TEMPLATE)
        from wired_part.utils.constants import DEFAULT_NOTEBOOK_SECTIONS
        return list(DEFAULT_NOTEBOOK_SECTIONS)
