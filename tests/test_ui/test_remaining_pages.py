"""pytest-qt tests for remaining UI pages (batch)."""

import pytest
from PySide6.QtWidgets import QTableWidget, QTabWidget

from wired_part.database.models import Job, PurchaseOrder, Truck


class TestIncomingPage:
    def test_creates_without_crash(self, qtbot, repo, admin_user):
        from wired_part.ui.pages.incoming_page import IncomingPage
        page = IncomingPage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        assert page is not None

    def test_has_order_list(self, qtbot, repo, admin_user):
        from wired_part.ui.pages.incoming_page import IncomingPage
        page = IncomingPage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        assert page.order_list is not None

    def test_has_items_table(self, qtbot, repo, admin_user):
        from wired_part.ui.pages.incoming_page import IncomingPage
        page = IncomingPage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        assert page.items_table is not None
        assert page.items_table.columnCount() == 9

    def test_receive_btn_disabled_initially(self, qtbot, repo, admin_user):
        from wired_part.ui.pages.incoming_page import IncomingPage
        page = IncomingPage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        assert not page.receive_btn.isEnabled()

    def test_refresh_empty(self, qtbot, repo, admin_user):
        from wired_part.ui.pages.incoming_page import IncomingPage
        page = IncomingPage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        page.refresh()


class TestJobsInventoryPage:
    def test_creates_without_crash(self, qtbot, repo):
        from wired_part.ui.pages.jobs_inventory_page import JobsInventoryPage
        page = JobsInventoryPage(repo)
        qtbot.addWidget(page)
        assert page is not None

    def test_has_tab_widget(self, qtbot, repo):
        from wired_part.ui.pages.jobs_inventory_page import JobsInventoryPage
        page = JobsInventoryPage(repo)
        qtbot.addWidget(page)
        assert isinstance(page.job_tabs, QTabWidget)

    def test_shows_empty_label_no_jobs(self, qtbot, repo):
        from wired_part.ui.pages.jobs_inventory_page import JobsInventoryPage
        page = JobsInventoryPage(repo)
        qtbot.addWidget(page)
        page.refresh()

    def test_creates_tab_per_job(self, qtbot, repo, sample_job):
        from wired_part.ui.pages.jobs_inventory_page import JobsInventoryPage
        page = JobsInventoryPage(repo)
        qtbot.addWidget(page)
        page.refresh()
        assert page.job_tabs.count() >= 1


class TestNewOrdersPage:
    def test_creates_without_crash(self, qtbot, repo, admin_user):
        from wired_part.ui.pages.new_orders_page import NewOrdersPage
        page = NewOrdersPage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        assert page is not None

    def test_has_job_combo(self, qtbot, repo, admin_user):
        from wired_part.ui.pages.new_orders_page import NewOrdersPage
        page = NewOrdersPage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        assert page.job_combo is not None

    def test_has_catalog_table(self, qtbot, repo, admin_user):
        from wired_part.ui.pages.new_orders_page import NewOrdersPage
        page = NewOrdersPage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        assert page.catalog_table is not None

    def test_has_order_table(self, qtbot, repo, admin_user):
        from wired_part.ui.pages.new_orders_page import NewOrdersPage
        page = NewOrdersPage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        assert page.order_table is not None

    def test_refresh_loads_catalog(
        self, qtbot, repo, admin_user, sample_parts
    ):
        from wired_part.ui.pages.new_orders_page import NewOrdersPage
        page = NewOrdersPage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        page.refresh()
        assert page.catalog_table.rowCount() >= 3


class TestOfficePage:
    def test_creates_without_crash(self, qtbot, repo, admin_user):
        from wired_part.ui.pages.office_page import OfficePage
        page = OfficePage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        assert page is not None

    def test_has_sub_tabs(self, qtbot, repo, admin_user):
        from wired_part.ui.pages.office_page import OfficePage
        page = OfficePage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        assert page.sub_tabs.count() >= 3

    def test_billing_table_exists(self, qtbot, repo, admin_user):
        from wired_part.ui.pages.office_page import OfficePage
        page = OfficePage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        assert page.billing_table is not None


class TestOrderHistoryPage:
    def test_creates_without_crash(self, qtbot, repo, admin_user):
        from wired_part.ui.pages.order_history_page import OrderHistoryPage
        page = OrderHistoryPage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        assert page is not None

    def test_has_filters(self, qtbot, repo, admin_user):
        from wired_part.ui.pages.order_history_page import OrderHistoryPage
        page = OrderHistoryPage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        assert page.search_input is not None
        assert page.status_filter is not None

    def test_has_analytics(self, qtbot, repo, admin_user):
        from wired_part.ui.pages.order_history_page import OrderHistoryPage
        page = OrderHistoryPage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        assert page.total_orders_label is not None

    def test_table_columns(self, qtbot, repo, admin_user):
        from wired_part.ui.pages.order_history_page import OrderHistoryPage
        page = OrderHistoryPage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        assert page.table.columnCount() == 9

    def test_refresh_empty(self, qtbot, repo, admin_user):
        from wired_part.ui.pages.order_history_page import OrderHistoryPage
        page = OrderHistoryPage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        page.refresh()
        assert page.table.rowCount() == 0


class TestPendingOrdersPage:
    def test_creates_without_crash(self, qtbot, repo, admin_user):
        from wired_part.ui.pages.pending_orders_page import PendingOrdersPage
        page = PendingOrdersPage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        assert page is not None

    def test_has_table(self, qtbot, repo, admin_user):
        from wired_part.ui.pages.pending_orders_page import PendingOrdersPage
        page = PendingOrdersPage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        assert page.table.columnCount() == 8

    def test_refresh_empty(self, qtbot, repo, admin_user):
        from wired_part.ui.pages.pending_orders_page import PendingOrdersPage
        page = PendingOrdersPage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        page.refresh()
        assert page.table.rowCount() == 0


class TestPendingTransfersPage:
    def test_creates_without_crash(self, qtbot, repo, admin_user):
        from wired_part.ui.pages.pending_transfers_page import (
            PendingTransfersPage,
        )
        page = PendingTransfersPage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        assert page is not None

    def test_has_sub_tabs(self, qtbot, repo, admin_user):
        from wired_part.ui.pages.pending_transfers_page import (
            PendingTransfersPage,
        )
        page = PendingTransfersPage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        assert page.sub_tabs.count() == 3

    def test_refresh_empty(self, qtbot, repo, admin_user):
        from wired_part.ui.pages.pending_transfers_page import (
            PendingTransfersPage,
        )
        page = PendingTransfersPage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        page.refresh()


class TestReturnsPage:
    def test_creates_without_crash(self, qtbot, repo, admin_user):
        from wired_part.ui.pages.returns_page import ReturnsPage
        page = ReturnsPage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        assert page is not None

    def test_has_table(self, qtbot, repo, admin_user):
        from wired_part.ui.pages.returns_page import ReturnsPage
        page = ReturnsPage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        assert page.table.columnCount() == 8

    def test_has_filters(self, qtbot, repo, admin_user):
        from wired_part.ui.pages.returns_page import ReturnsPage
        page = ReturnsPage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        assert page.search_input is not None
        assert page.status_filter is not None

    def test_refresh_empty(self, qtbot, repo, admin_user):
        from wired_part.ui.pages.returns_page import ReturnsPage
        page = ReturnsPage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        page.refresh()
        assert page.table.rowCount() == 0


class TestSettingsPage:
    def test_creates_without_crash(self, qtbot, repo, admin_user):
        from wired_part.ui.pages.settings_page import SettingsPage
        page = SettingsPage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        assert page is not None

    def test_has_sub_tabs(self, qtbot, repo, admin_user):
        from wired_part.ui.pages.settings_page import SettingsPage
        page = SettingsPage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        # Settings has multiple sub-tabs
        assert hasattr(page, 'sub_tabs') or hasattr(page, 'tabs')

    def test_users_table_exists(self, qtbot, repo, admin_user):
        from wired_part.ui.pages.settings_page import SettingsPage
        page = SettingsPage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        assert page.users_table is not None

    def test_users_table_populated(self, qtbot, repo, admin_user):
        from wired_part.ui.pages.settings_page import SettingsPage
        page = SettingsPage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        page.refresh()
        # At least the admin user should be listed
        assert page.users_table.rowCount() >= 1

    def test_hats_list_populated(self, qtbot, repo, admin_user):
        from wired_part.ui.pages.settings_page import SettingsPage
        page = SettingsPage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        assert page.hats_list.count() >= 1

    def test_categories_table_populated(self, qtbot, repo, admin_user):
        from wired_part.ui.pages.settings_page import SettingsPage
        page = SettingsPage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        assert page.categories_table.rowCount() >= 1

    def test_suppliers_table_exists(self, qtbot, repo, admin_user):
        from wired_part.ui.pages.settings_page import SettingsPage
        page = SettingsPage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        assert page.suppliers_table is not None

    def test_refresh_no_crash(self, qtbot, repo, admin_user):
        from wired_part.ui.pages.settings_page import SettingsPage
        page = SettingsPage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        page.refresh()

    def test_theme_combo_has_retro(self, qtbot, repo, admin_user):
        """Theme selector includes Dark, Light, and Retro options."""
        from wired_part.ui.pages.settings_page import SettingsPage
        page = SettingsPage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        themes = [
            page.theme_combo.itemData(i)
            for i in range(page.theme_combo.count())
        ]
        assert "dark" in themes
        assert "light" in themes
        assert "retro" in themes

    def test_has_three_sections(self, qtbot, repo, admin_user):
        """Settings has section combo with App, Team, My Settings."""
        from wired_part.ui.pages.settings_page import SettingsPage
        page = SettingsPage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        assert hasattr(page, "section_combo")
        assert hasattr(page, "section_stack")
        # Admin should see all 3 sections
        labels = [
            page.section_combo.itemText(i)
            for i in range(page.section_combo.count())
        ]
        assert "App Settings" in labels
        assert "Team Settings" in labels
        assert "My Settings" in labels

    def test_my_settings_visible_to_worker(self, qtbot, repo, worker_user):
        """Worker user (minimal perms) still sees My Settings."""
        from wired_part.ui.pages.settings_page import SettingsPage
        page = SettingsPage(repo, current_user=worker_user)
        qtbot.addWidget(page)
        labels = [
            page.section_combo.itemText(i)
            for i in range(page.section_combo.count())
        ]
        assert "My Settings" in labels

    def test_app_settings_hidden_from_worker(self, qtbot, repo, worker_user):
        """Worker user should NOT see App Settings."""
        from wired_part.ui.pages.settings_page import SettingsPage
        page = SettingsPage(repo, current_user=worker_user)
        qtbot.addWidget(page)
        labels = [
            page.section_combo.itemText(i)
            for i in range(page.section_combo.count())
        ]
        assert "App Settings" not in labels

    def test_my_settings_has_theme_combo(self, qtbot, repo, admin_user):
        """My Settings section has a per-user theme combo."""
        from wired_part.ui.pages.settings_page import SettingsPage
        page = SettingsPage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        assert hasattr(page, "my_theme_combo")
        themes = [
            page.my_theme_combo.itemData(i)
            for i in range(page.my_theme_combo.count())
        ]
        assert "dark" in themes
        assert "light" in themes
        assert "retro" in themes

    def test_my_settings_saves_theme(self, qtbot, repo, admin_user):
        """Saving My Settings persists the theme choice."""
        from wired_part.ui.pages.settings_page import SettingsPage
        page = SettingsPage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        page.my_theme_combo.setCurrentIndex(
            page.my_theme_combo.findData("retro")
        )
        page._save_my_settings()
        saved = repo.get_or_create_user_settings(admin_user.id)
        assert saved.theme == "retro"

    def test_my_settings_loads_current_values(self, qtbot, repo, admin_user):
        """My Settings loads the user's existing preferences."""
        from wired_part.ui.pages.settings_page import SettingsPage
        repo.update_user_settings(
            admin_user.id, theme="light", font_size=14,
        )
        page = SettingsPage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        assert page.my_theme_combo.currentData() == "light"
        assert page.my_font_spin.value() == 14


class TestTagMakerPage:
    def test_creates_without_crash(self, qtbot, repo, admin_user):
        from wired_part.ui.pages.tag_maker_page import TagMakerPage
        page = TagMakerPage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        assert page is not None

    def test_has_table(self, qtbot, repo, admin_user):
        from wired_part.ui.pages.tag_maker_page import TagMakerPage
        page = TagMakerPage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        assert page.table.columnCount() == 8

    def test_has_filter(self, qtbot, repo, admin_user):
        from wired_part.ui.pages.tag_maker_page import TagMakerPage
        page = TagMakerPage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        assert page.tag_filter is not None

    def test_refresh_with_parts(
        self, qtbot, repo, admin_user, sample_parts
    ):
        from wired_part.ui.pages.tag_maker_page import TagMakerPage
        page = TagMakerPage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        page.refresh()
        assert page.table.rowCount() >= 3


class TestTruckInventoryManagerPage:
    def test_creates_without_crash(self, qtbot, repo, admin_user):
        from wired_part.ui.pages.truck_inventory_manager_page import (
            TruckInventoryManagerPage,
        )
        page = TruckInventoryManagerPage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        assert page is not None

    def test_has_truck_combo(self, qtbot, repo, admin_user):
        from wired_part.ui.pages.truck_inventory_manager_page import (
            TruckInventoryManagerPage,
        )
        page = TruckInventoryManagerPage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        assert page.truck_combo is not None

    def test_has_table(self, qtbot, repo, admin_user):
        from wired_part.ui.pages.truck_inventory_manager_page import (
            TruckInventoryManagerPage,
        )
        page = TruckInventoryManagerPage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        assert page.table.columnCount() == 7

    def test_refresh_empty(self, qtbot, repo, admin_user):
        from wired_part.ui.pages.truck_inventory_manager_page import (
            TruckInventoryManagerPage,
        )
        page = TruckInventoryManagerPage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        page.refresh()


class TestTrucksInventoryPage:
    def test_creates_without_crash(self, qtbot, repo):
        from wired_part.ui.pages.trucks_inventory_page import (
            TrucksInventoryPage,
        )
        page = TrucksInventoryPage(repo)
        qtbot.addWidget(page)
        assert page is not None

    def test_has_tab_widget(self, qtbot, repo):
        from wired_part.ui.pages.trucks_inventory_page import (
            TrucksInventoryPage,
        )
        page = TrucksInventoryPage(repo)
        qtbot.addWidget(page)
        assert isinstance(page.truck_tabs, QTabWidget)

    def test_refresh_empty(self, qtbot, repo):
        from wired_part.ui.pages.trucks_inventory_page import (
            TrucksInventoryPage,
        )
        page = TrucksInventoryPage(repo)
        qtbot.addWidget(page)
        page.refresh()


class TestTrucksPage:
    def test_creates_without_crash(self, qtbot, repo, admin_user):
        from wired_part.ui.pages.trucks_page import TrucksPage
        page = TrucksPage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        assert page is not None

    def test_has_truck_list(self, qtbot, repo, admin_user):
        from wired_part.ui.pages.trucks_page import TrucksPage
        page = TrucksPage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        assert page.truck_list is not None

    def test_has_detail_tabs(self, qtbot, repo, admin_user):
        from wired_part.ui.pages.trucks_page import TrucksPage
        page = TrucksPage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        assert page.detail_tabs.count() == 3

    def test_refresh_empty(self, qtbot, repo, admin_user):
        from wired_part.ui.pages.trucks_page import TrucksPage
        page = TrucksPage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        page.refresh()

    def test_default_filter_is_my_truck(self, qtbot, repo, admin_user):
        from wired_part.ui.pages.trucks_page import TrucksPage
        page = TrucksPage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        assert page.filter_combo.currentData() == "mine"


class TestBrandManagementPage:
    def test_creates_without_crash(self, qtbot, repo, admin_user):
        from wired_part.ui.pages.brand_management_page import (
            BrandManagementPage,
        )
        page = BrandManagementPage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        assert page is not None

    def test_has_brand_list(self, qtbot, repo, admin_user):
        from wired_part.ui.pages.brand_management_page import (
            BrandManagementPage,
        )
        page = BrandManagementPage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        assert page.brand_list is not None

    def test_has_parts_table(self, qtbot, repo, admin_user):
        from wired_part.ui.pages.brand_management_page import (
            BrandManagementPage,
        )
        page = BrandManagementPage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        assert page.parts_table is not None

    def test_refresh_empty(self, qtbot, repo, admin_user):
        from wired_part.ui.pages.brand_management_page import (
            BrandManagementPage,
        )
        page = BrandManagementPage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        page.refresh()


class TestAgentPage:
    def test_creates_without_crash(self, qtbot, repo, admin_user):
        from wired_part.ui.pages.agent_page import AgentPage
        page = AgentPage(repo)
        qtbot.addWidget(page)
        assert page is not None

    def test_refresh_no_crash(self, qtbot, repo, admin_user):
        from wired_part.ui.pages.agent_page import AgentPage
        page = AgentPage(repo)
        qtbot.addWidget(page)
        if hasattr(page, 'refresh'):
            page.refresh()

    def test_chat_only_no_bg_group(self, qtbot, repo, admin_user):
        """AgentPage is chat-only after Phase D extraction."""
        from wired_part.ui.pages.agent_page import AgentPage
        page = AgentPage(repo)
        qtbot.addWidget(page)
        # Should have chat display and input but no bg agent controls
        assert page.chat_display is not None
        assert page.message_input is not None
        assert not hasattr(page, "audit_status")
        assert not hasattr(page, "bg_toggle_btn")
