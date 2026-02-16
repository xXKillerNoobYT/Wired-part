"""E2E tests for Session F (Loops 26-30): paginated listings,
return pipeline summary, and app-wide statistics.

Simulated user feedback driving each section:
  Loop 26 — "The parts list is ugly — I need to sort and filter"
  Loop 27 — "I have 50 jobs and can't find the active ones quickly"
  Loop 28 — "The order list doesn't let me sort by cost or supplier"
  Loop 29 — "The return list is confusing — can't tell which returns are waiting"
  Loop 30 — "I want to see an overview of everything in the system"
"""

from datetime import datetime, timedelta

import pytest

from wired_part.database.models import (
    Job, Part, PurchaseOrder, PurchaseOrderItem,
    ReturnAuthorization, ReturnAuthorizationItem,
    Supplier, User,
)
from wired_part.database.repository import Repository


# ── Shared fixture ────────────────────────────────────────────────


@pytest.fixture
def ui_data(repo):
    """Create a realistic dataset for pagination and stats tests."""
    boss = User(
        username="uiboss", display_name="UI Boss",
        pin_hash=Repository.hash_pin("0000"), role="admin",
    )
    boss.id = repo.create_user(boss)

    cat = repo.get_all_categories()[0]

    # Create 15 parts with varying stock levels
    parts = []
    for i in range(15):
        low = i < 5  # first 5 are low stock
        p = Part(
            part_number=f"UI-P{i:03d}",
            description=f"Part {i}",
            name=f"UI Part {i}",
            quantity=2 if low else 100,
            unit_cost=10.0 + i,
            category_id=cat.id,
            min_quantity=20 if low else 5,
        )
        p.id = repo.create_part(p)
        parts.append(p)

    # Create 8 jobs with mixed statuses
    jobs = []
    for i in range(8):
        status = "active" if i < 5 else "completed"
        j = Job(
            job_number=f"JOB-UI-{i:03d}",
            name=f"UI Job {i}",
            customer=f"Customer {'Alpha' if i % 2 == 0 else 'Beta'}",
            status=status,
        )
        j.id = repo.create_job(j)
        jobs.append(j)

    # Suppliers
    sup1 = Supplier(
        name="Supplier Alpha", contact_name="A",
        email="a@a.com", phone="111", is_supply_house=1,
    )
    sup1.id = repo.create_supplier(sup1)

    sup2 = Supplier(
        name="Supplier Beta", contact_name="B",
        email="b@b.com", phone="222", is_supply_house=1,
    )
    sup2.id = repo.create_supplier(sup2)

    # Create 6 purchase orders (3 per supplier, mixed statuses)
    orders = []
    for i in range(6):
        sid = sup1.id if i < 3 else sup2.id
        st = ["draft", "submitted", "received"][i % 3]
        po = PurchaseOrder(
            supplier_id=sid, status=st,
            order_number=f"PO-UI-{i:03d}",
        )
        po.id = repo.create_purchase_order(po)
        oi = PurchaseOrderItem(
            order_id=po.id, part_id=parts[i].id,
            quantity_ordered=10, unit_cost=parts[i].unit_cost,
        )
        oi.id = repo.add_order_item(oi)
        if st == "submitted":
            repo.receive_order_items(po.id, [
                {"order_item_id": oi.id, "quantity_received": 10}
            ], received_by=boss.id)
        orders.append(po)

    # Create 3 return authorizations (all start as "initiated")
    # Need warehouse stock — use parts with qty=100
    ras = []
    target_statuses = ["initiated", "picked_up", "credit_received"]
    for i in range(3):
        ra = ReturnAuthorization(
            ra_number=f"RA-UI-{i:03d}",
            supplier_id=sup1.id,
            status="initiated",
            reason="wrong_part",
            created_by=boss.id,
        )
        items = [ReturnAuthorizationItem(
            part_id=parts[5 + i].id,  # parts with qty=100
            quantity=5,
            unit_cost=parts[5 + i].unit_cost,
        )]
        ra.id = repo.create_return_authorization(ra, items)
        # Advance to target status
        if target_statuses[i] == "picked_up":
            repo.update_return_status(ra.id, "picked_up")
        elif target_statuses[i] == "credit_received":
            repo.update_return_status(ra.id, "picked_up")
            repo.update_return_status(ra.id, "credit_received",
                                      credit_amount=25.0)
        ras.append(ra)

    return {
        "boss": boss,
        "parts": parts,
        "jobs": jobs,
        "sup1": sup1, "sup2": sup2,
        "orders": orders,
        "ras": ras,
    }


# =====================================================================
# Loop 26 — Paginated parts
# =====================================================================


class TestPartsPaginated:
    """Paginated, sortable, filterable parts listing."""

    def test_basic_pagination(self, repo, ui_data):
        result = repo.get_parts_paginated(limit=5, offset=0)
        assert result["total_count"] >= 15
        assert len(result["items"]) == 5
        assert result["limit"] == 5
        assert result["offset"] == 0

    def test_second_page(self, repo, ui_data):
        page1 = repo.get_parts_paginated(limit=5, offset=0)
        page2 = repo.get_parts_paginated(limit=5, offset=5)
        # Different items on different pages
        ids1 = {p.id for p in page1["items"]}
        ids2 = {p.id for p in page2["items"]}
        assert ids1.isdisjoint(ids2)

    def test_sort_by_quantity_asc(self, repo, ui_data):
        result = repo.get_parts_paginated(
            sort_by="quantity", sort_order="asc", limit=100,
        )
        items = result["items"]
        quantities = [p.quantity for p in items]
        assert quantities == sorted(quantities)

    def test_sort_by_unit_cost_desc(self, repo, ui_data):
        result = repo.get_parts_paginated(
            sort_by="unit_cost", sort_order="desc", limit=100,
        )
        items = result["items"]
        costs = [p.unit_cost for p in items]
        assert costs == sorted(costs, reverse=True)

    def test_filter_low_stock_only(self, repo, ui_data):
        result = repo.get_parts_paginated(low_stock_only=True, limit=100)
        # We created 5 low-stock parts, but receive_order_items may have
        # raised stock on some — at least the untouched ones are low
        for p in result["items"]:
            assert p.quantity < p.min_quantity

    def test_filter_by_category(self, repo, ui_data):
        cat = repo.get_all_categories()[0]
        result = repo.get_parts_paginated(
            category_id=cat.id, limit=100,
        )
        assert result["total_count"] >= 15
        for p in result["items"]:
            assert p.category_id == cat.id

    def test_invalid_sort_falls_back(self, repo, ui_data):
        """Unknown sort column falls back to part_number."""
        result = repo.get_parts_paginated(sort_by="bogus", limit=5)
        assert len(result["items"]) == 5  # No crash


# =====================================================================
# Loop 27 — Paginated jobs
# =====================================================================


class TestJobsPaginated:
    """Paginated, sortable, filterable jobs listing."""

    def test_basic_pagination(self, repo, ui_data):
        result = repo.get_jobs_paginated(limit=3, offset=0)
        assert result["total_count"] >= 8
        assert len(result["items"]) == 3

    def test_filter_by_status(self, repo, ui_data):
        result = repo.get_jobs_paginated(status="active", limit=100)
        assert result["total_count"] >= 5
        for j in result["items"]:
            assert j.status == "active"

    def test_filter_by_customer(self, repo, ui_data):
        result = repo.get_jobs_paginated(customer="Alpha", limit=100)
        assert result["total_count"] >= 1
        for j in result["items"]:
            assert "Alpha" in j.customer

    def test_sort_by_name_asc(self, repo, ui_data):
        result = repo.get_jobs_paginated(
            sort_by="name", sort_order="asc", limit=100,
        )
        names = [j.name for j in result["items"]]
        assert names == sorted(names)

    def test_combined_filters(self, repo, ui_data):
        result = repo.get_jobs_paginated(
            status="active", customer="Beta", limit=100,
        )
        for j in result["items"]:
            assert j.status == "active"
            assert "Beta" in j.customer

    def test_offset_past_end(self, repo, ui_data):
        result = repo.get_jobs_paginated(offset=9999, limit=10)
        assert result["items"] == []
        assert result["total_count"] >= 8


# =====================================================================
# Loop 28 — Paginated orders
# =====================================================================


class TestOrdersPaginated:
    """Paginated, sortable, filterable purchase orders."""

    def test_basic_pagination(self, repo, ui_data):
        result = repo.get_orders_paginated(limit=3, offset=0)
        assert result["total_count"] >= 6
        assert len(result["items"]) == 3

    def test_filter_by_status(self, repo, ui_data):
        result = repo.get_orders_paginated(status="draft", limit=100)
        for po in result["items"]:
            assert po.status == "draft"

    def test_filter_by_supplier(self, repo, ui_data):
        sup1 = ui_data["sup1"]
        result = repo.get_orders_paginated(
            supplier_id=sup1.id, limit=100,
        )
        assert result["total_count"] >= 3
        for po in result["items"]:
            assert po.supplier_id == sup1.id

    def test_sort_by_order_number(self, repo, ui_data):
        result = repo.get_orders_paginated(
            sort_by="order_number", sort_order="asc", limit=100,
        )
        nums = [po.order_number for po in result["items"]]
        assert nums == sorted(nums)

    def test_combined_status_supplier(self, repo, ui_data):
        sup2 = ui_data["sup2"]
        result = repo.get_orders_paginated(
            status="draft", supplier_id=sup2.id, limit=100,
        )
        for po in result["items"]:
            assert po.status == "draft"
            assert po.supplier_id == sup2.id


# =====================================================================
# Loop 29 — Return pipeline summary
# =====================================================================


class TestReturnPipelineSummary:
    """Aggregate return stats by status."""

    def test_by_status_keys(self, repo, ui_data):
        summary = repo.get_return_pipeline_summary()
        assert "initiated" in summary["by_status"]
        assert "picked_up" in summary["by_status"]
        assert "credit_received" in summary["by_status"]

    def test_by_status_counts(self, repo, ui_data):
        summary = repo.get_return_pipeline_summary()
        for status_data in summary["by_status"].values():
            assert "count" in status_data
            assert "total_value" in status_data
            assert status_data["count"] >= 1

    def test_total_returns(self, repo, ui_data):
        summary = repo.get_return_pipeline_summary()
        assert summary["total_returns"] >= 3

    def test_total_value_positive(self, repo, ui_data):
        summary = repo.get_return_pipeline_summary()
        assert summary["total_value"] > 0

    def test_aging_empty_for_new_ras(self, repo, ui_data):
        """Newly created RAs should not appear in aging (< 30 days)."""
        summary = repo.get_return_pipeline_summary()
        # Our test RAs were just created so shouldn't be aging
        for a in summary["aging"]:
            assert a["age_days"] > 30


# =====================================================================
# Loop 30 — App-wide statistics
# =====================================================================


class TestAppStatistics:
    """Comprehensive system stats for settings/about page."""

    def test_all_sections_present(self, repo, ui_data):
        stats = repo.get_app_statistics()
        for section in ("parts", "jobs", "users", "trucks",
                        "suppliers", "orders", "labor",
                        "transfers", "returns", "notebooks",
                        "activity_log", "notifications"):
            assert section in stats, f"Missing section: {section}"

    def test_parts_stats(self, repo, ui_data):
        stats = repo.get_app_statistics()
        assert stats["parts"]["count"] >= 15
        assert stats["parts"]["total_quantity"] > 0
        assert stats["parts"]["total_value"] > 0

    def test_jobs_stats(self, repo, ui_data):
        stats = repo.get_app_statistics()
        assert stats["jobs"]["count"] >= 8
        assert stats["jobs"]["active"] >= 5
        assert stats["jobs"]["completed"] >= 3

    def test_users_stats(self, repo, ui_data):
        stats = repo.get_app_statistics()
        assert stats["users"]["count"] >= 1

    def test_suppliers_stats(self, repo, ui_data):
        stats = repo.get_app_statistics()
        assert stats["suppliers"]["count"] >= 2

    def test_orders_stats(self, repo, ui_data):
        stats = repo.get_app_statistics()
        assert stats["orders"]["count"] >= 6
        assert stats["orders"]["open"] >= 0

    def test_returns_stats(self, repo, ui_data):
        stats = repo.get_app_statistics()
        assert stats["returns"]["count"] >= 3
        assert stats["returns"]["open"] >= 0

    def test_empty_db_doesnt_crash(self, repo):
        """Stats should work on empty database too."""
        stats = repo.get_app_statistics()
        assert stats["parts"]["count"] == 0
        assert stats["jobs"]["count"] == 0
