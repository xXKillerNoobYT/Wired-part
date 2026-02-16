"""Shared fixtures for UI tests using pytest-qt."""

import pytest

from wired_part.database.connection import DatabaseConnection
from wired_part.database.models import Job, Part, Supplier, User
from wired_part.database.repository import Repository
from wired_part.database.schema import initialize_database


@pytest.fixture
def repo(tmp_path):
    """Fresh initialized database + repository."""
    db = DatabaseConnection(str(tmp_path / "ui_test.db"))
    initialize_database(db)
    return Repository(db)


@pytest.fixture
def admin_user(repo):
    """Admin user for UI tests."""
    user = User(
        username="admin",
        display_name="Admin User",
        pin_hash=Repository.hash_pin("1234"),
        role="admin",
    )
    user.id = repo.create_user(user)
    admin_hat = repo.get_hat_by_id(1)
    repo.assign_hat(user.id, admin_hat.id)
    return user


@pytest.fixture
def worker_user(repo):
    """Worker user with minimal permissions (no show_dollar_values)."""
    user = User(
        username="worker",
        display_name="Field Worker",
        pin_hash=Repository.hash_pin("9999"),
        role="user",
    )
    user.id = repo.create_user(user)
    worker_hat = repo.get_hat_by_name("Worker")
    repo.assign_hat(user.id, worker_hat.id)
    return user


@pytest.fixture
def sample_parts(repo):
    """Create a handful of parts for UI testing."""
    cat = repo.get_all_categories()[0]
    parts = []
    for pn, name, qty, cost in [
        ("UI-WIRE-001", "Test Wire", 50, 25.00),
        ("UI-BRKR-001", "Test Breaker", 30, 12.50),
        ("UI-OUTL-001", "Test Outlet", 100, 2.75),
    ]:
        p = Part(
            part_number=pn, name=name,
            quantity=qty, unit_cost=cost,
            category_id=cat.id,
        )
        p.id = repo.create_part(p)
        parts.append(p)
    return parts


@pytest.fixture
def sample_job(repo, admin_user):
    """Create a sample active job."""
    job = Job(
        job_number="J-UI-001",
        name="UI Test Job",
        customer="Test Customer",
        status="active",
    )
    job.id = repo.create_job(job)
    return job


@pytest.fixture
def sample_supplier(repo):
    """Create a sample supplier."""
    s = Supplier(name="UI Test Supplier", email="test@supplier.com")
    s.id = repo.create_supplier(s)
    return s
