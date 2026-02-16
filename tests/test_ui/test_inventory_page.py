"""pytest-qt tests for the Inventory (Warehouse) Page."""

import pytest
from PySide6.QtWidgets import QTableWidget

from wired_part.ui.pages.inventory_page import InventoryPage


class TestInventoryPage:
    def test_creates_without_crash(self, qtbot, repo):
        page = InventoryPage(repo)
        qtbot.addWidget(page)
        assert page is not None

    def test_has_table(self, qtbot, repo):
        page = InventoryPage(repo)
        qtbot.addWidget(page)
        assert isinstance(page.table, QTableWidget)

    def test_table_columns(self, qtbot, repo):
        page = InventoryPage(repo)
        qtbot.addWidget(page)
        assert page.table.columnCount() == 8

    def test_has_search_input(self, qtbot, repo):
        page = InventoryPage(repo)
        qtbot.addWidget(page)
        assert page.search_input is not None

    def test_has_category_filter(self, qtbot, repo):
        page = InventoryPage(repo)
        qtbot.addWidget(page)
        assert page.category_filter.count() >= 1

    def test_has_toolbar_buttons(self, qtbot, repo):
        page = InventoryPage(repo)
        qtbot.addWidget(page)
        assert page.add_btn is not None
        assert page.edit_btn is not None
        assert page.delete_btn is not None

    def test_edit_delete_disabled_without_selection(self, qtbot, repo):
        page = InventoryPage(repo)
        qtbot.addWidget(page)
        assert not page.edit_btn.isEnabled()
        assert not page.delete_btn.isEnabled()

    def test_refresh_with_parts(self, qtbot, repo, sample_parts):
        page = InventoryPage(repo)
        qtbot.addWidget(page)
        page.refresh()
        assert page.table.rowCount() >= 3

    def test_empty_inventory(self, qtbot, repo):
        page = InventoryPage(repo)
        qtbot.addWidget(page)
        page.refresh()
        assert page.table.rowCount() == 0
