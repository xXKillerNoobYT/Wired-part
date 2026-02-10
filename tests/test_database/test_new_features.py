"""Tests for new features: job priority, truck assignment notifications,
low stock alerts on consumption, and billing data."""

import pytest

from wired_part.database.models import (
    Job,
    JobAssignment,
    Notification,
    Part,
    Truck,
    TruckTransfer,
    User,
)
from wired_part.database.repository import Repository


@pytest.fixture
def feature_data(repo):
    """Create base data for feature tests."""
    user = User(
        username="tech1", display_name="Tech One",
        pin_hash=Repository.hash_pin("1234"),
        role="user", is_active=1,
    )
    user_id = repo.create_user(user)

    user2 = User(
        username="tech2", display_name="Tech Two",
        pin_hash=Repository.hash_pin("5678"),
        role="user", is_active=1,
    )
    user2_id = repo.create_user(user2)

    truck = Truck(
        truck_number="FT-001", name="Feature Truck",
        assigned_user_id=user_id, is_active=1,
    )
    truck_id = repo.create_truck(truck)

    cats = repo.get_all_categories()
    wire_cat = next((c for c in cats if c.name == "Wire & Cable"), None)
    cat_id = wire_cat.id if wire_cat else None

    part = Part(
        part_number="FT-WIRE-001", description="14/2 Romex 250ft",
        quantity=100, unit_cost=85.0, min_quantity=20,
        category_id=cat_id,
    )
    part_id = repo.create_part(part)

    # Transfer 30 to truck and receive
    transfer = TruckTransfer(
        truck_id=truck_id, part_id=part_id,
        quantity=30, created_by=user_id,
    )
    tid = repo.create_transfer(transfer)
    repo.receive_transfer(tid, user_id)

    # Create job
    job = Job(
        job_number="JOB-FT-001", name="Feature Test Job",
        customer="Test Customer", address="123 Test St",
        status="active", priority=2,
    )
    job_id = repo.create_job(job)

    return {
        "user_id": user_id,
        "user2_id": user2_id,
        "truck_id": truck_id,
        "part_id": part_id,
        "job_id": job_id,
        "cat_id": cat_id,
    }


class TestJobPriority:
    """Test job priority field and ordering."""

    def test_create_job_with_priority(self, repo):
        jid = repo.create_job(Job(
            job_number="PRI-001", name="Urgent Job",
            status="active", priority=1,
        ))
        job = repo.get_job_by_id(jid)
        assert job.priority == 1

    def test_default_priority_is_3(self, repo):
        jid = repo.create_job(Job(
            job_number="PRI-002", name="Normal Job",
            status="active",
        ))
        job = repo.get_job_by_id(jid)
        assert job.priority == 3

    def test_jobs_sorted_by_priority(self, repo):
        repo.create_job(Job(
            job_number="PRI-LOW", name="Low Priority",
            status="active", priority=5,
        ))
        repo.create_job(Job(
            job_number="PRI-URG", name="Urgent",
            status="active", priority=1,
        ))
        repo.create_job(Job(
            job_number="PRI-NRM", name="Normal",
            status="active", priority=3,
        ))

        jobs = repo.get_all_jobs("active")
        priorities = [j.priority for j in jobs]
        assert priorities == sorted(priorities)
        assert jobs[0].priority == 1
        assert jobs[-1].priority == 5

    def test_update_job_priority(self, repo):
        jid = repo.create_job(Job(
            job_number="PRI-UPD", name="Update Priority",
            status="active", priority=3,
        ))
        job = repo.get_job_by_id(jid)
        job.priority = 1
        repo.update_job(job)

        updated = repo.get_job_by_id(jid)
        assert updated.priority == 1


class TestTruckAssignmentNotifications:
    """Test that notifications are created when truck assignment changes."""

    def test_assign_truck_creates_notification(self, repo, feature_data):
        """Assigning a truck to a new user should notify that user."""
        # Create an unassigned truck
        tid = repo.create_truck(Truck(
            truck_number="NOTIF-001", name="Notification Truck",
            is_active=1,
        ))

        # Assign to user
        truck = repo.get_truck_by_id(tid)
        truck.assigned_user_id = feature_data["user_id"]
        repo.update_truck(truck)

        # User should have a notification about the assignment
        notifs = repo.get_user_notifications(feature_data["user_id"])
        assign_notifs = [
            n for n in notifs if n.title == "Truck Assigned"
        ]
        assert len(assign_notifs) >= 1
        assert "NOTIF-001" in assign_notifs[0].message

    def test_unassign_truck_creates_notification(self, repo, feature_data):
        """Unassigning a truck should notify the previous user."""
        # The truck from feature_data is assigned to user_id
        truck = repo.get_truck_by_id(feature_data["truck_id"])
        truck.assigned_user_id = None
        repo.update_truck(truck)

        notifs = repo.get_user_notifications(feature_data["user_id"])
        unassign_notifs = [
            n for n in notifs if n.title == "Truck Unassigned"
        ]
        assert len(unassign_notifs) >= 1
        assert "FT-001" in unassign_notifs[0].message

    def test_reassign_truck_notifies_both_users(self, repo, feature_data):
        """Reassigning a truck should notify both old and new user."""
        # The truck is currently assigned to user_id
        truck = repo.get_truck_by_id(feature_data["truck_id"])
        truck.assigned_user_id = feature_data["user2_id"]
        repo.update_truck(truck)

        # Old user should get "unassigned" notification
        notifs1 = repo.get_user_notifications(feature_data["user_id"])
        unassign = [n for n in notifs1 if n.title == "Truck Unassigned"]
        assert len(unassign) >= 1

        # New user should get "assigned" notification
        notifs2 = repo.get_user_notifications(feature_data["user2_id"])
        assign = [n for n in notifs2 if n.title == "Truck Assigned"]
        assert len(assign) >= 1

    def test_no_notification_when_assignment_unchanged(self, repo, feature_data):
        """Updating truck without changing assignment should not notify."""
        truck = repo.get_truck_by_id(feature_data["truck_id"])
        initial_count = repo.get_unread_count(feature_data["user_id"])

        # Update truck name, but keep same assignment
        truck.name = "Renamed Truck"
        repo.update_truck(truck)

        final_count = repo.get_unread_count(feature_data["user_id"])
        assert final_count == initial_count


class TestLowStockAlertsOnConsumption:
    """Test that low stock alerts are created after truck consumption."""

    def test_low_stock_alert_created(self, repo, feature_data):
        """When warehouse stock drops below min_quantity after consumption,
        a broadcast notification should be created."""
        # Part has qty=70 (100 - 30 transferred), min_quantity=20
        # Consume enough from truck so warehouse stock stays above min
        # but we need to set up a scenario where warehouse stock < min

        # Create a part with low warehouse stock
        low_part_id = repo.create_part(Part(
            part_number="LOW-ALERT-001", description="Low stock part",
            quantity=15, unit_cost=10.0, min_quantity=20,
        ))

        # Transfer some to the truck and receive
        tf = TruckTransfer(
            truck_id=feature_data["truck_id"],
            part_id=low_part_id,
            quantity=10,
            created_by=feature_data["user_id"],
        )
        tid = repo.create_transfer(tf)
        repo.receive_transfer(tid, feature_data["user_id"])
        # Warehouse now has 5 (15 - 10), which is < min_quantity(20)

        # Consume from truck — this should trigger a low stock alert
        repo.consume_from_truck(
            job_id=feature_data["job_id"],
            truck_id=feature_data["truck_id"],
            part_id=low_part_id,
            quantity=2,
            user_id=feature_data["user_id"],
        )

        # Check for broadcast notification about low stock
        notifs = repo.get_user_notifications(feature_data["user_id"])
        low_stock_notifs = [
            n for n in notifs
            if "Low Stock" in n.title and "LOW-ALERT-001" in n.title
        ]
        assert len(low_stock_notifs) >= 1
        assert "warning" == low_stock_notifs[0].severity

    def test_no_alert_when_stock_above_min(self, repo, feature_data):
        """No low stock notification when warehouse stock is above min."""
        # feature_data part has qty=70 (100-30), min_quantity=20
        # Consuming from truck shouldn't trigger alert because
        # warehouse stock is well above min
        repo.consume_from_truck(
            job_id=feature_data["job_id"],
            truck_id=feature_data["truck_id"],
            part_id=feature_data["part_id"],
            quantity=2,
            user_id=feature_data["user_id"],
        )

        notifs = repo.get_user_notifications(feature_data["user_id"])
        low_stock_notifs = [
            n for n in notifs
            if "Low Stock" in n.title and "FT-WIRE-001" in n.title
        ]
        assert len(low_stock_notifs) == 0


class TestBillingData:
    """Test billing data retrieval."""

    def test_billing_data_basic(self, repo, feature_data):
        """Get billing data for a job with consumed parts."""
        repo.consume_from_truck(
            job_id=feature_data["job_id"],
            truck_id=feature_data["truck_id"],
            part_id=feature_data["part_id"],
            quantity=5,
            user_id=feature_data["user_id"],
        )

        data = repo.get_billing_data(feature_data["job_id"])
        assert data is not None
        assert data["job"]["job_number"] == "JOB-FT-001"
        assert data["job"]["customer"] == "Test Customer"
        assert data["subtotal"] == 5 * 85.0  # 5 units at $85
        assert len(data["categories"]) >= 1

    def test_billing_data_with_assignments(self, repo, feature_data):
        """Billing data should include assigned users."""
        assignment = JobAssignment(
            job_id=feature_data["job_id"],
            user_id=feature_data["user_id"],
            role="lead",
        )
        repo.assign_user_to_job(assignment)

        # Add some consumption
        repo.consume_from_truck(
            job_id=feature_data["job_id"],
            truck_id=feature_data["truck_id"],
            part_id=feature_data["part_id"],
            quantity=3,
            user_id=feature_data["user_id"],
        )

        data = repo.get_billing_data(feature_data["job_id"])
        assert len(data["assigned_users"]) == 1
        assert data["assigned_users"][0]["name"] == "Tech One"
        assert data["assigned_users"][0]["role"] == "lead"

    def test_billing_data_empty_job(self, repo):
        """Billing data for a job with no parts should work."""
        jid = repo.create_job(Job(
            job_number="BILL-EMPTY", name="Empty Job",
            status="active",
        ))
        data = repo.get_billing_data(jid)
        assert data["subtotal"] == 0.0
        assert len(data["categories"]) == 0
        assert data["consumption_count"] == 0

    def test_billing_data_nonexistent_job(self, repo):
        """Billing data for a nonexistent job should return empty dict."""
        data = repo.get_billing_data(9999)
        assert data == {}

    def test_billing_data_category_grouping(self, repo, feature_data):
        """Billing data should group parts by category."""
        # Create a part in a different category
        cats = repo.get_all_categories()
        breaker_cat = next(
            (c for c in cats if c.name == "Breakers & Fuses"), None
        )

        other_part_id = repo.create_part(Part(
            part_number="FT-BRKR-001", description="20A Breaker",
            quantity=50, unit_cost=12.0, min_quantity=5,
            category_id=breaker_cat.id if breaker_cat else None,
        ))

        # Transfer and receive the other part to truck
        tf = TruckTransfer(
            truck_id=feature_data["truck_id"],
            part_id=other_part_id,
            quantity=10,
            created_by=feature_data["user_id"],
        )
        tid = repo.create_transfer(tf)
        repo.receive_transfer(tid, feature_data["user_id"])

        # Consume both parts
        repo.consume_from_truck(
            job_id=feature_data["job_id"],
            truck_id=feature_data["truck_id"],
            part_id=feature_data["part_id"],
            quantity=3,
            user_id=feature_data["user_id"],
        )
        repo.consume_from_truck(
            job_id=feature_data["job_id"],
            truck_id=feature_data["truck_id"],
            part_id=other_part_id,
            quantity=2,
            user_id=feature_data["user_id"],
        )

        data = repo.get_billing_data(feature_data["job_id"])
        assert len(data["categories"]) >= 2
        expected_total = (3 * 85.0) + (2 * 12.0)
        assert abs(data["subtotal"] - expected_total) < 0.01
