"""Warehouse Dashboard — summary cards and alerts for warehouse operations."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from wired_part.database.models import User
from wired_part.database.repository import Repository
from wired_part.ui.pages.dashboard_page import SummaryCard
from wired_part.utils.formatters import format_currency


class WarehouseDashboardPage(QWidget):
    """Warehouse overview with stock counts, value, low stock, and receiving."""

    def __init__(self, repo: Repository, current_user: User, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.current_user = current_user
        if current_user:
            self._perms = repo.get_user_permissions(current_user.id)
        else:
            self._perms = set()
        self._can_see_dollars = "show_dollar_values" in self._perms
        self._setup_ui()
        self.refresh()

    def _setup_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        content = QWidget()
        layout = QVBoxLayout(content)

        title = QLabel("Warehouse Dashboard")
        title.setObjectName("PageTitle")
        layout.addWidget(title)

        # Summary cards
        cards = QGridLayout()
        self.total_stock_card = SummaryCard("Total Stock Count")
        self.total_value_card = SummaryCard("Total Inventory Value")
        self.low_stock_card = SummaryCard("Low Stock Items")
        self.pending_incoming_card = SummaryCard("Pending Incoming")
        self.pending_orders_card = SummaryCard("Pending Orders")

        cards.addWidget(self.total_stock_card, 0, 0)
        cards.addWidget(self.total_value_card, 0, 1)
        cards.addWidget(self.low_stock_card, 0, 2)
        cards.addWidget(self.pending_incoming_card, 1, 0)
        cards.addWidget(self.pending_orders_card, 1, 1)
        # Hide value card if user lacks show_dollar_values permission
        self.total_value_card.setVisible(self._can_see_dollars)
        layout.addLayout(cards)

        # Low stock alerts
        bottom = QHBoxLayout()

        alerts_group = QGroupBox("Low Stock Alerts")
        alerts_layout = QVBoxLayout(alerts_group)
        self.alerts_list = QListWidget()
        self.alerts_list.setMinimumHeight(92)
        self.alerts_list.setMaximumHeight(240)
        alerts_layout.addWidget(self.alerts_list)
        bottom.addWidget(alerts_group)

        # Recent receiving activity
        receiving_group = QGroupBox("Recent Receiving Activity")
        receiving_layout = QVBoxLayout(receiving_group)
        self.receiving_list = QListWidget()
        self.receiving_list.setMinimumHeight(92)
        self.receiving_list.setMaximumHeight(240)
        receiving_layout.addWidget(self.receiving_list)
        bottom.addWidget(receiving_group)

        layout.addLayout(bottom)
        layout.addStretch()

        scroll.setWidget(content)
        outer.addWidget(scroll)

    def refresh(self):
        """Reload all warehouse dashboard data."""
        inv = self.repo.get_inventory_summary()
        self.total_stock_card.set_value(str(inv.get("total_parts", 0)))
        self.total_value_card.set_value(
            format_currency(inv.get("total_value", 0))
        )
        self.low_stock_card.set_value(str(inv.get("low_stock_count", 0)))

        # Pending incoming (orders with status 'approved' or 'ordered')
        try:
            order_summary = self.repo.get_orders_summary()
            self.pending_incoming_card.set_value(
                str(order_summary.get("awaiting_receipt", 0))
            )
            self.pending_orders_card.set_value(
                str(order_summary.get("pending_orders", 0))
            )
        except Exception:
            self.pending_incoming_card.set_value("—")
            self.pending_orders_card.set_value("—")

        # Low stock alerts
        self.alerts_list.clear()
        low_stock = self.repo.get_low_stock_parts()
        if low_stock:
            for p in low_stock[:15]:
                deficit = p.min_quantity - p.quantity
                self.alerts_list.addItem(
                    f"{p.part_number}: {p.quantity}/{p.min_quantity} "
                    f"(need {deficit} more)"
                )
        else:
            self.alerts_list.addItem("All stock levels are healthy")

        # Recent receiving activity
        self.receiving_list.clear()
        try:
            recent = self.repo.get_activity_log(
                entity_type="order", limit=10
            )
            if recent:
                for entry in recent:
                    self.receiving_list.addItem(
                        f"{entry.action}: {entry.description}"
                    )
            else:
                self.receiving_list.addItem("No recent receiving activity")
        except Exception:
            self.receiving_list.addItem("No recent receiving activity")
