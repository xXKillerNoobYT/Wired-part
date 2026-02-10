"""Labor overview page — all labor entries across jobs with summary stats."""

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from wired_part.database.models import LaborEntry, User
from wired_part.database.repository import Repository
from wired_part.utils.formatters import format_currency


class LaborPage(QWidget):
    """Cross-job labor overview with filtering, summary, and clock-in/out."""

    COLUMNS = [
        "Date", "User", "Job", "Category", "Hours",
        "Rate", "Cost", "Description",
    ]

    def __init__(self, repo: Repository, current_user: User = None):
        super().__init__()
        self.repo = repo
        self.current_user = current_user
        self._entries: list[LaborEntry] = []
        self._setup_ui()
        self.refresh()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # ── Toolbar ───────────────────────────────────────────────
        toolbar = QHBoxLayout()

        toolbar.addWidget(QLabel("From:"))
        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setDate(self.date_from.date().addMonths(-1))
        self.date_from.setDisplayFormat("yyyy-MM-dd")
        toolbar.addWidget(self.date_from)

        toolbar.addWidget(QLabel("To:"))
        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDisplayFormat("yyyy-MM-dd")
        toolbar.addWidget(self.date_to)

        toolbar.addWidget(QLabel("Job:"))
        self.job_filter = QComboBox()
        self.job_filter.addItem("All Jobs", None)
        for job in self.repo.get_all_jobs():
            self.job_filter.addItem(
                f"{job.job_number} — {job.name}", job.id
            )
        toolbar.addWidget(self.job_filter, 1)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh)
        toolbar.addWidget(refresh_btn)

        toolbar.addSpacing(20)

        self.clock_in_btn = QPushButton("Clock In")
        self.clock_in_btn.clicked.connect(self._on_clock_in)
        toolbar.addWidget(self.clock_in_btn)

        self.clock_out_btn = QPushButton("Clock Out")
        self.clock_out_btn.clicked.connect(self._on_clock_out)
        toolbar.addWidget(self.clock_out_btn)

        layout.addLayout(toolbar)

        # ── Active clock-in banner ────────────────────────────────
        self.active_banner = QLabel("")
        self.active_banner.setStyleSheet(
            "background-color: #313244; padding: 6px; "
            "border-radius: 4px; font-size: 13px;"
        )
        self.active_banner.setVisible(False)
        layout.addWidget(self.active_banner)

        # ── Labor table ───────────────────────────────────────────
        self.table = QTableWidget()
        self.table.setColumnCount(len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(
            7, QHeaderView.Stretch
        )
        layout.addWidget(self.table, 1)

        # ── Summary ──────────────────────────────────────────────
        summary_group = QGroupBox("Summary")
        summary_layout = QHBoxLayout()

        self.total_hours_label = QLabel("Total Hours: 0.00")
        self.total_hours_label.setStyleSheet(
            "font-weight: bold; font-size: 14px;"
        )
        summary_layout.addWidget(self.total_hours_label)

        self.total_cost_label = QLabel("Total Cost: $0.00")
        self.total_cost_label.setStyleSheet(
            "font-weight: bold; font-size: 14px;"
        )
        summary_layout.addWidget(self.total_cost_label)

        self.entry_count_label = QLabel("Entries: 0")
        summary_layout.addWidget(self.entry_count_label)

        summary_layout.addStretch()

        summary_group.setLayout(summary_layout)
        layout.addWidget(summary_group)

    def refresh(self):
        """Reload labor data based on current filters."""
        date_from = self.date_from.date().toString("yyyy-MM-dd")
        date_to = self.date_to.date().toString("yyyy-MM-dd")
        job_id = self.job_filter.currentData()

        if job_id:
            self._entries = self.repo.get_labor_entries_for_job(
                job_id, date_from=date_from, date_to=date_to
            )
        else:
            # Get all entries by getting entries for each job
            all_jobs = self.repo.get_all_jobs()
            self._entries = []
            for job in all_jobs:
                entries = self.repo.get_labor_entries_for_job(
                    job.id, date_from=date_from, date_to=date_to
                )
                self._entries.extend(entries)
            # Sort by date descending
            self._entries.sort(
                key=lambda e: str(e.start_time or ""), reverse=True
            )

        self._populate_table()
        self._update_summary()
        self._update_clock_status()

    def _populate_table(self):
        """Fill the table with labor entries."""
        self.table.setRowCount(len(self._entries))
        for row, entry in enumerate(self._entries):
            date_str = ""
            if entry.start_time:
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(str(entry.start_time))
                    date_str = dt.strftime("%Y-%m-%d %H:%M")
                except (ValueError, TypeError):
                    date_str = str(entry.start_time)[:16]

            cost = (entry.hours or 0) * (entry.rate_per_hour or 0)
            job_label = entry.job_number or ""

            cells = [
                QTableWidgetItem(date_str),
                QTableWidgetItem(entry.user_name or ""),
                QTableWidgetItem(job_label),
                QTableWidgetItem(entry.sub_task_category or ""),
                QTableWidgetItem(
                    f"{entry.hours:.2f}" if entry.hours else "—"
                ),
                QTableWidgetItem(
                    format_currency(entry.rate_per_hour)
                    if entry.rate_per_hour else "—"
                ),
                QTableWidgetItem(format_currency(cost)),
                QTableWidgetItem(entry.description or ""),
            ]
            for col, cell in enumerate(cells):
                if col in (4, 5, 6):
                    cell.setTextAlignment(
                        Qt.AlignRight | Qt.AlignVCenter
                    )
                # Highlight active entries (no end_time)
                if not entry.end_time:
                    cell.setForeground(Qt.cyan)
                elif entry.is_overtime:
                    cell.setForeground(Qt.yellow)
                self.table.setItem(row, col, cell)

    def _update_summary(self):
        """Update summary labels."""
        total_hours = sum(e.hours or 0 for e in self._entries)
        total_cost = sum(
            (e.hours or 0) * (e.rate_per_hour or 0)
            for e in self._entries
        )
        self.total_hours_label.setText(f"Total Hours: {total_hours:.2f}")
        self.total_cost_label.setText(
            f"Total Cost: {format_currency(total_cost)}"
        )
        self.entry_count_label.setText(f"Entries: {len(self._entries)}")

    def _update_clock_status(self):
        """Check and display active clock-in status."""
        if not self.current_user:
            self.active_banner.setVisible(False)
            self.clock_out_btn.setEnabled(False)
            return

        active = self.repo.get_active_clock_in(self.current_user.id)
        if active:
            self.active_banner.setText(
                f"Currently clocked in: "
                f"{active.job_number or 'N/A'} — "
                f"{active.sub_task_category} — "
                f"since {str(active.start_time)[:16]}"
            )
            self.active_banner.setVisible(True)
            self.clock_out_btn.setEnabled(True)
            self.clock_in_btn.setEnabled(False)
        else:
            self.active_banner.setVisible(False)
            self.clock_out_btn.setEnabled(False)
            self.clock_in_btn.setEnabled(True)

    def _on_clock_in(self):
        """Open clock-in dialog."""
        if not self.current_user:
            return
        from wired_part.ui.dialogs.clock_dialog import ClockInDialog
        dialog = ClockInDialog(
            self.repo, self.current_user.id, parent=self
        )
        if dialog.exec():
            self.refresh()

    def _on_clock_out(self):
        """Open clock-out dialog."""
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
            self.refresh()
