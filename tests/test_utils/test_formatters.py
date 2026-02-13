"""Tests for formatting utilities."""

from wired_part.utils.formatters import format_currency, format_quantity


class TestFormatCurrency:
    """Test USD currency formatting."""

    def test_basic_amount(self):
        assert format_currency(10.00) == "$10.00"

    def test_with_cents(self):
        assert format_currency(42.99) == "$42.99"

    def test_zero(self):
        assert format_currency(0) == "$0.00"

    def test_large_number_comma_separated(self):
        assert format_currency(1234567.89) == "$1,234,567.89"

    def test_small_cents(self):
        assert format_currency(0.01) == "$0.01"

    def test_negative_amount(self):
        assert format_currency(-50.00) == "$-50.00"

    def test_thousands(self):
        assert format_currency(9999.99) == "$9,999.99"


class TestFormatQuantity:
    """Test quantity formatting with low-stock flag."""

    def test_normal_quantity(self):
        assert format_quantity(100) == "100"

    def test_zero_quantity(self):
        assert format_quantity(0) == "0"

    def test_low_stock_flagged(self):
        assert format_quantity(3, min_quantity=10) == "3 (LOW)"

    def test_at_minimum_not_flagged(self):
        assert format_quantity(10, min_quantity=10) == "10"

    def test_above_minimum_not_flagged(self):
        assert format_quantity(50, min_quantity=10) == "50"

    def test_no_minimum_set(self):
        assert format_quantity(5, min_quantity=0) == "5"

    def test_default_min_quantity(self):
        assert format_quantity(0) == "0"
