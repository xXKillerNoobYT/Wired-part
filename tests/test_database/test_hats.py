"""Tests for the hats & permissions system."""

import json
import pytest

from wired_part.database.connection import DatabaseConnection
from wired_part.database.models import Hat, User
from wired_part.database.repository import Repository
from wired_part.database.schema import initialize_database
from wired_part.utils.constants import (
    DEFAULT_HAT_PERMISSIONS,
    FULL_ACCESS_HATS,
    HAT_NAMES,
    LOCKED_HAT_IDS,
    PERMISSION_KEYS,
)

# Convenience aliases for the new hat names
ADMIN_HAT = "Admin / CEO / Owner"
IT_HAT = "IT / Tech Junkie"
OFFICE_HAT = "Office / HR"


@pytest.fixture
def repo(tmp_path):
    db_path = tmp_path / "test.db"
    db = DatabaseConnection(str(db_path))
    initialize_database(db)
    return Repository(db)


@pytest.fixture
def admin_user(repo):
    user = User(
        username="admin1",
        display_name="Admin User",
        pin_hash=Repository.hash_pin("1234"),
        role="admin",
    )
    user.id = repo.create_user(user)
    # Assign Admin hat
    admin_hat = repo.get_hat_by_name(ADMIN_HAT)
    repo.assign_hat(user.id, admin_hat.id)
    return user


@pytest.fixture
def regular_user(repo):
    user = User(
        username="worker1",
        display_name="Regular Worker",
        pin_hash=Repository.hash_pin("5678"),
        role="user",
    )
    user.id = repo.create_user(user)
    # Assign Worker hat
    worker_hat = repo.get_hat_by_name("Worker")
    repo.assign_hat(user.id, worker_hat.id)
    return user


class TestHatSeeding:
    """Test that default hats are created during DB initialization."""

    def test_default_hats_exist(self, repo):
        hats = repo.get_all_hats()
        hat_names = [h.name for h in hats]
        for name in HAT_NAMES:
            assert name in hat_names, f"Hat '{name}' not seeded"

    def test_default_hat_count(self, repo):
        hats = repo.get_all_hats()
        assert len(hats) == len(HAT_NAMES)

    def test_admin_hat_has_all_permissions(self, repo):
        admin_hat = repo.get_hat_by_name(ADMIN_HAT)
        assert admin_hat is not None
        perms = admin_hat.permission_list
        assert set(perms) == set(PERMISSION_KEYS)

    def test_it_hat_has_all_permissions(self, repo):
        it_hat = repo.get_hat_by_name(IT_HAT)
        assert it_hat is not None
        perms = it_hat.permission_list
        assert set(perms) == set(PERMISSION_KEYS)

    def test_grunt_hat_has_minimal_permissions(self, repo):
        grunt_hat = repo.get_hat_by_name("Grunt")
        assert grunt_hat is not None
        perms = grunt_hat.permission_list
        expected = DEFAULT_HAT_PERMISSIONS["Grunt"]
        assert set(perms) == set(expected)


class TestHatCRUD:
    """Test hat CRUD operations."""

    def test_get_hat_by_name(self, repo):
        hat = repo.get_hat_by_name(ADMIN_HAT)
        assert hat is not None
        assert hat.name == ADMIN_HAT
        assert hat.is_system == 1

    def test_get_hat_by_id(self, repo):
        admin = repo.get_hat_by_name(ADMIN_HAT)
        hat = repo.get_hat_by_id(admin.id)
        assert hat is not None
        assert hat.name == ADMIN_HAT

    def test_update_hat_permissions(self, repo):
        worker_hat = repo.get_hat_by_name("Worker")
        new_perms = ["tab_dashboard", "labor_clock_in"]
        repo.update_hat_permissions(worker_hat.id, new_perms)

        updated = repo.get_hat_by_id(worker_hat.id)
        assert set(updated.permission_list) == set(new_perms)

    def test_create_custom_hat(self, repo):
        hat = Hat(
            name="Intern",
            permissions=json.dumps(["tab_dashboard"]),
            is_system=0,
        )
        hat_id = repo.create_hat(hat)
        assert hat_id > 0

        fetched = repo.get_hat_by_name("Intern")
        assert fetched is not None
        assert fetched.is_system == 0
        assert fetched.permission_list == ["tab_dashboard"]

    def test_rename_hat(self, repo):
        """Renaming a hat works for any hat."""
        worker_hat = repo.get_hat_by_name("Worker")
        repo.rename_hat(worker_hat.id, "Field Worker")
        renamed = repo.get_hat_by_id(worker_hat.id)
        assert renamed.name == "Field Worker"

    def test_rename_locked_hat_allowed(self, repo):
        """Locked hats can still be renamed."""
        admin_hat = repo.get_hat_by_name(ADMIN_HAT)
        assert admin_hat.id in LOCKED_HAT_IDS
        repo.rename_hat(admin_hat.id, "Big Boss")
        renamed = repo.get_hat_by_id(admin_hat.id)
        assert renamed.name == "Big Boss"


class TestLockedHats:
    """Test that locked hats are protected from permission/deletion changes."""

    def test_locked_hat_ids_exist(self, repo):
        """All locked hat IDs should correspond to existing hats."""
        for hat_id in LOCKED_HAT_IDS:
            hat = repo.get_hat_by_id(hat_id)
            assert hat is not None, f"Locked hat ID {hat_id} not found"

    def test_cannot_delete_locked_hat(self, repo):
        admin_hat = repo.get_hat_by_name(ADMIN_HAT)
        with pytest.raises(ValueError, match="locked"):
            repo.delete_hat(admin_hat.id)

    def test_cannot_delete_it_hat(self, repo):
        it_hat = repo.get_hat_by_name(IT_HAT)
        with pytest.raises(ValueError, match="locked"):
            repo.delete_hat(it_hat.id)

    def test_cannot_delete_office_hat(self, repo):
        office_hat = repo.get_hat_by_name(OFFICE_HAT)
        with pytest.raises(ValueError, match="locked"):
            repo.delete_hat(office_hat.id)

    def test_cannot_edit_locked_hat_permissions(self, repo):
        admin_hat = repo.get_hat_by_name(ADMIN_HAT)
        with pytest.raises(ValueError, match="locked"):
            repo.update_hat_permissions(admin_hat.id, ["tab_dashboard"])

    def test_cannot_edit_office_hat_permissions(self, repo):
        office_hat = repo.get_hat_by_name(OFFICE_HAT)
        with pytest.raises(ValueError, match="locked"):
            repo.update_hat_permissions(office_hat.id, ["tab_dashboard"])

    def test_can_delete_custom_hat(self, repo):
        """Non-locked hats can be deleted normally."""
        hat = Hat(name="Temp", permissions="[]", is_system=0)
        hat_id = repo.create_hat(hat)
        repo.delete_hat(hat_id)  # Should not raise
        assert repo.get_hat_by_id(hat_id) is None

    def test_can_edit_non_locked_hat_permissions(self, repo):
        """Non-locked system hats can have permissions edited."""
        worker_hat = repo.get_hat_by_name("Worker")
        assert worker_hat.id not in LOCKED_HAT_IDS
        repo.update_hat_permissions(
            worker_hat.id, ["tab_dashboard", "labor_clock_in"]
        )
        updated = repo.get_hat_by_id(worker_hat.id)
        assert "tab_dashboard" in updated.permission_list

    def test_only_three_hats_are_locked(self, repo):
        """Only IDs 1, 2, 3 are locked. No others."""
        assert LOCKED_HAT_IDS == {1, 2, 3}


class TestUserHatAssignment:
    """Test assigning hats to users."""

    def test_assign_hat(self, repo, admin_user):
        hats = repo.get_user_hats(admin_user.id)
        assert len(hats) == 1
        assert hats[0].hat_name == ADMIN_HAT

    def test_get_user_hat_names(self, repo, admin_user):
        names = repo.get_user_hat_names(admin_user.id)
        assert names == [ADMIN_HAT]

    def test_assign_multiple_hats(self, repo, admin_user):
        it_hat = repo.get_hat_by_name(IT_HAT)
        repo.assign_hat(admin_user.id, it_hat.id)

        names = repo.get_user_hat_names(admin_user.id)
        assert ADMIN_HAT in names
        assert IT_HAT in names

    def test_remove_hat(self, repo, regular_user):
        worker_hat = repo.get_hat_by_name("Worker")
        repo.remove_hat(regular_user.id, worker_hat.id)

        names = repo.get_user_hat_names(regular_user.id)
        assert len(names) == 0

    def test_set_user_hats_replaces_all(self, repo, admin_user):
        foreman_hat = repo.get_hat_by_name("Foreman")
        worker_hat = repo.get_hat_by_name("Worker")

        repo.set_user_hats(
            admin_user.id,
            [foreman_hat.id, worker_hat.id],
        )

        names = repo.get_user_hat_names(admin_user.id)
        assert set(names) == {"Foreman", "Worker"}

    def test_duplicate_assignment_ignored(self, repo, admin_user):
        admin_hat = repo.get_hat_by_name(ADMIN_HAT)
        repo.assign_hat(admin_user.id, admin_hat.id)  # Already has it

        hats = repo.get_user_hats(admin_user.id)
        assert len(hats) == 1  # Still just one


class TestPermissions:
    """Test effective permissions calculation."""

    def test_admin_has_all_permissions(self, repo, admin_user):
        perms = repo.get_user_permissions(admin_user.id)
        assert perms == set(PERMISSION_KEYS)

    def test_worker_has_limited_permissions(self, repo, regular_user):
        perms = repo.get_user_permissions(regular_user.id)
        expected = set(DEFAULT_HAT_PERMISSIONS["Worker"])
        assert perms == expected

    def test_user_has_permission(self, repo, admin_user):
        assert repo.user_has_permission(admin_user.id, "tab_dashboard")
        assert repo.user_has_permission(admin_user.id, "settings_hats")

    def test_worker_lacks_settings_permission(self, repo, regular_user):
        assert not repo.user_has_permission(
            regular_user.id, "settings_users"
        )
        assert not repo.user_has_permission(
            regular_user.id, "tab_settings"
        )

    def test_multiple_hats_union_permissions(self, repo):
        user = User(
            username="multi",
            display_name="Multi Hat",
            pin_hash=Repository.hash_pin("9999"),
            role="user",
        )
        user.id = repo.create_user(user)

        worker_hat = repo.get_hat_by_name("Worker")
        foreman_hat = repo.get_hat_by_name("Foreman")
        repo.assign_hat(user.id, worker_hat.id)
        repo.assign_hat(user.id, foreman_hat.id)

        perms = repo.get_user_permissions(user.id)
        worker_perms = set(DEFAULT_HAT_PERMISSIONS["Worker"])
        foreman_perms = set(DEFAULT_HAT_PERMISSIONS["Foreman"])
        expected = worker_perms | foreman_perms
        assert perms == expected

    def test_full_access_hat_check(self, repo, admin_user, regular_user):
        assert repo.user_has_any_full_access_hat(admin_user.id)
        assert not repo.user_has_any_full_access_hat(regular_user.id)

    def test_it_hat_is_full_access(self, repo):
        user = User(
            username="itguy",
            display_name="IT Person",
            pin_hash=Repository.hash_pin("1111"),
            role="user",
        )
        user.id = repo.create_user(user)
        it_hat = repo.get_hat_by_name(IT_HAT)
        repo.assign_hat(user.id, it_hat.id)

        perms = repo.get_user_permissions(user.id)
        assert perms == set(PERMISSION_KEYS)
        assert repo.user_has_any_full_access_hat(user.id)

    def test_no_hats_no_permissions(self, repo):
        user = User(
            username="nohats",
            display_name="No Hats",
            pin_hash=Repository.hash_pin("0000"),
            role="user",
        )
        user.id = repo.create_user(user)

        perms = repo.get_user_permissions(user.id)
        assert perms == set()
