"""Tests for purchase order CRUD, items, status workflow, and receiving."""

import json
import pytest

from wired_part.database.connection import DatabaseConnection
from wired_part.database.models import (
    Part,
    PurchaseOrder,
    PurchaseOrderItem,
    Supplier,
    User,
)
from wired_part.database.repository import Repository
from wired_part.database.schema import initialize_database


@pytest.fixture
def repo(tmp_path):
    db_path = tmp_path / "test.db"
    db = DatabaseConnection(str(db_path))
    initialize_database(db)
    return Repository(db)


@pytest.fixture
def supplier(repo):
    s = Supplier(name="Acme Electric", contact_name="John", is_active=1)
    s.id = repo.create_supplier(s)
    return s


@pytest.fixture
def parts(repo):
    """Create a few test parts."""
    p1 = Part(
        part_number="WIRE-001",
        description="14 AWG Wire",
        quantity=100,
        unit_cost=0.50,
        min_quantity=20,
    )
    p1.id = repo.create_part(p1)

    p2 = Part(
        part_number="COND-001",
        description='1/2" EMT Conduit',
        quantity=50,
        unit_cost=3.25,
        min_quantity=10,
    )
    p2.id = repo.create_part(p2)

    p3 = Part(
        part_number="BOX-001",
        description="4x4 Junction Box",
        quantity=30,
        unit_cost=2.75,
        min_quantity=5,
    )
    p3.id = repo.create_part(p3)

    return [p1, p2, p3]


@pytest.fixture
def test_user(repo):
    user = User(
        username="testuser",
        display_name="Test User",
        pin_hash=Repository.hash_pin("1234"),
        role="admin",
    )
    user.id = repo.create_user(user)
    return user


@pytest.fixture
def draft_order(repo, supplier, parts, test_user):
    """Create a draft order with items."""
    order = PurchaseOrder(
        order_number=repo.generate_order_number(),
        supplier_id=supplier.id,
        status="draft",
        notes="Test order",
        created_by=test_user.id,
    )
    order.id = repo.create_purchase_order(order)

    for p in parts[:2]:
        item = PurchaseOrderItem(
            order_id=order.id,
            part_id=p.id,
            quantity_ordered=10,
            unit_cost=p.unit_cost,
        )
        repo.add_order_item(item)

    return order


class TestPurchaseOrderCRUD:
    """Test purchase order create, read, update, delete."""

    def test_create_purchase_order(self, repo, supplier, test_user):
        order = PurchaseOrder(
            order_number=repo.generate_order_number(),
            supplier_id=supplier.id,
            status="draft",
            notes="Test PO",
            created_by=test_user.id,
        )
        order_id = repo.create_purchase_order(order)
        assert order_id > 0

    def test_get_order_by_id(self, repo, draft_order):
        order = repo.get_purchase_order_by_id(draft_order.id)
        assert order is not None
        assert order.order_number == draft_order.order_number
        assert order.supplier_name == "Acme Electric"
        assert order.item_count == 2
        assert order.status == "draft"

    def test_get_order_by_id_not_found(self, repo):
        order = repo.get_purchase_order_by_id(99999)
        assert order is None

    def test_get_all_orders(self, repo, draft_order):
        orders = repo.get_all_purchase_orders()
        assert len(orders) >= 1
        assert any(o.id == draft_order.id for o in orders)

    def test_get_all_orders_by_status(self, repo, draft_order):
        drafts = repo.get_all_purchase_orders(status="draft")
        assert len(drafts) >= 1

        submitted = repo.get_all_purchase_orders(status="submitted")
        assert len(submitted) == 0

    def test_search_orders(self, repo, draft_order):
        results = repo.search_purchase_orders("Acme")
        assert len(results) >= 1

        results = repo.search_purchase_orders("NONEXISTENT")
        assert len(results) == 0

    def test_update_order(self, repo, draft_order):
        draft_order.notes = "Updated notes"
        repo.update_purchase_order(draft_order)

        updated = repo.get_purchase_order_by_id(draft_order.id)
        assert updated.notes == "Updated notes"

    def test_delete_draft_order(self, repo, draft_order):
        repo.delete_purchase_order(draft_order.id)
        order = repo.get_purchase_order_by_id(draft_order.id)
        assert order is None

    def test_cannot_delete_submitted_order(self, repo, draft_order):
        repo.submit_purchase_order(draft_order.id)
        with pytest.raises(ValueError, match="Only draft"):
            repo.delete_purchase_order(draft_order.id)

    def test_generate_order_number(self, repo):
        num = repo.generate_order_number()
        assert num.startswith("PO-")
        assert len(num.split("-")) == 3

    def test_generate_order_number_increments(self, repo, supplier, test_user):
        num1 = repo.generate_order_number()
        order = PurchaseOrder(
            order_number=num1,
            supplier_id=supplier.id,
            created_by=test_user.id,
        )
        repo.create_purchase_order(order)

        num2 = repo.generate_order_number()
        # Second number should be different
        assert num2 != num1


class TestPurchaseOrderItems:
    """Test order line item operations."""

    def test_add_order_item(self, repo, draft_order, parts):
        item = PurchaseOrderItem(
            order_id=draft_order.id,
            part_id=parts[2].id,
            quantity_ordered=5,
            unit_cost=2.75,
        )
        item_id = repo.add_order_item(item)
        assert item_id > 0

    def test_get_order_items(self, repo, draft_order):
        items = repo.get_order_items(draft_order.id)
        assert len(items) == 2
        assert all(i.part_number != "" for i in items)
        assert all(i.quantity_ordered == 10 for i in items)

    def test_update_order_item(self, repo, draft_order):
        items = repo.get_order_items(draft_order.id)
        items[0].quantity_ordered = 20
        items[0].unit_cost = 1.00
        repo.update_order_item(items[0])

        updated = repo.get_order_items(draft_order.id)
        target = [i for i in updated if i.id == items[0].id][0]
        assert target.quantity_ordered == 20
        assert target.unit_cost == 1.00

    def test_remove_order_item(self, repo, draft_order):
        items = repo.get_order_items(draft_order.id)
        repo.remove_order_item(items[0].id)

        remaining = repo.get_order_items(draft_order.id)
        assert len(remaining) == 1

    def test_create_order_from_parts_list(
        self, repo, supplier, parts, test_user
    ):
        # Create a parts list
        from wired_part.database.models import PartsList, PartsListItem
        pl = PartsList(
            name="Test List",
            list_type="general",
            created_by=test_user.id,
        )
        pl_id = repo.create_parts_list(pl)

        repo.add_item_to_parts_list(PartsListItem(
            list_id=pl_id, part_id=parts[0].id, quantity=5
        ))
        repo.add_item_to_parts_list(PartsListItem(
            list_id=pl_id, part_id=parts[1].id, quantity=3
        ))

        order_id = repo.create_order_from_parts_list(
            pl_id, supplier.id, test_user.id
        )
        assert order_id > 0

        order = repo.get_purchase_order_by_id(order_id)
        assert order.parts_list_id == pl_id
        assert order.item_count == 2

        items = repo.get_order_items(order_id)
        assert len(items) == 2
        qtys = sorted([i.quantity_ordered for i in items])
        assert qtys == [3, 5]


class TestOrderStatusWorkflow:
    """Test order status transitions."""

    def test_submit_order(self, repo, draft_order):
        repo.submit_purchase_order(draft_order.id)
        order = repo.get_purchase_order_by_id(draft_order.id)
        assert order.status == "submitted"
        assert order.submitted_at is not None

    def test_cannot_submit_non_draft(self, repo, draft_order):
        repo.submit_purchase_order(draft_order.id)
        # Trying to submit again should not change anything
        repo.submit_purchase_order(draft_order.id)
        order = repo.get_purchase_order_by_id(draft_order.id)
        assert order.status == "submitted"

    def test_cancel_order(self, repo, draft_order):
        repo.cancel_purchase_order(draft_order.id)
        order = repo.get_purchase_order_by_id(draft_order.id)
        assert order.status == "cancelled"

    def test_close_order(self, repo, draft_order):
        repo.submit_purchase_order(draft_order.id)
        repo.close_purchase_order(draft_order.id, force=True)
        order = repo.get_purchase_order_by_id(draft_order.id)
        assert order.status == "closed"
        assert order.closed_at is not None

    def test_order_is_editable(self, repo, draft_order):
        order = repo.get_purchase_order_by_id(draft_order.id)
        assert order.is_editable is True

        repo.submit_purchase_order(draft_order.id)
        order = repo.get_purchase_order_by_id(draft_order.id)
        assert order.is_editable is False

    def test_order_is_receivable(self, repo, draft_order):
        order = repo.get_purchase_order_by_id(draft_order.id)
        assert order.is_receivable is False

        repo.submit_purchase_order(draft_order.id)
        order = repo.get_purchase_order_by_id(draft_order.id)
        assert order.is_receivable is True


class TestOrderReceiving:
    """Test order receiving workflow."""

    def test_receive_to_warehouse(self, repo, draft_order, parts, test_user):
        repo.submit_purchase_order(draft_order.id)
        items = repo.get_order_items(draft_order.id)

        # Use the actual part_id from the first order item
        target_part_id = items[0].part_id
        initial_qty = repo.get_part_by_id(target_part_id).quantity

        receipts = [{
            "order_item_id": items[0].id,
            "quantity_received": 5,
            "allocate_to": "warehouse",
        }]
        count = repo.receive_order_items(
            draft_order.id, receipts, test_user.id
        )
        assert count == 1

        # Warehouse quantity should increase
        updated_part = repo.get_part_by_id(target_part_id)
        assert updated_part.quantity == initial_qty + 5

    def test_receive_to_truck(self, repo, draft_order, parts, test_user):
        from wired_part.database.models import Truck
        truck = Truck(truck_number="T-001", name="Test Truck")
        truck.id = repo.create_truck(truck)

        repo.submit_purchase_order(draft_order.id)
        items = repo.get_order_items(draft_order.id)
        target_part_id = items[0].part_id

        receipts = [{
            "order_item_id": items[0].id,
            "quantity_received": 3,
            "allocate_to": "truck",
            "allocate_truck_id": truck.id,
        }]
        repo.receive_order_items(draft_order.id, receipts, test_user.id)

        # Should create a pending truck transfer
        transfers = repo.get_all_pending_transfers()
        truck_transfers = [
            t for t in transfers
            if t.truck_id == truck.id and t.part_id == target_part_id
        ]
        assert len(truck_transfers) >= 1
        assert truck_transfers[0].quantity == 3

    def test_partial_receive(self, repo, draft_order, parts, test_user):
        repo.submit_purchase_order(draft_order.id)
        items = repo.get_order_items(draft_order.id)

        # Receive only part of the first item
        receipts = [{
            "order_item_id": items[0].id,
            "quantity_received": 3,
            "allocate_to": "warehouse",
        }]
        repo.receive_order_items(draft_order.id, receipts, test_user.id)

        order = repo.get_purchase_order_by_id(draft_order.id)
        assert order.status == "partial"

    def test_full_receive_changes_status(
        self, repo, draft_order, parts, test_user
    ):
        repo.submit_purchase_order(draft_order.id)
        items = repo.get_order_items(draft_order.id)

        # Receive all items fully
        receipts = [
            {
                "order_item_id": item.id,
                "quantity_received": item.quantity_ordered,
                "allocate_to": "warehouse",
            }
            for item in items
        ]
        repo.receive_order_items(draft_order.id, receipts, test_user.id)

        order = repo.get_purchase_order_by_id(draft_order.id)
        # With AUTO_CLOSE_RECEIVED_ORDERS=True (default), fully received
        # orders are auto-closed
        assert order.status == "closed"

    def test_receive_creates_log(self, repo, draft_order, parts, test_user):
        repo.submit_purchase_order(draft_order.id)
        items = repo.get_order_items(draft_order.id)

        receipts = [{
            "order_item_id": items[0].id,
            "quantity_received": 5,
            "allocate_to": "warehouse",
            "notes": "Box 1 of 2",
        }]
        repo.receive_order_items(draft_order.id, receipts, test_user.id)

        log = repo.get_receive_log(order_id=draft_order.id)
        assert len(log) == 1
        assert log[0].quantity_received == 5
        assert log[0].allocate_to == "warehouse"
        assert log[0].notes == "Box 1 of 2"

    def test_receive_updates_warehouse_quantity(
        self, repo, draft_order, parts, test_user
    ):
        repo.submit_purchase_order(draft_order.id)
        items = repo.get_order_items(draft_order.id)
        target_part_id = items[0].part_id

        initial_qty = repo.get_part_by_id(target_part_id).quantity

        receipts = [{
            "order_item_id": items[0].id,
            "quantity_received": 7,
            "allocate_to": "warehouse",
        }]
        repo.receive_order_items(draft_order.id, receipts, test_user.id)

        part = repo.get_part_by_id(target_part_id)
        assert part.quantity == initial_qty + 7

    def test_allocation_suggestions(self, repo, parts):
        suggestions = repo.get_allocation_suggestions(parts[0].id)
        assert len(suggestions) >= 1
        # Should at least suggest warehouse
        targets = [s["target"] for s in suggestions]
        assert "warehouse" in targets

    def test_receive_summary(self, repo, draft_order, parts, test_user):
        summary = repo.get_order_receive_summary(draft_order.id)
        assert summary["total_items"] == 2
        assert summary["total_ordered"] == 20  # 10 + 10
        assert summary["total_received"] == 0

        repo.submit_purchase_order(draft_order.id)
        items = repo.get_order_items(draft_order.id)
        receipts = [{
            "order_item_id": items[0].id,
            "quantity_received": 5,
            "allocate_to": "warehouse",
        }]
        repo.receive_order_items(draft_order.id, receipts, test_user.id)

        summary = repo.get_order_receive_summary(draft_order.id)
        assert summary["total_received"] == 5
