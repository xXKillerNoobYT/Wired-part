"""pytest-qt tests for the BackgroundAgentsPage."""

import pytest
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QGroupBox, QLabel, QPushButton


class TestBackgroundAgentsPage:
    def test_creates_without_crash(self, qtbot, repo):
        from wired_part.ui.pages.background_agents_page import (
            BackgroundAgentsPage,
        )
        page = BackgroundAgentsPage(repo)
        qtbot.addWidget(page)
        assert page is not None

    def test_has_status_labels(self, qtbot, repo):
        from wired_part.ui.pages.background_agents_page import (
            BackgroundAgentsPage,
        )
        page = BackgroundAgentsPage(repo)
        qtbot.addWidget(page)
        assert isinstance(page.audit_status, QLabel)
        assert isinstance(page.admin_status, QLabel)
        assert isinstance(page.reminder_status, QLabel)

    def test_has_toggle_button(self, qtbot, repo):
        from wired_part.ui.pages.background_agents_page import (
            BackgroundAgentsPage,
        )
        page = BackgroundAgentsPage(repo)
        qtbot.addWidget(page)
        assert isinstance(page.bg_toggle_btn, QPushButton)
        assert "Start" in page.bg_toggle_btn.text()

    def test_status_labels_have_object_names(self, qtbot, repo):
        from wired_part.ui.pages.background_agents_page import (
            BackgroundAgentsPage,
        )
        page = BackgroundAgentsPage(repo)
        qtbot.addWidget(page)
        assert page.audit_status.objectName() == "AgentStatusLabel"
        assert page.admin_status.objectName() == "AgentStatusLabel"
        assert page.reminder_status.objectName() == "AgentStatusLabel"

    def test_get_status_label_mapping(self, qtbot, repo):
        from wired_part.ui.pages.background_agents_page import (
            BackgroundAgentsPage,
        )
        page = BackgroundAgentsPage(repo)
        qtbot.addWidget(page)
        assert page._get_status_label("audit_agent") is page.audit_status
        assert page._get_status_label("admin_agent") is page.admin_status
        assert page._get_status_label("reminder_agent") is page.reminder_status
        assert page._get_status_label("unknown") is None

    def test_refresh_without_manager(self, qtbot, repo):
        from wired_part.ui.pages.background_agents_page import (
            BackgroundAgentsPage,
        )
        page = BackgroundAgentsPage(repo)
        qtbot.addWidget(page)
        # Should not crash even without agent manager
        page.refresh()

    def test_error_sets_status_and_tooltip(self, qtbot, repo):
        from wired_part.ui.pages.background_agents_page import (
            BackgroundAgentsPage,
        )
        page = BackgroundAgentsPage(repo)
        qtbot.addWidget(page)
        page._on_bg_agent_error("audit_agent", "Connection refused")
        assert page.audit_status.text() == "Error"
        assert page.audit_status.property("status") == "error"
        assert "Connection refused" in page.audit_status.toolTip()

    def test_error_starts_clear_timer(self, qtbot, repo):
        from wired_part.ui.pages.background_agents_page import (
            BackgroundAgentsPage,
        )
        page = BackgroundAgentsPage(repo)
        qtbot.addWidget(page)
        page._on_bg_agent_error("admin_agent", "Timeout")
        assert "admin_agent" in page._error_timers
        timer = page._error_timers["admin_agent"]
        assert isinstance(timer, QTimer)
        assert timer.isActive()
        assert timer.isSingleShot()

    def test_clear_error_resets_to_idle(self, qtbot, repo):
        from wired_part.ui.pages.background_agents_page import (
            BackgroundAgentsPage,
        )
        page = BackgroundAgentsPage(repo)
        qtbot.addWidget(page)
        # Set error state
        page._on_bg_agent_error("reminder_agent", "Model not loaded")
        assert page.reminder_status.property("status") == "error"
        # Manually trigger clear
        page._clear_error("reminder_agent")
        assert page.reminder_status.text() == "Idle"
        assert page.reminder_status.property("status") == "idle"
        assert page.reminder_status.toolTip() == ""

    def test_done_cancels_error_timer(self, qtbot, repo):
        from wired_part.ui.pages.background_agents_page import (
            BackgroundAgentsPage,
        )
        page = BackgroundAgentsPage(repo)
        qtbot.addWidget(page)
        page._on_bg_agent_error("audit_agent", "Connection error")
        assert "audit_agent" in page._error_timers
        # Agent completes — should cancel the error timer
        page._on_bg_agent_done("audit_agent", "All checks passed")
        assert "audit_agent" not in page._error_timers
        assert page.audit_status.property("status") == "completed"

    def test_status_update_shows_waiting_text(self, qtbot, repo):
        from wired_part.ui.pages.background_agents_page import (
            BackgroundAgentsPage,
        )
        page = BackgroundAgentsPage(repo)
        qtbot.addWidget(page)
        page._on_bg_agent_status(
            "audit_agent", "Waiting for LLM (attempt 2/10)\u2026"
        )
        assert "Waiting for LLM" in page.audit_status.text()
        assert page.audit_status.property("status") == "running"

    def test_clear_error_does_nothing_if_not_error(self, qtbot, repo):
        """_clear_error should not reset if label has moved past error state."""
        from wired_part.ui.pages.background_agents_page import (
            BackgroundAgentsPage,
        )
        page = BackgroundAgentsPage(repo)
        qtbot.addWidget(page)
        # Set to completed (not error)
        page._on_bg_agent_done("admin_agent", "OK")
        page._clear_error("admin_agent")
        # Should stay completed, not go to idle
        assert page.admin_status.property("status") == "completed"
