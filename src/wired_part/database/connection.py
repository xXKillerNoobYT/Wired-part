"""SQLite connection management with context manager."""

import sqlite3
from contextlib import contextmanager
from pathlib import Path


class DatabaseConnection:
    """Manages SQLite connections with foreign key enforcement."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def get_connection(self):
        """Yield a connection that auto-commits or rolls back."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def execute(self, sql: str, params: tuple = ()):
        """Run a single statement and return the cursor."""
        with self.get_connection() as conn:
            cursor = conn.execute(sql, params)
            return cursor.fetchall()

    def execute_script(self, sql_script: str):
        """Run a multi-statement SQL script."""
        with self.get_connection() as conn:
            conn.executescript(sql_script)
