"""Tests for category CRUD and part-category relationships."""

import pytest

from wired_part.database.models import Category, Part


class TestCategoryCRUD:
    """Test category create, read, update, delete operations."""

    def test_get_all_categories(self, repo):
        """Default categories exist after init."""
        cats = repo.get_all_categories()
        assert len(cats) > 0

    def test_create_category(self, repo):
        cat = Category(name="Test Cat", description="A test category")
        cid = repo.create_category(cat)
        assert cid > 0

    def test_get_category_by_id(self, repo):
        cat = Category(name="Fetch Cat")
        cid = repo.create_category(cat)
        fetched = repo.get_category_by_id(cid)
        assert fetched is not None
        assert fetched.name == "Fetch Cat"

    def test_get_category_by_id_nonexistent(self, repo):
        assert repo.get_category_by_id(9999) is None

    def test_update_category(self, repo):
        cid = repo.create_category(Category(name="Old Name"))
        cat = repo.get_category_by_id(cid)
        cat.name = "New Name"
        repo.update_category(cat)
        updated = repo.get_category_by_id(cid)
        assert updated.name == "New Name"

    def test_delete_category(self, repo):
        cid = repo.create_category(Category(name="Delete Me"))
        repo.delete_category(cid)
        assert repo.get_category_by_id(cid) is None

    def test_delete_category_reassigns_parts(self, repo):
        """Deleting a category reassigns its parts to another."""
        cid_old = repo.create_category(Category(name="Old Cat"))
        cid_new = repo.create_category(Category(name="New Cat"))

        part = Part(
            part_number="CAT-TEST-001", name="Cat Part",
            quantity=1, category_id=cid_old,
        )
        pid = repo.create_part(part)

        repo.delete_category(cid_old, reassign_to=cid_new)

        p = repo.get_part_by_id(pid)
        assert p.category_id == cid_new

    def test_get_category_part_count(self, repo):
        cid = repo.create_category(Category(name="Count Cat"))
        for i in range(3):
            repo.create_part(Part(
                part_number=f"CPC-{i}", name=f"Part {i}",
                quantity=1, category_id=cid,
            ))
        assert repo.get_category_part_count(cid) == 3

    def test_get_category_part_count_empty(self, repo):
        cid = repo.create_category(Category(name="Empty Cat"))
        assert repo.get_category_part_count(cid) == 0


class TestPartsByCategory:
    """Test retrieving parts filtered by category."""

    def test_get_parts_by_category(self, repo):
        cid = repo.create_category(Category(name="Filter Cat"))
        for i in range(2):
            repo.create_part(Part(
                part_number=f"FLT-{i}", name=f"Filter Part {i}",
                quantity=5, category_id=cid,
            ))
        parts = repo.get_parts_by_category(cid)
        assert len(parts) == 2
        assert all(p.category_id == cid for p in parts)

    def test_get_parts_by_category_empty(self, repo):
        cid = repo.create_category(Category(name="No Parts Cat"))
        parts = repo.get_parts_by_category(cid)
        assert len(parts) == 0


class TestGetAllParts:
    """Test getting all parts from the repository."""

    def test_get_all_parts(self, repo):
        """get_all_parts returns created parts."""
        cid = repo.get_all_categories()[0].id
        for i in range(3):
            repo.create_part(Part(
                part_number=f"ALL-{i}", name=f"All Part {i}",
                quantity=10, category_id=cid,
            ))
        parts = repo.get_all_parts()
        pns = {p.part_number for p in parts}
        assert "ALL-0" in pns
        assert "ALL-1" in pns
        assert "ALL-2" in pns
