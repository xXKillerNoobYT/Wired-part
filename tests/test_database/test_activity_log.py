"""Tests for the activity log system (v12)."""

import pytest

from wired_part.database.connection import DatabaseConnection
from wired_part.database.models import ActivityLogEntry
from wired_part.database.repository import Repository
from wired_part.database.schema import initialize_database


@pytest.fixture
def repo(tmp_path):
    db = DatabaseConnection(str(tmp_path / "activity.db"))
    initialize_database(db)
    return Repository(db)


@pytest.fixture
def user(repo):
    from wired_part.database.models import User
    u = User(
        username="testuser",
        display_name="Test User",
        pin_hash=Repository.hash_pin("1234"),
    )
    u.id = repo.create_user(u)
    return u


class TestLogActivity:
    def test_log_activity_returns_id(self, repo, user):
        entry_id = repo.log_activity(
            user_id=user.id,
            action="created",
            entity_type="job",
            entity_id=1,
            entity_label="Job #001 - Test",
            details='{"status": "active"}',
        )
        assert entry_id is not None
        assert entry_id > 0

    def test_log_activity_system_action(self, repo):
        """System actions have no user_id."""
        entry_id = repo.log_activity(
            user_id=None,
            action="updated",
            entity_type="part",
            entity_id=5,
            entity_label="WIRE-12-2",
        )
        assert entry_id > 0

    def test_log_activity_minimal(self, repo, user):
        entry_id = repo.log_activity(
            user_id=user.id,
            action="deleted",
            entity_type="truck",
        )
        assert entry_id > 0


class TestGetActivityLog:
    def test_get_all(self, repo, user):
        repo.log_activity(user.id, "created", "job", 1, "Job #1")
        repo.log_activity(user.id, "updated", "job", 1, "Job #1")
        repo.log_activity(user.id, "created", "part", 2, "Part X")

        entries = repo.get_activity_log()
        assert len(entries) == 3
        assert all(isinstance(e, ActivityLogEntry) for e in entries)

    def test_filter_by_entity_type(self, repo, user):
        repo.log_activity(user.id, "created", "job", 1)
        repo.log_activity(user.id, "created", "part", 2)

        job_entries = repo.get_activity_log(entity_type="job")
        assert len(job_entries) == 1
        assert job_entries[0].entity_type == "job"

    def test_filter_by_entity_id(self, repo, user):
        repo.log_activity(user.id, "created", "job", 1)
        repo.log_activity(user.id, "updated", "job", 1)
        repo.log_activity(user.id, "created", "job", 2)

        entries = repo.get_activity_log(entity_type="job", entity_id=1)
        assert len(entries) == 2

    def test_filter_by_user(self, repo, user):
        from wired_part.database.models import User
        other = User(
            username="other", display_name="Other", pin_hash="x",
        )
        other.id = repo.create_user(other)

        repo.log_activity(user.id, "created", "job", 1)
        repo.log_activity(other.id, "created", "job", 2)

        entries = repo.get_activity_log(user_id=user.id)
        assert len(entries) == 1

    def test_limit(self, repo, user):
        for i in range(10):
            repo.log_activity(user.id, "created", "job", i)

        entries = repo.get_activity_log(limit=5)
        assert len(entries) == 5

    def test_entries_have_user_name(self, repo, user):
        repo.log_activity(user.id, "created", "job", 1)
        entries = repo.get_activity_log()
        assert entries[0].user_name == "Test User"

    def test_order_descending(self, repo, user):
        repo.log_activity(user.id, "created", "job", 1, "First")
        repo.log_activity(user.id, "created", "job", 2, "Second")

        entries = repo.get_activity_log()
        assert entries[0].entity_label == "Second"
        assert entries[1].entity_label == "First"


class TestRecentActivity:
    def test_get_recent(self, repo, user):
        for i in range(25):
            repo.log_activity(user.id, "created", "job", i)

        recent = repo.get_recent_activity(limit=10)
        assert len(recent) == 10


class TestEntityActivity:
    def test_get_entity_activity(self, repo, user):
        repo.log_activity(user.id, "created", "job", 42)
        repo.log_activity(user.id, "updated", "job", 42)
        repo.log_activity(user.id, "created", "job", 99)

        entries = repo.get_entity_activity("job", 42)
        assert len(entries) == 2
        assert all(e.entity_id == 42 for e in entries)
