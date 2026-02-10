"""Tests for the user management repository methods."""

import pytest

from wired_part.database.models import User
from wired_part.database.repository import Repository


class TestUserCRUD:
    """Test user creation, authentication, and management."""

    def test_create_user(self, repo):
        user = User(
            username="testuser",
            display_name="Test User",
            pin_hash=Repository.hash_pin("1234"),
            role="user",
            is_active=1,
        )
        user_id = repo.create_user(user)
        assert user_id is not None
        assert user_id > 0

    def test_get_user_by_username(self, repo):
        user = User(
            username="admin",
            display_name="Admin",
            pin_hash=Repository.hash_pin("0000"),
            role="admin",
            is_active=1,
        )
        repo.create_user(user)
        found = repo.get_user_by_username("admin")
        assert found is not None
        assert found.display_name == "Admin"
        assert found.role == "admin"

    def test_authenticate_user_success(self, repo):
        user = User(
            username="worker1",
            display_name="Worker One",
            pin_hash=Repository.hash_pin("5678"),
            role="user",
            is_active=1,
        )
        repo.create_user(user)
        result = repo.authenticate_user("worker1", "5678")
        assert result is not None
        assert result.username == "worker1"

    def test_authenticate_user_wrong_pin(self, repo):
        user = User(
            username="worker2",
            display_name="Worker Two",
            pin_hash=Repository.hash_pin("1111"),
            role="user",
            is_active=1,
        )
        repo.create_user(user)
        result = repo.authenticate_user("worker2", "9999")
        assert result is None

    def test_authenticate_inactive_user(self, repo):
        user = User(
            username="inactive",
            display_name="Inactive",
            pin_hash=Repository.hash_pin("1234"),
            role="user",
            is_active=0,
        )
        repo.create_user(user)
        result = repo.authenticate_user("inactive", "1234")
        assert result is None

    def test_deactivate_user(self, repo):
        user = User(
            username="todeactivate",
            display_name="Deactivate Me",
            pin_hash=Repository.hash_pin("1234"),
            role="user",
            is_active=1,
        )
        uid = repo.create_user(user)
        repo.deactivate_user(uid)
        found = repo.get_user_by_id(uid)
        assert found.is_active == 0

    def test_get_all_users_active_only(self, repo):
        repo.create_user(User(
            username="active1", display_name="Active",
            pin_hash=Repository.hash_pin("1234"),
            role="user", is_active=1,
        ))
        repo.create_user(User(
            username="inactive1", display_name="Inactive",
            pin_hash=Repository.hash_pin("1234"),
            role="user", is_active=0,
        ))
        active = repo.get_all_users(active_only=True)
        all_users = repo.get_all_users(active_only=False)
        assert len(active) == 1
        assert len(all_users) == 2

    def test_user_count(self, repo):
        assert repo.user_count() == 0
        repo.create_user(User(
            username="u1", display_name="U1",
            pin_hash=Repository.hash_pin("1234"),
            role="user", is_active=1,
        ))
        assert repo.user_count() == 1

    def test_hash_pin_deterministic(self):
        h1 = Repository.hash_pin("1234")
        h2 = Repository.hash_pin("1234")
        assert h1 == h2
        assert len(h1) == 64  # SHA-256 hex digest
