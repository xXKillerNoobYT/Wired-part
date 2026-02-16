"""Hardening tests for supply chain edge cases (Phase 6).

Tests RA stock validation, supplier NULL propagation, supplier chain
event labeling, and consume-from-truck supplier inheritance.
"""

import pytest

from wired_part.database.models import (
    Part,
    PurchaseOrder,
    PurchaseOrderItem,
    ReturnAuthorization,
    ReturnAuthorizationItem,
    Supplier,
    TruckTransfer,
)


class TestReturnAuthorizationValidation:
    """Return authorization stock and quantity validation."""

    def test_ra_insufficient_warehouse_stock_raises(
        self, repo, supplier, parts, admin_user
    ):
        """Cannot return more than warehouse has in stock."""
        part = parts[0]  # quantity=100
        ra = ReturnAuthorization(
            ra_number=repo.generate_ra_number(),
            supplier_id=supplier.id,
            status="initiated",
            created_by=admin_user.id,
        )
        item = ReturnAuthorizationItem(
            part_id=part.id,
            quantity=999,  # Way more than the 100 in stock
            unit_cost=part.unit_cost,
            reason="Overstock",
        )
        with pytest.raises(ValueError, match="Insufficient warehouse stock"):
            repo.create_return_authorization(ra, [item])

    def test_ra_zero_quantity_raises(
        self, repo, supplier, parts, admin_user
    ):
        """Return item quantity must be positive."""
        part = parts[0]
        ra = ReturnAuthorization(
            ra_number=repo.generate_ra_number(),
            supplier_id=supplier.id,
            status="initiated",
            created_by=admin_user.id,
        )
        item = ReturnAuthorizationItem(
            part_id=part.id,
            quantity=0,
            unit_cost=part.unit_cost,
            reason="Error",
        )
        with pytest.raises(ValueError, match="positive"):
            repo.create_return_authorization(ra, [item])

    def test_ra_negative_quantity_raises(
        self, repo, supplier, parts, admin_user
    ):
        """Return item quantity cannot be negative."""
        part = parts[0]
        ra = ReturnAuthorization(
            ra_number=repo.generate_ra_number(),
            supplier_id=supplier.id,
            status="initiated",
            created_by=admin_user.id,
        )
        item = ReturnAuthorizationItem(
            part_id=part.id,
            quantity=-5,
            unit_cost=part.unit_cost,
            reason="Negative",
        )
        with pytest.raises(ValueError, match="positive"):
            repo.create_return_authorization(ra, [item])

    def test_ra_nonexistent_part_raises(
        self, repo, supplier, admin_user
    ):
        """Return for a nonexistent part should fail."""
        ra = ReturnAuthorization(
            ra_number=repo.generate_ra_number(),
            supplier_id=supplier.id,
            status="initiated",
            created_by=admin_user.id,
        )
        item = ReturnAuthorizationItem(
            part_id=99999,
            quantity=1,
            unit_cost=10.0,
            reason="Ghost part",
        )
        with pytest.raises(ValueError, match="not found"):
            repo.create_return_authorization(ra, [item])

    def test_ra_valid_deduction_succeeds(
        self, repo, supplier, parts, admin_user
    ):
        """Valid RA deducts correct quantity from warehouse."""
        part = parts[0]  # quantity=100
        ra = ReturnAuthorization(
            ra_number=repo.generate_ra_number(),
            supplier_id=supplier.id,
            status="initiated",
            created_by=admin_user.id,
        )
        item = ReturnAuthorizationItem(
            part_id=part.id,
            quantity=10,
            unit_cost=part.unit_cost,
            reason="Overstock",
        )
        ra_id = repo.create_return_authorization(ra, [item])
        assert ra_id > 0

        # Verify warehouse stock reduced
        updated_part = repo.get_part_by_id(part.id)
        assert updated_part.quantity == 90  # 100 - 10

    def test_ra_exact_stock_deduction_succeeds(
        self, repo, supplier, parts, admin_user
    ):
        """Can return exactly what's in stock (brings warehouse to 0)."""
        part = parts[0]  # quantity=100
        ra = ReturnAuthorization(
            ra_number=repo.generate_ra_number(),
            supplier_id=supplier.id,
            status="initiated",
            created_by=admin_user.id,
        )
        item = ReturnAuthorizationItem(
            part_id=part.id,
            quantity=100,
            unit_cost=part.unit_cost,
            reason="Full return",
        )
        repo.create_return_authorization(ra, [item])
        updated_part = repo.get_part_by_id(part.id)
        assert updated_part.quantity == 0


class TestSupplierNullPropagation:
    """Verify supplier_id NULL edge cases in consumption."""

    def test_consume_inherits_existing_supplier_when_unknown(
        self, repo, supplier, parts, admin_user, truck_a, active_job
    ):
        """If job already has supplier X for a part but consume can't
        determine supplier, it should inherit the existing supplier_id."""
        part = parts[2]  # BRKR-20A

        # First: receive from known supplier directly to job
        po = PurchaseOrder(
            order_number="PO-NULL-001",
            supplier_id=supplier.id, status="submitted",
            created_by=admin_user.id,
        )
        po.id = repo.create_purchase_order(po)
        item_id = repo.add_order_item(PurchaseOrderItem(
            order_id=po.id, part_id=part.id,
            quantity_ordered=5, unit_cost=part.unit_cost,
        ))
        repo.receive_order_items(po.id, [{
            "order_item_id": item_id,
            "quantity_received": 5,
            "allocate_to": "job",
            "allocate_job_id": active_job.id,
        }], received_by=admin_user.id)

        # Put parts on truck WITHOUT supplier tracking
        # (direct insert to simulate legacy or manual add)
        repo.db.execute("""
            INSERT INTO truck_inventory (truck_id, part_id, quantity)
            VALUES (?, ?, ?)
            ON CONFLICT(truck_id, part_id) DO UPDATE SET
                quantity = quantity + excluded.quantity
        """, (truck_a.id, part.id, 10))

        # Consume from truck — supplier unknown from transfer,
        # but should inherit from existing job_parts
        repo.consume_from_truck(
            job_id=active_job.id,
            truck_id=truck_a.id,
            part_id=part.id,
            quantity=3,
            user_id=admin_user.id,
        )

        # Verify the job_parts still has the original supplier
        job_parts = repo.get_job_parts(active_job.id)
        jp = [j for j in job_parts if j.part_id == part.id]
        assert len(jp) == 1
        assert jp[0].supplier_id == supplier.id
        assert jp[0].quantity_used == 8  # 5 from PO + 3 from truck


class TestPartSupplierChainLabeling:
    """Verify get_part_supplier_chain labels events correctly."""

    def test_chain_distinguishes_outbound_and_return(
        self, repo, supplier, parts, admin_user, truck_a
    ):
        """Supply chain history should label return transfers as 'returned'
        and outbound transfers as 'transferred'."""
        part = parts[0]

        # Receive to warehouse
        po = PurchaseOrder(
            order_number="PO-CHAIN-LABEL",
            supplier_id=supplier.id, status="submitted",
            created_by=admin_user.id,
        )
        po.id = repo.create_purchase_order(po)
        item_id = repo.add_order_item(PurchaseOrderItem(
            order_id=po.id, part_id=part.id,
            quantity_ordered=20, unit_cost=part.unit_cost,
        ))
        repo.receive_order_items(po.id, [{
            "order_item_id": item_id,
            "quantity_received": 20,
            "allocate_to": "warehouse",
        }], received_by=admin_user.id)

        # Transfer to truck
        transfer = TruckTransfer(
            truck_id=truck_a.id,
            part_id=part.id,
            quantity=10,
            created_by=admin_user.id,
        )
        repo.create_transfer(transfer)
        transfers = repo.get_truck_transfers(truck_a.id, status="pending")
        repo.receive_transfer(
            [t for t in transfers if t.part_id == part.id][0].id,
            admin_user.id,
        )

        # Return from truck to warehouse
        repo.return_to_warehouse(
            truck_a.id, part.id, 3, admin_user.id,
        )

        # Check chain events
        chain = repo.get_part_supplier_chain(part.id)
        events = [e["event"] for e in chain]
        assert "received" in events
        assert "transferred" in events
        assert "returned" in events

    def test_chain_empty_for_unknown_part(self, repo):
        """Supply chain for a nonexistent part returns empty list."""
        chain = repo.get_part_supplier_chain(99999)
        assert chain == []


class TestSuggestedReturnSupplierEdgeCases:
    """Edge cases for get_suggested_return_supplier."""

    def test_no_history_returns_none(self, repo, parts):
        """Part with no receive history should return None."""
        part = parts[0]
        result = repo.get_suggested_return_supplier(part.id)
        assert result is None

    def test_job_context_beats_global(
        self, repo, parts, admin_user, active_job
    ):
        """When job has a specific supplier, that takes priority over
        the most recent global receive."""
        part = parts[1]
        # Supplier A: receives to job
        sup_a = Supplier(name="Supplier A")
        sup_a.id = repo.create_supplier(sup_a)
        po_a = PurchaseOrder(
            order_number="PO-SUGGEST-A",
            supplier_id=sup_a.id, status="submitted",
            created_by=admin_user.id,
        )
        po_a.id = repo.create_purchase_order(po_a)
        item_a = repo.add_order_item(PurchaseOrderItem(
            order_id=po_a.id, part_id=part.id,
            quantity_ordered=5, unit_cost=part.unit_cost,
        ))
        repo.receive_order_items(po_a.id, [{
            "order_item_id": item_a,
            "quantity_received": 5,
            "allocate_to": "job",
            "allocate_job_id": active_job.id,
        }], received_by=admin_user.id)

        # Supplier B: receives to warehouse AFTER (most recent globally)
        sup_b = Supplier(name="Supplier B")
        sup_b.id = repo.create_supplier(sup_b)
        po_b = PurchaseOrder(
            order_number="PO-SUGGEST-B",
            supplier_id=sup_b.id, status="submitted",
            created_by=admin_user.id,
        )
        po_b.id = repo.create_purchase_order(po_b)
        item_b = repo.add_order_item(PurchaseOrderItem(
            order_id=po_b.id, part_id=part.id,
            quantity_ordered=5, unit_cost=part.unit_cost,
        ))
        repo.receive_order_items(po_b.id, [{
            "order_item_id": item_b,
            "quantity_received": 5,
            "allocate_to": "warehouse",
        }], received_by=admin_user.id)

        # With job context → should return Supplier A (job-specific)
        suggested = repo.get_suggested_return_supplier(
            part.id, active_job.id
        )
        assert suggested == sup_a.id

        # Without job context → should return Supplier B (most recent)
        suggested_global = repo.get_suggested_return_supplier(part.id)
        assert suggested_global == sup_b.id
