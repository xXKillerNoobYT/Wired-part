"""Tests for part-supplier linking (many-to-many)."""

import pytest

from wired_part.database.models import Part, PartSupplier, Supplier


class TestPartSupplierLinks:
    """Test linking parts to suppliers and vice versa."""

    def _make_part_and_supplier(self, repo):
        pid = repo.create_part(Part(
            part_number="LINK-001", description="Test Part",
        ))
        sid = repo.create_supplier(Supplier(
            name="Test Supplier", preference_score=50,
        ))
        return pid, sid

    def test_link_part_supplier(self, repo):
        pid, sid = self._make_part_and_supplier(repo)
        link_id = repo.link_part_supplier(PartSupplier(
            part_id=pid, supplier_id=sid,
            supplier_part_number="SUP-PN-001",
            notes="Primary supplier",
        ))
        assert link_id > 0

    def test_get_part_suppliers(self, repo):
        pid, sid = self._make_part_and_supplier(repo)
        repo.link_part_supplier(PartSupplier(
            part_id=pid, supplier_id=sid,
            supplier_part_number="SUP-PN-001",
        ))
        links = repo.get_part_suppliers(pid)
        assert len(links) == 1
        assert links[0].supplier_name == "Test Supplier"
        assert links[0].supplier_part_number == "SUP-PN-001"

    def test_get_supplier_parts(self, repo):
        pid, sid = self._make_part_and_supplier(repo)
        repo.link_part_supplier(PartSupplier(
            part_id=pid, supplier_id=sid,
        ))
        links = repo.get_supplier_parts(sid)
        assert len(links) == 1
        assert links[0].part_id == pid

    def test_unlink_part_supplier(self, repo):
        pid, sid = self._make_part_and_supplier(repo)
        repo.link_part_supplier(PartSupplier(
            part_id=pid, supplier_id=sid,
        ))
        repo.unlink_part_supplier(pid, sid)
        links = repo.get_part_suppliers(pid)
        assert len(links) == 0

    def test_duplicate_link_fails(self, repo):
        pid, sid = self._make_part_and_supplier(repo)
        repo.link_part_supplier(PartSupplier(
            part_id=pid, supplier_id=sid,
        ))
        with pytest.raises(Exception):
            repo.link_part_supplier(PartSupplier(
                part_id=pid, supplier_id=sid,
            ))

    def test_multiple_suppliers_per_part(self, repo):
        pid = repo.create_part(Part(
            part_number="MULTI-001", description="Multi-supplier",
        ))
        sid1 = repo.create_supplier(Supplier(
            name="Supplier A", preference_score=80,
        ))
        sid2 = repo.create_supplier(Supplier(
            name="Supplier B", preference_score=60,
        ))
        repo.link_part_supplier(PartSupplier(
            part_id=pid, supplier_id=sid1,
        ))
        repo.link_part_supplier(PartSupplier(
            part_id=pid, supplier_id=sid2,
        ))
        links = repo.get_part_suppliers(pid)
        assert len(links) == 2
        names = [l.supplier_name for l in links]
        assert "Supplier A" in names
        assert "Supplier B" in names
