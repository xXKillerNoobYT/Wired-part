"""Main application window with tabbed interface."""

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
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

    logout_requested = Signal()

    def __init__(self, db: DatabaseConnection, current_user: User):
        super().__init__()
        self.db = db
        self.repo = Repository(db)
        self.current_user = current_user

        # Show user's hats in the title bar
        hat_names = self.repo.get_user_hat_names(current_user.id)
        hats_display = ", ".join(hat_names) if hat_names else current_user.role
        self.setWindowTitle(
            f"{APP_NAME} — {current_user.display_name} [{hats_display}]"
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
        """Build the tabbed central layout with grouped sections.

        Tab layout (7 tabs):
            0: Dashboard
            1: Parts Catalog          (standalone)
            2: Job Tracking           (sub-tabs: Jobs, Trucks, Labor)
            3: Warehouse & Trucks     (sub-tabs: Warehouse, Trucks Inv, Jobs Inv)
            4: Orders & Returns       (sub-tabs: Pending, Incoming, Returns, History)
            5: Agent
            6: Settings
        """
        from wired_part.ui.pages.dashboard_page import DashboardPage
        from wired_part.ui.pages.inventory_page import InventoryPage
        from wired_part.ui.pages.parts_catalog_page import PartsCatalogPage
        from wired_part.ui.pages.trucks_inventory_page import TrucksInventoryPage
        from wired_part.ui.pages.jobs_inventory_page import JobsInventoryPage
        from wired_part.ui.pages.truck_inventory_manager_page import TruckInventoryManagerPage
        from wired_part.ui.pages.trucks_page import TrucksPage
        from wired_part.ui.pages.jobs_page import JobsPage
        from wired_part.ui.pages.labor_page import LaborPage
        from wired_part.ui.pages.new_orders_page import NewOrdersPage
        from wired_part.ui.pages.pending_orders_page import PendingOrdersPage
        from wired_part.ui.pages.pending_transfers_page import PendingTransfersPage
        from wired_part.ui.pages.incoming_page import IncomingPage
        from wired_part.ui.pages.returns_page import ReturnsPage
        from wired_part.ui.pages.order_history_page import OrderHistoryPage
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

        logout_btn = QPushButton("Logout")
        logout_btn.setMinimumHeight(28)
        logout_btn.setStyleSheet(
            "color: #f38ba8; font-weight: bold;"
        )
        logout_btn.clicked.connect(self._on_logout)
        toolbar.addWidget(logout_btn)

        central_layout.addLayout(toolbar)

        # Notification panel (hidden by default)
        self.notif_panel = QWidget()
        notif_layout = QVBoxLayout(self.notif_panel)
        notif_layout.setContentsMargins(8, 4, 8, 4)
        self.notif_list = QListWidget()
        self.notif_list.setMaximumHeight(180)
        self.notif_list.itemClicked.connect(self._on_notification_clicked)
        notif_layout.addWidget(self.notif_list)
        self._notification_objects: list = []
        self.notif_panel.setVisible(False)
        central_layout.addWidget(self.notif_panel)

        # Main tabs
        self.tabs = QTabWidget()
        central_layout.addWidget(self.tabs)
        self.setCentralWidget(central)

        # ── Tab 0: Dashboard ─────────────────────────────────────
        self.dashboard_page = DashboardPage(self.repo, self.current_user)
        self.tabs.addTab(self.dashboard_page, "Dashboard")

        # ── Tab 1: Parts Catalog (standalone) ────────────────────
        self.parts_catalog_page = PartsCatalogPage(
            self.repo, self.current_user
        )
        self.tabs.addTab(self.parts_catalog_page, "Parts Catalog")

        # ── Tab 2: Job Tracking (sub-tabs) ───────────────────────
        jobs_container = QWidget()
        jobs_layout = QVBoxLayout(jobs_container)
        jobs_layout.setContentsMargins(0, 0, 0, 0)
        self.jobs_tabs = QTabWidget()

        self.jobs_page = JobsPage(self.repo, self.current_user)
        self.jobs_tabs.addTab(self.jobs_page, "Jobs")

        self.trucks_page = TrucksPage(self.repo, self.current_user)
        self.jobs_tabs.addTab(self.trucks_page, "Trucks")

        self.labor_page = LaborPage(self.repo, self.current_user)
        self.jobs_tabs.addTab(self.labor_page, "Labor Overview")

        self.jobs_tabs.currentChanged.connect(self._on_subtab_changed)
        jobs_layout.addWidget(self.jobs_tabs)
        self.tabs.addTab(jobs_container, "Job Tracking")

        # ── Tab 3: Warehouse & Trucks (sub-tabs) ─────────────────
        warehouse_container = QWidget()
        warehouse_layout = QVBoxLayout(warehouse_container)
        warehouse_layout.setContentsMargins(0, 0, 0, 0)
        self.warehouse_tabs = QTabWidget()

        self.inventory_page = InventoryPage(self.repo)
        self.warehouse_tabs.addTab(self.inventory_page, "Warehouse")

        self.trucks_inventory_page = TrucksInventoryPage(self.repo)
        self.warehouse_tabs.addTab(
            self.trucks_inventory_page, "Trucks Inventory"
        )

        self.jobs_inventory_page = JobsInventoryPage(self.repo)
        self.warehouse_tabs.addTab(
            self.jobs_inventory_page, "Jobs Inventory"
        )

        self.truck_inv_manager_page = TruckInventoryManagerPage(
            self.repo, self.current_user,
        )
        self.warehouse_tabs.addTab(
            self.truck_inv_manager_page, "Truck Stock Manager",
        )

        self.warehouse_tabs.currentChanged.connect(self._on_subtab_changed)
        warehouse_layout.addWidget(self.warehouse_tabs)
        self.tabs.addTab(warehouse_container, "Warehouse & Trucks")

        # ── Tab 4: Orders & Returns (sub-tabs) ───────────────────
        orders_container = QWidget()
        orders_layout = QVBoxLayout(orders_container)
        orders_layout.setContentsMargins(0, 0, 0, 0)
        self.orders_tabs = QTabWidget()

        self.new_orders_page = NewOrdersPage(
            self.repo, self.current_user,
        )
        self.orders_tabs.addTab(self.new_orders_page, "New Order")

        self.pending_transfers_page = PendingTransfersPage(
            self.repo, self.current_user,
        )
        self.orders_tabs.addTab(
            self.pending_transfers_page, "Pending Transfers",
        )

        self.pending_orders_page = PendingOrdersPage(
            self.repo, self.current_user
        )
        self.orders_tabs.addTab(self.pending_orders_page, "Pending Orders")

        self.incoming_page = IncomingPage(self.repo, self.current_user)
        self.orders_tabs.addTab(self.incoming_page, "Incoming / Receive")

        self.returns_page = ReturnsPage(self.repo, self.current_user)
        self.orders_tabs.addTab(self.returns_page, "Returns & Pickups")

        self.order_history_page = OrderHistoryPage(
            self.repo, self.current_user
        )
        self.orders_tabs.addTab(self.order_history_page, "Order History")

        self.orders_tabs.currentChanged.connect(self._on_subtab_changed)
        orders_layout.addWidget(self.orders_tabs)
        self.tabs.addTab(orders_container, "Orders & Returns")

        # ── Tab 5: Agent ─────────────────────────────────────────
        self.agent_page = AgentPage(self.repo)
        self.tabs.addTab(self.agent_page, "Agent")

        # ── Tab 6: Settings ──────────────────────────────────────
        self.settings_page = SettingsPage(self.repo, self.current_user)
        self.tabs.addTab(self.settings_page, "Settings")

        # Refresh data when switching tabs
        self.tabs.currentChanged.connect(self._on_tab_changed)

        # Apply hat-based permissions
        self._apply_permissions()

    def _apply_permissions(self):
        """Hide/show tabs based on the current user's hat permissions."""
        perms = self.repo.get_user_permissions(self.current_user.id)

        # Parts Catalog sub-tabs (Tab 1)
        parts_sub = self.parts_catalog_page.sub_tabs
        perm_map_parts = {
            0: "tab_parts_catalog",  # Catalog
            1: "parts_brands",       # Brand Management
            2: "parts_qr_tags",      # Tag Maker
        }
        for idx, perm in perm_map_parts.items():
            if idx < parts_sub.count():
                parts_sub.setTabVisible(idx, perm in perms)

        # Job Tracking sub-tabs (Tab 2)
        perm_map_jobs = {
            0: "tab_job_tracking",  # Jobs
            1: "tab_trucks",       # Trucks
            2: "tab_labor",        # Labor Overview
        }
        for idx, perm in perm_map_jobs.items():
            if idx < self.jobs_tabs.count():
                self.jobs_tabs.setTabVisible(idx, perm in perms)

        # Warehouse & Trucks sub-tabs (Tab 3)
        perm_map_warehouse = {
            0: "tab_warehouse",         # Warehouse
            1: "tab_trucks_inventory",  # Trucks Inventory
            2: "tab_jobs_inventory",    # Jobs Inventory
            3: "tab_trucks_inventory",  # Truck Stock Manager (same perm)
        }
        for idx, perm in perm_map_warehouse.items():
            if idx < self.warehouse_tabs.count():
                self.warehouse_tabs.setTabVisible(idx, perm in perms)

        # Orders & Returns sub-tabs (Tab 4)
        perm_map_orders = {
            0: "orders_create",    # New Order
            1: "tab_orders",       # Pending Transfers
            2: "orders_create",    # Pending Orders (create/manage)
            3: "orders_receive",   # Incoming / Receive
            4: "orders_return",    # Returns & Pickups
            5: "orders_history",   # Order History
        }
        for idx, perm in perm_map_orders.items():
            if idx < self.orders_tabs.count():
                self.orders_tabs.setTabVisible(idx, perm in perms)

        # Main tabs visibility
        # Tab 0 = Dashboard (always visible)
        # Tab 1 = Parts Catalog
        self.tabs.setTabVisible(1, "tab_parts_catalog" in perms)

        # Tab 2 = Job Tracking
        has_any_jobs = any(p in perms for p in perm_map_jobs.values())
        self.tabs.setTabVisible(2, has_any_jobs)

        # Tab 3 = Warehouse & Trucks
        has_any_warehouse = any(
            p in perms for p in perm_map_warehouse.values()
        )
        self.tabs.setTabVisible(3, has_any_warehouse)

        # Tab 4 = Orders & Returns
        self.tabs.setTabVisible(4, "tab_orders" in perms)

        # Tab 5 = Agent
        self.tabs.setTabVisible(5, "tab_agent" in perms)

        # Tab 6 = Settings
        self.tabs.setTabVisible(6, "tab_settings" in perms)

        # Update incomplete badge on Parts Catalog tab
        self._update_tab_badges()

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

    def _update_tab_badges(self):
        """Update tab text with badge counts (e.g. incomplete parts)."""
        try:
            count = self.repo.get_incomplete_parts_count()
            if count > 0:
                self.tabs.setTabText(1, f"Parts Catalog ({count})")
            else:
                self.tabs.setTabText(1, "Parts Catalog")
        except Exception:
            pass

    def _on_tab_changed(self, index: int):
        """Refresh the active tab's data."""
        widget = self.tabs.widget(index)
        if hasattr(widget, "refresh"):
            widget.refresh()
        # For container tabs with sub-tabs, refresh the active sub-tab
        for sub_tabs in (
            self.parts_catalog_page.sub_tabs,
            self.jobs_tabs, self.warehouse_tabs, self.orders_tabs,
        ):
            if sub_tabs.parent() == widget:
                sub_widget = sub_tabs.currentWidget()
                if hasattr(sub_widget, "refresh"):
                    sub_widget.refresh()
        self._update_status_bar()
        self._update_tab_badges()

    def _on_subtab_changed(self, index: int):
        """Refresh the active sub-tab's data."""
        sender = self.sender()
        if isinstance(sender, QTabWidget):
            widget = sender.widget(index)
            if hasattr(widget, "refresh"):
                widget.refresh()

    def _toggle_notifications(self, checked: bool):
        """Show/hide the notifications panel."""
        self.notif_panel.setVisible(checked)
        if checked:
            self._refresh_notifications()

    def _refresh_notifications(self):
        """Load recent notifications into the panel."""
        self.notif_list.clear()
        self._notification_objects = self.repo.get_user_notifications(
            self.current_user.id, limit=20
        )
        for n in self._notification_objects:
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
            item.setData(Qt.UserRole, n.id)
            self.notif_list.addItem(item)

    def _on_notification_clicked(self, item):
        """Navigate to the target tab when a notification is clicked."""
        nid = item.data(Qt.UserRole)
        if nid:
            self.repo.mark_notification_read(nid)
            self._update_status_bar()

        # Find the notification object
        notif = None
        for n in self._notification_objects:
            if n.id == nid:
                notif = n
                break

        if not notif or not notif.target_tab:
            return

        # Tab navigation mapping
        tab_map = {
            "dashboard": 0,
            "parts_catalog": 1,
            "job_tracking": 2,
            "warehouse": 3,
            "orders": 4,
            "agent": 5,
            "settings": 6,
        }
        tab_idx = tab_map.get(notif.target_tab)
        if tab_idx is not None:
            self.tabs.setCurrentIndex(tab_idx)

    def _mark_all_read(self):
        """Mark all notifications as read."""
        self.repo.mark_all_notifications_read(self.current_user.id)
        self._update_status_bar()
        if self.notif_panel.isVisible():
            self._refresh_notifications()

    def _on_logout(self):
        """Confirm and trigger logout."""
        reply = QMessageBox.question(
            self, "Logout",
            f"Logout as {self.current_user.display_name}?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self._notif_timer.stop()
            self.logout_requested.emit()
            self.close()
