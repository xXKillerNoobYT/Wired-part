"""Tests for parts lists and parts list items."""

import pytest

from wired_part.database.models import (
    Job,
    Part,
    PartsList,
    PartsListItem,
    User,
)
from wired_part.database.repository import Repository


@pytest.fixture
def list_data(repo):
    """Create supporting data for parts list tests."""
    # Create a user
    user = User(
        username="listuser", display_name="List User",
        pin_hash=Repository.hash_pin("1234"),
        role="user", is_active=1,
    )
    user_id = repo.create_user(user)

    # Create a job
    job = Job(
        job_number="JOB-LIST-001", name="List Test Job",
        status="active",
    )
    job_id = repo.create_job(job)

    # Create parts
    part1_id = repo.create_part(Part(
        part_number="PL-001", description="12/2 Romex",
        quantity=100, unit_cost=25.0,
    ))
    part2_id = repo.create_part(Part(
        part_number="PL-002", description="3/4 EMT Conduit",
        quantity=50, unit_cost=12.50,
    ))

    return {
        "user_id": user_id,
        "job_id": job_id,
        "part1_id": part1_id,
        "part2_id": part2_id,
    }


class TestPartsListCRUD:
    """Test parts list creation, retrieval, update, and deletion."""

    def test_create_parts_list(self, repo, list_data):
        pl = PartsList(
            name="Kitchen Remodel Parts",
            list_type="specific",
            job_id=list_data["job_id"],
            notes="Parts needed for kitchen",
            created_by=list_data["user_id"],
        )
        lid = repo.create_parts_list(pl)
        assert lid > 0

    def test_get_parts_list_by_id(self, repo, list_data):
        lid = repo.create_parts_list(PartsList(
            name="Test List",
            list_type="general",
            created_by=list_data["user_id"],
        ))
        pl = repo.get_parts_list_by_id(lid)
        assert pl is not None
        assert pl.name == "Test List"
        assert pl.list_type == "general"
        assert pl.created_by_name == "List User"

    def test_get_parts_list_with_job(self, repo, list_data):
        lid = repo.create_parts_list(PartsList(
            name="Job-Specific List",
            list_type="specific",
            job_id=list_data["job_id"],
            created_by=list_data["user_id"],
        ))
        pl = repo.get_parts_list_by_id(lid)
        assert pl.job_number == "JOB-LIST-001"

    def test_get_parts_list_not_found(self, repo):
        pl = repo.get_parts_list_by_id(9999)
        assert pl is None

    def test_get_all_parts_lists(self, repo, list_data):
        repo.create_parts_list(PartsList(
            name="List A", list_type="general",
            created_by=list_data["user_id"],
        ))
        repo.create_parts_list(PartsList(
            name="List B", list_type="specific",
            job_id=list_data["job_id"],
            created_by=list_data["user_id"],
        ))
        all_lists = repo.get_all_parts_lists()
        assert len(all_lists) == 2

    def test_get_all_parts_lists_filtered_by_type(self, repo, list_data):
        repo.create_parts_list(PartsList(
            name="General List", list_type="general",
        ))
        repo.create_parts_list(PartsList(
            name="Fast List", list_type="fast",
        ))
        repo.create_parts_list(PartsList(
            name="Specific List", list_type="specific",
        ))
        general = repo.get_all_parts_lists(list_type="general")
        assert len(general) == 1
        assert general[0].name == "General List"

        fast = repo.get_all_parts_lists(list_type="fast")
        assert len(fast) == 1
        assert fast[0].name == "Fast List"

    def test_update_parts_list(self, repo, list_data):
        lid = repo.create_parts_list(PartsList(
            name="Original", list_type="general",
        ))
        pl = repo.get_parts_list_by_id(lid)
        pl.name = "Updated"
        pl.list_type = "fast"
        pl.notes = "Updated notes"
        repo.update_parts_list(pl)

        updated = repo.get_parts_list_by_id(lid)
        assert updated.name == "Updated"
        assert updated.list_type == "fast"
        assert updated.notes == "Updated notes"

    def test_delete_parts_list(self, repo, list_data):
        lid = repo.create_parts_list(PartsList(
            name="To Delete", list_type="general",
        ))
        assert repo.get_parts_list_by_id(lid) is not None
        repo.delete_parts_list(lid)
        assert repo.get_parts_list_by_id(lid) is None


class TestPartsListItems:
    """Test adding, retrieving, and removing items from parts lists."""

    def test_add_item_to_list(self, repo, list_data):
        lid = repo.create_parts_list(PartsList(
            name="Item Test", list_type="general",
        ))
        item = PartsListItem(
            list_id=lid,
            part_id=list_data["part1_id"],
            quantity=5,
            notes="Need 5 rolls",
        )
        iid = repo.add_item_to_parts_list(item)
        assert iid > 0

    def test_get_parts_list_items(self, repo, list_data):
        lid = repo.create_parts_list(PartsList(
            name="Multi-Item List", list_type="general",
        ))
        repo.add_item_to_parts_list(PartsListItem(
            list_id=lid, part_id=list_data["part1_id"],
            quantity=10,
        ))
        repo.add_item_to_parts_list(PartsListItem(
            list_id=lid, part_id=list_data["part2_id"],
            quantity=20, notes="Extra conduit",
        ))

        items = repo.get_parts_list_items(lid)
        assert len(items) == 2
        # Sorted by part_number
        assert items[0].part_number == "PL-001"
        assert items[0].part_description == "12/2 Romex"
        assert items[0].quantity == 10
        assert items[0].unit_cost == 25.0
        assert items[1].part_number == "PL-002"
        assert items[1].quantity == 20

    def test_remove_item_from_list(self, repo, list_data):
        lid = repo.create_parts_list(PartsList(
            name="Remove Test", list_type="general",
        ))
        iid = repo.add_item_to_parts_list(PartsListItem(
            list_id=lid, part_id=list_data["part1_id"],
            quantity=5,
        ))
        items = repo.get_parts_list_items(lid)
        assert len(items) == 1

        repo.remove_item_from_parts_list(iid)
        items = repo.get_parts_list_items(lid)
        assert len(items) == 0

    def test_delete_list_cascades_items(self, repo, list_data):
        lid = repo.create_parts_list(PartsList(
            name="Cascade Test", list_type="general",
        ))
        repo.add_item_to_parts_list(PartsListItem(
            list_id=lid, part_id=list_data["part1_id"],
            quantity=5,
        ))
        repo.add_item_to_parts_list(PartsListItem(
            list_id=lid, part_id=list_data["part2_id"],
            quantity=10,
        ))
        # Delete the list — items should be cascade-deleted
        repo.delete_parts_list(lid)
        items = repo.get_parts_list_items(lid)
        assert len(items) == 0
