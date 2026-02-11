"""Tests for part type system (general vs specific), v8 fields."""

import json

import pytest

from wired_part.database.models import Brand, Part


class TestPartTypes:
    """Test general/specific part type handling."""

    def test_create_general_part(self, repo):
        pid = repo.create_part(Part(
            part_number="GEN-001",
            description="Standard Outlet",
            part_type="general",
            subcategory="Duplex",
            color_options=json.dumps(["White", "Ivory"]),
            type_style=json.dumps(["Decora"]),
        ))
        part = repo.get_part_by_id(pid)
        assert part.part_type == "general"
        assert part.is_general is True
        assert part.is_specific is False
        assert part.subcategory == "Duplex"
        assert part.color_option_list == ["White", "Ivory"]
        assert part.type_style_list == ["Decora"]

    def test_create_specific_part(self, repo):
        bid = repo.create_brand(Brand(name="Lutron"))
        pid = repo.create_part(Part(
            part_number="SP-001",
            description="Caseta Dimmer",
            part_type="specific",
            brand_id=bid,
            brand_part_number="PD-5ANS-WH",
            local_part_number="LP-0001",
        ))
        part = repo.get_part_by_id(pid)
        assert part.part_type == "specific"
        assert part.is_specific is True
        assert part.is_general is False
        assert part.brand_id == bid
        assert part.brand_part_number == "PD-5ANS-WH"
        assert part.local_part_number == "LP-0001"
        assert part.brand_name == "Lutron"

    def test_get_parts_by_type_general(self, repo):
        repo.create_part(Part(
            part_number="GEN-001", description="Outlet",
            part_type="general",
        ))
        repo.create_part(Part(
            part_number="SP-001", description="Dimmer",
            part_type="specific",
        ))
        general = repo.get_parts_by_type("general")
        assert len(general) == 1
        assert general[0].part_number == "GEN-001"

    def test_get_parts_by_type_specific(self, repo):
        repo.create_part(Part(
            part_number="GEN-001", description="Outlet",
            part_type="general",
        ))
        repo.create_part(Part(
            part_number="SP-001", description="Dimmer",
            part_type="specific",
        ))
        specific = repo.get_parts_by_type("specific")
        assert len(specific) == 1
        assert specific[0].part_number == "SP-001"

    def test_get_parts_by_brand(self, repo):
        bid = repo.create_brand(Brand(name="Lutron"))
        repo.create_part(Part(
            part_number="SP-001", description="Dimmer",
            part_type="specific", brand_id=bid,
        ))
        repo.create_part(Part(
            part_number="GEN-001", description="Outlet",
            part_type="general",
        ))
        brand_parts = repo.get_parts_by_brand(bid)
        assert len(brand_parts) == 1
        assert brand_parts[0].part_number == "SP-001"


class TestIncompleteDetection:
    """Test the is_incomplete property and count query."""

    def test_general_part_complete(self, repo):
        """General part with name, cost, category → not incomplete."""
        cats = repo.get_all_categories()
        pid = repo.create_part(Part(
            name="Good Part", part_number="GEN-OK",
            description="A good general part",
            part_type="general", unit_cost=5.0,
            category_id=cats[0].id,
        ))
        part = repo.get_part_by_id(pid)
        assert part.is_incomplete is False

    def test_general_part_missing_name(self, repo):
        """General part without name → incomplete."""
        cats = repo.get_all_categories()
        part = Part(
            name="", part_number="GEN-BAD", description="No name",
            part_type="general", unit_cost=5.0,
            category_id=cats[0].id,
        )
        assert part.is_incomplete is True

    def test_general_part_missing_cost(self, repo):
        cats = repo.get_all_categories()
        part = Part(
            name="Something", part_number="GEN-BAD2",
            part_type="general", unit_cost=0.0,
            category_id=cats[0].id,
        )
        assert part.is_incomplete is True

    def test_specific_part_complete(self, repo):
        cats = repo.get_all_categories()
        bid = repo.create_brand(Brand(name="TestBrand"))
        pid = repo.create_part(Part(
            name="Good Specific", part_number="SP-OK",
            description="A specific branded part",
            part_type="specific", unit_cost=25.0,
            category_id=cats[0].id,
            brand_id=bid, brand_part_number="TB-100",
        ))
        part = repo.get_part_by_id(pid)
        assert part.is_incomplete is False

    def test_specific_part_missing_brand(self, repo):
        cats = repo.get_all_categories()
        part = Part(
            name="Missing Brand", part_number="SP-BAD",
            part_type="specific", unit_cost=25.0,
            category_id=cats[0].id,
            brand_part_number="TB-100",
        )
        assert part.is_incomplete is True

    def test_specific_part_missing_brand_pn(self, repo):
        cats = repo.get_all_categories()
        bid = repo.create_brand(Brand(name="TestBrand"))
        part = Part(
            name="Missing BPN", part_number="SP-BAD2",
            part_type="specific", unit_cost=25.0,
            category_id=cats[0].id, brand_id=bid,
        )
        assert part.is_incomplete is True

    def test_specific_part_missing_part_number(self, repo):
        """Specific part without part_number → incomplete."""
        cats = repo.get_all_categories()
        bid = repo.create_brand(Brand(name="TestBrand2"))
        part = Part(
            name="No PN", part_number="",
            part_type="specific", unit_cost=25.0,
            category_id=cats[0].id,
            brand_id=bid, brand_part_number="TB-200",
        )
        assert part.is_incomplete is True

    def test_general_part_without_part_number_not_incomplete(self, repo):
        """General part without part_number → NOT incomplete (optional)."""
        cats = repo.get_all_categories()
        part = Part(
            name="General No PN", part_number="",
            part_type="general", unit_cost=5.0,
            category_id=cats[0].id,
        )
        assert part.is_incomplete is False

    def test_incomplete_parts_count(self, repo):
        cats = repo.get_all_categories()
        # Create a complete general part (has name, cost, category)
        repo.create_part(Part(
            name="Good Part", part_number="GEN-OK",
            part_type="general", unit_cost=5.0,
            category_id=cats[0].id,
        ))
        # Create an incomplete specific part (no brand)
        repo.create_part(Part(
            name="Incomplete Specific", part_number="SP-BAD",
            part_type="specific", unit_cost=25.0,
            category_id=cats[0].id,
        ))
        # Create an incomplete general part (no name)
        repo.create_part(Part(
            name="", part_number="GEN-BAD",
            part_type="general", unit_cost=5.0,
            category_id=cats[0].id,
        ))
        count = repo.get_incomplete_parts_count()
        assert count == 2


class TestQRTagTracking:
    """Test QR tag fields and queries."""

    def test_qr_tag_default_false(self, repo):
        pid = repo.create_part(Part(
            part_number="QR-001", description="No tag yet",
        ))
        part = repo.get_part_by_id(pid)
        assert part.has_qr_tag == 0

    def test_set_qr_tag(self, repo):
        pid = repo.create_part(Part(
            part_number="QR-002", description="Will get tag",
        ))
        part = repo.get_part_by_id(pid)
        part.has_qr_tag = 1
        repo.update_part(part)
        updated = repo.get_part_by_id(pid)
        assert updated.has_qr_tag == 1

    def test_get_parts_needing_qr_tags(self, repo):
        repo.create_part(Part(
            part_number="QR-YES", description="Has tag",
            has_qr_tag=1,
        ))
        repo.create_part(Part(
            part_number="QR-NO", description="No tag",
            has_qr_tag=0,
        ))
        needing = repo.get_parts_needing_qr_tags()
        pns = [p.part_number for p in needing]
        assert "QR-NO" in pns
        assert "QR-YES" not in pns


class TestLocalPartNumber:
    """Test local part number generation."""

    def test_generate_first_local_pn(self, repo):
        lpn = repo.generate_local_part_number()
        assert lpn == "LP-0001"

    def test_generate_sequential_local_pn(self, repo):
        repo.create_part(Part(
            part_number="P1", description="First",
            local_part_number="LP-0001",
        ))
        lpn = repo.generate_local_part_number()
        assert lpn == "LP-0002"

    def test_generate_handles_gaps(self, repo):
        repo.create_part(Part(
            part_number="P1", description="First",
            local_part_number="LP-0005",
        ))
        lpn = repo.generate_local_part_number()
        assert lpn == "LP-0006"


class TestSearchWithV8Fields:
    """Test that search_parts finds v8 fields."""

    def test_search_by_brand_part_number(self, repo):
        repo.create_part(Part(
            part_number="SP-001", description="Dimmer",
            brand_part_number="PD-5ANS-WH",
        ))
        results = repo.search_parts("PD-5ANS")
        assert len(results) == 1

    def test_search_by_local_part_number(self, repo):
        repo.create_part(Part(
            part_number="SP-002", description="Switch",
            local_part_number="LP-0042",
        ))
        results = repo.search_parts("LP-0042")
        assert len(results) == 1

    def test_search_by_brand_name(self, repo):
        bid = repo.create_brand(Brand(name="Lutron"))
        repo.create_part(Part(
            part_number="SP-003", description="Caseta",
            brand_id=bid,
        ))
        results = repo.search_parts("Lutron")
        assert len(results) == 1

    def test_search_by_subcategory(self, repo):
        repo.create_part(Part(
            part_number="GEN-001", description="Outlet",
            subcategory="Tamper-Resistant",
        ))
        results = repo.search_parts("Tamper")
        assert len(results) == 1
