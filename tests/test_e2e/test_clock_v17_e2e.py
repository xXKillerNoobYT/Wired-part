"""E2E tests for v17 clock-in/clock-out workflow with drive time and checkout notes."""

import json
from datetime import datetime, timedelta

import pytest

from wired_part.database.models import Job, LaborEntry, User
from wired_part.database.repository import Repository


@pytest.fixture
def worker(repo):
    user = User(
        username="clockworker",
        display_name="Clock Worker",
        pin_hash=Repository.hash_pin("1234"),
        role="user",
        is_active=1,
    )
    user.id = repo.create_user(user)
    return user


@pytest.fixture
def job(repo):
    j = Job(
        job_number="JOB-CLK-V17",
        name="Clock V17 Job",
        status="active",
        address="456 Electric Ave",
    )
    j.id = repo.create_job(j)
    return j


class TestClockV17FullWorkflow:
    """Full clock-in → clock-out workflow with drive time and checkout notes."""

    def test_clock_in_and_out_with_drive_time(self, repo, worker, job):
        """Clock in, clock out, set drive time, verify persistence."""
        eid = repo.clock_in(
            user_id=worker.id,
            job_id=job.id,
            category="Rough-in",
            lat=32.7767,
            lon=-96.7970,
        )

        result = repo.clock_out(eid, description="Ran 3 circuits in kitchen")

        # Update with drive time
        entry = repo.get_labor_entry_by_id(eid)
        entry.drive_time_minutes = 45
        repo.update_labor_entry(entry)

        fetched = repo.get_labor_entry_by_id(eid)
        assert fetched.drive_time_minutes == 45
        assert fetched.description == "Ran 3 circuits in kitchen"
        assert fetched.clock_in_lat == 32.7767

    def test_clock_out_with_checkout_notes(self, repo, worker, job):
        """Clock out with full checkout checklist and verify JSON persistence."""
        eid = repo.clock_in(
            user_id=worker.id,
            job_id=job.id,
            category="Testing",
        )
        result = repo.clock_out(eid, description="Tested all circuits")

        checkout = {
            "orders_done": True,
            "owner_notes_done": True,
            "materials_received": False,
            "work_left": "Part day remaining",
            "plan_day1": "Finish testing upstairs",
            "plan_day2": "Start trim-out downstairs",
            "next_big_things": "Panel upgrade scheduled for Thursday",
            "freeform_notes": [
                "Drywall crew delayed - bedroom circuits not accessible",
                "Need more AFCI breakers for bedrooms",
                "Homeowner asked about adding outlet in garage",
            ],
        }

        entry = repo.get_labor_entry_by_id(eid)
        entry.checkout_notes = json.dumps(checkout)
        entry.drive_time_minutes = 30
        repo.update_labor_entry(entry)

        fetched = repo.get_labor_entry_by_id(eid)
        assert fetched.drive_time_minutes == 30
        parsed = fetched.checkout_notes_dict
        assert parsed["orders_done"] is True
        assert parsed["work_left"] == "Part day remaining"
        assert len(parsed["freeform_notes"]) == 3
        assert "AFCI breakers" in parsed["freeform_notes"][1]

    def test_multiple_clock_cycles_with_v17_fields(self, repo, worker, job):
        """Multiple clock cycles, each with different drive/checkout data."""
        for day_offset in range(3):
            eid = repo.clock_in(
                user_id=worker.id,
                job_id=job.id,
                category="Rough-in" if day_offset < 2 else "Trim-out",
            )
            repo.clock_out(eid, description=f"Day {day_offset + 1} work")

            entry = repo.get_labor_entry_by_id(eid)
            entry.drive_time_minutes = 30 + (day_offset * 15)
            entry.checkout_notes = json.dumps({
                "work_left": "Full day remaining" if day_offset < 2 else "No work left (complete)",
                "plan_day1": f"Continue day {day_offset + 2}",
            })
            repo.update_labor_entry(entry)

        entries = repo.get_labor_entries_for_job(job.id)
        assert len(entries) == 3

        # Verify each has different drive times
        drive_times = sorted(
            [e.drive_time_minutes for e in entries]
        )
        assert drive_times == [30, 45, 60]

    def test_single_clock_in_protection(self, repo, worker, job):
        """Cannot clock into two jobs simultaneously."""
        job2 = Job(
            job_number="JOB-CLK-V17-2",
            name="Second Job",
            status="active",
        )
        job2.id = repo.create_job(job2)

        repo.clock_in(user_id=worker.id, job_id=job.id)

        with pytest.raises(ValueError, match="Already clocked in"):
            repo.clock_in(user_id=worker.id, job_id=job2.id)

    def test_weekly_hours_aggregation_with_drive_time(self, repo, worker, job):
        """Drive time is stored separately from work hours."""
        now = datetime.now()
        for i in range(5):
            entry = LaborEntry(
                user_id=worker.id,
                job_id=job.id,
                start_time=(now - timedelta(days=i)).isoformat(),
                end_time=(now - timedelta(days=i) + timedelta(hours=8)).isoformat(),
                hours=8.0,
                description=f"Day {i + 1}",
                drive_time_minutes=45,
            )
            repo.create_labor_entry(entry)

        entries = repo.get_labor_entries_for_user(worker.id)
        total_hours = sum(e.hours or 0 for e in entries)
        total_drive = sum(e.drive_time_minutes or 0 for e in entries)

        assert total_hours == 40.0
        assert total_drive == 225  # 5 days * 45 minutes
