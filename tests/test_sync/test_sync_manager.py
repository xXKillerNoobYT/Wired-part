"""Tests for the file-based sync module."""

import json
import os
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from wired_part.config import Config
from wired_part.database.connection import DatabaseConnection
from wired_part.database.models import Job, Part, Supplier, User
from wired_part.database.repository import Repository
from wired_part.database.schema import initialize_database
from wired_part.sync.sync_manager import (
    SyncError,
    SyncLockError,
    SyncManager,
)


@pytest.fixture
def db_a(tmp_path):
    """Database for device A."""
    db = DatabaseConnection(str(tmp_path / "device_a.db"))
    initialize_database(db)
    return db


@pytest.fixture
def db_b(tmp_path):
    """Database for device B."""
    db = DatabaseConnection(str(tmp_path / "device_b.db"))
    initialize_database(db)
    return db


@pytest.fixture
def sync_folder(tmp_path):
    """Shared sync folder between devices."""
    folder = tmp_path / "sync"
    folder.mkdir()
    return folder


@pytest.fixture
def repo_a(db_a):
    return Repository(db_a)


@pytest.fixture
def repo_b(db_b):
    return Repository(db_b)


def _make_sync_manager(db, sync_folder, device_id="device-a"):
    """Create a SyncManager with mocked config."""
    with patch.object(Config, "SYNC_ENABLED", True), \
         patch.object(Config, "SYNC_FOLDER_PATH", str(sync_folder)), \
         patch.object(Config, "LAST_SYNC_TIMESTAMP", ""), \
         patch.object(Config, "DEVICE_ID", device_id), \
         patch.object(Config, "get_device_id", return_value=device_id), \
         patch.object(Config, "update_last_sync"):
        mgr = SyncManager(db)
    return mgr


class TestSyncManagerConfig:
    def test_not_configured_when_disabled(self, db_a, sync_folder):
        with patch.object(Config, "SYNC_ENABLED", False), \
             patch.object(Config, "SYNC_FOLDER_PATH", str(sync_folder)), \
             patch.object(Config, "DEVICE_ID", "test"), \
             patch.object(Config, "get_device_id", return_value="test"):
            mgr = SyncManager(db_a)
            assert mgr.is_configured is False

    def test_not_configured_without_folder(self, db_a):
        with patch.object(Config, "SYNC_ENABLED", True), \
             patch.object(Config, "SYNC_FOLDER_PATH", ""), \
             patch.object(Config, "DEVICE_ID", "test"), \
             patch.object(Config, "get_device_id", return_value="test"):
            mgr = SyncManager(db_a)
            assert mgr.is_configured is False

    def test_configured_when_enabled_with_folder(self, db_a, sync_folder):
        mgr = _make_sync_manager(db_a, sync_folder)
        assert mgr.is_configured is True

    def test_device_id_set(self, db_a, sync_folder):
        mgr = _make_sync_manager(db_a, sync_folder, "my-device")
        assert mgr.device_id == "my-device"


class TestExport:
    def test_export_creates_file(self, db_a, sync_folder):
        mgr = _make_sync_manager(db_a, sync_folder)
        path = mgr.export_to_sync_folder()
        assert Path(path).exists()

    def test_export_contains_tables(self, db_a, sync_folder, repo_a):
        # Add some data
        cat = repo_a.get_all_categories()[0]
        repo_a.create_part(Part(
            part_number="TEST-001", name="Test Part",
            quantity=10, unit_cost=5.0, category_id=cat.id,
        ))
        mgr = _make_sync_manager(db_a, sync_folder)
        path = mgr.export_to_sync_folder()
        data = json.loads(Path(path).read_text(encoding="utf-8"))

        assert "tables" in data
        assert "parts" in data["tables"]
        assert "device_id" in data
        assert data["device_id"] == "device-a"

    def test_export_includes_schema_version(self, db_a, sync_folder):
        mgr = _make_sync_manager(db_a, sync_folder)
        path = mgr.export_to_sync_folder()
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        assert "schema_version" in data
        assert data["schema_version"] > 0

    def test_export_raises_when_not_configured(self, db_a, tmp_path):
        with patch.object(Config, "SYNC_ENABLED", False), \
             patch.object(Config, "SYNC_FOLDER_PATH", ""), \
             patch.object(Config, "DEVICE_ID", "test"), \
             patch.object(Config, "get_device_id", return_value="test"):
            mgr = SyncManager(db_a)
            with pytest.raises(SyncError, match="not configured"):
                mgr.export_to_sync_folder()


class TestImport:
    def test_import_ignores_own_file(self, db_a, sync_folder, repo_a):
        mgr = _make_sync_manager(db_a, sync_folder)
        mgr.export_to_sync_folder()
        # Import should find no other devices
        summary = mgr.import_from_sync_folder()
        assert len(summary) == 0

    def test_import_merges_from_other_device(
        self, db_a, db_b, sync_folder, repo_a, repo_b
    ):
        # Device B creates a supplier
        sup = Supplier(name="Device B Supplier")
        sup.id = repo_b.create_supplier(sup)

        # Device B exports
        mgr_b = _make_sync_manager(db_b, sync_folder, "device-b")
        mgr_b.export_to_sync_folder()

        # Device A imports
        mgr_a = _make_sync_manager(db_a, sync_folder, "device-a")
        summary = mgr_a.import_from_sync_folder()

        # Verify supplier was imported to device A
        suppliers = repo_a.get_all_suppliers()
        names = [s.name for s in suppliers]
        assert "Device B Supplier" in names

    def test_import_empty_sync_folder(self, db_a, sync_folder):
        mgr = _make_sync_manager(db_a, sync_folder)
        summary = mgr.import_from_sync_folder()
        assert len(summary) == 0

    def test_import_skips_corrupt_files(self, db_a, sync_folder):
        # Write corrupt JSON
        corrupt_file = sync_folder / "wiredpart_sync_bad-device.json"
        corrupt_file.write_text("NOT VALID JSON", encoding="utf-8")

        mgr = _make_sync_manager(db_a, sync_folder)
        # Should not raise
        summary = mgr.import_from_sync_folder()
        assert isinstance(summary, dict)


class TestFullSync:
    def test_sync_round_trip(self, db_a, db_b, sync_folder, repo_a, repo_b):
        # Device A creates data
        cat_a = repo_a.get_all_categories()[0]
        repo_a.create_part(Part(
            part_number="PART-FROM-A", name="Part A",
            quantity=10, unit_cost=5.0, category_id=cat_a.id,
        ))

        # Device B creates different data
        sup_b = Supplier(name="Supplier From B")
        sup_b.id = repo_b.create_supplier(sup_b)

        # Both devices sync
        mgr_a = _make_sync_manager(db_a, sync_folder, "device-a")
        mgr_b = _make_sync_manager(db_b, sync_folder, "device-b")

        # A exports, B exports
        mgr_a.export_to_sync_folder()
        mgr_b.export_to_sync_folder()

        # A imports from B, B imports from A
        mgr_a.import_from_sync_folder()
        mgr_b.import_from_sync_folder()

        # Verify cross-pollination
        suppliers_a = repo_a.get_all_suppliers()
        assert any(s.name == "Supplier From B" for s in suppliers_a)

    def test_sync_preserves_existing_data(
        self, db_a, db_b, sync_folder, repo_a, repo_b
    ):
        # Device A has a supplier
        sup = Supplier(name="Original Supplier")
        sup.id = repo_a.create_supplier(sup)

        # Sync device B (empty) into A
        mgr_b = _make_sync_manager(db_b, sync_folder, "device-b")
        mgr_b.export_to_sync_folder()

        mgr_a = _make_sync_manager(db_a, sync_folder, "device-a")
        mgr_a.import_from_sync_folder()

        # Original data should still be there
        suppliers = repo_a.get_all_suppliers()
        assert any(s.name == "Original Supplier" for s in suppliers)

    def test_schema_mismatch_skips_merge(
        self, db_a, db_b, sync_folder, repo_b
    ):
        # Device B exports
        mgr_b = _make_sync_manager(db_b, sync_folder, "device-b")
        path = mgr_b.export_to_sync_folder()

        # Tamper with schema version in export
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        data["schema_version"] = 999
        Path(path).write_text(json.dumps(data), encoding="utf-8")

        # Device A imports — should skip due to schema mismatch
        mgr_a = _make_sync_manager(db_a, sync_folder, "device-a")
        summary = mgr_a.import_from_sync_folder()
        assert summary.get("_skipped") == 1


class TestLocking:
    def test_lock_file_created_during_export(self, db_a, sync_folder):
        # We can't easily test this mid-operation, but we can verify
        # that lock is cleaned up after export
        mgr = _make_sync_manager(db_a, sync_folder)
        mgr.export_to_sync_folder()
        lock_path = sync_folder / "wiredpart_lock"
        assert not lock_path.exists()  # Lock released after export

    def test_stale_lock_is_cleaned(self, db_a, sync_folder):
        # Create a stale lock (old timestamp)
        lock_path = sync_folder / "wiredpart_lock"
        lock_data = {"device_id": "stale-device", "locked_at": "2020-01-01"}
        lock_path.write_text(json.dumps(lock_data), encoding="utf-8")
        # Make it old
        old_time = time.time() - 600
        os.utime(lock_path, (old_time, old_time))

        # Should succeed (stale lock cleaned up)
        mgr = _make_sync_manager(db_a, sync_folder)
        mgr.export_to_sync_folder()

    def test_active_lock_raises_error(self, db_a, sync_folder):
        # Create a fresh lock from another device
        lock_path = sync_folder / "wiredpart_lock"
        lock_data = {
            "device_id": "other-device",
            "locked_at": "2026-01-01T00:00:00",
        }
        lock_path.write_text(json.dumps(lock_data), encoding="utf-8")
        # Touch it to make it fresh
        os.utime(lock_path, None)

        mgr = _make_sync_manager(db_a, sync_folder)
        with pytest.raises(SyncLockError, match="other-device"):
            mgr.export_to_sync_folder()


class TestSyncStatus:
    def test_status_when_configured(self, db_a, sync_folder):
        mgr = _make_sync_manager(db_a, sync_folder)
        status = mgr.get_sync_status()
        assert status["enabled"] is True
        assert status["configured"] is True
        assert status["device_id"] == "device-a"

    def test_status_shows_other_devices(self, db_a, db_b, sync_folder):
        # Device B exports
        mgr_b = _make_sync_manager(db_b, sync_folder, "device-b")
        mgr_b.export_to_sync_folder()

        # Device A checks status
        mgr_a = _make_sync_manager(db_a, sync_folder, "device-a")
        status = mgr_a.get_sync_status()
        assert len(status["other_devices"]) == 1
        assert status["other_devices"][0]["device_id"] == "device-b"

    def test_status_when_not_configured(self, db_a):
        with patch.object(Config, "SYNC_ENABLED", False), \
             patch.object(Config, "SYNC_FOLDER_PATH", ""), \
             patch.object(Config, "DEVICE_ID", "test"), \
             patch.object(Config, "LAST_SYNC_TIMESTAMP", ""), \
             patch.object(Config, "SYNC_INTERVAL_MINUTES", 60), \
             patch.object(Config, "get_device_id", return_value="test"):
            mgr = SyncManager(db_a)
            status = mgr.get_sync_status()
            assert status["enabled"] is False
            assert status["configured"] is False


class TestDeviceId:
    def test_device_id_generated_on_first_call(self, tmp_path):
        """Config.get_device_id() generates a UUID on first call."""
        # Save original
        orig_id = Config.DEVICE_ID
        orig_settings = Config._SETTINGS_FILE if hasattr(Config, "_SETTINGS_FILE") else None

        try:
            Config.DEVICE_ID = ""
            # Mock _save_settings to avoid file I/O
            with patch("wired_part.config._save_settings"), \
                 patch("wired_part.config._load_settings", return_value={}):
                device_id = Config.get_device_id()
                assert len(device_id) > 0
                assert "-" in device_id  # UUID format
        finally:
            Config.DEVICE_ID = orig_id

    def test_device_id_stable_across_calls(self):
        """Second call returns the same ID."""
        orig_id = Config.DEVICE_ID
        try:
            Config.DEVICE_ID = "stable-test-id"
            assert Config.get_device_id() == "stable-test-id"
            assert Config.get_device_id() == "stable-test-id"
        finally:
            Config.DEVICE_ID = orig_id
