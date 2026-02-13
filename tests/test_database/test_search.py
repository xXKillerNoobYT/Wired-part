"""Tests for the global search system (v12)."""

import pytest

from wired_part.database.connection import DatabaseConnection
from wired_part.database.models import Job, Part, Supplier, User
from wired_part.database.repository import Repository
from wired_part.database.schema import initialize_database


@pytest.fixture
def repo(tmp_path):
    db = DatabaseConnection(str(tmp_path / "search.db"))
    initialize_database(db)
    return Repository(db)


@pytest.fixture
def populated_repo(repo):
    """Repo with jobs, parts, users, and orders for searching."""
    # Users
    u1 = User(
        username="jdoe", display_name="John Doe",
        pin_hash=Repository.hash_pin("1234"),
    )
    u1.id = repo.create_user(u1)
    u2 = User(
        username="jsmith", display_name="Jane Smith",
        pin_hash=Repository.hash_pin("5678"),
    )
    u2.id = repo.create_user(u2)

    # Jobs
    j1 = Job(
        job_number="J-2026-001", name="Main St Remodel",
        customer="Acme Corp", status="active",
    )
    j1.id = repo.create_job(j1)
    j2 = Job(
        job_number="J-2026-002", name="Office Tower Phase 2",
        customer="BigCo Inc", status="active",
    )
    j2.id = repo.create_job(j2)
    j3 = Job(
        job_number="J-2026-003", name="Residential Wiring",
        customer="Acme Corp", status="completed",
    )
    j3.id = repo.create_job(j3)

    # Parts
    cat = repo.get_all_categories()[0]
    p1 = Part(
        part_number="WIRE-12-2", name="Romex 12/2",
        description="12/2 NM-B Romex 250ft", quantity=100,
        unit_cost=89.99, category_id=cat.id,
    )
    p1.id = repo.create_part(p1)
    p2 = Part(
        part_number="BRKR-20A", name="20A Breaker",
        description="20A Single Pole Breaker", quantity=50,
        unit_cost=12.50, category_id=cat.id,
    )
    p2.id = repo.create_part(p2)

    # Supplier + Order
    s = Supplier(name="Big Electric Supply")
    s.id = repo.create_supplier(s)
    from wired_part.database.models import PurchaseOrder
    po = PurchaseOrder(
        order_number="PO-2026-001", supplier_id=s.id,
        status="submitted", created_by=u1.id,
    )
    po.id = repo.create_purchase_order(po)

    return {
        "repo": repo, "users": [u1, u2], "jobs": [j1, j2, j3],
        "parts": [p1, p2], "supplier": s, "order": po,
    }


class TestSearchAll:
    def test_search_finds_jobs_by_number(self, populated_repo):
        repo = populated_repo["repo"]
        results = repo.search_all("2026-001")
        assert len(results["jobs"]) >= 1
        assert "Main St" in results["jobs"][0]["label"]

    def test_search_finds_jobs_by_name(self, populated_repo):
        repo = populated_repo["repo"]
        results = repo.search_all("Remodel")
        assert len(results["jobs"]) >= 1

    def test_search_finds_jobs_by_customer(self, populated_repo):
        repo = populated_repo["repo"]
        results = repo.search_all("Acme")
        assert len(results["jobs"]) >= 1

    def test_search_finds_parts_by_number(self, populated_repo):
        repo = populated_repo["repo"]
        results = repo.search_all("WIRE-12")
        assert len(results["parts"]) >= 1

    def test_search_finds_parts_by_name(self, populated_repo):
        repo = populated_repo["repo"]
        results = repo.search_all("Romex")
        assert len(results["parts"]) >= 1

    def test_search_finds_users(self, populated_repo):
        repo = populated_repo["repo"]
        results = repo.search_all("John")
        assert len(results["users"]) >= 1

    def test_search_finds_orders(self, populated_repo):
        repo = populated_repo["repo"]
        results = repo.search_all("PO-2026")
        assert len(results["orders"]) >= 1

    def test_search_case_insensitive(self, populated_repo):
        repo = populated_repo["repo"]
        results = repo.search_all("remodel")
        assert len(results["jobs"]) >= 1

    def test_search_partial_match(self, populated_repo):
        repo = populated_repo["repo"]
        results = repo.search_all("Main")
        assert len(results["jobs"]) >= 1

    def test_search_empty_query(self, populated_repo):
        repo = populated_repo["repo"]
        results = repo.search_all("")
        assert results == {
            "jobs": [], "parts": [], "users": [],
            "orders": [], "pages": [],
        }

    def test_search_no_results(self, populated_repo):
        repo = populated_repo["repo"]
        results = repo.search_all("zzzznonexistent")
        assert all(len(v) == 0 for v in results.values())

    def test_search_result_structure(self, populated_repo):
        repo = populated_repo["repo"]
        results = repo.search_all("Main")
        job = results["jobs"][0]
        assert "id" in job
        assert "label" in job
        assert "sublabel" in job
        assert "type" in job
        assert job["type"] == "job"

    def test_active_jobs_ranked_first(self, populated_repo):
        repo = populated_repo["repo"]
        # "Acme" matches both active and completed jobs
        results = repo.search_all("Acme")
        assert len(results["jobs"]) >= 2
        # Active jobs should come first
        assert "[active]" in results["jobs"][0]["sublabel"]
