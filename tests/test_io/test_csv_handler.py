"""Tests for CSV import/export."""

import csv
from pathlib import Path

import pytest

from wired_part.database.models import Part
from wired_part.io.csv_handler import export_parts_csv, import_parts_csv


class TestCSVExport:
    def test_export_parts(self, repo, tmp_path):
        repo.create_part(Part(
            part_number="EXP-001",
            description="Export test part",
            quantity=5,
            unit_cost=9.99,
        ))

        outfile = tmp_path / "export.csv"
        count = export_parts_csv(repo, outfile)
        assert count == 1
        assert outfile.exists()

        with open(outfile) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) == 1
        assert rows[0]["part_number"] == "EXP-001"


class TestCSVImport:
    def test_import_new_parts(self, repo, tmp_path):
        csv_file = tmp_path / "import.csv"
        csv_file.write_text(
            "part_number,description,quantity,unit_cost\n"
            "IMP-001,Imported Part,10,5.99\n"
            "IMP-002,Another Part,20,12.50\n"
        )

        results = import_parts_csv(repo, csv_file)
        assert results["imported"] == 2
        assert results["skipped"] == 0
        assert not results["errors"]

        part = repo.get_part_by_number("IMP-001")
        assert part is not None
        assert part.quantity == 10

    def test_skip_duplicates(self, repo, tmp_path):
        repo.create_part(Part(
            part_number="DUP-001",
            description="Existing",
            quantity=1,
        ))

        csv_file = tmp_path / "dup.csv"
        csv_file.write_text(
            "part_number,description,quantity\n"
            "DUP-001,Should be skipped,99\n"
        )

        results = import_parts_csv(repo, csv_file)
        assert results["skipped"] == 1
        assert results["imported"] == 0

        # Original unchanged
        part = repo.get_part_by_number("DUP-001")
        assert part.quantity == 1

    def test_update_existing(self, repo, tmp_path):
        repo.create_part(Part(
            part_number="UPD-CSV",
            description="Original",
            quantity=5,
        ))

        csv_file = tmp_path / "update.csv"
        csv_file.write_text(
            "part_number,description,quantity\n"
            "UPD-CSV,Updated via CSV,25\n"
        )

        results = import_parts_csv(repo, csv_file, update_existing=True)
        assert results["updated"] == 1

        part = repo.get_part_by_number("UPD-CSV")
        assert part.description == "Updated via CSV"
        assert part.quantity == 25

    def test_validation_errors(self, repo, tmp_path):
        csv_file = tmp_path / "bad.csv"
        csv_file.write_text(
            "part_number,description,quantity\n"
            ",Missing part number,5\n"
            "BAD-QTY,Bad quantity,abc\n"
        )

        results = import_parts_csv(repo, csv_file)
        assert results["skipped"] == 2
        assert len(results["errors"]) >= 2
