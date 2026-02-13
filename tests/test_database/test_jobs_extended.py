"""Extended tests for jobs: search, work report, summary, and edge cases."""

import pytest
from datetime import datetime, timedelta

from wired_part.database.models import (
    Job, JobAssignment, LaborEntry, Part, User,
)
from wired_part.database.repository import Repository


@pytest.fixture
def job_data(repo):
    """User and multiple jobs for testing."""
    user = User(
        username="job_test_user", display_name="Job Tester",
        pin_hash=Repository.hash_pin("1234"),
        role="user", is_active=1,
    )
    user_id = repo.create_user(user)

    jobs = []
    for i, (num, name, status, bro) in enumerate([
        ("JEX-001", "Active Job", "active", "T&M"),
        ("JEX-002", "Completed Job", "completed", "C"),
        ("JEX-003", "On Hold Job", "on_hold", "SERVICE"),
        ("JEX-004", "Cancelled Job", "cancelled", ""),
    ]):
        j = Job(
            job_number=num, name=name, status=status,
            bill_out_rate=bro, customer=f"Client {i}",
            address=f"{i} Main St",
        )
        j.id = repo.create_job(j)
        repo.assign_user_to_job(JobAssignment(
            job_id=j.id, user_id=user_id, role="lead",
        ))
        jobs.append(j)

    return {"user_id": user_id, "jobs": jobs}


class TestGetJobByNumber:
    """Test looking up a job by its number."""

    def test_get_job_by_number(self, repo, job_data):
        job = repo.get_job_by_number("JEX-001")
        assert job is not None
        assert job.name == "Active Job"

    def test_get_job_by_number_nonexistent(self, repo, job_data):
        assert repo.get_job_by_number("NOPE-999") is None


class TestGetAllJobsFilters:
    """Test get_all_jobs with status filters."""

    def test_get_all_jobs_active(self, repo, job_data):
        active = repo.get_all_jobs("active")
        nums = {j.job_number for j in active}
        assert "JEX-001" in nums
        assert "JEX-002" not in nums

    def test_get_all_jobs_no_filter(self, repo, job_data):
        all_jobs = repo.get_all_jobs()
        nums = {j.job_number for j in all_jobs}
        assert "JEX-001" in nums
        assert "JEX-002" in nums
        assert "JEX-003" in nums


class TestWorkReportData:
    """Test work report data generation for a job."""

    def test_get_work_report_data(self, repo, job_data):
        job = job_data["jobs"][0]
        uid = job_data["user_id"]

        # Add labor entries
        for i in range(3):
            repo.create_labor_entry(LaborEntry(
                user_id=uid, job_id=job.id,
                start_time=datetime.now().isoformat(),
                hours=2.0 + i,
                sub_task_category="Rough-in",
            ))

        report = repo.get_work_report_data(job.id)
        assert report is not None
        assert "labor" in report
        assert len(report["labor"]["entries"]) == 3
        assert report["labor"]["summary"]["total_hours"] >= 6.0

    def test_work_report_empty_job(self, repo, job_data):
        job = job_data["jobs"][1]
        report = repo.get_work_report_data(job.id)
        assert report["labor"]["summary"]["total_hours"] == 0


class TestTruckPartQuantity:
    """Test getting a specific part's quantity on a truck."""

    def test_get_truck_part_quantity_empty(self, repo):
        from wired_part.database.models import Truck, User
        user = User(
            username="trk_user", display_name="Truck User",
            pin_hash=Repository.hash_pin("1234"),
        )
        user.id = repo.create_user(user)
        truck = Truck(
            truck_number="TQ-001", name="Test Truck",
            assigned_user_id=user.id,
        )
        truck.id = repo.create_truck(truck)

        part = Part(
            part_number="TQ-PART", name="Test Part",
            quantity=100,
        )
        part.id = repo.create_part(part)

        qty = repo.get_truck_part_quantity(truck.id, part.id)
        assert qty == 0


class TestJobStatusTransitions:
    """Test all status transitions."""

    def test_active_to_on_hold(self, repo, job_data):
        job = repo.get_job_by_id(job_data["jobs"][0].id)
        job.status = "on_hold"
        repo.update_job(job)
        assert repo.get_job_by_id(job.id).status == "on_hold"

    def test_on_hold_to_active(self, repo, job_data):
        job = repo.get_job_by_id(job_data["jobs"][2].id)
        job.status = "active"
        repo.update_job(job)
        assert repo.get_job_by_id(job.id).status == "active"

    def test_active_to_completed(self, repo, job_data):
        job = repo.get_job_by_id(job_data["jobs"][0].id)
        job.status = "completed"
        repo.update_job(job)
        assert repo.get_job_by_id(job.id).status == "completed"

    def test_active_to_cancelled(self, repo, job_data):
        job = repo.get_job_by_id(job_data["jobs"][0].id)
        job.status = "cancelled"
        repo.update_job(job)
        assert repo.get_job_by_id(job.id).status == "cancelled"
