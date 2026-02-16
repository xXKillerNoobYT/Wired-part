"""pytest-qt tests for the Dashboard Page."""

import pytest

from wired_part.database.models import Job, Truck
from wired_part.ui.pages.dashboard_page import DashboardPage


class TestDashboardPage:
    def test_creates_without_crash(self, qtbot, repo, admin_user):
        page = DashboardPage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        assert page is not None

    def test_has_summary_cards(self, qtbot, repo, admin_user):
        page = DashboardPage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        assert page.parts_card is not None
        assert page.jobs_card is not None
        assert page.trucks_card is not None

    def test_refresh_with_empty_db(self, qtbot, repo, admin_user):
        page = DashboardPage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        page.refresh()

    def test_refresh_with_data(
        self, qtbot, repo, admin_user, sample_parts, sample_job
    ):
        page = DashboardPage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        page.refresh()

    def test_clock_out_btn_disabled_when_not_clocked_in(
        self, qtbot, repo, admin_user
    ):
        page = DashboardPage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        assert not page.quick_clock_out_btn.isEnabled()

    def test_value_card_not_hidden_for_admin(self, qtbot, repo, admin_user):
        """Admin has show_dollar_values permission → card not hidden."""
        page = DashboardPage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        assert not page.value_card.isHidden()

    def test_value_card_hidden_for_worker(self, qtbot, repo, worker_user):
        """Worker does NOT have show_dollar_values → card hidden."""
        page = DashboardPage(repo, current_user=worker_user)
        qtbot.addWidget(page)
        assert page.value_card.isHidden()
