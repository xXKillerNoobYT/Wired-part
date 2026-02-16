"""Tests for Session G (Loops 31-35): sync hardening features.

Simulated user feedback driving each section:
  Loop 31 — "I synced and it overwrote my changes from this morning"
  Loop 32 — "I deleted a part on my laptop but it came back after sync"
  Loop 33 — "Sync takes forever — it's pushing everything every time"
  Loop 34 — "Can two people use the app on different computers at the same time?"
  Loop 35 — "The sync status just says 'Last sync: 2 hours ago' — is it working?"
"""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from wired_part.config import Config
from wired_part.database.connection import DatabaseConnection
from wired_part.database.models import Category, Part, Supplier
from wired_part.database.repository import Repository
from wired_part.database.schema import initialize_database
from wired_part.sync.sync_manager import SyncManager


# ── Fixtures ─────────────────────────────────────────────────────


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
# Loop 31 — Conflict detection
# =====================================================================


class TestConflictDetection:
    """Detect when both devices modified the same row."""

    def test_no_conflicts_when_different_rows(
        self, db_a, db_b, sync_folder, repo_a, repo_b
    ):
        # A and B create different suppliers
        repo_a.create_supplier(Supplier(name="Supplier A"))
        repo_b.create_supplier(Supplier(name="Supplier B"))

        mgr_b = _make_mgr(db_b, sync_folder, "device-b")
        path = mgr_b.export_to_sync_folder()
        data = json.loads(Path(path).read_text(encoding="utf-8"))

        mgr_a = _make_mgr(db_a, sync_folder, "device-a")
        conflicts = mgr_a.detect_conflicts(data)
        # No conflicts because they modified different rows
        assert len(conflicts) == 0

    def test_conflict_when_same_row_modified(
        self, db_a, db_b, sync_folder, repo_a, repo_b
    ):
        """Both devices modify the same seeded category differently."""
        cats_a = repo_a.get_all_categories()
        cats_b = repo_b.get_all_categories()
        shared_id = cats_a[0].id

        # Modify on A with a forced earlier timestamp
        cats_a[0].description = "Changed on device A"
        repo_a.update_category(cats_a[0])
        with db_a.get_connection() as conn:
            conn.execute(
                "UPDATE categories SET updated_at = '2026-01-01 10:00:00' "
                "WHERE id = ?", (shared_id,),
            )

        # Modify on B with a forced later timestamp
        cats_b[0].description = "Changed on device B"
        repo_b.update_category(cats_b[0])
        with db_b.get_connection() as conn:
            conn.execute(
                "UPDATE categories SET updated_at = '2026-01-02 10:00:00' "
                "WHERE id = ?", (shared_id,),
            )

        mgr_b = _make_mgr(db_b, sync_folder, "device-b")
        path = mgr_b.export_to_sync_folder()
        data = json.loads(Path(path).read_text(encoding="utf-8"))

        mgr_a = _make_mgr(db_a, sync_folder, "device-a")
        conflicts = mgr_a.detect_conflicts(data)

        cat_conflicts = [
            c for c in conflicts if c["table"] == "categories"
        ]
        assert len(cat_conflicts) >= 1

    def test_conflict_contains_both_versions(
        self, db_a, db_b, sync_folder, repo_a, repo_b
    ):
        """Conflict dict has local_data, remote_data, timestamps."""
        cats_a = repo_a.get_all_categories()
        cats_b = repo_b.get_all_categories()
        shared_id = cats_a[1].id

        cats_a[1].description = "A version"
        repo_a.update_category(cats_a[1])
        with db_a.get_connection() as conn:
            conn.execute(
                "UPDATE categories SET updated_at = '2026-01-01 08:00:00' "
                "WHERE id = ?", (shared_id,),
            )

        cats_b[1].description = "B version"
        repo_b.update_category(cats_b[1])
        with db_b.get_connection() as conn:
            conn.execute(
                "UPDATE categories SET updated_at = '2026-01-02 08:00:00' "
                "WHERE id = ?", (shared_id,),
            )

        mgr_b = _make_mgr(db_b, sync_folder, "device-b")
        path = mgr_b.export_to_sync_folder()
        data = json.loads(Path(path).read_text(encoding="utf-8"))

        mgr_a = _make_mgr(db_a, sync_folder, "device-a")
        conflicts = mgr_a.detect_conflicts(data)

        assert len(conflicts) >= 1
        c = conflicts[0]
        assert "local_data" in c
        assert "remote_data" in c
        assert "local_updated" in c
        assert "remote_updated" in c

    def test_no_conflict_for_new_remote_row(
        self, db_a, db_b, sync_folder, repo_b
    ):
        # Only B has a supplier — no conflict
        repo_b.create_supplier(Supplier(name="New from B"))

        mgr_b = _make_mgr(db_b, sync_folder, "device-b")
        path = mgr_b.export_to_sync_folder()
        data = json.loads(Path(path).read_text(encoding="utf-8"))

        mgr_a = _make_mgr(db_a, sync_folder, "device-a")
        conflicts = mgr_a.detect_conflicts(data)
        assert len(conflicts) == 0

    def test_schema_mismatch_returns_empty(
        self, db_a, db_b, sync_folder, repo_b
    ):
        repo_b.create_supplier(Supplier(name="Test"))
        mgr_b = _make_mgr(db_b, sync_folder, "device-b")
        path = mgr_b.export_to_sync_folder()
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        data["schema_version"] = 999

        mgr_a = _make_mgr(db_a, sync_folder, "device-a")
        conflicts = mgr_a.detect_conflicts(data)
        assert conflicts == []


# =====================================================================
# Loop 32 — Tombstone / soft-delete
# =====================================================================


class TestTombstoneTracking:
    """Detect and propagate deleted rows across devices."""

    def test_export_with_deletions_includes_tombstones_key(
        self, db_a, sync_folder, repo_a
    ):
        mgr = _make_mgr(db_a, sync_folder)
        export = mgr.export_with_deletions()
        assert "tombstones" in export

    def test_tombstones_empty_on_first_export(
        self, db_a, sync_folder, repo_a
    ):
        mgr = _make_mgr(db_a, sync_folder)
        export = mgr.export_with_deletions()
        # First export: no previous IDs, so no tombstones
        total = sum(len(v) for v in export["tombstones"].values())
        assert total == 0

    def test_tombstones_detected_after_deletion(
        self, db_a, sync_folder, repo_a
    ):
        # Create and export a supplier
        sup = Supplier(name="Will Delete")
        sup.id = repo_a.create_supplier(sup)

        mgr = _make_mgr(db_a, sync_folder)
        mgr.export_with_deletions()  # Records IDs

        # Now delete the supplier
        repo_a.delete_supplier(sup.id)

        # Second export should detect tombstone
        export2 = mgr.export_with_deletions()
        assert sup.id in export2["tombstones"].get("suppliers", [])

    def test_apply_tombstones_deletes_rows(
        self, db_a, sync_folder, repo_a
    ):
        sup = Supplier(name="To Be Tombstoned")
        sup.id = repo_a.create_supplier(sup)

        mgr = _make_mgr(db_a, sync_folder)
        tombstones = {"suppliers": [sup.id]}
        mgr.apply_tombstones(tombstones)

        # Should be deleted
        result = repo_a.get_all_suppliers()
        assert not any(s.id == sup.id for s in result)

    def test_apply_empty_tombstones(self, db_a, sync_folder):
        mgr = _make_mgr(db_a, sync_folder)
        mgr.apply_tombstones({})  # No crash
        mgr.apply_tombstones(None)  # No crash


# =====================================================================
# Loop 33 — Incremental sync
# =====================================================================


class TestIncrementalSync:
    """Only export rows changed since last sync."""

    def test_full_export_when_no_last_sync(
        self, db_a, sync_folder, repo_a
    ):
        cat = repo_a.get_all_categories()[0]
        repo_a.create_part(Part(
            part_number="INC-01", name="Incremental 1",
            quantity=5, unit_cost=1.0, category_id=cat.id,
        ))

        mgr = _make_mgr(db_a, sync_folder, last_sync="")
        export = mgr.export_incremental()
        # Should include categories (seeded data)
        assert "categories" in export["tables"]

    def test_incremental_flag_set(self, db_a, sync_folder, repo_a):
        mgr = _make_mgr(
            db_a, sync_folder,
            last_sync="2020-01-01T00:00:00",
        )
        export = mgr.export_incremental()
        assert export.get("incremental") is True
        assert export.get("since") == "2020-01-01T00:00:00"

    def test_incremental_excludes_old_data(
        self, db_a, sync_folder, repo_a
    ):
        """With a future last-sync timestamp, nothing should export."""
        mgr = _make_mgr(
            db_a, sync_folder,
            last_sync="2099-01-01T00:00:00",
        )
        export = mgr.export_incremental()
        # Tables with timestamp columns should be empty
        # Some tables without timestamps still export all rows
        tables_with_ts = {"parts", "jobs", "users", "trucks", "suppliers"}
        for table in tables_with_ts:
            rows = export.get("tables", {}).get(table, [])
            assert len(rows) == 0, f"{table} should have no rows"

    def test_incremental_includes_recent_changes(
        self, db_a, sync_folder, repo_a
    ):
        mgr = _make_mgr(
            db_a, sync_folder,
            last_sync="2020-01-01T00:00:00",  # very old
        )
        cat = repo_a.get_all_categories()[0]
        repo_a.create_part(Part(
            part_number="INC-NEW", name="New Part",
            quantity=10, unit_cost=5.0, category_id=cat.id,
        ))

        export = mgr.export_incremental()
        parts = export.get("tables", {}).get("parts", [])
        assert any(p["part_number"] == "INC-NEW" for p in parts)


# =====================================================================
# Loop 34 — Multi-device registry
# =====================================================================


class TestDeviceRegistry:
    """Track all devices that sync to the folder."""

    def test_register_device(self, db_a, sync_folder):
        mgr = _make_mgr(db_a, sync_folder, "device-alpha")
        mgr.register_device()

        devices = mgr.get_known_devices()
        assert len(devices) >= 1
        assert any(d["device_id"] == "device-alpha" for d in devices)

    def test_multiple_devices_registered(
        self, db_a, db_b, sync_folder
    ):
        mgr_a = _make_mgr(db_a, sync_folder, "device-alpha")
        mgr_b = _make_mgr(db_b, sync_folder, "device-beta")
        mgr_a.register_device()
        mgr_b.register_device()

        devices = mgr_a.get_known_devices()
        ids = [d["device_id"] for d in devices]
        assert "device-alpha" in ids
        assert "device-beta" in ids

    def test_device_entry_has_metadata(self, db_a, sync_folder):
        mgr = _make_mgr(db_a, sync_folder, "device-meta")
        mgr.register_device()

        devices = mgr.get_known_devices()
        entry = next(d for d in devices if d["device_id"] == "device-meta")
        assert "hostname" in entry
        assert "platform" in entry
        assert "last_seen" in entry
        assert "app_version" in entry

    def test_register_updates_last_seen(self, db_a, sync_folder):
        mgr = _make_mgr(db_a, sync_folder, "device-update")
        mgr.register_device()
        first = mgr.get_known_devices()[0]["last_seen"]

        import time
        time.sleep(0.1)
        mgr.register_device()
        second = mgr.get_known_devices()[0]["last_seen"]
        assert second >= first

    def test_empty_registry(self, db_a, sync_folder):
        mgr = _make_mgr(db_a, sync_folder)
        devices = mgr.get_known_devices()
        assert devices == []


# =====================================================================
# Loop 35 — Sync history log
# =====================================================================


class TestSyncHistory:
    """Track recent sync events for debugging."""

    def test_log_event(self, db_a, sync_folder):
        mgr = _make_mgr(db_a, sync_folder)
        mgr.log_sync_event("export", {"tables": 5})

        history = mgr.get_sync_history()
        assert len(history) == 1
        assert history[0]["event_type"] == "export"
        assert history[0]["device_id"] == "device-a"

    def test_multiple_events(self, db_a, sync_folder):
        mgr = _make_mgr(db_a, sync_folder)
        mgr.log_sync_event("export")
        mgr.log_sync_event("import", {"merged": 10})
        mgr.log_sync_event("error", {"message": "test error"})

        history = mgr.get_sync_history()
        assert len(history) == 3
        types = [h["event_type"] for h in history]
        assert types == ["export", "import", "error"]

    def test_history_limit(self, db_a, sync_folder):
        mgr = _make_mgr(db_a, sync_folder)
        mgr.log_sync_event("export")
        mgr.log_sync_event("import")

        history = mgr.get_sync_history(limit=1)
        assert len(history) == 1
        assert history[0]["event_type"] == "import"

    def test_history_capped_at_max(self, db_a, sync_folder):
        mgr = _make_mgr(db_a, sync_folder)
        # Write more than MAX_HISTORY_ENTRIES
        for i in range(55):
            mgr.log_sync_event("export", {"index": i})

        history = mgr.get_sync_history(limit=100)
        assert len(history) <= mgr.MAX_HISTORY_ENTRIES

    def test_history_persists_across_instances(
        self, db_a, sync_folder
    ):
        mgr1 = _make_mgr(db_a, sync_folder)
        mgr1.log_sync_event("export")

        mgr2 = _make_mgr(db_a, sync_folder)
        history = mgr2.get_sync_history()
        assert len(history) == 1

    def test_empty_history(self, db_a, sync_folder):
        mgr = _make_mgr(db_a, sync_folder)
        history = mgr.get_sync_history()
        assert history == []

    def test_event_has_timestamp(self, db_a, sync_folder):
        mgr = _make_mgr(db_a, sync_folder)
        mgr.log_sync_event("conflict")

        history = mgr.get_sync_history()
        assert "timestamp" in history[0]
        assert len(history[0]["timestamp"]) > 10  # ISO format
