"""E2E tests: labor, BRO snapshot, job reactivation, date filtering,
deprecation with job_quantity, and BRO deletion protection.

These tests exercise full business flows that span multiple repository
methods and verify data integrity across multi-step operations.
"""

import pytest
from datetime import datetime, timedelta

from wired_part.database.models import (
    Job, JobAssignment, JobPart, LaborEntry, Part, User,
)
from wired_part.database.repository import Repository


# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def labor_user(repo):
    """User for labor tests."""
    user = User(
        username="labor_e2e",
        display_name="E2E Worker",
        pin_hash=Repository.hash_pin("1234"),
        role="user", is_active=1,
    )
    user.id = repo.create_user(user)
    return user


@pytest.fixture
def second_user(repo):
    """Second user for multi-user tests."""
    user = User(
        username="labor_e2e_2",
        display_name="E2E Worker 2",
        pin_hash=Repository.hash_pin("5678"),
        role="user", is_active=1,
    )
    user.id = repo.create_user(user)
    return user


@pytest.fixture
def bro_job(repo, labor_user):
    """Active job with a BRO category."""
    job = Job(
        job_number="BRO-E2E-001",
        name="BRO E2E Job",
        customer="Test Corp",
        status="active",
        bill_out_rate="T&M",
    )
    job.id = repo.create_job(job)
    repo.assign_user_to_job(JobAssignment(
        job_id=job.id, user_id=labor_user.id, role="lead",
    ))
    return job


@pytest.fixture
def second_job(repo, labor_user):
    """Second active job with different BRO."""
    job = Job(
        job_number="BRO-E2E-002",
        name="Service Call Job",
        customer="Another Client",
        status="active",
        bill_out_rate="SERVICE",
    )
    job.id = repo.create_job(job)
    repo.assign_user_to_job(JobAssignment(
        job_id=job.id, user_id=labor_user.id, role="lead",
    ))
    return job


@pytest.fixture
def dep_part(repo):
    """Part for deprecation tests with warehouse stock."""
    part = Part(
        part_number="DEP-E2E-001",
        name="E2E Deprecated Widget",
        description="Widget for E2E deprecation",
        quantity=25,
        unit_cost=5.0,
    )
    part.id = repo.create_part(part)
    return part


# ═══════════════════════════════════════════════════════════════════
# LABOR CLOCK-IN / CLOCK-OUT END-TO-END
# ═══════════════════════════════════════════════════════════════════


class TestLaborClockWorkflow:
    """Full clock-in → work → clock-out workflow."""

    def test_full_clock_cycle(self, repo, labor_user, bro_job):
        """Clock in → clock out → verify entry has hours and description."""
        eid = repo.clock_in(
            user_id=labor_user.id,
            job_id=bro_job.id,
            category="Rough-in",
        )
        assert eid > 0

        # Verify active clock-in exists
        active = repo.get_active_clock_in(labor_user.id)
        assert active is not None
        assert active.end_time is None
        assert active.sub_task_category == "Rough-in"

        # Clock out
        result = repo.clock_out(
            eid, description="Ran wire from panel to bedroom"
        )
        assert result is not None
        assert result.end_time is not None
        assert result.hours >= 0
        assert result.description == "Ran wire from panel to bedroom"

        # No active clock-in anymore
        assert repo.get_active_clock_in(labor_user.id) is None

    def test_clock_in_with_gps_then_clock_out_with_gps(
        self, repo, labor_user, bro_job,
    ):
        """Both clock-in and clock-out capture GPS coordinates."""
        eid = repo.clock_in(
            user_id=labor_user.id,
            job_id=bro_job.id,
            category="Testing",
            lat=40.7128, lon=-74.0060,
        )
        result = repo.clock_out(
            eid, lat=40.7130, lon=-74.0055,
            description="Tested circuits",
        )
        entry = repo.get_labor_entry_by_id(eid)

        assert entry.clock_in_lat == 40.7128
        assert entry.clock_in_lon == -74.0060
        assert entry.clock_out_lat == 40.7130
        assert entry.clock_out_lon == -74.0055

    def test_prevents_double_clock_in(self, repo, labor_user, bro_job):
        """Cannot clock in when already clocked in."""
        repo.clock_in(
            user_id=labor_user.id,
            job_id=bro_job.id,
        )
        with pytest.raises(ValueError, match="Already clocked in"):
            repo.clock_in(
                user_id=labor_user.id,
                job_id=bro_job.id,
            )

    def test_clock_in_creates_notification(self, repo, labor_user, bro_job):
        """Clock-in broadcasts a notification."""
        repo.clock_in(
            user_id=labor_user.id,
            job_id=bro_job.id,
            category="Rough-in",
        )
        # Notifications are broadcast (user_id=None), query for this user
        notifs = repo.get_user_notifications(labor_user.id, limit=10)
        clock_notifs = [n for n in notifs if "clocked in" in n.message.lower()]
        assert len(clock_notifs) >= 1
        assert "E2E Worker" in clock_notifs[0].message

    def test_multi_user_clock_independently(
        self, repo, labor_user, second_user, bro_job,
    ):
        """Two users can clock in to the same job simultaneously."""
        # Assign second user
        repo.assign_user_to_job(JobAssignment(
            job_id=bro_job.id, user_id=second_user.id, role="worker",
        ))

        eid1 = repo.clock_in(
            user_id=labor_user.id, job_id=bro_job.id, category="Rough-in",
        )
        eid2 = repo.clock_in(
            user_id=second_user.id, job_id=bro_job.id, category="Testing",
        )
        assert eid1 != eid2

        # Both have active clock-ins
        assert repo.get_active_clock_in(labor_user.id) is not None
        assert repo.get_active_clock_in(second_user.id) is not None

        # Clock both out
        repo.clock_out(eid1, description="User 1 work")
        repo.clock_out(eid2, description="User 2 work")

        assert repo.get_active_clock_in(labor_user.id) is None
        assert repo.get_active_clock_in(second_user.id) is None

    def test_clock_in_different_jobs_sequentially(
        self, repo, labor_user, bro_job, second_job,
    ):
        """Clock in to job A, clock out, clock in to job B."""
        eid1 = repo.clock_in(
            user_id=labor_user.id, job_id=bro_job.id, category="Rough-in",
        )
        repo.clock_out(eid1, description="Job A done")

        eid2 = repo.clock_in(
            user_id=labor_user.id, job_id=second_job.id,
            category="Service Call",
        )
        repo.clock_out(eid2, description="Job B done")

        # Both entries exist
        entries_a = repo.get_labor_entries_for_job(bro_job.id)
        entries_b = repo.get_labor_entries_for_job(second_job.id)
        assert len(entries_a) == 1
        assert len(entries_b) == 1


# ═══════════════════════════════════════════════════════════════════
# BRO SNAPSHOT ON LABOR ENTRIES
# ═══════════════════════════════════════════════════════════════════


class TestBROSnapshot:
    """When creating labor entries, the job's BRO is snapshotted.
    Changing the job's BRO later must NOT alter existing entries."""

    def test_labor_entry_captures_job_bro(self, repo, labor_user, bro_job):
        """New labor entry snapshots the job's current BRO (T&M)."""
        eid = repo.create_labor_entry(LaborEntry(
            user_id=labor_user.id,
            job_id=bro_job.id,
            start_time=datetime.now().isoformat(),
            hours=3.0,
            sub_task_category="Rough-in",
        ))
        entry = repo.get_labor_entry_by_id(eid)
        assert entry.bill_out_rate == "T&M"

    def test_bro_snapshot_preserved_after_job_bro_change(
        self, repo, labor_user, bro_job,
    ):
        """Changing the job's BRO does NOT alter existing labor entries."""
        # Create entry when job BRO is "T&M"
        eid = repo.create_labor_entry(LaborEntry(
            user_id=labor_user.id,
            job_id=bro_job.id,
            start_time=datetime.now().isoformat(),
            hours=4.0,
            sub_task_category="Rough-in",
        ))

        # Change job BRO to "SERVICE"
        job = repo.get_job_by_id(bro_job.id)
        job.bill_out_rate = "SERVICE"
        repo.update_job(job)

        # Old entry still has "T&M"
        old_entry = repo.get_labor_entry_by_id(eid)
        assert old_entry.bill_out_rate == "T&M"

        # New entry gets "SERVICE"
        eid2 = repo.create_labor_entry(LaborEntry(
            user_id=labor_user.id,
            job_id=bro_job.id,
            start_time=datetime.now().isoformat(),
            hours=2.0,
            sub_task_category="Testing",
        ))
        new_entry = repo.get_labor_entry_by_id(eid2)
        assert new_entry.bill_out_rate == "SERVICE"

    def test_clock_in_snapshots_bro(self, repo, labor_user, bro_job):
        """clock_in() also snapshots BRO via create_labor_entry."""
        eid = repo.clock_in(
            user_id=labor_user.id,
            job_id=bro_job.id,
            category="Rough-in",
        )
        entry = repo.get_labor_entry_by_id(eid)
        assert entry.bill_out_rate == "T&M"

    def test_bro_snapshot_clock_in_preserved_after_change(
        self, repo, labor_user, bro_job,
    ):
        """Clock in with BRO 'T&M', change job to 'C', clock out —
        the entry still shows 'T&M'."""
        eid = repo.clock_in(
            user_id=labor_user.id,
            job_id=bro_job.id,
            category="Rough-in",
        )

        # Change job BRO mid-shift
        job = repo.get_job_by_id(bro_job.id)
        job.bill_out_rate = "C"
        repo.update_job(job)

        # Clock out
        repo.clock_out(eid, description="Done")

        # Entry retains original "T&M" snapshot
        entry = repo.get_labor_entry_by_id(eid)
        assert entry.bill_out_rate == "T&M"

    def test_bro_snapshot_with_explicit_override(self, repo, labor_user, bro_job):
        """If entry provides its own bill_out_rate, that takes precedence."""
        eid = repo.create_labor_entry(LaborEntry(
            user_id=labor_user.id,
            job_id=bro_job.id,
            start_time=datetime.now().isoformat(),
            hours=1.5,
            bill_out_rate="EMERGENCY",  # Override the job's "T&M"
        ))
        entry = repo.get_labor_entry_by_id(eid)
        assert entry.bill_out_rate == "EMERGENCY"

    def test_bro_snapshot_empty_when_job_has_no_bro(self, repo, labor_user):
        """Entry gets empty BRO when job has no BRO set."""
        job = Job(
            job_number="NO-BRO-001", name="No BRO Job",
            status="active", bill_out_rate="",
        )
        job.id = repo.create_job(job)

        eid = repo.create_labor_entry(LaborEntry(
            user_id=labor_user.id,
            job_id=job.id,
            start_time=datetime.now().isoformat(),
            hours=2.0,
        ))
        entry = repo.get_labor_entry_by_id(eid)
        assert entry.bill_out_rate == ""

    def test_multiple_bro_changes_each_entry_keeps_its_snapshot(
        self, repo, labor_user, bro_job,
    ):
        """Three BRO changes → three entries each with their own snapshot."""
        entries = []
        for bro_val in ["T&M", "C", "EMERGENCY"]:
            job = repo.get_job_by_id(bro_job.id)
            job.bill_out_rate = bro_val
            repo.update_job(job)

            eid = repo.create_labor_entry(LaborEntry(
                user_id=labor_user.id,
                job_id=bro_job.id,
                start_time=datetime.now().isoformat(),
                hours=1.0,
            ))
            entries.append(eid)

        # Verify each entry has its own BRO snapshot
        assert repo.get_labor_entry_by_id(entries[0]).bill_out_rate == "T&M"
        assert repo.get_labor_entry_by_id(entries[1]).bill_out_rate == "C"
        assert repo.get_labor_entry_by_id(entries[2]).bill_out_rate == "EMERGENCY"


# ═══════════════════════════════════════════════════════════════════
# JOB REACTIVATION
# ═══════════════════════════════════════════════════════════════════


class TestJobReactivation:
    """Test reactivating completed/cancelled jobs."""

    def test_reactivate_completed_job(self, repo, labor_user, bro_job):
        """Complete a job, then reactivate it back to active."""
        # Complete the job
        job = repo.get_job_by_id(bro_job.id)
        job.status = "completed"
        repo.update_job(job)
        assert repo.get_job_by_id(bro_job.id).status == "completed"

        # Reactivate
        job = repo.get_job_by_id(bro_job.id)
        job.status = "active"
        repo.update_job(job)
        assert repo.get_job_by_id(bro_job.id).status == "active"

    def test_reactivate_cancelled_job(self, repo, labor_user, bro_job):
        """Cancel a job, then reactivate it."""
        job = repo.get_job_by_id(bro_job.id)
        job.status = "cancelled"
        repo.update_job(job)
        assert repo.get_job_by_id(bro_job.id).status == "cancelled"

        job = repo.get_job_by_id(bro_job.id)
        job.status = "active"
        repo.update_job(job)
        assert repo.get_job_by_id(bro_job.id).status == "active"

    def test_reactivate_on_hold_job(self, repo, labor_user, bro_job):
        """Put a job on hold, then reactivate it."""
        job = repo.get_job_by_id(bro_job.id)
        job.status = "on_hold"
        repo.update_job(job)

        job = repo.get_job_by_id(bro_job.id)
        job.status = "active"
        repo.update_job(job)
        assert repo.get_job_by_id(bro_job.id).status == "active"

    def test_labor_entries_accessible_after_reactivation(
        self, repo, labor_user, bro_job,
    ):
        """Labor entries from before completion are still accessible."""
        # Create labor entry
        eid = repo.create_labor_entry(LaborEntry(
            user_id=labor_user.id,
            job_id=bro_job.id,
            start_time=datetime.now().isoformat(),
            hours=5.0,
            sub_task_category="Rough-in",
        ))

        # Complete the job
        job = repo.get_job_by_id(bro_job.id)
        job.status = "completed"
        repo.update_job(job)

        # Reactivate
        job = repo.get_job_by_id(bro_job.id)
        job.status = "active"
        repo.update_job(job)

        # Old entry is still there
        entry = repo.get_labor_entry_by_id(eid)
        assert entry is not None
        assert entry.hours == 5.0

        # Can get entries for the job
        entries = repo.get_labor_entries_for_job(bro_job.id)
        assert len(entries) == 1

    def test_can_clock_in_after_reactivation(
        self, repo, labor_user, bro_job,
    ):
        """After reactivating a completed job, users can clock in."""
        # Complete → Reactivate
        job = repo.get_job_by_id(bro_job.id)
        job.status = "completed"
        repo.update_job(job)

        job = repo.get_job_by_id(bro_job.id)
        job.status = "active"
        repo.update_job(job)

        # Clock in should work
        eid = repo.clock_in(
            user_id=labor_user.id,
            job_id=bro_job.id,
            category="Service Call",
        )
        assert eid > 0
        repo.clock_out(eid, description="Post-reactivation work")

    def test_reactivate_changes_bro_new_entries_get_new_bro(
        self, repo, labor_user, bro_job,
    ):
        """Reactivate a completed job, change BRO, new entries get new BRO,
        old entries keep old BRO."""
        # Entry with original BRO "T&M"
        eid_old = repo.create_labor_entry(LaborEntry(
            user_id=labor_user.id,
            job_id=bro_job.id,
            start_time=(datetime.now() - timedelta(days=365)).isoformat(),
            hours=8.0,
            sub_task_category="Rough-in",
        ))

        # Complete → Reactivate → Change BRO
        job = repo.get_job_by_id(bro_job.id)
        job.status = "completed"
        repo.update_job(job)

        job = repo.get_job_by_id(bro_job.id)
        job.status = "active"
        job.bill_out_rate = "SERVICE"
        repo.update_job(job)

        # New entry with new BRO
        eid_new = repo.create_labor_entry(LaborEntry(
            user_id=labor_user.id,
            job_id=bro_job.id,
            start_time=datetime.now().isoformat(),
            hours=3.0,
            sub_task_category="Service Call",
        ))

        # Old keeps "T&M", new gets "SERVICE"
        assert repo.get_labor_entry_by_id(eid_old).bill_out_rate == "T&M"
        assert repo.get_labor_entry_by_id(eid_new).bill_out_rate == "SERVICE"

    def test_parts_on_job_preserved_after_reactivation(
        self, repo, labor_user, bro_job, dep_part,
    ):
        """Parts assigned to a job are preserved through completion
        and reactivation."""
        # Assign part to job
        repo.assign_part_to_job(JobPart(
            part_id=dep_part.id,
            job_id=bro_job.id,
            quantity_used=5,
        ))
        assert len(repo.get_job_parts(bro_job.id)) == 1

        # Complete → Reactivate
        job = repo.get_job_by_id(bro_job.id)
        job.status = "completed"
        repo.update_job(job)

        job = repo.get_job_by_id(bro_job.id)
        job.status = "active"
        repo.update_job(job)

        # Parts still there
        job_parts = repo.get_job_parts(bro_job.id)
        assert len(job_parts) == 1
        assert job_parts[0].quantity_used == 5


# ═══════════════════════════════════════════════════════════════════
# BRO DELETION PROTECTION
# ═══════════════════════════════════════════════════════════════════


class TestBRODeletionProtection:
    """BRO categories cannot be deleted if active/on-hold jobs use them.

    Note: The actual protection is in the UI (settings_page._bro_remove),
    so we test the underlying query logic here — can we detect active jobs
    using a BRO category?
    """

    def test_detect_active_jobs_using_bro(self, repo, bro_job):
        """Can find active jobs that use a specific BRO category."""
        all_jobs = repo.get_all_jobs()
        active_with_bro = [
            j for j in all_jobs
            if j.bill_out_rate == "T&M"
            and j.status in ("active", "on_hold")
        ]
        assert len(active_with_bro) >= 1
        assert any(j.id == bro_job.id for j in active_with_bro)

    def test_no_active_jobs_allows_bro_removal(self, repo, bro_job):
        """If no active/on-hold jobs use a BRO, it can be removed."""
        # Complete the job so BRO "T&M" is no longer on an active job
        job = repo.get_job_by_id(bro_job.id)
        job.status = "completed"
        repo.update_job(job)

        all_jobs = repo.get_all_jobs()
        active_with_bro = [
            j for j in all_jobs
            if j.bill_out_rate == "T&M"
            and j.status in ("active", "on_hold")
        ]
        assert len(active_with_bro) == 0  # Safe to remove

    def test_on_hold_job_blocks_bro_removal(self, repo, bro_job):
        """On-hold jobs also block BRO removal."""
        job = repo.get_job_by_id(bro_job.id)
        job.status = "on_hold"
        repo.update_job(job)

        all_jobs = repo.get_all_jobs()
        on_hold_with_bro = [
            j for j in all_jobs
            if j.bill_out_rate == "T&M"
            and j.status in ("active", "on_hold")
        ]
        assert len(on_hold_with_bro) >= 1

    def test_completed_job_does_not_block_bro_removal(self, repo, bro_job):
        """Completed jobs do NOT block BRO removal."""
        job = repo.get_job_by_id(bro_job.id)
        job.status = "completed"
        repo.update_job(job)

        all_jobs = repo.get_all_jobs()
        blocking = [
            j for j in all_jobs
            if j.bill_out_rate == "T&M"
            and j.status in ("active", "on_hold")
        ]
        assert len(blocking) == 0

    def test_cancelled_job_does_not_block_bro_removal(self, repo, bro_job):
        """Cancelled jobs do NOT block BRO removal."""
        job = repo.get_job_by_id(bro_job.id)
        job.status = "cancelled"
        repo.update_job(job)

        all_jobs = repo.get_all_jobs()
        blocking = [
            j for j in all_jobs
            if j.bill_out_rate == "T&M"
            and j.status in ("active", "on_hold")
        ]
        assert len(blocking) == 0

    def test_different_bro_does_not_block(self, repo, bro_job, second_job):
        """Active jobs with a different BRO don't block deletion of 'T&M'."""
        # second_job has BRO "SERVICE", bro_job has "T&M"
        # Complete bro_job
        job = repo.get_job_by_id(bro_job.id)
        job.status = "completed"
        repo.update_job(job)

        all_jobs = repo.get_all_jobs()
        blocking_tm = [
            j for j in all_jobs
            if j.bill_out_rate == "T&M"
            and j.status in ("active", "on_hold")
        ]
        # Only completed bro_job had T&M, so it doesn't block
        assert len(blocking_tm) == 0

        # But SERVICE is still blocked (second_job is active)
        blocking_service = [
            j for j in all_jobs
            if j.bill_out_rate == "SERVICE"
            and j.status in ("active", "on_hold")
        ]
        assert len(blocking_service) >= 1


# ═══════════════════════════════════════════════════════════════════
# DATE FILTERING WITH END-OF-DAY BOUNDARY
# ═══════════════════════════════════════════════════════════════════


class TestDateFiltering:
    """Test that date filters correctly include entries at end-of-day."""

    def test_entries_on_end_date_included(self, repo, labor_user, bro_job):
        """Entries with time on the date_to day are included."""
        today = datetime.now()
        today_str = today.strftime("%Y-%m-%d")

        # Create entry with a specific datetime today
        eid = repo.create_labor_entry(LaborEntry(
            user_id=labor_user.id,
            job_id=bro_job.id,
            start_time=today.replace(hour=14, minute=30).isoformat(),
            hours=3.0,
            sub_task_category="Rough-in",
        ))

        # Filter using date-only string (no time component)
        entries = repo.get_labor_entries_for_job(
            bro_job.id,
            date_from=today_str,
            date_to=today_str,
        )
        assert len(entries) >= 1
        assert any(e.id == eid for e in entries)

    def test_entries_on_start_date_included(self, repo, labor_user, bro_job):
        """Entries at the start of date_from are included."""
        today = datetime.now()
        today_str = today.strftime("%Y-%m-%d")

        eid = repo.create_labor_entry(LaborEntry(
            user_id=labor_user.id,
            job_id=bro_job.id,
            start_time=today.replace(hour=0, minute=1).isoformat(),
            hours=1.0,
        ))

        entries = repo.get_labor_entries_for_job(
            bro_job.id,
            date_from=today_str,
            date_to=today_str,
        )
        assert any(e.id == eid for e in entries)

    def test_entries_outside_range_excluded(self, repo, labor_user, bro_job):
        """Entries outside the date range are excluded."""
        yesterday = datetime.now() - timedelta(days=1)
        tomorrow = datetime.now() + timedelta(days=1)

        repo.create_labor_entry(LaborEntry(
            user_id=labor_user.id,
            job_id=bro_job.id,
            start_time=yesterday.isoformat(),
            hours=2.0,
        ))
        repo.create_labor_entry(LaborEntry(
            user_id=labor_user.id,
            job_id=bro_job.id,
            start_time=tomorrow.isoformat(),
            hours=3.0,
        ))

        today_str = datetime.now().strftime("%Y-%m-%d")
        entries = repo.get_labor_entries_for_job(
            bro_job.id,
            date_from=today_str,
            date_to=today_str,
        )
        # Neither yesterday nor tomorrow entries should appear
        for e in entries:
            assert today_str in str(e.start_time)

    def test_date_range_spanning_multiple_days(self, repo, labor_user, bro_job):
        """Multi-day range captures all entries within range."""
        base = datetime.now()
        ids = []
        for offset in range(-3, 4):  # -3 to +3 days
            day = base + timedelta(days=offset)
            eid = repo.create_labor_entry(LaborEntry(
                user_id=labor_user.id,
                job_id=bro_job.id,
                start_time=day.isoformat(),
                hours=1.0,
            ))
            ids.append((offset, eid))

        # Filter for "today - 1" to "today + 1" (3 days)
        d_from = (base - timedelta(days=1)).strftime("%Y-%m-%d")
        d_to = (base + timedelta(days=1)).strftime("%Y-%m-%d")
        entries = repo.get_labor_entries_for_job(
            bro_job.id, date_from=d_from, date_to=d_to,
        )
        entry_ids = {e.id for e in entries}

        # Should include offset -1, 0, +1 but not -3, -2, +2, +3
        for offset, eid in ids:
            if -1 <= offset <= 1:
                assert eid in entry_ids, f"offset {offset} should be in range"
            elif abs(offset) >= 3:
                assert eid not in entry_ids, f"offset {offset} should be out"

    def test_user_entries_date_filtering(self, repo, labor_user, bro_job):
        """get_labor_entries_for_user also handles end-of-day correctly."""
        today = datetime.now()
        today_str = today.strftime("%Y-%m-%d")

        eid = repo.create_labor_entry(LaborEntry(
            user_id=labor_user.id,
            job_id=bro_job.id,
            start_time=today.replace(hour=17, minute=45).isoformat(),
            hours=1.5,
        ))

        entries = repo.get_labor_entries_for_user(
            labor_user.id,
            date_from=today_str,
            date_to=today_str,
        )
        assert any(e.id == eid for e in entries)


# ═══════════════════════════════════════════════════════════════════
# LABOR SUMMARY BY CATEGORY
# ═══════════════════════════════════════════════════════════════════


class TestLaborSummaryByCategory:
    """Verify the by_category summary uses sub_task_category key."""

    def test_by_category_structure(self, repo, labor_user, bro_job):
        """Each by_category item has sub_task_category, hours, entries."""
        for cat, hrs in [("Rough-in", 4.0), ("Testing", 2.0), ("Trim", 3.0)]:
            repo.create_labor_entry(LaborEntry(
                user_id=labor_user.id,
                job_id=bro_job.id,
                start_time=datetime.now().isoformat(),
                hours=hrs,
                sub_task_category=cat,
            ))

        summary = repo.get_labor_summary_for_job(bro_job.id)
        by_cat = summary["by_category"]
        assert len(by_cat) == 3

        # Each entry must have sub_task_category and hours keys
        for cat_row in by_cat:
            assert "sub_task_category" in cat_row
            assert "hours" in cat_row
            assert "entries" in cat_row

    def test_by_category_hours_correct(self, repo, labor_user, bro_job):
        """Hours are correctly summed per category."""
        repo.create_labor_entry(LaborEntry(
            user_id=labor_user.id, job_id=bro_job.id,
            start_time=datetime.now().isoformat(),
            hours=4.0, sub_task_category="Rough-in",
        ))
        repo.create_labor_entry(LaborEntry(
            user_id=labor_user.id, job_id=bro_job.id,
            start_time=datetime.now().isoformat(),
            hours=2.0, sub_task_category="Rough-in",
        ))
        repo.create_labor_entry(LaborEntry(
            user_id=labor_user.id, job_id=bro_job.id,
            start_time=datetime.now().isoformat(),
            hours=1.0, sub_task_category="Testing",
        ))

        summary = repo.get_labor_summary_for_job(bro_job.id)
        by_cat = {c["sub_task_category"]: c["hours"]
                  for c in summary["by_category"]}
        assert by_cat["Rough-in"] == 6.0
        assert by_cat["Testing"] == 1.0

    def test_by_user_structure(self, repo, labor_user, second_user, bro_job):
        """by_user summary correctly attributes hours."""
        repo.create_labor_entry(LaborEntry(
            user_id=labor_user.id, job_id=bro_job.id,
            start_time=datetime.now().isoformat(),
            hours=5.0,
        ))
        repo.create_labor_entry(LaborEntry(
            user_id=second_user.id, job_id=bro_job.id,
            start_time=datetime.now().isoformat(),
            hours=3.0,
        ))

        summary = repo.get_labor_summary_for_job(bro_job.id)
        by_user = {u["user_name"]: u["hours"] for u in summary["by_user"]}
        assert by_user["E2E Worker"] == 5.0
        assert by_user["E2E Worker 2"] == 3.0

    def test_empty_job_summary(self, repo, bro_job):
        """Empty job has zero hours and no categories."""
        summary = repo.get_labor_summary_for_job(bro_job.id)
        assert summary["total_hours"] == 0
        assert summary["entry_count"] == 0
        assert len(summary["by_category"]) == 0
        assert len(summary["by_user"]) == 0


# ═══════════════════════════════════════════════════════════════════
# DEPRECATION PIPELINE WITH JOB_QUANTITY
# ═══════════════════════════════════════════════════════════════════


class TestDeprecationJobQuantity:
    """Verify deprecation checks job_quantity (items on open jobs),
    not just whether open jobs exist."""

    def test_completed_job_does_not_block_deprecation(
        self, repo, labor_user, dep_part,
    ):
        """Parts on a COMPLETED job don't block deprecation."""
        # Create a completed job with parts
        job = Job(
            job_number="DEP-JQ-001", name="Completed Job",
            status="completed",
        )
        job.id = repo.create_job(job)
        repo.assign_part_to_job(JobPart(
            part_id=dep_part.id, job_id=job.id, quantity_used=5,
        ))

        # Start deprecation — should NOT be blocked (job is completed)
        repo.start_part_deprecation(dep_part.id)
        progress = repo.check_deprecation_progress(dep_part.id)
        # job_quantity counts items on ACTIVE jobs only
        # (completed job doesn't count)
        status = repo.advance_deprecation(dep_part.id)
        # Should advance past pending (to zero_stock if warehouse > 0)
        assert status in ("winding_down", "zero_stock")

    def test_active_job_with_zero_qty_does_not_block(
        self, repo, labor_user, dep_part,
    ):
        """An active job that has NO items of this part doesn't block."""
        job = Job(
            job_number="DEP-JQ-002", name="Active But No Parts",
            status="active",
        )
        job.id = repo.create_job(job)
        # Don't assign any parts

        repo.start_part_deprecation(dep_part.id)
        progress = repo.check_deprecation_progress(dep_part.id)
        assert progress["job_quantity"] == 0
        status = repo.advance_deprecation(dep_part.id)
        assert status != "pending"

    def test_active_job_with_parts_blocks_deprecation(
        self, repo, labor_user, dep_part,
    ):
        """Active job with items blocks at pending."""
        job = Job(
            job_number="DEP-JQ-003", name="Active With Parts",
            status="active",
        )
        job.id = repo.create_job(job)
        repo.assign_part_to_job(JobPart(
            part_id=dep_part.id, job_id=job.id, quantity_used=3,
        ))

        repo.start_part_deprecation(dep_part.id)
        status = repo.advance_deprecation(dep_part.id)
        assert status == "pending"

    def test_completing_blocking_job_unblocks_deprecation(
        self, repo, labor_user, dep_part,
    ):
        """Complete the blocking job → deprecation advances."""
        job = Job(
            job_number="DEP-JQ-004", name="Will Complete",
            status="active",
        )
        job.id = repo.create_job(job)
        repo.assign_part_to_job(JobPart(
            part_id=dep_part.id, job_id=job.id, quantity_used=4,
        ))

        repo.start_part_deprecation(dep_part.id)
        assert repo.advance_deprecation(dep_part.id) == "pending"

        # Complete the job
        job = repo.get_job_by_id(job.id)
        job.status = "completed"
        repo.update_job(job)

        # Now it should advance
        status = repo.advance_deprecation(dep_part.id)
        assert status in ("winding_down", "zero_stock")

    def test_removing_parts_from_job_unblocks_deprecation(
        self, repo, labor_user, dep_part,
    ):
        """Removing all items from an active job unblocks deprecation."""
        job = Job(
            job_number="DEP-JQ-005", name="Parts Removed",
            status="active",
        )
        job.id = repo.create_job(job)
        repo.assign_part_to_job(JobPart(
            part_id=dep_part.id, job_id=job.id, quantity_used=2,
        ))

        repo.start_part_deprecation(dep_part.id)
        assert repo.advance_deprecation(dep_part.id) == "pending"

        # Remove parts
        for jp in repo.get_job_parts(job.id):
            if jp.part_id == dep_part.id:
                repo.remove_part_from_job(jp.id)

        # job_quantity now 0 → advances
        progress = repo.check_deprecation_progress(dep_part.id)
        assert progress["job_quantity"] == 0
        status = repo.advance_deprecation(dep_part.id)
        assert status in ("winding_down", "zero_stock")

    def test_full_deprecation_pipeline(self, repo, dep_part):
        """Full pipeline: pending → winding_down → zero_stock → archived."""
        dep_part_obj = repo.get_part_by_id(dep_part.id)
        dep_part_obj.quantity = 0
        repo.update_part(dep_part_obj)

        repo.start_part_deprecation(dep_part.id)
        status = repo.advance_deprecation(dep_part.id)
        assert status == "archived"

        final = repo.get_part_by_id(dep_part.id)
        assert final.deprecation_status == "archived"
        assert final.deprecation_started_at is not None


# ═══════════════════════════════════════════════════════════════════
# COMPLETE E2E: LABOR + JOB LIFECYCLE + BRO
# ═══════════════════════════════════════════════════════════════════


class TestCompleteJobLaborLifecycle:
    """Full lifecycle: job creation → labor → BRO changes →
    completion → reactivation → new labor with new BRO."""

    def test_full_lifecycle(self, repo, labor_user, second_user):
        """Complete electrician workflow with labor, BRO changes,
        reactivation, and date filtering."""
        # ── 1. Create job with BRO ──────────────────────────────
        job = Job(
            job_number="LIFE-001",
            name="Full Lifecycle Job",
            customer="Client A",
            status="active",
            bill_out_rate="T&M",
            priority=2,
        )
        job.id = repo.create_job(job)
        repo.assign_user_to_job(JobAssignment(
            job_id=job.id, user_id=labor_user.id, role="lead",
        ))
        repo.assign_user_to_job(JobAssignment(
            job_id=job.id, user_id=second_user.id, role="worker",
        ))

        # ── 2. Both users clock in and work ─────────────────────
        eid1 = repo.clock_in(
            user_id=labor_user.id, job_id=job.id,
            category="Rough-in", lat=40.71, lon=-74.00,
        )
        eid2 = repo.clock_in(
            user_id=second_user.id, job_id=job.id,
            category="Testing",
        )

        # Clock out both
        repo.clock_out(eid1, description="Ran wire", lat=40.71, lon=-74.00)
        repo.clock_out(eid2, description="Tested circuits")

        # ── 3. Verify labor summary ─────────────────────────────
        summary = repo.get_labor_summary_for_job(job.id)
        assert summary["entry_count"] == 2
        assert len(summary["by_category"]) == 2
        assert len(summary["by_user"]) == 2

        # ── 4. BRO snapshot verification ────────────────────────
        e1 = repo.get_labor_entry_by_id(eid1)
        e2 = repo.get_labor_entry_by_id(eid2)
        assert e1.bill_out_rate == "T&M"
        assert e2.bill_out_rate == "T&M"

        # ── 5. Complete the job ─────────────────────────────────
        j = repo.get_job_by_id(job.id)
        j.status = "completed"
        repo.update_job(j)
        assert repo.get_job_by_id(job.id).status == "completed"

        # ── 6. Two years later: reactivate ──────────────────────
        j = repo.get_job_by_id(job.id)
        j.status = "active"
        j.bill_out_rate = "SERVICE"
        repo.update_job(j)
        assert repo.get_job_by_id(job.id).status == "active"
        assert repo.get_job_by_id(job.id).bill_out_rate == "SERVICE"

        # ── 7. New work with new BRO ────────────────────────────
        eid3 = repo.clock_in(
            user_id=labor_user.id, job_id=job.id,
            category="Service Call",
        )
        repo.clock_out(eid3, description="Follow-up visit")

        # ── 8. Old entries keep old BRO, new entry has new BRO ──
        assert repo.get_labor_entry_by_id(eid1).bill_out_rate == "T&M"
        assert repo.get_labor_entry_by_id(eid2).bill_out_rate == "T&M"
        assert repo.get_labor_entry_by_id(eid3).bill_out_rate == "SERVICE"

        # ── 9. Summary now shows 3 entries ──────────────────────
        summary = repo.get_labor_summary_for_job(job.id)
        assert summary["entry_count"] == 3
        assert summary["total_hours"] >= 0

        # ── 10. Date filtering works for today's entries ────────
        today_str = datetime.now().strftime("%Y-%m-%d")
        entries = repo.get_labor_entries_for_job(
            job.id, date_from=today_str, date_to=today_str,
        )
        assert len(entries) == 3  # All created today

    def test_multi_job_bro_isolation(self, repo, labor_user):
        """BRO snapshots are isolated per-job — changing one job's BRO
        doesn't affect entries on another job."""
        # Two jobs with different BROs
        job_a = Job(
            job_number="ISO-A", name="Job A", status="active",
            bill_out_rate="C",
        )
        job_a.id = repo.create_job(job_a)

        job_b = Job(
            job_number="ISO-B", name="Job B", status="active",
            bill_out_rate="EMERGENCY",
        )
        job_b.id = repo.create_job(job_b)

        # Create entries on both
        eid_a = repo.create_labor_entry(LaborEntry(
            user_id=labor_user.id, job_id=job_a.id,
            start_time=datetime.now().isoformat(), hours=4.0,
        ))
        eid_b = repo.create_labor_entry(LaborEntry(
            user_id=labor_user.id, job_id=job_b.id,
            start_time=datetime.now().isoformat(), hours=3.0,
        ))

        # Change job A's BRO
        j = repo.get_job_by_id(job_a.id)
        j.bill_out_rate = "T&M"
        repo.update_job(j)

        # Entry A still has "C", entry B still has "EMERGENCY"
        assert repo.get_labor_entry_by_id(eid_a).bill_out_rate == "C"
        assert repo.get_labor_entry_by_id(eid_b).bill_out_rate == "EMERGENCY"
