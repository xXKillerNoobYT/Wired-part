"""Tests for Session H (Loops 36-40): sync polish and offline mode.

Simulated user feedback driving each section:
  Loop 36 — "My sync folder is on Google Drive and the lock file gets stuck"
  Loop 37 — "I updated the app on one machine but not the other and now sync breaks"
  Loop 38 — "The sync status just says 'Last sync: 2 hours ago' — is it working?"
  Loop 39 — "My job chat messages aren't syncing to the other device"
  Loop 40 — "What happens if the sync folder is unavailable (no internet)?"
"""

import json
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from wired_part.config import Config
from wired_part.database.connection import DatabaseConnection
from wired_part.database.models import Supplier
from wired_part.database.repository import Repository
from wired_part.database.schema import initialize_database
from wired_part.sync.sync_manager import SYNC_TABLES, SyncManager


@pytest.fixture
def db_a(tmp_path):
    db = DatabaseConnection(str(tmp_path / "device_a.db"))
    initialize_database(db)
    return db


@pytest.fixture
def db_b(tmp_path):
    db = DatabaseConnection(str(tmp_path / "device_b.db"))
    initialize_database(db)
    return db


@pytest.fixture
def sync_folder(tmp_path):
    folder = tmp_path / "sync"
    folder.mkdir()
    return folder


@pytest.fixture
def repo_a(db_a):
    return Repository(db_a)


@pytest.fixture
def repo_b(db_b):
    return Repository(db_b)


def _make_mgr(db, sync_folder, device_id="device-a", last_sync=""):
    with patch.object(Config, "SYNC_ENABLED", True), \
         patch.object(Config, "SYNC_FOLDER_PATH", str(sync_folder)), \
         patch.object(Config, "LAST_SYNC_TIMESTAMP", last_sync), \
         patch.object(Config, "DEVICE_ID", device_id), \
         patch.object(Config, "get_device_id", return_value=device_id), \
         patch.object(Config, "update_last_sync"):
        mgr = SyncManager(db)
    return mgr


# =====================================================================
# Loop 36 — Force-break stale locks
# =====================================================================


class TestForceBreakLock:
    """Force-break stuck sync locks."""

    def test_force_break_removes_lock(self, db_a, sync_folder):
        lock_path = sync_folder / "wiredpart_lock"
        lock_path.write_text(
            json.dumps({"device_id": "stuck"}), encoding="utf-8",
        )

        mgr = _make_mgr(db_a, sync_folder)
        result = mgr.force_break_lock()
        assert result is not None
        assert result["device_id"] == "stuck"
        assert not lock_path.exists()

    def test_force_break_no_lock(self, db_a, sync_folder):
        mgr = _make_mgr(db_a, sync_folder)
        result = mgr.force_break_lock()
        assert result is None

    def test_get_lock_info(self, db_a, sync_folder):
        lock_path = sync_folder / "wiredpart_lock"
        lock_path.write_text(
            json.dumps({"device_id": "other", "pid": 123}),
            encoding="utf-8",
        )

        mgr = _make_mgr(db_a, sync_folder)
        info = mgr.get_lock_info()
        assert info is not None
        assert info["device_id"] == "other"
        assert "age_seconds" in info
        assert "is_stale" in info

    def test_lock_info_detects_stale(self, db_a, sync_folder):
        lock_path = sync_folder / "wiredpart_lock"
        lock_path.write_text(
            json.dumps({"device_id": "old"}), encoding="utf-8",
        )
        # Make it old
        import os
        old_time = time.time() - 600
        os.utime(lock_path, (old_time, old_time))

        mgr = _make_mgr(db_a, sync_folder)
        info = mgr.get_lock_info()
        assert info["is_stale"] is True

    def test_lock_info_none_when_no_lock(self, db_a, sync_folder):
        mgr = _make_mgr(db_a, sync_folder)
        assert mgr.get_lock_info() is None


# =====================================================================
# Loop 37 — Schema compatibility
# =====================================================================


class TestSchemaCompatibility:
    """Check schema version across devices."""

    def test_compatible_devices(self, db_a, db_b, sync_folder):
        mgr_b = _make_mgr(db_b, sync_folder, "device-b")
        mgr_b.export_to_sync_folder()

        mgr_a = _make_mgr(db_a, sync_folder, "device-a")
        result = mgr_a.check_schema_compatibility()
        assert result["local_version"] > 0
        assert "device-b" in result["compatible_devices"]
        assert len(result["incompatible_devices"]) == 0

    def test_incompatible_device(self, db_a, db_b, sync_folder):
        mgr_b = _make_mgr(db_b, sync_folder, "device-b")
        path = mgr_b.export_to_sync_folder()

        # Tamper schema version
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        data["schema_version"] = 999
        Path(path).write_text(json.dumps(data), encoding="utf-8")

        mgr_a = _make_mgr(db_a, sync_folder, "device-a")
        result = mgr_a.check_schema_compatibility()
        assert len(result["incompatible_devices"]) == 1
        assert result["incompatible_devices"][0]["device_id"] == "device-b"
        assert result["incompatible_devices"][0]["version"] == 999

    def test_corrupt_file_flagged(self, db_a, sync_folder):
        corrupt = sync_folder / "wiredpart_sync_bad.json"
        corrupt.write_text("NOT JSON", encoding="utf-8")

        mgr = _make_mgr(db_a, sync_folder)
        result = mgr.check_schema_compatibility()
        assert len(result["incompatible_devices"]) == 1
        assert result["incompatible_devices"][0]["version"] == "unknown"


# =====================================================================
# Loop 38 — Enhanced sync status
# =====================================================================


class TestDetailedSyncStatus:
    """Comprehensive sync status for UI."""

    def test_detailed_status_keys(self, db_a, sync_folder):
        mgr = _make_mgr(db_a, sync_folder)
        status = mgr.get_detailed_sync_status()
        assert "lock_info" in status
        assert "recent_history" in status
        assert "schema_compatibility" in status
        assert "known_devices" in status
        assert "last_sync_human" in status

    def test_never_synced(self, db_a, sync_folder):
        mgr = _make_mgr(db_a, sync_folder, last_sync="")
        status = mgr.get_detailed_sync_status()
        assert status["last_sync_human"] == "Never"

    def test_recently_synced(self, db_a, sync_folder):
        from datetime import datetime, timezone
        recent = datetime.now(timezone.utc).isoformat()
        mgr = _make_mgr(db_a, sync_folder, last_sync=recent)
        status = mgr.get_detailed_sync_status()
        assert "Just now" in status["last_sync_human"] or \
               "minute" in status["last_sync_human"]

    def test_includes_history(self, db_a, sync_folder):
        mgr = _make_mgr(db_a, sync_folder)
        mgr.log_sync_event("export")
        status = mgr.get_detailed_sync_status()
        assert len(status["recent_history"]) >= 1


# =====================================================================
# Loop 39 — Chat messages in sync
# =====================================================================


class TestChatInSync:
    """Verify job_updates (chat) table is included in sync."""

    def test_job_updates_in_sync_tables(self):
        assert "job_updates" in SYNC_TABLES

    def test_activity_log_in_sync_tables(self):
        assert "activity_log" in SYNC_TABLES

    def test_notifications_in_sync_tables(self):
        assert "notifications" in SYNC_TABLES

    def test_verify_sync_tables(self, db_a, sync_folder):
        mgr = _make_mgr(db_a, sync_folder)
        result = mgr.verify_sync_tables()
        assert "job_updates" in result["synced_tables"]
        # All sync tables should exist in the database
        assert result["missing_from_db"] == []

    def test_some_tables_not_in_sync(self, db_a, sync_folder):
        """Some tables (like schema_version, audits) may not be synced."""
        mgr = _make_mgr(db_a, sync_folder)
        result = mgr.verify_sync_tables()
        # missing_from_sync = DB tables not in SYNC_TABLES — that's OK
        assert isinstance(result["missing_from_sync"], list)


# =====================================================================
# Loop 40 — Graceful offline mode
# =====================================================================


class TestOfflineMode:
    """Sync gracefully handles unavailable folder."""

    def test_sync_safe_disabled(self, db_a, tmp_path):
        with patch.object(Config, "SYNC_ENABLED", False), \
             patch.object(Config, "SYNC_FOLDER_PATH", ""), \
             patch.object(Config, "DEVICE_ID", "test"), \
             patch.object(Config, "get_device_id", return_value="test"):
            mgr = SyncManager(db_a)
        result = mgr.sync_safe()
        assert result["status"] == "disabled"

    def test_sync_safe_no_folder(self, db_a, tmp_path):
        with patch.object(Config, "SYNC_ENABLED", True), \
             patch.object(Config, "SYNC_FOLDER_PATH", ""), \
             patch.object(Config, "DEVICE_ID", "test"), \
             patch.object(Config, "get_device_id", return_value="test"), \
             patch.object(Config, "LAST_SYNC_TIMESTAMP", ""):
            mgr = SyncManager(db_a)
        result = mgr.sync_safe()
        assert result["status"] == "no_folder_configured"

    def test_sync_safe_folder_missing(self, db_a, tmp_path):
        nonexistent = str(tmp_path / "does_not_exist")
        with patch.object(Config, "SYNC_ENABLED", True), \
             patch.object(Config, "SYNC_FOLDER_PATH", nonexistent), \
             patch.object(Config, "DEVICE_ID", "test"), \
             patch.object(Config, "get_device_id", return_value="test"), \
             patch.object(Config, "LAST_SYNC_TIMESTAMP", ""):
            mgr = SyncManager(db_a)
        result = mgr.sync_safe()
        assert result["status"] == "offline"

    def test_sync_safe_success(self, db_a, sync_folder):
        mgr = _make_mgr(db_a, sync_folder)
        result = mgr.sync_safe()
        assert result["status"] == "success"

    def test_sync_safe_locked(self, db_a, sync_folder):
        # Create a fresh lock from another device
        lock_path = sync_folder / "wiredpart_lock"
        lock_path.write_text(
            json.dumps({"device_id": "other"}), encoding="utf-8",
        )
        import os
        os.utime(lock_path, None)

        mgr = _make_mgr(db_a, sync_folder)
        result = mgr.sync_safe()
        assert result["status"] == "locked"
