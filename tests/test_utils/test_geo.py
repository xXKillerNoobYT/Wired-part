"""Tests for Haversine distance calculation."""

import pytest
from wired_part.utils.geo import haversine_miles


class TestHaversine:
    """Test the Haversine formula with known distances."""

    def test_same_point_is_zero(self):
        dist = haversine_miles(40.7128, -74.0060, 40.7128, -74.0060)
        assert dist == 0.0

    def test_new_york_to_los_angeles(self):
        # NYC to LA is approximately 2,451 miles
        dist = haversine_miles(40.7128, -74.0060, 34.0522, -118.2437)
        assert 2400 < dist < 2500

    def test_short_distance(self):
        # Two points ~0.3 miles apart in Manhattan
        dist = haversine_miles(40.7484, -73.9857, 40.7527, -73.9772)
        assert 0.1 < dist < 1.0

    def test_geofence_within_half_mile(self):
        # Points within 0.5 miles of each other
        # Empire State Building to nearby (~0.2 miles away)
        dist = haversine_miles(40.7484, -73.9857, 40.7500, -73.9870)
        assert dist < 0.5

    def test_geofence_outside_half_mile(self):
        # Points > 0.5 miles apart
        dist = haversine_miles(40.7484, -73.9857, 40.7600, -73.9700)
        assert dist > 0.5

    def test_north_south_pole(self):
        # North pole to south pole is approximately half earth circumference
        dist = haversine_miles(90, 0, -90, 0)
        assert 12400 < dist < 12500  # ~12,430 miles
