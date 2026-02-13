"""SyncManager — file-based database synchronization.

Each device maintains its own local SQLite database. Sync works by:
1. Exporting changed rows to a JSON file in the sync folder
2. Importing JSON files from other devices
3. Merging using last-write-wins per table row (by updated_at)

Sync folder layout:
    <sync_folder>/
        wiredpart_sync_<device_id>.json   — each device's export
        wiredpart_lock                     — lock file to prevent races
"""

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from wired_part.config import Config


# Tables included in sync (order matters for FK constraints)
SYNC_TABLES = [
    "categories",
    "suppliers",
    "users",
    "hats",
    "hat_permissions",
    "user_hats",
    "parts",
    "part_suppliers",
    "brands",
    "part_variants",
    "parts_lists",
    "parts_list_items",
    "trucks",
    "jobs",
    "job_assignments",
    "bro_categories",
    "billing_cycles",
    "purchase_orders",
    "purchase_order_items",
    "receive_log",
    "truck_transfers",
    "truck_inventory",
    "labor_entries",
    "consumption_log",
    "job_parts",
    "return_authorizations",
    "return_items",
    "notebook_sections",
    "notebook_pages",
    "notebook_attachments",
    "job_updates",
    "activity_log",
    "notifications",
]

# Tables that use updated_at for merge resolution
TABLES_WITH_UPDATED_AT = {
    "parts", "jobs", "users", "trucks", "suppliers", "categories",
    "purchase_orders", "purchase_order_items", "labor_entries",
    "notebook_pages",
}


class SyncError(Exception):
    """Base exception for sync operations."""


class SyncLockError(SyncError):
    """Another device is currently syncing."""


class SyncManager:
    """Manages file-based database synchronization."""

    LOCK_FILE = "wiredpart_lock"
    LOCK_TIMEOUT_SECONDS = 300  # 5 minute stale lock threshold
    EXPORT_PREFIX = "wiredpart_sync_"

    def __init__(self, db_connection):
        self.db = db_connection
        self.device_id = Config.get_device_id()
        self.sync_folder = Path(Config.SYNC_FOLDER_PATH) if Config.SYNC_FOLDER_PATH else None
        self._sync_enabled = Config.SYNC_ENABLED
        self._last_sync = Config.LAST_SYNC_TIMESTAMP
        self._interval_minutes = getattr(Config, "SYNC_INTERVAL_MINUTES", 60)

    @property
    def is_configured(self) -> bool:
        """Check if sync is enabled and properly configured."""
        return (
            self._sync_enabled
            and self.sync_folder is not None
            and self.sync_folder.exists()
        )

    def export_to_sync_folder(self) -> str:
        """Export local database to a JSON file in the sync folder.

        Returns the path to the exported file.
        """
        if not self.is_configured:
            raise SyncError("Sync is not configured. Set a sync folder in Settings.")

        self._acquire_lock()
        try:
            export_data = self._build_export()
            filename = f"{self.EXPORT_PREFIX}{self.device_id}.json"
            filepath = self.sync_folder / filename
            filepath.write_text(
                json.dumps(export_data, indent=2, default=str),
                encoding="utf-8",
            )
            # Update last sync timestamp
            now = datetime.now(timezone.utc).isoformat()
            self._last_sync = now
            Config.update_last_sync(now)
            return str(filepath)
        finally:
            self._release_lock()

    def import_from_sync_folder(self) -> dict:
        """Import and merge data from other devices' sync files.

        Returns a summary dict with counts of merged records per table.
        """
        if not self.is_configured:
            raise SyncError("Sync is not configured.")

        self._acquire_lock()
        try:
            summary = {}
            # Find all sync files from OTHER devices
            for filepath in self.sync_folder.glob(f"{self.EXPORT_PREFIX}*.json"):
                other_device_id = filepath.stem.replace(self.EXPORT_PREFIX, "")
                if other_device_id == self.device_id:
                    continue  # Skip our own export

                try:
                    data = json.loads(filepath.read_text(encoding="utf-8"))
                    device_summary = self._merge_import(data)
                    for table, count in device_summary.items():
                        summary[table] = summary.get(table, 0) + count
                except (json.JSONDecodeError, KeyError, OSError):
                    continue  # Skip corrupt files

            now = datetime.now(timezone.utc).isoformat()
            self._last_sync = now
            Config.update_last_sync(now)
            return summary
        finally:
            self._release_lock()

    def sync(self) -> dict:
        """Full sync: export local data, then import from others.

        Returns summary of merged records.
        """
        self.export_to_sync_folder()
        return self.import_from_sync_folder()

    def get_sync_status(self) -> dict:
        """Get current sync status information."""
        other_files = []
        if self.is_configured:
            for filepath in self.sync_folder.glob(f"{self.EXPORT_PREFIX}*.json"):
                device_id = filepath.stem.replace(self.EXPORT_PREFIX, "")
                if device_id != self.device_id:
                    stat = filepath.stat()
                    other_files.append({
                        "device_id": device_id,
                        "last_modified": datetime.fromtimestamp(
                            stat.st_mtime, tz=timezone.utc
                        ).isoformat(),
                        "size_bytes": stat.st_size,
                    })

        return {
            "enabled": self._sync_enabled,
            "configured": self.is_configured,
            "device_id": self.device_id,
            "sync_folder": str(self.sync_folder) if self.sync_folder else "",
            "last_sync": self._last_sync,
            "interval_minutes": self._interval_minutes,
            "other_devices": other_files,
        }

    # ── Export helpers ──────────────────────────────────────────

    def _build_export(self) -> dict:
        """Build the export data structure from the local database."""
        with self.db.get_connection() as conn:
            export = {
                "device_id": self.device_id,
                "exported_at": datetime.now(timezone.utc).isoformat(),
                "schema_version": self._get_schema_version(conn),
                "tables": {},
            }
            for table in SYNC_TABLES:
                rows = self._export_table(conn, table)
                if rows:
                    export["tables"][table] = rows
            return export

    def _export_table(self, conn, table: str) -> list[dict]:
        """Export all rows from a table as a list of dicts."""
        try:
            cursor = conn.execute(f"SELECT * FROM {table}")  # noqa: S608
            columns = [desc[0] for desc in cursor.description]
            rows = []
            for row in cursor.fetchall():
                row_dict = {columns[i]: row[i] for i in range(len(columns))}
                rows.append(row_dict)
            return rows
        except Exception:
            return []

    def _get_schema_version(self, conn) -> int:
        """Get the current schema version from the database."""
        try:
            row = conn.execute(
                "SELECT version FROM schema_version "
                "ORDER BY version DESC LIMIT 1"
            ).fetchone()
            return row[0] if row else 0
        except Exception:
            return 0

    # ── Import / merge helpers ─────────────────────────────────

    def _merge_import(self, data: dict) -> dict:
        """Merge imported data into the local database.

        Uses last-write-wins for tables with updated_at columns.
        For other tables, inserts missing rows (by primary key).

        Returns dict of {table_name: rows_merged_count}.
        """
        summary = {}
        schema_version = data.get("schema_version", 0)

        with self.db.get_connection() as conn:
            local_version = self._get_schema_version(conn)
            if schema_version != local_version:
                # Schema mismatch — skip merge to avoid corruption
                return {"_skipped": 1}

            for table in SYNC_TABLES:
                rows = data.get("tables", {}).get(table, [])
                if not rows:
                    continue
                count = self._merge_table(conn, table, rows)
                if count > 0:
                    summary[table] = count

        return summary

    def _merge_table(self, conn, table: str, rows: list[dict]) -> int:
        """Merge rows into a local table.

        For tables with updated_at: use last-write-wins.
        For tables without: insert if not exists (by primary key).
        """
        if not rows:
            return 0

        pk = self._get_primary_key(conn, table)
        if not pk:
            return 0

        merged = 0
        use_lww = table in TABLES_WITH_UPDATED_AT

        for row in rows:
            pk_value = row.get(pk)
            if pk_value is None:
                continue

            local_row = conn.execute(
                f"SELECT * FROM {table} WHERE {pk} = ?",  # noqa: S608
                (pk_value,),
            ).fetchone()

            if local_row is None:
                # Row doesn't exist locally — insert it
                columns = list(row.keys())
                placeholders = ", ".join("?" for _ in columns)
                col_names = ", ".join(columns)
                try:
                    conn.execute(
                        f"INSERT OR IGNORE INTO {table} ({col_names}) "  # noqa: S608
                        f"VALUES ({placeholders})",
                        tuple(row[c] for c in columns),
                    )
                    merged += 1
                except Exception:
                    pass  # FK violation, etc — skip
            elif use_lww:
                # Row exists — check if remote is newer
                local_updated = local_row["updated_at"] if "updated_at" in local_row.keys() else None
                remote_updated = row.get("updated_at")

                if remote_updated and local_updated and remote_updated > local_updated:
                    # Remote is newer — update local
                    columns = [c for c in row.keys() if c != pk]
                    set_clause = ", ".join(f"{c} = ?" for c in columns)
                    values = [row[c] for c in columns] + [pk_value]
                    try:
                        conn.execute(
                            f"UPDATE {table} SET {set_clause} "  # noqa: S608
                            f"WHERE {pk} = ?",
                            values,
                        )
                        merged += 1
                    except Exception:
                        pass

        return merged

    def _get_primary_key(self, conn, table: str) -> str | None:
        """Get the primary key column name for a table."""
        try:
            info = conn.execute(
                f"PRAGMA table_info({table})"  # noqa: S608
            ).fetchall()
            for col in info:
                if col[5] == 1:  # pk column in PRAGMA table_info
                    return col[1]  # column name
            return "id"  # default assumption
        except Exception:
            return None

    # ── Lock management ────────────────────────────────────────

    def _acquire_lock(self):
        """Acquire the sync folder lock."""
        if not self.sync_folder:
            raise SyncError("No sync folder configured.")

        lock_path = self.sync_folder / self.LOCK_FILE
        if lock_path.exists():
            # Check if lock is stale
            try:
                lock_age = time.time() - lock_path.stat().st_mtime
                if lock_age < self.LOCK_TIMEOUT_SECONDS:
                    lock_data = json.loads(
                        lock_path.read_text(encoding="utf-8")
                    )
                    raise SyncLockError(
                        f"Another device ({lock_data.get('device_id', 'unknown')}) "
                        f"is syncing. Try again in a moment."
                    )
            except (json.JSONDecodeError, OSError):
                pass
            # Stale lock — remove it
            try:
                lock_path.unlink()
            except OSError:
                pass

        # Create lock file
        lock_data = {
            "device_id": self.device_id,
            "locked_at": datetime.now(timezone.utc).isoformat(),
        }
        lock_path.write_text(
            json.dumps(lock_data), encoding="utf-8"
        )

    def _release_lock(self):
        """Release the sync folder lock."""
        if not self.sync_folder:
            return
        lock_path = self.sync_folder / self.LOCK_FILE
        try:
            if lock_path.exists():
                lock_data = json.loads(
                    lock_path.read_text(encoding="utf-8")
                )
                if lock_data.get("device_id") == self.device_id:
                    lock_path.unlink()
        except (json.JSONDecodeError, OSError):
            pass
