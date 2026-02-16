"""Tests for domain-specific dashboard pages (Phase C)."""

import pytest
from PySide6.QtWidgets import QListWidget, QTableWidget


# ── Warehouse Dashboard ──────────────────────────────────────

class TestWarehouseDashboard:
    def test_creates_without_crash(self, qtbot, repo, admin_user):
        from wired_part.ui.pages.warehouse_dashboard_page import (
            WarehouseDashboardPage,
        )
        page = WarehouseDashboardPage(repo, admin_user)
        qtbot.addWidget(page)
        assert page is not None

    def test_has_summary_cards(self, qtbot, repo, admin_user):
        from wired_part.ui.pages.warehouse_dashboard_page import (
            WarehouseDashboardPage,
        )
        page = WarehouseDashboardPage(repo, admin_user)
        qtbot.addWidget(page)
        assert page.total_stock_card is not None
        assert page.total_value_card is not None
        assert page.low_stock_card is not None
        assert page.pending_incoming_card is not None
        assert page.pending_orders_card is not None

    def test_has_lists(self, qtbot, repo, admin_user):
        from wired_part.ui.pages.warehouse_dashboard_page import (
            WarehouseDashboardPage,
        )
        page = WarehouseDashboardPage(repo, admin_user)
        qtbot.addWidget(page)
        assert isinstance(page.alerts_list, QListWidget)
        assert isinstance(page.receiving_list, QListWidget)

    def test_refresh_empty(self, qtbot, repo, admin_user):
        from wired_part.ui.pages.warehouse_dashboard_page import (
            WarehouseDashboardPage,
        )
        page = WarehouseDashboardPage(repo, admin_user)
        qtbot.addWidget(page)
        page.refresh()  # Should not crash with empty data

    def test_lists_have_minimum_height(self, qtbot, repo, admin_user):
        from wired_part.ui.pages.warehouse_dashboard_page import (
            WarehouseDashboardPage,
        )
        page = WarehouseDashboardPage(repo, admin_user)
        qtbot.addWidget(page)
        assert page.alerts_list.minimumHeight() >= 90
        assert page.receiving_list.minimumHeight() >= 90


# ── Jobs Dashboard ───────────────────────────────────────────

class TestJobsDashboard:
    def test_creates_without_crash(self, qtbot, repo, admin_user):
        from wired_part.ui.pages.jobs_dashboard_page import (
            JobsDashboardPage,
        )
        page = JobsDashboardPage(repo, admin_user)
        qtbot.addWidget(page)
        assert page is not None

    def test_has_summary_cards(self, qtbot, repo, admin_user):
        from wired_part.ui.pages.jobs_dashboard_page import (
            JobsDashboardPage,
        )
        page = JobsDashboardPage(repo, admin_user)
        qtbot.addWidget(page)
        assert page.active_jobs_card is not None
        assert page.on_hold_card is not None
        assert page.completed_card is not None
        assert page.labor_hours_card is not None

    def test_has_lists(self, qtbot, repo, admin_user):
        from wired_part.ui.pages.jobs_dashboard_page import (
            JobsDashboardPage,
        )
        page = JobsDashboardPage(repo, admin_user)
        qtbot.addWidget(page)
        assert isinstance(page.my_jobs_list, QListWidget)
        assert isinstance(page.activity_list, QListWidget)

    def test_refresh_empty(self, qtbot, repo, admin_user):
        from wired_part.ui.pages.jobs_dashboard_page import (
            JobsDashboardPage,
        )
        page = JobsDashboardPage(repo, admin_user)
        qtbot.addWidget(page)
        page.refresh()

    def test_refresh_with_data(self, qtbot, repo, admin_user, sample_job):
        from wired_part.ui.pages.jobs_dashboard_page import (
            JobsDashboardPage,
        )
        page = JobsDashboardPage(repo, admin_user)
        qtbot.addWidget(page)
        page.refresh()
        assert page.active_jobs_card.value_label.text() == "1"


# ── Trucks Dashboard ─────────────────────────────────────────

class TestTrucksDashboard:
    def test_creates_without_crash(self, qtbot, repo, admin_user):
        from wired_part.ui.pages.trucks_dashboard_page import (
            TrucksDashboardPage,
        )
        page = TrucksDashboardPage(repo, admin_user)
        qtbot.addWidget(page)
        assert page is not None

    def test_has_summary_cards(self, qtbot, repo, admin_user):
        from wired_part.ui.pages.trucks_dashboard_page import (
            TrucksDashboardPage,
        )
        page = TrucksDashboardPage(repo, admin_user)
        qtbot.addWidget(page)
        assert page.total_trucks_card is not None
        assert page.active_trucks_card is not None
        assert page.total_inv_value_card is not None
        assert page.pending_transfers_card is not None

    def test_has_fleet_table(self, qtbot, repo, admin_user):
        from wired_part.ui.pages.trucks_dashboard_page import (
            TrucksDashboardPage,
        )
        page = TrucksDashboardPage(repo, admin_user)
        qtbot.addWidget(page)
        assert isinstance(page.fleet_table, QTableWidget)

    def test_refresh_empty(self, qtbot, repo, admin_user):
        from wired_part.ui.pages.trucks_dashboard_page import (
            TrucksDashboardPage,
        )
        page = TrucksDashboardPage(repo, admin_user)
        qtbot.addWidget(page)
        page.refresh()


# ── Office Dashboard ─────────────────────────────────────────

class TestOfficeDashboard:
    def test_creates_without_crash(self, qtbot, repo, admin_user):
        from wired_part.ui.pages.office_dashboard_page import (
            OfficeDashboardPage,
        )
        page = OfficeDashboardPage(repo, admin_user)
        qtbot.addWidget(page)
        assert page is not None

    def test_has_summary_cards(self, qtbot, repo, admin_user):
        from wired_part.ui.pages.office_dashboard_page import (
            OfficeDashboardPage,
        )
        page = OfficeDashboardPage(repo, admin_user)
        qtbot.addWidget(page)
        assert page.labor_hours_card is not None
        assert page.parts_cost_card is not None
        assert page.active_jobs_card is not None
        assert page.pending_orders_card is not None

    def test_has_billing_list(self, qtbot, repo, admin_user):
        from wired_part.ui.pages.office_dashboard_page import (
            OfficeDashboardPage,
        )
        page = OfficeDashboardPage(repo, admin_user)
        qtbot.addWidget(page)
        assert isinstance(page.billing_list, QListWidget)

    def test_refresh_empty(self, qtbot, repo, admin_user):
        from wired_part.ui.pages.office_dashboard_page import (
            OfficeDashboardPage,
        )
        page = OfficeDashboardPage(repo, admin_user)
        qtbot.addWidget(page)
        page.refresh()
