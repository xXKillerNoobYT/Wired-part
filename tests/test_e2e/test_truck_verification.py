"""Tests for truck verification when consuming parts on a job.

Rules:
- Only trucks whose assigned user is also assigned to the job
  should appear in the consume-from-truck dropdown.
- If User A consumes from User B's truck on the same job,
  User B gets a notification.
- Trucks from unrelated jobs should NOT be selectable.
"""

import pytest

from wired_part.database.models import (
    Job, JobAssignment, Notification, Truck, TruckTransfer,
)


# ── helpers ────────────────────────────────────────────────────────
def _stock_truck(repo, truck_id, part_id, qty=20):
    """Put parts on a truck via warehouse transfer."""
    transfer = TruckTransfer(
        truck_id=truck_id,
        part_id=part_id,
        quantity=qty,
        direction="outbound",
        status="pending",
    )
    tid = repo.create_transfer(transfer)
    repo.receive_transfer(tid, received_by=1)


# ── Truck-for-job filtering ───────────────────────────────────────
class TestGetTrucksForJob:
    """get_trucks_for_job should only return trucks whose owner
    is assigned to that job."""

    def test_both_trucks_visible_on_shared_job(
        self, repo, active_job, truck_a, truck_b,
    ):
        """Admin and foreman are both on active_job → both trucks show."""
        trucks = repo.get_trucks_for_job(active_job.id)
        ids = {t.id for t in trucks}
        assert truck_a.id in ids
        assert truck_b.id in ids

    def test_unassigned_user_truck_excluded(
        self, repo, active_job, worker_user, truck_a, truck_b,
    ):
        """Worker is NOT assigned to active_job → worker's truck hidden."""
        worker_truck = Truck(
            truck_number="T-003",
            name="Worker Van",
            assigned_user_id=worker_user.id,
        )
        worker_truck.id = repo.create_truck(worker_truck)

        trucks = repo.get_trucks_for_job(active_job.id)
        ids = {t.id for t in trucks}
        assert truck_a.id in ids
        assert truck_b.id in ids
        assert worker_truck.id not in ids

    def test_different_job_isolates_trucks(
        self, repo, admin_user, foreman_user, worker_user,
        truck_a, truck_b,
    ):
        """Trucks from a different job's users don't leak into another."""
        # Create a second job with only the worker
        job2 = Job(
            job_number=repo.generate_job_number(),
            name="Other Job",
            customer="Other Customer",
            status="active",
        )
        job2.id = repo.create_job(job2)
        repo.assign_user_to_job(JobAssignment(
            job_id=job2.id, user_id=worker_user.id, role="lead",
        ))

        worker_truck = Truck(
            truck_number="T-004",
            name="Worker Special",
            assigned_user_id=worker_user.id,
        )
        worker_truck.id = repo.create_truck(worker_truck)

        # Job2 should only see the worker's truck
        trucks = repo.get_trucks_for_job(job2.id)
        ids = {t.id for t in trucks}
        assert worker_truck.id in ids
        assert truck_a.id not in ids  # admin not on job2
        assert truck_b.id not in ids  # foreman not on job2

    def test_inactive_truck_excluded(
        self, repo, active_job, admin_user, truck_a,
    ):
        """Inactive trucks are excluded even if the user is on the job."""
        truck_a_data = repo.get_truck_by_id(truck_a.id)
        truck_a_data.is_active = 0
        repo.update_truck(truck_a_data)

        trucks = repo.get_trucks_for_job(active_job.id)
        ids = {t.id for t in trucks}
        assert truck_a.id not in ids

    def test_truck_with_no_assigned_user_excluded(
        self, repo, active_job,
    ):
        """A truck with no assigned_user_id never matches any job."""
        orphan = Truck(
            truck_number="T-ORPHAN",
            name="Unassigned Truck",
            assigned_user_id=None,
        )
        orphan.id = repo.create_truck(orphan)

        trucks = repo.get_trucks_for_job(active_job.id)
        ids = {t.id for t in trucks}
        assert orphan.id not in ids

    def test_job_with_no_assignments_returns_empty(self, repo):
        """A job with zero user assignments → no trucks."""
        job = Job(
            job_number=repo.generate_job_number(),
            name="Empty Job",
            customer="Nobody",
            status="active",
        )
        job.id = repo.create_job(job)

        trucks = repo.get_trucks_for_job(job.id)
        assert trucks == []


# ── Cross-truck consumption notifications ─────────────────────────
class TestCrossTruckNotifications:
    """When User A consumes parts from User B's truck,
    User B should get a notification."""

    def test_consuming_own_truck_no_notification(
        self, repo, active_job, admin_user, truck_a, parts,
    ):
        """Admin consumes from their own truck → no notification."""
        wire = parts[0]
        _stock_truck(repo, truck_a.id, wire.id, 10)

        # Clear any existing notifications
        existing = repo.get_user_notifications(admin_user.id)

        repo.consume_from_truck(
            job_id=active_job.id, truck_id=truck_a.id,
            part_id=wire.id, quantity=2, user_id=admin_user.id,
        )

        # Admin should NOT get a "consumed from your truck" notification
        notifs = repo.get_user_notifications(admin_user.id, unread_only=True)
        consumption_notifs = [
            n for n in notifs if "consumed from your truck" in n.title.lower()
        ]
        assert len(consumption_notifs) == 0

    def test_consuming_other_user_truck_sends_notification(
        self, repo, active_job, admin_user, foreman_user,
        truck_b, parts,
    ):
        """Admin consumes from foreman's truck → foreman gets notified."""
        wire = parts[0]
        _stock_truck(repo, truck_b.id, wire.id, 10)

        repo.consume_from_truck(
            job_id=active_job.id, truck_id=truck_b.id,
            part_id=wire.id, quantity=3, user_id=admin_user.id,
        )

        # Foreman should get a notification
        notifs = repo.get_user_notifications(
            foreman_user.id, unread_only=True,
        )
        consumption_notifs = [
            n for n in notifs
            if "consumed from your truck" in n.title.lower()
        ]
        assert len(consumption_notifs) == 1

        notif = consumption_notifs[0]
        assert "Admin Boss" in notif.message
        assert "3" in notif.message  # quantity
        assert wire.part_number in notif.message
        assert notif.user_id == foreman_user.id
        assert notif.target_tab == "trucks"

    def test_notification_includes_job_info(
        self, repo, active_job, admin_user, foreman_user,
        truck_b, parts,
    ):
        """Notification message includes the job reference."""
        outlet = parts[3]
        _stock_truck(repo, truck_b.id, outlet.id, 20)

        repo.consume_from_truck(
            job_id=active_job.id, truck_id=truck_b.id,
            part_id=outlet.id, quantity=5, user_id=admin_user.id,
        )

        notifs = repo.get_user_notifications(
            foreman_user.id, unread_only=True,
        )
        consumption_notifs = [
            n for n in notifs
            if "consumed from your truck" in n.title.lower()
        ]
        assert len(consumption_notifs) == 1
        assert active_job.name in consumption_notifs[0].message

    def test_multiple_consumptions_multiple_notifications(
        self, repo, active_job, admin_user, foreman_user,
        truck_b, parts,
    ):
        """Multiple consumption events → multiple notifications."""
        wire = parts[0]
        breaker = parts[2]
        _stock_truck(repo, truck_b.id, wire.id, 10)
        _stock_truck(repo, truck_b.id, breaker.id, 10)

        repo.consume_from_truck(
            job_id=active_job.id, truck_id=truck_b.id,
            part_id=wire.id, quantity=2, user_id=admin_user.id,
        )
        repo.consume_from_truck(
            job_id=active_job.id, truck_id=truck_b.id,
            part_id=breaker.id, quantity=1, user_id=admin_user.id,
        )

        notifs = repo.get_user_notifications(
            foreman_user.id, unread_only=True,
        )
        consumption_notifs = [
            n for n in notifs
            if "consumed from your truck" in n.title.lower()
        ]
        assert len(consumption_notifs) == 2

    def test_no_notification_when_no_user_id(
        self, repo, active_job, foreman_user, truck_b, parts,
    ):
        """If consume is called without user_id, no notification sent."""
        wire = parts[0]
        _stock_truck(repo, truck_b.id, wire.id, 10)

        repo.consume_from_truck(
            job_id=active_job.id, truck_id=truck_b.id,
            part_id=wire.id, quantity=1, user_id=None,
        )

        notifs = repo.get_user_notifications(
            foreman_user.id, unread_only=True,
        )
        consumption_notifs = [
            n for n in notifs
            if "consumed from your truck" in n.title.lower()
        ]
        assert len(consumption_notifs) == 0
