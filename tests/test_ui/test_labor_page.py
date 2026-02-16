"""pytest-qt tests for the Labor Page widget."""

import pytest
from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import QTableWidget

from wired_part.ui.pages.labor_page import LaborPage, _quick_filter_dates


class TestQuickFilterDates:
    """Test the date range calculation logic (no Qt widgets needed)."""

    def test_this_period_starts_at_month_begin(self):
        d_from, d_to = _quick_filter_dates("This Period")
        today = QDate.currentDate()
        assert d_from.day() == 1
        assert d_from.month() == today.month()
        assert d_to == today

    def test_last_period_is_previous_month(self):
        d_from, d_to = _quick_filter_dates("Last Period")
        today = QDate.currentDate()
        first_this = QDate(today.year(), today.month(), 1)
        last_month_end = first_this.addDays(-1)
        assert d_to == last_month_end
        assert d_from.month() == last_month_end.month()
        assert d_from.day() == 1

    def test_year_to_date_starts_jan_1(self):
        d_from, d_to = _quick_filter_dates("Year to Date")
        today = QDate.currentDate()
        assert d_from == QDate(today.year(), 1, 1)
        assert d_to == today

    def test_unknown_filter_falls_back_to_year(self):
        d_from, d_to = _quick_filter_dates("NonExistent")
        today = QDate.currentDate()
        assert d_from == QDate(today.year(), 1, 1)


class TestLaborPageWidget:
    """Test the LaborPage widget instantiation and behavior."""

    def test_creates_without_crash(self, qtbot, repo, admin_user):
        """LaborPage can be instantiated with a real repo."""
        page = LaborPage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        assert page.table is not None
        assert isinstance(page.table, QTableWidget)

    def test_has_correct_columns(self, qtbot, repo, admin_user):
        """Table has the expected column headers."""
        page = LaborPage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        headers = [
            page.table.horizontalHeaderItem(i).text()
            for i in range(page.table.columnCount())
        ]
        assert headers == [
            "Date", "User", "Job", "Category", "Hours", "Description",
        ]

    def test_empty_table_on_no_entries(self, qtbot, repo, admin_user):
        """With no labor entries, table should be empty."""
        page = LaborPage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        assert page.table.rowCount() == 0

    def test_summary_shows_zero_on_empty(self, qtbot, repo, admin_user):
        """Summary labels show zeros when no data."""
        page = LaborPage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        assert "0.00" in page.total_hours_label.text()
        assert "0" in page.entry_count_label.text()

    def test_clock_in_button_enabled_by_default(
        self, qtbot, repo, admin_user
    ):
        """Clock In button should be enabled when not clocked in."""
        page = LaborPage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        assert page.clock_in_btn.isEnabled()
        assert not page.clock_out_btn.isEnabled()

    def test_quick_filter_buttons_exist(self, qtbot, repo, admin_user):
        """Quick filter buttons should be present."""
        page = LaborPage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        buttons = page.findChildren(
            type(page.clock_in_btn), ""  # QPushButton
        )
        labels = [b.text() for b in buttons]
        assert "This Period" in labels
        assert "Year to Date" in labels

    def test_refresh_does_not_crash(self, qtbot, repo, admin_user):
        """Calling refresh on an empty DB doesn't crash."""
        page = LaborPage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        page.refresh()
        assert page.table.rowCount() == 0

    def test_job_filter_populated(
        self, qtbot, repo, admin_user, sample_job
    ):
        """Job filter combo has 'All Jobs' plus created jobs."""
        page = LaborPage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        assert page.job_filter.count() >= 2  # "All Jobs" + sample_job
        assert page.job_filter.itemText(0) == "All Jobs"
