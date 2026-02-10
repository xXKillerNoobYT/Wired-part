"""Database backup script — creates timestamped SQLite backup."""

import shutil
import sys
from datetime import datetime
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from wired_part.config import Config


def backup_database():
    """Copy the database file to the backup directory with a timestamp."""
    db_path = Config.DATABASE_PATH
    backup_dir = Config.BACKUP_PATH
    backup_dir.mkdir(parents=True, exist_ok=True)

    if not db_path.exists():
        print(f"Database not found at {db_path}")
        return

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = backup_dir / f"wired_part_{timestamp}.db"
    shutil.copy2(db_path, backup_file)
    print(f"Backup created: {backup_file}")

    # Keep only last 10 backups
    backups = sorted(backup_dir.glob("wired_part_*.db"), reverse=True)
    for old in backups[10:]:
        old.unlink()
        print(f"Removed old backup: {old.name}")


if __name__ == "__main__":
    backup_database()
