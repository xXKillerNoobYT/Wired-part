"""Standalone CSV import script — import parts from command line."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from wired_part.config import Config
from wired_part.database.connection import DatabaseConnection
from wired_part.database.schema import initialize_database
from wired_part.database.repository import Repository
from wired_part.io.csv_handler import import_parts_csv


def main():
    if len(sys.argv) < 2:
        print("Usage: python import_csv.py <filepath.csv> [--update]")
        sys.exit(1)

    filepath = sys.argv[1]
    update = "--update" in sys.argv

    db = DatabaseConnection(Config.DATABASE_PATH)
    initialize_database(db)
    repo = Repository(db)

    print(f"Importing from: {filepath}")
    if update:
        print("Mode: Update existing parts")

    results = import_parts_csv(repo, filepath, update_existing=update)

    print(f"\nResults:")
    print(f"  Imported: {results['imported']}")
    print(f"  Updated:  {results['updated']}")
    print(f"  Skipped:  {results['skipped']}")

    if results["errors"]:
        print(f"\nErrors ({len(results['errors'])}):")
        for err in results["errors"]:
            print(f"  - {err}")


if __name__ == "__main__":
    main()
