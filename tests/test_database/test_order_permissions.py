"""Tests for order-related permissions across hats."""

import pytest

from wired_part.database.connection import DatabaseConnection
from wired_part.database.models import User
from wired_part.database.repository import Repository
from wired_part.database.schema import initialize_database
from wired_part.utils.constants import PERMISSION_KEYS


@pytest.fixture
def repo(tmp_path):
    db_path = tmp_path / "test.db"
    db = DatabaseConnection(str(db_path))
    initialize_database(db)
    return Repository(db)


def _create_user_with_hat(repo, username, hat_name):
    """Helper to create a user and assign a hat."""
    user = User(
        username=username,
        display_name=username.title(),
        pin_hash=Repository.hash_pin("1234"),
        role="user",
    )
    user.id = repo.create_user(user)
    hat = repo.get_hat_by_name(hat_name)
    repo.assign_hat(user.id, hat.id)
    return user


class TestOrderPermissions:
    """Test that order permissions are correctly assigned to hats."""

    def test_admin_has_all_order_permissions(self, repo):
        user = _create_user_with_hat(repo, "admin1", "Admin")
        perms = repo.get_user_permissions(user.id)
        assert "tab_orders" in perms
        assert "orders_create" in perms
        assert "orders_edit" in perms
        assert "orders_submit" in perms
        assert "orders_receive" in perms
        assert "orders_return" in perms
        assert "orders_history" in perms

    def test_office_has_all_order_permissions(self, repo):
        user = _create_user_with_hat(repo, "office1", "Office")
        perms = repo.get_user_permissions(user.id)
        assert "tab_orders" in perms
        assert "orders_create" in perms
        assert "orders_edit" in perms
        assert "orders_submit" in perms
        assert "orders_receive" in perms
        assert "orders_return" in perms
        assert "orders_history" in perms

    def test_worker_lacks_order_permissions(self, repo):
        user = _create_user_with_hat(repo, "worker1", "Worker")
        perms = repo.get_user_permissions(user.id)
        assert "tab_orders" not in perms
        assert "orders_create" not in perms
        assert "orders_receive" not in perms

    def test_foreman_can_receive(self, repo):
        user = _create_user_with_hat(repo, "foreman1", "Foreman")
        perms = repo.get_user_permissions(user.id)
        assert "tab_orders" in perms
        assert "orders_receive" in perms
        assert "orders_create" not in perms

    def test_job_manager_can_create_and_receive(self, repo):
        user = _create_user_with_hat(repo, "jm1", "Job Manager")
        perms = repo.get_user_permissions(user.id)
        assert "tab_orders" in perms
        assert "orders_create" in perms
        assert "orders_receive" in perms
        assert "orders_history" in perms
        assert "orders_edit" not in perms

    def test_order_permissions_in_global_keys(self, repo):
        """Ensure all order permissions are in the master list."""
        order_perms = [
            "tab_orders", "orders_create", "orders_edit",
            "orders_submit", "orders_receive", "orders_return",
            "orders_history",
        ]
        for perm in order_perms:
            assert perm in PERMISSION_KEYS, f"{perm} not in PERMISSION_KEYS"
