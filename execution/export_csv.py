"""Standalone CSV export script — export parts or jobs from command line."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from wired_part.config import Config
from wired_part.database.connection import DatabaseConnection
from wired_part.database.schema import initialize_database
from wired_part.database.repository import Repository
from wired_part.io.csv_handler import export_parts_csv, export_jobs_csv


def main():
    if len(sys.argv) < 3:
        print("Usage: python export_csv.py <parts|jobs> <output.csv>")
        sys.exit(1)

    data_type = sys.argv[1].lower()
    filepath = sys.argv[2]

    db = DatabaseConnection(Config.DATABASE_PATH)
    initialize_database(db)
    repo = Repository(db)

    if data_type == "parts":
        count = export_parts_csv(repo, filepath)
    elif data_type == "jobs":
        count = export_jobs_csv(repo, filepath)
    else:
        print(f"Unknown data type: {data_type}. Use 'parts' or 'jobs'.")
        sys.exit(1)

    print(f"Exported {count} {data_type} to {filepath}")


if __name__ == "__main__":
    main()
