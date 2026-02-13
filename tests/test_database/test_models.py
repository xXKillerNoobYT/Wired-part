"""Tests for dataclass model properties and computed fields."""

import json
import pytest

from wired_part.database.models import (
    Hat,
    Job,
    JobPart,
    LaborEntry,
    NotebookPage,
    Part,
    PurchaseOrder,
    PurchaseOrderItem,
    ReturnAuthorizationItem,
)


class TestPartProperties:
    """Test Part model computed properties."""

    def test_display_name_uses_name(self):
        p = Part(name="Widget", description="A widget", part_number="W-001")
        assert p.display_name == "Widget"

    def test_display_name_falls_to_description(self):
        p = Part(name="", description="Big Widget", part_number="W-002")
        assert p.display_name == "Big Widget"

    def test_display_name_falls_to_part_number(self):
        p = Part(name="", description="", part_number="W-003")
        assert p.display_name == "W-003"

    def test_display_name_unnamed(self):
        p = Part(name="", description="", part_number="")
        assert p.display_name == "(Unnamed)"

    def test_is_low_stock(self):
        p = Part(quantity=3, min_quantity=10)
        assert p.is_low_stock is True

    def test_is_not_low_stock(self):
        p = Part(quantity=50, min_quantity=10)
        assert p.is_low_stock is False

    def test_is_low_stock_no_min(self):
        p = Part(quantity=0, min_quantity=0)
        assert p.is_low_stock is False

    def test_is_over_stock(self):
        p = Part(quantity=200, max_quantity=100)
        assert p.is_over_stock is True

    def test_is_not_over_stock(self):
        p = Part(quantity=50, max_quantity=100)
        assert p.is_over_stock is False

    def test_total_value(self):
        p = Part(quantity=10, unit_cost=5.50)
        assert p.total_value == 55.0

    def test_is_specific(self):
        p = Part(part_type="specific")
        assert p.is_specific is True
        assert p.is_general is False

    def test_is_general(self):
        p = Part(part_type="general")
        assert p.is_general is True
        assert p.is_specific is False

    def test_quantity_window_str(self):
        p = Part(min_quantity=10, max_quantity=100)
        assert "10" in p.quantity_window_str
        assert "100" in p.quantity_window_str

    def test_quantity_window_str_no_limits(self):
        p = Part(min_quantity=0, max_quantity=0)
        assert p.quantity_window_str == ""

    def test_color_option_list_valid_json(self):
        p = Part(color_options='["Red", "Blue"]')
        assert p.color_option_list == ["Red", "Blue"]

    def test_color_option_list_empty(self):
        p = Part(color_options="")
        assert p.color_option_list == []

    def test_color_option_list_invalid_json(self):
        p = Part(color_options="not json")
        assert p.color_option_list == []

    def test_type_style_list_valid(self):
        p = Part(type_style='["Standard", "Premium"]')
        assert p.type_style_list == ["Standard", "Premium"]

    def test_type_style_list_empty(self):
        p = Part(type_style="")
        assert p.type_style_list == []

    def test_pdf_list_valid(self):
        p = Part(pdfs='["spec.pdf", "manual.pdf"]')
        assert p.pdf_list == ["spec.pdf", "manual.pdf"]

    def test_pdf_list_empty(self):
        p = Part(pdfs="")
        assert p.pdf_list == []


class TestJobPartProperties:
    """Test JobPart computed properties."""

    def test_total_cost(self):
        jp = JobPart(quantity_used=5, unit_cost_at_use=10.0)
        assert jp.total_cost == 50.0

    def test_total_cost_zero(self):
        jp = JobPart(quantity_used=0, unit_cost_at_use=10.0)
        assert jp.total_cost == 0.0


class TestLaborEntryProperties:
    """Test LaborEntry photo_list property."""

    def test_photo_list_valid_json(self):
        entry = LaborEntry(photos='["/photo1.jpg", "/photo2.jpg"]')
        assert entry.photo_list == ["/photo1.jpg", "/photo2.jpg"]

    def test_photo_list_empty_string(self):
        entry = LaborEntry(photos="")
        assert entry.photo_list == []

    def test_photo_list_none(self):
        entry = LaborEntry(photos=None)
        assert entry.photo_list == []

    def test_photo_list_invalid_json(self):
        entry = LaborEntry(photos="bad json")
        assert entry.photo_list == []

    def test_bill_out_rate_default(self):
        entry = LaborEntry()
        assert entry.bill_out_rate == ""


class TestNotebookPageProperties:
    """Test NotebookPage property methods."""

    def test_part_reference_list_valid(self):
        page = NotebookPage(part_references='[1, 2, 3]')
        assert page.part_reference_list == [1, 2, 3]

    def test_part_reference_list_empty(self):
        page = NotebookPage(part_references="")
        assert page.part_reference_list == []


class TestHatProperties:
    """Test Hat permission_list property."""

    def test_permission_list_valid(self):
        hat = Hat(permissions='["tab_dashboard", "labor_clock_in"]')
        assert hat.permission_list == ["tab_dashboard", "labor_clock_in"]

    def test_permission_list_empty(self):
        hat = Hat(permissions="")
        assert hat.permission_list == []


class TestPurchaseOrderProperties:
    """Test PurchaseOrder computed properties."""

    def test_is_editable_draft(self):
        po = PurchaseOrder(status="draft")
        assert po.is_editable is True

    def test_not_editable_submitted(self):
        po = PurchaseOrder(status="submitted")
        assert po.is_editable is False

    def test_not_editable_closed(self):
        po = PurchaseOrder(status="closed")
        assert po.is_editable is False

    def test_is_receivable_submitted(self):
        po = PurchaseOrder(status="submitted")
        assert po.is_receivable is True

    def test_is_receivable_partial(self):
        po = PurchaseOrder(status="partial")
        assert po.is_receivable is True

    def test_not_receivable_draft(self):
        po = PurchaseOrder(status="draft")
        assert po.is_receivable is False


class TestPurchaseOrderItemProperties:
    """Test PurchaseOrderItem computed properties."""

    def test_quantity_remaining(self):
        item = PurchaseOrderItem(quantity_ordered=100, quantity_received=40)
        assert item.quantity_remaining == 60

    def test_quantity_remaining_zero(self):
        item = PurchaseOrderItem(quantity_ordered=50, quantity_received=50)
        assert item.quantity_remaining == 0

    def test_quantity_remaining_negative_clamps(self):
        item = PurchaseOrderItem(quantity_ordered=10, quantity_received=15)
        assert item.quantity_remaining == 0

    def test_is_fully_received(self):
        item = PurchaseOrderItem(quantity_ordered=10, quantity_received=10)
        assert item.is_fully_received is True

    def test_is_not_fully_received(self):
        item = PurchaseOrderItem(quantity_ordered=10, quantity_received=5)
        assert item.is_fully_received is False

    def test_line_total(self):
        item = PurchaseOrderItem(quantity_ordered=20, unit_cost=5.0)
        assert item.line_total == 100.0


class TestReturnAuthorizationItemProperties:
    """Test ReturnAuthorizationItem line_total."""

    def test_line_total(self):
        item = ReturnAuthorizationItem(quantity=5, unit_cost=12.0)
        assert item.line_total == 60.0
