"""Tests for the import data validator."""

import pytest
from wired_part.io.validators import validate_part_row


class TestValidatePartRow:
    def test_valid_row_no_errors(self):
        row = {
            "part_number": "PN-001",
            "description": "10 AWG Wire",
            "quantity": "100",
            "unit_cost": "12.50",
            "min_quantity": "10",
        }
        assert validate_part_row(row, 1) == []

    def test_missing_part_number(self):
        row = {"part_number": "", "description": "Some part"}
        errors = validate_part_row(row, 1)
        assert len(errors) == 1
        assert "part_number is required" in errors[0]

    def test_part_number_whitespace_only(self):
        row = {"part_number": "   ", "description": "Some part"}
        errors = validate_part_row(row, 1)
        assert any("part_number is required" in e for e in errors)

    def test_part_number_exceeds_50_chars(self):
        row = {"part_number": "A" * 51, "description": "Some part"}
        errors = validate_part_row(row, 1)
        assert any("exceeds 50 chars" in e for e in errors)

    def test_part_number_exactly_50_chars(self):
        row = {"part_number": "A" * 50, "description": "Some part"}
        errors = validate_part_row(row, 1)
        assert errors == []

    def test_missing_description(self):
        row = {"part_number": "PN-001", "description": ""}
        errors = validate_part_row(row, 1)
        assert any("description is required" in e for e in errors)

    def test_description_whitespace_only(self):
        row = {"part_number": "PN-001", "description": "   "}
        errors = validate_part_row(row, 1)
        assert any("description is required" in e for e in errors)

    def test_negative_quantity(self):
        row = {
            "part_number": "PN-001",
            "description": "Wire",
            "quantity": "-5",
        }
        errors = validate_part_row(row, 1)
        assert any("quantity cannot be negative" in e for e in errors)

    def test_non_integer_quantity(self):
        row = {
            "part_number": "PN-001",
            "description": "Wire",
            "quantity": "abc",
        }
        errors = validate_part_row(row, 1)
        assert any("quantity must be an integer" in e for e in errors)

    def test_empty_quantity_ok(self):
        row = {"part_number": "PN-001", "description": "Wire", "quantity": ""}
        assert validate_part_row(row, 1) == []

    def test_zero_quantity_ok(self):
        row = {
            "part_number": "PN-001",
            "description": "Wire",
            "quantity": "0",
        }
        assert validate_part_row(row, 1) == []

    def test_negative_unit_cost(self):
        row = {
            "part_number": "PN-001",
            "description": "Wire",
            "unit_cost": "-10.0",
        }
        errors = validate_part_row(row, 1)
        assert any("unit_cost cannot be negative" in e for e in errors)

    def test_non_numeric_unit_cost(self):
        row = {
            "part_number": "PN-001",
            "description": "Wire",
            "unit_cost": "xyz",
        }
        errors = validate_part_row(row, 1)
        assert any("unit_cost must be a number" in e for e in errors)

    def test_empty_unit_cost_ok(self):
        row = {
            "part_number": "PN-001",
            "description": "Wire",
            "unit_cost": "",
        }
        assert validate_part_row(row, 1) == []

    def test_negative_min_quantity(self):
        row = {
            "part_number": "PN-001",
            "description": "Wire",
            "min_quantity": "-1",
        }
        errors = validate_part_row(row, 1)
        assert any("min_quantity cannot be negative" in e for e in errors)

    def test_non_integer_min_quantity(self):
        row = {
            "part_number": "PN-001",
            "description": "Wire",
            "min_quantity": "3.5",
        }
        errors = validate_part_row(row, 1)
        assert any("min_quantity must be an integer" in e for e in errors)

    def test_empty_min_quantity_ok(self):
        row = {
            "part_number": "PN-001",
            "description": "Wire",
            "min_quantity": "",
        }
        assert validate_part_row(row, 1) == []

    def test_multiple_errors(self):
        row = {
            "part_number": "",
            "description": "",
            "quantity": "-1",
            "unit_cost": "bad",
            "min_quantity": "-2",
        }
        errors = validate_part_row(row, 1)
        assert len(errors) == 5

    def test_missing_keys_treated_as_empty(self):
        row = {}
        errors = validate_part_row(row, 1)
        # part_number required + description required
        assert len(errors) == 2

    def test_row_num_in_error_messages(self):
        row = {"part_number": "", "description": "Wire"}
        errors = validate_part_row(row, 42)
        assert "Row 42" in errors[0]

    def test_float_quantity_rejected(self):
        row = {
            "part_number": "PN-001",
            "description": "Wire",
            "quantity": "3.7",
        }
        errors = validate_part_row(row, 1)
        assert any("quantity must be an integer" in e for e in errors)
