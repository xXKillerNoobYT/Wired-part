"""Main application window with tabbed interface."""

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from wired_part.database.connection import DatabaseConnection
from wired_part.database.models import User
from wired_part.database.repository import Repository
from wired_part.utils.constants import (
    APP_NAME,
    DEFAULT_WINDOW_HEIGHT,
    DEFAULT_WINDOW_WIDTH,
    MIN_WINDOW_HEIGHT,
    MIN_WINDOW_WIDTH,
)


class MainWindow(QMainWindow):
    """Primary application window."""

    def __init__(self, db: DatabaseConnection, current_user: User):
        super().__init__()
        self.db = db
        self.repo = Repository(db)
        self.current_user = current_user

        self.setWindowTitle(
            f"{APP_NAME} — {current_user.display_name} ({current_user.role})"
        )
        self.resize(DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT)
        self.setMinimumSize(MIN_WINDOW_WIDTH, MIN_WINDOW_HEIGHT)

        self._setup_ui()
        self._setup_status_bar()
        self._setup_background_agents()
        self._update_status_bar()

        # Auto-refresh notification count every 60 seconds
        self._notif_timer = QTimer(self)
        self._notif_timer.timeout.connect(self._update_status_bar)
        self._notif_timer.start(60_000)

    def _setup_ui(self):
        """Build the tabbed central layout."""
        from wired_part.ui.pages.dashboard_page import DashboardPage
        from wired_part.ui.pages.inventory_page import InventoryPage
        from wired_part.ui.pages.trucks_page import TrucksPage
        from wired_part.ui.pages.jobs_page import JobsPage
        from wired_part.ui.pages.agent_page import AgentPage
        from wired_part.ui.pages.settings_page import SettingsPage

        # Central container with toolbar + tabs
        central = QWidget()
        central_layout = QVBoxLayout(central)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)

        # Top toolbar with notification bell
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(8, 4, 8, 4)
        toolbar.addStretch()

        self.notif_btn = QPushButton("Notifications (0)")
        self.notif_btn.setMinimumHeight(28)
        self.notif_btn.setCheckable(True)
        self.notif_btn.clicked.connect(self._toggle_notifications)
        toolbar.addWidget(self.notif_btn)

        mark_read_btn = QPushButton("Mark All Read")
        mark_read_btn.setMinimumHeight(28)
        mark_read_btn.clicked.connect(self._mark_all_read)
        toolbar.addWidget(mark_read_btn)

        central_layout.addLayout(toolbar)

        # Notification panel (hidden by default)
        self.notif_panel = QWidget()
        notif_layout = QVBoxLayout(self.notif_panel)
        notif_layout.setContentsMargins(8, 4, 8, 4)
        self.notif_list = QListWidget()
        self.notif_list.setMaximumHeight(180)
        notif_layout.addWidget(self.notif_list)
        self.notif_panel.setVisible(False)
        central_layout.addWidget(self.notif_panel)

        # Tabs
        self.tabs = QTabWidget()
        central_layout.addWidget(self.tabs)
        self.setCentralWidget(central)

        self.dashboard_page = DashboardPage(self.repo, self.current_user)
        self.inventory_page = InventoryPage(self.repo)
        self.trucks_page = TrucksPage(self.repo, self.current_user)
        self.jobs_page = JobsPage(self.repo, self.current_user)
        self.agent_page = AgentPage(self.repo)
        self.settings_page = SettingsPage(self.repo, self.current_user)

        self.tabs.addTab(self.dashboard_page, "Dashboard")
        self.tabs.addTab(self.inventory_page, "Inventory")
        self.tabs.addTab(self.trucks_page, "Trucks")
        self.tabs.addTab(self.jobs_page, "Jobs")
        self.tabs.addTab(self.agent_page, "Agent")
        self.tabs.addTab(self.settings_page, "Settings")

        # Refresh data when switching tabs
        self.tabs.currentChanged.connect(self._on_tab_changed)

    def _setup_background_agents(self):
        """Initialize the background agent manager."""
        from wired_part.agent.background import AgentManager
        self.agent_manager = AgentManager(
            self.repo, self.current_user, parent=self
        )
        # Connect to agent page so it can control/monitor agents
        self.agent_page.set_agent_manager(self.agent_manager)
        # Refresh notification count when agents create notifications
        self.agent_manager.agent_completed.connect(
            lambda *_: self._update_status_bar()
        )

    def _setup_status_bar(self):
        """Add status bar with inventory summary and notification count."""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        self.status_label = QLabel("Ready")
        self.parts_count_label = QLabel("Parts: 0")
        self.low_stock_label = QLabel("Low Stock: 0")
        self.notification_label = QLabel("Notifications: 0")
        self.user_label = QLabel(
            f"User: {self.current_user.display_name}"
        )

        self.status_bar.addWidget(self.status_label, 1)
        self.status_bar.addPermanentWidget(self.notification_label)
        self.status_bar.addPermanentWidget(self.parts_count_label)
        self.status_bar.addPermanentWidget(self.low_stock_label)
        self.status_bar.addPermanentWidget(self.user_label)

    def _update_status_bar(self):
        """Refresh status bar counts."""
        summary = self.repo.get_inventory_summary()
        total = summary.get("total_parts", 0)
        low = summary.get("low_stock_count", 0)
        self.parts_count_label.setText(f"Parts: {total}")
        self.low_stock_label.setText(f"Low Stock: {low}")

        unread = self.repo.get_unread_count(self.current_user.id)
        if unread > 0:
            self.notification_label.setText(f"Notifications: {unread}")
            self.notification_label.setStyleSheet(
                "color: #f38ba8; font-weight: bold;"
            )
            self.notif_btn.setText(f"Notifications ({unread})")
            self.notif_btn.setStyleSheet(
                "color: #f38ba8; font-weight: bold;"
            )
        else:
            self.notification_label.setText("Notifications: 0")
            self.notification_label.setStyleSheet("")
            self.notif_btn.setText("Notifications (0)")
            self.notif_btn.setStyleSheet("")

    def _on_tab_changed(self, index: int):
        """Refresh the active tab's data."""
        widget = self.tabs.widget(index)
        if hasattr(widget, "refresh"):
            widget.refresh()
        self._update_status_bar()

    def _toggle_notifications(self, checked: bool):
        """Show/hide the notifications panel."""
        self.notif_panel.setVisible(checked)
        if checked:
            self._refresh_notifications()

    def _refresh_notifications(self):
        """Load recent notifications into the panel."""
        self.notif_list.clear()
        notifications = self.repo.get_user_notifications(
            self.current_user.id, limit=20
        )
        for n in notifications:
            prefix = ""
            if n.severity == "warning":
                prefix = "[!] "
            elif n.severity == "critical":
                prefix = "[!!] "
            read_marker = "" if n.is_read else " (new)"
            text = f"{prefix}{n.title}{read_marker}\n{n.message}"
            item = QListWidgetItem(text)
            if not n.is_read:
                item.setBackground(Qt.GlobalColor.darkYellow)
            self.notif_list.addItem(item)

    def _mark_all_read(self):
        """Mark all notifications as read."""
        self.repo.mark_all_notifications_read(self.current_user.id)
        self._update_status_bar()
        if self.notif_panel.isVisible():
            self._refresh_notifications()
