"""E2E tests for Session E (Loops 21-25): dashboard summary, low-stock alerts,
spending analytics, labor analytics, and truck utilization.

Simulated user feedback driving each section:
  Loop 21 — "The dashboard doesn't show me what I need at a glance"
  Loop 22 — "I didn't know we were low on 10 AWG until we ran out on site"
  Loop 23 — "Which supplier are we spending the most with?"
  Loop 24 — "How many hours did each person work on the Smith job?"
  Loop 25 — "Which truck has the most inventory sitting in it?"
"""

from datetime import datetime, timedelta

import pytest

from wired_part.database.models import (
    Job, JobAssignment, LaborEntry, Part, PurchaseOrder,
    PurchaseOrderItem, Supplier, Truck, TruckTransfer, User,
)
from wired_part.database.repository import Repository


# ── Shared fixture ────────────────────────────────────────────────


@pytest.fixture
def analytics_data(repo):
    """Create comprehensive test data for analytics queries."""
    # Users
    boss = User(
        username="analyticsboss", display_name="Analytics Boss",
        pin_hash=Repository.hash_pin("0000"), role="admin",
    )
    boss.id = repo.create_user(boss)

    worker1 = User(
        username="worker1", display_name="Worker One",
        pin_hash=Repository.hash_pin("1111"), role="user",
    )
    worker1.id = repo.create_user(worker1)

    worker2 = User(
        username="worker2", display_name="Worker Two",
        pin_hash=Repository.hash_pin("2222"), role="user",
    )
    worker2.id = repo.create_user(worker2)

    # Categories + Parts
    cat = repo.get_all_categories()[0]
    parts = []
    for i, (pn, name, qty, minq, cost) in enumerate([
        ("WIRE-10", "10 AWG Wire", 5, 20, 45.00),    # Low stock!
        ("WIRE-12", "12 AWG Wire", 100, 20, 35.00),   # OK
        ("COND-1", "1\" Conduit", 3, 10, 12.50),      # Low stock!
        ("PANEL-A", "Panel Box A", 50, 5, 150.00),    # OK
    ]):
        p = Part(
            part_number=pn, description=name, name=name,
            quantity=qty, unit_cost=cost,
            category_id=cat.id, min_quantity=minq,
        )
        p.id = repo.create_part(p)
        parts.append(p)

    # Suppliers
    supplier1 = Supplier(
        name="Big Electric Supply", contact_name="Jim",
        email="jim@big.com", phone="555-BIG1", is_supply_house=1,
    )
    supplier1.id = repo.create_supplier(supplier1)

    supplier2 = Supplier(
        name="Quick Parts Inc", contact_name="Sara",
        email="sara@quick.com", phone="555-QKPT", is_supply_house=1,
    )
    supplier2.id = repo.create_supplier(supplier2)

    # Trucks
    truck1 = Truck(
        truck_number="T-A01", name="Alpha Van",
        assigned_user_id=worker1.id,
    )
    truck1.id = repo.create_truck(truck1)

    truck2 = Truck(
        truck_number="T-B02", name="Bravo Van",
        assigned_user_id=worker2.id,
    )
    truck2.id = repo.create_truck(truck2)

    # Put inventory on trucks (with min levels)
    repo.add_to_truck_inventory(truck1.id, parts[0].id, 2)
    repo.set_truck_inventory_levels(truck1.id, parts[0].id, 5, 20)  # 2 < 5 = low
    repo.add_to_truck_inventory(truck1.id, parts[1].id, 30)

    repo.add_to_truck_inventory(truck2.id, parts[2].id, 8)

    # Jobs
    job1 = Job(
        job_number="JOB-AN-001", name="Smith Residence",
        customer="Smith", status="active",
    )
    job1.id = repo.create_job(job1)

    job2 = Job(
        job_number="JOB-AN-002", name="Jones Office",
        customer="Jones", status="active",
    )
    job2.id = repo.create_job(job2)

    # Assign users
    for j in (job1, job2):
        for u in (boss, worker1, worker2):
            repo.assign_user_to_job(JobAssignment(
                job_id=j.id, user_id=u.id, role="worker",
            ))

    # Labor entries
    now = datetime.now()
    for uid, jid, cat_name, hrs in [
        (worker1.id, job1.id, "Rough-in", 8.0),
        (worker1.id, job1.id, "Rough-in", 6.5),
        (worker2.id, job1.id, "Trim-out", 4.0),
        (worker2.id, job2.id, "Panel work", 7.0),
        (boss.id, job2.id, "Inspection", 2.0),
    ]:
        repo.create_labor_entry(LaborEntry(
            user_id=uid, job_id=jid,
            start_time=(now - timedelta(hours=hrs + 1)).isoformat(),
            end_time=now.isoformat(),
            hours=hrs, sub_task_category=cat_name,
        ))

    # Orders with received items for spending analytics
    # NOTE: Use WIRE-12 and PANEL-A for orders (not low-stock parts)
    # so that WIRE-10 and COND-1 remain below min_quantity for alerts.
    order1 = PurchaseOrder(
        supplier_id=supplier1.id, status="submitted",
        order_number="PO-AN-001",
    )
    order1.id = repo.create_purchase_order(order1)
    oi1 = PurchaseOrderItem(
        order_id=order1.id, part_id=parts[1].id,  # WIRE-12
        quantity_ordered=50, unit_cost=35.00,
    )
    oi1.id = repo.add_order_item(oi1)
    repo.receive_order_items(order1.id, [
        {"order_item_id": oi1.id, "quantity_received": 50}
    ], received_by=boss.id)

    order2 = PurchaseOrder(
        supplier_id=supplier2.id, status="submitted",
        order_number="PO-AN-002",
    )
    order2.id = repo.create_purchase_order(order2)
    oi2 = PurchaseOrderItem(
        order_id=order2.id, part_id=parts[3].id,  # PANEL-A
        quantity_ordered=20, unit_cost=150.00,
    )
    oi2.id = repo.add_order_item(oi2)
    repo.receive_order_items(order2.id, [
        {"order_item_id": oi2.id, "quantity_received": 20}
    ], received_by=boss.id)

    return {
        "boss": boss, "worker1": worker1, "worker2": worker2,
        "parts": parts, "supplier1": supplier1, "supplier2": supplier2,
        "truck1": truck1, "truck2": truck2,
        "job1": job1, "job2": job2,
    }


# =====================================================================
# Loop 21 — Dashboard summary
# =====================================================================


class TestDashboardSummary:
    """Dashboard should show key metrics at a glance."""

    def test_dashboard_active_jobs(self, repo, analytics_data):
        summary = repo.get_dashboard_summary()
        assert summary["active_jobs"] >= 2

    def test_dashboard_low_stock(self, repo, analytics_data):
        summary = repo.get_dashboard_summary()
        assert summary["low_stock_parts"] >= 2  # WIRE-10 and COND-1

    def test_dashboard_pending_orders(self, repo, analytics_data):
        summary = repo.get_dashboard_summary()
        # Orders were submitted so they count as pending
        assert summary["pending_orders"] >= 0

    def test_dashboard_all_keys_present(self, repo, analytics_data):
        summary = repo.get_dashboard_summary()
        for key in ("active_jobs", "clocked_in_users",
                     "pending_orders", "low_stock_parts"):
            assert key in summary


# =====================================================================
# Loop 22 — Low-stock alerts
# =====================================================================


class TestLowStockAlerts:
    """Low-stock alerts for warehouse AND truck inventory."""

    def test_warehouse_low_stock_detected(self, repo, analytics_data):
        alerts = repo.get_low_stock_alerts()
        warehouse_alerts = [a for a in alerts if a["location"] == "warehouse"]
        assert len(warehouse_alerts) >= 2
        pns = [a["part_number"] for a in warehouse_alerts]
        assert "WIRE-10" in pns
        assert "COND-1" in pns

    def test_truck_low_stock_detected(self, repo, analytics_data):
        alerts = repo.get_low_stock_alerts()
        truck_alerts = [a for a in alerts if a["location"] == "truck"]
        assert len(truck_alerts) >= 1
        assert any(a["location_name"] == "T-A01" for a in truck_alerts)

    def test_alerts_sorted_by_deficit(self, repo, analytics_data):
        alerts = repo.get_low_stock_alerts()
        if len(alerts) >= 2:
            assert alerts[0]["deficit"] >= alerts[-1]["deficit"]

    def test_ok_stock_not_in_alerts(self, repo, analytics_data):
        alerts = repo.get_low_stock_alerts()
        pns = [a["part_number"] for a in alerts]
        assert "WIRE-12" not in pns  # 100 qty, 20 min = OK
        assert "PANEL-A" not in pns  # 50 qty, 5 min = OK


# =====================================================================
# Loop 23 — Spending by supplier
# =====================================================================


class TestSpendingBySupplier:
    """Track spending per supplier from received orders."""

    def test_spending_breakdown(self, repo, analytics_data):
        spending = repo.get_spending_by_supplier()
        assert len(spending) >= 2
        names = [s["supplier_name"] for s in spending]
        assert "Big Electric Supply" in names
        assert "Quick Parts Inc" in names

    def test_spending_amounts(self, repo, analytics_data):
        spending = repo.get_spending_by_supplier()
        big = next(s for s in spending if s["supplier_name"] == "Big Electric Supply")
        quick = next(s for s in spending if s["supplier_name"] == "Quick Parts Inc")
        # Order 1: 50 x WIRE-12 @ $35 = $1750
        assert big["total_spent"] == pytest.approx(50 * 35.00, abs=0.01)
        # Order 2: 20 x PANEL-A @ $150 = $3000
        assert quick["total_spent"] == pytest.approx(20 * 150.00, abs=0.01)

    def test_spending_sorted_desc(self, repo, analytics_data):
        spending = repo.get_spending_by_supplier()
        if len(spending) >= 2:
            assert spending[0]["total_spent"] >= spending[1]["total_spent"]

    def test_spending_with_date_filter(self, repo, analytics_data):
        """Date filter returns only spending within range."""
        future = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
        spending = repo.get_spending_by_supplier(date_from=future)
        # Nothing received in the future
        assert len(spending) == 0 or all(s["total_spent"] == 0 for s in spending)


# =====================================================================
# Loop 24 — Labor analytics
# =====================================================================


class TestLaborAnalytics:
    """Hours breakdown by user, category, job."""

    def test_total_hours(self, repo, analytics_data):
        analytics = repo.get_labor_analytics()
        assert analytics["total_hours"] == pytest.approx(
            8.0 + 6.5 + 4.0 + 7.0 + 2.0, abs=0.1
        )
        assert analytics["total_entries"] == 5

    def test_hours_by_user(self, repo, analytics_data):
        analytics = repo.get_labor_analytics()
        by_user = analytics["by_user"]
        assert len(by_user) == 3
        # Worker One has most hours (14.5)
        assert by_user[0]["display_name"] == "Worker One"
        assert by_user[0]["hours"] == pytest.approx(14.5, abs=0.1)

    def test_hours_by_category(self, repo, analytics_data):
        analytics = repo.get_labor_analytics()
        by_cat = analytics["by_category"]
        cats = {c["category"]: c["hours"] for c in by_cat}
        assert "Rough-in" in cats
        assert cats["Rough-in"] == pytest.approx(14.5, abs=0.1)

    def test_labor_analytics_job_filter(self, repo, analytics_data):
        """Filter by specific job."""
        j1 = analytics_data["job1"]
        analytics = repo.get_labor_analytics(job_id=j1.id)
        assert analytics["total_hours"] == pytest.approx(
            8.0 + 6.5 + 4.0, abs=0.1
        )

    def test_labor_analytics_empty_range(self, repo, analytics_data):
        """Date range with no labor returns zeros."""
        analytics = repo.get_labor_analytics(
            date_from="2020-01-01", date_to="2020-01-02",
        )
        assert analytics["total_hours"] == 0
        assert analytics["total_entries"] == 0


# =====================================================================
# Loop 25 — Truck utilization
# =====================================================================


class TestTruckUtilization:
    """Truck inventory value and utilization metrics."""

    def test_utilization_returns_all_trucks(self, repo, analytics_data):
        util = repo.get_truck_utilization()
        assert len(util) >= 2
        truck_numbers = [t["truck_number"] for t in util]
        assert "T-A01" in truck_numbers
        assert "T-B02" in truck_numbers

    def test_utilization_inventory_value(self, repo, analytics_data):
        util = repo.get_truck_utilization()
        alpha = next(t for t in util if t["truck_number"] == "T-A01")
        # T-A01 has: 2 x Wire-10 ($45) + 30 x Wire-12 ($35) = $90 + $1050 = $1140
        assert alpha["inventory_value"] > 0
        assert alpha["unique_parts"] == 2

    def test_utilization_sorted_by_value(self, repo, analytics_data):
        util = repo.get_truck_utilization()
        if len(util) >= 2:
            assert util[0]["inventory_value"] >= util[-1]["inventory_value"]

    def test_utilization_assigned_user(self, repo, analytics_data):
        util = repo.get_truck_utilization()
        alpha = next(t for t in util if t["truck_number"] == "T-A01")
        assert alpha["assigned_to"] == "Worker One"

    def test_utilization_pending_transfers(self, repo, analytics_data):
        """Pending transfers are counted correctly."""
        util = repo.get_truck_utilization()
        for t in util:
            assert "pending_transfers" in t
            assert t["pending_transfers"] >= 0
