"""Dashboard page — overview of inventory, jobs, trucks, notifications."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from wired_part.database.models import User
from wired_part.database.repository import Repository
from wired_part.utils.formatters import format_currency


class SummaryCard(QFrame):
    """A styled card showing a metric."""

    def __init__(self, title: str, value: str = "0", parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet(
            "SummaryCard { border: 1px solid #45475a; border-radius: 8px; "
            "padding: 12px; }"
        )
        layout = QVBoxLayout(self)
        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("color: #6c7086; font-size: 12px;")
        self.value_label = QLabel(value)
        self.value_label.setStyleSheet("font-size: 24px; font-weight: bold;")
        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)

    def set_value(self, value: str):
        self.value_label.setText(value)


class DashboardPage(QWidget):
    """Main dashboard with summary cards, personal info, and alerts."""

    def __init__(self, repo: Repository, current_user: User, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.current_user = current_user
        self._setup_ui()
        self.refresh()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Title with user greeting
        title = QLabel(f"Dashboard — Welcome, {self.current_user.display_name}")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        layout.addWidget(title)

        # Summary cards row
        cards_layout = QGridLayout()

        self.parts_card = SummaryCard("Total Parts")
        self.value_card = SummaryCard("Inventory Value")
        self.low_stock_card = SummaryCard("Low Stock Items")
        self.jobs_card = SummaryCard("Active Jobs")
        self.trucks_card = SummaryCard("Active Trucks")
        self.pending_card = SummaryCard("Pending Transfers")
        self.hours_card = SummaryCard("Hours This Week")

        cards_layout.addWidget(self.parts_card, 0, 0)
        cards_layout.addWidget(self.value_card, 0, 1)
        cards_layout.addWidget(self.low_stock_card, 0, 2)
        cards_layout.addWidget(self.hours_card, 0, 3)
        cards_layout.addWidget(self.jobs_card, 1, 0)
        cards_layout.addWidget(self.trucks_card, 1, 1)
        cards_layout.addWidget(self.pending_card, 1, 2)

        layout.addLayout(cards_layout)

        # Middle section: My Active Jobs + My Truck
        middle = QHBoxLayout()

        # My active jobs
        my_jobs_group = QGroupBox("My Active Jobs")
        my_jobs_layout = QVBoxLayout(my_jobs_group)
        self.my_jobs_list = QListWidget()
        self.my_jobs_list.setMaximumHeight(180)
        my_jobs_layout.addWidget(self.my_jobs_list)
        middle.addWidget(my_jobs_group)

        # My truck
        my_truck_group = QGroupBox("My Truck")
        my_truck_layout = QVBoxLayout(my_truck_group)
        self.my_truck_label = QLabel("No truck assigned")
        self.my_truck_label.setWordWrap(True)
        self.my_truck_label.setStyleSheet("padding: 8px;")
        my_truck_layout.addWidget(self.my_truck_label)
        self.truck_inv_list = QListWidget()
        self.truck_inv_list.setMaximumHeight(140)
        my_truck_layout.addWidget(self.truck_inv_list)
        middle.addWidget(my_truck_group)

        # Currently clocked in
        clock_group = QGroupBox("Currently Clocked In")
        clock_layout = QVBoxLayout(clock_group)
        self.clock_status_label = QLabel("Not clocked in")
        self.clock_status_label.setWordWrap(True)
        self.clock_status_label.setStyleSheet("padding: 8px;")
        clock_layout.addWidget(self.clock_status_label)

        self.quick_clock_out_btn = QPushButton("Quick Clock Out")
        self.quick_clock_out_btn.clicked.connect(self._on_quick_clock_out)
        self.quick_clock_out_btn.setEnabled(False)
        clock_layout.addWidget(self.quick_clock_out_btn)
        middle.addWidget(clock_group)

        layout.addLayout(middle)

        # Bottom section: notifications + low stock
        bottom = QHBoxLayout()

        # Recent notifications
        notif_group = QGroupBox("Recent Notifications")
        notif_layout = QVBoxLayout(notif_group)
        self.notif_list = QListWidget()
        self.notif_list.setMaximumHeight(160)
        notif_layout.addWidget(self.notif_list)
        bottom.addWidget(notif_group)

        # Low stock alerts
        alerts_group = QGroupBox("Low Stock Alerts")
        alerts_layout = QVBoxLayout(alerts_group)
        self.alerts_list = QListWidget()
        self.alerts_list.setMaximumHeight(160)
        alerts_layout.addWidget(self.alerts_list)
        bottom.addWidget(alerts_group)

        layout.addLayout(bottom)
        layout.addStretch()

    def refresh(self):
        # Inventory summary
        inv = self.repo.get_inventory_summary()
        self.parts_card.set_value(str(inv.get("total_parts", 0)))
        self.value_card.set_value(
            format_currency(inv.get("total_value", 0))
        )
        self.low_stock_card.set_value(str(inv.get("low_stock_count", 0)))

        # Jobs summary
        job_summary = self.repo.get_job_summary("active")
        self.jobs_card.set_value(str(job_summary.get("total_jobs", 0)))

        # Trucks
        trucks = self.repo.get_all_trucks(active_only=True)
        self.trucks_card.set_value(str(len(trucks)))

        # Pending transfers
        pending = self.repo.get_all_pending_transfers()
        self.pending_card.set_value(str(len(pending)))

        # Hours this week
        from datetime import datetime, timedelta
        today = datetime.now()
        week_start = today - timedelta(days=today.weekday())
        week_start_str = week_start.strftime("%Y-%m-%d")
        today_str = today.strftime("%Y-%m-%d")
        my_entries = self.repo.get_labor_entries_for_user(
            self.current_user.id,
            date_from=week_start_str,
            date_to=today_str,
        )
        weekly_hours = sum(e.hours or 0 for e in my_entries)
        self.hours_card.set_value(f"{weekly_hours:.1f}")

        # Currently clocked in
        active_entry = self.repo.get_active_clock_in(self.current_user.id)
        if active_entry:
            self.clock_status_label.setText(
                f"<b>Job:</b> {active_entry.job_number or 'N/A'}<br>"
                f"<b>Category:</b> {active_entry.sub_task_category}<br>"
                f"<b>Since:</b> {str(active_entry.start_time)[:16]}"
            )
            self.quick_clock_out_btn.setEnabled(True)
            self._active_entry_id = active_entry.id
        else:
            self.clock_status_label.setText("Not clocked in")
            self.quick_clock_out_btn.setEnabled(False)
            self._active_entry_id = None

        # My Active Jobs
        self.my_jobs_list.clear()
        all_active = self.repo.get_all_jobs("active")
        my_jobs = []
        for job in all_active:
            assignments = self.repo.get_job_assignments(job.id)
            if any(a.user_id == self.current_user.id for a in assignments):
                my_jobs.append(job)
        if my_jobs:
            for job in my_jobs:
                role_list = self.repo.get_job_assignments(job.id)
                my_role = next(
                    (a.role for a in role_list
                     if a.user_id == self.current_user.id),
                    "worker",
                )
                item = QListWidgetItem(
                    f"{job.job_number} — {job.name} [{my_role.title()}]"
                )
                self.my_jobs_list.addItem(item)
        else:
            self.my_jobs_list.addItem("No active job assignments")

        # My Truck
        self.truck_inv_list.clear()
        my_truck = None
        for truck in trucks:
            if truck.assigned_user_id == self.current_user.id:
                my_truck = truck
                break
        if my_truck:
            self.my_truck_label.setText(
                f"<b>{my_truck.truck_number}</b> — {my_truck.name}"
            )
            truck_inv = self.repo.get_truck_inventory(my_truck.id)
            if truck_inv:
                for ti in truck_inv[:10]:
                    self.truck_inv_list.addItem(
                        f"{ti.part_number}: {ti.quantity} on-hand"
                    )
            else:
                self.truck_inv_list.addItem("No parts on truck")
            # Show pending transfers for my truck
            my_pending = self.repo.get_truck_transfers(
                my_truck.id, status="pending"
            )
            if my_pending:
                self.truck_inv_list.addItem(
                    f"--- {len(my_pending)} pending transfer(s) ---"
                )
        else:
            self.my_truck_label.setText("No truck assigned to you")

        # Notifications
        self.notif_list.clear()
        notifications = self.repo.get_user_notifications(
            self.current_user.id, unread_only=True, limit=5
        )
        if notifications:
            for n in notifications:
                icon = {"info": "i", "warning": "!", "critical": "!!"}.get(
                    n.severity, "i"
                )
                item = QListWidgetItem(f"[{icon}] {n.title}: {n.message}")
                self.notif_list.addItem(item)
        else:
            self.notif_list.addItem("No unread notifications")

        # Low stock alerts
        self.alerts_list.clear()
        low_stock = self.repo.get_low_stock_parts()
        if low_stock:
            for p in low_stock[:10]:
                deficit = p.min_quantity - p.quantity
                self.alerts_list.addItem(
                    f"{p.part_number}: {p.quantity}/{p.min_quantity} "
                    f"(need {deficit} more)"
                )
        else:
            self.alerts_list.addItem("All stock levels are healthy")

    def _on_quick_clock_out(self):
        """Quick clock out from the dashboard."""
        if not self._active_entry_id:
            return
        from wired_part.ui.dialogs.clock_dialog import ClockOutDialog
        dialog = ClockOutDialog(
            self.repo, self._active_entry_id, parent=self
        )
        if dialog.exec():
            self.refresh()
