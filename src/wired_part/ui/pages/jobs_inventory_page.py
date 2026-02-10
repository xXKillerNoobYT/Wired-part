"""Jobs Inventory page — dynamic sub-tabs per active/on-hold job with parts."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QTabBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from wired_part.database.repository import Repository
from wired_part.utils.formatters import format_currency

# Color palette for job statuses (tab background colors)
JOB_STATUS_COLORS = {
    "active": QColor("#a6e3a1"),      # Green
    "on_hold": QColor("#fab387"),      # Orange/Peach
    "completed": QColor("#a6adc8"),    # Gray
    "cancelled": QColor("#f38ba8"),    # Red
}

# Text colors for status labels
JOB_STATUS_TEXT_COLORS = {
    "active": "#a6e3a1",
    "on_hold": "#fab387",
    "completed": "#a6adc8",
    "cancelled": "#f38ba8",
}


class _JobInventoryTab(QWidget):
    """Single job's parts inventory view."""

    COLUMNS = [
        "Part #", "Description", "Qty Used", "Unit Cost",
        "Total Cost", "Notes",
    ]

    def __init__(self, repo: Repository, job_id: int, job_label: str,
                 job_status: str):
        super().__init__()
        self.repo = repo
        self.job_id = job_id
        self.job_label = job_label
        self.job_status = job_status
        self._parts: list = []
        self._setup_ui()
        self.refresh()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # ── Header ──────────────────────────────────────────────
        header = QHBoxLayout()
        title = QLabel(f"Parts for {self.job_label}")
        title.setStyleSheet("font-size: 13px; font-weight: bold;")
        header.addWidget(title)

        # Status badge
        status_color = JOB_STATUS_TEXT_COLORS.get(
            self.job_status, "#cdd6f4"
        )
        self.status_label = QLabel(self.job_status.replace("_", " ").title())
        self.status_label.setStyleSheet(
            f"color: {status_color}; font-weight: bold; "
            f"padding: 2px 8px; border: 1px solid {status_color}; "
            f"border-radius: 4px;"
        )
        header.addWidget(self.status_label)

        self.summary_label = QLabel("")
        self.summary_label.setStyleSheet("color: #a6adc8;")
        header.addStretch()
        header.addWidget(self.summary_label)
        layout.addLayout(header)

        # ── Search ──────────────────────────────────────────────
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search this job's parts...")
        self.search_input.textChanged.connect(self._on_search)
        layout.addWidget(self.search_input)

        # ── Table ───────────────────────────────────────────────
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
            1, QHeaderView.Stretch
        )
        layout.addWidget(self.table)

    def refresh(self):
        """Reload parts for this job."""
        self._parts = self.repo.get_job_parts(self.job_id)
        self._on_search()

    def _on_search(self):
        """Filter parts by search text."""
        search = self.search_input.text().strip().lower()
        if search:
            filtered = [
                p for p in self._parts
                if search in p.part_number.lower()
                or search in p.part_description.lower()
                or search in (p.notes or "").lower()
            ]
        else:
            filtered = self._parts
        self._populate_table(filtered)

    def _populate_table(self, parts):
        """Fill table with job parts."""
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(parts))

        total_cost = 0.0
        total_qty = 0

        for row, jp in enumerate(parts):
            cost = jp.quantity_used * jp.unit_cost_at_use
            total_cost += cost
            total_qty += jp.quantity_used

            cells = [
                QTableWidgetItem(jp.part_number),
                QTableWidgetItem(jp.part_description),
                self._num_item(jp.quantity_used),
                QTableWidgetItem(format_currency(jp.unit_cost_at_use)),
                QTableWidgetItem(format_currency(cost)),
                QTableWidgetItem(jp.notes or ""),
            ]

            for col, cell in enumerate(cells):
                self.table.setItem(row, col, cell)

        self.table.setSortingEnabled(True)
        self.summary_label.setText(
            f"{len(parts)} parts  |  {total_qty} total items  |  "
            f"Cost: {format_currency(total_cost)}"
        )

    @staticmethod
    def _num_item(value: int) -> QTableWidgetItem:
        """Create a right-aligned numeric table item for proper sorting."""
        item = QTableWidgetItem()
        item.setData(Qt.ItemDataRole.DisplayRole, value)
        item.setTextAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        return item


class JobsInventoryPage(QWidget):
    """Container page with dynamic sub-tabs per active/on-hold job.

    Tabs are color-coded by job status:
    - Active  = Green tab
    - On Hold = Orange/Peach tab
    """

    def __init__(self, repo: Repository):
        super().__init__()
        self.repo = repo
        self._job_tabs: dict[int, _JobInventoryTab] = {}
        self._setup_ui()
        self.refresh()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # ── Header ──────────────────────────────────────────────
        header = QHBoxLayout()
        header.setContentsMargins(8, 4, 8, 4)
        title = QLabel("Jobs Inventory")
        title.setStyleSheet("font-size: 14px; font-weight: bold;")
        header.addWidget(title)

        # Legend
        legend = QHBoxLayout()
        legend.setSpacing(16)

        active_dot = QLabel("\u25CF Active")
        active_dot.setStyleSheet(
            f"color: {JOB_STATUS_TEXT_COLORS['active']}; font-weight: bold;"
        )
        legend.addWidget(active_dot)

        hold_dot = QLabel("\u25CF On Hold")
        hold_dot.setStyleSheet(
            f"color: {JOB_STATUS_TEXT_COLORS['on_hold']}; font-weight: bold;"
        )
        legend.addWidget(hold_dot)

        header.addStretch()
        header.addLayout(legend)

        self.job_count_label = QLabel("")
        self.job_count_label.setStyleSheet("color: #a6adc8; margin-left: 16px;")
        header.addWidget(self.job_count_label)
        layout.addLayout(header)

        # ── Job sub-tabs ────────────────────────────────────────
        self.job_tabs = QTabWidget()
        self.job_tabs.currentChanged.connect(self._on_job_tab_changed)
        layout.addWidget(self.job_tabs)

        # ── Empty state ─────────────────────────────────────────
        self.empty_label = QLabel(
            "No active or on-hold jobs with parts.\n\n"
            "Assign parts to jobs in the Job Tracking > Jobs tab."
        )
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setStyleSheet(
            "color: #6c7086; font-size: 12px; padding: 40px;"
        )
        layout.addWidget(self.empty_label)
        self.empty_label.setVisible(False)

    def refresh(self):
        """Rebuild job tabs from database."""
        # Get active and on-hold jobs
        active_jobs = self.repo.get_all_jobs(status="active")
        hold_jobs = self.repo.get_all_jobs(status="on_hold")

        # Sort: active first, then on_hold; within each group by priority
        all_jobs = []
        for job in active_jobs:
            all_jobs.append(job)
        for job in hold_jobs:
            all_jobs.append(job)

        current_job_ids = {j.id for j in all_jobs}
        existing_ids = set(self._job_tabs.keys())

        # Remove tabs for jobs that are no longer active/on_hold
        for job_id in existing_ids - current_job_ids:
            tab = self._job_tabs.pop(job_id)
            idx = self.job_tabs.indexOf(tab)
            if idx >= 0:
                self.job_tabs.removeTab(idx)

        # Rebuild all tabs in correct order
        # Clear and re-add to maintain sort order
        self.job_tabs.blockSignals(True)

        # Remove all tabs but keep widget references
        while self.job_tabs.count() > 0:
            self.job_tabs.removeTab(0)

        # Re-add in order
        new_tab_map = {}
        for job in all_jobs:
            label = f"{job.job_number} — {job.name}"
            if job.customer:
                label += f" ({job.customer})"

            if job.id in self._job_tabs:
                tab = self._job_tabs[job.id]
                tab.job_status = job.status
                tab.refresh()
            else:
                tab = _JobInventoryTab(
                    self.repo, job.id, label, job.status
                )

            new_tab_map[job.id] = tab
            idx = self.job_tabs.addTab(tab, label)

            # Color-code the tab
            color = JOB_STATUS_COLORS.get(job.status)
            if color:
                self.job_tabs.tabBar().setTabTextColor(idx, color)

        self._job_tabs = new_tab_map
        self.job_tabs.blockSignals(False)

        has_jobs = len(all_jobs) > 0
        self.job_tabs.setVisible(has_jobs)
        self.empty_label.setVisible(not has_jobs)

        active_count = len(active_jobs)
        hold_count = len(hold_jobs)
        self.job_count_label.setText(
            f"{active_count} active, {hold_count} on hold"
        )

    def _on_job_tab_changed(self, index: int):
        """Refresh the selected job tab."""
        widget = self.job_tabs.widget(index)
        if hasattr(widget, "refresh"):
            widget.refresh()
