"""E2E tests for Sessions K-L (Loops 51-60): final features and hardening.

Simulated user feedback driving each section:
  Loop 51 — "I click buttons too fast and get errors"
  Loop 52 — "Import fails silently when my CSV has weird formatting"
  Loop 53 — "I need to see cost breakdowns for jobs"
  Loop 54 — "The agent doesn't know about chat, returns, or billing"
  Loop 55 — "Permissions don't stop me from doing things I shouldn't"
  Loop 56 — "Activity log doesn't capture most of what I do"
  Loop 57 — "I have 500 parts and scrolling through lists is slow"
  Loop 58 — "Error messages don't make sense to non-technical users"
  Loop 59 — "The app should tell me what's important when I open it"
  Loop 60 — "I feel confident using this app every day — it just works"
"""

from datetime import datetime, timedelta

import pytest

from wired_part.database.models import (
    Job, JobAssignment, LaborEntry, Notification, Part,
    PurchaseOrder, PurchaseOrderItem, ReturnAuthorization,
    ReturnAuthorizationItem, Supplier, Truck, TruckTransfer, User,
)
from wired_part.database.repository import Repository


@pytest.fixture
def final_data(repo):
    """Comprehensive data for final hardening tests."""
    admin = User(
        username="finaladmin", display_name="Final Admin",
        pin_hash=Repository.hash_pin("0000"), role="admin",
    )
    admin.id = repo.create_user(admin)

    cat = repo.get_all_categories()[0]

    # Many parts for pagination/stress testing
    parts = []
    for i in range(25):
        p = Part(
            part_number=f"FIN-P{i:03d}",
            description=f"Final Part {i}",
            name=f"Final Part {i}",
            quantity=10 + i * 5,
            unit_cost=5.0 + i,
            category_id=cat.id,
            min_quantity=50 if i < 5 else 5,
        )
        p.id = repo.create_part(p)
        parts.append(p)

    sup = Supplier(
        name="Final Supply Co", contact_name="Final",
        email="f@f.com", phone="555-FIN", is_supply_house=1,
    )
    sup.id = repo.create_supplier(sup)

    truck = Truck(
        truck_number="T-FIN", name="Final Van",
        assigned_user_id=admin.id,
    )
    truck.id = repo.create_truck(truck)

    jobs = []
    for i in range(5):
        j = Job(
            job_number=f"JOB-FIN-{i:03d}",
            name=f"Final Job {i}",
            customer=f"Client {i}",
            status="active",
        )
        j.id = repo.create_job(j)
        repo.assign_user_to_job(JobAssignment(
            job_id=j.id, user_id=admin.id, role="lead",
        ))
        jobs.append(j)

    # Add labor entries across jobs
    now = datetime.now()
    for i, j in enumerate(jobs[:3]):
        repo.create_labor_entry(LaborEntry(
            user_id=admin.id, job_id=j.id,
            start_time=(now - timedelta(hours=4 + i)).isoformat(),
            end_time=now.isoformat(),
            hours=4.0 + i, sub_task_category="General",
        ))

    # Create orders
    for i in range(3):
        po = PurchaseOrder(
            supplier_id=sup.id, status="submitted",
            order_number=f"PO-FIN-{i:03d}",
        )
        po.id = repo.create_purchase_order(po)
        oi = PurchaseOrderItem(
            order_id=po.id, part_id=parts[i].id,
            quantity_ordered=20, unit_cost=parts[i].unit_cost,
        )
        repo.add_order_item(oi)

    return {
        "admin": admin, "parts": parts, "sup": sup,
        "truck": truck, "jobs": jobs,
    }


# =====================================================================
# Loop 51 — Double-submit protection (idempotency checks)
# =====================================================================


class TestDoubleSubmitProtection:
    """Verify that rapid repeat operations don't cause corruption."""

    def test_double_create_job_different_numbers(self, repo, final_data):
        """Two jobs with different numbers should work."""
        j1 = Job(
            job_number="DOUBLE-001", name="First",
            customer="C", status="active",
        )
        j2 = Job(
            job_number="DOUBLE-002", name="Second",
            customer="C", status="active",
        )
        j1.id = repo.create_job(j1)
        j2.id = repo.create_job(j2)
        assert j1.id != j2.id

    def test_transfer_respects_stock(self, repo, final_data):
        """Two rapid transfers shouldn't overdraft warehouse."""
        d = final_data
        part = d["parts"][10]  # has quantity = 10 + 10*5 = 60
        t1 = repo.create_transfer(TruckTransfer(
            part_id=part.id, truck_id=d["truck"].id,
            quantity=30, created_by=d["admin"].id,
        ))
        # Second transfer for same amount
        t2 = repo.create_transfer(TruckTransfer(
            part_id=part.id, truck_id=d["truck"].id,
            quantity=30, created_by=d["admin"].id,
        ))
        # Warehouse should be at 0 now
        p = repo.get_part_by_id(part.id)
        assert p.quantity == 0

        # Third transfer should fail
        with pytest.raises(ValueError):
            repo.create_transfer(TruckTransfer(
                part_id=part.id, truck_id=d["truck"].id,
                quantity=1, created_by=d["admin"].id,
            ))


# =====================================================================
# Loop 52 — Import validation
# =====================================================================


class TestImportValidation:
    """CSV import handles edge cases."""

    def test_invalid_category_rejected(self, repo, final_data):
        """Creating a part with non-existent category_id should fail."""
        p = Part(
            part_number="BAD-CAT-001",
            name="Bad Category", quantity=5,
            category_id=99999,  # does not exist
        )
        with pytest.raises(Exception):  # IntegrityError from FK
            repo.create_part(p)

    def test_duplicate_part_numbers_allowed(self, repo, final_data):
        """Parts with duplicate part_numbers can coexist (no UNIQUE constraint)."""
        p = Part(
            part_number="FIN-P000",  # already exists
            name="Duplicate OK", quantity=5,
            category_id=final_data["parts"][0].category_id,
        )
        p.id = repo.create_part(p)
        assert p.id > 0


# =====================================================================
# Loop 53 — Job cost breakdowns
# =====================================================================


class TestJobCostBreakdown:
    """Job cost tracking via labor and parts."""

    def test_labor_summary_for_job(self, repo, final_data):
        d = final_data
        summary = repo.get_labor_summary_for_job(d["jobs"][0].id)
        assert summary["total_hours"] >= 4.0
        assert summary["entry_count"] >= 1

    def test_job_total_cost(self, repo, final_data):
        d = final_data
        cost = repo.get_job_total_cost(d["jobs"][0].id)
        assert isinstance(cost, (int, float))


# =====================================================================
# Loop 54 — Agent tools coverage
# =====================================================================


class TestAgentToolsCoverage:
    """Repository methods used by agent tools work correctly."""

    def test_inventory_summary(self, repo, final_data):
        summary = repo.get_inventory_summary()
        assert "total_parts" in summary
        assert summary["total_parts"] >= 25

    def test_orders_summary(self, repo, final_data):
        summary = repo.get_orders_summary()
        assert "pending_orders" in summary

    def test_job_summary(self, repo, final_data):
        summary = repo.get_job_summary()
        assert "total_jobs" in summary
        assert summary["total_jobs"] >= 5


# =====================================================================
# Loop 55 — Permission checks
# =====================================================================


class TestPermissionEnforcement:
    """Critical operations require proper authorization."""

    def test_order_close_requires_force_with_unreceived(
        self, repo, final_data
    ):
        d = final_data
        # Create a submitted order with items
        po = PurchaseOrder(
            supplier_id=d["sup"].id, status="submitted",
            order_number="PO-PERM-001",
        )
        po.id = repo.create_purchase_order(po)
        oi = PurchaseOrderItem(
            order_id=po.id, part_id=d["parts"][15].id,
            quantity_ordered=10, unit_cost=20.0,
        )
        repo.add_order_item(oi)

        with pytest.raises(ValueError, match="unreceived"):
            repo.close_purchase_order(po.id)

    def test_job_delete_requires_force_with_labor(
        self, repo, final_data
    ):
        d = final_data
        with pytest.raises(ValueError):
            repo.delete_job(d["jobs"][0].id)


# =====================================================================
# Loop 56 — Activity log coverage
# =====================================================================


class TestActivityLogCoverage:
    """Activity log captures key operations."""

    def test_activity_log_has_entries(self, repo, final_data):
        d = final_data
        # Explicitly log an activity entry
        repo.log_activity(
            user_id=d["admin"].id, action="created",
            entity_type="part", entity_id=d["parts"][0].id,
            entity_label=d["parts"][0].part_number,
        )
        log = repo.get_recent_activity(limit=50)
        assert len(log) >= 1

    def test_entity_activity(self, repo, final_data):
        d = final_data
        repo.log_activity(
            user_id=d["admin"].id, action="updated",
            entity_type="part", entity_id=d["parts"][0].id,
            entity_label=d["parts"][0].part_number,
        )
        activity = repo.get_entity_activity("part", d["parts"][0].id)
        assert isinstance(activity, list)
        assert len(activity) >= 1


# =====================================================================
# Loop 57 — Large dataset pagination
# =====================================================================


class TestLargeDatasetPagination:
    """Pagination works correctly with many records."""

    def test_iterate_all_parts(self, repo, final_data):
        """Walk through all pages and verify total matches."""
        all_items = []
        offset = 0
        while True:
            page = repo.get_parts_paginated(limit=5, offset=offset)
            if not page["items"]:
                break
            all_items.extend(page["items"])
            offset += 5
            if offset >= page["total_count"]:
                break
        assert len(all_items) == page["total_count"]

    def test_iterate_all_jobs(self, repo, final_data):
        all_items = []
        offset = 0
        while True:
            page = repo.get_jobs_paginated(limit=3, offset=offset)
            if not page["items"]:
                break
            all_items.extend(page["items"])
            offset += 3
            if offset >= page["total_count"]:
                break
        assert len(all_items) == page["total_count"]


# =====================================================================
# Loop 58 — Validation and error messages
# =====================================================================


class TestValidationMessages:
    """Operations give clear error messages on invalid input."""

    def test_return_insufficient_stock_message(self, repo, final_data):
        d = final_data
        # Try to return more than in warehouse
        part = d["parts"][0]
        ra = ReturnAuthorization(
            ra_number="RA-FAIL", supplier_id=d["sup"].id,
            created_by=d["admin"].id,
        )
        items = [ReturnAuthorizationItem(
            part_id=part.id, quantity=9999, unit_cost=5.0,
        )]
        with pytest.raises(ValueError, match="[Ii]nsufficient"):
            repo.create_return_authorization(ra, items)

    def test_transfer_insufficient_stock_message(self, repo, final_data):
        d = final_data
        with pytest.raises(ValueError):
            repo.create_transfer(TruckTransfer(
                part_id=d["parts"][0].id, truck_id=d["truck"].id,
                quantity=9999, created_by=d["admin"].id,
            ))


# =====================================================================
# Loop 59 — Dashboard actionable items
# =====================================================================


class TestDashboardActionable:
    """Dashboard shows actionable data."""

    def test_dashboard_shows_active_jobs(self, repo, final_data):
        summary = repo.get_dashboard_summary()
        assert summary["active_jobs"] >= 5

    def test_low_stock_alerts_found(self, repo, final_data):
        alerts = repo.get_low_stock_alerts()
        # Parts 0-4 have min_quantity=50 but qty ranges from 10-30
        low = [a for a in alerts if a["location"] == "warehouse"]
        assert len(low) >= 1

    def test_spending_by_supplier(self, repo, final_data):
        spending = repo.get_spending_by_supplier()
        assert isinstance(spending, list)


# =====================================================================
# Loop 60 — Full system audit
# =====================================================================


class TestFullSystemAudit:
    """Final verification that everything works together."""

    def test_app_statistics_complete(self, repo, final_data):
        stats = repo.get_app_statistics()
        assert stats["parts"]["count"] >= 25
        assert stats["jobs"]["count"] >= 5
        assert stats["users"]["count"] >= 1
        assert stats["suppliers"]["count"] >= 1

    def test_all_pipelines_accessible(self, repo, final_data):
        """All major query methods return without error."""
        d = final_data
        # Parts
        assert len(repo.get_all_parts()) >= 25
        # Jobs
        assert len(repo.get_all_jobs()) >= 5
        # Orders
        assert len(repo.get_all_purchase_orders()) >= 3
        # Returns
        repo.get_all_return_authorizations()  # No crash
        # Trucks
        repo.get_truck_utilization()
        # Labor analytics
        repo.get_labor_analytics()
        # Dashboard
        repo.get_dashboard_summary()
        # Search
        repo.search_all("Final")
        # Return pipeline
        repo.get_return_pipeline_summary()

    def test_pagination_consistency_across_entities(self, repo, final_data):
        """Paginated counts match full list counts."""
        parts_all = repo.get_all_parts()
        parts_paged = repo.get_parts_paginated(limit=100)
        assert parts_paged["total_count"] == len(parts_all)

        jobs_all = repo.get_all_jobs()
        jobs_paged = repo.get_jobs_paginated(limit=100)
        assert jobs_paged["total_count"] == len(jobs_all)

    def test_analytics_dont_crash_on_empty_filters(self, repo, final_data):
        """Analytics methods handle empty/extreme filters."""
        repo.get_spending_by_supplier(date_from="2099-01-01")
        repo.get_labor_analytics(date_from="2099-01-01", date_to="2099-01-02")
        repo.get_labor_analytics(job_id=9999)


# =====================================================================
# Theme & Permission Constants Integrity
# =====================================================================


class TestThemeAndPermissions:
    """Verify theme files exist and permission keys are complete."""

    def test_retro_qss_exists(self):
        """Retro CRT theme file must exist alongside dark and light."""
        from pathlib import Path
        styles_dir = (
            Path(__file__).resolve().parent.parent.parent
            / "src" / "wired_part" / "ui" / "styles"
        )
        assert (styles_dir / "dark.qss").exists()
        assert (styles_dir / "light.qss").exists()
        assert (styles_dir / "retro.qss").exists()

    def test_retro_qss_has_green_text(self):
        """Retro theme should use green terminal colors."""
        from pathlib import Path
        retro = (
            Path(__file__).resolve().parent.parent.parent
            / "src" / "wired_part" / "ui" / "styles" / "retro.qss"
        ).read_text(encoding="utf-8")
        assert "#33ff33" in retro  # Classic green phosphor
        assert "#0a0a0a" in retro  # Black background
        assert "#ffcc00" in retro  # Yellow accent

    def test_show_dollar_values_permission_exists(self):
        """show_dollar_values must be in PERMISSION_KEYS."""
        from wired_part.utils.constants import PERMISSION_KEYS
        assert "show_dollar_values" in PERMISSION_KEYS

    def test_show_dollar_values_in_admin_hat(self):
        """Admin hat gets show_dollar_values via full key list."""
        from wired_part.utils.constants import DEFAULT_HAT_PERMISSIONS
        assert "show_dollar_values" in DEFAULT_HAT_PERMISSIONS[
            "Admin / CEO / Owner"
        ]

    def test_show_dollar_values_not_in_office_hat(self):
        """Office/HR hat does NOT get show_dollar_values by default."""
        from wired_part.utils.constants import DEFAULT_HAT_PERMISSIONS
        assert "show_dollar_values" not in DEFAULT_HAT_PERMISSIONS[
            "Office / HR"
        ]

    def test_show_dollar_values_not_in_worker_hat(self):
        """Worker hat should NOT have show_dollar_values."""
        from wired_part.utils.constants import DEFAULT_HAT_PERMISSIONS
        assert "show_dollar_values" not in DEFAULT_HAT_PERMISSIONS[
            "Worker"
        ]

    def test_office_hat_not_locked(self):
        """Office/HR hat (ID 3) should be editable, not locked."""
        from wired_part.utils.constants import LOCKED_HAT_IDS
        assert 3 not in LOCKED_HAT_IDS
        assert LOCKED_HAT_IDS == {1, 2}
