"""Labor log dialog — full labor history for a job with filtering and summary."""

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QDateEdit,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from wired_part.database.models import LaborEntry
from wired_part.database.repository import Repository
from wired_part.utils.formatters import format_currency


class LaborLogDialog(QDialog):
    """Full labor history viewer for a specific job."""

    COLUMNS = [
        "Date", "User", "Category", "Hours", "Rate",
        "Cost", "Description", "Overtime",
    ]

    def __init__(self, repo: Repository, job_id: int,
                 job_name: str = "", parent=None):
        super().__init__(parent)
        self.repo = repo
        self.job_id = job_id
        self.setWindowTitle(
            f"Labor Log: {job_name}" if job_name else "Labor Log"
        )
        self.resize(900, 600)
        self._entries: list[LaborEntry] = []
        self._setup_ui()
        self._refresh()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # ── Date filter toolbar ───────────────────────────────────
        filter_layout = QHBoxLayout()

        filter_layout.addWidget(QLabel("From:"))
        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setDate(self.date_from.date().addMonths(-3))
        self.date_from.setDisplayFormat("yyyy-MM-dd")
        filter_layout.addWidget(self.date_from)

        filter_layout.addWidget(QLabel("To:"))
        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDate(QDate.currentDate())
        self.date_to.setDisplayFormat("yyyy-MM-dd")
        filter_layout.addWidget(self.date_to)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._refresh)
        filter_layout.addWidget(refresh_btn)

        filter_layout.addStretch()

        add_btn = QPushButton("+ Manual Entry")
        add_btn.clicked.connect(self._on_add_entry)
        filter_layout.addWidget(add_btn)

        edit_btn = QPushButton("Edit")
        edit_btn.clicked.connect(self._on_edit_entry)
        filter_layout.addWidget(edit_btn)

        delete_btn = QPushButton("Delete")
        delete_btn.clicked.connect(self._on_delete_entry)
        filter_layout.addWidget(delete_btn)

        layout.addLayout(filter_layout)

        # ── Labor entries table ───────────────────────────────────
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
            6, QHeaderView.Stretch  # Description column
        )
        layout.addWidget(self.table, 1)

        # ── Summary section ───────────────────────────────────────
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

        self.category_summary_label = QLabel("")
        self.category_summary_label.setWordWrap(True)
        summary_layout.addWidget(self.category_summary_label, 1)

        summary_group.setLayout(summary_layout)
        layout.addWidget(summary_group)

        # ── Bottom bar ────────────────────────────────────────────
        bottom = QHBoxLayout()
        bottom.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        bottom.addWidget(close_btn)
        layout.addLayout(bottom)

    def _refresh(self):
        """Reload labor entries from the database."""
        date_from = self.date_from.date().toString("yyyy-MM-dd")
        date_to = self.date_to.date().toString("yyyy-MM-dd")

        self._entries = self.repo.get_labor_entries_for_job(
            self.job_id, date_from=date_from, date_to=date_to
        )
        self._populate_table()
        self._update_summary()

    def _populate_table(self):
        """Fill the table with labor entries."""
        self.table.setRowCount(len(self._entries))
        for row, entry in enumerate(self._entries):
            # Parse date from start_time
            date_str = ""
            if entry.start_time:
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(str(entry.start_time))
                    date_str = dt.strftime("%Y-%m-%d %H:%M")
                except (ValueError, TypeError):
                    date_str = str(entry.start_time)[:16]

            cost = (entry.hours or 0) * (entry.rate_per_hour or 0)

            cells = [
                QTableWidgetItem(date_str),
                QTableWidgetItem(entry.user_name or ""),
                QTableWidgetItem(entry.sub_task_category or ""),
                QTableWidgetItem(f"{entry.hours:.2f}" if entry.hours else "—"),
                QTableWidgetItem(
                    format_currency(entry.rate_per_hour)
                    if entry.rate_per_hour else "—"
                ),
                QTableWidgetItem(format_currency(cost)),
                QTableWidgetItem(entry.description or ""),
                QTableWidgetItem("Yes" if entry.is_overtime else ""),
            ]
            for col, cell in enumerate(cells):
                if col in (3, 4, 5):  # Right-align numbers
                    cell.setTextAlignment(
                        Qt.AlignRight | Qt.AlignVCenter
                    )
                if entry.is_overtime:
                    cell.setForeground(Qt.yellow)
                self.table.setItem(row, col, cell)

    def _update_summary(self):
        """Update the summary section."""
        summary = self.repo.get_labor_summary_for_job(self.job_id)
        self.total_hours_label.setText(
            f"Total Hours: {summary['total_hours']:.2f}"
        )
        self.total_cost_label.setText(
            f"Total Cost: {format_currency(summary['total_cost'])}"
        )
        self.entry_count_label.setText(
            f"Entries: {summary['entry_count']}"
        )

        # Category breakdown
        by_cat = summary.get("by_category", [])
        if by_cat:
            parts = []
            for cat in by_cat:
                parts.append(
                    f"{cat['category']}: {cat['hours']:.1f}h"
                )
            self.category_summary_label.setText(
                "By Category: " + " | ".join(parts)
            )
        else:
            self.category_summary_label.setText("")

    def _selected_entry(self) -> LaborEntry | None:
        """Return the currently selected entry, or None."""
        rows = self.table.selectionModel().selectedRows()
        if rows:
            return self._entries[rows[0].row()]
        return None

    def _on_add_entry(self):
        """Open manual entry dialog."""
        from wired_part.ui.dialogs.labor_entry_dialog import LaborEntryDialog
        dialog = LaborEntryDialog(
            self.repo, job_id=self.job_id, parent=self
        )
        if dialog.exec():
            self._refresh()

    def _on_edit_entry(self):
        """Edit selected entry."""
        entry = self._selected_entry()
        if not entry:
            QMessageBox.information(
                self, "No Selection", "Select an entry to edit."
            )
            return
        full_entry = self.repo.get_labor_entry_by_id(entry.id)
        if not full_entry:
            return
        from wired_part.ui.dialogs.labor_entry_dialog import LaborEntryDialog
        dialog = LaborEntryDialog(
            self.repo, entry=full_entry, parent=self
        )
        if dialog.exec():
            self._refresh()

    def _on_delete_entry(self):
        """Delete selected entry."""
        entry = self._selected_entry()
        if not entry:
            QMessageBox.information(
                self, "No Selection", "Select an entry to delete."
            )
            return
        reply = QMessageBox.question(
            self, "Delete Entry",
            f"Delete this labor entry?\n"
            f"{entry.user_name} — {entry.hours:.2f}h — "
            f"{entry.sub_task_category}\n"
            "This cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.repo.delete_labor_entry(entry.id)
            self._refresh()
