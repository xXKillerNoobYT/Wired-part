"""Trucks Dashboard — fleet overview with summary cards and status table."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGridLayout,
    QGroupBox,
    QHeaderView,
    QLabel,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from wired_part.database.models import User
from wired_part.database.repository import Repository
from wired_part.ui.pages.dashboard_page import SummaryCard


class TrucksDashboardPage(QWidget):
    """Trucks overview with fleet counts and status table."""

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

        title = QLabel("Trucks Dashboard")
        title.setObjectName("PageTitle")
        layout.addWidget(title)

        # Summary cards
        cards = QGridLayout()
        self.total_trucks_card = SummaryCard("Total Trucks")
        self.active_trucks_card = SummaryCard("Active Trucks")
        self.total_inv_value_card = SummaryCard("Total Truck Inv Value")
        self.pending_transfers_card = SummaryCard("Pending Transfers")

        cards.addWidget(self.total_trucks_card, 0, 0)
        cards.addWidget(self.active_trucks_card, 0, 1)
        cards.addWidget(self.total_inv_value_card, 0, 2)
        cards.addWidget(self.pending_transfers_card, 0, 3)
        # Hide value card if user lacks show_dollar_values permission
        self.total_inv_value_card.setVisible(self._can_see_dollars)
        layout.addLayout(cards)

        # Fleet status table
        fleet_group = QGroupBox("Fleet Status")
        fleet_layout = QVBoxLayout(fleet_group)
        self.fleet_table = QTableWidget()
        self.fleet_table.setColumnCount(4)
        self.fleet_table.setHorizontalHeaderLabels([
            "Truck", "Assigned To", "Items", "Pending Transfers",
        ])
        self.fleet_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )
        self.fleet_table.setMinimumHeight(92)
        self.fleet_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.fleet_table.setSelectionBehavior(QTableWidget.SelectRows)
        fleet_layout.addWidget(self.fleet_table)
        layout.addWidget(fleet_group)

        layout.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll)

    def refresh(self):
        """Reload all trucks dashboard data."""
        all_trucks = self.repo.get_all_trucks(active_only=False)
        active_trucks = [t for t in all_trucks if t.is_active]
        self.total_trucks_card.set_value(str(len(all_trucks)))
        self.active_trucks_card.set_value(str(len(active_trucks)))

        # Pending transfers
        pending = self.repo.get_all_pending_transfers()
        self.pending_transfers_card.set_value(str(len(pending)))

        # Total truck inventory value
        total_value = 0.0
        self.fleet_table.setRowCount(len(active_trucks))
        for row, truck in enumerate(active_trucks):
            self.fleet_table.setItem(
                row, 0, QTableWidgetItem(
                    f"{truck.truck_number} — {truck.name}"
                )
            )
            # Assigned user
            assigned = ""
            if truck.assigned_user_id:
                try:
                    user = self.repo.get_user_by_id(truck.assigned_user_id)
                    if user:
                        assigned = user.display_name
                except Exception:
                    pass
            self.fleet_table.setItem(
                row, 1, QTableWidgetItem(assigned or "Unassigned")
            )
            # Inventory count
            inv = self.repo.get_truck_inventory(truck.id)
            item_count = sum(i.quantity for i in inv)
            self.fleet_table.setItem(
                row, 2, QTableWidgetItem(str(item_count))
            )
            # Pending transfers for this truck
            truck_pending = self.repo.get_truck_transfers(
                truck.id, status="pending"
            )
            self.fleet_table.setItem(
                row, 3, QTableWidgetItem(str(len(truck_pending)))
            )
            # Accumulate value
            for ti in inv:
                total_value += (ti.quantity or 0) * (ti.unit_cost or 0)

        from wired_part.utils.formatters import format_currency
        self.total_inv_value_card.set_value(format_currency(total_value))
