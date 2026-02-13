"""E2E tests: supply house workflows, billing cycles, and notebook operations."""

import pytest
from datetime import datetime, timedelta

from wired_part.database.models import (
    Job, JobAssignment, LaborEntry, NotebookPage, NotebookSection,
    Part, PurchaseOrder, PurchaseOrderItem,
    Supplier, User,
)
from wired_part.database.repository import Repository


@pytest.fixture
def supply_user(repo):
    user = User(
        username="supply_e2e", display_name="Supply Worker",
        pin_hash=Repository.hash_pin("1234"),
        role="user", is_active=1,
    )
    user.id = repo.create_user(user)
    return user


@pytest.fixture
def supply_house(repo):
    s = Supplier(
        name="Big Supply House",
        contact_name="Sam",
        email="sam@bighouse.com",
        phone="555-SUPP",
        is_supply_house=1,
        operating_hours="Mon-Fri 6am-5pm, Sat 7am-12pm",
    )
    s.id = repo.create_supplier(s)
    return s


@pytest.fixture
def regular_supplier(repo):
    s = Supplier(
        name="Online Vendor",
        contact_name="Web",
        email="order@vendor.com",
        phone="555-VEND",
        is_supply_house=0,
    )
    s.id = repo.create_supplier(s)
    return s


@pytest.fixture
def test_parts(repo, supply_house):
    from wired_part.database.models import PartSupplier
    cat = repo.get_all_categories()[0]
    parts = []
    for pn, name, qty, cost in [
        ("SUP-WIRE", "Wire Spool", 50, 89.99),
        ("SUP-PIPE", "Conduit Pipe", 100, 15.50),
        ("SUP-BOX", "Junction Box", 200, 3.25),
    ]:
        p = Part(
            part_number=pn, name=name,
            quantity=qty, unit_cost=cost,
            category_id=cat.id, min_quantity=20,
        )
        p.id = repo.create_part(p)
        repo.link_part_supplier(PartSupplier(
            part_id=p.id, supplier_id=supply_house.id,
        ))
        parts.append(p)
    return parts


# ═══════════════════════════════════════════════════════════════════
# SUPPLY HOUSE WORKFLOW
# ═══════════════════════════════════════════════════════════════════


class TestSupplyHouseWorkflow:
    """Supply house vs regular supplier, ordering, receiving."""

    def test_distinguish_supply_houses(
        self, repo, supply_house, regular_supplier,
    ):
        """Can filter supply houses from regular suppliers."""
        all_suppliers = repo.get_all_suppliers()
        houses = [s for s in all_suppliers if s.is_supply_house]
        regulars = [s for s in all_suppliers if not s.is_supply_house]

        assert any(s.id == supply_house.id for s in houses)
        assert any(s.id == regular_supplier.id for s in regulars)

    def test_supply_house_has_operating_hours(
        self, repo, supply_house,
    ):
        """Supply house has operating hours for phone script."""
        s = repo.get_supplier_by_id(supply_house.id)
        assert s.operating_hours is not None
        assert "Mon" in s.operating_hours

    def test_order_from_supply_house_full_cycle(
        self, repo, supply_user, supply_house, test_parts,
    ):
        """Create PO from supply house -> submit -> receive -> stock."""
        wire = test_parts[0]
        original_qty = wire.quantity

        po = PurchaseOrder(
            order_number=repo.generate_order_number(),
            supplier_id=supply_house.id,
            status="draft",
            created_by=supply_user.id,
        )
        po.id = repo.create_purchase_order(po)
        repo.add_order_item(PurchaseOrderItem(
            order_id=po.id, part_id=wire.id,
            quantity_ordered=25, unit_cost=wire.unit_cost,
        ))
        repo.submit_purchase_order(po.id)

        items = repo.get_order_items(po.id)
        repo.receive_order_items(po.id, [{
            "order_item_id": items[0].id,
            "quantity_received": 25,
            "allocate_to": "warehouse",
        }], supply_user.id)

        assert repo.get_part_by_id(wire.id).quantity == original_qty + 25

    def test_update_supplier_to_supply_house(
        self, repo, regular_supplier,
    ):
        """Convert a regular supplier to a supply house."""
        s = repo.get_supplier_by_id(regular_supplier.id)
        s.is_supply_house = 1
        s.operating_hours = "Mon-Fri 8am-5pm"
        repo.update_supplier(s)

        updated = repo.get_supplier_by_id(regular_supplier.id)
        assert updated.is_supply_house == 1
        assert "Mon" in updated.operating_hours


# ═══════════════════════════════════════════════════════════════════
# BILLING CYCLE WORKFLOW
# ═══════════════════════════════════════════════════════════════════


class TestBillingCycleWorkflow:
    """End-to-end billing cycle: create, retrieve, use with billing data."""

    def test_get_or_create_billing_cycle(self, repo):
        """Create a billing cycle via get_or_create."""
        bc = repo.get_or_create_billing_cycle(
            job_id=None, cycle_type="monthly", billing_day=1
        )
        assert bc is not None
        assert bc.cycle_type == "monthly"
        assert bc.billing_day == 1

    def test_get_or_create_billing_cycle_for_job(self, repo):
        """Create a job-specific billing cycle."""
        job = Job(
            job_number="BC-JOB-001", name="Cycle Job",
            status="active",
        )
        job.id = repo.create_job(job)
        bc = repo.get_or_create_billing_cycle(
            job_id=job.id, cycle_type="weekly", billing_day=1
        )
        assert bc.cycle_type == "weekly"

        # Second call returns same cycle
        bc2 = repo.get_or_create_billing_cycle(job_id=job.id)
        assert bc2.id == bc.id

    def test_get_billing_cycles_list(self, repo):
        """List all billing cycles."""
        repo.get_or_create_billing_cycle(
            job_id=None, cycle_type="monthly", billing_day=15
        )
        cycles = repo.get_billing_cycles()
        assert len(cycles) >= 1

    def test_billing_data_for_job_with_parts(self, repo, supply_user):
        """Generate billing data for a job with assigned parts."""
        job = Job(
            job_number="BILL-E2E-001", name="Billing Test",
            status="active", bill_out_rate="T&M",
        )
        job.id = repo.create_job(job)

        # Billing data returns parts/material info, not labor hours
        billing = repo.get_billing_data(job.id)
        assert billing is not None
        assert "subtotal" in billing
        assert "categories" in billing
        assert "job" in billing
        assert billing["job"]["job_number"] == "BILL-E2E-001"

    def test_billing_data_empty_job(self, repo):
        """Empty job has zero subtotal in billing data."""
        job = Job(job_number="BILL-EMPTY", name="No Work", status="active")
        job.id = repo.create_job(job)
        billing = repo.get_billing_data(job.id)
        assert billing["subtotal"] == 0.0
        assert billing["consumption_count"] == 0

    def test_labor_summary_for_job_with_hours(self, repo, supply_user):
        """Labor summary correctly tallies hours for a job."""
        job = Job(
            job_number="LABOR-SUM-001", name="Labor Summary Test",
            status="active", bill_out_rate="T&M",
        )
        job.id = repo.create_job(job)

        for cat, hrs in [("Rough-in", 8.0), ("Testing", 2.5)]:
            repo.create_labor_entry(LaborEntry(
                user_id=supply_user.id, job_id=job.id,
                start_time=datetime.now().isoformat(),
                hours=hrs, sub_task_category=cat,
            ))

        summary = repo.get_labor_summary_for_job(job.id)
        assert summary["total_hours"] == 10.5
        assert summary["entry_count"] == 2


# ═══════════════════════════════════════════════════════════════════
# NOTEBOOK OPERATIONS
# ═══════════════════════════════════════════════════════════════════


class TestNotebookWorkflow:
    """Notebook page create, update, search, delete via proper API."""

    def test_full_notebook_lifecycle(self, repo, supply_user):
        """Create job notebook -> sections -> pages -> update -> search -> delete."""
        job = Job(
            job_number="NB-E2E-001", name="Notebook Job",
            status="active",
        )
        job.id = repo.create_job(job)

        # get_or_create_notebook creates notebook + default sections
        notebook = repo.get_or_create_notebook(job.id)
        assert notebook is not None
        assert notebook.job_id == job.id

        # Get sections
        sections = repo.get_sections(notebook.id)
        assert len(sections) >= 1
        section = sections[0]

        # Create pages in first section
        page1 = NotebookPage(
            section_id=section.id,
            title="Day 1 Notes", content="Arrived on site at 7am.",
            created_by=supply_user.id,
        )
        page1.id = repo.create_page(page1)
        assert page1.id > 0

        page2 = NotebookPage(
            section_id=section.id,
            title="Material List", content="Wire, breakers, outlets",
            created_by=supply_user.id,
        )
        page2.id = repo.create_page(page2)

        # Get pages for section
        pages = repo.get_pages(section.id)
        assert len(pages) >= 2

        # Update a page
        p = repo.get_page_by_id(page1.id)
        p.content = "Arrived on site at 7am. Started rough-in."
        repo.update_page(p)
        updated = repo.get_page_by_id(page1.id)
        assert "rough-in" in updated.content

        # Search across all notebooks
        results = repo.search_notebook_pages("breakers")
        assert len(results) >= 1
        assert any(r.id == page2.id for r in results)

        # Delete
        repo.delete_page(page2.id)
        assert repo.get_page_by_id(page2.id) is None

    def test_search_notebook_pages_no_results(self, repo):
        results = repo.search_notebook_pages("xyznonexistent")
        assert len(results) == 0

    def test_notebook_sections_created_automatically(self, repo):
        """Default sections are created when notebook is first accessed."""
        job = Job(
            job_number="NB-SEC-001", name="Section Job",
            status="active",
        )
        job.id = repo.create_job(job)
        notebook = repo.get_or_create_notebook(job.id)
        sections = repo.get_sections(notebook.id)
        # Default sections come from Config.get_notebook_sections()
        assert len(sections) >= 1

    def test_add_custom_section(self, repo, supply_user):
        """Can add a custom section to a notebook."""
        job = Job(
            job_number="NB-CUSTOM-001", name="Custom Section",
            status="active",
        )
        job.id = repo.create_job(job)
        notebook = repo.get_or_create_notebook(job.id)

        original_count = len(repo.get_sections(notebook.id))
        new_section = NotebookSection(
            notebook_id=notebook.id,
            name="Punch List",
        )
        new_section.id = repo.create_section(new_section)
        assert new_section.id > 0

        assert len(repo.get_sections(notebook.id)) == original_count + 1


# ═══════════════════════════════════════════════════════════════════
# MULTI-PART SHORTFALL + REORDER
# ═══════════════════════════════════════════════════════════════════


class TestShortfallAndReorder:
    """Detect shortfall, create PO to fix it, receive and verify."""

    def test_shortfall_triggers_reorder(
        self, repo, supply_user, supply_house, test_parts,
    ):
        """Full cycle: low stock -> detect -> order -> receive -> restored."""
        box = test_parts[2]  # min=20, qty=200

        # Reduce stock below minimum
        box_obj = repo.get_part_by_id(box.id)
        box_obj.quantity = 5  # below min of 20
        repo.update_part(box_obj)

        # Verify shortfall is detectable
        assert repo.get_part_by_id(box.id).is_low_stock

        # Create restock PO
        po = PurchaseOrder(
            order_number=repo.generate_order_number(),
            supplier_id=supply_house.id,
            status="draft",
            created_by=supply_user.id,
        )
        po.id = repo.create_purchase_order(po)
        repo.add_order_item(PurchaseOrderItem(
            order_id=po.id, part_id=box.id,
            quantity_ordered=50, unit_cost=box.unit_cost,
        ))
        repo.submit_purchase_order(po.id)

        items = repo.get_order_items(po.id)
        repo.receive_order_items(po.id, [{
            "order_item_id": items[0].id,
            "quantity_received": 50,
            "allocate_to": "warehouse",
        }], supply_user.id)

        # Stock restored above minimum
        box_after = repo.get_part_by_id(box.id)
        assert box_after.quantity == 55
        assert not box_after.is_low_stock
