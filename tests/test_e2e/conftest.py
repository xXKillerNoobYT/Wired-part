"""E2E test fixtures — fully wired-up test environment."""

import pytest

from wired_part.database.connection import DatabaseConnection
from wired_part.database.models import (
    Job, JobAssignment, Part, PurchaseOrder, PurchaseOrderItem,
    Supplier, Truck, TruckTransfer, User,
)
from wired_part.database.repository import Repository
from wired_part.database.schema import initialize_database


@pytest.fixture
def repo(tmp_path):
    """Fresh initialized database + repository."""
    db = DatabaseConnection(str(tmp_path / "e2e.db"))
    initialize_database(db)
    return Repository(db)


@pytest.fixture
def admin_user(repo):
    """Admin user with full permissions (Admin hat)."""
    user = User(
        username="admin",
        display_name="Admin Boss",
        pin_hash=Repository.hash_pin("1234"),
        role="admin",
    )
    user.id = repo.create_user(user)
    admin_hat = repo.get_hat_by_id(1)  # Admin hat is always id=1
    repo.assign_hat(user.id, admin_hat.id)
    return user


@pytest.fixture
def foreman_user(repo):
    """Foreman user with limited permissions."""
    user = User(
        username="foreman",
        display_name="Site Foreman",
        pin_hash=Repository.hash_pin("5678"),
        role="user",
    )
    user.id = repo.create_user(user)
    foreman_hat = repo.get_hat_by_name("Foreman")
    repo.assign_hat(user.id, foreman_hat.id)
    return user


@pytest.fixture
def worker_user(repo):
    """Worker user with minimal permissions."""
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
def supplier(repo):
    """Active supplier for purchase orders."""
    s = Supplier(
        name="Acme Electric Supply",
        contact_name="John Supplier",
        email="john@acme.com",
        phone="555-1234",
        is_supply_house=1,
        operating_hours="Mon-Fri 6am-5pm",
    )
    s.id = repo.create_supplier(s)
    return s


@pytest.fixture
def parts(repo, supplier):
    """5 test parts with warehouse stock and linked supplier."""
    from wired_part.database.models import PartSupplier

    items = [
        ("WIRE-12-2", "12/2 NM-B Romex 250ft", 100, 89.99),
        ("WIRE-14-2", "14/2 NM-B Romex 250ft", 80, 64.99),
        ("BRKR-20A", "20A Single Pole Breaker", 50, 12.50),
        ("OUTLET-DR", "Duplex Outlet Decora White", 200, 2.75),
        ("BOX-NW-1G", "New Work 1-Gang Box", 150, 0.85),
    ]
    result = []
    cat = repo.get_all_categories()[0]  # Use first category
    for pn, desc, qty, cost in items:
        p = Part(
            part_number=pn,
            name=desc.split()[0],
            description=desc,
            quantity=qty,
            unit_cost=cost,
            category_id=cat.id,
            min_quantity=10,
            max_quantity=qty * 3,
        )
        p.id = repo.create_part(p)
        # Link supplier
        repo.link_part_supplier(PartSupplier(
            part_id=p.id, supplier_id=supplier.id,
        ))
        result.append(p)
    return result


@pytest.fixture
def truck_a(repo, admin_user):
    """Truck assigned to admin user."""
    t = Truck(
        truck_number="T-001",
        name="Admin Van",
        assigned_user_id=admin_user.id,
    )
    t.id = repo.create_truck(t)
    return t


@pytest.fixture
def truck_b(repo, foreman_user):
    """Truck assigned to foreman user."""
    t = Truck(
        truck_number="T-002",
        name="Foreman Truck",
        assigned_user_id=foreman_user.id,
    )
    t.id = repo.create_truck(t)
    return t


@pytest.fixture
def active_job(repo, admin_user, foreman_user):
    """Active job with both users assigned."""
    job = Job(
        job_number=repo.generate_job_number(),
        name="Big Electrical Remodel",
        customer="Test Customer Inc.",
        address="123 Main St, Anytown USA",
        status="active",
        priority=2,
    )
    job.id = repo.create_job(job)
    # Lead = admin, Worker = foreman
    repo.assign_user_to_job(JobAssignment(
        job_id=job.id, user_id=admin_user.id, role="lead",
    ))
    repo.assign_user_to_job(JobAssignment(
        job_id=job.id, user_id=foreman_user.id, role="worker",
    ))
    return job
