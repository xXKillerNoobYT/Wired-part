"""Tests for the bill_out_rate (BRO) category field on Jobs."""

import pytest

from wired_part.database.models import Job


class TestJobBillOutRate:
    """Verify bill_out_rate stores and retrieves BRO category codes."""

    def test_create_job_with_bro_category(self, repo):
        job = Job(
            job_number="BRO-001",
            name="Rate Test Job",
            customer="Test Corp",
            bill_out_rate="T&M",
        )
        job_id = repo.create_job(job)
        assert job_id > 0

        saved = repo.get_job_by_id(job_id)
        assert saved.bill_out_rate == "T&M"

    def test_create_job_default_bro_empty(self, repo):
        job = Job(
            job_number="BRO-002",
            name="No Rate Job",
        )
        job_id = repo.create_job(job)
        saved = repo.get_job_by_id(job_id)
        assert saved.bill_out_rate == ""

    def test_update_job_bro_category(self, repo):
        job = Job(
            job_number="BRO-003",
            name="Update Rate Job",
            bill_out_rate="C",
        )
        job_id = repo.create_job(job)

        saved = repo.get_job_by_id(job_id)
        saved.bill_out_rate = "SERVICE"
        repo.update_job(saved)

        updated = repo.get_job_by_id(job_id)
        assert updated.bill_out_rate == "SERVICE"

    def test_bro_in_all_jobs(self, repo):
        categories = ["C", "T&M", "EMERGENCY"]
        for i, cat in enumerate(categories):
            repo.create_job(Job(
                job_number=f"BRO-ALL-{i}",
                name=f"Job {i}",
                bill_out_rate=cat,
            ))

        jobs = repo.get_all_jobs()
        bro_jobs = [j for j in jobs if j.job_number.startswith("BRO-ALL")]
        rates = sorted(j.bill_out_rate for j in bro_jobs)
        assert rates == sorted(categories)

    def test_bro_category_is_string_type(self, repo):
        job = Job(
            job_number="BRO-TYPE",
            name="Type Check Job",
            bill_out_rate="EMERGENCY",
        )
        job_id = repo.create_job(job)
        saved = repo.get_job_by_id(job_id)
        assert isinstance(saved.bill_out_rate, str)

    def test_bro_can_be_cleared(self, repo):
        job = Job(
            job_number="BRO-CLR",
            name="Clear BRO Job",
            bill_out_rate="T&M",
        )
        job_id = repo.create_job(job)

        saved = repo.get_job_by_id(job_id)
        saved.bill_out_rate = ""
        repo.update_job(saved)

        updated = repo.get_job_by_id(job_id)
        assert updated.bill_out_rate == ""
