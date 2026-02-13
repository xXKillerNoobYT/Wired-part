"""Tests for part deprecation pipeline."""

import pytest

from wired_part.database.models import Job, JobPart, Part, User
from wired_part.database.repository import Repository


@pytest.fixture
def dep_data(repo):
    """Create test data for deprecation tests."""
    user = User(
        username="dep_user", display_name="Dep User",
        pin_hash=Repository.hash_pin("1234"),
        role="user", is_active=1,
    )
    user_id = repo.create_user(user)

    job = Job(
        job_number="JOB-DEP-001", name="Deprecation Test Job",
        status="active", address="123 Test St",
    )
    job_id = repo.create_job(job)

    part = Part(
        part_number="DP-001", name="Deprecated Widget",
        description="Widget to deprecate", quantity=10,
        unit_cost=5.0,
    )
    part_id = repo.create_part(part)

    return {"user_id": user_id, "job_id": job_id, "part_id": part_id}


class TestDeprecationStart:
    """Test starting deprecation."""

    def test_start_deprecation(self, repo, dep_data):
        repo.start_part_deprecation(dep_data["part_id"])
        part = repo.get_part_by_id(dep_data["part_id"])
        assert part.deprecation_status == "pending"
        assert part.deprecation_started_at is not None

    def test_start_deprecation_idempotent(self, repo, dep_data):
        pid = dep_data["part_id"]
        repo.start_part_deprecation(pid)
        # Starting again should not change anything (already not NULL)
        repo.start_part_deprecation(pid)
        part = repo.get_part_by_id(pid)
        assert part.deprecation_status == "pending"


class TestDeprecationProgress:
    """Test checking deprecation progress."""

    def test_check_progress_no_deps(self, repo, dep_data):
        progress = repo.check_deprecation_progress(dep_data["part_id"])
        assert progress["open_jobs"] == 0
        assert progress["job_quantity"] == 0
        assert progress["truck_quantity"] == 0
        assert progress["warehouse_quantity"] == 10

    def test_check_progress_with_job(self, repo, dep_data):
        # Assign part to job
        repo.assign_part_to_job(JobPart(
            part_id=dep_data["part_id"],
            job_id=dep_data["job_id"],
            quantity_used=3,
        ))
        progress = repo.check_deprecation_progress(dep_data["part_id"])
        assert progress["open_jobs"] == 1
        assert progress["job_quantity"] == 3


class TestDeprecationAdvance:
    """Test advancing through deprecation stages.

    advance_deprecation loops through all stages in one call,
    stopping only when a condition blocks further progress.
    """

    def test_advance_skips_to_zero_stock_when_no_jobs_no_trucks(
        self, repo, dep_data,
    ):
        """No open jobs, no truck qty, but warehouse has 10 →
        pending → winding_down → zero_stock (blocked by warehouse)."""
        pid = dep_data["part_id"]
        repo.start_part_deprecation(pid)
        status = repo.advance_deprecation(pid)
        assert status == "zero_stock"

    def test_pending_blocked_by_items_on_open_job(self, repo, dep_data):
        """Pending stays pending if items of this part are on open jobs."""
        pid = dep_data["part_id"]
        repo.assign_part_to_job(JobPart(
            part_id=pid,
            job_id=dep_data["job_id"],
            quantity_used=2,
        ))
        repo.start_part_deprecation(pid)
        status = repo.advance_deprecation(pid)
        assert status == "pending"

    def test_zero_stock_blocked_by_warehouse(self, repo, dep_data):
        """zero_stock stays if warehouse has inventory."""
        pid = dep_data["part_id"]
        repo.start_part_deprecation(pid)
        status = repo.advance_deprecation(pid)
        assert status == "zero_stock"
        # Still blocked
        status2 = repo.advance_deprecation(pid)
        assert status2 == "zero_stock"

    def test_full_pipeline_immediate_archive(self, repo, dep_data):
        """When qty=0, no trucks, no jobs → goes straight to archived."""
        pid = dep_data["part_id"]
        part = repo.get_part_by_id(pid)
        part.quantity = 0
        repo.update_part(part)

        repo.start_part_deprecation(pid)
        status = repo.advance_deprecation(pid)
        assert status == "archived"

        final = repo.get_part_by_id(pid)
        assert final.deprecation_status == "archived"

    def test_advance_after_clearing_warehouse(self, repo, dep_data):
        """After warehouse qty hits 0, advance completes to archived."""
        pid = dep_data["part_id"]
        repo.start_part_deprecation(pid)

        # First advance: stops at zero_stock (warehouse=10)
        status = repo.advance_deprecation(pid)
        assert status == "zero_stock"

        # Clear warehouse
        part = repo.get_part_by_id(pid)
        part.quantity = 0
        repo.update_part(part)

        # Now advance finishes
        status = repo.advance_deprecation(pid)
        assert status == "archived"

    def test_pending_not_blocked_after_removing_job_parts(self, repo, dep_data):
        """After all parts are removed from open job, pending advances."""
        pid = dep_data["part_id"]
        # Assign part to job with qty=2
        repo.assign_part_to_job(JobPart(
            part_id=pid,
            job_id=dep_data["job_id"],
            quantity_used=2,
        ))
        repo.start_part_deprecation(pid)
        # Blocked at pending (job_quantity=2)
        assert repo.advance_deprecation(pid) == "pending"

        # Remove the part from the job (simulate return)
        job_parts = repo.get_job_parts(dep_data["job_id"])
        for jp in job_parts:
            if jp.part_id == pid:
                repo.remove_part_from_job(jp.id)

        # job_quantity is now 0 even though job is still open → should advance
        progress = repo.check_deprecation_progress(pid)
        assert progress["job_quantity"] == 0
        status = repo.advance_deprecation(pid)
        # Advances past pending (no items on jobs), stops at zero_stock
        assert status == "zero_stock"

    def test_advance_after_clearing_job(self, repo, dep_data):
        """After job is completed, advance continues through pipeline."""
        pid = dep_data["part_id"]
        repo.assign_part_to_job(JobPart(
            part_id=pid,
            job_id=dep_data["job_id"],
            quantity_used=2,
        ))
        repo.start_part_deprecation(pid)

        # Blocked at pending
        assert repo.advance_deprecation(pid) == "pending"

        # Complete the job
        job = repo.get_job_by_id(dep_data["job_id"])
        job.status = "completed"
        repo.update_job(job)

        # Now advances past pending → stops at zero_stock (warehouse=10)
        assert repo.advance_deprecation(pid) == "zero_stock"


class TestDeprecationCancel:
    """Test cancelling deprecation."""

    def test_cancel_pending(self, repo, dep_data):
        pid = dep_data["part_id"]
        # Block at pending with an open job
        repo.assign_part_to_job(JobPart(
            part_id=pid,
            job_id=dep_data["job_id"],
            quantity_used=2,
        ))
        repo.start_part_deprecation(pid)
        repo.advance_deprecation(pid)
        assert repo.get_part_by_id(pid).deprecation_status == "pending"

        repo.cancel_deprecation(pid)
        part = repo.get_part_by_id(pid)
        assert part.deprecation_status is None

    def test_cancel_zero_stock(self, repo, dep_data):
        pid = dep_data["part_id"]
        repo.start_part_deprecation(pid)
        repo.advance_deprecation(pid)  # → zero_stock (blocked by warehouse)
        assert repo.get_part_by_id(pid).deprecation_status == "zero_stock"

        repo.cancel_deprecation(pid)
        part = repo.get_part_by_id(pid)
        assert part.deprecation_status is None

    def test_cannot_cancel_archived(self, repo, dep_data):
        pid = dep_data["part_id"]
        part = repo.get_part_by_id(pid)
        part.quantity = 0
        repo.update_part(part)

        repo.start_part_deprecation(pid)
        repo.advance_deprecation(pid)  # → archived (all clear)

        repo.cancel_deprecation(pid)  # Should not change archived
        part = repo.get_part_by_id(pid)
        assert part.deprecation_status == "archived"


class TestGetDeprecatedParts:
    """Test querying deprecated parts."""

    def test_get_deprecated_parts(self, repo, dep_data):
        repo.start_part_deprecation(dep_data["part_id"])
        deprecated = repo.get_deprecated_parts()
        assert len(deprecated) >= 1
        assert any(p.id == dep_data["part_id"] for p in deprecated)

    def test_no_deprecated_parts(self, repo, dep_data):
        deprecated = repo.get_deprecated_parts()
        # Should not include our test part (not deprecated yet)
        assert not any(p.id == dep_data["part_id"] for p in deprecated)
