"""Tests for job location caching and proximity checks."""

import pytest

from wired_part.database.models import Job, JobLocation
from wired_part.database.repository import Repository


@pytest.fixture
def geo_data(repo):
    """Create a job for geolocation tests."""
    job = Job(
        job_number="JOB-GEO-001", name="Geo Test Job",
        status="active", address="350 5th Ave, New York, NY",
    )
    job_id = repo.create_job(job)
    return {"job_id": job_id}


class TestJobLocationCRUD:
    """Test job location caching."""

    def test_set_and_get_location(self, repo, geo_data):
        loc = JobLocation(
            job_id=geo_data["job_id"],
            latitude=40.7484,
            longitude=-73.9857,
            geocoded_address="350 5th Ave, New York, NY 10118",
        )
        repo.set_job_location(loc)

        fetched = repo.get_job_location(geo_data["job_id"])
        assert fetched is not None
        assert abs(fetched.latitude - 40.7484) < 0.001
        assert abs(fetched.longitude - (-73.9857)) < 0.001

    def test_update_location(self, repo, geo_data):
        repo.set_job_location(JobLocation(
            job_id=geo_data["job_id"],
            latitude=40.0, longitude=-74.0,
        ))
        # Update with new coordinates
        repo.set_job_location(JobLocation(
            job_id=geo_data["job_id"],
            latitude=41.0, longitude=-75.0,
        ))
        fetched = repo.get_job_location(geo_data["job_id"])
        assert abs(fetched.latitude - 41.0) < 0.001
        assert abs(fetched.longitude - (-75.0)) < 0.001

    def test_get_location_not_found(self, repo):
        loc = repo.get_job_location(9999)
        assert loc is None

    def test_delete_location(self, repo, geo_data):
        repo.set_job_location(JobLocation(
            job_id=geo_data["job_id"],
            latitude=40.0, longitude=-74.0,
        ))
        repo.delete_job_location(geo_data["job_id"])
        assert repo.get_job_location(geo_data["job_id"]) is None


class TestProximityCheck:
    """Test geofence proximity checking."""

    def test_within_radius(self, repo, geo_data):
        # Set job location to Empire State Building
        repo.set_job_location(JobLocation(
            job_id=geo_data["job_id"],
            latitude=40.7484,
            longitude=-73.9857,
        ))
        # Check from very close point (~0.1 miles)
        result = repo.check_proximity(40.7490, -73.9860, geo_data["job_id"])
        assert result["within_radius"] is True
        assert result["distance_miles"] < 0.5

    def test_outside_radius(self, repo, geo_data):
        # Set job location to Empire State Building
        repo.set_job_location(JobLocation(
            job_id=geo_data["job_id"],
            latitude=40.7484,
            longitude=-73.9857,
        ))
        # Check from ~1 mile away
        result = repo.check_proximity(40.7600, -73.9700, geo_data["job_id"])
        assert result["within_radius"] is False
        assert result["distance_miles"] > 0.5

    def test_no_location_returns_true(self, repo, geo_data):
        """If no location is set, proximity check should pass."""
        result = repo.check_proximity(40.0, -74.0, geo_data["job_id"])
        assert result["within_radius"] is True
        assert result.get("no_location") is True
