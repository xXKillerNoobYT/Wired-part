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


class TestDeprecationAdvance:
    """Test advancing through deprecation stages."""

    def test_advance_from_pending(self, repo, dep_data):
        """Pending → winding_down when no open jobs."""
        pid = dep_data["part_id"]
        repo.start_part_deprecation(pid)
        status = repo.advance_deprecation(pid)
        assert status == "winding_down"

    def test_pending_blocked_by_open_job(self, repo, dep_data):
        """Pending stays pending if jobs are open."""
        pid = dep_data["part_id"]
        repo.assign_part_to_job(JobPart(
            part_id=pid,
            job_id=dep_data["job_id"],
            quantity_used=2,
        ))
        repo.start_part_deprecation(pid)
        status = repo.advance_deprecation(pid)
        assert status == "pending"

    def test_advance_winding_down_to_zero_stock(self, repo, dep_data):
        """Winding_down → zero_stock when no truck inventory."""
        pid = dep_data["part_id"]
        repo.start_part_deprecation(pid)
        repo.advance_deprecation(pid)  # → winding_down
        status = repo.advance_deprecation(pid)
        assert status == "zero_stock"

    def test_advance_zero_stock_to_archived(self, repo, dep_data):
        """Zero_stock → archived when warehouse qty = 0."""
        pid = dep_data["part_id"]
        # Set warehouse qty to 0
        part = repo.get_part_by_id(pid)
        part.quantity = 0
        repo.update_part(part)

        repo.start_part_deprecation(pid)
        repo.advance_deprecation(pid)  # → winding_down
        repo.advance_deprecation(pid)  # → zero_stock
        status = repo.advance_deprecation(pid)
        assert status == "archived"

    def test_full_pipeline(self, repo, dep_data):
        """Full pipeline: pending → winding_down → zero_stock → archived."""
        pid = dep_data["part_id"]

        # Set qty to 0 so all stages pass
        part = repo.get_part_by_id(pid)
        part.quantity = 0
        repo.update_part(part)

        repo.start_part_deprecation(pid)
        assert repo.advance_deprecation(pid) == "winding_down"
        assert repo.advance_deprecation(pid) == "zero_stock"
        assert repo.advance_deprecation(pid) == "archived"

        final = repo.get_part_by_id(pid)
        assert final.deprecation_status == "archived"


class TestDeprecationCancel:
    """Test cancelling deprecation."""

    def test_cancel_pending(self, repo, dep_data):
        pid = dep_data["part_id"]
        repo.start_part_deprecation(pid)
        repo.cancel_deprecation(pid)
        part = repo.get_part_by_id(pid)
        assert part.deprecation_status is None

    def test_cancel_winding_down(self, repo, dep_data):
        pid = dep_data["part_id"]
        repo.start_part_deprecation(pid)
        repo.advance_deprecation(pid)  # → winding_down
        repo.cancel_deprecation(pid)
        part = repo.get_part_by_id(pid)
        assert part.deprecation_status is None

    def test_cannot_cancel_archived(self, repo, dep_data):
        pid = dep_data["part_id"]
        part = repo.get_part_by_id(pid)
        part.quantity = 0
        repo.update_part(part)

        repo.start_part_deprecation(pid)
        repo.advance_deprecation(pid)
        repo.advance_deprecation(pid)
        repo.advance_deprecation(pid)  # → archived

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
