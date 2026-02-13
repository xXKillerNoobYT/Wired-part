"""E2E tests: complete workflows from start to finish.

These tests exercise full business flows across multiple repository methods,
verifying that stock quantities, statuses, and audit trails stay correct
throughout multi-step operations.
"""

import pytest

from wired_part.database.models import (
    JobPart, Notification, Part, PurchaseOrder, PurchaseOrderItem,
    TruckTransfer,
)
from wired_part.utils.constants import PERMISSION_KEYS


class TestWarehouseToTruckFlow:
    """Warehouse → Truck transfer, then consumption on a job."""

    def test_transfer_deducts_warehouse_adds_truck(
        self, repo, admin_user, parts, truck_a,
    ):
        """Create transfer → receive → verify both stock levels."""
        wire = parts[0]  # WIRE-12-2, qty=100
        original_qty = wire.quantity

        # Create outbound transfer (pending)
        xfer_id = repo.create_transfer(TruckTransfer(
            truck_id=truck_a.id,
            part_id=wire.id,
            quantity=25,
            created_by=admin_user.id,
        ))

        # Warehouse immediately deducted
        wire_now = repo.get_part_by_id(wire.id)
        assert wire_now.quantity == original_qty - 25

        # Truck doesn't have it yet (still pending)
        truck_inv = repo.get_truck_inventory(truck_a.id)
        truck_qty = {ti.part_id: ti.quantity for ti in truck_inv}
        assert truck_qty.get(wire.id, 0) == 0

        # Receive the transfer
        repo.receive_transfer(xfer_id, received_by=admin_user.id)

        # Truck now has the parts
        truck_inv = repo.get_truck_inventory(truck_a.id)
        truck_qty = {ti.part_id: ti.quantity for ti in truck_inv}
        assert truck_qty[wire.id] == 25

        # Warehouse still at the deducted amount
        wire_now = repo.get_part_by_id(wire.id)
        assert wire_now.quantity == original_qty - 25

    def test_cancel_transfer_restores_warehouse(
        self, repo, admin_user, parts, truck_a,
    ):
        """Cancelling a pending transfer restores warehouse stock."""
        breaker = parts[2]  # BRKR-20A, qty=50
        original_qty = breaker.quantity

        xfer_id = repo.create_transfer(TruckTransfer(
            truck_id=truck_a.id,
            part_id=breaker.id,
            quantity=10,
            created_by=admin_user.id,
        ))

        # Warehouse deducted
        assert repo.get_part_by_id(breaker.id).quantity == original_qty - 10

        # Cancel
        repo.cancel_transfer(xfer_id)

        # Warehouse restored
        assert repo.get_part_by_id(breaker.id).quantity == original_qty

    def test_multiple_transfers_to_same_truck(
        self, repo, admin_user, parts, truck_a,
    ):
        """Multiple transfers to the same truck accumulate correctly."""
        outlet = parts[3]  # OUTLET-DR, qty=200

        # Two transfers of different quantities
        xfer1 = repo.create_transfer(TruckTransfer(
            truck_id=truck_a.id, part_id=outlet.id,
            quantity=30, created_by=admin_user.id,
        ))
        xfer2 = repo.create_transfer(TruckTransfer(
            truck_id=truck_a.id, part_id=outlet.id,
            quantity=20, created_by=admin_user.id,
        ))

        repo.receive_transfer(xfer1, received_by=admin_user.id)
        repo.receive_transfer(xfer2, received_by=admin_user.id)

        # Truck should have 30+20 = 50
        truck_inv = repo.get_truck_inventory(truck_a.id)
        truck_qty = {ti.part_id: ti.quantity for ti in truck_inv}
        assert truck_qty[outlet.id] == 50

        # Warehouse should have 200-30-20 = 150
        assert repo.get_part_by_id(outlet.id).quantity == 150

    def test_insufficient_warehouse_stock_raises(
        self, repo, admin_user, parts, truck_a,
    ):
        """Cannot transfer more than warehouse stock."""
        box = parts[4]  # BOX-NW-1G, qty=150

        with pytest.raises(ValueError, match="Insufficient"):
            repo.create_transfer(TruckTransfer(
                truck_id=truck_a.id, part_id=box.id,
                quantity=999, created_by=admin_user.id,
            ))


class TestTruckToJobConsumption:
    """Truck → Job consumption flow."""

    def test_consume_deducts_truck_adds_job(
        self, repo, admin_user, parts, truck_a, active_job,
    ):
        """Consume from truck: deducts truck, records on job."""
        wire = parts[0]

        # Stock the truck first
        xfer_id = repo.create_transfer(TruckTransfer(
            truck_id=truck_a.id, part_id=wire.id,
            quantity=20, created_by=admin_user.id,
        ))
        repo.receive_transfer(xfer_id, received_by=admin_user.id)

        # Consume 5 on the job
        repo.consume_from_truck(
            job_id=active_job.id, truck_id=truck_a.id,
            part_id=wire.id, quantity=5, user_id=admin_user.id,
        )

        # Truck now has 15
        truck_inv = repo.get_truck_inventory(truck_a.id)
        truck_qty = {ti.part_id: ti.quantity for ti in truck_inv}
        assert truck_qty[wire.id] == 15

        # Job has the 5 recorded
        job_parts = repo.get_job_parts(active_job.id)
        assert len(job_parts) == 1
        assert job_parts[0].quantity_used == 5
        assert job_parts[0].consumed_from_truck_id == truck_a.id

        # Consumption log has the entry
        log = repo.get_consumption_log(job_id=active_job.id)
        assert len(log) == 1
        assert log[0].quantity == 5
        assert log[0].truck_id == truck_a.id

    def test_multiple_consumptions_accumulate(
        self, repo, admin_user, parts, truck_a, active_job,
    ):
        """Multiple consumptions of the same part on the same job accumulate."""
        outlet = parts[3]

        # Stock truck with 50
        xfer_id = repo.create_transfer(TruckTransfer(
            truck_id=truck_a.id, part_id=outlet.id,
            quantity=50, created_by=admin_user.id,
        ))
        repo.receive_transfer(xfer_id, received_by=admin_user.id)

        # Consume twice
        repo.consume_from_truck(
            active_job.id, truck_a.id, outlet.id, 10, admin_user.id,
        )
        repo.consume_from_truck(
            active_job.id, truck_a.id, outlet.id, 8, admin_user.id,
        )

        # Truck: 50 - 10 - 8 = 32
        truck_inv = repo.get_truck_inventory(truck_a.id)
        truck_qty = {ti.part_id: ti.quantity for ti in truck_inv}
        assert truck_qty[outlet.id] == 32

        # Job: 10 + 8 = 18 (should accumulate via ON CONFLICT)
        job_parts = repo.get_job_parts(active_job.id)
        jp = [p for p in job_parts if p.part_id == outlet.id]
        assert len(jp) == 1
        assert jp[0].quantity_used == 18

        # Two log entries
        log = repo.get_consumption_log(job_id=active_job.id)
        assert len(log) == 2

    def test_consume_more_than_truck_stock_raises(
        self, repo, admin_user, parts, truck_a, active_job,
    ):
        """Cannot consume more than on-hand truck stock."""
        wire = parts[0]

        # Stock truck with 5
        xfer_id = repo.create_transfer(TruckTransfer(
            truck_id=truck_a.id, part_id=wire.id,
            quantity=5, created_by=admin_user.id,
        ))
        repo.receive_transfer(xfer_id, received_by=admin_user.id)

        with pytest.raises(ValueError, match="Insufficient"):
            repo.consume_from_truck(
                active_job.id, truck_a.id, wire.id, 10, admin_user.id,
            )


class TestPurchaseOrderWorkflow:
    """Full PO lifecycle: draft → submit → receive → close."""

    def test_full_po_lifecycle(
        self, repo, admin_user, supplier, parts,
    ):
        """Create PO → add items → submit → receive → auto-close."""
        wire = parts[0]
        breaker = parts[2]
        original_wire_qty = wire.quantity
        original_breaker_qty = breaker.quantity

        # 1. Create draft PO
        po = PurchaseOrder(
            order_number=repo.generate_order_number(),
            supplier_id=supplier.id,
            status="draft",
            created_by=admin_user.id,
        )
        po_id = repo.create_purchase_order(po)
        assert po_id > 0

        # 2. Add line items
        repo.add_order_item(PurchaseOrderItem(
            order_id=po_id, part_id=wire.id,
            quantity_ordered=50, unit_cost=wire.unit_cost,
        ))
        repo.add_order_item(PurchaseOrderItem(
            order_id=po_id, part_id=breaker.id,
            quantity_ordered=20, unit_cost=breaker.unit_cost,
        ))

        items = repo.get_order_items(po_id)
        assert len(items) == 2

        # 3. Submit
        repo.submit_purchase_order(po_id)
        po_now = repo.get_purchase_order_by_id(po_id)
        assert po_now.status == "submitted"
        assert po_now.submitted_at is not None

        # 4. Receive all items (allocate to warehouse)
        receipts = []
        for item in items:
            receipts.append({
                "order_item_id": item.id,
                "quantity_received": item.quantity_ordered,
                "allocate_to": "warehouse",
            })
        repo.receive_order_items(po_id, receipts, admin_user.id)

        # 5. Check status — should be closed (AUTO_CLOSE default)
        po_final = repo.get_purchase_order_by_id(po_id)
        assert po_final.status in ("received", "closed")

        # 6. Warehouse stock increased
        wire_after = repo.get_part_by_id(wire.id)
        breaker_after = repo.get_part_by_id(breaker.id)
        assert wire_after.quantity == original_wire_qty + 50
        assert breaker_after.quantity == original_breaker_qty + 20

    def test_partial_receive(self, repo, admin_user, supplier, parts):
        """Receiving partial quantities sets status to 'partial'."""
        outlet = parts[3]

        po_id = repo.create_purchase_order(PurchaseOrder(
            order_number=repo.generate_order_number(),
            supplier_id=supplier.id,
            status="draft",
            created_by=admin_user.id,
        ))
        repo.add_order_item(PurchaseOrderItem(
            order_id=po_id, part_id=outlet.id,
            quantity_ordered=100, unit_cost=outlet.unit_cost,
        ))
        repo.submit_purchase_order(po_id)

        items = repo.get_order_items(po_id)
        # Receive only 40 of 100
        repo.receive_order_items(po_id, [{
            "order_item_id": items[0].id,
            "quantity_received": 40,
            "allocate_to": "warehouse",
        }], admin_user.id)

        po_now = repo.get_purchase_order_by_id(po_id)
        assert po_now.status == "partial"

        # Receive remaining 60
        items = repo.get_order_items(po_id)
        repo.receive_order_items(po_id, [{
            "order_item_id": items[0].id,
            "quantity_received": 60,
            "allocate_to": "warehouse",
        }], admin_user.id)

        po_final = repo.get_purchase_order_by_id(po_id)
        assert po_final.status in ("received", "closed")


class TestCompleteEndToEnd:
    """Full end-to-end: user → parts → job → truck → PO → receive → consume → audit."""

    def test_complete_electrician_workflow(
        self, repo, admin_user, foreman_user, supplier, parts,
        truck_a, truck_b, active_job,
    ):
        """Simulate a complete day for an electrician crew."""
        wire = parts[0]   # qty=100
        breaker = parts[2]  # qty=50
        outlet = parts[3]  # qty=200

        # ── 1. Stock both trucks from warehouse ──────────────────
        # Admin's truck gets wire and breakers
        xfer1 = repo.create_transfer(TruckTransfer(
            truck_id=truck_a.id, part_id=wire.id,
            quantity=20, created_by=admin_user.id,
        ))
        xfer2 = repo.create_transfer(TruckTransfer(
            truck_id=truck_a.id, part_id=breaker.id,
            quantity=10, created_by=admin_user.id,
        ))
        repo.receive_transfer(xfer1, received_by=admin_user.id)
        repo.receive_transfer(xfer2, received_by=admin_user.id)

        # Foreman's truck gets outlets
        xfer3 = repo.create_transfer(TruckTransfer(
            truck_id=truck_b.id, part_id=outlet.id,
            quantity=40, created_by=admin_user.id,
        ))
        repo.receive_transfer(xfer3, received_by=foreman_user.id)

        # Verify warehouse after transfers
        assert repo.get_part_by_id(wire.id).quantity == 80  # 100-20
        assert repo.get_part_by_id(breaker.id).quantity == 40  # 50-10
        assert repo.get_part_by_id(outlet.id).quantity == 160  # 200-40

        # ── 2. Consume parts on the job ──────────────────────────
        # Admin uses wire from his truck
        repo.consume_from_truck(
            active_job.id, truck_a.id, wire.id, 12, admin_user.id,
            notes="Ran wire to panel",
        )
        # Foreman uses outlets from his truck
        repo.consume_from_truck(
            active_job.id, truck_b.id, outlet.id, 15, foreman_user.id,
            notes="Installed outlets in kitchen",
        )
        # Admin uses breakers from his truck
        repo.consume_from_truck(
            active_job.id, truck_a.id, breaker.id, 3, admin_user.id,
            notes="Installed breakers in panel",
        )

        # Verify truck levels after consumption
        inv_a = {ti.part_id: ti.quantity
                 for ti in repo.get_truck_inventory(truck_a.id)}
        assert inv_a[wire.id] == 8     # 20-12
        assert inv_a[breaker.id] == 7  # 10-3

        inv_b = {ti.part_id: ti.quantity
                 for ti in repo.get_truck_inventory(truck_b.id)}
        assert inv_b[outlet.id] == 25  # 40-15

        # ── 3. Verify job records ────────────────────────────────
        job_parts = repo.get_job_parts(active_job.id)
        assert len(job_parts) == 3
        consumption = repo.get_consumption_log(job_id=active_job.id)
        assert len(consumption) == 3

        # ── 4. Create PO to restock warehouse ────────────────────
        po_id = repo.create_purchase_order(PurchaseOrder(
            order_number=repo.generate_order_number(),
            supplier_id=supplier.id,
            status="draft",
            created_by=admin_user.id,
        ))
        repo.add_order_item(PurchaseOrderItem(
            order_id=po_id, part_id=wire.id,
            quantity_ordered=100, unit_cost=wire.unit_cost,
        ))
        repo.add_order_item(PurchaseOrderItem(
            order_id=po_id, part_id=outlet.id,
            quantity_ordered=200, unit_cost=outlet.unit_cost,
        ))
        repo.submit_purchase_order(po_id)

        items = repo.get_order_items(po_id)
        receipts = [{
            "order_item_id": item.id,
            "quantity_received": item.quantity_ordered,
            "allocate_to": "warehouse",
        } for item in items]
        repo.receive_order_items(po_id, receipts, admin_user.id)

        # ── 5. Verify final warehouse levels ─────────────────────
        assert repo.get_part_by_id(wire.id).quantity == 180  # 80+100
        assert repo.get_part_by_id(outlet.id).quantity == 360  # 160+200
        assert repo.get_part_by_id(breaker.id).quantity == 40  # unchanged

        # ── 6. Run an audit on truck_a ───────────────────────────
        # Confirm the wire count is correct
        repo.record_audit_result(
            audit_type="truck", target_id=truck_a.id,
            part_id=wire.id,
            expected_quantity=8, actual_quantity=8,
            status="confirmed", audited_by=admin_user.id,
        )
        summary = repo.get_audit_summary(
            audit_type="truck", target_id=truck_a.id,
        )
        assert summary["confirmed_count"] >= 1


class TestPermissionsWorkflow:
    """Test that permissions actually control access."""

    def test_admin_has_all_permissions(self, repo, admin_user):
        perms = repo.get_user_permissions(admin_user.id)
        assert perms == set(PERMISSION_KEYS)

    def test_foreman_can_transfer_but_not_settings(
        self, repo, foreman_user,
    ):
        perms = repo.get_user_permissions(foreman_user.id)
        assert "trucks_transfer" in perms
        assert "tab_settings" not in perms
        assert "settings_users" not in perms

    def test_worker_minimal_access(self, repo, worker_user):
        perms = repo.get_user_permissions(worker_user.id)
        assert "tab_dashboard" in perms
        assert "labor_clock_in" in perms
        assert "parts_delete" not in perms
        assert "orders_create" not in perms

    def test_multi_hat_union(self, repo, worker_user):
        """Assigning an extra hat expands permissions."""
        perms_before = repo.get_user_permissions(worker_user.id)
        assert "trucks_transfer" not in perms_before

        foreman_hat = repo.get_hat_by_name("Foreman")
        repo.assign_hat(worker_user.id, foreman_hat.id)

        perms_after = repo.get_user_permissions(worker_user.id)
        assert "trucks_transfer" in perms_after
        assert perms_after > perms_before  # Strictly more permissions


class TestReturnToWarehouse:
    """Truck → Warehouse return flow."""

    def test_return_restores_warehouse(
        self, repo, admin_user, parts, truck_a,
    ):
        """Parts returned from truck go back to warehouse."""
        box = parts[4]  # qty=150

        # Transfer 30 to truck
        xfer_id = repo.create_transfer(TruckTransfer(
            truck_id=truck_a.id, part_id=box.id,
            quantity=30, created_by=admin_user.id,
        ))
        repo.receive_transfer(xfer_id, received_by=admin_user.id)

        # Warehouse: 120, Truck: 30
        assert repo.get_part_by_id(box.id).quantity == 120

        # Return 15 from truck
        repo.return_to_warehouse(
            truck_id=truck_a.id, part_id=box.id,
            quantity=15, user_id=admin_user.id,
        )

        # Warehouse: 135, Truck: 15
        assert repo.get_part_by_id(box.id).quantity == 135
        truck_inv = {ti.part_id: ti.quantity
                     for ti in repo.get_truck_inventory(truck_a.id)}
        assert truck_inv[box.id] == 15
