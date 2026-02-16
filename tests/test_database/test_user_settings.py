"""Tests for user_settings table (schema v16) and repository CRUD."""

import json

import pytest

from wired_part.database.models import User, UserSettings
from wired_part.database.repository import Repository
from wired_part.database.schema import SCHEMA_VERSION


@pytest.fixture
def user(repo):
    """Create a user for settings tests."""
    u = User(
        username="settingsuser",
        display_name="Settings User",
        pin_hash=Repository.hash_pin("1234"),
        role="user",
    )
    u.id = repo.create_user(u)
    return u


class TestSchemaVersion:
    """Ensure schema was bumped to v17."""

    def test_schema_version_is_17(self):
        assert SCHEMA_VERSION == 17

    def test_user_settings_table_exists(self, repo):
        rows = repo.db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='user_settings'",
        )
        assert len(rows) == 1


class TestUserSettingsModel:
    """Test the UserSettings dataclass and its helpers."""

    def test_defaults(self):
        s = UserSettings()
        assert s.theme == "dark"
        assert s.font_size == 10
        assert s.compact_mode == 0
        assert s.sidebar_collapsed == 0
        assert s.default_truck_filter == "mine"
        assert s.preferred_date_range == "This Period"

    def test_dashboard_card_list_empty(self):
        s = UserSettings(dashboard_cards="[]")
        assert s.dashboard_card_list == []

    def test_dashboard_card_list_populated(self):
        s = UserSettings(dashboard_cards='["stock","value"]')
        assert s.dashboard_card_list == ["stock", "value"]

    def test_dashboard_card_list_bad_json(self):
        s = UserSettings(dashboard_cards="not-json")
        assert s.dashboard_card_list == []

    def test_mute_list_empty(self):
        s = UserSettings(notification_mute_list="[]")
        assert s.mute_list == []

    def test_mute_list_populated(self):
        s = UserSettings(notification_mute_list='["agent","system"]')
        assert s.mute_list == ["agent", "system"]

    def test_favorite_categories_list(self):
        s = UserSettings(favorite_labor_categories='["Rough-In","Trim"]')
        assert s.favorite_categories_list == ["Rough-In", "Trim"]

    def test_favorite_categories_list_bad_json(self):
        s = UserSettings(favorite_labor_categories="nope")
        assert s.favorite_categories_list == []


class TestUserSettingsCRUD:
    """Test repository get_or_create / update methods."""

    def test_get_or_create_creates_defaults(self, repo, user):
        settings = repo.get_or_create_user_settings(user.id)
        assert isinstance(settings, UserSettings)
        assert settings.user_id == user.id
        assert settings.theme == "dark"
        assert settings.font_size == 10

    def test_get_or_create_returns_existing(self, repo, user):
        s1 = repo.get_or_create_user_settings(user.id)
        s2 = repo.get_or_create_user_settings(user.id)
        assert s1.id == s2.id

    def test_update_theme(self, repo, user):
        repo.get_or_create_user_settings(user.id)
        repo.update_user_settings(user.id, theme="retro")
        s = repo.get_or_create_user_settings(user.id)
        assert s.theme == "retro"

    def test_update_multiple_fields(self, repo, user):
        repo.update_user_settings(
            user.id,
            font_size=14,
            compact_mode=1,
            default_truck_filter="all",
        )
        s = repo.get_or_create_user_settings(user.id)
        assert s.font_size == 14
        assert s.compact_mode == 1
        assert s.default_truck_filter == "all"

    def test_update_dashboard_cards_json(self, repo, user):
        cards = json.dumps(["stock", "value", "orders"])
        repo.update_user_settings(user.id, dashboard_cards=cards)
        s = repo.get_or_create_user_settings(user.id)
        assert s.dashboard_card_list == ["stock", "value", "orders"]

    def test_update_ignores_protected_fields(self, repo, user):
        """id, created_at, updated_at cannot be overwritten via kwargs."""
        s_orig = repo.get_or_create_user_settings(user.id)
        repo.update_user_settings(user.id, id=999)
        s = repo.get_or_create_user_settings(user.id)
        assert s.id == s_orig.id  # id unchanged

    def test_update_empty_kwargs_noop(self, repo, user):
        repo.get_or_create_user_settings(user.id)
        repo.update_user_settings(user.id)  # no kwargs — should not crash

    def test_cascade_delete_user(self, repo, user):
        """Deleting a user should cascade-delete their settings."""
        repo.get_or_create_user_settings(user.id)
        repo.db.execute("DELETE FROM users WHERE id = ?", (user.id,))
        rows = repo.db.execute(
            "SELECT * FROM user_settings WHERE user_id = ?", (user.id,),
        )
        assert len(rows) == 0

    def test_unique_constraint(self, repo, user):
        """Only one settings row per user."""
        repo.get_or_create_user_settings(user.id)
        with pytest.raises(Exception):
            repo.db.execute(
                "INSERT INTO user_settings (user_id) VALUES (?)", (user.id,),
            )

    def test_updated_at_bumps_on_update(self, repo, user):
        repo.get_or_create_user_settings(user.id)
        s1 = repo.get_or_create_user_settings(user.id)
        repo.update_user_settings(user.id, theme="light")
        s2 = repo.get_or_create_user_settings(user.id)
        # updated_at should be >= original
        assert s2.updated_at >= s1.updated_at
