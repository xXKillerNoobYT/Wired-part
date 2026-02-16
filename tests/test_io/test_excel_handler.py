"""Tests for the Excel import/export handler."""

import pytest
from pathlib import Path

from wired_part.database.connection import DatabaseConnection
from wired_part.database.models import Job, Part
from wired_part.database.repository import Repository
from wired_part.database.schema import initialize_database


@pytest.fixture
def repo(tmp_path):
    db = DatabaseConnection(str(tmp_path / "excel_test.db"))
    initialize_database(db)
    return Repository(db)


@pytest.fixture
def sample_parts(repo):
    cat = repo.get_all_categories()[0]
    parts = []
    for pn, name, qty, cost in [
        ("XL-001", "Excel Wire", 50, 10.0),
        ("XL-002", "Excel Breaker", 30, 25.0),
    ]:
        p = Part(
            part_number=pn, name=name, description=name,
            quantity=qty, unit_cost=cost, category_id=cat.id,
        )
        p.id = repo.create_part(p)
        parts.append(p)
    return parts


@pytest.fixture
def sample_jobs(repo):
    jobs = []
    for jn, name in [("J-XL-001", "Excel Job 1"), ("J-XL-002", "Excel Job 2")]:
        j = Job(job_number=jn, name=name, status="active")
        j.id = repo.create_job(j)
        jobs.append(j)
    return jobs


class TestExportPartsExcel:
    def test_creates_file(self, repo, sample_parts, tmp_path):
        from wired_part.io.excel_handler import export_parts_excel
        filepath = tmp_path / "parts.xlsx"
        count = export_parts_excel(repo, filepath)
        assert filepath.exists()
        assert count >= 2

    def test_creates_parent_dirs(self, repo, sample_parts, tmp_path):
        from wired_part.io.excel_handler import export_parts_excel
        filepath = tmp_path / "subdir" / "parts.xlsx"
        count = export_parts_excel(repo, filepath)
        assert filepath.exists()

    def test_empty_db_exports_zero(self, repo, tmp_path):
        from wired_part.io.excel_handler import export_parts_excel
        filepath = tmp_path / "empty.xlsx"
        count = export_parts_excel(repo, filepath)
        assert count == 0


class TestExportJobsExcel:
    def test_creates_file(self, repo, sample_jobs, tmp_path):
        from wired_part.io.excel_handler import export_jobs_excel
        filepath = tmp_path / "jobs.xlsx"
        count = export_jobs_excel(repo, filepath)
        assert filepath.exists()
        assert count >= 2


class TestImportPartsExcel:
    def test_import_roundtrip(self, repo, sample_parts, tmp_path):
        from wired_part.io.excel_handler import (
            export_parts_excel,
            import_parts_excel,
        )
        filepath = tmp_path / "roundtrip.xlsx"
        export_parts_excel(repo, filepath)

        # Create fresh repo for import
        db2 = DatabaseConnection(str(tmp_path / "import_test.db"))
        initialize_database(db2)
        repo2 = Repository(db2)

        result = import_parts_excel(repo2, filepath)
        assert result["imported"] >= 2
        assert result["errors"] == []
