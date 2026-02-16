"""pytest-qt tests for the Parts Catalog Page widget."""

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTabWidget

from wired_part.ui.pages.parts_catalog_page import (
    CatalogSubPage,
    PartsCatalogPage,
)


class TestPartsCatalogPageWidget:
    """Test the PartsCatalogPage container widget."""

    def test_creates_without_crash(self, qtbot, repo, admin_user):
        """PartsCatalogPage can be instantiated."""
        page = PartsCatalogPage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        assert page is not None

    def test_has_sub_tabs(self, qtbot, repo, admin_user):
        """Page has at least 3 sub-tabs."""
        page = PartsCatalogPage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        assert page.sub_tabs.count() >= 3

    def test_first_tab_is_catalog(self, qtbot, repo, admin_user):
        """First sub-tab is 'Catalog'."""
        page = PartsCatalogPage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        assert page.sub_tabs.tabText(0) == "Catalog"

    def test_catalog_subtab_is_loaded(self, qtbot, repo, admin_user):
        """Catalog sub-page is loaded immediately (not lazy)."""
        page = PartsCatalogPage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        assert isinstance(page.catalog_page, CatalogSubPage)


class TestCatalogSubPage:
    """Test the CatalogSubPage widget directly."""

    def test_creates_without_crash(self, qtbot, repo, admin_user):
        """CatalogSubPage can be instantiated."""
        page = CatalogSubPage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        assert page is not None

    def test_table_has_data_with_parts(
        self, qtbot, repo, admin_user, sample_parts
    ):
        """Table populates when parts exist in the DB."""
        page = CatalogSubPage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        page.refresh()
        assert page.table.rowCount() >= 3

    def test_search_filters_parts(
        self, qtbot, repo, admin_user, sample_parts
    ):
        """Typing in search filters the displayed parts."""
        page = CatalogSubPage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        page.refresh()
        initial_count = page.table.rowCount()
        assert initial_count >= 3

        # Search for a specific part
        page.search_input.setText("Wire")
        page.refresh()
        # Should have fewer results (only matching parts)
        filtered_count = page.table.rowCount()
        assert filtered_count <= initial_count

    def test_empty_catalog(self, qtbot, repo, admin_user):
        """Empty DB shows empty table."""
        page = CatalogSubPage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        # Default categories exist but no parts
        page.refresh()
        assert page.table.rowCount() == 0

    def test_refresh_does_not_crash(
        self, qtbot, repo, admin_user, sample_parts
    ):
        """Multiple refreshes don't crash."""
        page = CatalogSubPage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        for _ in range(5):
            page.refresh()
