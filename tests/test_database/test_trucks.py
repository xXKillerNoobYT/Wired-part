"""Tests for truck management, transfers, and inventory."""

import pytest

from wired_part.database.models import (
    Part,
    Truck,
    TruckTransfer,
    User,
)
from wired_part.database.repository import Repository


@pytest.fixture
def setup_data(repo):
    """Create a user, truck, and part for testing."""
    user = User(
        username="driver1", display_name="Driver One",
        pin_hash=Repository.hash_pin("1234"),
        role="user", is_active=1,
    )
    user_id = repo.create_user(user)

    truck = Truck(
        truck_number="TRUCK-001", name="Test Truck",
        assigned_user_id=user_id, is_active=1,
    )
    truck_id = repo.create_truck(truck)

    part = Part(
        part_number="WIRE-001", description="12/2 Romex",
        quantity=100, unit_cost=25.0, min_quantity=10,
    )
    part_id = repo.create_part(part)

    return {"user_id": user_id, "truck_id": truck_id, "part_id": part_id}


class TestTruckCRUD:
    """Test truck creation and retrieval."""

    def test_create_truck(self, repo):
        truck = Truck(
            truck_number="T-100", name="Ford F250",
            is_active=1,
        )
        tid = repo.create_truck(truck)
        assert tid > 0

    def test_get_truck_by_id(self, repo, setup_data):
        truck = repo.get_truck_by_id(setup_data["truck_id"])
        assert truck is not None
        assert truck.truck_number == "TRUCK-001"
        assert truck.assigned_user_name == "Driver One"

    def test_get_all_trucks(self, repo, setup_data):
        trucks = repo.get_all_trucks(active_only=True)
        assert len(trucks) >= 1
        assert any(t.truck_number == "TRUCK-001" for t in trucks)


class TestTransferWorkflow:
    """Test the warehouse -> truck transfer workflow."""

    def test_create_transfer_deducts_warehouse(self, repo, setup_data):
        transfer = TruckTransfer(
            truck_id=setup_data["truck_id"],
            part_id=setup_data["part_id"],
            quantity=10,
            created_by=setup_data["user_id"],
        )
        tid = repo.create_transfer(transfer)
        assert tid > 0

        # Warehouse stock should be reduced
        part = repo.get_part_by_id(setup_data["part_id"])
        assert part.quantity == 90

    def test_create_transfer_insufficient_stock(self, repo, setup_data):
        transfer = TruckTransfer(
            truck_id=setup_data["truck_id"],
            part_id=setup_data["part_id"],
            quantity=999,
            created_by=setup_data["user_id"],
        )
        with pytest.raises(ValueError, match="Insufficient"):
            repo.create_transfer(transfer)

    def test_receive_transfer_adds_to_truck(self, repo, setup_data):
        transfer = TruckTransfer(
            truck_id=setup_data["truck_id"],
            part_id=setup_data["part_id"],
            quantity=15,
            created_by=setup_data["user_id"],
        )
        tid = repo.create_transfer(transfer)

        # Receive the transfer
        repo.receive_transfer(tid, setup_data["user_id"])

        # Truck should now have 15 on-hand
        inv = repo.get_truck_inventory(setup_data["truck_id"])
        assert len(inv) == 1
        assert inv[0].quantity == 15

        # Transfer should be marked as received
        transfers = repo.get_truck_transfers(
            setup_data["truck_id"], status="received"
        )
        assert len(transfers) >= 1

    def test_cancel_transfer_restores_warehouse(self, repo, setup_data):
        transfer = TruckTransfer(
            truck_id=setup_data["truck_id"],
            part_id=setup_data["part_id"],
            quantity=20,
            created_by=setup_data["user_id"],
        )
        tid = repo.create_transfer(transfer)

        # Stock was 100, now 80
        part = repo.get_part_by_id(setup_data["part_id"])
        assert part.quantity == 80

        # Cancel
        repo.cancel_transfer(tid)

        # Stock restored to 100
        part = repo.get_part_by_id(setup_data["part_id"])
        assert part.quantity == 100

    def test_return_to_warehouse(self, repo, setup_data):
        # First: transfer 10 to truck and receive
        transfer = TruckTransfer(
            truck_id=setup_data["truck_id"],
            part_id=setup_data["part_id"],
            quantity=10,
            created_by=setup_data["user_id"],
        )
        tid = repo.create_transfer(transfer)
        repo.receive_transfer(tid, setup_data["user_id"])

        # Warehouse: 90, Truck: 10
        part = repo.get_part_by_id(setup_data["part_id"])
        assert part.quantity == 90

        # Return 5 to warehouse
        repo.return_to_warehouse(
            setup_data["truck_id"], setup_data["part_id"],
            5, setup_data["user_id"]
        )

        # Warehouse: 95, Truck: 5
        part = repo.get_part_by_id(setup_data["part_id"])
        assert part.quantity == 95

        inv = repo.get_truck_inventory(setup_data["truck_id"])
        assert inv[0].quantity == 5
