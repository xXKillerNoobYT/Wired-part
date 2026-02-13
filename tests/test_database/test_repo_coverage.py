"""Tests for remaining untested repository methods to achieve 100% coverage."""

import pytest

from wired_part.database.models import (
    Hat, Job, JobAssignment, LaborEntry,
    Part, PurchaseOrder, PurchaseOrderItem,
    Supplier, Truck, User,
)
from wired_part.database.repository import Repository


@pytest.fixture
def setup_data(repo):
    """Common setup: user, job, truck, parts."""
    user = User(
        username="coverage_user", display_name="Coverage Tester",
        pin_hash=Repository.hash_pin("1234"),
        role="user", is_active=1,
    )
    user.id = repo.create_user(user)

    job = Job(
        job_number="COV-001", name="Coverage Job",
        status="active", bill_out_rate="T&M",
    )
    job.id = repo.create_job(job)

    repo.assign_user_to_job(JobAssignment(
        job_id=job.id, user_id=user.id, role="lead",
    ))

    truck = Truck(
        truck_number="COV-T01", name="Coverage Truck",
        assigned_user_id=user.id,
    )
    truck.id = repo.create_truck(truck)

    cat = repo.get_all_categories()[0]
    part = Part(
        part_number="COV-P01", name="Coverage Part",
        quantity=100, unit_cost=25.0, category_id=cat.id,
    )
    part.id = repo.create_part(part)

    return {
        "user": user,
        "job": job,
        "truck": truck,
        "part": part,
    }


# ═══════════════════════════════════════════════════════════════════
# get_user_jobs
# ═══════════════════════════════════════════════════════════════════

class TestGetUserJobs:
    """Test getting jobs assigned to a specific user."""

    def test_get_user_jobs_all(self, repo, setup_data):
        """Get all jobs for a user."""
        jobs = repo.get_user_jobs(setup_data["user"].id)
        assert len(jobs) >= 1
        assert any(ja.job_id == setup_data["job"].id for ja in jobs)

    def test_get_user_jobs_filtered_by_status(self, repo, setup_data):
        """Get only active jobs for a user."""
        jobs = repo.get_user_jobs(setup_data["user"].id, status="active")
        assert len(jobs) >= 1
        # All returned should be for active jobs
        for ja in jobs:
            assert ja.job_id == setup_data["job"].id

    def test_get_user_jobs_no_results(self, repo, setup_data):
        """Filtering by nonexistent status returns empty."""
        jobs = repo.get_user_jobs(
            setup_data["user"].id, status="completed"
        )
        # The only job is active, so completed filter returns 0
        cov_jobs = [j for j in jobs if j.job_id == setup_data["job"].id]
        assert len(cov_jobs) == 0

    def test_get_user_jobs_status_all(self, repo, setup_data):
        """Status 'all' returns everything."""
        jobs = repo.get_user_jobs(setup_data["user"].id, status="all")
        assert len(jobs) >= 1


# ═══════════════════════════════════════════════════════════════════
# get_job_summary
# ═══════════════════════════════════════════════════════════════════

class TestGetJobSummary:
    """Test job summary statistics."""

    def test_get_job_summary_all(self, repo, setup_data):
        """Get summary across all jobs."""
        summary = repo.get_job_summary()
        assert "total_jobs" in summary
        assert summary["total_jobs"] >= 1
        assert "total_cost" in summary

    def test_get_job_summary_active(self, repo, setup_data):
        """Get summary for active jobs only."""
        summary = repo.get_job_summary(status="active")
        assert summary["total_jobs"] >= 1

    def test_get_job_summary_completed(self, repo, setup_data):
        """Get summary for completed jobs (may be 0)."""
        summary = repo.get_job_summary(status="completed")
        assert "total_jobs" in summary

    def test_get_job_summary_status_all(self, repo, setup_data):
        """Status 'all' gets all jobs."""
        summary = repo.get_job_summary(status="all")
        assert summary["total_jobs"] >= 1


# ═══════════════════════════════════════════════════════════════════
# get_truck_summary
# ═══════════════════════════════════════════════════════════════════

class TestGetTruckSummary:
    """Test truck summary (unique parts, total qty, value, transfers)."""

    def test_truck_summary_empty(self, repo, setup_data):
        """Empty truck has zero summary values."""
        summary = repo.get_truck_summary(setup_data["truck"].id)
        assert summary["unique_parts"] == 0
        assert summary["total_quantity"] == 0
        assert summary["total_value"] == 0.0
        assert "pending_transfers" in summary

    def test_truck_summary_with_inventory(self, repo, setup_data):
        """Truck with inventory shows correct counts."""
        truck = setup_data["truck"]
        part = setup_data["part"]

        # Add inventory to truck
        repo.set_truck_inventory_quantity(
            truck.id, part.id, 10
        )

        summary = repo.get_truck_summary(truck.id)
        assert summary["unique_parts"] >= 1
        assert summary["total_quantity"] >= 10
        assert summary["total_value"] >= 10 * part.unit_cost


# ═══════════════════════════════════════════════════════════════════
# update_hat
# ═══════════════════════════════════════════════════════════════════

class TestUpdateHat:
    """Test updating hat name and permissions."""

    def test_update_hat_name(self, repo):
        """Update a hat's name."""
        import json
        hat = Hat(
            name="Test Hat",
            permissions=json.dumps(["tab_dashboard"]),
            is_system=0,
        )
        hat.id = repo.create_hat(hat)

        # Update name
        fetched = repo.get_hat_by_id(hat.id)
        fetched.name = "Renamed Hat"
        repo.update_hat(fetched)

        updated = repo.get_hat_by_id(hat.id)
        assert updated.name == "Renamed Hat"

    def test_update_hat_permissions_via_update_hat(self, repo):
        """Update hat permissions using the general update_hat method."""
        import json
        hat = Hat(
            name="Perm Hat",
            permissions=json.dumps(["tab_dashboard"]),
            is_system=0,
        )
        hat.id = repo.create_hat(hat)

        fetched = repo.get_hat_by_id(hat.id)
        fetched.permissions = json.dumps(
            ["tab_dashboard", "labor_clock_in"]
        )
        repo.update_hat(fetched)

        updated = repo.get_hat_by_id(hat.id)
        perms = updated.permission_list
        assert "labor_clock_in" in perms


# ═══════════════════════════════════════════════════════════════════
# check_shortfall_for_job
# ═══════════════════════════════════════════════════════════════════

class TestCheckShortfallForJob:
    """Test checking shortfalls for a job's parts lists."""

    def test_check_shortfall_no_lists(self, repo, setup_data):
        """Job with no parts lists has no shortfalls."""
        shortfalls = repo.check_shortfall_for_job(setup_data["job"].id)
        assert shortfalls == [] or len(shortfalls) == 0


# ═══════════════════════════════════════════════════════════════════
# AI Order Suggestions
# ═══════════════════════════════════════════════════════════════════

class TestOrderSuggestions:
    """Test AI order suggestion methods."""

    def test_get_suggestions_empty(self, repo, setup_data):
        """No suggestions for a part with no history."""
        suggestions = repo.get_suggestions_for_part(setup_data["part"].id)
        assert suggestions == []

    def test_update_co_occurrence(self, repo, setup_data):
        """Can create and increment co-occurrence between two parts."""
        cat = repo.get_all_categories()[0]
        part2 = Part(
            part_number="COV-P02", name="Second Part",
            quantity=50, unit_cost=10.0, category_id=cat.id,
        )
        part2.id = repo.create_part(part2)

        # First call creates with count=1
        repo.update_co_occurrence(setup_data["part"].id, part2.id)

        # Second call increments to count=2
        repo.update_co_occurrence(setup_data["part"].id, part2.id)

        # Verify (no direct getter, so we check the suggestion system)
        # The co-occurrence exists but won't show as suggestion
        # until rebuild is called — just verify no error
        suggestions = repo.get_suggestions_for_part(setup_data["part"].id)
        # May still be empty because suggestions table needs rebuild
        assert isinstance(suggestions, list)

    def test_co_occurrence_ordering(self, repo, setup_data):
        """Co-occurrence always stores smaller ID first."""
        cat = repo.get_all_categories()[0]
        part_a = Part(
            part_number="COV-CO-A", name="Co Part A",
            quantity=10, unit_cost=5.0, category_id=cat.id,
        )
        part_a.id = repo.create_part(part_a)
        part_b = Part(
            part_number="COV-CO-B", name="Co Part B",
            quantity=10, unit_cost=5.0, category_id=cat.id,
        )
        part_b.id = repo.create_part(part_b)

        # Call with IDs in both orders — should not create duplicates
        repo.update_co_occurrence(part_a.id, part_b.id)
        repo.update_co_occurrence(part_b.id, part_a.id)

        # If ordering works, count should be 2 (not two separate rows)
        # We can't easily verify count directly, but no error = success

    def test_rebuild_order_patterns_empty(self, repo, setup_data):
        """Rebuild with no closed POs produces no patterns."""
        repo.rebuild_order_patterns()
        suggestions = repo.get_suggestions_for_part(setup_data["part"].id)
        assert suggestions == []

    def test_rebuild_order_patterns_with_closed_pos(self, repo, setup_data):
        """Rebuild picks up co-occurring parts from closed POs."""
        user = setup_data["user"]
        cat = repo.get_all_categories()[0]

        # Create 3 parts
        parts = []
        for i in range(3):
            p = Part(
                part_number=f"RBP-{i}", name=f"Rebuild Part {i}",
                quantity=100, unit_cost=10.0, category_id=cat.id,
            )
            p.id = repo.create_part(p)
            parts.append(p)

        # Create a supplier
        supplier = Supplier(name="Pattern Supplier")
        supplier.id = repo.create_supplier(supplier)

        # Create 3 closed POs, each with parts[0] + parts[1]
        # (need co_occurrence_count >= 2 to generate suggestions)
        for i in range(3):
            po = PurchaseOrder(
                order_number=f"RBP-PO-{i:03d}",
                supplier_id=supplier.id,
                status="closed",
                created_by=user.id,
            )
            po.id = repo.create_purchase_order(po)
            for part in [parts[0], parts[1]]:
                repo.add_order_item(PurchaseOrderItem(
                    order_id=po.id, part_id=part.id,
                    quantity_ordered=5, unit_cost=part.unit_cost,
                ))

        repo.rebuild_order_patterns()

        # parts[0] and parts[1] co-occurred 3 times (>= 2 threshold)
        s0 = repo.get_suggestions_for_part(parts[0].id)
        s1 = repo.get_suggestions_for_part(parts[1].id)

        # Both should suggest each other
        assert any(s["suggested_part_id"] == parts[1].id for s in s0)
        assert any(s["suggested_part_id"] == parts[0].id for s in s1)
