"""Tests for return authorization CRUD, items, status workflow."""

import pytest

from wired_part.database.connection import DatabaseConnection
from wired_part.database.models import (
    Part,
    ReturnAuthorization,
    ReturnAuthorizationItem,
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
    p1 = Part(
        part_number="WIRE-001",
        description="14 AWG Wire",
        quantity=100,
        unit_cost=0.50,
        min_quantity=20,
    )
    p1.id = repo.create_part(p1)

    p2 = Part(
        part_number="BOX-001",
        description="4x4 Junction Box",
        quantity=50,
        unit_cost=2.75,
        min_quantity=5,
    )
    p2.id = repo.create_part(p2)
    return [p1, p2]


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
def initiated_ra(repo, supplier, parts, test_user):
    """Create an RA with items in initiated status."""
    ra = ReturnAuthorization(
        ra_number=repo.generate_ra_number(),
        supplier_id=supplier.id,
        status="initiated",
        reason="wrong_part",
        notes="Wrong part shipped",
        created_by=test_user.id,
    )
    items = [
        ReturnAuthorizationItem(
            part_id=parts[0].id,
            quantity=5,
            unit_cost=parts[0].unit_cost,
            reason="Wrong gauge",
        ),
    ]
    ra.id = repo.create_return_authorization(ra, items)
    return ra


class TestReturnAuthorizationCRUD:
    """Test return authorization create, read, delete."""

    def test_create_return_authorization(
        self, repo, supplier, parts, test_user
    ):
        ra = ReturnAuthorization(
            ra_number=repo.generate_ra_number(),
            supplier_id=supplier.id,
            status="initiated",
            reason="damaged",
            notes="Damaged in shipping",
            created_by=test_user.id,
        )
        items = [
            ReturnAuthorizationItem(
                part_id=parts[0].id,
                quantity=3,
                unit_cost=0.50,
                reason="Bent connectors",
            ),
        ]
        ra_id = repo.create_return_authorization(ra, items)
        assert ra_id > 0

    def test_get_ra_by_id(self, repo, initiated_ra):
        ra = repo.get_return_authorization_by_id(initiated_ra.id)
        assert ra is not None
        assert ra.supplier_name == "Acme Electric"
        assert ra.reason == "wrong_part"
        assert ra.item_count == 1

    def test_get_all_ras(self, repo, initiated_ra):
        ras = repo.get_all_return_authorizations()
        assert len(ras) >= 1
        assert any(r.id == initiated_ra.id for r in ras)

    def test_get_all_ras_by_status(self, repo, initiated_ra):
        initiated = repo.get_all_return_authorizations(status="initiated")
        assert len(initiated) >= 1

        picked_up = repo.get_all_return_authorizations(status="picked_up")
        assert len(picked_up) == 0

    def test_generate_ra_number(self, repo):
        num = repo.generate_ra_number()
        assert num.startswith("RA-")
        assert len(num.split("-")) == 3

    def test_delete_initiated_ra(self, repo, initiated_ra):
        repo.delete_return_authorization(initiated_ra.id)
        ra = repo.get_return_authorization_by_id(initiated_ra.id)
        assert ra is None

    def test_cannot_delete_picked_up_ra(self, repo, initiated_ra):
        repo.update_return_status(initiated_ra.id, "picked_up")
        with pytest.raises(ValueError, match="Only initiated"):
            repo.delete_return_authorization(initiated_ra.id)


class TestReturnItems:
    """Test return authorization item operations."""

    def test_add_return_items(self, repo, supplier, parts, test_user):
        ra = ReturnAuthorization(
            ra_number=repo.generate_ra_number(),
            supplier_id=supplier.id,
            status="initiated",
            reason="overstock",
            created_by=test_user.id,
        )
        items = [
            ReturnAuthorizationItem(
                part_id=parts[0].id, quantity=2, unit_cost=0.50,
            ),
            ReturnAuthorizationItem(
                part_id=parts[1].id, quantity=3, unit_cost=2.75,
            ),
        ]
        ra_id = repo.create_return_authorization(ra, items)

        fetched_items = repo.get_return_items(ra_id)
        assert len(fetched_items) == 2

    def test_get_return_items(self, repo, initiated_ra):
        items = repo.get_return_items(initiated_ra.id)
        assert len(items) == 1
        assert items[0].part_number == "WIRE-001"
        assert items[0].quantity == 5
        assert items[0].reason == "Wrong gauge"

    def test_return_deducts_inventory(self, repo, supplier, parts, test_user):
        initial_qty = repo.get_part_by_id(parts[0].id).quantity

        ra = ReturnAuthorization(
            ra_number=repo.generate_ra_number(),
            supplier_id=supplier.id,
            status="initiated",
            reason="wrong_part",
            created_by=test_user.id,
        )
        items = [
            ReturnAuthorizationItem(
                part_id=parts[0].id, quantity=10, unit_cost=0.50,
            ),
        ]
        repo.create_return_authorization(ra, items)

        part = repo.get_part_by_id(parts[0].id)
        assert part.quantity == initial_qty - 10

    def test_delete_return_restores_inventory(
        self, repo, supplier, parts, test_user
    ):
        initial_qty = repo.get_part_by_id(parts[0].id).quantity

        ra = ReturnAuthorization(
            ra_number=repo.generate_ra_number(),
            supplier_id=supplier.id,
            status="initiated",
            reason="wrong_part",
            created_by=test_user.id,
        )
        items = [
            ReturnAuthorizationItem(
                part_id=parts[0].id, quantity=8, unit_cost=0.50,
            ),
        ]
        ra_id = repo.create_return_authorization(ra, items)

        # Quantity should be reduced
        part = repo.get_part_by_id(parts[0].id)
        assert part.quantity == initial_qty - 8

        # Delete restores it
        repo.delete_return_authorization(ra_id)
        part = repo.get_part_by_id(parts[0].id)
        assert part.quantity == initial_qty


class TestReturnStatusWorkflow:
    """Test return status transitions."""

    def test_mark_picked_up(self, repo, initiated_ra):
        repo.update_return_status(initiated_ra.id, "picked_up")
        ra = repo.get_return_authorization_by_id(initiated_ra.id)
        assert ra.status == "picked_up"
        assert ra.picked_up_at is not None

    def test_mark_credit_received(self, repo, initiated_ra):
        repo.update_return_status(initiated_ra.id, "picked_up")
        repo.update_return_status(
            initiated_ra.id, "credit_received", credit_amount=25.50
        )
        ra = repo.get_return_authorization_by_id(initiated_ra.id)
        assert ra.status == "credit_received"
        assert ra.credit_received_at is not None
        assert ra.credit_amount == 25.50

    def test_credit_amount_set_on_credit_received(
        self, repo, initiated_ra
    ):
        repo.update_return_status(
            initiated_ra.id, "credit_received", credit_amount=100.00
        )
        ra = repo.get_return_authorization_by_id(initiated_ra.id)
        assert ra.credit_amount == 100.00

    def test_cancel_return(self, repo, initiated_ra):
        repo.update_return_status(initiated_ra.id, "cancelled")
        ra = repo.get_return_authorization_by_id(initiated_ra.id)
        assert ra.status == "cancelled"
