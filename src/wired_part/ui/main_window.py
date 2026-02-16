"""Main application window with tabbed interface."""

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from wired_part.database.connection import DatabaseConnection
from wired_part.database.models import User
from wired_part.database.repository import Repository
from wired_part.ui.widgets.search_dialog import SearchDialog
from wired_part.ui.widgets.toast_widget import ToastManager
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
        self._setup_global_shortcuts()
        self._update_status_bar()

        # Toast notification manager
        self.toast = ToastManager(self)

        # Auto-refresh notification count every 60 seconds
        self._notif_timer = QTimer(self)
        self._notif_timer.timeout.connect(self._update_status_bar)
        self._notif_timer.start(60_000)

    # ── Helpers ──────────────────────────────────────────────────

    @staticmethod
    def _placeholder(label: str) -> QWidget:
        """Return a placeholder widget for a page that doesn't exist yet."""
        w = QWidget()
        lay = QVBoxLayout(w)
        lbl = QLabel(label)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(lbl)
        return w

    def _setup_ui(self):
        """Build the tabbed central layout with grouped sections.

        Tab layout (8 tabs):
            0: Dashboard
            1: Parts Catalog          (standalone, with internal sub-tabs)
            2: Warehouse              (sub-tabs: Dashboard*, Supplies, Supplier Orders, Trucks, Transfers)
            3: Job Tracking           (sub-tabs: Dashboard*, Job Detail, Job Transfers*, Clock*, Notes*)
            4: Trucks                 (sub-tabs: Dashboard*, Truck Detail, Truck Inventory)
            5: Office                 (sub-tabs: Dashboard*, Billing, Timesheet, Parts Reports, Procurement*)
            6: Agent
            7: Settings

        * = placeholder page (to be built in later phases)
        """
        from wired_part.ui.pages.agent_page import AgentPage
        from wired_part.ui.pages.background_agents_page import BackgroundAgentsPage
        from wired_part.ui.pages.dashboard_page import DashboardPage
        from wired_part.ui.pages.incoming_page import IncomingPage
        from wired_part.ui.pages.jobs_dashboard_page import JobsDashboardPage
        from wired_part.ui.pages.notifications_page import NotificationsPage
        from wired_part.ui.pages.office_dashboard_page import OfficeDashboardPage
        from wired_part.ui.pages.procurement_planner_page import ProcurementPlannerPage
        from wired_part.ui.pages.inventory_page import InventoryPage
        from wired_part.ui.pages.jobs_page import JobsPage
        from wired_part.ui.pages.labor_page import LaborPage
        from wired_part.ui.pages.new_orders_page import NewOrdersPage
        from wired_part.ui.pages.office_page import OfficePage
        from wired_part.ui.pages.order_history_page import OrderHistoryPage
        from wired_part.ui.pages.parts_catalog_page import PartsCatalogPage
        from wired_part.ui.pages.pending_orders_page import PendingOrdersPage
        from wired_part.ui.pages.pending_transfers_page import PendingTransfersPage
        from wired_part.ui.pages.returns_page import ReturnsPage
        from wired_part.ui.pages.settings_page import SettingsPage
        from wired_part.ui.pages.trucks_dashboard_page import TrucksDashboardPage
        from wired_part.ui.pages.trucks_inventory_page import TrucksInventoryPage
        from wired_part.ui.pages.trucks_page import TrucksPage
        from wired_part.ui.pages.warehouse_dashboard_page import WarehouseDashboardPage

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
        self.notif_btn.setObjectName("NotificationButton")
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
        logout_btn.setObjectName("LogoutButton")
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

        # ── Tab 1: Parts Catalog (standalone with internal sub-tabs) ─
        self.parts_catalog_page = PartsCatalogPage(
            self.repo, self.current_user
        )
        self.tabs.addTab(self.parts_catalog_page, "Parts Catalog")

        # ── Tab 2: Warehouse (5 sub-tabs) ────────────────────────
        warehouse_container = QWidget()
        warehouse_layout = QVBoxLayout(warehouse_container)
        warehouse_layout.setContentsMargins(0, 0, 0, 0)
        self.warehouse_tabs = QTabWidget()

        # 2-0: Warehouse Dashboard
        self.warehouse_dashboard = WarehouseDashboardPage(
            self.repo, self.current_user
        )
        self.warehouse_tabs.addTab(self.warehouse_dashboard, "Dashboard")

        # 2-1: Warehouse Supplies
        self.inventory_page = InventoryPage(self.repo, self.current_user)
        self.warehouse_tabs.addTab(self.inventory_page, "Warehouse Supplies")

        # 2-2: Supplier Orders (QComboBox + QStackedWidget)
        supplier_orders_container = QWidget()
        so_layout = QVBoxLayout(supplier_orders_container)
        so_layout.setContentsMargins(4, 4, 4, 4)

        self.supplier_orders_combo = QComboBox()
        self.supplier_orders_combo.addItems([
            "New Order",
            "Pending Orders",
            "Incoming / Receive",
            "Returns & Pickups",
            "Order History",
        ])
        so_layout.addWidget(self.supplier_orders_combo)

        self.supplier_orders_stack = QStackedWidget()
        self.new_orders_page = NewOrdersPage(self.repo, self.current_user)
        self.supplier_orders_stack.addWidget(self.new_orders_page)

        self.pending_orders_page = PendingOrdersPage(
            self.repo, self.current_user
        )
        self.supplier_orders_stack.addWidget(self.pending_orders_page)

        self.incoming_page = IncomingPage(self.repo, self.current_user)
        self.supplier_orders_stack.addWidget(self.incoming_page)

        self.returns_page = ReturnsPage(self.repo, self.current_user)
        self.supplier_orders_stack.addWidget(self.returns_page)

        self.order_history_page = OrderHistoryPage(
            self.repo, self.current_user
        )
        self.supplier_orders_stack.addWidget(self.order_history_page)

        self.supplier_orders_combo.currentIndexChanged.connect(
            self._on_supplier_orders_changed
        )
        so_layout.addWidget(self.supplier_orders_stack)
        self.warehouse_tabs.addTab(
            supplier_orders_container, "Supplier Orders"
        )

        # 2-3: Truck Transfers
        self.pending_transfers_page = PendingTransfersPage(
            self.repo, self.current_user,
        )
        self.warehouse_tabs.addTab(
            self.pending_transfers_page, "Truck Transfers"
        )

        self.warehouse_tabs.currentChanged.connect(self._on_subtab_changed)
        warehouse_layout.addWidget(self.warehouse_tabs)
        self.tabs.addTab(warehouse_container, "Warehouse")

        # ── Tab 3: Job Tracking (5 sub-tabs) ─────────────────────
        jobs_container = QWidget()
        jobs_layout = QVBoxLayout(jobs_container)
        jobs_layout.setContentsMargins(0, 0, 0, 0)
        self.jobs_tabs = QTabWidget()

        # 3-0: Jobs Dashboard
        self.jobs_dashboard = JobsDashboardPage(
            self.repo, self.current_user
        )
        self.jobs_tabs.addTab(self.jobs_dashboard, "Dashboard")

        # 3-1: Job Detail
        self.jobs_page = JobsPage(self.repo, self.current_user)
        self.jobs_tabs.addTab(self.jobs_page, "Job Detail")

        # 3-2: Job Transfers (placeholder)
        self.job_transfers = self._placeholder(
            "Job Transfers — coming soon"
        )
        self.jobs_tabs.addTab(self.job_transfers, "Job Transfers")

        # 3-3: Clock In/Out (placeholder)
        self.clock_placeholder = self._placeholder(
            "Clock In/Out — coming soon"
        )
        self.jobs_tabs.addTab(self.clock_placeholder, "Clock In/Out")

        # 3-4: Job Notes (placeholder)
        self.job_notes = self._placeholder(
            "Job Notes — coming soon"
        )
        self.jobs_tabs.addTab(self.job_notes, "Job Notes")

        self.jobs_tabs.currentChanged.connect(self._on_subtab_changed)
        jobs_layout.addWidget(self.jobs_tabs)
        self.tabs.addTab(jobs_container, "Job Tracking")

        # ── Tab 4: Trucks (3 sub-tabs) ───────────────────────────
        trucks_container = QWidget()
        trucks_layout = QVBoxLayout(trucks_container)
        trucks_layout.setContentsMargins(0, 0, 0, 0)
        self.trucks_tabs = QTabWidget()

        # 4-0: Trucks Dashboard
        self.trucks_dashboard = TrucksDashboardPage(
            self.repo, self.current_user
        )
        self.trucks_tabs.addTab(self.trucks_dashboard, "Dashboard")

        # 4-1: Truck Detail — separate TrucksPage instance
        self.trucks_detail_page = TrucksPage(self.repo, self.current_user)
        self.trucks_tabs.addTab(self.trucks_detail_page, "Truck Detail")

        # 4-2: Truck Inventory
        self.trucks_inventory_page = TrucksInventoryPage(
            self.repo, self.current_user
        )
        self.trucks_tabs.addTab(
            self.trucks_inventory_page, "Truck Inventory"
        )

        self.trucks_tabs.currentChanged.connect(self._on_subtab_changed)
        trucks_layout.addWidget(self.trucks_tabs)
        self.tabs.addTab(trucks_container, "Trucks")

        # ── Tab 5: Office (3 sub-tabs) ───────────────────────────
        office_container = QWidget()
        office_layout = QVBoxLayout(office_container)
        office_layout.setContentsMargins(0, 0, 0, 0)
        self.office_tabs = QTabWidget()

        # 5-0: Office Dashboard
        self.office_dashboard = OfficeDashboardPage(
            self.repo, self.current_user
        )
        self.office_tabs.addTab(self.office_dashboard, "Dashboard")

        # 5-1: Reports (existing OfficePage with its internal sub-tabs)
        self.office_page = OfficePage(self.repo, self.current_user)
        self.office_tabs.addTab(self.office_page, "Reports")

        # 5-2: Procurement Planner
        self.procurement_page = ProcurementPlannerPage(
            self.repo, self.current_user
        )
        self.office_tabs.addTab(
            self.procurement_page, "Procurement Planner"
        )

        self.office_tabs.currentChanged.connect(self._on_subtab_changed)
        office_layout.addWidget(self.office_tabs)
        self.tabs.addTab(office_container, "Office")

        # ── Tab 6: Agent (2 sub-tabs) ──────────────────────────────
        agent_container = QWidget()
        agent_layout = QVBoxLayout(agent_container)
        agent_layout.setContentsMargins(0, 0, 0, 0)
        self.agent_tabs = QTabWidget()

        # 6-0: Agent Chat
        self.agent_page = AgentPage(self.repo)
        self.agent_tabs.addTab(self.agent_page, "Agent Chat")

        # 6-1: Notifications
        self.notifications_page = NotificationsPage(
            self.repo, self.current_user
        )
        self.notifications_page.navigate_requested.connect(
            self._on_notification_navigate
        )
        self.agent_tabs.addTab(self.notifications_page, "Notifications")

        # 6-2: Background Agents
        self.bg_agents_page = BackgroundAgentsPage(self.repo)
        self.agent_tabs.addTab(self.bg_agents_page, "Background Agents")

        self.agent_tabs.currentChanged.connect(self._on_subtab_changed)
        agent_layout.addWidget(self.agent_tabs)
        self.tabs.addTab(agent_container, "Agent")

        # ── Tab 7: Settings ──────────────────────────────────────
        self.settings_page = SettingsPage(self.repo, self.current_user)
        self.tabs.addTab(self.settings_page, "Settings")

        # ── Labor page (used by Job Tracking, kept as attribute) ──
        self.labor_page = LaborPage(self.repo, self.current_user)

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

        # Warehouse sub-tabs (Tab 2)
        perm_map_warehouse = {
            0: "tab_warehouse",     # Dashboard
            1: "tab_warehouse",     # Warehouse Supplies
            2: "tab_orders",        # Supplier Orders
            3: "tab_orders",        # Truck Transfers
        }
        for idx, perm in perm_map_warehouse.items():
            if idx < self.warehouse_tabs.count():
                self.warehouse_tabs.setTabVisible(idx, perm in perms)

        # Job Tracking sub-tabs (Tab 3)
        perm_map_jobs = {
            0: "tab_job_tracking",  # Dashboard
            1: "tab_job_tracking",  # Job Detail
            2: "tab_job_tracking",  # Job Transfers
            3: "tab_job_tracking",  # Clock In/Out
            4: "tab_job_tracking",  # Job Notes
        }
        for idx, perm in perm_map_jobs.items():
            if idx < self.jobs_tabs.count():
                self.jobs_tabs.setTabVisible(idx, perm in perms)

        # Trucks sub-tabs (Tab 4)
        perm_map_trucks = {
            0: "tab_trucks",            # Dashboard
            1: "tab_trucks",            # Truck Detail
            2: "tab_trucks_inventory",  # Truck Inventory
        }
        for idx, perm in perm_map_trucks.items():
            if idx < self.trucks_tabs.count():
                self.trucks_tabs.setTabVisible(idx, perm in perms)

        # Office sub-tabs (Tab 5)
        perm_map_office = {
            0: "tab_office",    # Dashboard
            1: "tab_office",    # Reports
            2: "tab_office",    # Procurement Planner
        }
        for idx, perm in perm_map_office.items():
            if idx < self.office_tabs.count():
                self.office_tabs.setTabVisible(idx, perm in perms)

        # Main tabs visibility
        # Tab 0 = Dashboard (always visible)
        # Tab 1 = Parts Catalog
        self.tabs.setTabVisible(1, "tab_parts_catalog" in perms)

        # Tab 2 = Warehouse
        has_any_warehouse = any(
            p in perms for p in perm_map_warehouse.values()
        )
        self.tabs.setTabVisible(2, has_any_warehouse)

        # Tab 3 = Job Tracking
        has_any_jobs = any(p in perms for p in perm_map_jobs.values())
        self.tabs.setTabVisible(3, has_any_jobs)

        # Tab 4 = Trucks
        has_any_trucks = any(p in perms for p in perm_map_trucks.values())
        self.tabs.setTabVisible(4, has_any_trucks)

        # Tab 5 = Office
        self.tabs.setTabVisible(5, "tab_office" in perms)

        # Agent sub-tabs (Tab 6)
        perm_map_agent = {
            0: "tab_agent",     # Agent Chat
            1: "tab_agent",     # Notifications
            2: "tab_agent",     # Background Agents
        }
        for idx, perm in perm_map_agent.items():
            if idx < self.agent_tabs.count():
                self.agent_tabs.setTabVisible(idx, perm in perms)

        # Tab 6 = Agent
        self.tabs.setTabVisible(6, "tab_agent" in perms)

        # Tab 7 = Settings — always visible (My Settings for everyone)
        self.tabs.setTabVisible(7, True)

        # Update incomplete badge on Parts Catalog tab
        self._update_tab_badges()

    def _setup_background_agents(self):
        """Initialize the background agent manager."""
        from wired_part.agent.background import AgentManager
        self.agent_manager = AgentManager(
            self.repo, self.current_user, parent=self
        )
        # Connect to agent page (keeps reference for compat)
        self.agent_page.set_agent_manager(self.agent_manager)
        # Connect to background agents page for control/monitoring
        self.bg_agents_page.set_agent_manager(self.agent_manager)
        # Refresh notification count when agents create notifications
        self.agent_manager.agent_completed.connect(
            lambda *_: self._update_status_bar()
        )

    def _setup_global_shortcuts(self):
        """Set up application-wide keyboard shortcuts."""
        search_shortcut = QShortcut(QKeySequence("Ctrl+K"), self)
        search_shortcut.activated.connect(self._show_search)

    def _show_search(self):
        """Open the global search dialog."""
        dlg = SearchDialog(self.repo, self)
        dlg.result_selected.connect(self._on_search_result)
        # Center on the main window
        dlg.move(
            self.geometry().center().x() - dlg.width() // 2,
            self.geometry().top() + 100,
        )
        dlg.exec()

    def _on_search_result(self, entity_type: str, entity_id: int):
        """Navigate to a search result."""
        if entity_type == "job":
            self.tabs.setCurrentIndex(3)  # Job Tracking tab
        elif entity_type == "part":
            self.tabs.setCurrentIndex(1)  # Parts Catalog tab
        elif entity_type == "order":
            self.tabs.setCurrentIndex(2)  # Warehouse → Supplier Orders
            self.warehouse_tabs.setCurrentIndex(2)

    def _setup_status_bar(self):
        """Add status bar with clock status, inventory summary, and search hint."""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        self.clock_status_label = QLabel("")
        self.clock_status_label.setObjectName("ClockStatusLabel")
        self.status_label = QLabel("Ready")
        self.parts_count_label = QLabel("Parts: 0")
        self.low_stock_label = QLabel("Low Stock: 0")
        self.notification_label = QLabel("Notifications: 0")
        self.notification_label.setObjectName("NotificationCountLabel")
        self.search_hint_label = QLabel("Ctrl+K: Search")
        self.search_hint_label.setObjectName("SearchHintStatus")
        self.user_label = QLabel(
            f"User: {self.current_user.display_name}"
        )

        self.status_bar.addWidget(self.clock_status_label)
        self.status_bar.addWidget(self.status_label, 1)
        self.status_bar.addPermanentWidget(self.search_hint_label)
        self.status_bar.addPermanentWidget(self.notification_label)
        self.status_bar.addPermanentWidget(self.parts_count_label)
        self.status_bar.addPermanentWidget(self.low_stock_label)
        self.status_bar.addPermanentWidget(self.user_label)

    def _update_status_bar(self):
        """Refresh status bar counts including clock-in status."""
        summary = self.repo.get_inventory_summary()
        total = summary.get("total_parts", 0)
        low = summary.get("low_stock_count", 0)
        self.parts_count_label.setText(f"Parts: {total}")
        self.low_stock_label.setText(f"Low Stock: {low}")

        # Update clock-in status
        active = self.repo.get_active_clock_in(self.current_user.id)
        if active:
            job_label = active.job_number or f"Job #{active.job_id}"
            start = ""
            if active.start_time:
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(str(active.start_time))
                    start = dt.strftime(" since %I:%M %p")
                except (ValueError, TypeError):
                    pass
            self.clock_status_label.setText(
                f"Clocked in: {job_label}{start}"
            )
            self.clock_status_label.setProperty("active", True)
        else:
            self.clock_status_label.setText("")
            self.clock_status_label.setProperty("active", False)
        self.clock_status_label.style().polish(self.clock_status_label)

        unread = self.repo.get_unread_count(self.current_user.id)
        if unread > 0:
            self.notification_label.setText(f"Notifications: {unread}")
            self.notification_label.setProperty("alert", True)
            self.notif_btn.setText(f"Notifications ({unread})")
            self.notif_btn.setProperty("alert", True)
        else:
            self.notification_label.setText("Notifications: 0")
            self.notification_label.setProperty("alert", False)
            self.notif_btn.setText("Notifications (0)")
            self.notif_btn.setProperty("alert", False)
        self.notification_label.style().polish(self.notification_label)
        self.notif_btn.style().polish(self.notif_btn)

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
            self.warehouse_tabs, self.jobs_tabs,
            self.trucks_tabs, self.office_tabs,
            self.agent_tabs,
        ):
            if sub_tabs.parent() == widget:
                sub_widget = sub_tabs.currentWidget()
                if hasattr(sub_widget, "refresh"):
                    sub_widget.refresh()
        # Also refresh supplier orders stacked widget if visible
        if index == 2 and self.warehouse_tabs.currentIndex() == 2:
            current_order_page = self.supplier_orders_stack.currentWidget()
            if hasattr(current_order_page, "refresh"):
                current_order_page.refresh()
        self._update_status_bar()
        self._update_tab_badges()

    def _on_subtab_changed(self, index: int):
        """Refresh the active sub-tab's data."""
        sender = self.sender()
        if isinstance(sender, QTabWidget):
            widget = sender.widget(index)
            if hasattr(widget, "refresh"):
                widget.refresh()

    def _on_supplier_orders_changed(self, index: int):
        """Switch the supplier orders stacked widget and refresh."""
        self.supplier_orders_stack.setCurrentIndex(index)
        widget = self.supplier_orders_stack.currentWidget()
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
                font = item.font()
                font.setBold(True)
                item.setFont(font)
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
            "warehouse": 2,
            "orders": 2,
            "job_tracking": 3,
            "trucks": 4,
            "office": 5,
            "agent": 6,
            "settings": 7,
        }
        tab_idx = tab_map.get(notif.target_tab)
        if tab_idx is not None:
            self.tabs.setCurrentIndex(tab_idx)

    def _on_notification_navigate(self, target_tab: str, entity_id: int):
        """Navigate to a tab from the full Notifications page."""
        tab_map = {
            "dashboard": 0,
            "parts_catalog": 1,
            "warehouse": 2,
            "orders": 2,
            "job_tracking": 3,
            "trucks": 4,
            "office": 5,
            "agent": 6,
            "settings": 7,
        }
        tab_idx = tab_map.get(target_tab)
        if tab_idx is not None:
            self.tabs.setCurrentIndex(tab_idx)
        self._update_status_bar()

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
