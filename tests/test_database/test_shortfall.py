"""Tests for shortfall detection and supply house features."""

import pytest

from wired_part.database.connection import DatabaseConnection
from wired_part.database.models import (
    Part,
    PartsList,
    PartsListItem,
    Supplier,
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
def parts(repo):
    """Create sample parts with varying stock levels."""
    p1_id = repo.create_part(Part(
        part_number="WIRE-001", description="12/2 NM-B Wire",
        quantity=100, unit_cost=0.50, min_quantity=20,
    ))
    p2_id = repo.create_part(Part(
        part_number="BOX-001", description="Single Gang Box",
        quantity=5, unit_cost=1.25, min_quantity=10,
    ))
    p3_id = repo.create_part(Part(
        part_number="BRK-001", description="20A Breaker",
        quantity=0, unit_cost=8.50, min_quantity=5,
    ))
    p4_id = repo.create_part(Part(
        part_number="SW-001", description="Single Pole Switch",
        quantity=50, unit_cost=2.00, min_quantity=10,
    ))
    return p1_id, p2_id, p3_id, p4_id


@pytest.fixture
def parts_list(repo, parts):
    """Create a parts list requiring specific quantities."""
    p1_id, p2_id, p3_id, p4_id = parts
    list_id = repo.create_parts_list(PartsList(
        name="Test Job List", list_type="general",
    ))
    # Need 50 WIRE-001 (in stock: 100 -- OK)
    repo.add_item_to_parts_list(PartsListItem(
        list_id=list_id, part_id=p1_id, quantity=50,
    ))
    # Need 20 BOX-001 (in stock: 5 -- SHORTFALL: 15)
    repo.add_item_to_parts_list(PartsListItem(
        list_id=list_id, part_id=p2_id, quantity=20,
    ))
    # Need 10 BRK-001 (in stock: 0 -- SHORTFALL: 10)
    repo.add_item_to_parts_list(PartsListItem(
        list_id=list_id, part_id=p3_id, quantity=10,
    ))
    # Need 25 SW-001 (in stock: 50 -- OK)
    repo.add_item_to_parts_list(PartsListItem(
        list_id=list_id, part_id=p4_id, quantity=25,
    ))
    return list_id


class TestShortfallDetection:
    """Test check_shortfall() method."""

    def test_detects_shortfalls(self, repo, parts_list, parts):
        shortfalls = repo.check_shortfall(parts_list)
        assert len(shortfalls) == 2  # BOX-001 and BRK-001

    def test_shortfall_details(self, repo, parts_list, parts):
        shortfalls = repo.check_shortfall(parts_list)
        by_part = {sf["part_number"]: sf for sf in shortfalls}

        # BOX-001: need 20, have 5, short 15
        assert "BOX-001" in by_part
        box = by_part["BOX-001"]
        assert box["required"] == 20
        assert box["in_stock"] == 5
        assert box["shortfall"] == 15

        # BRK-001: need 10, have 0, short 10
        assert "BRK-001" in by_part
        brk = by_part["BRK-001"]
        assert brk["required"] == 10
        assert brk["in_stock"] == 0
        assert brk["shortfall"] == 10

    def test_no_shortfall_when_sufficient_stock(self, repo, parts):
        """List with items all in stock should return empty."""
        p1_id, _, _, p4_id = parts
        list_id = repo.create_parts_list(PartsList(
            name="Well-Stocked List", list_type="general",
        ))
        repo.add_item_to_parts_list(PartsListItem(
            list_id=list_id, part_id=p1_id, quantity=10,
        ))
        repo.add_item_to_parts_list(PartsListItem(
            list_id=list_id, part_id=p4_id, quantity=10,
        ))
        shortfalls = repo.check_shortfall(list_id)
        assert shortfalls == []

    def test_shortfall_includes_unit_cost(self, repo, parts_list):
        shortfalls = repo.check_shortfall(parts_list)
        for sf in shortfalls:
            assert "unit_cost" in sf
            assert sf["unit_cost"] > 0

    def test_empty_list_no_shortfalls(self, repo):
        list_id = repo.create_parts_list(PartsList(
            name="Empty List", list_type="general",
        ))
        shortfalls = repo.check_shortfall(list_id)
        assert shortfalls == []


class TestSupplyHouseSupport:
    """Test supply house fields on suppliers."""

    def test_create_supply_house_supplier(self, repo):
        sid = repo.create_supplier(Supplier(
            name="City Electric Supply",
            phone="555-1234",
            is_supply_house=1,
            operating_hours="Mon-Fri 6am-5pm, Sat 7am-12pm",
        ))
        supplier = repo.get_supplier_by_id(sid)
        assert supplier.is_supply_house == 1
        assert supplier.operating_hours == "Mon-Fri 6am-5pm, Sat 7am-12pm"

    def test_regular_supplier_not_supply_house(self, repo):
        sid = repo.create_supplier(Supplier(
            name="Online Wholesale",
        ))
        supplier = repo.get_supplier_by_id(sid)
        assert supplier.is_supply_house == 0
        assert supplier.operating_hours == ""

    def test_update_to_supply_house(self, repo):
        sid = repo.create_supplier(Supplier(
            name="Local Hardware",
        ))
        supplier = repo.get_supplier_by_id(sid)
        assert supplier.is_supply_house == 0

        supplier.is_supply_house = 1
        supplier.operating_hours = "Mon-Sat 7am-6pm"
        repo.update_supplier(supplier)

        updated = repo.get_supplier_by_id(sid)
        assert updated.is_supply_house == 1
        assert updated.operating_hours == "Mon-Sat 7am-6pm"

    def test_filter_supply_houses(self, repo):
        repo.create_supplier(Supplier(
            name="Regular Supplier A",
            is_supply_house=0,
        ))
        repo.create_supplier(Supplier(
            name="Supply House B",
            is_supply_house=1,
            operating_hours="Mon-Fri 6am-5pm",
        ))
        repo.create_supplier(Supplier(
            name="Supply House C",
            is_supply_house=1,
            operating_hours="Mon-Sat 7am-6pm",
        ))

        all_suppliers = repo.get_all_suppliers()
        supply_houses = [s for s in all_suppliers if s.is_supply_house]
        assert len(supply_houses) == 2

        regular = [s for s in all_suppliers if not s.is_supply_house]
        assert len(regular) == 1
