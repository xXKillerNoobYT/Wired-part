"""Tests for labor entries, clock-in/out, and summaries."""

import pytest
from datetime import datetime, timedelta

from wired_part.database.models import (
    Job,
    LaborEntry,
    User,
)
from wired_part.database.repository import Repository


@pytest.fixture
def labor_data(repo):
    """Create user and job for labor tests."""
    user = User(
        username="laborer1", display_name="Laborer One",
        pin_hash=Repository.hash_pin("1234"),
        role="user", is_active=1,
    )
    user_id = repo.create_user(user)

    job = Job(
        job_number="JOB-LABOR-001", name="Labor Test Job",
        status="active", address="123 Main St",
    )
    job_id = repo.create_job(job)

    return {"user_id": user_id, "job_id": job_id}


class TestLaborEntryCRUD:
    """Test basic labor entry operations."""

    def test_create_labor_entry(self, repo, labor_data):
        entry = LaborEntry(
            user_id=labor_data["user_id"],
            job_id=labor_data["job_id"],
            start_time=datetime.now().isoformat(),
            end_time=(datetime.now() + timedelta(hours=2)).isoformat(),
            hours=2.0,
            description="Rough-in wiring",
            sub_task_category="Rough-in",
        )
        eid = repo.create_labor_entry(entry)
        assert eid > 0

    def test_get_labor_entry_by_id(self, repo, labor_data):
        now = datetime.now()
        entry = LaborEntry(
            user_id=labor_data["user_id"],
            job_id=labor_data["job_id"],
            start_time=now.isoformat(),
            hours=3.5,
            description="Testing circuits",
            sub_task_category="Testing",
        )
        eid = repo.create_labor_entry(entry)
        fetched = repo.get_labor_entry_by_id(eid)
        assert fetched is not None
        assert fetched.user_name == "Laborer One"
        assert fetched.job_number == "JOB-LABOR-001"
        assert fetched.sub_task_category == "Testing"

    def test_update_labor_entry(self, repo, labor_data):
        eid = repo.create_labor_entry(LaborEntry(
            user_id=labor_data["user_id"],
            job_id=labor_data["job_id"],
            start_time=datetime.now().isoformat(),
            hours=1.0,
            description="Original",
        ))
        entry = repo.get_labor_entry_by_id(eid)
        entry.description = "Updated description"
        entry.hours = 2.5
        repo.update_labor_entry(entry)

        updated = repo.get_labor_entry_by_id(eid)
        assert updated.description == "Updated description"
        assert updated.hours == 2.5

    def test_delete_labor_entry(self, repo, labor_data):
        eid = repo.create_labor_entry(LaborEntry(
            user_id=labor_data["user_id"],
            job_id=labor_data["job_id"],
            start_time=datetime.now().isoformat(),
        ))
        assert repo.get_labor_entry_by_id(eid) is not None
        repo.delete_labor_entry(eid)
        assert repo.get_labor_entry_by_id(eid) is None

    def test_get_entries_for_job(self, repo, labor_data):
        for i in range(3):
            repo.create_labor_entry(LaborEntry(
                user_id=labor_data["user_id"],
                job_id=labor_data["job_id"],
                start_time=datetime.now().isoformat(),
                hours=float(i + 1),
            ))
        entries = repo.get_labor_entries_for_job(labor_data["job_id"])
        assert len(entries) == 3

    def test_get_entries_for_user(self, repo, labor_data):
        repo.create_labor_entry(LaborEntry(
            user_id=labor_data["user_id"],
            job_id=labor_data["job_id"],
            start_time=datetime.now().isoformat(),
            hours=4.0,
        ))
        entries = repo.get_labor_entries_for_user(labor_data["user_id"])
        assert len(entries) == 1


class TestClockInOut:
    """Test clock-in and clock-out workflow."""

    def test_clock_in(self, repo, labor_data):
        eid = repo.clock_in(
            user_id=labor_data["user_id"],
            job_id=labor_data["job_id"],
            category="Rough-in",
        )
        assert eid > 0
        entry = repo.get_labor_entry_by_id(eid)
        assert entry.end_time is None
        assert entry.sub_task_category == "Rough-in"

    def test_clock_in_prevents_duplicate(self, repo, labor_data):
        repo.clock_in(
            user_id=labor_data["user_id"],
            job_id=labor_data["job_id"],
        )
        with pytest.raises(ValueError, match="Already clocked in"):
            repo.clock_in(
                user_id=labor_data["user_id"],
                job_id=labor_data["job_id"],
            )

    def test_clock_out(self, repo, labor_data):
        eid = repo.clock_in(
            user_id=labor_data["user_id"],
            job_id=labor_data["job_id"],
        )
        result = repo.clock_out(
            eid, description="Completed wiring"
        )
        assert result is not None
        assert result.end_time is not None
        assert result.hours >= 0  # May be 0.0 when clocked in/out instantly in tests
        assert result.description == "Completed wiring"

    def test_clock_out_nonexistent_raises(self, repo):
        with pytest.raises(ValueError, match="not found"):
            repo.clock_out(9999)

    def test_get_active_clock_in(self, repo, labor_data):
        assert repo.get_active_clock_in(labor_data["user_id"]) is None

        repo.clock_in(
            user_id=labor_data["user_id"],
            job_id=labor_data["job_id"],
        )
        active = repo.get_active_clock_in(labor_data["user_id"])
        assert active is not None
        assert active.end_time is None

    def test_clock_in_with_gps(self, repo, labor_data):
        eid = repo.clock_in(
            user_id=labor_data["user_id"],
            job_id=labor_data["job_id"],
            lat=40.7128, lon=-74.0060,
        )
        entry = repo.get_labor_entry_by_id(eid)
        assert entry.clock_in_lat == 40.7128
        assert entry.clock_in_lon == -74.0060


class TestLaborSummary:
    """Test labor summary aggregation."""

    def test_summary_totals(self, repo, labor_data):
        repo.create_labor_entry(LaborEntry(
            user_id=labor_data["user_id"],
            job_id=labor_data["job_id"],
            start_time=datetime.now().isoformat(),
            hours=4.0,
            sub_task_category="Rough-in",
        ))
        repo.create_labor_entry(LaborEntry(
            user_id=labor_data["user_id"],
            job_id=labor_data["job_id"],
            start_time=datetime.now().isoformat(),
            hours=2.0,
            sub_task_category="Testing",
        ))

        summary = repo.get_labor_summary_for_job(labor_data["job_id"])
        assert summary["total_hours"] == 6.0
        assert summary["entry_count"] == 2
        assert len(summary["by_category"]) == 2
        assert len(summary["by_user"]) == 1

    def test_empty_summary(self, repo, labor_data):
        summary = repo.get_labor_summary_for_job(labor_data["job_id"])
        assert summary["total_hours"] == 0
        assert summary["entry_count"] == 0
