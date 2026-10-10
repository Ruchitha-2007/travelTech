import pytest
from datetime import datetime, timezone, timedelta
from route_engine import (
    densify_polyline, check_route_against_active_zones
)
from safety_engine import haversine_distance

def test_densify_polyline():
    # 2 points ~10 km apart
    p1 = (13.0, 80.0)
    p2 = (13.0, 80.09)  # approx 9.7 km
    raw = [p1, p2]
    
    # Step = 0.2 km (200 meters)
    dense = densify_polyline(raw, step_km=0.2)
    assert len(dense) > 40
    # Every consecutive point distance <= 0.25 km
    for i in range(len(dense) - 1):
        d = haversine_distance(dense[i][0], dense[i][1], dense[i+1][0], dense[i+1][1])
        assert d <= 0.25

def test_check_route_against_active_zones_with_arrival_time():
    now_utc = datetime(2026, 10, 10, 10, 0, 0, tzinfo=timezone.utc)
    
    # Route: start (13.0, 80.0) to end (13.2, 80.0), total duration 3600s (1 hour)
    sampled = [(13.0, 80.0), (13.1, 80.0), (13.2, 80.0)]
    duration_sec = 3600.0  # 1 hour
    
    # Midpoint (13.1, 80.0) reached around 10:30 UTC
    
    # Zone 1: Midpoint hazard, ACTIVE from 10:15 to 11:00 UTC (Crosses and hits!)
    zone_hitting = {
        "id": "zh",
        "type": "FLOOD",
        "severity": 3,
        "center_lat": 13.1,
        "center_lon": 80.0,
        "radius_km": 5.0,
        "start_time": now_utc + timedelta(minutes=15),
        "end_time": now_utc + timedelta(minutes=60),
        "source": "Open-Meteo"
    }

    # Zone 2: Hazard at midpoint that ends BEFORE user reaches it (ends at 10:15)
    zone_passed_early = {
        "id": "zp",
        "type": "FLOOD",
        "severity": 3,
        "center_lat": 13.1,
        "center_lon": 80.0,
        "radius_km": 5.0,
        "start_time": now_utc - timedelta(hours=1),
        "end_time": now_utc + timedelta(minutes=15),
        "source": "Open-Meteo"
    }

    # Case A: zone_hitting should be detected
    is_haz, crossed, segments = check_route_against_active_zones(sampled, duration_sec, [zone_hitting], now_utc)
    assert is_haz is True
    assert len(crossed) == 1
    assert crossed[0]["id"] == "zh"

    # Case B: zone_passed_early should NOT trigger because it expires before user reaches midpoint (10:30 > 10:15)
    is_haz_early, crossed_early, _ = check_route_against_active_zones(sampled, duration_sec, [zone_passed_early], now_utc)
    assert is_haz_early is False
    assert len(crossed_early) == 0
