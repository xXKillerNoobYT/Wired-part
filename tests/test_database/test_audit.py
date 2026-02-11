"""Tests for inventory audit system."""

import pytest

from wired_part.database.models import Job, Part, Truck, User
from wired_part.database.repository import Repository


@pytest.fixture
def audit_data(repo):
    """Create test data for audit tests."""
    user = User(
        username="auditor", display_name="Auditor",
        pin_hash=Repository.hash_pin("1234"),
        role="admin", is_active=1,
    )
    user_id = repo.create_user(user)

    part1 = Part(
        part_number="AUD-001", name="Audit Widget A",
        quantity=10, unit_cost=5.0,
    )
    part1_id = repo.create_part(part1)

    part2 = Part(
        part_number="AUD-002", name="Audit Widget B",
        quantity=5, unit_cost=3.0,
    )
    part2_id = repo.create_part(part2)

    truck = Truck(
        truck_number="TRUCK-AUD-01", name="Audit Truck",
    )
    truck_id = repo.create_truck(truck)

    job = Job(
        job_number="JOB-AUD-001", name="Audit Test Job",
        status="active",
    )
    job_id = repo.create_job(job)

    return {
        "user_id": user_id,
        "part1_id": part1_id,
        "part2_id": part2_id,
        "truck_id": truck_id,
        "job_id": job_id,
    }


class TestAuditItems:
    """Test getting items to audit."""

    def test_get_warehouse_items(self, repo, audit_data):
        items = repo.get_audit_items("warehouse", limit=10)
        assert len(items) >= 2
        # All should have quantity > 0
        for item in items:
            assert item["expected_quantity"] > 0

    def test_limit_works(self, repo, audit_data):
        items = repo.get_audit_items("warehouse", limit=1)
        assert len(items) == 1

    def test_full_audit(self, repo, audit_data):
        items = repo.get_audit_items("warehouse", limit=0)
        assert len(items) >= 2


class TestRecordAudit:
    """Test recording audit results."""

    def test_record_confirmed(self, repo, audit_data):
        aid = repo.record_audit_result(
            "warehouse", None, audit_data["part1_id"],
            expected_quantity=10, actual_quantity=10,
            status="confirmed", audited_by=audit_data["user_id"],
        )
        assert aid > 0

    def test_record_discrepancy(self, repo, audit_data):
        aid = repo.record_audit_result(
            "warehouse", None, audit_data["part1_id"],
            expected_quantity=10, actual_quantity=8,
            status="discrepancy", audited_by=audit_data["user_id"],
        )
        assert aid > 0

    def test_record_skipped(self, repo, audit_data):
        aid = repo.record_audit_result(
            "warehouse", None, audit_data["part1_id"],
            expected_quantity=10, actual_quantity=0,
            status="skipped",
        )
        assert aid > 0

    def test_record_truck_audit(self, repo, audit_data):
        # Add part to truck first
        repo.add_to_truck_inventory(
            audit_data["truck_id"], audit_data["part1_id"], 5,
        )
        aid = repo.record_audit_result(
            "truck", audit_data["truck_id"], audit_data["part1_id"],
            expected_quantity=5, actual_quantity=5,
            status="confirmed",
        )
        assert aid > 0


class TestAuditSummary:
    """Test audit summary queries."""

    def test_empty_summary(self, repo, audit_data):
        summary = repo.get_audit_summary("warehouse")
        assert summary["total_count"] == 0

    def test_summary_after_audits(self, repo, audit_data):
        repo.record_audit_result(
            "warehouse", None, audit_data["part1_id"],
            10, 10, "confirmed", audit_data["user_id"],
        )
        repo.record_audit_result(
            "warehouse", None, audit_data["part2_id"],
            5, 3, "discrepancy", audit_data["user_id"],
        )

        summary = repo.get_audit_summary("warehouse")
        assert summary["confirmed_count"] == 1
        assert summary["discrepancy_count"] == 1
        assert summary["total_count"] == 2
        assert summary["last_audit"] is not None

    def test_summary_by_target(self, repo, audit_data):
        repo.add_to_truck_inventory(
            audit_data["truck_id"], audit_data["part1_id"], 5,
        )
        repo.record_audit_result(
            "truck", audit_data["truck_id"], audit_data["part1_id"],
            5, 5, "confirmed",
        )

        summary = repo.get_audit_summary(
            "truck", audit_data["truck_id"]
        )
        assert summary["confirmed_count"] == 1
        assert summary["total_count"] == 1

    def test_oldest_items_first(self, repo, audit_data):
        """Items never audited should appear first."""
        # Record audit for part1 only
        repo.record_audit_result(
            "warehouse", None, audit_data["part1_id"],
            10, 10, "confirmed",
        )
        # Get audit items — part2 (never audited) should be first
        items = repo.get_audit_items("warehouse", limit=10)
        part_ids = [i["part_id"] for i in items]
        idx1 = part_ids.index(audit_data["part1_id"])
        idx2 = part_ids.index(audit_data["part2_id"])
        assert idx2 < idx1  # part2 should come before part1
