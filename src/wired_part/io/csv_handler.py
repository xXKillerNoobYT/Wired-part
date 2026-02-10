"""CSV import and export for parts and jobs."""

import csv
from pathlib import Path
from typing import Optional

from wired_part.database.models import Part
from wired_part.database.repository import Repository
from wired_part.io.validators import validate_part_row

PART_CSV_COLUMNS = [
    "part_number", "description", "quantity", "min_quantity",
    "location", "category", "unit_cost", "supplier", "notes",
]

JOB_CSV_COLUMNS = [
    "job_number", "name", "customer", "address", "status", "notes",
]


def export_parts_csv(repo: Repository, filepath: str | Path) -> int:
    """Export all parts to CSV. Returns the number of rows written."""
    parts = repo.get_all_parts()
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=PART_CSV_COLUMNS)
        writer.writeheader()
        for part in parts:
            writer.writerow({
                "part_number": part.part_number,
                "description": part.description,
                "quantity": part.quantity,
                "min_quantity": part.min_quantity,
                "location": part.location,
                "category": part.category_name,
                "unit_cost": part.unit_cost,
                "supplier": part.supplier,
                "notes": part.notes,
            })
    return len(parts)


def export_jobs_csv(repo: Repository, filepath: str | Path) -> int:
    """Export all jobs to CSV. Returns the number of rows written."""
    jobs = repo.get_all_jobs()
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=JOB_CSV_COLUMNS)
        writer.writeheader()
        for job in jobs:
            writer.writerow({
                "job_number": job.job_number,
                "name": job.name,
                "customer": job.customer,
                "address": job.address,
                "status": job.status,
                "notes": job.notes,
            })
    return len(jobs)


def import_parts_csv(
    repo: Repository,
    filepath: str | Path,
    update_existing: bool = False,
) -> dict:
    """Import parts from CSV. Returns results dict with counts and errors."""
    filepath = Path(filepath)
    results = {"imported": 0, "updated": 0, "skipped": 0, "errors": []}

    # Build category name -> id lookup
    categories = {c.name: c.id for c in repo.get_all_categories()}

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row_num, row in enumerate(reader, start=2):
                errors = validate_part_row(row, row_num)
                if errors:
                    results["errors"].extend(errors)
                    results["skipped"] += 1
                    continue

                pn = row["part_number"].strip()
                existing = repo.get_part_by_number(pn)

                category_id = categories.get(
                    row.get("category", "").strip()
                )

                part = Part(
                    id=existing.id if existing else None,
                    part_number=pn,
                    description=row.get("description", "").strip(),
                    quantity=int(row.get("quantity", 0) or 0),
                    min_quantity=int(row.get("min_quantity", 0) or 0),
                    location=row.get("location", "").strip(),
                    category_id=category_id,
                    unit_cost=float(row.get("unit_cost", 0) or 0),
                    supplier=row.get("supplier", "").strip(),
                    notes=row.get("notes", "").strip(),
                )

                if existing and update_existing:
                    repo.update_part(part)
                    results["updated"] += 1
                elif existing:
                    results["skipped"] += 1
                else:
                    repo.create_part(part)
                    results["imported"] += 1

    except Exception as e:
        results["errors"].append(f"File error: {e}")

    return results
