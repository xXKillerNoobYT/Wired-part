"""Office Dashboard — billing and labor overview for office staff."""

from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGridLayout,
    QGroupBox,
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


class OfficeDashboardPage(QWidget):
    """Office overview with labor hours, costs, and billing info."""

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

        title = QLabel("Office Dashboard")
        title.setObjectName("PageTitle")
        layout.addWidget(title)

        # Summary cards
        cards = QGridLayout()
        self.labor_hours_card = SummaryCard("Labor Hours This Period")
        self.parts_cost_card = SummaryCard("Parts Cost This Period")
        self.active_jobs_card = SummaryCard("Active Jobs")
        self.pending_orders_card = SummaryCard("Pending Orders")

        cards.addWidget(self.labor_hours_card, 0, 0)
        cards.addWidget(self.parts_cost_card, 0, 1)
        cards.addWidget(self.active_jobs_card, 0, 2)
        cards.addWidget(self.pending_orders_card, 0, 3)
        # Hide cost card if user lacks show_dollar_values permission
        self.parts_cost_card.setVisible(self._can_see_dollars)
        layout.addLayout(cards)

        # Recent billing activity
        billing_group = QGroupBox("Recent Billing Cycles")
        billing_layout = QVBoxLayout(billing_group)
        self.billing_list = QListWidget()
        self.billing_list.setMinimumHeight(92)
        self.billing_list.setMaximumHeight(200)
        billing_layout.addWidget(self.billing_list)
        layout.addWidget(billing_group)

        layout.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll)

    def refresh(self):
        """Reload all office dashboard data."""
        now = datetime.now()
        month_start = now.replace(day=1).strftime("%Y-%m-%d")
        today_str = now.strftime("%Y-%m-%d")

        # Labor hours this period (all users)
        try:
            all_users = self.repo.get_all_users()
            total_hours = 0.0
            for user in all_users:
                entries = self.repo.get_labor_entries_for_user(
                    user.id, date_from=month_start, date_to=today_str,
                )
                total_hours += sum(e.hours or 0 for e in entries)
            self.labor_hours_card.set_value(f"{total_hours:.1f}")
        except Exception:
            self.labor_hours_card.set_value("—")

        # Parts cost this period
        try:
            inv = self.repo.get_inventory_summary()
            self.parts_cost_card.set_value(
                format_currency(inv.get("total_value", 0))
            )
        except Exception:
            self.parts_cost_card.set_value("—")

        # Active jobs
        active = self.repo.get_all_jobs("active")
        self.active_jobs_card.set_value(str(len(active)))

        # Pending orders
        try:
            order_summary = self.repo.get_orders_summary()
            self.pending_orders_card.set_value(
                str(order_summary.get("pending_orders", 0))
            )
        except Exception:
            self.pending_orders_card.set_value("—")

        # Recent billing cycles
        self.billing_list.clear()
        try:
            cycles = self.repo.get_all_billing_cycles()
            if cycles:
                for c in cycles[:5]:
                    status = "Closed" if c.is_closed else "Open"
                    self.billing_list.addItem(
                        f"Period {c.start_date} to {c.end_date} [{status}]"
                    )
            else:
                self.billing_list.addItem("No billing cycles yet")
        except Exception:
            self.billing_list.addItem("No billing cycles yet")
