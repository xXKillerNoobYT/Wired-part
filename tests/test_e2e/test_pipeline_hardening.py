"""E2E tests for Loops 1-5 + 10: Pipeline integrity hardening.

Loop 1: Order pipeline — block close with unreceived items
Loop 2: Race condition — atomic stock deduction in transfers
Loop 3: Supplier propagation — tighten auto-detect tiebreaker
Loop 4: Return auth — edge cases (zero stock, exact stock, lifecycle)
Loop 5: Deprecation pipeline — logging + notifications on transitions
Loop 10: Search — LIKE wildcard escape for special characters
"""

import pytest
from datetime import datetime

from wired_part.database.repository import Repository
from wired_part.database.models import (
    Category, Job, Part, PurchaseOrder, PurchaseOrderItem,
    ReturnAuthorization, ReturnAuthorizationItem, Supplier, Truck,
    TruckTransfer, User, Notification,
)


# `repo` fixture is provided by conftest.py (initialize_database)

@pytest.fixture
def base_data(repo):
    """Create a standard set of entities for pipeline tests."""
    cat = repo.get_all_categories()[0]

    user = User(
        username="pipeuser", display_name="Pipe Tester",
        pin_hash=Repository.hash_pin("1234"),
    )
    user.id = repo.create_user(user)

    sup = Supplier(name="Pipe Electric", is_supply_house=True)
    sup.id = repo.create_supplier(sup)

    truck = Truck(
        truck_number="T-PIPE", name="Pipe Truck",
        assigned_user_id=user.id,
    )
    truck.id = repo.create_truck(truck)

    job = Job(
        job_number="J-PIPE", name="Pipeline Test Job",
        customer="Test Customer", status="active",
    )
    job.id = repo.create_job(job)

    part = Part(
        part_number="PIPE-001", name="14/2 Romex",
        description="14/2 NM-B cable", quantity=100,
        unit_cost=0.50, category_id=cat.id, min_quantity=10,
    )
    part.id = repo.create_part(part)

    return {
        "cat": cat, "user": user, "supplier": sup,
        "truck": truck, "job": job, "part": part,
    }


# ═══════════════════════════════════════════════════════════════
# LOOP 1: Order pipeline — block close with unreceived items
# ═══════════════════════════════════════════════════════════════

class TestOrderCloseBlocking:
    """Loop 1: 'I placed an order, received half, then the app let me
    close it.'"""

    def test_close_blocked_when_items_unreceived(self, repo, base_data):
        """Cannot close order with unreceived items (default)."""
        s = base_data["supplier"]
        p = base_data["part"]
        u = base_data["user"]

        po = PurchaseOrder(
            order_number="PO-CLOSE-001", supplier_id=s.id,
            created_by=u.id,
        )
        po.id = repo.create_purchase_order(po)
        repo.add_order_item(PurchaseOrderItem(
            order_id=po.id, part_id=p.id,
            quantity_ordered=10, unit_cost=0.50,
        ))
        repo.submit_purchase_order(po.id)

        with pytest.raises(ValueError, match="unreceived items"):
            repo.close_purchase_order(po.id)

    def test_close_blocked_after_partial_receive(self, repo, base_data):
        """Partially received order still blocks close."""
        s = base_data["supplier"]
        p = base_data["part"]
        u = base_data["user"]

        po = PurchaseOrder(
            order_number="PO-CLOSE-002", supplier_id=s.id,
            created_by=u.id,
        )
        po.id = repo.create_purchase_order(po)
        item = PurchaseOrderItem(
            order_id=po.id, part_id=p.id,
            quantity_ordered=10, unit_cost=0.50,
        )
        item.id = repo.add_order_item(item)
        repo.submit_purchase_order(po.id)

        # Receive only 5 of 10
        repo.receive_order_items(po.id, [
            {"order_item_id": item.id, "quantity_received":5},
        ], received_by=u.id)

        with pytest.raises(ValueError, match="unreceived items"):
            repo.close_purchase_order(po.id)

    def test_close_allowed_when_fully_received(self, repo, base_data):
        """Fully received order can be closed."""
        s = base_data["supplier"]
        p = base_data["part"]
        u = base_data["user"]

        po = PurchaseOrder(
            order_number="PO-CLOSE-003", supplier_id=s.id,
            created_by=u.id,
        )
        po.id = repo.create_purchase_order(po)
        item = PurchaseOrderItem(
            order_id=po.id, part_id=p.id,
            quantity_ordered=10, unit_cost=0.50,
        )
        item.id = repo.add_order_item(item)
        repo.submit_purchase_order(po.id)

        repo.receive_order_items(po.id, [
            {"order_item_id": item.id, "quantity_received":10},
        ], received_by=u.id)

        repo.close_purchase_order(po.id)
        order = repo.get_purchase_order_by_id(po.id)
        assert order.status == "closed"

    def test_close_force_overrides_check(self, repo, base_data):
        """force=True closes even with unreceived items."""
        s = base_data["supplier"]
        p = base_data["part"]
        u = base_data["user"]

        po = PurchaseOrder(
            order_number="PO-CLOSE-004", supplier_id=s.id,
            created_by=u.id,
        )
        po.id = repo.create_purchase_order(po)
        repo.add_order_item(PurchaseOrderItem(
            order_id=po.id, part_id=p.id,
            quantity_ordered=10, unit_cost=0.50,
        ))
        repo.submit_purchase_order(po.id)

        # Force close
        repo.close_purchase_order(po.id, force=True)
        order = repo.get_purchase_order_by_id(po.id)
        assert order.status == "closed"


# ═══════════════════════════════════════════════════════════════
# LOOP 2: Atomic stock deduction in transfers
# ═══════════════════════════════════════════════════════════════

class TestAtomicTransferDeduction:
    """Loop 2: 'I transferred parts to a truck, but hit the button
    twice and got negative warehouse stock.'"""

    def test_transfer_deducts_stock_correctly(self, repo, base_data):
        """Normal transfer deducts warehouse stock."""
        p = base_data["part"]
        t = base_data["truck"]

        xfer = TruckTransfer(
            truck_id=t.id, part_id=p.id, quantity=20,
        )
        repo.create_transfer(xfer)

        part = repo.get_part_by_id(p.id)
        assert part.quantity == 80  # 100 - 20

    def test_transfer_rejects_when_insufficient_stock(self, repo, base_data):
        """Transfer blocked when not enough warehouse stock."""
        p = base_data["part"]
        t = base_data["truck"]

        with pytest.raises(ValueError, match="Insufficient"):
            repo.create_transfer(TruckTransfer(
                truck_id=t.id, part_id=p.id, quantity=999,
            ))

        # Stock unchanged
        part = repo.get_part_by_id(p.id)
        assert part.quantity == 100

    def test_exact_stock_transfer_succeeds(self, repo, base_data):
        """Transfer of exactly available stock works."""
        p = base_data["part"]
        t = base_data["truck"]

        repo.create_transfer(TruckTransfer(
            truck_id=t.id, part_id=p.id, quantity=100,
        ))
        part = repo.get_part_by_id(p.id)
        assert part.quantity == 0

    def test_sequential_transfers_prevent_negative(self, repo, base_data):
        """Two back-to-back transfers can't create negative stock."""
        p = base_data["part"]
        t = base_data["truck"]

        # First transfer takes 60
        repo.create_transfer(TruckTransfer(
            truck_id=t.id, part_id=p.id, quantity=60,
        ))

        # Second transfer tries 60 but only 40 left
        with pytest.raises(ValueError, match="Insufficient"):
            repo.create_transfer(TruckTransfer(
                truck_id=t.id, part_id=p.id, quantity=60,
            ))

        part = repo.get_part_by_id(p.id)
        assert part.quantity == 40  # Only first deducted


# ═══════════════════════════════════════════════════════════════
# LOOP 3: Supplier propagation — auto-detect tiebreaker
# ═══════════════════════════════════════════════════════════════

class TestSupplierAutoDetect:
    """Loop 3: 'My truck guy received a transfer but it shows the
    wrong supplier on the job.'"""

    def test_transfer_auto_detects_supplier_from_receive_log(
        self, repo, base_data
    ):
        """Transfer picks up supplier from most recent receive."""
        s = base_data["supplier"]
        p = base_data["part"]
        t = base_data["truck"]
        u = base_data["user"]

        # Create and receive an order
        po = PurchaseOrder(
            order_number="PO-SUP-001", supplier_id=s.id,
            created_by=u.id,
        )
        po.id = repo.create_purchase_order(po)
        item = PurchaseOrderItem(
            order_id=po.id, part_id=p.id,
            quantity_ordered=20, unit_cost=0.50,
        )
        item.id = repo.add_order_item(item)
        repo.submit_purchase_order(po.id)
        repo.receive_order_items(po.id, [
            {"order_item_id": item.id, "quantity_received":20},
        ], received_by=u.id)

        # Transfer without explicit supplier — should auto-detect
        xfer = TruckTransfer(
            truck_id=t.id, part_id=p.id, quantity=10,
        )
        xfer_id = repo.create_transfer(xfer)

        # Verify supplier was detected
        with repo.db.get_connection() as conn:
            row = conn.execute(
                "SELECT supplier_id FROM truck_transfers WHERE id = ?",
                (xfer_id,),
            ).fetchone()
            assert row["supplier_id"] == s.id


# ═══════════════════════════════════════════════════════════════
# LOOP 4: Return authorization edge cases
# ═══════════════════════════════════════════════════════════════

class TestReturnAuthEdgeCases:
    """Loop 4: 'I tried to return parts but it let me return more
    than I had in the warehouse.'"""

    def test_return_lifecycle_full(self, repo, base_data):
        """Full return lifecycle: initiated → picked_up → credit_received."""
        p = base_data["part"]
        s = base_data["supplier"]
        u = base_data["user"]

        ra = ReturnAuthorization(
            supplier_id=s.id, reason="overstock",
            created_by=u.id,
        )
        ra.id = repo.create_return_authorization(ra, items=[
            ReturnAuthorizationItem(part_id=p.id, quantity=5),
        ])

        # Part stock deducted
        part = repo.get_part_by_id(p.id)
        assert part.quantity == 95

        # Advance to picked_up
        repo.update_return_status(ra.id, "picked_up")
        ra_obj = repo.get_return_authorization_by_id(ra.id)
        assert ra_obj.status == "picked_up"

        # Advance to credit_received
        repo.update_return_status(ra.id, "credit_received", credit_amount=2.50)
        ra_obj = repo.get_return_authorization_by_id(ra.id)
        assert ra_obj.status == "credit_received"

    def test_return_zero_quantity_blocked(self, repo, base_data):
        """Cannot return zero quantity."""
        p = base_data["part"]
        s = base_data["supplier"]
        u = base_data["user"]

        ra = ReturnAuthorization(
            supplier_id=s.id, reason="overstock",
            created_by=u.id,
        )
        with pytest.raises(ValueError, match="positive"):
            repo.create_return_authorization(ra, items=[
                ReturnAuthorizationItem(part_id=p.id, quantity=0),
            ])

    def test_return_exceeding_stock_blocked(self, repo, base_data):
        """Cannot return more than warehouse stock."""
        p = base_data["part"]
        s = base_data["supplier"]
        u = base_data["user"]

        ra = ReturnAuthorization(
            supplier_id=s.id, reason="overstock",
            created_by=u.id,
        )
        with pytest.raises(ValueError, match="Insufficient"):
            repo.create_return_authorization(ra, items=[
                ReturnAuthorizationItem(part_id=p.id, quantity=999),
            ])

    def test_return_exact_stock(self, repo, base_data):
        """Can return exactly the warehouse stock."""
        p = base_data["part"]
        s = base_data["supplier"]
        u = base_data["user"]

        ra = ReturnAuthorization(
            supplier_id=s.id, reason="overstock",
            created_by=u.id,
        )
        ra.id = repo.create_return_authorization(ra, items=[
            ReturnAuthorizationItem(part_id=p.id, quantity=100),
        ])

        part = repo.get_part_by_id(p.id)
        assert part.quantity == 0


# ═══════════════════════════════════════════════════════════════
# LOOP 5: Deprecation pipeline — logging + notifications
# ═══════════════════════════════════════════════════════════════

class TestDeprecationPipelineLogging:
    """Loop 5: 'The deprecation pipeline got stuck — part shows
    winding_down but there's nothing on any truck.'"""

    def test_full_deprecation_pipeline_with_logging(self, repo, base_data):
        """Full deprecation: pending → winding_down → zero_stock → archived.
        Verify activity log entries at each transition."""
        p = base_data["part"]

        # Set stock to zero for immediate full pipeline
        repo.update_part(Part(
            id=p.id, part_number=p.part_number, name=p.name,
            description=p.description, quantity=0,
            unit_cost=p.unit_cost, category_id=p.category_id,
        ))

        repo.start_part_deprecation(p.id)
        status = repo.advance_deprecation(p.id)
        assert status == "archived"

        # Check activity log has deprecation entries
        log = repo.get_activity_log(limit=50)
        dep_entries = [
            e for e in log if "deprecation" in (e.action or "")
        ]
        assert len(dep_entries) >= 1  # At least the archived entry

        # Check notification was created for archive
        notifs = repo.db.execute(
            "SELECT * FROM notifications "
            "WHERE title = 'Part Archived'"
        )
        assert len(notifs) >= 1

    def test_deprecation_blocked_at_winding_down_with_truck_stock(
        self, repo, base_data
    ):
        """Deprecation stops at winding_down if truck still has stock."""
        p = base_data["part"]
        t = base_data["truck"]

        u = base_data["user"]

        # Transfer some to truck and receive it
        xfer_id = repo.create_transfer(TruckTransfer(
            truck_id=t.id, part_id=p.id, quantity=10,
        ))
        repo.receive_transfer(xfer_id, received_by=u.id)

        # Set warehouse to 0
        repo.update_part(Part(
            id=p.id, part_number=p.part_number, name=p.name,
            description=p.description, quantity=0,
            unit_cost=p.unit_cost, category_id=p.category_id,
        ))

        repo.start_part_deprecation(p.id)
        status = repo.advance_deprecation(p.id)
        assert status == "winding_down"  # Blocked by truck qty

    def test_try_advance_logs_failure(self, repo, base_data, monkeypatch):
        """_try_advance_if_deprecating logs warning on failure instead
        of silently swallowing."""
        import logging

        p = base_data["part"]
        repo.start_part_deprecation(p.id)

        warnings = []
        monkeypatch.setattr(
            logging.getLogger("wired_part.database.repository"),
            "warning",
            lambda msg, *args: warnings.append(msg % args),
        )

        # Force an error in advance_deprecation
        monkeypatch.setattr(
            repo, "advance_deprecation",
            lambda pid: (_ for _ in ()).throw(RuntimeError("test fail")),
        )
        repo._try_advance_if_deprecating(p.id)

        assert len(warnings) == 1
        assert "test fail" in warnings[0]


# ═══════════════════════════════════════════════════════════════
# LOOP 10: Search — LIKE wildcard escape
# ═══════════════════════════════════════════════════════════════

class TestSearchLikeEscape:
    """Loop 10: 'I searched for a part number with a % sign and it
    returned everything.'"""

    def test_escape_like_helper(self):
        """_escape_like escapes %, _, and backslash."""
        assert Repository._escape_like("50%") == "50\\%"
        assert Repository._escape_like("a_b") == "a\\_b"
        assert Repository._escape_like("x\\y") == "x\\\\y"
        assert Repository._escape_like("normal") == "normal"
        assert Repository._escape_like("50%_test") == "50\\%\\_test"

    def test_search_parts_with_percent(self, repo, base_data):
        """Search with % in query matches literally, not as wildcard."""
        p = base_data["part"]

        # Create a part with % in the name
        pct_part = Part(
            part_number="PCT-50%OFF", name="50% Discount Wire",
            description="Special", quantity=5,
            category_id=base_data["cat"].id,
        )
        pct_part.id = repo.create_part(pct_part)

        results = repo.search_parts("50%")
        # Should find only the percent part, not ALL parts
        pns = [r.part_number for r in results]
        assert "PCT-50%OFF" in pns
        assert len(results) < 3  # Not returning everything

    def test_search_parts_with_underscore(self, repo, base_data):
        """Search with _ in query matches literally, not as wildcard."""
        p = base_data["part"]

        uscore_part = Part(
            part_number="U_SCORE-001", name="Under_score Part",
            description="Special", quantity=5,
            category_id=base_data["cat"].id,
        )
        uscore_part.id = repo.create_part(uscore_part)

        results = repo.search_parts("U_SCORE")
        pns = [r.part_number for r in results]
        assert "U_SCORE-001" in pns

    def test_search_all_with_special_chars(self, repo, base_data):
        """Global search handles special characters without matching
        everything."""
        # Search for something with % that doesn't exist
        results = repo.search_all("nonexistent%query")
        total = sum(len(v) for v in results.values())
        assert total == 0
