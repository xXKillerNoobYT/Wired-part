"""pytest-qt tests for the NotificationsPage."""

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QTableWidget

from wired_part.database.models import Notification


class TestNotificationsPage:
    def test_creates_without_crash(self, qtbot, repo, admin_user):
        from wired_part.ui.pages.notifications_page import NotificationsPage
        page = NotificationsPage(repo, admin_user)
        qtbot.addWidget(page)
        assert page is not None

    def test_has_filter_combos(self, qtbot, repo, admin_user):
        from wired_part.ui.pages.notifications_page import NotificationsPage
        page = NotificationsPage(repo, admin_user)
        qtbot.addWidget(page)
        assert isinstance(page.severity_combo, QComboBox)
        assert isinstance(page.source_combo, QComboBox)
        assert isinstance(page.status_combo, QComboBox)

    def test_has_table(self, qtbot, repo, admin_user):
        from wired_part.ui.pages.notifications_page import NotificationsPage
        page = NotificationsPage(repo, admin_user)
        qtbot.addWidget(page)
        assert isinstance(page.table, QTableWidget)
        assert page.table.columnCount() == 6

    def test_refresh_empty(self, qtbot, repo, admin_user):
        from wired_part.ui.pages.notifications_page import NotificationsPage
        page = NotificationsPage(repo, admin_user)
        qtbot.addWidget(page)
        page.refresh()
        assert page.table.rowCount() == 0

    def test_refresh_with_data(self, qtbot, repo, admin_user):
        from wired_part.ui.pages.notifications_page import NotificationsPage
        # Create some notifications
        for i in range(3):
            repo.create_notification(Notification(
                user_id=admin_user.id,
                title=f"Test {i}",
                message=f"Msg {i}",
                severity="info",
                source="system",
            ))
        page = NotificationsPage(repo, admin_user)
        qtbot.addWidget(page)
        page.refresh()
        assert page.table.rowCount() == 3

    def test_filter_by_severity(self, qtbot, repo, admin_user):
        from wired_part.ui.pages.notifications_page import NotificationsPage
        repo.create_notification(Notification(
            user_id=admin_user.id, title="Info", message="",
            severity="info", source="system",
        ))
        repo.create_notification(Notification(
            user_id=admin_user.id, title="Warn", message="",
            severity="warning", source="system",
        ))
        page = NotificationsPage(repo, admin_user)
        qtbot.addWidget(page)
        # Filter by warning
        page.severity_combo.setCurrentText("warning")
        assert page.table.rowCount() == 1

    def test_filter_by_status(self, qtbot, repo, admin_user):
        from wired_part.ui.pages.notifications_page import NotificationsPage
        nid = repo.create_notification(Notification(
            user_id=admin_user.id, title="Read one", message="",
            severity="info", source="system",
        ))
        repo.mark_notification_read(nid)
        repo.create_notification(Notification(
            user_id=admin_user.id, title="Unread one", message="",
            severity="info", source="system",
        ))
        page = NotificationsPage(repo, admin_user)
        qtbot.addWidget(page)
        # Filter by Unread
        page.status_combo.setCurrentText("Unread")
        assert page.table.rowCount() == 1

    def test_mark_all_read(self, qtbot, repo, admin_user):
        from wired_part.ui.pages.notifications_page import NotificationsPage
        for i in range(3):
            repo.create_notification(Notification(
                user_id=admin_user.id,
                title=f"Test {i}", message="",
                severity="info", source="system",
            ))
        page = NotificationsPage(repo, admin_user)
        qtbot.addWidget(page)
        page.refresh()
        page._mark_all_read()
        assert repo.get_unread_count(admin_user.id) == 0

    def test_dismiss_selected_marks_read(self, qtbot, repo, admin_user):
        from wired_part.ui.pages.notifications_page import NotificationsPage
        repo.create_notification(Notification(
            user_id=admin_user.id, title="Dismiss me", message="",
            severity="info", source="system",
        ))
        page = NotificationsPage(repo, admin_user)
        qtbot.addWidget(page)
        page.refresh()
        # Select first row
        page.table.selectRow(0)
        page._dismiss_selected()
        assert repo.get_unread_count(admin_user.id) == 0

    def test_navigate_signal_emitted(self, qtbot, repo, admin_user):
        from wired_part.ui.pages.notifications_page import NotificationsPage
        repo.create_notification(Notification(
            user_id=admin_user.id, title="Go to job", message="",
            severity="info", source="system",
            target_tab="job_tracking", target_data="42",
        ))
        page = NotificationsPage(repo, admin_user)
        qtbot.addWidget(page)
        page.refresh()
        # Listen for navigate signal
        signals = []
        page.navigate_requested.connect(
            lambda tab, eid: signals.append((tab, eid))
        )
        page._on_cell_clicked(0, 0)
        assert len(signals) == 1
        assert signals[0] == ("job_tracking", 42)

    def test_table_minimum_height(self, qtbot, repo, admin_user):
        from wired_part.ui.pages.notifications_page import NotificationsPage
        page = NotificationsPage(repo, admin_user)
        qtbot.addWidget(page)
        assert page.table.minimumHeight() >= 90
