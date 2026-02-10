"""Formatting utilities for display values."""


def format_currency(value: float) -> str:
    """Format a float as USD currency."""
    return f"${value:,.2f}"


def format_quantity(value: int, min_quantity: int = 0) -> str:
    """Format quantity, flagging low stock."""
    if min_quantity > 0 and value < min_quantity:
        return f"{value} (LOW)"
    return str(value)
