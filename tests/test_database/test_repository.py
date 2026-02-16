"""Tests for the Repository layer."""

import pytest

from wired_part.database.models import Job, JobPart, Part


class TestCategorySeed:
    def test_default_categories_exist(self, repo):
        categories = repo.get_all_categories()
        names = [c.name for c in categories]
        assert "Wire & Cable" in names
        assert "Breakers & Fuses" in names
        assert len(categories) == 10


class TestPartsCRUD:
    def test_create_and_get_part(self, repo):
        part = Part(
            part_number="14-2-NM",
            description="14/2 Romex 250ft",
            quantity=10,
            unit_cost=89.99,
            location="Shelf A",
        )
        part_id = repo.create_part(part)
        assert part_id > 0

        fetched = repo.get_part_by_id(part_id)
        assert fetched.part_number == "14-2-NM"
        assert fetched.quantity == 10
        assert fetched.unit_cost == 89.99

    def test_get_part_by_number(self, repo):
        repo.create_part(Part(
            part_number="TEST-001",
            description="Test part",
            quantity=5,
        ))
        found = repo.get_part_by_number("TEST-001")
        assert found is not None
        assert found.description == "Test part"

    def test_update_part(self, repo):
        pid = repo.create_part(Part(
            part_number="UPD-001",
            description="Original",
            quantity=1,
        ))
        part = repo.get_part_by_id(pid)
        part.description = "Updated"
        part.quantity = 99
        repo.update_part(part)

        updated = repo.get_part_by_id(pid)
        assert updated.description == "Updated"
        assert updated.quantity == 99

    def test_delete_part(self, repo):
        pid = repo.create_part(Part(
            part_number="DEL-001",
            description="To delete",
            quantity=1,
        ))
        repo.delete_part(pid)
        assert repo.get_part_by_id(pid) is None

    def test_can_delete_part_no_references(self, repo):
        pid = repo.create_part(Part(
            part_number="CAN-DEL-001",
            description="No refs",
            quantity=0,
        ))
        can, reason = repo.can_delete_part(pid)
        assert can is True
        assert reason == ""

    def test_can_delete_part_blocked_by_truck_inventory(self, repo):
        from wired_part.database.models import Truck
        pid = repo.create_part(Part(
            part_number="CAN-DEL-002",
            description="On truck",
            quantity=10,
        ))
        truck = Truck(name="Test Truck", truck_number="T-100")
        truck.id = repo.create_truck(truck)
        repo.add_to_truck_inventory(truck.id, pid, 5)
        can, reason = repo.can_delete_part(pid)
        assert can is False
        assert "truck" in reason.lower()

    def test_can_delete_part_blocked_by_active_job(self, repo):
        from wired_part.database.models import Job
        pid = repo.create_part(Part(
            part_number="CAN-DEL-003",
            description="On job",
            quantity=10,
        ))
        job = Job(job_number="JOB-DEL-001", name="Del Job",
                  customer="Test", status="active")
        job.id = repo.create_job(job)
        # Directly insert a job_parts row to simulate consumption
        repo.db.execute(
            "INSERT INTO job_parts (job_id, part_id, quantity_used, "
            "unit_cost_at_use) VALUES (?, ?, 3, 5.00)",
            (job.id, pid),
        )
        can, reason = repo.can_delete_part(pid)
        assert can is False
        assert "active job" in reason.lower()

    def test_delete_part_force_cleans_history(self, repo):
        """force=True removes FK child rows then the part."""
        from wired_part.database.models import Truck, User
        pid = repo.create_part(Part(
            part_number="FORCE-DEL-001",
            description="Force del",
            quantity=10,
        ))
        truck = Truck(name="FD Truck", truck_number="T-FD")
        truck.id = repo.create_truck(truck)
        user = User(username="fduser", display_name="FD User",
                    pin_hash="1234")
        user.id = repo.create_user(user)
        # Directly insert a truck_transfers row (FK RESTRICT on part_id)
        repo.db.execute(
            "INSERT INTO truck_transfers "
            "(part_id, truck_id, quantity, direction, status, created_by) "
            "VALUES (?, ?, 5, 'outbound', 'received', ?)",
            (pid, truck.id, user.id),
        )
        # Without force, this would raise IntegrityError
        repo.delete_part(pid, force=True)
        assert repo.get_part_by_id(pid) is None

    def test_delete_part_no_force_raises_with_fk(self, repo):
        """Without force, FK RESTRICT blocks deletion."""
        import sqlite3
        from wired_part.database.models import Truck, User
        pid = repo.create_part(Part(
            part_number="NOFRC-DEL-001",
            description="No force",
            quantity=10,
        ))
        truck = Truck(name="NF Truck", truck_number="T-NF")
        truck.id = repo.create_truck(truck)
        user = User(username="nfuser", display_name="NF User",
                    pin_hash="1234")
        user.id = repo.create_user(user)
        repo.db.execute(
            "INSERT INTO truck_transfers "
            "(part_id, truck_id, quantity, direction, status, created_by) "
            "VALUES (?, ?, 5, 'outbound', 'received', ?)",
            (pid, truck.id, user.id),
        )
        with pytest.raises(sqlite3.IntegrityError):
            repo.delete_part(pid)

    def test_search_parts(self, repo):
        repo.create_part(Part(
            part_number="ROMEX-14",
            description="14/2 Romex wire",
            quantity=5,
        ))
        repo.create_part(Part(
            part_number="EMT-34",
            description="3/4 EMT conduit",
            quantity=10,
        ))
        results = repo.search_parts("Romex")
        assert len(results) == 1
        assert results[0].part_number == "ROMEX-14"

    def test_low_stock_parts(self, repo):
        repo.create_part(Part(
            part_number="LOW-001",
            description="Low stock item",
            quantity=2,
            min_quantity=10,
        ))
        repo.create_part(Part(
            part_number="OK-001",
            description="Sufficient stock",
            quantity=20,
            min_quantity=5,
        ))
        low = repo.get_low_stock_parts()
        assert len(low) == 1
        assert low[0].part_number == "LOW-001"


class TestJobsCRUD:
    def test_create_and_get_job(self, repo):
        job = Job(
            job_number="JOB-2026-001",
            name="Kitchen Remodel",
            customer="John Smith",
            status="active",
        )
        jid = repo.create_job(job)
        assert jid > 0

        fetched = repo.get_job_by_id(jid)
        assert fetched.name == "Kitchen Remodel"
        assert fetched.status == "active"

    def test_generate_job_number(self, repo):
        num = repo.generate_job_number()
        assert num.startswith("JOB-2026-") or num.startswith("JOB-")
        assert num.endswith("001")

    def test_filter_jobs_by_status(self, repo):
        repo.create_job(Job(
            job_number="JOB-A", name="Active", status="active"
        ))
        repo.create_job(Job(
            job_number="JOB-C", name="Completed", status="completed"
        ))
        active = repo.get_all_jobs("active")
        assert len(active) == 1
        assert active[0].job_number == "JOB-A"


class TestJobParts:
    def test_assign_and_deduct(self, repo):
        pid = repo.create_part(Part(
            part_number="JP-001",
            description="Test part",
            quantity=10,
            unit_cost=5.00,
        ))
        jid = repo.create_job(Job(
            job_number="JP-JOB-001", name="Test Job", status="active"
        ))

        jp = JobPart(job_id=jid, part_id=pid, quantity_used=3)
        repo.assign_part_to_job(jp)

        # Check stock deducted
        part = repo.get_part_by_id(pid)
        assert part.quantity == 7

        # Check assignment recorded
        assigned = repo.get_job_parts(jid)
        assert len(assigned) == 1
        assert assigned[0].quantity_used == 3
        assert assigned[0].unit_cost_at_use == 5.00

    def test_insufficient_stock_raises(self, repo):
        pid = repo.create_part(Part(
            part_number="JP-002",
            description="Scarce part",
            quantity=2,
        ))
        jid = repo.create_job(Job(
            job_number="JP-JOB-002", name="Test", status="active"
        ))

        jp = JobPart(job_id=jid, part_id=pid, quantity_used=5)
        with pytest.raises(ValueError, match="Insufficient stock"):
            repo.assign_part_to_job(jp)

    def test_remove_restores_stock(self, repo):
        pid = repo.create_part(Part(
            part_number="JP-003",
            description="Removable part",
            quantity=10,
        ))
        jid = repo.create_job(Job(
            job_number="JP-JOB-003", name="Test", status="active"
        ))

        jp = JobPart(job_id=jid, part_id=pid, quantity_used=4)
        repo.assign_part_to_job(jp)

        assigned = repo.get_job_parts(jid)
        repo.remove_part_from_job(assigned[0].id)

        part = repo.get_part_by_id(pid)
        assert part.quantity == 10  # restored

    def test_job_total_cost(self, repo):
        pid = repo.create_part(Part(
            part_number="JP-004",
            description="Costed part",
            quantity=20,
            unit_cost=12.50,
        ))
        jid = repo.create_job(Job(
            job_number="JP-JOB-004", name="Cost Test", status="active"
        ))

        jp = JobPart(job_id=jid, part_id=pid, quantity_used=4)
        repo.assign_part_to_job(jp)

        total = repo.get_job_total_cost(jid)
        assert total == 50.00


class TestSummaries:
    def test_inventory_summary(self, repo):
        repo.create_part(Part(
            part_number="SUM-001", description="A", quantity=10,
            unit_cost=5.00, min_quantity=20,
        ))
        repo.create_part(Part(
            part_number="SUM-002", description="B", quantity=5,
            unit_cost=10.00,
        ))

        summary = repo.get_inventory_summary()
        assert summary["total_parts"] == 2
        assert summary["total_quantity"] == 15
        assert summary["total_value"] == 100.0  # 10*5 + 5*10
        assert summary["low_stock_count"] == 1
