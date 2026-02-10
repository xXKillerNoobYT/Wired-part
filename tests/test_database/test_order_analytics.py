"""Tests for order analytics and summary methods."""

import pytest

from wired_part.database.connection import DatabaseConnection
from wired_part.database.models import (
    Part,
    PurchaseOrder,
    PurchaseOrderItem,
    ReturnAuthorization,
    ReturnAuthorizationItem,
    Supplier,
    User,
)
from wired_part.database.repository import Repository
from wired_part.database.schema import initialize_database


@pytest.fixture
def repo(tmp_path):
    db_path = tmp_path / "test.db"
    db = DatabaseConnection(str(db_path))
    initialize_database(db)
    return Repository(db)


@pytest.fixture
def supplier(repo):
    s = Supplier(name="Acme Electric", is_active=1)
    s.id = repo.create_supplier(s)
    return s


@pytest.fixture
def parts(repo):
    p1 = Part(
        part_number="WIRE-001",
        description="14 AWG Wire",
        quantity=100,
        unit_cost=0.50,
    )
    p1.id = repo.create_part(p1)
    return [p1]


@pytest.fixture
def test_user(repo):
    user = User(
        username="testuser",
        display_name="Test User",
        pin_hash=Repository.hash_pin("1234"),
        role="admin",
    )
    user.id = repo.create_user(user)
    return user


@pytest.fixture
def sample_orders(repo, supplier, parts, test_user):
    """Create a few orders in various states."""
    orders = []
    for i in range(3):
        order = PurchaseOrder(
            order_number=repo.generate_order_number(),
            supplier_id=supplier.id,
            status="draft",
            created_by=test_user.id,
        )
        order.id = repo.create_purchase_order(order)
        repo.add_order_item(PurchaseOrderItem(
            order_id=order.id,
            part_id=parts[0].id,
            quantity_ordered=10 * (i + 1),
            unit_cost=0.50,
        ))
        orders.append(order)

    # Submit the first two
    repo.submit_purchase_order(orders[0].id)
    repo.submit_purchase_order(orders[1].id)

    return orders


class TestOrderAnalytics:
    """Test order analytics aggregation."""

    def test_order_analytics_basic(self, repo, sample_orders):
        analytics = repo.get_order_analytics()
        assert analytics["total_orders"] == 3
        assert analytics["total_spent"] > 0
        assert analytics["top_supplier"] == "Acme Electric"

    def test_order_analytics_by_status(self, repo, sample_orders):
        analytics = repo.get_order_analytics()
        assert "by_status" in analytics
        assert analytics["by_status"].get("submitted", 0) == 2
        assert analytics["by_status"].get("draft", 0) == 1

    def test_supplier_order_history(self, repo, sample_orders, supplier):
        history = repo.get_supplier_order_history(supplier.id)
        assert len(history) == 3

    def test_orders_summary_for_dashboard(self, repo, sample_orders):
        summary = repo.get_orders_summary()
        assert summary["pending_orders"] == 2  # 2 submitted
        assert summary["draft_orders"] == 1
        assert summary["items_awaiting"] > 0
        assert summary["open_returns"] == 0
