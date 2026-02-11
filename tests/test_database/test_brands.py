"""Tests for brand CRUD operations."""

import pytest

from wired_part.database.models import Brand, Part


class TestBrandCRUD:
    """Test brand creation, retrieval, update, and deletion."""

    def test_create_brand(self, repo):
        brand = Brand(name="Lutron", website="https://lutron.com",
                      notes="Dimmer specialist")
        bid = repo.create_brand(brand)
        assert bid > 0

    def test_get_all_brands(self, repo):
        repo.create_brand(Brand(name="Lutron"))
        repo.create_brand(Brand(name="Leviton"))
        repo.create_brand(Brand(name="Eaton"))
        brands = repo.get_all_brands()
        names = [b.name for b in brands]
        assert "Eaton" in names
        assert "Leviton" in names
        assert "Lutron" in names
        # Should be ordered alphabetically
        assert names == sorted(names)

    def test_get_brand_by_id(self, repo):
        bid = repo.create_brand(Brand(name="Lutron",
                                       website="https://lutron.com"))
        brand = repo.get_brand_by_id(bid)
        assert brand is not None
        assert brand.name == "Lutron"
        assert brand.website == "https://lutron.com"

    def test_get_brand_by_id_not_found(self, repo):
        assert repo.get_brand_by_id(9999) is None

    def test_get_brand_by_name(self, repo):
        repo.create_brand(Brand(name="Leviton"))
        brand = repo.get_brand_by_name("Leviton")
        assert brand is not None
        assert brand.name == "Leviton"

    def test_get_brand_by_name_not_found(self, repo):
        assert repo.get_brand_by_name("NonExistent") is None

    def test_update_brand(self, repo):
        bid = repo.create_brand(Brand(name="Lutron"))
        brand = repo.get_brand_by_id(bid)
        brand.website = "https://lutron.com"
        brand.notes = "Updated notes"
        repo.update_brand(brand)
        updated = repo.get_brand_by_id(bid)
        assert updated.website == "https://lutron.com"
        assert updated.notes == "Updated notes"

    def test_delete_brand(self, repo):
        bid = repo.create_brand(Brand(name="ToDelete"))
        repo.delete_brand(bid)
        assert repo.get_brand_by_id(bid) is None

    def test_unique_brand_name(self, repo):
        repo.create_brand(Brand(name="Lutron"))
        with pytest.raises(Exception):
            repo.create_brand(Brand(name="Lutron"))

    def test_delete_brand_clears_part_reference(self, repo):
        """Deleting a brand should SET NULL on parts.brand_id."""
        bid = repo.create_brand(Brand(name="TestBrand"))
        pid = repo.create_part(Part(
            part_number="SP-001", description="Test",
            part_type="specific", brand_id=bid,
            brand_part_number="TB-100",
        ))
        repo.delete_brand(bid)
        part = repo.get_part_by_id(pid)
        assert part.brand_id is None
