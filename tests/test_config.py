"""Tests for Config class — settings persistence and retrieval."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch

from wired_part.config import Config, _load_settings, _save_settings


@pytest.fixture
def settings_file(tmp_path):
    """Temporary settings file for isolation."""
    return tmp_path / "settings.json"


@pytest.fixture(autouse=True)
def isolate_config(settings_file, monkeypatch):
    """Redirect settings I/O to temp file so tests don't touch real config."""
    import wired_part.config as config_mod
    monkeypatch.setattr(config_mod, "_SETTINGS_FILE", settings_file)

    # Snapshot all mutable Config attributes before each test
    saved = {
        "BRO_CATEGORIES": Config.BRO_CATEGORIES,
        "NOTEBOOK_SECTIONS_TEMPLATE": Config.NOTEBOOK_SECTIONS_TEMPLATE,
        "APP_THEME": Config.APP_THEME,
        "LM_STUDIO_BASE_URL": Config.LM_STUDIO_BASE_URL,
        "LM_STUDIO_API_KEY": Config.LM_STUDIO_API_KEY,
        "LM_STUDIO_MODEL": Config.LM_STUDIO_MODEL,
        "LM_STUDIO_TIMEOUT": Config.LM_STUDIO_TIMEOUT,
        "AUDIT_AGENT_INTERVAL": Config.AUDIT_AGENT_INTERVAL,
        "ADMIN_AGENT_INTERVAL": Config.ADMIN_AGENT_INTERVAL,
        "REMINDER_AGENT_INTERVAL": Config.REMINDER_AGENT_INTERVAL,
        "GEOFENCE_RADIUS": Config.GEOFENCE_RADIUS,
        "PHOTOS_DIRECTORY": Config.PHOTOS_DIRECTORY,
        "OVERTIME_THRESHOLD": Config.OVERTIME_THRESHOLD,
        "DEFAULT_BILLING_CYCLE": Config.DEFAULT_BILLING_CYCLE,
        "DEFAULT_BILLING_DAY": Config.DEFAULT_BILLING_DAY,
        "TIMESHEET_CYCLE": Config.TIMESHEET_CYCLE,
        "TIMESHEET_DAY": Config.TIMESHEET_DAY,
        "ORDER_NUMBER_PREFIX": Config.ORDER_NUMBER_PREFIX,
        "RA_NUMBER_PREFIX": Config.RA_NUMBER_PREFIX,
        "AUTO_CLOSE_RECEIVED_ORDERS": Config.AUTO_CLOSE_RECEIVED_ORDERS,
    }
    yield
    # Restore all Config attributes after each test
    for attr, val in saved.items():
        setattr(Config, attr, val)


class TestConfigDefaults:
    """Verify default configuration values."""

    def test_app_theme_default(self):
        assert Config.APP_THEME in ("dark", "light")

    def test_geofence_radius_is_float(self):
        assert isinstance(Config.GEOFENCE_RADIUS, float)

    def test_overtime_threshold_default(self):
        assert Config.OVERTIME_THRESHOLD >= 0

    def test_auto_close_default_is_bool(self):
        assert isinstance(Config.AUTO_CLOSE_RECEIVED_ORDERS, bool)

    def test_order_prefix_default(self):
        assert isinstance(Config.ORDER_NUMBER_PREFIX, str)
        assert len(Config.ORDER_NUMBER_PREFIX) >= 1

    def test_ra_prefix_default(self):
        assert isinstance(Config.RA_NUMBER_PREFIX, str)


class TestConfigBROCategories:
    """Test BRO category get/update."""

    def test_get_bro_categories_defaults(self):
        Config.BRO_CATEGORIES = None
        cats = Config.get_bro_categories()
        assert isinstance(cats, list)
        assert len(cats) > 0

    def test_update_bro_categories(self, settings_file):
        Config.update_bro_categories(["T&M", "C", "SERVICE"])
        assert Config.BRO_CATEGORIES == ["T&M", "C", "SERVICE"]

        # Persisted to disk
        data = json.loads(settings_file.read_text(encoding="utf-8"))
        assert data["bro_categories"] == ["T&M", "C", "SERVICE"]

    def test_get_bro_categories_after_update(self):
        Config.update_bro_categories(["A", "B"])
        cats = Config.get_bro_categories()
        assert cats == ["A", "B"]

    def test_bro_returns_copy_not_reference(self):
        Config.update_bro_categories(["X", "Y"])
        cats1 = Config.get_bro_categories()
        cats1.append("Z")
        cats2 = Config.get_bro_categories()
        assert "Z" not in cats2


class TestConfigNotebookSections:
    """Test notebook sections get/update."""

    def test_get_notebook_sections_defaults(self):
        Config.NOTEBOOK_SECTIONS_TEMPLATE = None
        sections = Config.get_notebook_sections()
        assert isinstance(sections, list)
        assert len(sections) > 0

    def test_update_notebook_template(self, settings_file):
        Config.update_notebook_template(["Notes", "Photos", "Materials"])
        assert Config.NOTEBOOK_SECTIONS_TEMPLATE == [
            "Notes", "Photos", "Materials"
        ]

        data = json.loads(settings_file.read_text(encoding="utf-8"))
        assert data["notebook_sections_template"] == [
            "Notes", "Photos", "Materials"
        ]

    def test_get_notebook_sections_after_update(self):
        Config.update_notebook_template(["A", "B"])
        assert Config.get_notebook_sections() == ["A", "B"]


class TestConfigTheme:
    """Test theme update and persistence."""

    def test_update_theme(self, settings_file):
        Config.update_theme("light")
        assert Config.APP_THEME == "light"

        data = json.loads(settings_file.read_text(encoding="utf-8"))
        assert data["app_theme"] == "light"

    def test_update_theme_dark(self, settings_file):
        Config.update_theme("dark")
        assert Config.APP_THEME == "dark"


class TestConfigLLMSettings:
    """Test LLM settings update."""

    def test_update_llm_settings(self, settings_file):
        Config.update_llm_settings(
            base_url="http://test:1234/v1",
            api_key="test-key",
            model="test-model",
            timeout=120,
        )
        assert Config.LM_STUDIO_BASE_URL == "http://test:1234/v1"
        assert Config.LM_STUDIO_API_KEY == "test-key"
        assert Config.LM_STUDIO_MODEL == "test-model"
        assert Config.LM_STUDIO_TIMEOUT == 120

        data = json.loads(settings_file.read_text(encoding="utf-8"))
        assert data["lm_studio_model"] == "test-model"


class TestConfigAgentIntervals:
    """Test agent interval settings."""

    def test_update_agent_intervals(self, settings_file):
        Config.update_agent_intervals(audit=10, admin=20, reminder=5)
        assert Config.AUDIT_AGENT_INTERVAL == 10
        assert Config.ADMIN_AGENT_INTERVAL == 20
        assert Config.REMINDER_AGENT_INTERVAL == 5

        data = json.loads(settings_file.read_text(encoding="utf-8"))
        assert data["audit_agent_interval"] == 10


class TestConfigLaborSettings:
    """Test labor settings update."""

    def test_update_labor_settings(self, settings_file):
        Config.update_labor_settings(
            radius=1.0, photos_dir="/tmp/photos", overtime=10.0,
        )
        assert Config.GEOFENCE_RADIUS == 1.0
        assert Config.PHOTOS_DIRECTORY == "/tmp/photos"
        assert Config.OVERTIME_THRESHOLD == 10.0


class TestConfigBillingSettings:
    """Test billing settings update."""

    def test_update_billing_settings(self, settings_file):
        Config.update_billing_settings(cycle="biweekly", day=15)
        assert Config.DEFAULT_BILLING_CYCLE == "biweekly"
        assert Config.DEFAULT_BILLING_DAY == 15

    def test_update_timesheet_settings(self, settings_file):
        Config.update_timesheet_settings(cycle="monthly", day=1)
        assert Config.TIMESHEET_CYCLE == "monthly"
        assert Config.TIMESHEET_DAY == 1


class TestConfigOrderSettings:
    """Test order/return settings update."""

    def test_update_order_settings(self, settings_file):
        Config.update_order_settings(
            po_prefix="WP", ra_prefix="RET", auto_close=False,
        )
        assert Config.ORDER_NUMBER_PREFIX == "WP"
        assert Config.RA_NUMBER_PREFIX == "RET"
        assert Config.AUTO_CLOSE_RECEIVED_ORDERS is False


class TestSettingsFileIO:
    """Test settings file loading and saving."""

    def test_load_nonexistent_returns_empty(self, settings_file):
        # Settings file doesn't exist yet
        assert not settings_file.exists()
        data = _load_settings()
        assert data == {}

    def test_save_and_load_roundtrip(self, settings_file):
        _save_settings({"foo": "bar", "num": 42})
        assert settings_file.exists()
        data = _load_settings()
        assert data["foo"] == "bar"
        assert data["num"] == 42

    def test_corrupt_json_returns_empty(self, settings_file):
        settings_file.write_text("NOT JSON {{{", encoding="utf-8")
        data = _load_settings()
        assert data == {}
