"""Tests for part variant CRUD operations (v9 — type_style hierarchy)."""

import pytest

from wired_part.database.models import Part, PartVariant


class TestPartVariantCRUD:
    """Test variant creation, retrieval, update, and deletion."""

    def _make_part(self, repo):
        return repo.create_part(Part(
            name="Test Part", part_number="VAR-001",
            description="Test Part for Variants",
            part_type="specific",
        ))

    def test_create_variant(self, repo):
        pid = self._make_part(repo)
        vid = repo.create_part_variant(PartVariant(
            part_id=pid, type_style="Standard",
            color_finish="White",
            brand_part_number="TP-WH",
            notes="Standard white",
        ))
        assert vid > 0

    def test_get_part_variants(self, repo):
        pid = self._make_part(repo)
        repo.create_part_variant(PartVariant(
            part_id=pid, type_style="Standard",
            color_finish="White",
            brand_part_number="TP-WH",
        ))
        repo.create_part_variant(PartVariant(
            part_id=pid, type_style="Standard",
            color_finish="Ivory",
            brand_part_number="TP-IV",
        ))
        variants = repo.get_part_variants(pid)
        assert len(variants) == 2
        colors = [v.color_finish for v in variants]
        assert "Ivory" in colors
        assert "White" in colors

    def test_get_variant_by_id(self, repo):
        pid = self._make_part(repo)
        vid = repo.create_part_variant(PartVariant(
            part_id=pid, type_style="GFI",
            color_finish="Black",
            brand_part_number="TP-BK",
            image_path="/images/black.png",
        ))
        variant = repo.get_part_variant_by_id(vid)
        assert variant is not None
        assert variant.type_style == "GFI"
        assert variant.color_finish == "Black"
        assert variant.brand_part_number == "TP-BK"
        assert variant.image_path == "/images/black.png"

    def test_update_variant(self, repo):
        pid = self._make_part(repo)
        vid = repo.create_part_variant(PartVariant(
            part_id=pid, type_style="Standard",
            color_finish="White",
        ))
        variant = repo.get_part_variant_by_id(vid)
        variant.brand_part_number = "TP-WH-NEW"
        variant.notes = "Updated"
        variant.type_style = "Decora"
        repo.update_part_variant(variant)
        updated = repo.get_part_variant_by_id(vid)
        assert updated.brand_part_number == "TP-WH-NEW"
        assert updated.notes == "Updated"
        assert updated.type_style == "Decora"

    def test_delete_variant(self, repo):
        pid = self._make_part(repo)
        vid = repo.create_part_variant(PartVariant(
            part_id=pid, type_style="Standard",
            color_finish="White",
        ))
        repo.delete_part_variant(vid)
        assert repo.get_part_variant_by_id(vid) is None

    def test_unique_color_per_type_style(self, repo):
        """Same color_finish + type_style on same part should fail."""
        pid = self._make_part(repo)
        repo.create_part_variant(PartVariant(
            part_id=pid, type_style="Standard",
            color_finish="White",
        ))
        with pytest.raises(Exception):
            repo.create_part_variant(PartVariant(
                part_id=pid, type_style="Standard",
                color_finish="White",
            ))

    def test_same_color_different_types_allowed(self, repo):
        """Same color under different type/styles should be allowed."""
        pid = self._make_part(repo)
        repo.create_part_variant(PartVariant(
            part_id=pid, type_style="Standard",
            color_finish="White",
        ))
        vid2 = repo.create_part_variant(PartVariant(
            part_id=pid, type_style="GFI",
            color_finish="White",
        ))
        assert vid2 > 0
        variants = repo.get_part_variants(pid)
        assert len(variants) == 2

    def test_variant_type_style_field(self, repo):
        """Verify type_style is saved and retrieved correctly."""
        pid = self._make_part(repo)
        vid = repo.create_part_variant(PartVariant(
            part_id=pid, type_style="Decora",
            color_finish="Light Almond",
            brand_part_number="DEC-LA",
        ))
        variant = repo.get_part_variant_by_id(vid)
        assert variant.type_style == "Decora"
        assert variant.color_finish == "Light Almond"
        assert variant.brand_part_number == "DEC-LA"

    def test_variants_ordered_by_type_then_color(self, repo):
        """Variants should be ordered by type_style, then color_finish."""
        pid = self._make_part(repo)
        repo.create_part_variant(PartVariant(
            part_id=pid, type_style="Standard",
            color_finish="White",
        ))
        repo.create_part_variant(PartVariant(
            part_id=pid, type_style="GFI",
            color_finish="Black",
        ))
        repo.create_part_variant(PartVariant(
            part_id=pid, type_style="GFI",
            color_finish="Almond",
        ))
        variants = repo.get_part_variants(pid)
        assert len(variants) == 3
        assert variants[0].type_style == "GFI"
        assert variants[0].color_finish == "Almond"
        assert variants[1].type_style == "GFI"
        assert variants[1].color_finish == "Black"
        assert variants[2].type_style == "Standard"
        assert variants[2].color_finish == "White"

    def test_cascade_delete_with_part(self, repo):
        """Deleting a part should cascade-delete its variants."""
        pid = self._make_part(repo)
        vid = repo.create_part_variant(PartVariant(
            part_id=pid, type_style="Standard",
            color_finish="Red",
        ))
        repo.delete_part(pid)
        assert repo.get_part_variant_by_id(vid) is None
