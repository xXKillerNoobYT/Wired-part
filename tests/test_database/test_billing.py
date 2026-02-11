"""Tests for billing cycles and periods."""

import pytest

from wired_part.database.models import (
    BillingCycle,
    BillingPeriod,
    Job,
    User,
)
from wired_part.database.repository import Repository


@pytest.fixture
def billing_data(repo):
    """Create test data for billing tests."""
    user = User(
        username="billing_user", display_name="Billing User",
        pin_hash=Repository.hash_pin("1234"),
        role="user", is_active=1,
    )
    user_id = repo.create_user(user)
    job = Job(
        job_number="JOB-BILL-001", name="Billing Test Job",
        status="active", address="123 Test St",
    )
    job_id = repo.create_job(job)
    return {"user_id": user_id, "job_id": job_id}


class TestBillingCycles:
    """Test billing cycle CRUD operations."""

    def test_create_cycle_for_job(self, repo, billing_data):
        cycle = repo.get_or_create_billing_cycle(
            job_id=billing_data["job_id"],
            cycle_type="monthly",
            billing_day=15,
        )
        assert cycle.id is not None
        assert cycle.job_id == billing_data["job_id"]
        assert cycle.cycle_type == "monthly"
        assert cycle.billing_day == 15

    def test_create_company_default_cycle(self, repo):
        cycle = repo.get_or_create_billing_cycle(
            job_id=None,
            cycle_type="weekly",
            billing_day=1,
        )
        assert cycle.id is not None
        assert cycle.job_id is None
        assert cycle.cycle_type == "weekly"

    def test_get_existing_cycle(self, repo, billing_data):
        cycle1 = repo.get_or_create_billing_cycle(
            job_id=billing_data["job_id"],
            cycle_type="monthly",
            billing_day=1,
        )
        cycle2 = repo.get_or_create_billing_cycle(
            job_id=billing_data["job_id"],
        )
        assert cycle1.id == cycle2.id

    def test_get_all_cycles(self, repo, billing_data):
        repo.get_or_create_billing_cycle(
            job_id=billing_data["job_id"],
            cycle_type="monthly",
        )
        repo.get_or_create_billing_cycle(
            job_id=None,
            cycle_type="weekly",
        )
        cycles = repo.get_billing_cycles()
        assert len(cycles) >= 2

    def test_cycle_types(self, repo, billing_data):
        for ctype in ["weekly", "biweekly", "monthly", "quarterly"]:
            jid = repo.create_job(Job(
                job_number=f"JOB-{ctype}",
                name=f"Job {ctype}",
                status="active",
            ))
            cycle = repo.get_or_create_billing_cycle(
                job_id=jid,
                cycle_type=ctype,
            )
            assert cycle.cycle_type == ctype


class TestBillingPeriods:
    """Test billing period operations."""

    def test_create_period(self, repo, billing_data):
        cycle = repo.get_or_create_billing_cycle(
            job_id=billing_data["job_id"],
            cycle_type="monthly",
        )
        period_id = repo.create_billing_period(
            cycle.id, "2025-01-01", "2025-01-31"
        )
        assert period_id > 0

    def test_get_periods(self, repo, billing_data):
        cycle = repo.get_or_create_billing_cycle(
            job_id=billing_data["job_id"],
            cycle_type="monthly",
        )
        repo.create_billing_period(cycle.id, "2025-01-01", "2025-01-31")
        repo.create_billing_period(cycle.id, "2025-02-01", "2025-02-28")

        periods = repo.get_billing_periods(cycle.id)
        assert len(periods) == 2
        assert periods[0].period_start == "2025-02-01"  # DESC order
        assert periods[1].period_start == "2025-01-01"

    def test_close_period(self, repo, billing_data):
        cycle = repo.get_or_create_billing_cycle(
            job_id=billing_data["job_id"],
            cycle_type="monthly",
        )
        period_id = repo.create_billing_period(
            cycle.id, "2025-01-01", "2025-01-31"
        )
        repo.close_billing_period(period_id)

        periods = repo.get_billing_periods(cycle.id)
        assert periods[0].status == "closed"

    def test_close_nonexistent_period_raises(self, repo):
        with pytest.raises(ValueError, match="not found"):
            repo.close_billing_period(99999)

    def test_period_has_joined_fields(self, repo, billing_data):
        cycle = repo.get_or_create_billing_cycle(
            job_id=billing_data["job_id"],
            cycle_type="quarterly",
        )
        repo.create_billing_period(cycle.id, "2025-01-01", "2025-03-31")

        periods = repo.get_billing_periods(cycle.id)
        assert periods[0].cycle_type == "quarterly"
        assert periods[0].job_number == "JOB-BILL-001"

    def test_get_billing_data_for_period(self, repo, billing_data):
        data = repo.get_billing_data_for_period(
            billing_data["job_id"], "2025-01-01", "2025-12-31"
        )
        assert "job" in data
        assert "categories" in data
        assert "subtotal" in data
