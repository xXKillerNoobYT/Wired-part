"""Jobs management page — list/detail split view with part assignments."""

from datetime import datetime
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from wired_part.database.models import Job, User
from wired_part.database.repository import Repository
from wired_part.utils.constants import JOB_STATUSES
from wired_part.utils.formatters import format_currency


class JobsPage(QWidget):
    """Jobs management with list and detail panels."""

    def __init__(self, repo: Repository, current_user: User = None):
        super().__init__()
        self.repo = repo
        self.current_user = current_user
        self._jobs: list[Job] = []
        self._selected_job: Optional[Job] = None
        self._setup_ui()

        # Default to "Active" for regular users, "All" for admins
        if self.current_user and self.current_user.role != "admin":
            idx = self.status_filter.findData("active")
            if idx >= 0:
                self.status_filter.setCurrentIndex(idx)

        self.refresh()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # ── Toolbar ─────────────────────────────────────────────
        toolbar = QHBoxLayout()

        self.add_btn = QPushButton("+ New Job")
        self.add_btn.clicked.connect(self._on_add)
        toolbar.addWidget(self.add_btn)

        toolbar.addWidget(QLabel("View:"))
        self.status_filter = QComboBox()
        self.status_filter.addItem("All", "all")
        for s in JOB_STATUSES:
            self.status_filter.addItem(s.title(), s)
        self.status_filter.currentIndexChanged.connect(self._on_filter)
        toolbar.addWidget(self.status_filter)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search jobs...")
        self.search_input.textChanged.connect(self._on_search)
        toolbar.addWidget(self.search_input, 1)

        layout.addLayout(toolbar)

        # ── Splitter: list | detail ─────────────────────────────
        splitter = QSplitter(Qt.Horizontal)

        # Left: job list
        self.job_list = QListWidget()
        self.job_list.currentItemChanged.connect(self._on_job_selected)
        splitter.addWidget(self.job_list)

        # Right: job details
        self.detail_panel = self._build_detail_panel()
        splitter.addWidget(self.detail_panel)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)

        layout.addWidget(splitter)

    def _build_detail_panel(self) -> QWidget:
        """Create the right-side detail view."""
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # Job info
        info_group = QGroupBox("Job Details")
        info_layout = QFormLayout()

        self.detail_number = QLabel("-")
        info_layout.addRow("Job #:", self.detail_number)

        self.detail_name = QLabel("-")
        info_layout.addRow("Name:", self.detail_name)

        self.detail_customer = QLabel("-")
        info_layout.addRow("Customer:", self.detail_customer)

        self.detail_address = QLabel("-")
        info_layout.addRow("Address:", self.detail_address)

        self.detail_status = QLabel("-")
        info_layout.addRow("Status:", self.detail_status)

        self.detail_priority = QLabel("-")
        info_layout.addRow("Priority:", self.detail_priority)

        self.detail_notes = QLabel("-")
        self.detail_notes.setWordWrap(True)
        info_layout.addRow("Notes:", self.detail_notes)

        info_group.setLayout(info_layout)
        layout.addWidget(info_group)

        # Parts assigned
        parts_group = QGroupBox("Parts Assigned")
        parts_layout = QVBoxLayout()

        self.parts_table = QTableWidget()
        self.parts_table.setColumnCount(4)
        self.parts_table.setHorizontalHeaderLabels(
            ["Part #", "Description", "Qty", "Cost"]
        )
        self.parts_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.parts_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.parts_table.horizontalHeader().setStretchLastSection(True)
        self.parts_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.Stretch
        )
        parts_layout.addWidget(self.parts_table)

        self.total_cost_label = QLabel("Total: $0.00")
        self.total_cost_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        parts_layout.addWidget(self.total_cost_label)

        # Part action buttons
        part_btns = QHBoxLayout()
        self.assign_btn = QPushButton("+ Assign Part")
        self.assign_btn.clicked.connect(self._on_assign_part)
        self.assign_btn.setEnabled(False)
        part_btns.addWidget(self.assign_btn)

        self.remove_part_btn = QPushButton("Remove Part")
        self.remove_part_btn.clicked.connect(self._on_remove_part)
        self.remove_part_btn.setEnabled(False)
        part_btns.addWidget(self.remove_part_btn)
        parts_layout.addLayout(part_btns)

        parts_group.setLayout(parts_layout)
        layout.addWidget(parts_group)

        # Assigned users
        users_group = QGroupBox("Assigned Users")
        users_layout = QVBoxLayout()
        self.users_list = QListWidget()
        self.users_list.setMaximumHeight(80)
        users_layout.addWidget(self.users_list)

        user_btns = QHBoxLayout()
        self.assign_user_btn = QPushButton("+ Assign User")
        self.assign_user_btn.clicked.connect(self._on_assign_user)
        self.assign_user_btn.setEnabled(False)
        user_btns.addWidget(self.assign_user_btn)

        self.consume_btn = QPushButton("Consume from Truck")
        self.consume_btn.clicked.connect(self._on_consume)
        self.consume_btn.setEnabled(False)
        user_btns.addWidget(self.consume_btn)
        users_layout.addLayout(user_btns)

        users_group.setLayout(users_layout)
        layout.addWidget(users_group)

        # Labor tracking
        labor_group = QGroupBox("Labor Tracking")
        labor_layout = QVBoxLayout()

        self.labor_summary_label = QLabel("No labor entries")
        self.labor_summary_label.setWordWrap(True)
        labor_layout.addWidget(self.labor_summary_label)

        labor_btns = QHBoxLayout()
        self.clock_in_btn = QPushButton("Clock In")
        self.clock_in_btn.clicked.connect(self._on_clock_in)
        self.clock_in_btn.setEnabled(False)
        labor_btns.addWidget(self.clock_in_btn)

        self.clock_out_btn = QPushButton("Clock Out")
        self.clock_out_btn.clicked.connect(self._on_clock_out)
        self.clock_out_btn.setEnabled(False)
        labor_btns.addWidget(self.clock_out_btn)

        self.manual_entry_btn = QPushButton("Manual Entry")
        self.manual_entry_btn.clicked.connect(self._on_manual_entry)
        self.manual_entry_btn.setEnabled(False)
        labor_btns.addWidget(self.manual_entry_btn)

        self.view_labor_btn = QPushButton("View All")
        self.view_labor_btn.clicked.connect(self._on_view_labor)
        self.view_labor_btn.setEnabled(False)
        labor_btns.addWidget(self.view_labor_btn)

        labor_layout.addLayout(labor_btns)
        labor_group.setLayout(labor_layout)
        layout.addWidget(labor_group)

        # Job action buttons
        action_btns = QHBoxLayout()
        self.edit_btn = QPushButton("Edit")
        self.edit_btn.clicked.connect(self._on_edit)
        self.edit_btn.setEnabled(False)
        action_btns.addWidget(self.edit_btn)

        self.complete_btn = QPushButton("Complete")
        self.complete_btn.clicked.connect(self._on_complete)
        self.complete_btn.setEnabled(False)
        action_btns.addWidget(self.complete_btn)

        self.delete_btn = QPushButton("Delete")
        self.delete_btn.clicked.connect(self._on_delete)
        self.delete_btn.setEnabled(False)
        action_btns.addWidget(self.delete_btn)

        self.billing_btn = QPushButton("Generate Billing")
        self.billing_btn.clicked.connect(self._on_billing)
        self.billing_btn.setEnabled(False)
        action_btns.addWidget(self.billing_btn)

        self.notes_btn = QPushButton("Notes")
        self.notes_btn.clicked.connect(self._on_notes)
        self.notes_btn.setEnabled(False)
        action_btns.addWidget(self.notes_btn)

        self.work_report_btn = QPushButton("Work Report")
        self.work_report_btn.clicked.connect(self._on_work_report)
        self.work_report_btn.setEnabled(False)
        action_btns.addWidget(self.work_report_btn)

        layout.addLayout(action_btns)
        return panel

    def refresh(self):
        """Reload jobs from the database."""
        status = self.status_filter.currentData()
        search = self.search_input.text().strip().lower()

        self._jobs = self.repo.get_all_jobs(status if status != "all" else None)

        if search:
            self._jobs = [
                j for j in self._jobs
                if search in j.job_number.lower()
                or search in j.name.lower()
                or search in (j.customer or "").lower()
            ]

        self.job_list.clear()
        _PRIORITY_LABELS = {1: "P1", 2: "P2", 3: "P3", 4: "P4", 5: "P5"}
        for job in self._jobs:
            p_label = _PRIORITY_LABELS.get(job.priority, "P3")
            item = QListWidgetItem(
                f"[{p_label}] {job.job_number}\n"
                f"{job.name}\nStatus: {job.status.title()}"
            )
            item.setData(Qt.UserRole, job.id)
            self.job_list.addItem(item)

        if not self._jobs:
            self._clear_detail()

    def _clear_detail(self):
        """Reset detail panel to empty state."""
        self._selected_job = None
        self.detail_number.setText("-")
        self.detail_name.setText("-")
        self.detail_customer.setText("-")
        self.detail_address.setText("-")
        self.detail_status.setText("-")
        self.detail_priority.setText("-")
        self.detail_notes.setText("-")
        self.parts_table.setRowCount(0)
        self.total_cost_label.setText("Total: $0.00")
        self.users_list.clear()
        self.labor_summary_label.setText("No labor entries")
        for btn in (self.edit_btn, self.complete_btn, self.delete_btn,
                     self.assign_btn, self.remove_part_btn,
                     self.assign_user_btn, self.consume_btn,
                     self.billing_btn,
                     self.clock_in_btn, self.clock_out_btn,
                     self.manual_entry_btn, self.view_labor_btn,
                     self.notes_btn, self.work_report_btn):
            btn.setEnabled(False)

    def _on_job_selected(self, current, previous):
        """Show details for the selected job."""
        if not current:
            self._clear_detail()
            return

        job_id = current.data(Qt.UserRole)
        job = self.repo.get_job_by_id(job_id)
        if not job:
            self._clear_detail()
            return

        _PRIORITY_NAMES = {
            1: "1 — Urgent", 2: "2 — High", 3: "3 — Normal",
            4: "4 — Low", 5: "5 — Deferred",
        }
        self._selected_job = job
        self.detail_number.setText(job.job_number)
        self.detail_name.setText(job.name)
        self.detail_customer.setText(job.customer or "-")
        self.detail_address.setText(job.address or "-")
        self.detail_status.setText(job.status.title())
        self.detail_priority.setText(
            _PRIORITY_NAMES.get(job.priority, "3 — Normal")
        )
        self.detail_notes.setText(job.notes or "-")

        # Load assigned parts
        job_parts = self.repo.get_job_parts(job.id)
        self.parts_table.setRowCount(len(job_parts))
        for row, jp in enumerate(job_parts):
            self.parts_table.setItem(row, 0, QTableWidgetItem(jp.part_number))
            self.parts_table.setItem(
                row, 1, QTableWidgetItem(jp.part_description)
            )
            self.parts_table.setItem(
                row, 2, QTableWidgetItem(str(jp.quantity_used))
            )
            self.parts_table.setItem(
                row, 3,
                QTableWidgetItem(format_currency(jp.total_cost)),
            )

        total = self.repo.get_job_total_cost(job.id)
        self.total_cost_label.setText(f"Total: {format_currency(total)}")

        # Load assigned users
        assignments = self.repo.get_job_assignments(job.id)
        self.users_list.clear()
        for a in assignments:
            self.users_list.addItem(f"{a.user_name} ({a.role.title()})")

        # Load labor summary
        labor = self.repo.get_labor_summary_for_job(job.id)
        if labor["entry_count"] > 0:
            self.labor_summary_label.setText(
                f"{labor['entry_count']} entries — "
                f"{labor['total_hours']:.1f}h — "
                f"{format_currency(labor['total_cost'])}"
            )
        else:
            self.labor_summary_label.setText("No labor entries")

        # Check if user has active clock-in
        has_active = False
        if self.current_user:
            active = self.repo.get_active_clock_in(self.current_user.id)
            has_active = active is not None and active.job_id == job.id

        # Enable buttons
        is_active = job.status == "active"
        self.edit_btn.setEnabled(True)
        self.complete_btn.setEnabled(is_active)
        self.delete_btn.setEnabled(True)
        self.assign_btn.setEnabled(is_active)
        self.remove_part_btn.setEnabled(is_active)
        self.assign_user_btn.setEnabled(is_active)
        self.consume_btn.setEnabled(is_active)
        self.billing_btn.setEnabled(True)
        self.notes_btn.setEnabled(True)
        self.work_report_btn.setEnabled(True)
        self.clock_in_btn.setEnabled(is_active and not has_active)
        self.clock_out_btn.setEnabled(has_active)
        self.manual_entry_btn.setEnabled(True)
        self.view_labor_btn.setEnabled(True)

    def _on_filter(self):
        self.refresh()

    def _on_search(self):
        self.refresh()

    def _on_add(self):
        from wired_part.ui.dialogs.job_dialog import JobDialog
        dialog = JobDialog(self.repo, parent=self)
        if dialog.exec():
            self.refresh()

    def _on_edit(self):
        if not self._selected_job:
            return
        from wired_part.ui.dialogs.job_dialog import JobDialog
        dialog = JobDialog(self.repo, job=self._selected_job, parent=self)
        if dialog.exec():
            self.refresh()

    def _on_complete(self):
        if not self._selected_job:
            return
        reply = QMessageBox.question(
            self, "Complete Job",
            f"Mark '{self._selected_job.job_number}' as completed?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self._selected_job.status = "completed"
            self._selected_job.completed_at = datetime.now().isoformat()
            self.repo.update_job(self._selected_job)
            self.refresh()

    def _on_delete(self):
        if not self._selected_job:
            return
        reply = QMessageBox.question(
            self, "Delete Job",
            f"Delete '{self._selected_job.job_number}'?\n"
            "Assigned parts will be returned to inventory.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            # Return parts to inventory before deleting
            job_parts = self.repo.get_job_parts(self._selected_job.id)
            for jp in job_parts:
                self.repo.remove_part_from_job(jp.id)
            self.repo.delete_job(self._selected_job.id)
            self.refresh()

    def _on_assign_part(self):
        if not self._selected_job:
            return
        from wired_part.ui.dialogs.assign_parts_dialog import AssignPartsDialog
        dialog = AssignPartsDialog(
            self.repo, self._selected_job, parent=self
        )
        if dialog.exec():
            # Refresh detail to show new assignment
            self._on_job_selected(self.job_list.currentItem(), None)

    def _on_remove_part(self):
        if not self._selected_job:
            return
        rows = self.parts_table.selectionModel().selectedRows()
        if not rows:
            QMessageBox.information(
                self, "No Selection", "Select a part to remove."
            )
            return
        job_parts = self.repo.get_job_parts(self._selected_job.id)
        jp = job_parts[rows[0].row()]
        reply = QMessageBox.question(
            self, "Remove Part",
            f"Remove {jp.part_number} from this job?\n"
            f"{jp.quantity_used} units will be returned to inventory.",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.repo.remove_part_from_job(jp.id)
            self._on_job_selected(self.job_list.currentItem(), None)

    def _on_assign_user(self):
        if not self._selected_job:
            return
        from wired_part.ui.dialogs.job_assign_dialog import JobAssignDialog
        dialog = JobAssignDialog(
            self.repo, self._selected_job.id, parent=self
        )
        if dialog.exec():
            self._on_job_selected(self.job_list.currentItem(), None)

    def _on_consume(self):
        if not self._selected_job:
            return
        from wired_part.ui.dialogs.consume_dialog import ConsumeDialog
        dialog = ConsumeDialog(
            self.repo, self._selected_job.id,
            self.current_user, parent=self
        )
        if dialog.exec():
            self._on_job_selected(self.job_list.currentItem(), None)

    def _on_billing(self):
        if not self._selected_job:
            return
        from wired_part.ui.dialogs.billing_dialog import BillingDialog
        dialog = BillingDialog(
            self.repo, self._selected_job.id, parent=self
        )
        dialog.exec()

    def _on_clock_in(self):
        if not self._selected_job or not self.current_user:
            return
        from wired_part.ui.dialogs.clock_dialog import ClockInDialog
        dialog = ClockInDialog(
            self.repo, self.current_user.id,
            job_id=self._selected_job.id, parent=self
        )
        if dialog.exec():
            self._on_job_selected(self.job_list.currentItem(), None)

    def _on_clock_out(self):
        if not self.current_user:
            return
        active = self.repo.get_active_clock_in(self.current_user.id)
        if not active:
            QMessageBox.information(
                self, "Not Clocked In", "No active clock-in found."
            )
            return
        from wired_part.ui.dialogs.clock_dialog import ClockOutDialog
        dialog = ClockOutDialog(self.repo, active.id, parent=self)
        if dialog.exec():
            self._on_job_selected(self.job_list.currentItem(), None)

    def _on_manual_entry(self):
        if not self._selected_job:
            return
        user_id = self.current_user.id if self.current_user else None
        from wired_part.ui.dialogs.labor_entry_dialog import LaborEntryDialog
        dialog = LaborEntryDialog(
            self.repo, user_id=user_id,
            job_id=self._selected_job.id, parent=self
        )
        if dialog.exec():
            self._on_job_selected(self.job_list.currentItem(), None)

    def _on_view_labor(self):
        if not self._selected_job:
            return
        from wired_part.ui.dialogs.labor_log_dialog import LaborLogDialog
        dialog = LaborLogDialog(
            self.repo, self._selected_job.id,
            job_name=self._selected_job.name, parent=self
        )
        dialog.exec()
        self._on_job_selected(self.job_list.currentItem(), None)

    def _on_notes(self):
        if not self._selected_job:
            return
        user_id = self.current_user.id if self.current_user else None
        from wired_part.ui.dialogs.notebook_dialog import NotebookDialog
        dialog = NotebookDialog(
            self.repo, self._selected_job.id,
            job_name=self._selected_job.name,
            user_id=user_id, parent=self
        )
        dialog.exec()

    def _on_work_report(self):
        if not self._selected_job:
            return
        from wired_part.ui.dialogs.work_report_dialog import WorkReportDialog
        dialog = WorkReportDialog(
            self.repo, self._selected_job.id, parent=self
        )
        dialog.exec()
