"""Validation rules for import data."""


def validate_part_row(row: dict, row_num: int) -> list[str]:
    """Validate a single row of part import data. Returns list of error strings."""
    errors = []

    pn = row.get("part_number", "").strip()
    if not pn:
        errors.append(f"Row {row_num}: part_number is required")
    elif len(pn) > 50:
        errors.append(f"Row {row_num}: part_number exceeds 50 chars")

    desc = row.get("description", "").strip()
    if not desc:
        errors.append(f"Row {row_num}: description is required")

    qty = row.get("quantity", "")
    if qty != "":
        try:
            q = int(qty)
            if q < 0:
                errors.append(f"Row {row_num}: quantity cannot be negative")
        except (ValueError, TypeError):
            errors.append(f"Row {row_num}: quantity must be an integer")

    cost = row.get("unit_cost", "")
    if cost != "":
        try:
            c = float(cost)
            if c < 0:
                errors.append(f"Row {row_num}: unit_cost cannot be negative")
        except (ValueError, TypeError):
            errors.append(f"Row {row_num}: unit_cost must be a number")

    min_qty = row.get("min_quantity", "")
    if min_qty != "":
        try:
            m = int(min_qty)
            if m < 0:
                errors.append(f"Row {row_num}: min_quantity cannot be negative")
        except (ValueError, TypeError):
            errors.append(f"Row {row_num}: min_quantity must be an integer")

    return errors
