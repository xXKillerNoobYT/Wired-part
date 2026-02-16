"""Tests for v17 features: drive_time_minutes, checkout_notes on labor entries."""

import json
from datetime import datetime, timedelta

import pytest

from wired_part.database.models import Job, LaborEntry, User
from wired_part.database.repository import Repository
from wired_part.database.schema import SCHEMA_VERSION


@pytest.fixture
def labor_user(repo):
    """Create a user for v17 labor tests."""
    user = User(
        username="v17worker",
        display_name="V17 Worker",
        pin_hash=Repository.hash_pin("1234"),
        role="user",
        is_active=1,
    )
    user.id = repo.create_user(user)
    return user


@pytest.fixture
def labor_job(repo):
    """Create a job for v17 labor tests."""
    job = Job(
        job_number="JOB-V17-001",
        name="V17 Test Job",
        status="active",
        address="123 Test St",
    )
    job.id = repo.create_job(job)
    return job


class TestSchemaV17:
    """Verify schema version and new columns."""

    def test_schema_version_is_17(self):
        assert SCHEMA_VERSION == 17

    def test_labor_entries_has_drive_time_column(self, repo):
        """drive_time_minutes column exists in labor_entries table."""
        rows = repo.db.execute(
            "PRAGMA table_info(labor_entries)",
        )
        col_names = [r["name"] for r in rows]
        assert "drive_time_minutes" in col_names

    def test_labor_entries_has_checkout_notes_column(self, repo):
        """checkout_notes column exists in labor_entries table."""
        rows = repo.db.execute(
            "PRAGMA table_info(labor_entries)",
        )
        col_names = [r["name"] for r in rows]
        assert "checkout_notes" in col_names


class TestDriveTimeMinutes:
    """Test drive_time_minutes field on LaborEntry."""

    def test_default_drive_time_is_zero(self, repo, labor_user, labor_job):
        """New labor entries default to 0 drive time."""
        eid = repo.create_labor_entry(LaborEntry(
            user_id=labor_user.id,
            job_id=labor_job.id,
            start_time=datetime.now().isoformat(),
            hours=2.0,
        ))
        entry = repo.get_labor_entry_by_id(eid)
        assert entry.drive_time_minutes == 0

    def test_save_and_retrieve_drive_time(self, repo, labor_user, labor_job):
        """Drive time can be saved and retrieved."""
        eid = repo.create_labor_entry(LaborEntry(
            user_id=labor_user.id,
            job_id=labor_job.id,
            start_time=datetime.now().isoformat(),
            hours=4.0,
            drive_time_minutes=45,
        ))
        entry = repo.get_labor_entry_by_id(eid)
        assert entry.drive_time_minutes == 45

    def test_update_drive_time(self, repo, labor_user, labor_job):
        """Drive time can be updated after creation."""
        eid = repo.create_labor_entry(LaborEntry(
            user_id=labor_user.id,
            job_id=labor_job.id,
            start_time=datetime.now().isoformat(),
            hours=3.0,
        ))
        entry = repo.get_labor_entry_by_id(eid)
        entry.drive_time_minutes = 90
        repo.update_labor_entry(entry)

        updated = repo.get_labor_entry_by_id(eid)
        assert updated.drive_time_minutes == 90

    def test_clock_in_out_preserves_drive_time(self, repo, labor_user, labor_job):
        """Drive time set on clock-out persists."""
        eid = repo.clock_in(
            user_id=labor_user.id,
            job_id=labor_job.id,
            category="Rough-in",
        )
        result = repo.clock_out(eid, description="Done")
        # Update drive time after clock out
        entry = repo.get_labor_entry_by_id(eid)
        entry.drive_time_minutes = 30
        repo.update_labor_entry(entry)

        fetched = repo.get_labor_entry_by_id(eid)
        assert fetched.drive_time_minutes == 30


class TestCheckoutNotes:
    """Test checkout_notes JSON field on LaborEntry."""

    def test_default_checkout_notes_empty(self, repo, labor_user, labor_job):
        """New labor entries have empty checkout notes."""
        eid = repo.create_labor_entry(LaborEntry(
            user_id=labor_user.id,
            job_id=labor_job.id,
            start_time=datetime.now().isoformat(),
            hours=2.0,
        ))
        entry = repo.get_labor_entry_by_id(eid)
        assert entry.checkout_notes == "{}"
        assert entry.checkout_notes_dict == {}

    def test_save_checkout_notes_json(self, repo, labor_user, labor_job):
        """Checkout notes can store JSON checklist data."""
        notes = {
            "orders_done": True,
            "owner_notes_done": False,
            "materials_picked_up": True,
            "work_left": "Part day remaining",
            "plan_day1": "Finish kitchen rough-in",
            "plan_day2": "Start bathroom",
            "next_big_things": "Panel upgrade next week",
            "freeform_notes": ["Need more 12/2 wire", "Drywall in way"],
        }
        eid = repo.create_labor_entry(LaborEntry(
            user_id=labor_user.id,
            job_id=labor_job.id,
            start_time=datetime.now().isoformat(),
            hours=8.0,
            checkout_notes=json.dumps(notes),
        ))
        entry = repo.get_labor_entry_by_id(eid)
        parsed = entry.checkout_notes_dict
        assert parsed["orders_done"] is True
        assert parsed["owner_notes_done"] is False
        assert parsed["work_left"] == "Part day remaining"
        assert len(parsed["freeform_notes"]) == 2

    def test_update_checkout_notes(self, repo, labor_user, labor_job):
        """Checkout notes can be updated after creation."""
        eid = repo.create_labor_entry(LaborEntry(
            user_id=labor_user.id,
            job_id=labor_job.id,
            start_time=datetime.now().isoformat(),
            hours=4.0,
        ))
        entry = repo.get_labor_entry_by_id(eid)
        new_notes = {"orders_done": True, "work_left": "No work left (complete)"}
        entry.checkout_notes = json.dumps(new_notes)
        repo.update_labor_entry(entry)

        updated = repo.get_labor_entry_by_id(eid)
        assert updated.checkout_notes_dict["orders_done"] is True
        assert "No work left" in updated.checkout_notes_dict["work_left"]

    def test_checkout_notes_dict_handles_invalid_json(self):
        """Property handles corrupt JSON gracefully."""
        entry = LaborEntry(checkout_notes="not valid json")
        assert entry.checkout_notes_dict == {}

    def test_checkout_notes_dict_handles_none(self):
        """Property handles None gracefully."""
        entry = LaborEntry(checkout_notes=None)
        assert entry.checkout_notes_dict == {}

    def test_checkout_notes_dict_handles_empty_string(self):
        """Property handles empty string gracefully."""
        entry = LaborEntry(checkout_notes="")
        assert entry.checkout_notes_dict == {}
