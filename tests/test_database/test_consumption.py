"""Tests for part consumption from truck to job."""

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
def full_setup(repo):
    """Create user, truck, part (with on-hand), and active job."""
    user = User(
        username="tech1", display_name="Tech One",
        pin_hash=Repository.hash_pin("1234"),
        role="user", is_active=1,
    )
    user_id = repo.create_user(user)

    truck = Truck(
        truck_number="T-200", name="Service Van",
        assigned_user_id=user_id, is_active=1,
    )
    truck_id = repo.create_truck(truck)

    part = Part(
        part_number="WIRE-200", description="14/2 Romex",
        quantity=50, unit_cost=15.0, min_quantity=5,
    )
    part_id = repo.create_part(part)

    # Transfer 20 to truck and receive
    transfer = TruckTransfer(
        truck_id=truck_id, part_id=part_id,
        quantity=20, created_by=user_id,
    )
    tid = repo.create_transfer(transfer)
    repo.receive_transfer(tid, user_id)

    # Create job
    job = Job(job_number="JOB-TEST-001", name="Test Job", status="active")
    job_id = repo.create_job(job)

    return {
        "user_id": user_id,
        "truck_id": truck_id,
        "part_id": part_id,
        "job_id": job_id,
    }


class TestConsumption:
    """Test consuming parts from truck on-hand to a job."""

    def test_consume_from_truck(self, repo, full_setup):
        repo.consume_from_truck(
            job_id=full_setup["job_id"],
            truck_id=full_setup["truck_id"],
            part_id=full_setup["part_id"],
            quantity=5,
            user_id=full_setup["user_id"],
        )

        # Truck on-hand should decrease
        inv = repo.get_truck_inventory(full_setup["truck_id"])
        assert inv[0].quantity == 15

        # Job should have parts assigned
        jp = repo.get_job_parts(full_setup["job_id"])
        assert len(jp) == 1
        assert jp[0].quantity_used == 5

        # Consumption log should have entry
        logs = repo.get_consumption_log(job_id=full_setup["job_id"])
        assert len(logs) == 1
        assert logs[0].quantity == 5

    def test_consume_insufficient_truck_stock(self, repo, full_setup):
        with pytest.raises(ValueError, match="Insufficient truck stock"):
            repo.consume_from_truck(
                job_id=full_setup["job_id"],
                truck_id=full_setup["truck_id"],
                part_id=full_setup["part_id"],
                quantity=999,
                user_id=full_setup["user_id"],
            )

    def test_consume_accumulates_on_same_part(self, repo, full_setup):
        repo.consume_from_truck(
            job_id=full_setup["job_id"],
            truck_id=full_setup["truck_id"],
            part_id=full_setup["part_id"],
            quantity=3,
            user_id=full_setup["user_id"],
        )
        repo.consume_from_truck(
            job_id=full_setup["job_id"],
            truck_id=full_setup["truck_id"],
            part_id=full_setup["part_id"],
            quantity=2,
            user_id=full_setup["user_id"],
        )

        jp = repo.get_job_parts(full_setup["job_id"])
        assert len(jp) == 1
        assert jp[0].quantity_used == 5

        # Truck should have 20 - 5 = 15
        inv = repo.get_truck_inventory(full_setup["truck_id"])
        assert inv[0].quantity == 15


class TestJobAssignments:
    """Test user-to-job assignment management."""

    def test_assign_user_to_job(self, repo, full_setup):
        assignment = JobAssignment(
            job_id=full_setup["job_id"],
            user_id=full_setup["user_id"],
            role="lead",
        )
        aid = repo.assign_user_to_job(assignment)
        assert aid > 0

        assignments = repo.get_job_assignments(full_setup["job_id"])
        assert len(assignments) == 1
        assert assignments[0].user_name == "Tech One"
        assert assignments[0].role == "lead"

    def test_remove_user_from_job(self, repo, full_setup):
        assignment = JobAssignment(
            job_id=full_setup["job_id"],
            user_id=full_setup["user_id"],
            role="worker",
        )
        aid = repo.assign_user_to_job(assignment)
        repo.remove_user_from_job(aid)

        assignments = repo.get_job_assignments(full_setup["job_id"])
        assert len(assignments) == 0


class TestNotifications:
    """Test notification creation and retrieval."""

    def test_create_notification(self, repo):
        # Create a user first (needed for queries)
        user = User(
            username="notifuser", display_name="Notif User",
            pin_hash=Repository.hash_pin("1234"),
            role="user", is_active=1,
        )
        uid = repo.create_user(user)

        notif = Notification(
            user_id=uid,
            title="Low Stock Alert",
            message="Wire is below minimum",
            severity="warning",
            source="audit_agent",
        )
        nid = repo.create_notification(notif)
        assert nid > 0

        # Should appear in user's notifications
        notifs = repo.get_user_notifications(uid)
        assert len(notifs) >= 1
        assert notifs[0].title == "Low Stock Alert"

    def test_unread_count(self, repo):
        user = User(
            username="countuser", display_name="Count User",
            pin_hash=Repository.hash_pin("1234"),
            role="user", is_active=1,
        )
        uid = repo.create_user(user)

        assert repo.get_unread_count(uid) == 0

        repo.create_notification(Notification(
            user_id=uid, title="Test", message="msg",
            severity="info", source="system",
        ))
        assert repo.get_unread_count(uid) == 1

    def test_mark_all_read(self, repo):
        user = User(
            username="readuser", display_name="Read User",
            pin_hash=Repository.hash_pin("1234"),
            role="user", is_active=1,
        )
        uid = repo.create_user(user)

        repo.create_notification(Notification(
            user_id=uid, title="N1", message="m1",
            severity="info", source="system",
        ))
        repo.create_notification(Notification(
            user_id=uid, title="N2", message="m2",
            severity="warning", source="system",
        ))
        assert repo.get_unread_count(uid) == 2

        repo.mark_all_notifications_read(uid)
        assert repo.get_unread_count(uid) == 0

    def test_broadcast_notification(self, repo):
        """Notifications with user_id=None should be visible to all users."""
        user = User(
            username="bcast", display_name="Bcast",
            pin_hash=Repository.hash_pin("1234"),
            role="user", is_active=1,
        )
        uid = repo.create_user(user)

        repo.create_notification(Notification(
            user_id=None, title="System Alert", message="For everyone",
            severity="critical", source="system",
        ))

        notifs = repo.get_user_notifications(uid)
        assert len(notifs) >= 1
        assert any(n.title == "System Alert" for n in notifs)
