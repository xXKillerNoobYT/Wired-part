"""Hardening tests for order lifecycle edge cases (Phase 6)."""

import pytest

from wired_part.database.models import (
    Job,
    Part,
    PurchaseOrder,
    PurchaseOrderItem,
    Supplier,
    User,
)
from wired_part.database.repository import Repository


@pytest.fixture
def order_setup(repo):
    """Create supplier, user, part, and job for order tests."""
    supplier = Supplier(name="Hardening Supplier")
    supplier.id = repo.create_supplier(supplier)

    user = User(
        username="hardener", display_name="Hardener",
        pin_hash=Repository.hash_pin("1234"),
        role="admin", is_active=1,
    )
    user_id = repo.create_user(user)

    cat = repo.get_all_categories()[0]
    part = Part(
        part_number="HARD-001", name="Hardening Part",
        quantity=100, unit_cost=10.0, category_id=cat.id,
    )
    part.id = repo.create_part(part)

    job = Job(job_number="JOB-HARD", name="Hardening Job", status="active")
    job.id = repo.create_job(job)

    return {
        "supplier_id": supplier.id,
        "user_id": user_id,
        "part_id": part.id,
        "job_id": job.id,
    }


class TestSubmitOrderValidation:
    def test_submit_empty_order_raises(self, repo, order_setup):
        """Cannot submit a PO with zero items."""
        po = PurchaseOrder(
            supplier_id=order_setup["supplier_id"],
            created_by=order_setup["user_id"],
        )
        po.id = repo.create_purchase_order(po)

        with pytest.raises(ValueError, match="no items"):
            repo.submit_purchase_order(po.id)

    def test_submit_order_with_items_succeeds(self, repo, order_setup):
        """Can submit a PO that has items."""
        po = PurchaseOrder(
            supplier_id=order_setup["supplier_id"],
            created_by=order_setup["user_id"],
        )
        po.id = repo.create_purchase_order(po)
        item = PurchaseOrderItem(
            order_id=po.id,
            part_id=order_setup["part_id"],
            quantity_ordered=5,
            unit_cost=10.0,
        )
        repo.add_order_item(item)

        repo.submit_purchase_order(po.id)
        updated = repo.get_purchase_order_by_id(po.id)
        assert updated.status == "submitted"


class TestAddOrderItemValidation:
    def test_zero_quantity_raises(self, repo, order_setup):
        po = PurchaseOrder(
            supplier_id=order_setup["supplier_id"],
            created_by=order_setup["user_id"],
        )
        po.id = repo.create_purchase_order(po)

        item = PurchaseOrderItem(
            order_id=po.id,
            part_id=order_setup["part_id"],
            quantity_ordered=0,
            unit_cost=5.0,
        )
        with pytest.raises(ValueError, match="positive"):
            repo.add_order_item(item)

    def test_negative_quantity_raises(self, repo, order_setup):
        po = PurchaseOrder(
            supplier_id=order_setup["supplier_id"],
            created_by=order_setup["user_id"],
        )
        po.id = repo.create_purchase_order(po)

        item = PurchaseOrderItem(
            order_id=po.id,
            part_id=order_setup["part_id"],
            quantity_ordered=-3,
            unit_cost=5.0,
        )
        with pytest.raises(ValueError, match="positive"):
            repo.add_order_item(item)

    def test_negative_unit_cost_raises(self, repo, order_setup):
        po = PurchaseOrder(
            supplier_id=order_setup["supplier_id"],
            created_by=order_setup["user_id"],
        )
        po.id = repo.create_purchase_order(po)

        item = PurchaseOrderItem(
            order_id=po.id,
            part_id=order_setup["part_id"],
            quantity_ordered=5,
            unit_cost=-10.0,
        )
        with pytest.raises(ValueError, match="negative"):
            repo.add_order_item(item)

    def test_valid_item_succeeds(self, repo, order_setup):
        po = PurchaseOrder(
            supplier_id=order_setup["supplier_id"],
            created_by=order_setup["user_id"],
        )
        po.id = repo.create_purchase_order(po)

        item = PurchaseOrderItem(
            order_id=po.id,
            part_id=order_setup["part_id"],
            quantity_ordered=10,
            unit_cost=5.0,
        )
        item_id = repo.add_order_item(item)
        assert item_id > 0


class TestReceiveOrderValidation:
    def _create_submitted_order(self, repo, setup, qty=10):
        """Helper to create a submitted order with one item."""
        po = PurchaseOrder(
            supplier_id=setup["supplier_id"],
            created_by=setup["user_id"],
        )
        po.id = repo.create_purchase_order(po)
        item = PurchaseOrderItem(
            order_id=po.id,
            part_id=setup["part_id"],
            quantity_ordered=qty,
            unit_cost=10.0,
        )
        item.id = repo.add_order_item(item)
        repo.submit_purchase_order(po.id)
        return po.id, item.id

    def test_receive_on_closed_order_raises(self, repo, order_setup):
        """Cannot receive items on a closed order."""
        po_id, item_id = self._create_submitted_order(repo, order_setup)

        # Receive all items to close the order
        repo.receive_order_items(po_id, [{
            "order_item_id": item_id,
            "quantity_received": 10,
            "allocate_to": "warehouse",
        }], order_setup["user_id"])

        # Now the order should be closed (auto-close)
        order = repo.get_purchase_order_by_id(po_id)
        assert order.status in ("closed", "received")

        # Try to receive more — should fail
        with pytest.raises(ValueError, match="cannot receive"):
            repo.receive_order_items(po_id, [{
                "order_item_id": item_id,
                "quantity_received": 1,
                "allocate_to": "warehouse",
            }], order_setup["user_id"])

    def test_over_receiving_raises(self, repo, order_setup):
        """Cannot receive more than ordered quantity."""
        po_id, item_id = self._create_submitted_order(
            repo, order_setup, qty=5
        )

        with pytest.raises(ValueError, match="remaining"):
            repo.receive_order_items(po_id, [{
                "order_item_id": item_id,
                "quantity_received": 10,
                "allocate_to": "warehouse",
            }], order_setup["user_id"])

    def test_partial_receive_then_over_receive_raises(
        self, repo, order_setup
    ):
        """After partial receive, cannot exceed remaining quantity."""
        po_id, item_id = self._create_submitted_order(
            repo, order_setup, qty=10
        )

        # Receive 7 of 10
        repo.receive_order_items(po_id, [{
            "order_item_id": item_id,
            "quantity_received": 7,
            "allocate_to": "warehouse",
        }], order_setup["user_id"])

        # Try to receive 5 more (only 3 remaining)
        with pytest.raises(ValueError, match="remaining"):
            repo.receive_order_items(po_id, [{
                "order_item_id": item_id,
                "quantity_received": 5,
                "allocate_to": "warehouse",
            }], order_setup["user_id"])

    def test_exact_remaining_receive_succeeds(self, repo, order_setup):
        """Can receive exactly the remaining quantity."""
        po_id, item_id = self._create_submitted_order(
            repo, order_setup, qty=10
        )

        # Receive 7
        repo.receive_order_items(po_id, [{
            "order_item_id": item_id,
            "quantity_received": 7,
            "allocate_to": "warehouse",
        }], order_setup["user_id"])

        # Receive exactly 3 more (completes the order)
        repo.receive_order_items(po_id, [{
            "order_item_id": item_id,
            "quantity_received": 3,
            "allocate_to": "warehouse",
        }], order_setup["user_id"])

    def test_receive_nonexistent_order_raises(self, repo, order_setup):
        """Cannot receive items for a nonexistent order."""
        with pytest.raises(ValueError, match="not found"):
            repo.receive_order_items(99999, [{
                "order_item_id": 1,
                "quantity_received": 1,
                "allocate_to": "warehouse",
            }], order_setup["user_id"])

    def test_receive_on_draft_order_raises(self, repo, order_setup):
        """Cannot receive items on a draft (unsubmitted) order."""
        po = PurchaseOrder(
            supplier_id=order_setup["supplier_id"],
            created_by=order_setup["user_id"],
        )
        po.id = repo.create_purchase_order(po)
        item = PurchaseOrderItem(
            order_id=po.id,
            part_id=order_setup["part_id"],
            quantity_ordered=5,
            unit_cost=10.0,
        )
        item.id = repo.add_order_item(item)

        with pytest.raises(ValueError, match="cannot receive"):
            repo.receive_order_items(po.id, [{
                "order_item_id": item.id,
                "quantity_received": 5,
                "allocate_to": "warehouse",
            }], order_setup["user_id"])
