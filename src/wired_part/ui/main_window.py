"""Main application window with tabbed interface."""

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QLabel,
    QMainWindow,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from wired_part.database.connection import DatabaseConnection
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

    def __init__(self, db: DatabaseConnection):
        super().__init__()
        self.db = db
        self.repo = Repository(db)

        self.setWindowTitle(APP_NAME)
        self.resize(DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT)
        self.setMinimumSize(MIN_WINDOW_WIDTH, MIN_WINDOW_HEIGHT)

        self._setup_ui()
        self._setup_status_bar()
        self._update_status_bar()

    def _setup_ui(self):
        """Build the tabbed central layout."""
        from wired_part.ui.pages.inventory_page import InventoryPage
        from wired_part.ui.pages.jobs_page import JobsPage
        from wired_part.ui.pages.agent_page import AgentPage

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.inventory_page = InventoryPage(self.repo)
        self.jobs_page = JobsPage(self.repo)
        self.agent_page = AgentPage(self.repo)

        self.tabs.addTab(self.inventory_page, "Inventory")
        self.tabs.addTab(self.jobs_page, "Jobs")
        self.tabs.addTab(self.agent_page, "Agent")

        # Refresh data when switching tabs
        self.tabs.currentChanged.connect(self._on_tab_changed)

    def _setup_status_bar(self):
        """Add status bar with inventory summary."""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        self.status_label = QLabel("Ready")
        self.parts_count_label = QLabel("Parts: 0")
        self.low_stock_label = QLabel("Low Stock: 0")
        self.db_label = QLabel("DB: local")

        self.status_bar.addWidget(self.status_label, 1)
        self.status_bar.addPermanentWidget(self.parts_count_label)
        self.status_bar.addPermanentWidget(self.low_stock_label)
        self.status_bar.addPermanentWidget(self.db_label)

    def _update_status_bar(self):
        """Refresh status bar counts."""
        summary = self.repo.get_inventory_summary()
        total = summary.get("total_parts", 0)
        low = summary.get("low_stock_count", 0)
        self.parts_count_label.setText(f"Parts: {total}")
        self.low_stock_label.setText(f"Low Stock: {low}")

    def _on_tab_changed(self, index: int):
        """Refresh the active tab's data."""
        widget = self.tabs.widget(index)
        if hasattr(widget, "refresh"):
            widget.refresh()
        self._update_status_bar()
