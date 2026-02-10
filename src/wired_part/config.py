"""Application configuration — loads .env and provides settings."""

import os
from pathlib import Path

from dotenv import load_dotenv

# Find the project root (where .env lives)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(_PROJECT_ROOT / ".env")


class Config:
    """Central configuration loaded from environment variables."""

    # Paths
    PROJECT_ROOT: Path = _PROJECT_ROOT
    DATABASE_PATH: Path = Path(
        os.getenv("DATABASE_PATH", str(_PROJECT_ROOT / "data" / "wired_part.db"))
    )
    BACKUP_PATH: Path = Path(
        os.getenv("DATABASE_BACKUP_PATH", str(_PROJECT_ROOT / "data" / "backups"))
    )

    # LM Studio
    LM_STUDIO_BASE_URL: str = os.getenv(
        "LM_STUDIO_BASE_URL", "http://localhost:1234/v1"
    )
    LM_STUDIO_API_KEY: str = os.getenv("LM_STUDIO_API_KEY", "lm-studio")
    LM_STUDIO_MODEL: str = os.getenv("LM_STUDIO_MODEL", "local-model")
    LM_STUDIO_TIMEOUT: int = int(os.getenv("LM_STUDIO_TIMEOUT", "60"))

    # UI
    APP_THEME: str = os.getenv("APP_THEME", "dark")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
