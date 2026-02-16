"""pytest-qt tests for ALL UI dialogs."""

import pytest
from PySide6.QtWidgets import QDialog

from wired_part.database.models import (
    Category,
    Job,
    Part,
    PartsList,
    PurchaseOrder,
    PurchaseOrderItem,
    ReturnAuthorization,
    Supplier,
    Truck,
    User,
)


# ── Fixtures ──────────────────────────────────────────────────

@pytest.fixture
def sample_truck(repo, admin_user):
    t = Truck(
        truck_number="T-DLG-001",
        name="Dialog Test Truck",
        assigned_user_id=admin_user.id,
    )
    t.id = repo.create_truck(t)
    return t


@pytest.fixture
def submitted_order(repo, admin_user, sample_supplier, sample_parts):
    po = PurchaseOrder(
        order_number="PO-DLG-001",
        supplier_id=sample_supplier.id,
        status="submitted",
        created_by=admin_user.id,
    )
    po.id = repo.create_purchase_order(po)
    repo.add_order_item(PurchaseOrderItem(
        order_id=po.id, part_id=sample_parts[0].id,
        quantity_ordered=10, unit_cost=25.0,
    ))
    return po


@pytest.fixture
def sample_parts_list(repo, admin_user):
    from wired_part.database.models import PartsList
    pl = PartsList(name="DLG Test List", list_type="general")
    pl.id = repo.create_parts_list(pl)
    return pl


# ── Category Dialog ───────────────────────────────────────────

class TestCategoryDialog:
    def test_creates_for_new(self, qtbot, repo):
        from wired_part.ui.dialogs.category_dialog import CategoryDialog
        dlg = CategoryDialog(repo)
        qtbot.addWidget(dlg)
        assert dlg.windowTitle() is not None
        assert dlg.name_input is not None

    def test_creates_for_edit(self, qtbot, repo):
        from wired_part.ui.dialogs.category_dialog import CategoryDialog
        cat = repo.get_all_categories()[0]
        dlg = CategoryDialog(repo, category=cat)
        qtbot.addWidget(dlg)
        assert dlg.name_input.text() == cat.name


# ── Supplier Dialog ───────────────────────────────────────────

class TestSupplierDialog:
    def test_creates_for_new(self, qtbot, repo):
        from wired_part.ui.dialogs.supplier_dialog import SupplierDialog
        dlg = SupplierDialog(repo)
        qtbot.addWidget(dlg)
        assert dlg.name_input is not None
        assert dlg.name_input.text() == ""

    def test_creates_for_edit(self, qtbot, repo, sample_supplier):
        from wired_part.ui.dialogs.supplier_dialog import SupplierDialog
        dlg = SupplierDialog(repo, supplier=sample_supplier)
        qtbot.addWidget(dlg)
        assert dlg.name_input.text() == "UI Test Supplier"


# ── Truck Dialog ──────────────────────────────────────────────

class TestTruckDialog:
    def test_creates_for_new(self, qtbot, repo):
        from wired_part.ui.dialogs.truck_dialog import TruckDialog
        dlg = TruckDialog(repo)
        qtbot.addWidget(dlg)
        assert dlg.number_input is not None
        assert dlg.name_input is not None

    def test_creates_for_edit(self, qtbot, repo, sample_truck):
        from wired_part.ui.dialogs.truck_dialog import TruckDialog
        dlg = TruckDialog(repo, truck=sample_truck)
        qtbot.addWidget(dlg)
        assert dlg.number_input.text() == "T-DLG-001"


# ── Job Dialog ────────────────────────────────────────────────

class TestJobDialog:
    def test_creates_for_new(self, qtbot, repo):
        from wired_part.ui.dialogs.job_dialog import JobDialog
        dlg = JobDialog(repo)
        qtbot.addWidget(dlg)
        assert dlg.name_input is not None

    def test_creates_for_edit(self, qtbot, repo, sample_job):
        from wired_part.ui.dialogs.job_dialog import JobDialog
        dlg = JobDialog(repo, job=sample_job)
        qtbot.addWidget(dlg)
        assert dlg.name_input.text() == "UI Test Job"


# ── User Dialog ───────────────────────────────────────────────

class TestUserDialog:
    def test_creates_for_new(self, qtbot, repo, admin_user):
        from wired_part.ui.dialogs.user_dialog import UserDialog
        dlg = UserDialog(repo, current_user=admin_user)
        qtbot.addWidget(dlg)
        assert dlg.username_input is not None
        assert dlg.pin_input is not None

    def test_creates_for_edit(self, qtbot, repo, admin_user):
        from wired_part.ui.dialogs.user_dialog import UserDialog
        dlg = UserDialog(repo, user=admin_user, current_user=admin_user)
        qtbot.addWidget(dlg)
        assert dlg.username_input.text() == "admin"


# ── Part Dialog ───────────────────────────────────────────────

class TestPartDialog:
    def test_creates_for_new(self, qtbot, repo):
        from wired_part.ui.dialogs.part_dialog import PartDialog
        dlg = PartDialog(repo)
        qtbot.addWidget(dlg)
        assert dlg.name_input is not None
        assert dlg.part_number_input is not None

    def test_creates_for_edit(self, qtbot, repo, sample_parts):
        from wired_part.ui.dialogs.part_dialog import PartDialog
        dlg = PartDialog(repo, part=sample_parts[0])
        qtbot.addWidget(dlg)
        assert dlg.part_number_input.text() == "UI-WIRE-001"


# ── Part Picker Dialog ────────────────────────────────────────

class TestPartPickerDialog:
    def test_creates_without_crash(self, qtbot, repo):
        from wired_part.ui.dialogs.part_picker_dialog import PartPickerDialog
        dlg = PartPickerDialog(repo)
        qtbot.addWidget(dlg)
        assert dlg.search_input is not None
        assert dlg.table is not None

    def test_populates_with_parts(self, qtbot, repo, sample_parts):
        from wired_part.ui.dialogs.part_picker_dialog import PartPickerDialog
        dlg = PartPickerDialog(repo)
        qtbot.addWidget(dlg)
        assert dlg.table.rowCount() >= 3


# ── Order Dialog ──────────────────────────────────────────────

class TestOrderDialog:
    def test_creates_for_new(self, qtbot, repo, admin_user):
        from wired_part.ui.dialogs.order_dialog import OrderDialog
        dlg = OrderDialog(repo, current_user=admin_user)
        qtbot.addWidget(dlg)
        assert dlg.supplier_combo is not None

    def test_creates_for_edit(
        self, qtbot, repo, admin_user, submitted_order
    ):
        from wired_part.ui.dialogs.order_dialog import OrderDialog
        order = repo.get_purchase_order_by_id(submitted_order.id)
        dlg = OrderDialog(repo, order=order, current_user=admin_user)
        qtbot.addWidget(dlg)


# ── Order Detail Dialog ───────────────────────────────────────

class TestOrderDetailDialog:
    def test_creates_without_crash(
        self, qtbot, repo, submitted_order
    ):
        from wired_part.ui.dialogs.order_detail_dialog import (
            OrderDetailDialog,
        )
        dlg = OrderDetailDialog(repo, order_id=submitted_order.id)
        qtbot.addWidget(dlg)
        assert dlg.items_table is not None


# ── Order From List Dialog ────────────────────────────────────

class TestOrderFromListDialog:
    def test_creates_without_crash(self, qtbot, repo, admin_user):
        from wired_part.ui.dialogs.order_from_list_dialog import (
            OrderFromListDialog,
        )
        dlg = OrderFromListDialog(repo, current_user=admin_user)
        qtbot.addWidget(dlg)
        assert dlg.list_combo is not None


# ── Split Order Dialog ────────────────────────────────────────

class TestSplitOrderDialog:
    def test_creates_without_crash(self, qtbot, repo, admin_user):
        from wired_part.ui.dialogs.split_order_dialog import SplitOrderDialog
        dlg = SplitOrderDialog(repo, current_user=admin_user)
        qtbot.addWidget(dlg)
        assert dlg.list_combo is not None


# ── Transfer Dialog ───────────────────────────────────────────

class TestTransferDialog:
    def test_creates_without_crash(
        self, qtbot, repo, sample_truck, admin_user
    ):
        from wired_part.ui.dialogs.transfer_dialog import TransferDialog
        dlg = TransferDialog(repo, sample_truck.id, admin_user)
        qtbot.addWidget(dlg)
        assert dlg.table is not None


# ── Receive Dialog ────────────────────────────────────────────

class TestReceiveDialog:
    def test_creates_without_crash(
        self, qtbot, repo, sample_truck, admin_user
    ):
        from wired_part.ui.dialogs.receive_dialog import ReceiveDialog
        dlg = ReceiveDialog(repo, sample_truck.id, admin_user)
        qtbot.addWidget(dlg)
        assert dlg.table is not None


# ── Consume Dialog ────────────────────────────────────────────

class TestConsumeDialog:
    def test_creates_without_crash(
        self, qtbot, repo, sample_job, admin_user
    ):
        from wired_part.ui.dialogs.consume_dialog import ConsumeDialog
        dlg = ConsumeDialog(repo, sample_job.id, admin_user)
        qtbot.addWidget(dlg)
        assert dlg.truck_combo is not None


# ── Return Dialog ─────────────────────────────────────────────

class TestReturnDialog:
    def test_creates_without_crash(self, qtbot, repo, admin_user):
        from wired_part.ui.dialogs.return_dialog import ReturnDialog
        dlg = ReturnDialog(repo, current_user=admin_user)
        qtbot.addWidget(dlg)
        assert dlg.supplier_combo is not None
        assert dlg.items_table is not None


# ── Supply House Dialog ───────────────────────────────────────

class TestSupplyHouseDialog:
    def test_creates_without_crash(self, qtbot, repo, admin_user):
        from wired_part.ui.dialogs.supply_house_dialog import (
            SupplyHouseDialog,
        )
        dlg = SupplyHouseDialog(repo, current_user=admin_user)
        qtbot.addWidget(dlg)
        assert dlg.supplier_combo is not None


# ── Billing Dialog ────────────────────────────────────────────

class TestBillingDialog:
    def test_creates_without_crash(self, qtbot, repo, sample_job):
        from wired_part.ui.dialogs.billing_dialog import BillingDialog
        dlg = BillingDialog(repo, job_id=sample_job.id)
        qtbot.addWidget(dlg)
        assert dlg.preview is not None


# ── Work Report Dialog ────────────────────────────────────────

class TestWorkReportDialog:
    def test_creates_without_crash(self, qtbot, repo, sample_job):
        from wired_part.ui.dialogs.work_report_dialog import (
            WorkReportDialog,
        )
        dlg = WorkReportDialog(repo, job_id=sample_job.id)
        qtbot.addWidget(dlg)
        assert dlg.preview is not None
        assert dlg.type_selector is not None


# ── Audit Dialog ──────────────────────────────────────────────

class TestAuditDialog:
    def test_creates_without_crash(self, qtbot, repo, admin_user):
        from wired_part.ui.dialogs.audit_dialog import AuditDialog
        dlg = AuditDialog(
            repo, audit_type="warehouse",
            current_user_id=admin_user.id,
        )
        qtbot.addWidget(dlg)
        assert dlg is not None


# ── Export Dialog ─────────────────────────────────────────────

class TestExportDialog:
    def test_creates_without_crash(self, qtbot, repo):
        from wired_part.ui.dialogs.export_dialog import ExportDialog
        dlg = ExportDialog(repo)
        qtbot.addWidget(dlg)
        assert dlg.data_type is not None
        assert dlg.format_type is not None


# ── Import Dialog ─────────────────────────────────────────────

class TestImportDialog:
    def test_creates_without_crash(self, qtbot, repo):
        from wired_part.ui.dialogs.import_dialog import ImportDialog
        dlg = ImportDialog(repo)
        qtbot.addWidget(dlg)


# ── Job Assign Dialog ─────────────────────────────────────────

class TestJobAssignDialog:
    def test_creates_without_crash(self, qtbot, repo, sample_job):
        from wired_part.ui.dialogs.job_assign_dialog import JobAssignDialog
        dlg = JobAssignDialog(repo, job_id=sample_job.id)
        qtbot.addWidget(dlg)
        assert dlg.user_combo is not None
        assert dlg.role_combo is not None


# ── Assign Parts Dialog ───────────────────────────────────────

class TestAssignPartsDialog:
    def test_creates_without_crash(self, qtbot, repo, sample_job):
        from wired_part.ui.dialogs.assign_parts_dialog import (
            AssignPartsDialog,
        )
        dlg = AssignPartsDialog(repo, sample_job)
        qtbot.addWidget(dlg)
        assert dlg.table is not None


# ── Labor Entry Dialog ────────────────────────────────────────

class TestLaborEntryDialog:
    def test_creates_without_crash(
        self, qtbot, repo, admin_user, sample_job
    ):
        from wired_part.ui.dialogs.labor_entry_dialog import (
            LaborEntryDialog,
        )
        dlg = LaborEntryDialog(
            repo, user_id=admin_user.id, job_id=sample_job.id,
        )
        qtbot.addWidget(dlg)
        assert dlg.job_selector is not None
        assert dlg.hours_input is not None


# ── Labor Log Dialog ──────────────────────────────────────────

class TestLaborLogDialog:
    def test_creates_without_crash(self, qtbot, repo, sample_job):
        from wired_part.ui.dialogs.labor_log_dialog import LaborLogDialog
        dlg = LaborLogDialog(
            repo, job_id=sample_job.id, job_name="UI Test Job",
        )
        qtbot.addWidget(dlg)
        assert dlg.table is not None


# ── Clock Dialog (special — uses GPS threads) ─────────────────

class TestClockDialog:
    def test_clock_in_creates(
        self, qtbot, repo, admin_user, sample_job, monkeypatch,
    ):
        from wired_part.ui.dialogs.clock_dialog import (
            ClockInDialog, _GPSSection,
        )
        monkeypatch.setattr(
            _GPSSection, "auto_detect", lambda self: None,
        )
        dlg = ClockInDialog(
            repo, user_id=admin_user.id, job_id=sample_job.id,
        )
        qtbot.addWidget(dlg)
        assert dlg.job_selector is not None
        assert dlg.category_selector is not None


# ── Notebook Dialog ───────────────────────────────────────────

class TestNotebookDialog:
    def test_creates_without_crash(
        self, qtbot, repo, sample_job, admin_user
    ):
        from wired_part.ui.dialogs.notebook_dialog import NotebookDialog
        dlg = NotebookDialog(
            repo, job_id=sample_job.id,
            job_name="UI Test Job", user_id=admin_user.id,
        )
        qtbot.addWidget(dlg)
        assert dlg.notebook_widget is not None


# ── Notes Search Dialog ───────────────────────────────────────

class TestNotesSearchDialog:
    def test_creates_without_crash(self, qtbot, repo):
        from wired_part.ui.dialogs.notes_search_dialog import (
            NotesSearchDialog,
        )
        dlg = NotesSearchDialog(repo, results=[], query="test")
        qtbot.addWidget(dlg)
        assert dlg.table is not None


# ── Parts List Dialog ─────────────────────────────────────────

class TestPartsListDialog:
    def test_creates_for_new(self, qtbot, repo):
        from wired_part.ui.dialogs.parts_list_dialog import PartsListDialog
        dlg = PartsListDialog(repo)
        qtbot.addWidget(dlg)
        assert dlg.name_input is not None

    def test_creates_for_edit(self, qtbot, repo, sample_parts_list):
        from wired_part.ui.dialogs.parts_list_dialog import PartsListDialog
        pl = repo.get_parts_list_by_id(sample_parts_list.id)
        dlg = PartsListDialog(repo, parts_list=pl)
        qtbot.addWidget(dlg)
        assert dlg.name_input.text() == "DLG Test List"


# ── Parts List Items Dialog ───────────────────────────────────

class TestPartsListItemsDialog:
    def test_creates_without_crash(self, qtbot, repo, sample_parts_list):
        from wired_part.ui.dialogs.parts_list_items_dialog import (
            PartsListItemsDialog,
        )
        dlg = PartsListItemsDialog(
            repo, list_id=sample_parts_list.id,
            list_name="DLG Test List",
        )
        qtbot.addWidget(dlg)
        assert dlg.table is not None


# ── Parts List Manager Dialog ─────────────────────────────────

class TestPartsListManagerDialog:
    def test_creates_without_crash(self, qtbot, repo, admin_user):
        from wired_part.ui.dialogs.parts_list_manager_dialog import (
            PartsListManagerDialog,
        )
        dlg = PartsListManagerDialog(repo, current_user=admin_user)
        qtbot.addWidget(dlg)
        assert dlg.lists_table is not None
        assert dlg.items_table is not None
