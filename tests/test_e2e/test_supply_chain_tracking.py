"""E2E tests for supply chain supplier tracking (v12).

Tests the complete part lifecycle: order → receive → warehouse → truck →
job → return, verifying supplier_id is preserved at every stage.
"""

import pytest

from wired_part.database.models import (
    PurchaseOrder, PurchaseOrderItem, TruckTransfer,
)


class TestSupplierTrackingThroughChain:
    """Verify supplier_id is preserved from PO through to job consumption."""

    def test_receive_to_warehouse_captures_supplier(
        self, repo, supplier, parts, admin_user
    ):
        """Receiving to warehouse should record supplier_id in receive_log."""
        part = parts[0]  # WIRE-12-2
        # Create and submit PO
        po = PurchaseOrder(
            order_number="PO-TRACK-001",
            supplier_id=supplier.id,
            status="submitted",
            created_by=admin_user.id,
        )
        po.id = repo.create_purchase_order(po)
        item_id = repo.add_order_item(PurchaseOrderItem(
            order_id=po.id, part_id=part.id,
            quantity_ordered=10, unit_cost=part.unit_cost,
        ))

        # Receive to warehouse
        repo.receive_order_items(po.id, [{
            "order_item_id": item_id,
            "quantity_received": 10,
            "allocate_to": "warehouse",
        }], received_by=admin_user.id)

        # Verify receive_log has supplier_id
        logs = repo.get_receive_log(po.id)
        assert len(logs) == 1
        assert logs[0].supplier_id == supplier.id

    def test_receive_to_truck_captures_supplier_on_transfer(
        self, repo, supplier, parts, admin_user, truck_a
    ):
        """Receiving to truck should create transfer WITH supplier_id."""
        part = parts[1]  # WIRE-14-2
        po = PurchaseOrder(
            order_number="PO-TRACK-002",
            supplier_id=supplier.id,
            status="submitted",
            created_by=admin_user.id,
        )
        po.id = repo.create_purchase_order(po)
        item_id = repo.add_order_item(PurchaseOrderItem(
            order_id=po.id, part_id=part.id,
            quantity_ordered=5, unit_cost=part.unit_cost,
        ))

        # Receive to truck
        repo.receive_order_items(po.id, [{
            "order_item_id": item_id,
            "quantity_received": 5,
            "allocate_to": "truck",
            "allocate_truck_id": truck_a.id,
        }], received_by=admin_user.id)

        # Verify the pending transfer has supplier_id
        transfers = repo.get_truck_transfers(truck_a.id, status="pending")
        matching = [t for t in transfers if t.part_id == part.id]
        assert len(matching) == 1
        assert matching[0].supplier_id == supplier.id
        assert matching[0].source_order_id == po.id

    def test_receive_to_job_captures_supplier_on_job_parts(
        self, repo, supplier, parts, admin_user, active_job
    ):
        """Receiving directly to job should set supplier_id on job_parts."""
        part = parts[2]  # BRKR-20A
        po = PurchaseOrder(
            order_number="PO-TRACK-003",
            supplier_id=supplier.id,
            status="submitted",
            created_by=admin_user.id,
        )
        po.id = repo.create_purchase_order(po)
        item_id = repo.add_order_item(PurchaseOrderItem(
            order_id=po.id, part_id=part.id,
            quantity_ordered=3, unit_cost=part.unit_cost,
        ))

        # Receive directly to job
        repo.receive_order_items(po.id, [{
            "order_item_id": item_id,
            "quantity_received": 3,
            "allocate_to": "job",
            "allocate_job_id": active_job.id,
        }], received_by=admin_user.id)

        # Verify job_parts has supplier_id
        job_parts = repo.get_job_parts(active_job.id)
        matching = [jp for jp in job_parts if jp.part_id == part.id]
        assert len(matching) == 1
        assert matching[0].supplier_id == supplier.id
        assert matching[0].source_order_id == po.id

    def test_consume_from_truck_propagates_supplier(
        self, repo, supplier, parts, admin_user, truck_a, active_job
    ):
        """Full chain: PO → receive to truck → receive transfer →
        consume from truck → verify supplier on consumption_log."""
        part = parts[3]  # OUTLET-DR
        # Create PO → receive to truck
        po = PurchaseOrder(
            order_number="PO-TRACK-004",
            supplier_id=supplier.id,
            status="submitted",
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
            "allocate_to": "truck",
            "allocate_truck_id": truck_a.id,
        }], received_by=admin_user.id)

        # Receive the pending transfer to put parts on truck
        transfers = repo.get_truck_transfers(truck_a.id, status="pending")
        matching = [t for t in transfers if t.part_id == part.id]
        assert len(matching) == 1
        repo.receive_transfer(matching[0].id, admin_user.id)

        # Now consume from truck to job
        repo.consume_from_truck(
            job_id=active_job.id,
            truck_id=truck_a.id,
            part_id=part.id,
            quantity=5,
            user_id=admin_user.id,
        )

        # Verify supplier tracked in job_parts
        job_parts = repo.get_job_parts(active_job.id)
        jp = [j for j in job_parts if j.part_id == part.id]
        assert len(jp) == 1
        assert jp[0].supplier_id == supplier.id
        assert jp[0].source_order_id == po.id

    def test_suggested_return_supplier_from_job(
        self, repo, supplier, parts, admin_user, truck_a, active_job
    ):
        """Suggested supplier for return should match the original supplier."""
        part = parts[4]  # BOX-NW-1G
        # Full chain: PO → truck → job
        po = PurchaseOrder(
            order_number="PO-TRACK-005",
            supplier_id=supplier.id,
            status="submitted",
            created_by=admin_user.id,
        )
        po.id = repo.create_purchase_order(po)
        item_id = repo.add_order_item(PurchaseOrderItem(
            order_id=po.id, part_id=part.id,
            quantity_ordered=10, unit_cost=part.unit_cost,
        ))
        repo.receive_order_items(po.id, [{
            "order_item_id": item_id,
            "quantity_received": 10,
            "allocate_to": "truck",
            "allocate_truck_id": truck_a.id,
        }], received_by=admin_user.id)
        transfers = repo.get_truck_transfers(truck_a.id, status="pending")
        repo.receive_transfer(
            [t for t in transfers if t.part_id == part.id][0].id,
            admin_user.id,
        )
        repo.consume_from_truck(
            active_job.id, truck_a.id, part.id, 5, admin_user.id,
        )

        # Now check: system should suggest the correct supplier for return
        suggested = repo.get_suggested_return_supplier(
            part.id, active_job.id
        )
        assert suggested == supplier.id

    def test_suggested_return_supplier_no_job_context(
        self, repo, supplier, parts, admin_user
    ):
        """Without job context, falls back to most recent receive."""
        part = parts[0]
        po = PurchaseOrder(
            order_number="PO-TRACK-006",
            supplier_id=supplier.id,
            status="submitted",
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
            "allocate_to": "warehouse",
        }], received_by=admin_user.id)

        suggested = repo.get_suggested_return_supplier(part.id)
        assert suggested == supplier.id

    def test_part_supplier_chain_shows_full_history(
        self, repo, supplier, parts, admin_user, truck_a, active_job
    ):
        """get_part_supplier_chain returns all movements with supplier."""
        part = parts[0]
        po = PurchaseOrder(
            order_number="PO-CHAIN-001",
            supplier_id=supplier.id,
            status="submitted",
            created_by=admin_user.id,
        )
        po.id = repo.create_purchase_order(po)
        item_id = repo.add_order_item(PurchaseOrderItem(
            order_id=po.id, part_id=part.id,
            quantity_ordered=10, unit_cost=part.unit_cost,
        ))
        # Receive to warehouse
        repo.receive_order_items(po.id, [{
            "order_item_id": item_id,
            "quantity_received": 10,
            "allocate_to": "warehouse",
        }], received_by=admin_user.id)

        chain = repo.get_part_supplier_chain(part.id)
        assert len(chain) >= 1
        assert chain[0]["supplier_name"] == "Acme Electric Supply"

    def test_manual_transfer_auto_detects_supplier(
        self, repo, supplier, parts, admin_user, truck_a
    ):
        """create_transfer (manual warehouse→truck) should auto-detect
        the most recent supplier for the part from receive_log."""
        part = parts[0]
        # First: receive from PO so receive_log has supplier
        po = PurchaseOrder(
            order_number="PO-AUTO-001",
            supplier_id=supplier.id,
            status="submitted",
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
            "allocate_to": "warehouse",
        }], received_by=admin_user.id)

        # Now: manual transfer (user moves from warehouse to truck)
        transfer = TruckTransfer(
            truck_id=truck_a.id,
            part_id=part.id,
            quantity=3,
            created_by=admin_user.id,
        )
        tid = repo.create_transfer(transfer)

        # Verify transfer auto-detected the supplier
        transfers = repo.get_truck_transfers(truck_a.id, status="pending")
        t = [x for x in transfers if x.id == tid][0]
        assert t.supplier_id == supplier.id
        assert t.source_order_id == po.id


class TestMultipleSupplierScenario:
    """When a part is sourced from multiple suppliers."""

    def test_most_recent_supplier_wins(
        self, repo, parts, admin_user, truck_a, active_job
    ):
        """If part received from 2 suppliers, suggested return uses
        the most recent one."""
        part = parts[0]

        # Supplier A
        from wired_part.database.models import Supplier
        sup_a = Supplier(name="Supplier Alpha")
        sup_a.id = repo.create_supplier(sup_a)
        po_a = PurchaseOrder(
            order_number="PO-MULTI-A",
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
            "allocate_to": "warehouse",
        }], received_by=admin_user.id)

        # Supplier B (received AFTER A, so B is most recent)
        sup_b = Supplier(name="Supplier Beta")
        sup_b.id = repo.create_supplier(sup_b)
        po_b = PurchaseOrder(
            order_number="PO-MULTI-B",
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

        # Suggested supplier should be the most recent (B)
        suggested = repo.get_suggested_return_supplier(part.id)
        assert suggested == sup_b.id


class TestSupplierPerPartPerJobEnforcement:
    """Enforce that a given part on a given job always comes from
    the same supplier. Different parts can come from different
    suppliers on the same job, but the same part cannot."""

    def test_receive_to_job_rejects_different_supplier(
        self, repo, supplier, parts, admin_user, active_job
    ):
        """Receiving same part from a DIFFERENT supplier to the same
        job should raise ValueError."""
        from wired_part.database.models import Supplier

        part = parts[0]

        # First: receive from original supplier → job (succeeds)
        po1 = PurchaseOrder(
            order_number="PO-ENFORCE-001",
            supplier_id=supplier.id, status="submitted",
            created_by=admin_user.id,
        )
        po1.id = repo.create_purchase_order(po1)
        item1 = repo.add_order_item(PurchaseOrderItem(
            order_id=po1.id, part_id=part.id,
            quantity_ordered=5, unit_cost=part.unit_cost,
        ))
        repo.receive_order_items(po1.id, [{
            "order_item_id": item1,
            "quantity_received": 5,
            "allocate_to": "job",
            "allocate_job_id": active_job.id,
        }], received_by=admin_user.id)

        # Second: try to receive same part from DIFFERENT supplier → job
        other_supplier = Supplier(name="Other Supply Co")
        other_supplier.id = repo.create_supplier(other_supplier)
        po2 = PurchaseOrder(
            order_number="PO-ENFORCE-002",
            supplier_id=other_supplier.id, status="submitted",
            created_by=admin_user.id,
        )
        po2.id = repo.create_purchase_order(po2)
        item2 = repo.add_order_item(PurchaseOrderItem(
            order_id=po2.id, part_id=part.id,
            quantity_ordered=3, unit_cost=part.unit_cost,
        ))

        with pytest.raises(ValueError, match="Supplier conflict"):
            repo.receive_order_items(po2.id, [{
                "order_item_id": item2,
                "quantity_received": 3,
                "allocate_to": "job",
                "allocate_job_id": active_job.id,
            }], received_by=admin_user.id)

    def test_receive_to_job_allows_same_supplier_again(
        self, repo, supplier, parts, admin_user, active_job
    ):
        """Receiving same part from the SAME supplier again is fine."""
        part = parts[0]

        # First receive
        po1 = PurchaseOrder(
            order_number="PO-SAME-001",
            supplier_id=supplier.id, status="submitted",
            created_by=admin_user.id,
        )
        po1.id = repo.create_purchase_order(po1)
        item1 = repo.add_order_item(PurchaseOrderItem(
            order_id=po1.id, part_id=part.id,
            quantity_ordered=5, unit_cost=part.unit_cost,
        ))
        repo.receive_order_items(po1.id, [{
            "order_item_id": item1,
            "quantity_received": 5,
            "allocate_to": "job",
            "allocate_job_id": active_job.id,
        }], received_by=admin_user.id)

        # Second receive — same supplier, should succeed
        po2 = PurchaseOrder(
            order_number="PO-SAME-002",
            supplier_id=supplier.id, status="submitted",
            created_by=admin_user.id,
        )
        po2.id = repo.create_purchase_order(po2)
        item2 = repo.add_order_item(PurchaseOrderItem(
            order_id=po2.id, part_id=part.id,
            quantity_ordered=3, unit_cost=part.unit_cost,
        ))
        repo.receive_order_items(po2.id, [{
            "order_item_id": item2,
            "quantity_received": 3,
            "allocate_to": "job",
            "allocate_job_id": active_job.id,
        }], received_by=admin_user.id)

        # Verify total quantity accumulated
        job_parts = repo.get_job_parts(active_job.id)
        jp = [j for j in job_parts if j.part_id == part.id]
        assert len(jp) == 1
        assert jp[0].quantity_used == 8  # 5 + 3

    def test_different_parts_different_suppliers_same_job_ok(
        self, repo, supplier, parts, admin_user, active_job
    ):
        """Different parts CAN come from different suppliers on same job."""
        from wired_part.database.models import Supplier

        part_a = parts[0]
        part_b = parts[1]

        # Part A from original supplier
        po1 = PurchaseOrder(
            order_number="PO-DIFF-001",
            supplier_id=supplier.id, status="submitted",
            created_by=admin_user.id,
        )
        po1.id = repo.create_purchase_order(po1)
        item1 = repo.add_order_item(PurchaseOrderItem(
            order_id=po1.id, part_id=part_a.id,
            quantity_ordered=5, unit_cost=part_a.unit_cost,
        ))
        repo.receive_order_items(po1.id, [{
            "order_item_id": item1,
            "quantity_received": 5,
            "allocate_to": "job",
            "allocate_job_id": active_job.id,
        }], received_by=admin_user.id)

        # Part B from a DIFFERENT supplier — should be fine
        other_supplier = Supplier(name="Different Supply Co")
        other_supplier.id = repo.create_supplier(other_supplier)
        po2 = PurchaseOrder(
            order_number="PO-DIFF-002",
            supplier_id=other_supplier.id, status="submitted",
            created_by=admin_user.id,
        )
        po2.id = repo.create_purchase_order(po2)
        item2 = repo.add_order_item(PurchaseOrderItem(
            order_id=po2.id, part_id=part_b.id,
            quantity_ordered=3, unit_cost=part_b.unit_cost,
        ))
        # This should NOT raise — different part, different supplier is fine
        repo.receive_order_items(po2.id, [{
            "order_item_id": item2,
            "quantity_received": 3,
            "allocate_to": "job",
            "allocate_job_id": active_job.id,
        }], received_by=admin_user.id)

        job_parts = repo.get_job_parts(active_job.id)
        assert len(job_parts) == 2

    def test_consume_from_truck_rejects_different_supplier(
        self, repo, supplier, parts, admin_user, truck_a, active_job
    ):
        """Consuming from truck when job already has part from a
        different supplier should raise ValueError."""
        from wired_part.database.models import Supplier

        part = parts[3]  # OUTLET-DR

        # First: receive from original supplier directly to job
        po1 = PurchaseOrder(
            order_number="PO-TRUCK-ENF-001",
            supplier_id=supplier.id, status="submitted",
            created_by=admin_user.id,
        )
        po1.id = repo.create_purchase_order(po1)
        item1 = repo.add_order_item(PurchaseOrderItem(
            order_id=po1.id, part_id=part.id,
            quantity_ordered=5, unit_cost=part.unit_cost,
        ))
        repo.receive_order_items(po1.id, [{
            "order_item_id": item1,
            "quantity_received": 5,
            "allocate_to": "job",
            "allocate_job_id": active_job.id,
        }], received_by=admin_user.id)

        # Now: stock the truck from a DIFFERENT supplier
        other_supplier = Supplier(name="Rival Electric")
        other_supplier.id = repo.create_supplier(other_supplier)
        po2 = PurchaseOrder(
            order_number="PO-TRUCK-ENF-002",
            supplier_id=other_supplier.id, status="submitted",
            created_by=admin_user.id,
        )
        po2.id = repo.create_purchase_order(po2)
        item2 = repo.add_order_item(PurchaseOrderItem(
            order_id=po2.id, part_id=part.id,
            quantity_ordered=20, unit_cost=part.unit_cost,
        ))
        repo.receive_order_items(po2.id, [{
            "order_item_id": item2,
            "quantity_received": 20,
            "allocate_to": "truck",
            "allocate_truck_id": truck_a.id,
        }], received_by=admin_user.id)
        transfers = repo.get_truck_transfers(truck_a.id, status="pending")
        matching = [t for t in transfers if t.part_id == part.id]
        repo.receive_transfer(matching[0].id, admin_user.id)

        # Try to consume from truck to the same job — different supplier
        with pytest.raises(ValueError, match="Supplier conflict"):
            repo.consume_from_truck(
                job_id=active_job.id,
                truck_id=truck_a.id,
                part_id=part.id,
                quantity=5,
                user_id=admin_user.id,
            )

    def test_consume_from_truck_allows_same_supplier(
        self, repo, supplier, parts, admin_user, truck_a, active_job
    ):
        """Consuming from truck when supplier matches is allowed."""
        part = parts[4]  # BOX-NW-1G

        # Receive from supplier → truck
        po = PurchaseOrder(
            order_number="PO-TRUCK-OK-001",
            supplier_id=supplier.id, status="submitted",
            created_by=admin_user.id,
        )
        po.id = repo.create_purchase_order(po)
        item = repo.add_order_item(PurchaseOrderItem(
            order_id=po.id, part_id=part.id,
            quantity_ordered=20, unit_cost=part.unit_cost,
        ))
        repo.receive_order_items(po.id, [{
            "order_item_id": item,
            "quantity_received": 20,
            "allocate_to": "truck",
            "allocate_truck_id": truck_a.id,
        }], received_by=admin_user.id)
        transfers = repo.get_truck_transfers(truck_a.id, status="pending")
        matching = [t for t in transfers if t.part_id == part.id]
        repo.receive_transfer(matching[0].id, admin_user.id)

        # Consume twice from same supplier — both should succeed
        repo.consume_from_truck(
            active_job.id, truck_a.id, part.id, 5, admin_user.id,
        )
        repo.consume_from_truck(
            active_job.id, truck_a.id, part.id, 3, admin_user.id,
        )

        job_parts = repo.get_job_parts(active_job.id)
        jp = [j for j in job_parts if j.part_id == part.id]
        assert len(jp) == 1
        assert jp[0].quantity_used == 8
        assert jp[0].supplier_id == supplier.id


class TestJobUpdates:
    """Tests for the job updates/comments system (v12)."""

    def test_create_job_update(self, repo, admin_user, active_job):
        uid = repo.create_job_update(
            active_job.id, admin_user.id, "Starting rough-in today"
        )
        assert uid > 0

    def test_get_job_updates(self, repo, admin_user, active_job):
        repo.create_job_update(
            active_job.id, admin_user.id, "First update"
        )
        repo.create_job_update(
            active_job.id, admin_user.id, "Second update"
        )
        updates = repo.get_job_updates(active_job.id)
        assert len(updates) == 2
        assert updates[0].message == "Second update"  # Most recent first

    def test_pin_job_update(self, repo, admin_user, active_job):
        uid = repo.create_job_update(
            active_job.id, admin_user.id, "Important note"
        )
        repo.create_job_update(
            active_job.id, admin_user.id, "Regular note"
        )
        repo.pin_job_update(uid, pinned=True)

        updates = repo.get_job_updates(active_job.id)
        assert updates[0].message == "Important note"  # Pinned first
        assert updates[0].is_pinned == 1

    def test_delete_job_update(self, repo, admin_user, active_job):
        uid = repo.create_job_update(
            active_job.id, admin_user.id, "To be deleted"
        )
        repo.delete_job_update(uid)
        updates = repo.get_job_updates(active_job.id)
        assert len(updates) == 0

    def test_get_latest_across_jobs(self, repo, admin_user, active_job):
        # Create a second job
        from wired_part.database.models import Job
        job2 = Job(
            job_number="J-2026-099", name="Second Job",
            customer="Customer B", status="active",
        )
        job2.id = repo.create_job(job2)

        repo.create_job_update(active_job.id, admin_user.id, "Job 1 update")
        repo.create_job_update(job2.id, admin_user.id, "Job 2 update")

        latest = repo.get_latest_updates_across_jobs(limit=10)
        assert len(latest) == 2
        # Most recent first
        assert latest[0].message == "Job 2 update"

    def test_update_types(self, repo, admin_user, active_job):
        repo.create_job_update(
            active_job.id, admin_user.id,
            "Status changed to on_hold",
            update_type="status_change",
        )
        updates = repo.get_job_updates(active_job.id)
        assert updates[0].update_type == "status_change"

    def test_update_with_user_name(self, repo, admin_user, active_job):
        repo.create_job_update(
            active_job.id, admin_user.id, "Test"
        )
        updates = repo.get_job_updates(active_job.id)
        assert updates[0].user_name == "Admin Boss"
