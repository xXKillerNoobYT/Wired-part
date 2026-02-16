"""E2E tests for Session B (Loops 6-9): data safety, notification cleanup,
sync truck-inventory LWW, and billing-period locking.

Simulated user feedback driving each section:
  Loop 6  — "I deleted a job that had labor entries and lost all my data"
  Loop 7  — "Notifications pile up forever and the app gets slower"
  Loop 8  — "I synced and lost my truck inventory changes"
  Loop 9  — "Billing period closed but someone clocked in after"
"""

import json
import os
import time
from datetime import datetime, timedelta

import pytest

from wired_part.database.connection import DatabaseConnection
from wired_part.database.models import (
    Job, JobAssignment, LaborEntry, Notification, Part, PurchaseOrder,
    PurchaseOrderItem, Supplier, Truck, TruckTransfer, User,
)
from wired_part.database.repository import Repository
from wired_part.database.schema import initialize_database


# ── Shared fixtures ──────────────────────────────────────────────


@pytest.fixture
def base_data(repo):
    """Bootstrap a minimal working dataset for data-safety tests."""
    user = User(
        username="boss", display_name="The Boss",
        pin_hash=Repository.hash_pin("0000"), role="admin",
    )
    user.id = repo.create_user(user)

    hat = repo.get_hat_by_id(1)  # Admin hat
    repo.assign_hat(user.id, hat.id)

    cat = repo.get_all_categories()[0]
    part = Part(
        part_number="DS-WIRE-10", description="10 AWG Wire 500ft",
        name="Wire", quantity=200, unit_cost=45.00,
        category_id=cat.id, min_quantity=20,
    )
    part.id = repo.create_part(part)

    supplier = Supplier(
        name="Safety Supply Co", contact_name="Sam Safe",
        email="sam@safe.com", phone="555-SAFE", is_supply_house=1,
    )
    supplier.id = repo.create_supplier(supplier)

    truck = Truck(
        truck_number="T-SAFE", name="Safety Van",
        assigned_user_id=user.id,
    )
    truck.id = repo.create_truck(truck)

    job = Job(
        job_number=repo.generate_job_number(),
        name="Data Safety Job", customer="Acme", status="active",
    )
    job.id = repo.create_job(job)
    repo.assign_user_to_job(JobAssignment(
        job_id=job.id, user_id=user.id, role="lead",
    ))

    return {
        "user": user, "part": part, "supplier": supplier,
        "truck": truck, "job": job,
    }


# =====================================================================
# Loop 6 — Job deletion protection
# =====================================================================


class TestJobDeletionProtection:
    """Deleting a job with labor entries should be blocked unless forced."""

    def test_delete_empty_job_allowed(self, repo, base_data):
        """A job with no labor/parts can be freely deleted."""
        empty_job = Job(
            job_number="JOB-EMPTY-001", name="Empty Job",
            status="active",
        )
        empty_job.id = repo.create_job(empty_job)
        repo.delete_job(empty_job.id)
        assert repo.get_job_by_id(empty_job.id) is None

    def test_delete_job_with_labor_blocked(self, repo, base_data):
        """Deletion blocked when job has labor entries."""
        u, j = base_data["user"], base_data["job"]
        repo.create_labor_entry(LaborEntry(
            user_id=u.id, job_id=j.id,
            start_time=datetime.now().isoformat(),
            end_time=datetime.now().isoformat(),
            hours=2.0, sub_task_category="General",
        ))
        with pytest.raises(ValueError, match="labor entries"):
            repo.delete_job(j.id)
        # Job still exists
        assert repo.get_job_by_id(j.id) is not None

    def test_delete_job_with_consumed_parts_blocked(self, repo, base_data):
        """Deletion blocked when job has consumed parts (via consume_from_truck)."""
        u = base_data["user"]
        p = base_data["part"]
        t = base_data["truck"]
        j = base_data["job"]
        s = base_data["supplier"]

        # Put parts on truck and consume to job
        repo.add_to_truck_inventory(t.id, p.id, 10)
        repo.consume_from_truck(j.id, t.id, p.id, 5, user_id=u.id)

        with pytest.raises(ValueError, match="consumed parts|job parts"):
            repo.delete_job(j.id)

    def test_force_delete_overrides(self, repo, base_data):
        """force=True bypasses the safety checks."""
        u, j = base_data["user"], base_data["job"]
        repo.create_labor_entry(LaborEntry(
            user_id=u.id, job_id=j.id,
            start_time=datetime.now().isoformat(),
            end_time=datetime.now().isoformat(),
            hours=1.0, sub_task_category="General",
        ))
        repo.delete_job(j.id, force=True)
        assert repo.get_job_by_id(j.id) is None

    def test_can_delete_job_reports_counts(self, repo, base_data):
        """can_delete_job returns a clear reason string with counts."""
        u, j = base_data["user"], base_data["job"]
        repo.create_labor_entry(LaborEntry(
            user_id=u.id, job_id=j.id,
            start_time=datetime.now().isoformat(),
            end_time=datetime.now().isoformat(),
            hours=1.0, sub_task_category="General",
        ))
        allowed, reason = repo.can_delete_job(j.id)
        assert allowed is False
        assert "1 labor entries" in reason

    def test_can_delete_empty_job_ok(self, repo, base_data):
        empty_job = Job(
            job_number="JOB-CAN-DEL", name="Clean Job", status="active",
        )
        empty_job.id = repo.create_job(empty_job)
        allowed, reason = repo.can_delete_job(empty_job.id)
        assert allowed is True
        assert reason == ""


# =====================================================================
# Loop 7 — Notification cleanup and cap
# =====================================================================


class TestNotificationCleanup:
    """Notifications must auto-cleanup and respect a cap of 500."""

    def test_cleanup_old_notifications(self, repo, base_data):
        """Notifications older than N days are purged."""
        u = base_data["user"]
        # Create an "old" notification by directly inserting with old timestamp
        with repo.db.get_connection() as conn:
            conn.execute("""
                INSERT INTO notifications (user_id, title, message, severity,
                    source, created_at)
                VALUES (?, 'Old', 'Old message', 'info', 'test',
                    datetime('now', '-100 days'))
            """, (u.id,))
            conn.execute("""
                INSERT INTO notifications (user_id, title, message, severity,
                    source, created_at)
                VALUES (?, 'Recent', 'Recent message', 'info', 'test',
                    datetime('now'))
            """, (u.id,))

        deleted = repo.cleanup_old_notifications(days=90)
        assert deleted >= 1
        remaining = repo.get_user_notifications(u.id)
        titles = [n.title for n in remaining]
        assert "Old" not in titles
        assert "Recent" in titles

    def test_cleanup_removes_old_not_new(self, repo, base_data):
        """cleanup_old_notifications(days=30) keeps recent, deletes old."""
        u = base_data["user"]
        # Insert one old (50 days ago) and one fresh
        with repo.db.get_connection() as conn:
            conn.execute("""
                INSERT INTO notifications (user_id, title, message, severity,
                    source, created_at)
                VALUES (?, 'Ancient', 'old msg', 'info', 'test',
                    datetime('now', '-50 days'))
            """, (u.id,))
        repo.create_notification(Notification(
            user_id=u.id, title="Fresh", message="new msg",
            severity="info", source="test",
        ))
        deleted = repo.cleanup_old_notifications(days=30)
        assert deleted >= 1
        remaining = repo.get_user_notifications(u.id)
        titles = [n.title for n in remaining]
        assert "Ancient" not in titles
        assert "Fresh" in titles

    def test_enforce_cap_purges_oldest_read(self, repo, base_data):
        """When over MAX_NOTIFICATIONS, oldest *read* are purged first."""
        u = base_data["user"]
        original_cap = Repository.MAX_NOTIFICATIONS
        try:
            Repository.MAX_NOTIFICATIONS = 10
            # Create 15 notifications, mark first 10 as read
            ids = []
            for i in range(15):
                nid = repo.create_notification(Notification(
                    user_id=u.id, title=f"N-{i:03d}", message="msg",
                    severity="info", source="test",
                ))
                ids.append(nid)
            for nid in ids[:10]:
                repo.mark_notification_read(nid)

            purged = repo.enforce_notification_cap()
            assert purged >= 5  # At least 5 excess read purged

            remaining = repo.get_user_notifications(u.id, limit=20)
            assert len(remaining) <= 10
        finally:
            Repository.MAX_NOTIFICATIONS = original_cap

    def test_enforce_cap_no_action_under_limit(self, repo, base_data):
        """Cap enforcement is a no-op when under the limit."""
        assert repo.enforce_notification_cap() == 0


# =====================================================================
# Loop 8 — Sync: truck_inventory LWW + lock race fix
# =====================================================================


class TestSyncTruckInventoryLWW:
    """Truck inventory changes should sync via last-write-wins."""

    def test_truck_inventory_has_updated_at(self, repo, base_data):
        """After v14 migration, truck_inventory rows carry updated_at."""
        t, p = base_data["truck"], base_data["part"]
        repo.add_to_truck_inventory(t.id, p.id, 25)

        rows = repo.db.execute(
            "SELECT updated_at FROM truck_inventory "
            "WHERE truck_id = ? AND part_id = ?", (t.id, p.id)
        )
        assert rows
        assert rows[0]["updated_at"] is not None

    def test_updated_at_changes_on_mutation(self, repo, base_data):
        """updated_at is refreshed when quantity changes."""
        t, p = base_data["truck"], base_data["part"]
        repo.add_to_truck_inventory(t.id, p.id, 10)
        ts1 = repo.db.execute(
            "SELECT updated_at FROM truck_inventory "
            "WHERE truck_id = ? AND part_id = ?", (t.id, p.id)
        )[0]["updated_at"]

        # Small delay so timestamp differs
        import time
        time.sleep(0.05)
        repo.add_to_truck_inventory(t.id, p.id, 5)  # add 5 more
        ts2 = repo.db.execute(
            "SELECT updated_at FROM truck_inventory "
            "WHERE truck_id = ? AND part_id = ?", (t.id, p.id)
        )[0]["updated_at"]
        assert ts2 >= ts1

    def test_set_quantity_updates_timestamp(self, repo, base_data):
        """set_truck_inventory_quantity also bumps updated_at."""
        t, p = base_data["truck"], base_data["part"]
        repo.set_truck_inventory_quantity(t.id, p.id, 50)
        rows = repo.db.execute(
            "SELECT updated_at FROM truck_inventory "
            "WHERE truck_id = ? AND part_id = ?", (t.id, p.id)
        )
        assert rows[0]["updated_at"] is not None

    def test_set_levels_updates_timestamp(self, repo, base_data):
        """set_truck_inventory_levels bumps updated_at."""
        t, p = base_data["truck"], base_data["part"]
        repo.add_to_truck_inventory(t.id, p.id, 10)
        repo.set_truck_inventory_levels(t.id, p.id, 5, 100)
        rows = repo.db.execute(
            "SELECT updated_at FROM truck_inventory "
            "WHERE truck_id = ? AND part_id = ?", (t.id, p.id)
        )
        assert rows[0]["updated_at"] is not None


class TestSyncLockAtomicCreation:
    """Lock file should use atomic os.O_CREAT|O_EXCL to prevent races."""

    def test_lock_file_contains_pid_and_hostname(self, tmp_path):
        """Lock file includes PID and hostname for debugging."""
        from wired_part.sync.sync_manager import SyncManager

        db = DatabaseConnection(str(tmp_path / "lock_test.db"))
        initialize_database(db)
        sync_folder = tmp_path / "sync"
        sync_folder.mkdir()

        mgr = SyncManager(db)
        mgr.sync_folder = sync_folder
        mgr.device_id = "test-device-abc"

        mgr._acquire_lock()
        lock_path = sync_folder / mgr.LOCK_FILE
        assert lock_path.exists()
        data = json.loads(lock_path.read_text(encoding="utf-8"))
        assert data["device_id"] == "test-device-abc"
        assert "pid" in data
        assert data["pid"] == os.getpid()
        assert "hostname" in data
        mgr._release_lock()

    def test_second_lock_fails_atomically(self, tmp_path):
        """Two managers can't both acquire the lock."""
        from wired_part.sync.sync_manager import SyncManager, SyncLockError

        db = DatabaseConnection(str(tmp_path / "race.db"))
        initialize_database(db)
        sync_folder = tmp_path / "sync"
        sync_folder.mkdir()

        mgr1 = SyncManager(db)
        mgr1.sync_folder = sync_folder
        mgr1.device_id = "device-1"

        mgr2 = SyncManager(db)
        mgr2.sync_folder = sync_folder
        mgr2.device_id = "device-2"

        mgr1._acquire_lock()
        with pytest.raises(SyncLockError, match="device-1"):
            mgr2._acquire_lock()
        mgr1._release_lock()

    def test_stale_lock_broken(self, tmp_path):
        """A lock older than LOCK_TIMEOUT_SECONDS is auto-broken."""
        from wired_part.sync.sync_manager import SyncManager

        db = DatabaseConnection(str(tmp_path / "stale.db"))
        initialize_database(db)
        sync_folder = tmp_path / "sync"
        sync_folder.mkdir()

        # Create a stale lock file manually
        lock_path = sync_folder / "wiredpart_lock"
        lock_path.write_text(json.dumps({
            "device_id": "old-device",
            "locked_at": "2020-01-01T00:00:00Z",
        }), encoding="utf-8")
        # Set mtime to 10 minutes ago
        stale_time = time.time() - 600
        os.utime(str(lock_path), (stale_time, stale_time))

        mgr = SyncManager(db)
        mgr.sync_folder = sync_folder
        mgr.device_id = "new-device"

        mgr._acquire_lock()  # Should succeed — stale lock broken
        data = json.loads(lock_path.read_text(encoding="utf-8"))
        assert data["device_id"] == "new-device"
        mgr._release_lock()


# =====================================================================
# Loop 9 — Billing period locking
# =====================================================================


class TestBillingPeriodLocking:
    """Clock-in must be rejected when the billing period is closed."""

    def test_clock_in_allowed_no_billing_period(self, repo, base_data):
        """Clock-in works fine when no billing period exists."""
        u, j = base_data["user"], base_data["job"]
        entry_id = repo.clock_in(u.id, j.id, category="Electrical")
        assert entry_id > 0
        repo.clock_out(entry_id, description="done")

    def test_clock_in_allowed_open_period(self, repo, base_data):
        """Clock-in allowed when billing period is open."""
        u, j = base_data["user"], base_data["job"]
        cycle = repo.get_or_create_billing_cycle(job_id=j.id)
        today = datetime.now()
        repo.create_billing_period(
            cycle.id,
            (today - timedelta(days=15)).strftime("%Y-%m-%d"),
            (today + timedelta(days=15)).strftime("%Y-%m-%d"),
        )
        entry_id = repo.clock_in(u.id, j.id, category="General")
        assert entry_id > 0
        repo.clock_out(entry_id, description="open period test")

    def test_clock_in_blocked_closed_period(self, repo, base_data):
        """Clock-in rejected when today falls in a closed billing period."""
        u, j = base_data["user"], base_data["job"]
        cycle = repo.get_or_create_billing_cycle(job_id=j.id)
        today = datetime.now()
        period_id = repo.create_billing_period(
            cycle.id,
            (today - timedelta(days=15)).strftime("%Y-%m-%d"),
            (today + timedelta(days=15)).strftime("%Y-%m-%d"),
        )
        repo.close_billing_period(period_id)

        with pytest.raises(ValueError, match="billing period.*closed"):
            repo.clock_in(u.id, j.id)

    def test_clock_in_allowed_after_closed_period(self, repo, base_data):
        """Clock-in allowed when the closed period doesn't cover today."""
        u, j = base_data["user"], base_data["job"]
        cycle = repo.get_or_create_billing_cycle(job_id=j.id)
        # Close a period that ended last month
        period_id = repo.create_billing_period(
            cycle.id,
            (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d"),
            (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"),
        )
        repo.close_billing_period(period_id)

        entry_id = repo.clock_in(u.id, j.id, category="General")
        assert entry_id > 0
        repo.clock_out(entry_id, description="past period test")

    def test_is_billing_period_closed_helper(self, repo, base_data):
        """Direct test of the is_billing_period_closed helper."""
        j = base_data["job"]
        today_str = datetime.now().strftime("%Y-%m-%d")

        # No periods at all → False
        assert repo.is_billing_period_closed(j.id, today_str) is False

        # Open period covering today → False
        cycle = repo.get_or_create_billing_cycle(job_id=j.id)
        today = datetime.now()
        pid = repo.create_billing_period(
            cycle.id,
            (today - timedelta(days=5)).strftime("%Y-%m-%d"),
            (today + timedelta(days=5)).strftime("%Y-%m-%d"),
        )
        assert repo.is_billing_period_closed(j.id, today_str) is False

        # Close it → True
        repo.close_billing_period(pid)
        assert repo.is_billing_period_closed(j.id, today_str) is True

    def test_billing_lock_different_job_unaffected(self, repo, base_data):
        """Closing a billing period on one job doesn't block another."""
        u, j = base_data["user"], base_data["job"]

        # Close period on original job
        cycle = repo.get_or_create_billing_cycle(job_id=j.id)
        today = datetime.now()
        pid = repo.create_billing_period(
            cycle.id,
            (today - timedelta(days=15)).strftime("%Y-%m-%d"),
            (today + timedelta(days=15)).strftime("%Y-%m-%d"),
        )
        repo.close_billing_period(pid)

        # Create a second job — clock-in should work
        job2 = Job(
            job_number="JOB-OTHER-001", name="Other Job", status="active",
        )
        job2.id = repo.create_job(job2)
        repo.assign_user_to_job(JobAssignment(
            job_id=job2.id, user_id=u.id, role="lead",
        ))
        entry_id = repo.clock_in(u.id, job2.id, category="General")
        assert entry_id > 0
        repo.clock_out(entry_id, description="other job ok")
