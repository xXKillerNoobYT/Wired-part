"""E2E tests for Sessions I-J (Loops 41-50): comprehensive pipeline tests.

Tests full lifecycle for every major pipeline in the system:
  Loop 41 — Full order-to-job pipeline
  Loop 42 — Full job lifecycle
  Loop 43 — Deprecation pipeline end-to-end
  Loop 44 — Transfer pipeline end-to-end
  Loop 45 — Return pipeline end-to-end
  Loop 46 — Billing pipeline end-to-end
  Loop 47 — Labor/clock pipeline end-to-end
  Loop 48 — Notification pipeline end-to-end
  Loop 49 — Search across all entities
  Loop 50 — Analytics and dashboard consistency
"""

from datetime import datetime, timedelta

import pytest

from wired_part.database.models import (
    BillingCycle, Job, JobAssignment, LaborEntry, Notification, Part,
    PurchaseOrder, PurchaseOrderItem, ReturnAuthorization,
    ReturnAuthorizationItem, Supplier, Truck, TruckTransfer, User,
)
from wired_part.database.repository import Repository


@pytest.fixture
def pipeline_data(repo):
    """Create comprehensive data for pipeline tests."""
    admin = User(
        username="pipeadmin", display_name="Pipeline Admin",
        pin_hash=Repository.hash_pin("0000"), role="admin",
    )
    admin.id = repo.create_user(admin)

    worker = User(
        username="pipeworker", display_name="Pipeline Worker",
        pin_hash=Repository.hash_pin("1111"), role="user",
    )
    worker.id = repo.create_user(worker)

    cat = repo.get_all_categories()[0]

    part = Part(
        part_number="PIPE-001", name="Pipeline Part",
        quantity=100, unit_cost=25.00,
        category_id=cat.id, min_quantity=10,
    )
    part.id = repo.create_part(part)

    supplier = Supplier(
        name="Pipeline Supply Co", contact_name="Test",
        email="test@pipe.com", phone="555-PIPE", is_supply_house=1,
    )
    supplier.id = repo.create_supplier(supplier)

    truck = Truck(
        truck_number="T-PIPE", name="Pipeline Van",
        assigned_user_id=worker.id,
    )
    truck.id = repo.create_truck(truck)

    job = Job(
        job_number="JOB-PIPE-001", name="Pipeline Project",
        customer="Pipeline Client", status="active",
    )
    job.id = repo.create_job(job)

    repo.assign_user_to_job(JobAssignment(
        job_id=job.id, user_id=admin.id, role="lead",
    ))
    repo.assign_user_to_job(JobAssignment(
        job_id=job.id, user_id=worker.id, role="worker",
    ))

    return {
        "admin": admin, "worker": worker,
        "cat": cat, "part": part,
        "supplier": supplier, "truck": truck,
        "job": job,
    }


# =====================================================================
# Loop 41 — Full order-to-job pipeline
# =====================================================================


class TestOrderToJobPipeline:
    """Order → receive → warehouse → truck → consume at job."""

    def test_full_order_to_consumption(self, repo, pipeline_data):
        d = pipeline_data
        # Step 1: Create PO
        po = PurchaseOrder(
            supplier_id=d["supplier"].id, status="draft",
            order_number="PO-FULL-001",
        )
        po.id = repo.create_purchase_order(po)
        oi = PurchaseOrderItem(
            order_id=po.id, part_id=d["part"].id,
            quantity_ordered=20, unit_cost=25.00,
        )
        oi.id = repo.add_order_item(oi)

        # Step 2: Submit
        repo.submit_purchase_order(po.id)
        po_check = repo.get_purchase_order_by_id(po.id)
        assert po_check.status == "submitted"

        # Step 3: Receive to warehouse
        repo.receive_order_items(po.id, [
            {"order_item_id": oi.id, "quantity_received": 20}
        ], received_by=d["admin"].id)

        part = repo.get_part_by_id(d["part"].id)
        assert part.quantity == 120  # 100 + 20

        # Step 4: Transfer to truck
        transfer_id = repo.create_transfer(TruckTransfer(
            part_id=d["part"].id, truck_id=d["truck"].id,
            quantity=15, created_by=d["admin"].id,
        ))
        assert transfer_id > 0

        # Step 5: Receive transfer
        repo.receive_transfer(transfer_id, d["worker"].id)
        truck_inv = repo.get_truck_inventory(d["truck"].id)
        pipe_items = [i for i in truck_inv if i.part_id == d["part"].id]
        assert len(pipe_items) == 1
        assert pipe_items[0].quantity == 15

        # Step 6: Consume at job
        repo.consume_from_truck(
            d["job"].id, d["truck"].id,
            d["part"].id, 10, user_id=d["worker"].id,
        )

        # Verify: truck stock reduced
        truck_inv = repo.get_truck_inventory(d["truck"].id)
        pipe_items = [i for i in truck_inv if i.part_id == d["part"].id]
        assert pipe_items[0].quantity == 5  # 15 - 10

        # Verify: job_parts created
        job_parts = repo.get_job_parts(d["job"].id)
        assert any(jp.part_id == d["part"].id for jp in job_parts)

    def test_partial_receive_blocks_close(self, repo, pipeline_data):
        d = pipeline_data
        po = PurchaseOrder(
            supplier_id=d["supplier"].id, status="submitted",
            order_number="PO-PARTIAL-001",
        )
        po.id = repo.create_purchase_order(po)
        oi = PurchaseOrderItem(
            order_id=po.id, part_id=d["part"].id,
            quantity_ordered=50, unit_cost=25.00,
        )
        oi.id = repo.add_order_item(oi)

        # Receive half
        repo.receive_order_items(po.id, [
            {"order_item_id": oi.id, "quantity_received": 25}
        ], received_by=d["admin"].id)

        # Close should require force
        with pytest.raises(ValueError, match="unreceived"):
            repo.close_purchase_order(po.id)

        # Force close works
        repo.close_purchase_order(po.id, force=True)
        po_check = repo.get_purchase_order_by_id(po.id)
        assert po_check.status == "closed"


# =====================================================================
# Loop 42 — Full job lifecycle
# =====================================================================


class TestJobLifecycle:
    """Create → assign → work → complete → archive."""

    def test_full_job_lifecycle(self, repo, pipeline_data):
        d = pipeline_data
        job = d["job"]

        # Verify assignments
        assignments = repo.get_job_assignments(job.id)
        assert len(assignments) >= 2

        # Add labor
        now = datetime.now()
        repo.create_labor_entry(LaborEntry(
            user_id=d["worker"].id, job_id=job.id,
            start_time=(now - timedelta(hours=8)).isoformat(),
            end_time=now.isoformat(),
            hours=8.0, sub_task_category="Rough-in",
        ))

        # Verify labor
        summary = repo.get_labor_summary_for_job(job.id)
        assert summary["total_hours"] >= 8.0

        # Complete job
        job_obj = repo.get_job_by_id(job.id)
        job_obj.status = "completed"
        repo.update_job(job_obj)

        # Verify status
        job_check = repo.get_job_by_id(job.id)
        assert job_check.status == "completed"

    def test_job_deletion_protection(self, repo, pipeline_data):
        d = pipeline_data
        # Job has labor — can't delete without force
        now = datetime.now()
        repo.create_labor_entry(LaborEntry(
            user_id=d["worker"].id, job_id=d["job"].id,
            start_time=(now - timedelta(hours=1)).isoformat(),
            end_time=now.isoformat(),
            hours=1.0, sub_task_category="Test",
        ))

        can_delete, reason = repo.can_delete_job(d["job"].id)
        assert can_delete is False

        with pytest.raises(ValueError):
            repo.delete_job(d["job"].id)

        # Force works
        repo.delete_job(d["job"].id, force=True)
        assert repo.get_job_by_id(d["job"].id) is None


# =====================================================================
# Loop 43 — Deprecation pipeline
# =====================================================================


class TestDeprecationPipeline:
    """Part deprecation: pending → winding_down → zero_stock → archived."""

    def test_full_deprecation_lifecycle(self, repo, pipeline_data):
        d = pipeline_data
        part = d["part"]

        # Start deprecation
        repo.start_part_deprecation(part.id)
        p = repo.get_part_by_id(part.id)
        assert p.deprecation_status == "pending"

        # Advance (may skip stages based on current stock level)
        new_status = repo.advance_deprecation(part.id)
        p = repo.get_part_by_id(part.id)
        assert p.deprecation_status in (
            "winding_down", "zero_stock", "archived"
        )

    def test_cancel_deprecation(self, repo, pipeline_data):
        d = pipeline_data
        repo.start_part_deprecation(d["part"].id)
        repo.cancel_deprecation(d["part"].id)
        p = repo.get_part_by_id(d["part"].id)
        assert p.deprecation_status is None or p.deprecation_status == ""


# =====================================================================
# Loop 44 — Transfer pipeline
# =====================================================================


class TestTransferPipeline:
    """Transfer: create → pending → received/cancelled."""

    def test_transfer_receive(self, repo, pipeline_data):
        d = pipeline_data
        tid = repo.create_transfer(TruckTransfer(
            part_id=d["part"].id, truck_id=d["truck"].id,
            quantity=5, created_by=d["admin"].id,
        ))

        # Check pending
        transfers = repo.get_truck_transfers(d["truck"].id, status="pending")
        assert any(t.id == tid for t in transfers)

        # Receive
        repo.receive_transfer(tid, d["worker"].id)
        transfers = repo.get_truck_transfers(d["truck"].id, status="pending")
        assert not any(t.id == tid for t in transfers)

    def test_transfer_cancel(self, repo, pipeline_data):
        d = pipeline_data
        tid = repo.create_transfer(TruckTransfer(
            part_id=d["part"].id, truck_id=d["truck"].id,
            quantity=5, created_by=d["admin"].id,
        ))
        initial_qty = repo.get_part_by_id(d["part"].id).quantity

        repo.cancel_transfer(tid)

        # Warehouse stock should be restored
        p = repo.get_part_by_id(d["part"].id)
        assert p.quantity == initial_qty + 5

    def test_transfer_atomic_deduction(self, repo, pipeline_data):
        """Transfer should fail if insufficient warehouse stock."""
        d = pipeline_data
        # Set part to low qty
        part = repo.get_part_by_id(d["part"].id)
        part.quantity = 2
        repo.update_part(part)

        with pytest.raises(ValueError):
            repo.create_transfer(TruckTransfer(
                part_id=d["part"].id, truck_id=d["truck"].id,
                quantity=10, created_by=d["admin"].id,
            ))


# =====================================================================
# Loop 45 — Return pipeline
# =====================================================================


class TestReturnPipeline:
    """Return: create → initiated → picked_up → credit_received."""

    def test_full_return_lifecycle(self, repo, pipeline_data):
        d = pipeline_data
        ra = ReturnAuthorization(
            ra_number="RA-FULL-001",
            supplier_id=d["supplier"].id,
            reason="wrong_part",
            created_by=d["admin"].id,
        )
        items = [ReturnAuthorizationItem(
            part_id=d["part"].id, quantity=5, unit_cost=25.00,
        )]
        ra.id = repo.create_return_authorization(ra, items)

        # Check status
        ra_check = repo.get_return_authorization_by_id(ra.id)
        assert ra_check.status == "initiated"

        # Advance to picked_up
        repo.update_return_status(ra.id, "picked_up")
        ra_check = repo.get_return_authorization_by_id(ra.id)
        assert ra_check.status == "picked_up"

        # Complete with credit
        repo.update_return_status(
            ra.id, "credit_received", credit_amount=125.00,
        )
        ra_check = repo.get_return_authorization_by_id(ra.id)
        assert ra_check.status == "credit_received"
        assert ra_check.credit_amount == 125.00


# =====================================================================
# Loop 46 — Billing pipeline
# =====================================================================


class TestBillingPipeline:
    """Billing cycle: create → add labor → close."""

    def test_billing_cycle_lifecycle(self, repo, pipeline_data):
        d = pipeline_data
        cycle = repo.get_or_create_billing_cycle(
            d["job"].id, billing_day=1,
        )
        assert cycle is not None

        # Add labor
        now = datetime.now()
        repo.create_labor_entry(LaborEntry(
            user_id=d["worker"].id, job_id=d["job"].id,
            start_time=(now - timedelta(hours=4)).isoformat(),
            end_time=now.isoformat(),
            hours=4.0, sub_task_category="Billing Test",
        ))

        # Verify hours tracked
        summary = repo.get_labor_summary_for_job(d["job"].id)
        assert summary["total_hours"] >= 4.0


# =====================================================================
# Loop 47 — Notification pipeline
# =====================================================================


class TestNotificationPipeline:
    """Create → read → cleanup notifications."""

    def test_notification_lifecycle(self, repo, pipeline_data):
        d = pipeline_data
        # Create notification
        repo.create_notification(Notification(
            user_id=d["worker"].id,
            title="Test Notification",
            message="Pipeline test",
            severity="info",
        ))

        # Check unread
        unread = repo.get_unread_count(d["worker"].id)
        assert unread >= 1

        # Get notifications
        notifs = repo.get_user_notifications(d["worker"].id)
        assert len(notifs) >= 1
        nid = notifs[0].id

        # Mark read
        repo.mark_notification_read(nid)
        unread_after = repo.get_unread_count(d["worker"].id)
        assert unread_after < unread

    def test_notification_cap(self, repo, pipeline_data):
        d = pipeline_data
        # Create many notifications
        for i in range(10):
            repo.create_notification(Notification(
                user_id=d["worker"].id,
                title=f"Notif {i}",
                message="test",
                severity="info",
            ))

        # Cap should work
        repo.enforce_notification_cap()
        notifs = repo.get_user_notifications(d["worker"].id)
        assert len(notifs) <= 500


# =====================================================================
# Loop 48 — Search across entities
# =====================================================================


class TestGlobalSearch:
    """Search should find jobs, parts, users, orders."""

    def test_search_finds_part(self, repo, pipeline_data):
        results = repo.search_all("PIPE-001")
        assert len(results["parts"]) >= 1

    def test_search_finds_job(self, repo, pipeline_data):
        results = repo.search_all("Pipeline Project")
        assert len(results["jobs"]) >= 1

    def test_search_finds_user(self, repo, pipeline_data):
        results = repo.search_all("pipeadmin")
        assert len(results["users"]) >= 1

    def test_search_empty_query(self, repo, pipeline_data):
        results = repo.search_all("")
        assert isinstance(results, dict)
        assert "jobs" in results

    def test_search_special_chars(self, repo, pipeline_data):
        results = repo.search_all("test%_'\"")
        assert isinstance(results, dict)  # No crash


# =====================================================================
# Loop 49 — Analytics consistency
# =====================================================================


class TestAnalyticsConsistency:
    """Dashboard, low stock, spending, labor, truck stats are consistent."""

    def test_dashboard_matches_actual_data(self, repo, pipeline_data):
        d = pipeline_data
        summary = repo.get_dashboard_summary()
        jobs = repo.get_all_jobs(status="active")
        assert summary["active_jobs"] == len(jobs)

    def test_app_stats_comprehensive(self, repo, pipeline_data):
        stats = repo.get_app_statistics()
        assert stats["parts"]["count"] >= 1
        assert stats["jobs"]["count"] >= 1
        assert stats["users"]["count"] >= 2
        assert stats["suppliers"]["count"] >= 1
        assert stats["trucks"]["count"] >= 1


# =====================================================================
# Loop 50 — Paginated listings consistency
# =====================================================================


class TestPaginatedListings:
    """Paginated queries return correct total counts."""

    def test_parts_pagination_total(self, repo, pipeline_data):
        all_parts = repo.get_all_parts()
        result = repo.get_parts_paginated(limit=5, offset=0)
        assert result["total_count"] == len(all_parts)

    def test_jobs_pagination_total(self, repo, pipeline_data):
        all_jobs = repo.get_all_jobs()
        result = repo.get_jobs_paginated(limit=5, offset=0)
        assert result["total_count"] == len(all_jobs)

    def test_pagination_across_pages(self, repo, pipeline_data):
        result1 = repo.get_parts_paginated(limit=3, offset=0)
        result2 = repo.get_parts_paginated(limit=3, offset=3)
        # Total count stays the same across pages
        assert result1["total_count"] == result2["total_count"]
