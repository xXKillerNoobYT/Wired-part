"""Office page — billing reports, timesheet reports, labor overview.

This tab consolidates office-only tasks that are separate from
day-to-day field work: generating billing reports, reviewing
timesheets, and viewing labor cost summaries.

Quick filters: This Period, Last Period, Last 3 Months, YTD, 1 Year,
5 Year, 10 Year — shared across all three sub-tabs.
"""

from datetime import datetime, timedelta

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
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from wired_part.database.models import User
from wired_part.database.repository import Repository
from wired_part.utils.formatters import format_currency


# ── Quick-filter date range definitions ──────────────────────────

_QUICK_FILTERS = [
    "This Period",
    "Last Period",
    "Last 3 Months",
    "Year to Date",
    "1 Year",
    "5 Year",
    "10 Year",
]


def _quick_filter_dates(label: str) -> tuple[QDate, QDate]:
    """Return (from_date, to_date) for the given quick-filter label."""
    today = QDate.currentDate()

    if label == "This Period":
        # Current month
        return QDate(today.year(), today.month(), 1), today

    if label == "Last Period":
        first_this = QDate(today.year(), today.month(), 1)
        last_month_end = first_this.addDays(-1)
        return QDate(
            last_month_end.year(), last_month_end.month(), 1
        ), last_month_end

    if label == "Last 3 Months":
        return today.addMonths(-3), today

    if label == "Year to Date":
        return QDate(today.year(), 1, 1), today

    if label == "1 Year":
        return today.addYears(-1), today

    if label == "5 Year":
        return today.addYears(-5), today

    if label == "10 Year":
        return today.addYears(-10), today

    # Fallback — current year
    return QDate(today.year(), 1, 1), today


class OfficePage(QWidget):
    """Office hub with sub-tabs for billing, timesheets, and labor costs."""

    def __init__(self, repo: Repository, current_user: User, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.current_user = current_user
        self._perms: set[str] = set()
        if current_user:
            self._perms = repo.get_user_permissions(current_user.id)
        self._can_see_dollars = "show_dollar_values" in self._perms
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        title = QLabel("Office")
        title.setStyleSheet("font-size: 20px; font-weight: bold; padding: 8px;")
        layout.addWidget(title)

        self.sub_tabs = QTabWidget()

        # Sub-tab 1: Billing Reports
        self.billing_widget = QWidget()
        self._setup_billing_tab()
        self.sub_tabs.addTab(self.billing_widget, "Billing Reports")

        # Sub-tab 2: Timesheet Reports
        self.timesheet_widget = QWidget()
        self._setup_timesheet_tab()
        self.sub_tabs.addTab(self.timesheet_widget, "Timesheet Reports")

        # Sub-tab 3: Labor Cost Summary
        self.labor_cost_widget = QWidget()
        self._setup_labor_cost_tab()
        self.sub_tabs.addTab(self.labor_cost_widget, "Labor Cost Summary")

        layout.addWidget(self.sub_tabs)

    # ── Shared: quick-filter row builder ──────────────────────────

    def _build_quick_filters(self, on_click_callback) -> QHBoxLayout:
        """Create a row of quick-filter buttons.

        Returns the layout.  The callback receives (from_date, to_date)
        as QDate objects.
        """
        row = QHBoxLayout()
        row.addWidget(QLabel("Quick:"))
        for label in _QUICK_FILTERS:
            btn = QPushButton(label)
            btn.setStyleSheet("padding: 4px 10px;")
            btn.setToolTip(f"Set date range to {label}")
            btn.clicked.connect(
                lambda checked=False, lbl=label, cb=on_click_callback:
                    cb(lbl)
            )
            row.addWidget(btn)
        row.addStretch()
        return row

    # ── Billing Reports Sub-Tab ──────────────────────────────────

    def _setup_billing_tab(self):
        layout = QVBoxLayout(self.billing_widget)

        # Row 1: Quick filters
        layout.addLayout(
            self._build_quick_filters(self._billing_quick_filter)
        )

        # Row 2: Filters + Generate
        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("Job:"))
        self.billing_job_filter = QComboBox()
        self.billing_job_filter.addItem("All Jobs", None)
        for job in self.repo.get_all_jobs():
            bro_str = f" [{job.bill_out_rate}]" if job.bill_out_rate else ""
            self.billing_job_filter.addItem(
                f"{job.job_number} — {job.name}{bro_str}", job.id
            )
        toolbar.addWidget(self.billing_job_filter, 1)

        toolbar.addWidget(QLabel("BRO:"))
        self.billing_bro_filter = QComboBox()
        self.billing_bro_filter.addItem("All", None)
        from wired_part.config import Config
        for cat in Config.get_bro_categories():
            self.billing_bro_filter.addItem(cat, cat)
        self.billing_bro_filter.addItem("(None)", "")
        toolbar.addWidget(self.billing_bro_filter)

        toolbar.addWidget(QLabel("From:"))
        self.billing_date_from = QDateEdit()
        self.billing_date_from.setCalendarPopup(True)
        self.billing_date_from.setDisplayFormat("yyyy-MM-dd")
        toolbar.addWidget(self.billing_date_from)

        toolbar.addWidget(QLabel("To:"))
        self.billing_date_to = QDateEdit()
        self.billing_date_to.setCalendarPopup(True)
        self.billing_date_to.setDisplayFormat("yyyy-MM-dd")
        toolbar.addWidget(self.billing_date_to)

        gen_btn = QPushButton("Generate Report")
        gen_btn.setMinimumHeight(30)
        gen_btn.clicked.connect(self._generate_billing_report)
        toolbar.addWidget(gen_btn)

        layout.addLayout(toolbar)

        # Default: Year to Date
        ytd_from, ytd_to = _quick_filter_dates("Year to Date")
        self.billing_date_from.setDate(ytd_from)
        self.billing_date_to.setDate(ytd_to)

        # Billing table
        self.billing_table = QTableWidget()
        self.billing_table.setColumnCount(5)
        self.billing_table.setHorizontalHeaderLabels([
            "Job", "BRO", "Hours", "Parts Cost", "Total Cost",
        ])
        self.billing_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.billing_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.billing_table.setAlternatingRowColors(True)
        self.billing_table.setSortingEnabled(True)
        self.billing_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.billing_table, 1)

        # Summary
        summary = QHBoxLayout()
        self.billing_total_label = QLabel(
            "Total: $0.00" if self._can_see_dollars else "Total: \u2014"
        )
        self.billing_total_label.setStyleSheet(
            "font-weight: bold; font-size: 16px;"
        )
        summary.addWidget(self.billing_total_label)
        self.billing_hours_label = QLabel("Hours: 0.00")
        self.billing_hours_label.setStyleSheet(
            "font-weight: bold; font-size: 14px; margin-left: 20px;"
        )
        summary.addWidget(self.billing_hours_label)
        summary.addStretch()
        layout.addLayout(summary)

    def _billing_quick_filter(self, label: str):
        """Apply a quick date filter and auto-generate billing report."""
        d_from, d_to = _quick_filter_dates(label)
        self.billing_date_from.setDate(d_from)
        self.billing_date_to.setDate(d_to)
        self._generate_billing_report()

    def _generate_billing_report(self):
        """Generate billing report grouped by job with BRO category.

        Uses the *entry-level* BRO snapshot so historical records are
        accurate even after a job's BRO has changed.
        """
        date_from = self.billing_date_from.date().toString("yyyy-MM-dd")
        date_to = self.billing_date_to.date().toString("yyyy-MM-dd")
        job_id = self.billing_job_filter.currentData()
        bro_filter = self.billing_bro_filter.currentData()

        jobs = self.repo.get_all_jobs()
        if job_id:
            jobs = [j for j in jobs if j.id == job_id]

        # Filter by BRO category if selected (uses current job BRO)
        if bro_filter is not None:
            jobs = [j for j in jobs if (j.bill_out_rate or "") == bro_filter]

        rows = []
        for job in jobs:
            entries = self.repo.get_labor_entries_for_job(
                job.id, date_from=date_from, date_to=date_to
            )
            total_hours = sum(e.hours or 0 for e in entries)
            if total_hours == 0:
                continue

            # Use entry-level BRO snapshot; fallback to job's current BRO
            entry_bros = set(
                e.bill_out_rate for e in entries if e.bill_out_rate
            )
            bro_display = (
                ", ".join(sorted(entry_bros))
                if entry_bros
                else (job.bill_out_rate or "")
            )

            parts_cost = self._get_job_parts_cost(job.id)

            rows.append({
                "job_label": f"{job.job_number} — {job.name}",
                "bro": bro_display,
                "hours": total_hours,
                "parts_cost": parts_cost,
                "total": parts_cost,
            })

        # Sort: newest / most hours on top
        rows.sort(key=lambda r: r["hours"], reverse=True)

        self.billing_table.setSortingEnabled(False)
        self.billing_table.setRowCount(len(rows))
        grand_total = 0
        grand_hours = 0
        for i, row in enumerate(rows):
            self.billing_table.setItem(
                i, 0, QTableWidgetItem(row["job_label"])
            )

            bro_item = QTableWidgetItem(row["bro"] or "—")
            bro_item.setTextAlignment(Qt.AlignCenter)
            if row["bro"]:
                bro_item.setForeground(Qt.cyan)
            self.billing_table.setItem(i, 1, bro_item)

            hrs_item = QTableWidgetItem(f"{row['hours']:.2f}")
            hrs_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.billing_table.setItem(i, 2, hrs_item)

            parts_item = QTableWidgetItem(
                format_currency(row["parts_cost"])
                if self._can_see_dollars else "\u2014"
            )
            parts_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.billing_table.setItem(i, 3, parts_item)

            total_item = QTableWidgetItem(
                format_currency(row["total"])
                if self._can_see_dollars else "\u2014"
            )
            total_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            total_item.setForeground(Qt.green)
            self.billing_table.setItem(i, 4, total_item)

            grand_total += row["total"]
            grand_hours += row["hours"]

        self.billing_table.setSortingEnabled(True)
        self.billing_total_label.setText(
            f"Parts Total: {format_currency(grand_total)}"
            if self._can_see_dollars
            else "Parts Total: \u2014"
        )
        self.billing_hours_label.setText(f"Total Hours: {grand_hours:.2f}")

    def _get_job_parts_cost(self, job_id: int) -> float:
        """Sum up the cost of parts consumed on a job."""
        try:
            job_parts = self.repo.get_job_parts(job_id)
            return sum(
                (jp.unit_cost_at_use or 0) * (jp.quantity_used or 0)
                for jp in job_parts
            )
        except Exception:
            return 0.0

    # ── Timesheet Reports Sub-Tab ────────────────────────────────

    def _setup_timesheet_tab(self):
        layout = QVBoxLayout(self.timesheet_widget)

        # Row 1: Quick filters
        layout.addLayout(
            self._build_quick_filters(self._ts_quick_filter)
        )

        # Row 2: Filters + Generate
        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("User:"))
        self.ts_user_filter = QComboBox()
        self.ts_user_filter.addItem("All Users", None)
        for user in self.repo.get_all_users():
            self.ts_user_filter.addItem(user.display_name, user.id)
        toolbar.addWidget(self.ts_user_filter, 1)

        toolbar.addWidget(QLabel("From:"))
        self.ts_date_from = QDateEdit()
        self.ts_date_from.setCalendarPopup(True)
        self.ts_date_from.setDisplayFormat("yyyy-MM-dd")
        toolbar.addWidget(self.ts_date_from)

        toolbar.addWidget(QLabel("To:"))
        self.ts_date_to = QDateEdit()
        self.ts_date_to.setCalendarPopup(True)
        self.ts_date_to.setDisplayFormat("yyyy-MM-dd")
        toolbar.addWidget(self.ts_date_to)

        gen_btn = QPushButton("Generate Timesheet")
        gen_btn.setMinimumHeight(30)
        gen_btn.clicked.connect(self._generate_timesheet_report)
        toolbar.addWidget(gen_btn)

        layout.addLayout(toolbar)

        # Default: Year to Date
        ytd_from, ytd_to = _quick_filter_dates("Year to Date")
        self.ts_date_from.setDate(ytd_from)
        self.ts_date_to.setDate(ytd_to)

        # Timesheet table — includes BRO column
        self.ts_table = QTableWidget()
        self.ts_table.setColumnCount(7)
        self.ts_table.setHorizontalHeaderLabels([
            "Date", "User", "Job", "BRO", "Category", "Hours", "Overtime",
        ])
        self.ts_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.ts_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.ts_table.setAlternatingRowColors(True)
        self.ts_table.setSortingEnabled(True)
        self.ts_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.ts_table, 1)

        # Summary
        summary = QHBoxLayout()
        self.ts_total_hours_label = QLabel("Total Hours: 0.00")
        self.ts_total_hours_label.setStyleSheet(
            "font-weight: bold; font-size: 14px;"
        )
        summary.addWidget(self.ts_total_hours_label)

        self.ts_overtime_label = QLabel("Overtime Entries: 0")
        self.ts_overtime_label.setStyleSheet("color: #fab387;")
        summary.addWidget(self.ts_overtime_label)

        self.ts_entry_count_label = QLabel("Entries: 0")
        summary.addWidget(self.ts_entry_count_label)

        summary.addStretch()
        layout.addLayout(summary)

    def _ts_quick_filter(self, label: str):
        """Apply a quick date filter and auto-generate timesheet."""
        d_from, d_to = _quick_filter_dates(label)
        self.ts_date_from.setDate(d_from)
        self.ts_date_to.setDate(d_to)
        self._generate_timesheet_report()

    def _generate_timesheet_report(self):
        """Generate timesheet report for selected user/period."""
        date_from = self.ts_date_from.date().toString("yyyy-MM-dd")
        date_to = self.ts_date_to.date().toString("yyyy-MM-dd")
        user_id = self.ts_user_filter.currentData()

        all_entries = []
        for job in self.repo.get_all_jobs():
            entries = self.repo.get_labor_entries_for_job(
                job.id, date_from=date_from, date_to=date_to
            )
            all_entries.extend(entries)

        # Filter by user if selected
        if user_id:
            all_entries = [e for e in all_entries if e.user_id == user_id]

        # Sort by date descending (newest on top)
        all_entries.sort(
            key=lambda e: str(e.start_time or ""), reverse=True
        )

        self.ts_table.setSortingEnabled(False)
        self.ts_table.setRowCount(len(all_entries))
        total_hours = 0
        overtime_count = 0

        for row, entry in enumerate(all_entries):
            date_str = ""
            if entry.start_time:
                try:
                    dt = datetime.fromisoformat(str(entry.start_time))
                    date_str = dt.strftime("%Y-%m-%d %H:%M")
                except (ValueError, TypeError):
                    date_str = str(entry.start_time)[:16]

            hrs = entry.hours or 0
            total_hours += hrs
            is_ot = entry.is_overtime

            cells = [
                QTableWidgetItem(date_str),
                QTableWidgetItem(entry.user_name or ""),
                QTableWidgetItem(entry.job_number or ""),
                QTableWidgetItem(entry.bill_out_rate or ""),
                QTableWidgetItem(entry.sub_task_category or ""),
                QTableWidgetItem(f"{hrs:.2f}"),
                QTableWidgetItem("YES" if is_ot else ""),
            ]
            for col, cell in enumerate(cells):
                if col == 5:  # Hours column
                    cell.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                if col == 3 and entry.bill_out_rate:  # BRO column
                    cell.setForeground(Qt.cyan)
                    cell.setTextAlignment(Qt.AlignCenter)
                if is_ot:
                    cell.setForeground(Qt.yellow)
                self.ts_table.setItem(row, col, cell)

            if is_ot:
                overtime_count += 1

        self.ts_table.setSortingEnabled(True)
        self.ts_total_hours_label.setText(f"Total Hours: {total_hours:.2f}")
        self.ts_overtime_label.setText(f"Overtime Entries: {overtime_count}")
        self.ts_entry_count_label.setText(f"Entries: {len(all_entries)}")

    # ── Labor Cost Summary Sub-Tab ───────────────────────────────

    def _setup_labor_cost_tab(self):
        layout = QVBoxLayout(self.labor_cost_widget)

        # Row 1: Quick filters
        layout.addLayout(
            self._build_quick_filters(self._cost_quick_filter)
        )

        # Row 2: Filters + Generate
        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("Period:"))
        self.cost_date_from = QDateEdit()
        self.cost_date_from.setCalendarPopup(True)
        self.cost_date_from.setDisplayFormat("yyyy-MM-dd")
        toolbar.addWidget(self.cost_date_from)

        toolbar.addWidget(QLabel("to"))
        self.cost_date_to = QDateEdit()
        self.cost_date_to.setCalendarPopup(True)
        self.cost_date_to.setDisplayFormat("yyyy-MM-dd")
        toolbar.addWidget(self.cost_date_to)

        gen_btn = QPushButton("Generate Summary")
        gen_btn.setMinimumHeight(30)
        gen_btn.clicked.connect(self._generate_labor_cost_summary)
        toolbar.addWidget(gen_btn)

        layout.addLayout(toolbar)

        # Default: Year to Date
        ytd_from, ytd_to = _quick_filter_dates("Year to Date")
        self.cost_date_from.setDate(ytd_from)
        self.cost_date_to.setDate(ytd_to)

        # Per-user cost table
        self.cost_table = QTableWidget()
        self.cost_table.setColumnCount(5)
        self.cost_table.setHorizontalHeaderLabels([
            "User", "Total Hours", "Regular Hours",
            "Overtime Hours", "Jobs Worked",
        ])
        self.cost_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.cost_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.cost_table.setAlternatingRowColors(True)
        self.cost_table.setSortingEnabled(True)
        self.cost_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.cost_table, 1)

        # Summary
        summary = QHBoxLayout()
        self.cost_total_label = QLabel("Company Total Hours: 0.00")
        self.cost_total_label.setStyleSheet(
            "font-weight: bold; font-size: 16px;"
        )
        summary.addWidget(self.cost_total_label)
        summary.addStretch()
        layout.addLayout(summary)

    def _cost_quick_filter(self, label: str):
        """Apply a quick date filter and auto-generate labor cost summary."""
        d_from, d_to = _quick_filter_dates(label)
        self.cost_date_from.setDate(d_from)
        self.cost_date_to.setDate(d_to)
        self._generate_labor_cost_summary()

    def _generate_labor_cost_summary(self):
        """Generate per-user labor summary for the period."""
        date_from = self.cost_date_from.date().toString("yyyy-MM-dd")
        date_to = self.cost_date_to.date().toString("yyyy-MM-dd")

        # Collect all labor entries
        all_entries = []
        for job in self.repo.get_all_jobs():
            entries = self.repo.get_labor_entries_for_job(
                job.id, date_from=date_from, date_to=date_to
            )
            all_entries.extend(entries)

        # Group by user
        user_data: dict[int, dict] = {}
        for entry in all_entries:
            uid = entry.user_id or 0
            if uid not in user_data:
                user_data[uid] = {
                    "name": entry.user_name or "Unknown",
                    "total_hours": 0,
                    "regular_hours": 0,
                    "overtime_hours": 0,
                    "jobs": set(),
                }
            hrs = entry.hours or 0
            user_data[uid]["total_hours"] += hrs
            if entry.is_overtime:
                user_data[uid]["overtime_hours"] += hrs
            else:
                user_data[uid]["regular_hours"] += hrs
            if entry.job_id:
                user_data[uid]["jobs"].add(entry.job_id)

        # Sort by most hours (top contributors first)
        rows = sorted(
            user_data.values(),
            key=lambda x: x["total_hours"],
            reverse=True,
        )
        self.cost_table.setSortingEnabled(False)
        self.cost_table.setRowCount(len(rows))
        company_total = 0

        for i, row in enumerate(rows):
            self.cost_table.setItem(i, 0, QTableWidgetItem(row["name"]))

            total_item = QTableWidgetItem(f"{row['total_hours']:.2f}")
            total_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.cost_table.setItem(i, 1, total_item)

            reg_item = QTableWidgetItem(f"{row['regular_hours']:.2f}")
            reg_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.cost_table.setItem(i, 2, reg_item)

            ot_item = QTableWidgetItem(f"{row['overtime_hours']:.2f}")
            ot_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            if row["overtime_hours"] > 0:
                ot_item.setForeground(Qt.yellow)
            self.cost_table.setItem(i, 3, ot_item)

            jobs_item = QTableWidgetItem(str(len(row["jobs"])))
            jobs_item.setTextAlignment(Qt.AlignCenter)
            self.cost_table.setItem(i, 4, jobs_item)

            company_total += row["total_hours"]

        self.cost_table.setSortingEnabled(True)
        self.cost_total_label.setText(
            f"Company Total Hours: {company_total:.2f}"
        )

    def refresh(self):
        """Refresh data when tab is selected."""
        pass  # Reports are generated on-demand via quick filters / buttons
