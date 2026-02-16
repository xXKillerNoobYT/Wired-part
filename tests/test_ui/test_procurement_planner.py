"""pytest-qt tests for the ProcurementPlannerPage."""

import pytest
from PySide6.QtWidgets import QListWidget, QTableWidget

from wired_part.database.models import Part, Supplier


class TestProcurementPlanner:
    def test_creates_without_crash(self, qtbot, repo, admin_user):
        from wired_part.ui.pages.procurement_planner_page import (
            ProcurementPlannerPage,
        )
        page = ProcurementPlannerPage(repo, admin_user)
        qtbot.addWidget(page)
        assert page is not None

    def test_has_parts_table(self, qtbot, repo, admin_user):
        from wired_part.ui.pages.procurement_planner_page import (
            ProcurementPlannerPage,
        )
        page = ProcurementPlannerPage(repo, admin_user)
        qtbot.addWidget(page)
        assert isinstance(page.parts_table, QTableWidget)
        assert page.parts_table.columnCount() == 5

    def test_has_unassigned_list(self, qtbot, repo, admin_user):
        from wired_part.ui.pages.procurement_planner_page import (
            ProcurementPlannerPage,
        )
        page = ProcurementPlannerPage(repo, admin_user)
        qtbot.addWidget(page)
        assert isinstance(page.unassigned_list, QListWidget)

    def test_load_low_stock_empty(self, qtbot, repo, admin_user):
        from wired_part.ui.pages.procurement_planner_page import (
            ProcurementPlannerPage,
        )
        page = ProcurementPlannerPage(repo, admin_user)
        qtbot.addWidget(page)
        page._load_low_stock()
        assert page.parts_table.rowCount() == 0

    def test_load_low_stock_with_data(
        self, qtbot, repo, admin_user, sample_parts,
    ):
        from wired_part.ui.pages.procurement_planner_page import (
            ProcurementPlannerPage,
        )
        # Make one part low stock
        p = sample_parts[0]
        p.quantity = 1
        p.min_quantity = 10
        repo.update_part(p)

        page = ProcurementPlannerPage(repo, admin_user)
        qtbot.addWidget(page)
        page._load_low_stock()
        assert page.parts_table.rowCount() >= 1

    def test_auto_assign_no_suppliers(
        self, qtbot, repo, admin_user, sample_parts,
    ):
        from wired_part.ui.pages.procurement_planner_page import (
            ProcurementPlannerPage,
        )
        p = sample_parts[0]
        p.quantity = 1
        p.min_quantity = 10
        repo.update_part(p)

        page = ProcurementPlannerPage(repo, admin_user)
        qtbot.addWidget(page)
        page._load_low_stock()
        page._auto_assign()
        # With no part_supplier links, all go to unassigned
        assert page.unassigned_list.count() >= 1

    def test_generate_pos_empty(self, qtbot, repo, admin_user):
        from wired_part.ui.pages.procurement_planner_page import (
            ProcurementPlannerPage,
        )
        page = ProcurementPlannerPage(repo, admin_user)
        qtbot.addWidget(page)
        page._generate_pos()
        assert "No supplier" in page.status_label.text()

    def test_clear_all(self, qtbot, repo, admin_user, sample_parts):
        from wired_part.ui.pages.procurement_planner_page import (
            ProcurementPlannerPage,
        )
        p = sample_parts[0]
        p.quantity = 1
        p.min_quantity = 10
        repo.update_part(p)

        page = ProcurementPlannerPage(repo, admin_user)
        qtbot.addWidget(page)
        page._load_low_stock()
        assert page.parts_table.rowCount() >= 1
        page._clear_all()
        assert page.parts_table.rowCount() == 0

    def test_parts_table_minimum_height(self, qtbot, repo, admin_user):
        from wired_part.ui.pages.procurement_planner_page import (
            ProcurementPlannerPage,
        )
        page = ProcurementPlannerPage(repo, admin_user)
        qtbot.addWidget(page)
        assert page.parts_table.minimumHeight() >= 90
