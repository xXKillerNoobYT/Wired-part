"""Dashboard page — overview of inventory, jobs, trucks, notifications."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
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
        self.setObjectName("SummaryCard")
        self.setFrameShape(QFrame.StyledPanel)
        layout = QVBoxLayout(self)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("SummaryCardTitle")
        self.value_label = QLabel(value)
        self.value_label.setObjectName("SummaryCardValue")
        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)

    def set_value(self, value: str):
        self.value_label.setText(value)


class DashboardPage(QWidget):
    """Main dashboard with summary cards, personal info, and alerts."""

    # Signal emitted when user wants to navigate to a specific tab
    navigate_to_tab = Signal(int)

    def __init__(self, repo: Repository, current_user: User, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.current_user = current_user
        self._perms: set[str] = set()
        if current_user:
            self._perms = repo.get_user_permissions(current_user.id)
        self._active_entry_id = None
        self._active_job_id = None
        self._setup_ui()
        self.refresh()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Title with user greeting
        title = QLabel(
            f"Dashboard -- Welcome, {self.current_user.display_name}"
        )
        title.setObjectName("PageTitle")
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
        self.orders_card = SummaryCard("Pending Orders")
        self.returns_card = SummaryCard("Open Returns")

        cards_layout.addWidget(self.parts_card, 0, 0)
        cards_layout.addWidget(self.value_card, 0, 1)
        cards_layout.addWidget(self.low_stock_card, 0, 2)
        cards_layout.addWidget(self.hours_card, 0, 3)

        # Inventory Value is admin-level info -- hide if no permission
        self.value_card.setVisible(
            "show_dollar_values" in self._perms
        )
        cards_layout.addWidget(self.jobs_card, 1, 0)
        cards_layout.addWidget(self.trucks_card, 1, 1)
        cards_layout.addWidget(self.pending_card, 1, 2)
        cards_layout.addWidget(self.orders_card, 1, 3)
        cards_layout.addWidget(self.returns_card, 2, 0)

        layout.addLayout(cards_layout)

        # Middle section: My Active Jobs + My Truck + Currently Clocked In
        middle = QHBoxLayout()

        # My active jobs -- clickable for clock-in
        my_jobs_group = QGroupBox("My Active Jobs")
        my_jobs_layout = QVBoxLayout(my_jobs_group)

        self.my_jobs_list = QListWidget()
        self.my_jobs_list.setMaximumHeight(150)
        self.my_jobs_list.setToolTip(
            "Select a job and click Clock In below"
        )
        my_jobs_layout.addWidget(self.my_jobs_list)

        # Clock In button -- select a job from the list above
        self.clock_in_btn = QPushButton("Clock In to Selected Job")
        self.clock_in_btn.setToolTip(
            "Select a job above, then click to clock in"
        )
        self.clock_in_btn.clicked.connect(self._on_clock_in)
        self.clock_in_btn.setEnabled(False)
        my_jobs_layout.addWidget(self.clock_in_btn)
        self.my_jobs_list.currentItemChanged.connect(
            self._on_my_job_selection_changed
        )
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

        # Action buttons for the active clock-in job
        btn_row = QVBoxLayout()

        self.quick_clock_out_btn = QPushButton("Quick Clock Out")
        self.quick_clock_out_btn.clicked.connect(self._on_quick_clock_out)
        self.quick_clock_out_btn.setEnabled(False)
        btn_row.addWidget(self.quick_clock_out_btn)

        self.make_order_btn = QPushButton("Make Order for This Job")
        self.make_order_btn.setToolTip(
            "Create a purchase order for the job you're clocked into"
        )
        self.make_order_btn.clicked.connect(self._on_make_order)
        self.make_order_btn.setEnabled(False)
        btn_row.addWidget(self.make_order_btn)

        self.job_notes_btn = QPushButton("Job Notes")
        self.job_notes_btn.setToolTip(
            "Open notes for the job you're clocked into"
        )
        self.job_notes_btn.clicked.connect(self._on_job_notes)
        self.job_notes_btn.setEnabled(False)
        btn_row.addWidget(self.job_notes_btn)

        clock_layout.addLayout(btn_row)
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

    def _on_my_job_selection_changed(self, current, previous):
        """Enable/disable Clock In based on job list selection."""
        has_selection = current is not None
        not_clocked_in = self._active_entry_id is None
        self.clock_in_btn.setEnabled(has_selection and not_clocked_in)

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
            self.make_order_btn.setEnabled(True)
            self.job_notes_btn.setEnabled(True)
            self.clock_in_btn.setEnabled(False)
            self._active_entry_id = active_entry.id
            self._active_job_id = active_entry.job_id
        else:
            self.clock_status_label.setText("Not clocked in")
            self.quick_clock_out_btn.setEnabled(False)
            self.make_order_btn.setEnabled(False)
            self.job_notes_btn.setEnabled(False)
            self._active_entry_id = None
            self._active_job_id = None
            # Re-evaluate clock-in button based on selection
            self._on_my_job_selection_changed(
                self.my_jobs_list.currentItem(), None
            )

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
                    f"{job.job_number} -- {job.name} [{my_role.title()}]"
                )
                item.setData(Qt.ItemDataRole.UserRole, job.id)
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
                f"<b>{my_truck.truck_number}</b> -- {my_truck.name}"
            )
            truck_inv = self.repo.get_truck_inventory(my_truck.id)
            if truck_inv:
                for ti in truck_inv[:10]:
                    self.truck_inv_list.addItem(
                        f"{ti.part_number}: {ti.quantity} on-hand"
                    )
            else:
                self.truck_inv_list.addItem("No parts on truck")
            my_pending = self.repo.get_truck_transfers(
                my_truck.id, status="pending"
            )
            if my_pending:
                self.truck_inv_list.addItem(
                    f"--- {len(my_pending)} pending transfer(s) ---"
                )
        else:
            self.my_truck_label.setText("No truck assigned to you")

        # Orders summary
        try:
            order_summary = self.repo.get_orders_summary()
            pending_count = order_summary.get("pending_orders", 0)
            awaiting = order_summary.get("awaiting_receipt", 0)
            self.orders_card.set_value(f"{pending_count}")
            if awaiting > 0:
                self.orders_card.title_label.setText(
                    f"Pending Orders ({awaiting} awaiting)"
                )
            else:
                self.orders_card.title_label.setText("Pending Orders")
        except Exception:
            self.orders_card.set_value("--")

        # Open returns
        try:
            open_returns = self.repo.get_all_return_authorizations()
            active_returns = [
                r for r in open_returns
                if r.status in ("initiated", "picked_up")
            ]
            self.returns_card.set_value(str(len(active_returns)))
        except Exception:
            self.returns_card.set_value("--")

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

    def _on_clock_in(self):
        """Clock in to the selected job from the My Active Jobs list."""
        item = self.my_jobs_list.currentItem()
        if not item:
            QMessageBox.warning(
                self, "No Job Selected",
                "Please select a job from your active jobs list."
            )
            return

        job_id = item.data(Qt.ItemDataRole.UserRole)
        if not job_id:
            return

        # Double-check not already clocked in
        active = self.repo.get_active_clock_in(self.current_user.id)
        if active:
            QMessageBox.warning(
                self, "Already Clocked In",
                f"You are already clocked in to "
                f"{active.job_number or 'a job'}.\n"
                "Please clock out first.",
            )
            return

        from wired_part.ui.dialogs.clock_dialog import ClockInDialog
        dialog = ClockInDialog(
            self.repo, self.current_user.id,
            job_id=job_id, parent=self
        )
        if dialog.exec():
            self.refresh()

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

    def _on_make_order(self):
        """Open order dialog for the job the user is clocked into."""
        if not self._active_job_id:
            return
        from wired_part.ui.dialogs.order_dialog import OrderDialog
        job = self.repo.get_job_by_id(self._active_job_id)
        if not job:
            return
        dialog = OrderDialog(self.repo, job_id=job.id, parent=self)
        if dialog.exec():
            QMessageBox.information(
                self, "Order Created",
                f"Purchase order created for {job.job_number}."
            )
            self.refresh()

    def _on_job_notes(self):
        """Open notebook dialog for the job the user is clocked into."""
        if not self._active_job_id:
            return
        from wired_part.ui.dialogs.notebook_dialog import NotebookDialog
        job = self.repo.get_job_by_id(self._active_job_id)
        if not job:
            return
        dialog = NotebookDialog(
            self.repo, job_id=job.id, parent=self
        )
        dialog.exec()
