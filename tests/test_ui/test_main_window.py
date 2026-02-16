"""pytest-qt tests for the MainWindow and LoginDialog."""

import json
import pytest
from PySide6.QtWidgets import QComboBox, QStackedWidget, QTabWidget

from wired_part.database.connection import DatabaseConnection
from wired_part.database.models import User
from wired_part.database.repository import Repository
from wired_part.database.schema import initialize_database


@pytest.fixture
def db_and_repo(tmp_path):
    """Return (db, repo) tuple for MainWindow tests."""
    db = DatabaseConnection(str(tmp_path / "main.db"))
    initialize_database(db)
    repo = Repository(db)
    return db, repo


@pytest.fixture
def admin_for_main(db_and_repo):
    db, repo = db_and_repo
    user = User(
        username="admin",
        display_name="Admin User",
        pin_hash=Repository.hash_pin("1234"),
        role="admin",
    )
    user.id = repo.create_user(user)
    admin_hat = repo.get_hat_by_id(1)
    repo.assign_hat(user.id, admin_hat.id)
    return user


class TestMainWindow:
    def test_creates_without_crash(
        self, qtbot, db_and_repo, admin_for_main
    ):
        from wired_part.ui.main_window import MainWindow
        db, _ = db_and_repo
        win = MainWindow(db, current_user=admin_for_main)
        qtbot.addWidget(win)
        assert win is not None

    def test_has_8_tabs(self, qtbot, db_and_repo, admin_for_main):
        from wired_part.ui.main_window import MainWindow
        db, _ = db_and_repo
        win = MainWindow(db, current_user=admin_for_main)
        qtbot.addWidget(win)
        assert isinstance(win.tabs, QTabWidget)
        assert win.tabs.count() == 8
        labels = [win.tabs.tabText(i) for i in range(8)]
        assert labels[0] == "Dashboard"
        assert labels[1] == "Parts Catalog"
        assert labels[2] == "Warehouse"
        assert labels[3] == "Job Tracking"
        assert labels[4] == "Trucks"
        assert labels[5] == "Office"
        assert labels[6] == "Agent"
        assert labels[7] == "Settings"

    def test_window_title_includes_user(
        self, qtbot, db_and_repo, admin_for_main
    ):
        from wired_part.ui.main_window import MainWindow
        db, _ = db_and_repo
        win = MainWindow(db, current_user=admin_for_main)
        qtbot.addWidget(win)
        assert "Admin User" in win.windowTitle()

    def test_has_toast_manager(
        self, qtbot, db_and_repo, admin_for_main
    ):
        from wired_part.ui.main_window import MainWindow
        db, _ = db_and_repo
        win = MainWindow(db, current_user=admin_for_main)
        qtbot.addWidget(win)
        assert win.toast is not None

    def test_has_notification_button(
        self, qtbot, db_and_repo, admin_for_main
    ):
        from wired_part.ui.main_window import MainWindow
        db, _ = db_and_repo
        win = MainWindow(db, current_user=admin_for_main)
        qtbot.addWidget(win)
        assert win.notif_btn is not None

    def test_toolbar_object_names(
        self, qtbot, db_and_repo, admin_for_main
    ):
        """Verify key toolbar widgets have QSS object names."""
        from wired_part.ui.main_window import MainWindow
        db, _ = db_and_repo
        win = MainWindow(db, current_user=admin_for_main)
        qtbot.addWidget(win)
        assert win.notif_btn.objectName() == "NotificationButton"
        assert win.notification_label.objectName() == "NotificationCountLabel"
        assert win.clock_status_label.objectName() == "ClockStatusLabel"
        assert win.search_hint_label.objectName() == "SearchHintStatus"

    def test_warehouse_subtabs(
        self, qtbot, db_and_repo, admin_for_main
    ):
        """Warehouse tab has 4 sub-tabs with correct labels."""
        from wired_part.ui.main_window import MainWindow
        db, _ = db_and_repo
        win = MainWindow(db, current_user=admin_for_main)
        qtbot.addWidget(win)
        wt = win.warehouse_tabs
        assert wt.count() == 4
        assert wt.tabText(0) == "Dashboard"
        assert wt.tabText(1) == "Warehouse Supplies"
        assert wt.tabText(2) == "Supplier Orders"
        assert wt.tabText(3) == "Truck Transfers"

    def test_supplier_orders_combo_stack(
        self, qtbot, db_and_repo, admin_for_main
    ):
        """Supplier Orders uses QComboBox + QStackedWidget with 5 items."""
        from wired_part.ui.main_window import MainWindow
        db, _ = db_and_repo
        win = MainWindow(db, current_user=admin_for_main)
        qtbot.addWidget(win)
        combo = win.supplier_orders_combo
        stack = win.supplier_orders_stack
        assert isinstance(combo, QComboBox)
        assert isinstance(stack, QStackedWidget)
        assert combo.count() == 5
        assert stack.count() == 5
        assert combo.itemText(0) == "New Order"
        assert combo.itemText(4) == "Order History"

    def test_jobs_subtabs(
        self, qtbot, db_and_repo, admin_for_main
    ):
        """Job Tracking tab has 5 sub-tabs."""
        from wired_part.ui.main_window import MainWindow
        db, _ = db_and_repo
        win = MainWindow(db, current_user=admin_for_main)
        qtbot.addWidget(win)
        jt = win.jobs_tabs
        assert jt.count() == 5
        assert jt.tabText(0) == "Dashboard"
        assert jt.tabText(1) == "Job Detail"

    def test_trucks_subtabs(
        self, qtbot, db_and_repo, admin_for_main
    ):
        """Trucks tab has 3 sub-tabs."""
        from wired_part.ui.main_window import MainWindow
        db, _ = db_and_repo
        win = MainWindow(db, current_user=admin_for_main)
        qtbot.addWidget(win)
        tt = win.trucks_tabs
        assert tt.count() == 3
        assert tt.tabText(0) == "Dashboard"
        assert tt.tabText(1) == "Truck Detail"
        assert tt.tabText(2) == "Truck Inventory"

    def test_office_subtabs(
        self, qtbot, db_and_repo, admin_for_main
    ):
        """Office tab has 3 sub-tabs (Dashboard, Reports, Procurement)."""
        from wired_part.ui.main_window import MainWindow
        db, _ = db_and_repo
        win = MainWindow(db, current_user=admin_for_main)
        qtbot.addWidget(win)
        ot = win.office_tabs
        assert ot.count() == 3
        assert ot.tabText(0) == "Dashboard"
        assert ot.tabText(1) == "Reports"
        assert ot.tabText(2) == "Procurement Planner"


    def test_agent_subtabs(
        self, qtbot, db_and_repo, admin_for_main
    ):
        """Agent tab has 3 sub-tabs (Chat, Notifications, Background Agents)."""
        from wired_part.ui.main_window import MainWindow
        db, _ = db_and_repo
        win = MainWindow(db, current_user=admin_for_main)
        qtbot.addWidget(win)
        at = win.agent_tabs
        assert at.count() == 3
        assert at.tabText(0) == "Agent Chat"
        assert at.tabText(1) == "Notifications"
        assert at.tabText(2) == "Background Agents"

    def test_notifications_page_exists(
        self, qtbot, db_and_repo, admin_for_main
    ):
        """MainWindow has a notifications_page attribute."""
        from wired_part.ui.main_window import MainWindow
        db, _ = db_and_repo
        win = MainWindow(db, current_user=admin_for_main)
        qtbot.addWidget(win)
        assert win.notifications_page is not None

    def test_bg_agents_page_exists(
        self, qtbot, db_and_repo, admin_for_main
    ):
        """MainWindow has a bg_agents_page attribute."""
        from wired_part.ui.main_window import MainWindow
        db, _ = db_and_repo
        win = MainWindow(db, current_user=admin_for_main)
        qtbot.addWidget(win)
        assert win.bg_agents_page is not None


class TestLoginDialog:
    def test_creates_without_crash(self, qtbot, db_and_repo):
        from wired_part.ui.login_dialog import LoginDialog
        _, repo = db_and_repo
        dlg = LoginDialog(repo)
        qtbot.addWidget(dlg)
        assert dlg is not None

    def test_shows_users(self, qtbot, db_and_repo, admin_for_main):
        from wired_part.ui.login_dialog import LoginDialog
        _, repo = db_and_repo
        dlg = LoginDialog(repo)
        qtbot.addWidget(dlg)
        # Should show at least one user card
        assert dlg._cards is not None
        assert len(dlg._cards) >= 1

    def test_pin_panel_hidden_initially(
        self, qtbot, db_and_repo, admin_for_main
    ):
        from wired_part.ui.login_dialog import LoginDialog
        _, repo = db_and_repo
        dlg = LoginDialog(repo)
        qtbot.addWidget(dlg)
        assert not dlg.pin_panel.isVisible()

    def test_authenticated_user_none_initially(
        self, qtbot, db_and_repo, admin_for_main
    ):
        from wired_part.ui.login_dialog import LoginDialog
        _, repo = db_and_repo
        dlg = LoginDialog(repo)
        qtbot.addWidget(dlg)
        assert dlg.authenticated_user is None


class TestFirstRunDialog:
    def test_creates_without_crash(self, qtbot, db_and_repo):
        from wired_part.ui.login_dialog import FirstRunDialog
        _, repo = db_and_repo
        dlg = FirstRunDialog(repo)
        qtbot.addWidget(dlg)
        assert dlg is not None

    def test_has_form_fields(self, qtbot, db_and_repo):
        from wired_part.ui.login_dialog import FirstRunDialog
        _, repo = db_and_repo
        dlg = FirstRunDialog(repo)
        qtbot.addWidget(dlg)
        assert dlg.username_input is not None
        assert dlg.display_name_input is not None
        assert dlg.pin_input is not None
        assert dlg.pin_confirm is not None

    def test_created_user_none_initially(self, qtbot, db_and_repo):
        from wired_part.ui.login_dialog import FirstRunDialog
        _, repo = db_and_repo
        dlg = FirstRunDialog(repo)
        qtbot.addWidget(dlg)
        assert dlg.created_user is None
