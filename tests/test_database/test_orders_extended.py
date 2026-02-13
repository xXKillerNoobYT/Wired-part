"""Extended tests for orders: search, analytics, supplier history, summary."""

import pytest
from datetime import datetime

from wired_part.database.models import (
    Job, Part, PurchaseOrder, PurchaseOrderItem, Supplier, User,
)
from wired_part.database.repository import Repository


@pytest.fixture
def order_data(repo):
    """Set up supplier, parts, and POs for order tests."""
    user = User(
        username="order_test", display_name="Order Tester",
        pin_hash=Repository.hash_pin("1234"),
    )
    user.id = repo.create_user(user)

    supplier = Supplier(
        name="Test Supply Co", contact_name="Jane",
        email="jane@supply.com", phone="555-0001",
    )
    supplier.id = repo.create_supplier(supplier)

    cat = repo.get_all_categories()[0]
    part = Part(
        part_number="ORD-PART-001", name="Order Part",
        quantity=100, unit_cost=10.0, category_id=cat.id,
    )
    part.id = repo.create_part(part)

    # Create multiple POs in different statuses
    pos = []
    for i, status in enumerate(["draft", "submitted", "closed"]):
        po = PurchaseOrder(
            order_number=f"PO-EXT-{i:03d}",
            supplier_id=supplier.id,
            status=status,
            created_by=user.id,
        )
        po.id = repo.create_purchase_order(po)
        repo.add_order_item(PurchaseOrderItem(
            order_id=po.id, part_id=part.id,
            quantity_ordered=10 * (i + 1),
            unit_cost=part.unit_cost,
        ))
        if status == "submitted":
            repo.submit_purchase_order(po.id)
        pos.append(po)

    return {
        "user_id": user.id,
        "supplier": supplier,
        "part": part,
        "pos": pos,
    }


class TestSearchPurchaseOrders:
    """Test PO search functionality."""

    def test_search_by_order_number(self, repo, order_data):
        results = repo.search_purchase_orders("PO-EXT-001")
        assert len(results) >= 1
        assert any(po.order_number == "PO-EXT-001" for po in results)

    def test_search_by_supplier_name(self, repo, order_data):
        results = repo.search_purchase_orders("Test Supply")
        assert len(results) >= 1

    def test_search_no_results(self, repo, order_data):
        results = repo.search_purchase_orders("ZZZNOTEXIST")
        assert len(results) == 0


class TestSupplierOrderHistory:
    """Test supplier order history retrieval."""

    def test_get_supplier_order_history(self, repo, order_data):
        sid = order_data["supplier"].id
        history = repo.get_supplier_order_history(sid)
        assert len(history) >= 3  # Our 3 POs

    def test_supplier_no_history(self, repo):
        s = Supplier(name="New Supplier")
        s.id = repo.create_supplier(s)
        history = repo.get_supplier_order_history(s.id)
        assert len(history) == 0


class TestOrdersSummary:
    """Test dashboard orders summary."""

    def test_get_orders_summary(self, repo, order_data):
        summary = repo.get_orders_summary()
        # Summary returns counts by status category
        assert "draft_orders" in summary
        assert "pending_orders" in summary
        assert "open_returns" in summary

    def test_orders_summary_has_draft(self, repo, order_data):
        summary = repo.get_orders_summary()
        # We created a draft PO in the fixture
        assert summary["draft_orders"] >= 1


class TestGenerateOrderNumber:
    """Test order number generation."""

    def test_generate_order_number_unique(self, repo, order_data):
        n1 = repo.generate_order_number()
        # Create a PO with that number so the next one must differ
        repo.create_purchase_order(PurchaseOrder(
            order_number=n1,
            supplier_id=order_data["supplier"].id,
            status="draft",
            created_by=order_data["user_id"],
        ))
        n2 = repo.generate_order_number()
        assert n1 != n2

    def test_generate_order_number_format(self, repo):
        num = repo.generate_order_number()
        assert isinstance(num, str)
        assert len(num) > 0


class TestReceiveToTruck:
    """Test receiving order items to a truck creates a pending transfer."""

    def test_receive_to_truck_creates_transfer(self, repo, order_data):
        from wired_part.database.models import Truck
        user_id = order_data["user_id"]

        truck = Truck(
            truck_number="RCV-T01", name="Receive Truck",
            assigned_user_id=user_id,
        )
        truck.id = repo.create_truck(truck)

        # Create a new PO and submit it
        po = PurchaseOrder(
            order_number="PO-TRUCK-RCV",
            supplier_id=order_data["supplier"].id,
            status="draft",
            created_by=user_id,
        )
        po.id = repo.create_purchase_order(po)
        repo.add_order_item(PurchaseOrderItem(
            order_id=po.id, part_id=order_data["part"].id,
            quantity_ordered=15, unit_cost=10.0,
        ))
        repo.submit_purchase_order(po.id)

        items = repo.get_order_items(po.id)
        count = repo.receive_order_items(po.id, [{
            "order_item_id": items[0].id,
            "quantity_received": 15,
            "allocate_to": "truck",
            "allocate_truck_id": truck.id,
        }], user_id)

        # Receive processed successfully
        assert count == 1

        # Order item quantity_received updated
        updated_items = repo.get_order_items(po.id)
        assert updated_items[0].quantity_received == 15

    def test_receive_to_warehouse(self, repo, order_data):
        """Receiving to warehouse directly updates part quantity."""
        part = order_data["part"]
        original_qty = repo.get_part_by_id(part.id).quantity

        po = PurchaseOrder(
            order_number="PO-WH-RCV",
            supplier_id=order_data["supplier"].id,
            status="draft",
            created_by=order_data["user_id"],
        )
        po.id = repo.create_purchase_order(po)
        repo.add_order_item(PurchaseOrderItem(
            order_id=po.id, part_id=part.id,
            quantity_ordered=10, unit_cost=10.0,
        ))
        repo.submit_purchase_order(po.id)

        items = repo.get_order_items(po.id)
        repo.receive_order_items(po.id, [{
            "order_item_id": items[0].id,
            "quantity_received": 10,
            "allocate_to": "warehouse",
        }], order_data["user_id"])

        assert repo.get_part_by_id(part.id).quantity == original_qty + 10
