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
        for job in self._jobs:
            item = QListWidgetItem(
                f"{job.job_number}\n{job.name}\nStatus: {job.status.title()}"
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
        self.detail_notes.setText("-")
        self.parts_table.setRowCount(0)
        self.total_cost_label.setText("Total: $0.00")
        self.users_list.clear()
        for btn in (self.edit_btn, self.complete_btn, self.delete_btn,
                     self.assign_btn, self.remove_part_btn,
                     self.assign_user_btn, self.consume_btn):
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

        self._selected_job = job
        self.detail_number.setText(job.job_number)
        self.detail_name.setText(job.name)
        self.detail_customer.setText(job.customer or "-")
        self.detail_address.setText(job.address or "-")
        self.detail_status.setText(job.status.title())
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

        # Enable buttons
        is_active = job.status == "active"
        self.edit_btn.setEnabled(True)
        self.complete_btn.setEnabled(is_active)
        self.delete_btn.setEnabled(True)
        self.assign_btn.setEnabled(is_active)
        self.remove_part_btn.setEnabled(is_active)
        self.assign_user_btn.setEnabled(is_active)
        self.consume_btn.setEnabled(is_active)

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
