"""Tests for supplier CRUD operations."""

import pytest

from wired_part.database.models import Supplier


class TestSupplierCRUD:
    """Test supplier creation, retrieval, update, and deletion."""

    def test_create_supplier(self, repo):
        supplier = Supplier(
            name="Acme Electric Supply",
            contact_name="John Doe",
            email="john@acme.com",
            phone="555-0100",
            address="123 Main St",
            preference_score=80,
            delivery_schedule="Next day delivery",
        )
        sid = repo.create_supplier(supplier)
        assert sid > 0

    def test_get_supplier_by_id(self, repo):
        sid = repo.create_supplier(Supplier(
            name="Best Parts Co",
            contact_name="Jane Smith",
            email="jane@bestparts.com",
            phone="555-0200",
            preference_score=90,
        ))
        supplier = repo.get_supplier_by_id(sid)
        assert supplier is not None
        assert supplier.name == "Best Parts Co"
        assert supplier.contact_name == "Jane Smith"
        assert supplier.email == "jane@bestparts.com"
        assert supplier.preference_score == 90

    def test_get_supplier_by_id_not_found(self, repo):
        supplier = repo.get_supplier_by_id(9999)
        assert supplier is None

    def test_get_all_suppliers(self, repo):
        repo.create_supplier(Supplier(
            name="Supplier A", preference_score=60,
        ))
        repo.create_supplier(Supplier(
            name="Supplier B", preference_score=90,
        ))
        suppliers = repo.get_all_suppliers()
        assert len(suppliers) == 2
        # Higher preference_score first
        assert suppliers[0].name == "Supplier B"
        assert suppliers[1].name == "Supplier A"

    def test_get_all_suppliers_active_only(self, repo):
        repo.create_supplier(Supplier(
            name="Active Supplier", is_active=1, preference_score=50,
        ))
        repo.create_supplier(Supplier(
            name="Inactive Supplier", is_active=0, preference_score=50,
        ))
        active = repo.get_all_suppliers(active_only=True)
        all_suppliers = repo.get_all_suppliers(active_only=False)
        assert len(active) == 1
        assert active[0].name == "Active Supplier"
        assert len(all_suppliers) == 2

    def test_update_supplier(self, repo):
        sid = repo.create_supplier(Supplier(
            name="Original Name",
            contact_name="Old Contact",
            preference_score=50,
        ))
        supplier = repo.get_supplier_by_id(sid)
        supplier.name = "Updated Name"
        supplier.contact_name = "New Contact"
        supplier.preference_score = 95
        repo.update_supplier(supplier)

        updated = repo.get_supplier_by_id(sid)
        assert updated.name == "Updated Name"
        assert updated.contact_name == "New Contact"
        assert updated.preference_score == 95

    def test_delete_supplier(self, repo):
        sid = repo.create_supplier(Supplier(
            name="To Delete", preference_score=50,
        ))
        assert repo.get_supplier_by_id(sid) is not None
        repo.delete_supplier(sid)
        assert repo.get_supplier_by_id(sid) is None

    def test_supplier_default_values(self, repo):
        sid = repo.create_supplier(Supplier(name="Minimal Supplier"))
        supplier = repo.get_supplier_by_id(sid)
        assert supplier.name == "Minimal Supplier"
        assert supplier.preference_score == 50
        assert supplier.is_active == 1
        assert supplier.contact_name == ""
        assert supplier.email == ""
