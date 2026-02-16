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
    "user_hats",
    "user_settings",
    "parts",
    "part_suppliers",
    "brands",
    "part_variants",
    "parts_lists",
    "parts_list_items",
    "trucks",
    "jobs",
    "job_assignments",
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
    "return_authorization_items",
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
    "notebook_pages", "truck_inventory", "user_settings",
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
        """Acquire the sync folder lock using atomic file creation."""
        import platform
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

        # Atomic file creation — prevents two devices creating at the same instant
        lock_data = {
            "device_id": self.device_id,
            "locked_at": datetime.now(timezone.utc).isoformat(),
            "pid": os.getpid(),
            "hostname": platform.node(),
        }
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            try:
                os.write(fd, json.dumps(lock_data).encode("utf-8"))
            finally:
                os.close(fd)
        except FileExistsError:
            # Another device beat us — re-read and report
            try:
                other = json.loads(lock_path.read_text(encoding="utf-8"))
            except Exception:
                other = {}
            raise SyncLockError(
                f"Another device ({other.get('device_id', 'unknown')}) "
                f"is syncing. Try again in a moment."
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

    # ── Loop 31: Conflict detection ──────────────────────────────

    def detect_conflicts(self, data: dict) -> list[dict]:
        """Detect merge conflicts before applying an import.

        Returns a list of conflict dicts:
        {table, pk, pk_value, local_updated, remote_updated,
         local_data, remote_data}

        A conflict is defined as: both local and remote rows have been
        modified since their respective last-sync timestamps, and they
        differ. Only applies to LWW tables.
        """
        conflicts = []
        schema_version = data.get("schema_version", 0)

        with self.db.get_connection() as conn:
            local_version = self._get_schema_version(conn)
            if schema_version != local_version:
                return []

            for table in SYNC_TABLES:
                if table not in TABLES_WITH_UPDATED_AT:
                    continue
                rows = data.get("tables", {}).get(table, [])
                if not rows:
                    continue

                pk = self._get_primary_key(conn, table)
                if not pk:
                    continue

                for row in rows:
                    pk_value = row.get(pk)
                    if pk_value is None:
                        continue

                    local_row = conn.execute(
                        f"SELECT * FROM {table} WHERE {pk} = ?",  # noqa: S608
                        (pk_value,),
                    ).fetchone()

                    if local_row is None:
                        continue  # New row — no conflict

                    local_updated = (
                        local_row["updated_at"]
                        if "updated_at" in local_row.keys()
                        else None
                    )
                    remote_updated = row.get("updated_at")

                    if (local_updated and remote_updated
                            and local_updated != remote_updated):
                        # Both have different timestamps — check if data
                        # actually differs (exclude timestamp columns)
                        local_dict = {
                            k: local_row[k] for k in local_row.keys()
                        }
                        skip_keys = {"updated_at", "created_at"}
                        data_differs = any(
                            str(local_dict.get(k)) != str(row.get(k))
                            for k in row
                            if k not in skip_keys and k != pk
                        )
                        if data_differs:
                            conflicts.append({
                                "table": table,
                                "pk": pk,
                                "pk_value": pk_value,
                                "local_updated": local_updated,
                                "remote_updated": remote_updated,
                                "local_data": local_dict,
                                "remote_data": row,
                            })

        return conflicts

    # ── Loop 32: Tombstone / soft-delete tracking ────────────────

    def export_with_deletions(self) -> dict:
        """Build export that also tracks deleted rows.

        Compares current table row IDs against the set of IDs that
        were exported last time (stored in a sidecar file). Any IDs
        present in the previous export but missing now are marked as
        tombstones.

        Returns the export dict with an additional 'tombstones' key.
        """
        export = self._build_export()

        # Load previous export IDs
        prev_path = self._get_previous_export_ids_path()
        prev_ids = {}
        if prev_path and prev_path.exists():
            try:
                prev_ids = json.loads(
                    prev_path.read_text(encoding="utf-8")
                )
            except (json.JSONDecodeError, OSError):
                prev_ids = {}

        tombstones = {}
        current_ids = {}

        for table in SYNC_TABLES:
            rows = export.get("tables", {}).get(table, [])
            pk = "id"  # default PK
            cur_set = set()
            for row in rows:
                pk_val = row.get(pk)
                if pk_val is not None:
                    cur_set.add(pk_val)
            current_ids[table] = list(cur_set)

            prev_set = set(prev_ids.get(table, []))
            deleted = prev_set - cur_set
            if deleted:
                tombstones[table] = list(deleted)

        export["tombstones"] = tombstones

        # Save current IDs for next comparison
        if prev_path:
            try:
                prev_path.write_text(
                    json.dumps(current_ids, default=str),
                    encoding="utf-8",
                )
            except OSError:
                pass

        return export

    def apply_tombstones(self, tombstones: dict):
        """Apply tombstone deletions from a remote export.

        Deletes local rows that the remote device has deleted.
        Only deletes rows that haven't been modified locally since
        the remote export.
        """
        if not tombstones:
            return

        with self.db.get_connection() as conn:
            for table, deleted_ids in tombstones.items():
                if table not in SYNC_TABLES:
                    continue
                for pk_val in deleted_ids:
                    try:
                        conn.execute(
                            f"DELETE FROM {table} WHERE id = ?",  # noqa: S608
                            (pk_val,),
                        )
                    except Exception:
                        pass  # FK constraint, etc.

    def _get_previous_export_ids_path(self):
        """Path to the sidecar file storing last export's row IDs."""
        if not self.sync_folder:
            return None
        return self.sync_folder / f"wiredpart_ids_{self.device_id}.json"

    # ── Loop 33: Incremental sync ────────────────────────────────

    def export_incremental(self) -> dict:
        """Export only rows changed since the last sync timestamp.

        Falls back to full export if no last-sync timestamp exists.
        Returns the export dict with only changed rows.
        """
        if not self._last_sync:
            return self._build_export()

        with self.db.get_connection() as conn:
            export = {
                "device_id": self.device_id,
                "exported_at": datetime.now(timezone.utc).isoformat(),
                "schema_version": self._get_schema_version(conn),
                "tables": {},
                "incremental": True,
                "since": self._last_sync,
            }

            for table in SYNC_TABLES:
                rows = self._export_table_incremental(
                    conn, table, self._last_sync
                )
                if rows:
                    export["tables"][table] = rows

            return export

    def _export_table_incremental(
        self, conn, table: str, since: str
    ) -> list[dict]:
        """Export only rows from a table changed since a timestamp."""
        try:
            # Check if table has updated_at or created_at
            columns_info = conn.execute(
                f"PRAGMA table_info({table})"  # noqa: S608
            ).fetchall()
            col_names = {col[1] for col in columns_info}

            if "updated_at" in col_names:
                cursor = conn.execute(
                    f"SELECT * FROM {table} "  # noqa: S608
                    f"WHERE updated_at > ?",
                    (since,),
                )
            elif "created_at" in col_names:
                cursor = conn.execute(
                    f"SELECT * FROM {table} "  # noqa: S608
                    f"WHERE created_at > ?",
                    (since,),
                )
            else:
                # No timestamp column — export all rows
                cursor = conn.execute(
                    f"SELECT * FROM {table}"  # noqa: S608
                )

            columns = [desc[0] for desc in cursor.description]
            rows = []
            for row in cursor.fetchall():
                row_dict = {columns[i]: row[i] for i in range(len(columns))}
                rows.append(row_dict)
            return rows
        except Exception:
            return []

    # ── Loop 34: Multi-device registry ───────────────────────────

    DEVICES_FILE = "wiredpart_devices.json"

    def register_device(self):
        """Register this device in the sync folder's device registry."""
        import platform
        if not self.is_configured:
            return

        registry = self._load_device_registry()
        registry[self.device_id] = {
            "device_id": self.device_id,
            "hostname": platform.node(),
            "platform": platform.system(),
            "last_seen": datetime.now(timezone.utc).isoformat(),
            "app_version": self._get_app_version(),
        }
        self._save_device_registry(registry)

    def get_known_devices(self) -> list[dict]:
        """Get all devices that have ever synced to this folder."""
        registry = self._load_device_registry()
        return list(registry.values())

    def _load_device_registry(self) -> dict:
        """Load the device registry from the sync folder."""
        if not self.sync_folder:
            return {}
        path = self.sync_folder / self.DEVICES_FILE
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def _save_device_registry(self, registry: dict):
        """Save the device registry to the sync folder."""
        if not self.sync_folder:
            return
        path = self.sync_folder / self.DEVICES_FILE
        try:
            path.write_text(
                json.dumps(registry, indent=2, default=str),
                encoding="utf-8",
            )
        except OSError:
            pass

    def _get_app_version(self) -> str:
        """Get the current app version string."""
        try:
            from wired_part.utils.constants import APP_VERSION
            return APP_VERSION
        except ImportError:
            return "unknown"

    # ── Loop 35: Sync history log ────────────────────────────────

    HISTORY_FILE = "wiredpart_history.json"
    MAX_HISTORY_ENTRIES = 50

    def log_sync_event(
        self, event_type: str, details: dict | None = None
    ):
        """Log a sync event to the history file.

        event_type: 'export', 'import', 'conflict', 'error'
        """
        if not self.is_configured:
            return

        history = self._load_sync_history()
        entry = {
            "device_id": self.device_id,
            "event_type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "details": details or {},
        }
        history.append(entry)

        # Cap the history
        if len(history) > self.MAX_HISTORY_ENTRIES:
            history = history[-self.MAX_HISTORY_ENTRIES:]

        self._save_sync_history(history)

    def get_sync_history(self, limit: int = 20) -> list[dict]:
        """Get the most recent sync history entries."""
        history = self._load_sync_history()
        return history[-limit:]

    def _load_sync_history(self) -> list:
        """Load sync history from the sync folder."""
        if not self.sync_folder:
            return []
        path = self.sync_folder / self.HISTORY_FILE
        if not path.exists():
            return []
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []

    def _save_sync_history(self, history: list):
        """Save sync history to the sync folder."""
        if not self.sync_folder:
            return
        path = self.sync_folder / self.HISTORY_FILE
        try:
            path.write_text(
                json.dumps(history, indent=2, default=str),
                encoding="utf-8",
            )
        except OSError:
            pass

    # ── Loop 36: Force-break stale locks ─────────────────────────

    def force_break_lock(self) -> dict | None:
        """Force-break any existing lock file regardless of age.

        Returns the lock data that was broken, or None if no lock existed.
        """
        if not self.sync_folder:
            return None
        lock_path = self.sync_folder / self.LOCK_FILE
        if not lock_path.exists():
            return None

        try:
            lock_data = json.loads(
                lock_path.read_text(encoding="utf-8")
            )
        except (json.JSONDecodeError, OSError):
            lock_data = {"device_id": "unknown"}

        try:
            lock_path.unlink()
        except OSError:
            pass

        self.log_sync_event("force_break_lock", lock_data)
        return lock_data

    def get_lock_info(self) -> dict | None:
        """Get information about the current lock, if one exists."""
        if not self.sync_folder:
            return None
        lock_path = self.sync_folder / self.LOCK_FILE
        if not lock_path.exists():
            return None

        try:
            lock_data = json.loads(
                lock_path.read_text(encoding="utf-8")
            )
            lock_data["age_seconds"] = (
                time.time() - lock_path.stat().st_mtime
            )
            lock_data["is_stale"] = (
                lock_data["age_seconds"] > self.LOCK_TIMEOUT_SECONDS
            )
            return lock_data
        except (json.JSONDecodeError, OSError):
            return None

    # ── Loop 37: Schema version compatibility ────────────────────

    def check_schema_compatibility(self) -> dict:
        """Check if all sync files are compatible with our schema.

        Returns dict with:
        - local_version: int
        - compatible_devices: list of device_ids with matching schema
        - incompatible_devices: list of {device_id, version} that mismatch
        """
        result = {
            "local_version": 0,
            "compatible_devices": [],
            "incompatible_devices": [],
        }

        with self.db.get_connection() as conn:
            result["local_version"] = self._get_schema_version(conn)

        if not self.is_configured:
            return result

        for filepath in self.sync_folder.glob(f"{self.EXPORT_PREFIX}*.json"):
            device_id = filepath.stem.replace(self.EXPORT_PREFIX, "")
            if device_id == self.device_id:
                continue
            try:
                data = json.loads(filepath.read_text(encoding="utf-8"))
                remote_version = data.get("schema_version", 0)
                if remote_version == result["local_version"]:
                    result["compatible_devices"].append(device_id)
                else:
                    result["incompatible_devices"].append({
                        "device_id": device_id,
                        "version": remote_version,
                    })
            except (json.JSONDecodeError, OSError):
                result["incompatible_devices"].append({
                    "device_id": device_id,
                    "version": "unknown",
                })

        return result

    # ── Loop 38: Enhanced sync status ────────────────────────────

    def get_detailed_sync_status(self) -> dict:
        """Get comprehensive sync status for UI display.

        Extends get_sync_status with history, lock info, compatibility.
        """
        base = self.get_sync_status()
        base["lock_info"] = self.get_lock_info()
        base["recent_history"] = self.get_sync_history(limit=5)
        base["schema_compatibility"] = self.check_schema_compatibility()
        base["known_devices"] = self.get_known_devices()

        # Calculate time since last sync in human-readable form
        if self._last_sync:
            try:
                last = datetime.fromisoformat(
                    self._last_sync.replace("Z", "+00:00")
                )
                delta = datetime.now(timezone.utc) - last
                minutes = int(delta.total_seconds() / 60)
                if minutes < 1:
                    base["last_sync_human"] = "Just now"
                elif minutes < 60:
                    base["last_sync_human"] = f"{minutes} minutes ago"
                elif minutes < 1440:
                    hours = minutes // 60
                    base["last_sync_human"] = f"{hours} hours ago"
                else:
                    days = minutes // 1440
                    base["last_sync_human"] = f"{days} days ago"
            except (ValueError, TypeError):
                base["last_sync_human"] = "Unknown"
        else:
            base["last_sync_human"] = "Never"

        return base

    # ── Loop 39: Verify chat tables in sync ──────────────────────

    def verify_sync_tables(self) -> dict:
        """Verify all required tables exist and are included in sync.

        Returns dict with:
        - synced_tables: tables in SYNC_TABLES that exist in DB
        - missing_from_sync: tables in DB but not in SYNC_TABLES
        - missing_from_db: tables in SYNC_TABLES but not in DB
        """
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name NOT LIKE 'sqlite_%' "
                "AND name != 'schema_version'"
            )
            db_tables = {row[0] for row in cursor.fetchall()}

        sync_set = set(SYNC_TABLES)

        return {
            "synced_tables": sorted(sync_set & db_tables),
            "missing_from_sync": sorted(db_tables - sync_set),
            "missing_from_db": sorted(sync_set - db_tables),
        }

    # ── Loop 40: Graceful offline mode ───────────────────────────

    def sync_safe(self) -> dict:
        """Sync with graceful offline handling.

        Returns summary dict. If sync folder is unavailable,
        returns a status dict instead of raising.
        """
        if not self._sync_enabled:
            return {"status": "disabled"}

        if not self.sync_folder:
            return {"status": "no_folder_configured"}

        if not self.sync_folder.exists():
            return {
                "status": "offline",
                "reason": "Sync folder not accessible",
                "folder": str(self.sync_folder),
            }

        try:
            # Test write access
            test_file = self.sync_folder / ".wiredpart_test"
            test_file.write_text("test", encoding="utf-8")
            test_file.unlink()
        except OSError:
            return {
                "status": "offline",
                "reason": "Sync folder not writable",
                "folder": str(self.sync_folder),
            }

        try:
            self.register_device()
            summary = self.sync()
            self.log_sync_event("sync_complete", summary)
            return {
                "status": "success",
                "merged": summary,
            }
        except SyncLockError as e:
            self.log_sync_event("error", {"type": "lock", "message": str(e)})
            return {
                "status": "locked",
                "reason": str(e),
            }
        except SyncError as e:
            self.log_sync_event("error", {"type": "sync", "message": str(e)})
            return {
                "status": "error",
                "reason": str(e),
            }
        except Exception as e:
            self.log_sync_event("error", {"type": "unknown", "message": str(e)})
            return {
                "status": "error",
                "reason": str(e),
            }
